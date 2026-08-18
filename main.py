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
    Registers clean Telegram bot menu commands with multi-language (i18n) support.
    Defaults to English for global users and Russian for Russian Telegram clients.
    """
    commands_en = [
        BotCommand(command="chats", description="💬 Dialog branches & history"),
        BotCommand(command="project", description="📁 Workspace project explorer"),
        BotCommand(command="model", description="🧠 Switch model & thinking"),
        BotCommand(command="settings", description="⚙️ Settings, engine & language"),
        BotCommand(command="status", description="📊 Current session status"),
        BotCommand(command="help", description="❓ Feature manual & tips"),
    ]

    commands_ru = [
        BotCommand(command="chats", description="💬 Ветки диалогов и история"),
        BotCommand(command="project", description="📁 Выбрать проект на Mac"),
        BotCommand(command="model", description="🧠 Сменить модель & Thinking"),
        BotCommand(command="settings", description="⚙️ Настройки и обслуживание"),
        BotCommand(command="status", description="📊 Текущий статус"),
        BotCommand(command="help", description="❓ Справка по возможностям"),
    ]

    try:
        # 1. Global default (English) for international clients
        await bot.set_my_commands(commands_en)
        # 2. Explicit English
        await bot.set_my_commands(commands_en, language_code="en")
        # 3. Explicit Russian
        await bot.set_my_commands(commands_ru, language_code="ru")
        logger.info("Telegram menu commands registered successfully (EN default + RU).")
    except Exception as e:
        logger.warning(f"Failed to update Telegram commands menu: {e}")


async def main():
    logger.info("Starting Antigravity TG...")

    # Startup Safety Guard: ensure deny rules are intact on disk
    from src.engine.antigravity_bridge import ensure_deny_integrity
    ensure_deny_integrity()

    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "your_telegram_bot_token_here":
        logger.error(
            "\n❌ ERROR: BOT_TOKEN is missing in .env!\n"
            "1. Open .env\n"
            "2. Paste your token from @BotFather into BOT_TOKEN=\n"
            "3. Restart the bot: python main.py"
        )
        return

    bot = create_bot()
    dp = create_dispatcher()

    # Automatically register multi-language command menu
    await setup_bot_commands(bot)

    logger.info("Bot is ready. Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Bot session closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
