import logging
from pathlib import Path
from aiogram import Router, types, F
from aiogram.filters import Command
from src.engine.session_manager import session_manager
from src.bot.keyboards.navigator_kb import (
    build_navigator_keyboard,
    get_subdirectories,
    ITEMS_PER_PAGE
)

logger = logging.getLogger(__name__)
router = Router(name="navigator_router")


def format_navigator_text(current_project: Path, browse_dir: Path) -> str:
    return (
        f"📁 <b>Файловый проводник проектов</b>\n\n"
        f"🎯 <b>Активный проект:</b>\n<code>{current_project}</code>\n\n"
        f"🔍 <b>Просмотр папки:</b>\n<code>{browse_dir}</code>\n\n"
        f"<i>Выберите подпапку или нажмите «Выбрать эту папку»:</i>"
    )


@router.message(Command("project"))
async def cmd_project(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    session.navigation_dir = session.current_project_dir
    session.navigation_page = 0

    kb, page, total_pages = build_navigator_keyboard(session.navigation_dir, session.navigation_page)
    text = format_navigator_text(session.current_project_dir, session.navigation_dir)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("nav_sel:"))
async def cb_nav_select(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    idx = int(callback.data.split(":")[1])

    subdirs = get_subdirectories(session.navigation_dir)
    start_idx = session.navigation_page * ITEMS_PER_PAGE
    target_idx = start_idx + idx

    if 0 <= target_idx < len(subdirs):
        target_dir = subdirs[target_idx]
        try:
            # Проверяем доступность
            list(target_dir.iterdir())
            session.navigation_dir = target_dir
            session.navigation_page = 0
        except PermissionError:
            await callback.answer("⚠️ Нет прав доступа к этой папке!", show_alert=True)
            return

    kb, page, total_pages = build_navigator_keyboard(session.navigation_dir, session.navigation_page)
    text = format_navigator_text(session.current_project_dir, session.navigation_dir)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "nav_up")
async def cb_nav_up(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    parent_dir = session.navigation_dir.parent

    if parent_dir != session.navigation_dir and parent_dir.exists():
        session.navigation_dir = parent_dir
        session.navigation_page = 0

    kb, page, total_pages = build_navigator_keyboard(session.navigation_dir, session.navigation_page)
    text = format_navigator_text(session.current_project_dir, session.navigation_dir)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("nav_page:"))
async def cb_nav_page(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    page_num = int(callback.data.split(":")[1])
    session.navigation_page = page_num

    kb, page, total_pages = build_navigator_keyboard(session.navigation_dir, session.navigation_page)
    text = format_navigator_text(session.current_project_dir, session.navigation_dir)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "nav_choose")
async def cb_nav_choose(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    session.current_project_dir = session.navigation_dir
    session.reset_conversation()
    session_manager.save_to_disk()

    await callback.message.edit_text(
        f"✅ <b>Рабочая папка успешно выбрана!</b>\n\n"
        f"📁 <b>Активный проект:</b>\n<code>{session.current_project_dir}</code>\n\n"
        f"<i>Теперь все задачи и команды агента будут выполняться в этой директории. Контекст диалога обновлен.</i>",
        parse_mode="HTML"
    )
    await callback.answer("Проект выбран!")


@router.callback_query(F.data == "nav_close")
async def cb_nav_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Закрыто")


@router.callback_query(F.data == "nav_noop")
async def cb_nav_noop(callback: types.CallbackQuery):
    await callback.answer()
