import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from src.engine.session_manager import session_manager
from src.engine.mcp_loader import get_mcp_summary
from src.engine.skills_loader import get_skills_summary
from src.engine.models_loader import get_all_models
from src.engine.uploads_manager import get_uploads_stats, clean_uploads_dir
from src.bot.keyboards.settings_kb import (
    build_featured_models_keyboard,
    build_all_models_keyboard,
    build_system_settings_keyboard
)
from src.bot.utils.formatter import split_message
from src.bot.locales import t

logger = logging.getLogger(__name__)
router = Router(name="settings_router")


def format_featured_models_text(
    current_model: str,
    reasoning_effort: str,
    lang: str = "en"
) -> str:
    if lang == "ru":
        effort_names = {
            "high": "Высокий (High 🧠)",
            "medium": "Средний (Medium ⚡)",
            "low": "Низкий (Low 🚀)",
            "off": "Выключен (Off ⏱)"
        }
    else:
        effort_names = {
            "high": "High 🧠",
            "medium": "Medium ⚡",
            "low": "Low 🚀",
            "off": "Off ⏱"
        }
    effort_str = effort_names.get(reasoning_effort, reasoning_effort)

    return t("featured_models_title", lang, model=current_model, effort=effort_str)


def format_all_models_text(current_model: str, total_models: int, lang: str = "en") -> str:
    return t("all_models_title", lang, model=current_model, count=total_models)


def format_system_settings_text(
    safety_approval: bool,
    engine_mode: str,
    queue_mode: str = "queue",
    uploads_count: int = 0,
    uploads_mb: float = 0.0,
    lang: str = "en"
) -> str:
    safety_desc = t("safety_ask_desc" if safety_approval else "safety_auto_desc", lang)
    queue_desc = t("queue_on_desc" if queue_mode == "queue" else "queue_off_desc", lang)
    engine_desc = t("engine_cli_desc" if engine_mode == "cli" else "engine_sdk_desc", lang)
    lang_name = "English 🇬🇧" if lang == "en" else "Русский 🇷🇺"

    return t(
        "settings_title",
        lang,
        safety_desc=safety_desc,
        queue_desc=queue_desc,
        engine_desc=engine_desc,
        lang_name=lang_name,
        uploads_count=uploads_count,
        uploads_mb=uploads_mb
    )


