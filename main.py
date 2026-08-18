import asyncio
import logging
from aiogram.types import BotCommand
from src.config import settings
from src.bot.app import create_bot, create_dispatcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AntigravityTG")


async def setup_bot_commands(bot):
    """
    Чистый и лаконичный список команд для меню Telegram.
    Команды /new, /rename, /force работают, но вынесены из главного меню,
    так как доступны через интерактивные кнопки интерфейса.
    """
    commands = [
        BotCommand(command="chats", description="💬 Ветки диалогов и история"),
        BotCommand(command="project", description="📁 Выбрать проект на Mac"),
        BotCommand(command="model", description="🧠 Сменить модель & Thinking"),
        BotCommand(command="settings", description="⚙️ Настройки и обслуживание"),
        BotCommand(command="status", description="📊 Текущий статус"),
        BotCommand(command="help", description="❓ Справка по возможностям"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Команды меню Telegram бота успешно обновлены.")
    except Exception as e:
        logger.warning(f"Не удалось обновить меню команд в Telegram: {e}")


async def main():
    logger.info("Запуск Antigravity TG...")

    # Startup Safety Guard: гарантируем наличие правил Deny на диске
    from src.engine.antigravity_bridge import ensure_deny_integrity
    ensure_deny_integrity()

    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "your_telegram_bot_token_here":
        logger.error(
            "\n❌ ОШИБКА: BOT_TOKEN не указан в файле .env!\n"
            "1. Откройте файл .env\n"
            "2. Вставьте ваш токен бота от @BotFather в поле BOT_TOKEN=\n"
            "3. Перезапустите бота: python main.py"
        )
        return

    bot = create_bot()
    dp = create_dispatcher()

    # Автоматическое обновление меню команд в Telegram
    await setup_bot_commands(bot)

    logger.info("Бот готов к приему сообщений. Запуск polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
