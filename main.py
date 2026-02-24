import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from ai.claude import ClaudeClient
from bot.handlers import start, solve, daily, stats, settings
from bot.middlewares import AllowedUserMiddleware, ServiceMiddleware
from bot.scheduler import setup_scheduler
from config import load_config, setup_logging
from db.database import init_db
from db.users import get_user
from leetcode.client import LeetCodeClient

logger = logging.getLogger(__name__)


async def main():
    config = load_config()
    setup_logging(config.log_level)

    logger.info("Starting LeetCode Bot...")

    await init_db(config.db_path)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Middleware
    dp.update.outer_middleware(AllowedUserMiddleware(config.allowed_telegram_id))
    dp.update.outer_middleware(ServiceMiddleware(config.db_path))

    # Create AI client
    ai_client = ClaudeClient(api_key=config.anthropic_api_key)

    # Create LeetCode client from stored cookies (if user exists)
    lc_client = None
    user = await get_user(config.db_path, config.allowed_telegram_id)
    if user and user.get("lc_session") and user.get("lc_csrf"):
        lc_client = LeetCodeClient(
            session_cookie=user["lc_session"],
            csrf_token=user["lc_csrf"],
            locale=user.get("locale", "ru"),
        )

    # Mutable dict so handlers can update lc_client on cookie refresh
    services = {"ai_client": ai_client, "lc_client": lc_client}
    dp["services"] = services

    # Include routers
    dp.include_router(start.router)
    dp.include_router(daily.router)
    dp.include_router(solve.router)
    dp.include_router(stats.router)
    dp.include_router(settings.router)

    # Set bot commands
    await bot.set_my_commands([
        BotCommand(command="daily", description="Daily problem"),
        BotCommand(command="random", description="Random problem"),
        BotCommand(command="problem", description="Problem by slug"),
        BotCommand(command="stats", description="Statistics"),
        BotCommand(command="settings", description="Settings"),
        BotCommand(command="skip", description="Skip problem"),
        BotCommand(command="cancel", description="Cancel session"),
    ])

    # Setup scheduler
    scheduler = setup_scheduler(bot, config.allowed_telegram_id, config.db_path)

    logger.info("Bot started successfully")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        lc = services.get("lc_client")
        if lc:
            await lc.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
