from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from src.engine.session_manager import session_manager
from src.engine.uploads_manager import get_uploads_stats
from src.bot.locales import t

router = Router(name="common_router")


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    text = t("start_welcome", session.language)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    text = t("help_text", session.language)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    active_chat = session.get_active_chat()
    files_count, files_mb = get_uploads_stats()

    lang = session.language
    if session.engine_mode == "cli":
        engine_label = "🟣 Antigravity CLI (Google Account ⚡)" if lang == "en" else "🟣 Antigravity CLI (Google AI Pro ⚡)"
    else:
        engine_label = "🟢 Python SDK (Gemini API Key ☁️)" if lang == "en" else "🟢 Python SDK (API Key ☁️)"

    if session.safety_approval:
        safety_label = "🔒 ON (Ask)" if lang == "en" else "🔒 ВКЛ (Ask)"
    else:
        safety_label = "⚡ OFF (Full Auto)" if lang == "en" else "⚡ ВЫКЛ (Full Auto)"

    lang_label = "🇬🇧 English" if lang == "en" else "🇷🇺 Русский"

    text = t(
        "status_title",
        lang,
        chat_title=active_chat.title,
        project_dir=str(session.current_project_dir),
        model=session.current_model,
        effort=session.reasoning_effort,
        engine_label=engine_label,
        safety_label=safety_label,
        language_label=lang_label,
        files_count=files_count,
        files_mb=files_mb
    )

    await message.answer(text, parse_mode="HTML")


@router.message(Command("quota", "limits"))
@router.message(F.text.func(lambda text: bool(text and text.strip().casefold().rstrip("?!.,:;") in {
    "квота", "квоты", "лимит", "лимиты", "quota", "limits"
})))
async def cmd_quota(message: types.Message):
    from src.engine.quota_monitor import quota_monitor
    session = session_manager.get_session(message.from_user.id)
    report = quota_monitor.get_summary_report(lang=session.language)
    try:
        await message.answer(report, parse_mode="HTML")
    except Exception:
        await message.answer(report, parse_mode=None)
