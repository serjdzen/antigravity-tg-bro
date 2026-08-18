import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.config import settings
from src.bot.middlewares.auth import AuthMiddleware
from src.bot.handlers.common import router as common_router
from src.bot.handlers.navigator import router as navigator_router
from src.bot.handlers.settings import router as settings_router
from src.bot.handlers.chats import router as chats_router
from src.bot.handlers.chat import router as chat_router

logger = logging.getLogger(__name__)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    # Регистрация middleware безопасности
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Подключение роутеров
    dp.include_router(common_router)
    dp.include_router(navigator_router)
    dp.include_router(settings_router)
    dp.include_router(chats_router)
    dp.include_router(chat_router)

    return dp


def create_bot() -> Bot:
    if not settings.BOT_TOKEN:
        logger.warning("BOT_TOKEN не задан в .env! Бот не сможет подключиться к Telegram.")
    return Bot(
        token=settings.BOT_TOKEN or "DUMMY_TOKEN",
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
