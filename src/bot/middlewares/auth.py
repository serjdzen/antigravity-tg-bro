import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from src.config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        allowed_ids = settings.allowed_ids_set

        # Если список разрешенных ID еще не настроен
        if not allowed_ids:
            if isinstance(event, Message):
                await event.answer(
                    f"⚠️ Бот еще не настроен!\n"
                    f"Добавьте ваш Telegram ID в файл `.env`:\n\n"
                    f"<code>ALLOWED_USER_IDS={user_id}</code>\n\n"
                    f"После этого перезапустите бота.",
                    parse_mode="HTML"
                )
            return

        # Если пользователь не в белом списке
        if user_id not in allowed_ids:
            logger.warning(f"Неавторизованная попытка доступа от ID: {user_id}")
            if isinstance(event, Message):
                await event.answer(
                    f"⛔ Доступ запрещен.\nВаш Telegram ID: <code>{user_id}</code>",
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещен.", show_alert=True)
            return

        return await handler(event, data)
