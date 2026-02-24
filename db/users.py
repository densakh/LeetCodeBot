import json
import logging
from datetime import datetime, timezone

import aiosqlite

from db.database import get_connection

logger = logging.getLogger(__name__)


async def get_user(db_path: str, telegram_id: int) -> dict | None:
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def create_user(db_path: str, telegram_id: int, locale: str = "ru") -> None:
    async with get_connection(db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, locale, created_at) VALUES (?, ?, ?)",
            (telegram_id, locale, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def update_user(db_path: str, telegram_id: int, **fields) -> None:
    if "topics" in fields and isinstance(fields["topics"], list):
        fields["topics"] = json.dumps(fields["topics"])

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    values.append(telegram_id)

    async with get_connection(db_path) as db:
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE telegram_id = ?", values
        )
        await db.commit()


async def update_cookies(
    db_path: str, telegram_id: int, session: str, csrf: str
) -> None:
    async with get_connection(db_path) as db:
        await db.execute(
            "UPDATE users SET lc_session = ?, lc_csrf = ?, cookies_updated = ? WHERE telegram_id = ?",
            (session, csrf, datetime.now(timezone.utc).isoformat(), telegram_id),
        )
        await db.commit()


async def get_solved_slugs(db_path: str, telegram_id: int) -> list[str]:
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            "SELECT DISTINCT problem_slug FROM solved_problems WHERE telegram_id = ?",
            (telegram_id,),
        )
        rows = await cursor.fetchall()
        return [row["problem_slug"] for row in rows]


async def add_solved_problem(
    db_path: str,
    telegram_id: int,
    problem_slug: str,
    problem_id: int,
    difficulty: str,
    result: str,
    attempts: int,
) -> None:
    async with get_connection(db_path) as db:
        await db.execute(
            """INSERT INTO solved_problems
               (telegram_id, problem_slug, problem_id, difficulty, result, attempts, solved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                telegram_id,
                problem_slug,
                problem_id,
                difficulty,
                result,
                attempts,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()


async def get_stats(db_path: str, telegram_id: int) -> dict:
    async with get_connection(db_path) as db:
        # Total solved
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM solved_problems WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        total = row["total"]

        # By difficulty
        by_difficulty = {"Easy": 0, "Medium": 0, "Hard": 0}
        cursor = await db.execute(
            """SELECT difficulty, COUNT(*) as cnt
               FROM solved_problems WHERE telegram_id = ?
               GROUP BY difficulty""",
            (telegram_id,),
        )
        for row in await cursor.fetchall():
            if row["difficulty"] in by_difficulty:
                by_difficulty[row["difficulty"]] = row["cnt"]

        # Streak: count consecutive UTC days backwards from today
        cursor = await db.execute(
            """SELECT DISTINCT date(solved_at) as day
               FROM solved_problems WHERE telegram_id = ?
               ORDER BY day DESC""",
            (telegram_id,),
        )
        days = [row["day"] for row in await cursor.fetchall()]

        streak = 0
        if days:
            from datetime import date, timedelta

            today = datetime.now(timezone.utc).date()
            expected = today
            for day_str in days:
                day = date.fromisoformat(day_str)
                if day == expected:
                    streak += 1
                    expected -= timedelta(days=1)
                elif day < expected:
                    break

        # Favorite topics: top 3
        cursor = await db.execute(
            """SELECT sp.difficulty, sp.problem_slug
               FROM solved_problems sp WHERE sp.telegram_id = ?""",
            (telegram_id,),
        )
        # Get topics from solved problems by joining with sessions or just return empty
        # Since we don't store topics per problem in solved_problems, we use solve_sessions
        # Actually, let's track from the user's configured topics
        user = await get_user(db_path, telegram_id)
        topics_list = []
        if user and user.get("topics"):
            try:
                topics_list = json.loads(user["topics"])[:3]
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "total": total,
            "by_difficulty": by_difficulty,
            "streak": streak,
            "favorite_topics": topics_list,
        }


async def update_adaptive_difficulty(
    db_path: str, telegram_id: int, accepted: bool
) -> None:
    user = await get_user(db_path, telegram_id)
    if not user or user["difficulty"] != "Adaptive":
        return

    current = user["current_difficulty"] or "Easy"
    consecutive_solved = user["consecutive_solved"] or 0
    consecutive_failed = user["consecutive_failed"] or 0

    levels = ["Easy", "Medium", "Hard"]

    if accepted:
        consecutive_solved += 1
        consecutive_failed = 0

        if consecutive_solved >= 3:
            idx = levels.index(current)
            if idx < len(levels) - 1:
                current = levels[idx + 1]
            consecutive_solved = 0
    else:
        consecutive_failed += 1
        consecutive_solved = 0

        if consecutive_failed >= 2:
            idx = levels.index(current)
            if idx > 0:
                current = levels[idx - 1]
            consecutive_failed = 0

    await update_user(
        db_path,
        telegram_id,
        current_difficulty=current,
        consecutive_solved=consecutive_solved,
        consecutive_failed=consecutive_failed,
    )
