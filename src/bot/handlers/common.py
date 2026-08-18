from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from src.engine.session_manager import session_manager
from src.engine.uploads_manager import get_uploads_stats

router = Router(name="common_router")


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Добро пожаловать в Antigravity TG!</b>\n\n"
        "Управляйте локальной разработкой на Mac прямо из Telegram голосом, текстом и скриншотами.\n\n"
        "<b>Главные команды:</b>\n"
        "💬 /chats — Ветки диалогов и история\n"
        "📁 /project — Навигатор по папкам Mac\n"
        "🧠 /model — Выбор модели и Thinking Effort\n"
        "⚙️ /settings — Безопасность и очистка uploads\n"
        "📊 /status — Текущий статус сессии\n"
        "❓ /help — Подробная справка\n\n"
        "🎙 <i>Вы можете надиктовывать задачи голосовыми сообщениями, присылать скриншоты или скачивать файлы через <code>/get путь/к/файлу</code>.</i>",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Справка по возможностям Antigravity TG:</b>\n\n"
        "• <b>💬 Ветки диалогов:</b> /chats — создание новых веток, история и переименование.\n"
        "• <b>📁 Выбор проекта:</b> /project — проводник по папкам на Mac.\n"
        "• <b>🎙 Голосовые задачи:</b> Отправляйте голосовые сообщения — мгновенная расшифровка через Groq Whisper.\n"
        "• <b>📸 Фото и скриншоты:</b> Отправьте скриншот ошибки или макет с подписью — модель Gemini сразу проанализирует изображение.\n"
        "• <b>📥 Скачивание файлов:</b> <code>/get path/to/file.ext</code> — бот пришлет файл из проекта в Telegram.\n"
        "• <b>🛡 Безопасность:</b> /settings — включение/выключение подтверждений на опасные команды.\n"
        "• <b>🧠 Модели:</b> /model — выбор моделей (Gemini 3.7 Flash, Pro, Claude) и уровня Thinking.",
        parse_mode="HTML"
    )


@router.message(Command("status"))
async def cmd_status(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    active_chat = session.get_active_chat()
    files_count, files_mb = get_uploads_stats()

    engine_label = "🟣 Antigravity CLI (Google AI Pro ⚡)" if session.engine_mode == "cli" else "🟢 Python SDK (API Key ☁️)"
    safety_label = "🔒 Защита ВКЛ (Ask)" if session.safety_approval else "⚡ Защита ВЫКЛ (Full Auto)"

    await message.answer(
        "📊 <b>Текущий статус сессии:</b>\n\n"
        f"💬 <b>Активная ветка:</b> <code>{active_chat.title}</code>\n"
        f"📁 <b>Рабочий проект:</b> <code>{session.current_project_dir}</code>\n"
        f"🤖 <b>Модель:</b> <code>{session.current_model}</code> (Effort: <code>{session.reasoning_effort}</code>)\n"
        f"⚙️ <b>Движок:</b> {engine_label}\n"
        f"🛡 <b>Безопасность:</b> {safety_label}\n"
        f"📁 <b>Папка uploads:</b> {files_count} файлов ({files_mb:.1f} MB)\n"
        "🟢 <b>Статус:</b> Готов к работе 🚀",
        parse_mode="HTML"
    )
