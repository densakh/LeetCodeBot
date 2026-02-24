import os
from contextlib import asynccontextmanager

import aiosqlite


async def init_db(db_path: str = "data/bot.db") -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id        INTEGER PRIMARY KEY,
                lc_session         TEXT,
                lc_csrf            TEXT,
                lc_username        TEXT,
                preferred_lang     TEXT,
                difficulty         TEXT,
                current_difficulty TEXT,
                topics             TEXT,
                locale             TEXT DEFAULT 'ru',
                cookies_updated    TIMESTAMP,
                consecutive_solved INTEGER DEFAULT 0,
                consecutive_failed INTEGER DEFAULT 0,
                created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS solved_problems (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER,
                problem_slug    TEXT,
                problem_id      INTEGER,
                difficulty      TEXT,
                result          TEXT,
                attempts        INTEGER,
                solved_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS solve_sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER,
                problem_slug    TEXT,
                language        TEXT,
                user_approach   TEXT,
                current_code    TEXT,
                iteration       INTEGER DEFAULT 0,
                status          TEXT DEFAULT 'active',
                started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


@asynccontextmanager
async def get_connection(db_path: str = "data/bot.db"):
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        yield db
