import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.i18n import I18n
from bot.messages import fmt_stats
from db.users import get_user, get_stats

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: Message, i18n: I18n, db_path: str):
    user = await get_user(db_path, message.from_user.id)
    if not user:
        await message.answer(i18n.get("errors.not_configured"))
        return

    stats = await get_stats(db_path, message.from_user.id)
    text = fmt_stats(stats, i18n)
    await message.answer(text, parse_mode="HTML")