@router.message(Command("model"))
async def cmd_model(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    kb = build_featured_models_keyboard(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    files_count, files_mb = get_uploads_stats()
    kb = build_system_settings_keyboard(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "toggle_safety")
async def cb_toggle_safety(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    session.safety_approval = not session.safety_approval
    session_manager.save_to_disk()

    files_count, files_mb = get_uploads_stats()
    kb = build_system_settings_keyboard(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    state_str = "ON (Ask)" if session.safety_approval else "OFF (Full Auto)"
    await callback.answer(f"Security: {state_str}")


@router.callback_query(F.data == "toggle_queue")
async def cb_toggle_queue(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    session.queue_mode = "block" if session.queue_mode == "queue" else "queue"
    session_manager.save_to_disk()

    files_count, files_mb = get_uploads_stats()
    kb = build_system_settings_keyboard(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    state_str = "ON (Queue)" if session.queue_mode == "queue" else "OFF (Block)"
    await callback.answer(f"Queue: {state_str}")


@router.callback_query(F.data == "toggle_language")
async def cb_toggle_language(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    session.language = "ru" if session.language == "en" else "en"
    session_manager.save_to_disk()

    files_count, files_mb = get_uploads_stats()
    kb = build_system_settings_keyboard(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    lang_notice = "Язык переключен на Русский 🇷🇺" if session.language == "ru" else "Language switched to English 🇬🇧"
    await callback.answer(lang_notice, show_alert=False)


@router.callback_query(F.data.startswith("toggle_engine:"))
async def cb_toggle_engine(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    new_mode = callback.data.split(":")[1]
    session.engine_mode = new_mode
    session_manager.save_to_disk()

    files_count, files_mb = get_uploads_stats()
    kb = build_system_settings_keyboard(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    mode_name = "Antigravity CLI" if new_mode == "cli" else "Python SDK"
    await callback.answer(f"Engine: {mode_name}")


@router.callback_query(F.data == "clean_uploads")
async def cb_clean_uploads(callback: types.CallbackQuery):
    deleted_count = clean_uploads_dir()
    session = session_manager.get_session(callback.from_user.id)
    files_count, files_mb = get_uploads_stats()

    kb = build_system_settings_keyboard(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        queue_mode=session.queue_mode,
        uploads_count=files_count,
        uploads_mb=files_mb,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    alert_msg = t("alert_uploads_cleaned", session.language, count=deleted_count)
    await callback.answer(alert_msg, show_alert=True)


@router.callback_query(F.data == "toggle_effort")
async def cb_toggle_effort(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    cycle = ["low", "medium", "high", "off"]
    cur_idx = cycle.index(session.reasoning_effort) if session.reasoning_effort in cycle else 0
    next_effort = cycle[(cur_idx + 1) % len(cycle)]
    session.reasoning_effort = next_effort

    active_chat = session.get_active_chat()
    active_chat.effort = next_effort
    session_manager.save_to_disk()

    kb = build_featured_models_keyboard(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer(f"Thinking Effort: {next_effort.upper()}")


@router.callback_query(F.data.startswith("set_model:"))
async def cb_set_model(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    model_id = callback.data.split(":", 1)[1]
    session.current_model = model_id

    active_chat = session.get_active_chat()
    active_chat.model = model_id
    session_manager.save_to_disk()

    kb = build_featured_models_keyboard(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer(f"Model: {model_id}")


@router.callback_query(F.data == "mod_view:featured")
async def cb_view_featured(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    kb = build_featured_models_keyboard(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("mod_view:all:"))
async def cb_view_all(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    page_num = int(callback.data.split(":")[2])

    kb, page, total_pages = build_all_models_keyboard(session.current_model, page=page_num, lang=session.language)
    all_models = get_all_models()
    text = format_all_models_text(session.current_model, len(all_models), lang=session.language)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("mod_page:"))
async def cb_mod_page(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    page_num = int(callback.data.split(":")[1])

    kb, page, total_pages = build_all_models_keyboard(session.current_model, page=page_num, lang=session.language)
    all_models = get_all_models()
    text = format_all_models_text(session.current_model, len(all_models), lang=session.language)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "mod_refresh")
async def cb_mod_refresh(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    kb = build_featured_models_keyboard(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )
    all_models = get_all_models(force_refresh=True)
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort,
        lang=session.language
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    notice = "Models catalog refreshed!" if session.language == "en" else "Список моделей обновлен из API!"
    await callback.answer(f"🔄 {notice}", show_alert=True)


@router.callback_query(F.data == "mod_noop")
async def cb_mod_noop(callback: types.CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "settings_close")
async def cb_settings_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@router.message(Command("mcp"))
async def cmd_mcp(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    summary = get_mcp_summary()
    lang = session.language

    if not summary:
        msg = "🔌 <b>Connected MCP Servers:</b>\n\n<i>No MCP servers configured.</i>" if lang == "en" else "🔌 <b>Подключенные MCP-серверы:</b>\n\n<i>Серверы не найдены в конфигурации.</i>"
        await message.answer(msg, parse_mode="HTML")
        return

    header = f"🔌 <b>Connected MCP Servers ({len(summary)}):</b>\n" if lang == "en" else f"🔌 <b>Подключенные MCP-серверы ({len(summary)}):</b>\n"
    lines = [header]
    for idx, (name, details) in enumerate(summary.items(), 1):
        lines.append(f"<b>{idx}. {name}</b> ({details})")

    text = "\n".join(lines)
    chunks = split_message(text, max_chars=3900)
    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")


@router.message(Command("skills"))
async def cmd_skills(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    skills = get_skills_summary(session.current_project_dir)
    lang = session.language

    if not skills:
        msg = "🧩 <b>Local Skills:</b>\n\n<i>No skills found in workspace.</i>" if lang == "en" else "🧩 <b>Локальные скиллы:</b>\n\n<i>Скиллы не найдены.</i>"
        await message.answer(msg, parse_mode="HTML")
        return

    header = f"🧩 <b>Discovered Antigravity Skills ({len(skills)}):</b>\n" if lang == "en" else f"🧩 <b>Обнаруженные скиллы Antigravity ({len(skills)}):</b>\n"
    lines = [header]
    for idx, (name, desc) in enumerate(sorted(skills.items()), 1):
        clean_desc = desc if len(desc) <= 90 else desc[:87] + "..."
        lines.append(f"<b>{idx}. <code>{name}</code></b> — {clean_desc}")

    text = "\n".join(lines)
    chunks = split_message(text, max_chars=3900)
    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")
