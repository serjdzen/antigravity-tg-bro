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

logger = logging.getLogger(__name__)
router = Router(name="settings_router")


def format_featured_models_text(
    current_model: str,
    reasoning_effort: str
) -> str:
    effort_names = {
        "high": "Высокий (High 🧠)",
        "medium": "Средний (Medium ⚡)",
        "low": "Низкий (Low 🚀)",
        "off": "Выключен (Off ⏱)"
    }
    effort_str = effort_names.get(reasoning_effort, reasoning_effort)

    return (
        f"🧠 <b>Выбор AI-модели & Уровня Размышлений:</b>\n\n"
        f"🎯 <b>Активная модель:</b> <code>{current_model}</code>\n"
        f"💭 <b>Thinking Effort:</b> <code>{effort_str}</code>\n\n"
        f"⭐️ <b>Топ-модели (Google Gemini 3.x & Claude):</b>\n"
        f"<i>Нажмите на нужную модель для немедленного переключения:</i>"
    )


def format_all_models_text(current_model: str, total_models: int) -> str:
    return (
        f"🧠 <b>Полный список моделей API ({total_models}):</b>\n\n"
        f"🎯 <b>Активная модель:</b> <code>{current_model}</code>\n\n"
        f"<i>Листайте страницы кнопками ниже:</i>"
    )


def format_system_settings_text(
    safety_approval: bool,
    engine_mode: str,
    uploads_count: int,
    uploads_mb: float
) -> str:
    mode_label = "🟣 <b>Antigravity CLI</b> <i>(Подписка Google One AI Pro)</i>" if engine_mode == "cli" else "🟢 <b>Python SDK</b> <i>(API-ключ / Cloud)</i>"
    safety_label = "🔒 <b>ВКЛЮЧЕНА (Ask)</b> — опасные команды блокируются и требуют подтверждения кнопкой." if safety_approval else "⚡ <b>ВЫКЛЮЧЕНА (Full Auto)</b> — все команды выполняются сразу без вопросов."

    return (
        f"⚙️ <b>Системные Настройки & Обслуживание:</b>\n\n"
        f"🛡 <b>Режим безопасности:</b>\n{safety_label}\n\n"
        f"⚙️ <b>Движок выполнения:</b>\n{mode_label}\n\n"
        f"📁 <b>Временные загрузки (uploads):</b>\n"
        f"• Файлов в очереди: <b>{uploads_count} шт.</b> ({uploads_mb:.1f} MB)\n\n"
        f"<i>Используйте кнопки для управления параметрами:</i>"
    )


@router.message(Command("model"))
async def cmd_model(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    kb = build_featured_models_keyboard(
        session.current_model,
        session.reasoning_effort
    )
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    files_count, files_mb = get_uploads_stats()
    kb = build_system_settings_keyboard(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        uploads_count=files_count,
        uploads_mb=files_mb
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        uploads_count=files_count,
        uploads_mb=files_mb
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
        uploads_count=files_count,
        uploads_mb=files_mb
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        uploads_count=files_count,
        uploads_mb=files_mb
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    state_str = "ВКЛЮЧЕНА (Ask)" if session.safety_approval else "ВЫКЛЮЧЕНА (Full Auto)"
    await callback.answer(f"Защита: {state_str}")


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
        uploads_count=files_count,
        uploads_mb=files_mb
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        uploads_count=files_count,
        uploads_mb=files_mb
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    mode_name = "Antigravity CLI (Google AI Pro)" if new_mode == "cli" else "Python SDK (API Key)"
    await callback.answer(f"Движок: {mode_name}")


@router.callback_query(F.data == "clean_uploads")
async def cb_clean_uploads(callback: types.CallbackQuery):
    deleted_count = clean_uploads_dir()
    session = session_manager.get_session(callback.from_user.id)
    files_count, files_mb = get_uploads_stats()

    kb = build_system_settings_keyboard(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        uploads_count=files_count,
        uploads_mb=files_mb
    )
    text = format_system_settings_text(
        safety_approval=session.safety_approval,
        engine_mode=session.engine_mode,
        uploads_count=files_count,
        uploads_mb=files_mb
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer(f"🧹 Удалено {deleted_count} временных файлов!", show_alert=True)


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
        session.reasoning_effort
    )
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer(f"Уровень размышлений: {next_effort.upper()}")


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
        session.reasoning_effort
    )
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer(f"Модель: {model_id}")


@router.callback_query(F.data == "mod_view:featured")
async def cb_view_featured(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    kb = build_featured_models_keyboard(
        session.current_model,
        session.reasoning_effort
    )
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort
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

    kb, page, total_pages = build_all_models_keyboard(session.current_model, page=page_num)
    all_models = get_all_models()
    text = format_all_models_text(session.current_model, len(all_models))

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("mod_page:"))
async def cb_mod_page(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    page_num = int(callback.data.split(":")[1])

    kb, page, total_pages = build_all_models_keyboard(session.current_model, page=page_num)
    all_models = get_all_models()
    text = format_all_models_text(session.current_model, len(all_models))

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
        session.reasoning_effort
    )
    all_models = get_all_models(force_refresh=True)
    text = format_featured_models_text(
        session.current_model,
        session.reasoning_effort
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer("🔄 Список моделей обновлен из API!", show_alert=True)


@router.callback_query(F.data == "mod_noop")
async def cb_mod_noop(callback: types.CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "settings_close")
async def cb_settings_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Закрыто")


@router.message(Command("mcp"))
async def cmd_mcp(message: types.Message):
    summary = get_mcp_summary()

    if not summary:
        await message.answer("🔌 <b>Подключенные MCP-серверы:</b>\n\n<i>Серверы не найдены в конфигурации.</i>", parse_mode="HTML")
        return

    lines = [f"🔌 <b>Подключенные MCP-серверы ({len(summary)}):</b>\n"]
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

    if not skills:
        await message.answer("🧩 <b>Локальные скиллы:</b>\n\n<i>Скиллы не найдены.</i>", parse_mode="HTML")
        return

    lines = [f"🧩 <b>Обнаруженные скиллы Antigravity ({len(skills)}):</b>\n"]
    for idx, (name, desc) in enumerate(sorted(skills.items()), 1):
        clean_desc = desc if len(desc) <= 90 else desc[:87] + "..."
        lines.append(f"<b>{idx}. <code>{name}</code></b> — {clean_desc}")

    text = "\n".join(lines)
    chunks = split_message(text, max_chars=3900)
    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")
