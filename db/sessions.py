import logging
from datetime import datetime, timezone, timedelta

import aiosqlite

from db.database import get_connection

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_HOURS = 24


async def create_session(
    db_path: str, telegram_id: int, problem_slug: str
) -> int:
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """INSERT INTO solve_sessions (telegram_id, problem_slug, status, started_at)
               VALUES (?, ?, 'active', ?)""",
            (telegram_id, problem_slug, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_session(db_path: str, telegram_id: int) -> dict | None:
    async with get_connection(db_path) as db:
        cursor = await db.execute(
            """SELECT * FROM solve_sessions
               WHERE telegram_id = ? AND status = 'active'
               ORDER BY started_at DESC LIMIT 1""",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def update_session(db_path: str, session_id: int, **fields) -> None:
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    values.append(session_id)

    async with get_connection(db_path) as db:
        await db.execute(
            f"UPDATE solve_sessions SET {set_clause} WHERE id = ?", values
        )
        await db.commit()


async def cancel_session(db_path: str, session_id: int) -> None:
    await update_session(db_path, session_id, status="cancelled")


async def skip_session(db_path: str, session_id: int) -> None:
    await update_session(db_path, session_id, status="skipped")


async def complete_session(db_path: str, session_id: int) -> None:
    await update_session(db_path, session_id, status="completed")


async def check_session_timeout(db_path: str, telegram_id: int) -> bool:
    session = await get_active_session(db_path, telegram_id)
    if session is None:
        return False

    started = datetime.fromisoformat(session["started_at"])
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - started > timedelta(hours=SESSION_TIMEOUT_HOURS):
        await cancel_session(db_path, session["id"])
        return True

    return False
