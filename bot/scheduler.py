import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.i18n import I18n
from config import COOKIE_INSTRUCTION_RU, COOKIE_INSTRUCTION_EN
from db.users import get_user

logger = logging.getLogger(__name__)


async def check_cookie_freshness(bot: Bot, telegram_id: int, db_path: str):
    user = await get_user(db_path, telegram_id)
    if not user or not user.get("cookies_updated"):
        return

    updated = datetime.fromisoformat(user["cookies_updated"])
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - updated > timedelta(days=5):
        locale = user.get("locale", "ru")
        i18n = I18n(locale)
        await bot.send_message(
            telegram_id,
            i18n.get("cookie.reminder"),
        )
        logger.info("Sent cookie freshness reminder to %d", telegram_id)


def setup_scheduler(bot: Bot, telegram_id: int, db_path: str) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_cookie_freshness,
        "cron",
        hour=12,
        minute=0,
        args=[bot, telegram_id, db_path],
        id="cookie_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")
    return scheduler
