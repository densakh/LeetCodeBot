import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.i18n import I18n
from db.users import get_user

logger = logging.getLogger(__name__)


class AllowedUserMiddleware(BaseMiddleware):
    def __init__(self, allowed_id: int):
        self.allowed_id = allowed_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Update):
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user

        if user is None:
            return

        if user.id != self.allowed_id:
            logger.warning("Unauthorized access attempt from user %d", user.id)
            return

        return await handler(event, data)


class ServiceMiddleware(BaseMiddleware):
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db_path"] = self.db_path

        # Determine user ID for i18n
        user_obj = None
        if isinstance(event, Update):
            if event.message:
                user_obj = event.message.from_user
            elif event.callback_query:
                user_obj = event.callback_query.from_user

        locale = "ru"
        if user_obj:
            db_user = await get_user(self.db_path, user_obj.id)
            if db_user and db_user.get("locale"):
                locale = db_user["locale"]

        data["i18n"] = I18n(locale)

        return await handler(event, data)
