import logging
from pathlib import Path
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from src.engine.session_manager import session_manager, UserSession
from src.bot.keyboards.chats_kb import build_chats_keyboard
from src.bot.locales import t

logger = logging.getLogger(__name__)
router = Router(name="chats_router")


class RenameChatStates(StatesGroup):
    waiting_for_title = State()


def format_chats_menu_text(session: UserSession) -> str:
    active_chat = session.get_active_chat()
    return t(
        "chats_menu_title",
        session.language,
        title=active_chat.title,
        project_dir=active_chat.project_dir,
        model=active_chat.model,
        effort=active_chat.effort,
        count=active_chat.messages_count
    )


@router.message(Command("chats"))
@router.message(Command("branch"))
async def cmd_chats(message: types.Message):
    session = session_manager.get_session(message.from_user.id)
    kb = build_chats_keyboard(session)
    text = format_chats_menu_text(session)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("rename"))
async def cmd_rename(message: types.Message, command: CommandObject):
    session = session_manager.get_session(message.from_user.id)
    active_chat = session.get_active_chat()

    if command.args and command.args.strip():
        new_name = command.args.strip()
        active_chat.title = f"💬 {new_name}" if not new_name.startswith("💬") else new_name
        session_manager.save_to_disk()
        res_text = t("rename_success", session.language, title=active_chat.title)
        await message.answer(res_text, parse_mode="HTML")
    else:
        usage = t("rename_prompt", session.language, title=active_chat.title)
        await message.answer(usage, parse_mode="HTML")


@router.callback_query(F.data == "chat_action:rename")
async def cb_chat_rename_start(callback: types.CallbackQuery, state: FSMContext):
    session = session_manager.get_session(callback.from_user.id)
    active_chat = session.get_active_chat()
    await state.set_state(RenameChatStates.waiting_for_title)

    prompt = t("rename_prompt", session.language, title=active_chat.title)
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()


@router.message(RenameChatStates.waiting_for_title, Command("cancel"))
async def cmd_cancel_rename(message: types.Message, state: FSMContext):
    session = session_manager.get_session(message.from_user.id)
    await state.clear()
    await message.answer(t("rename_cancelled", session.language))


@router.message(RenameChatStates.waiting_for_title, F.text & ~F.text.startswith("/"))
async def process_rename_title(message: types.Message, state: FSMContext):
    session = session_manager.get_session(message.from_user.id)
    active_chat = session.get_active_chat()

    new_name = message.text.strip()
    active_chat.title = f"💬 {new_name}" if not new_name.startswith("💬") else new_name
    session_manager.save_to_disk()
    await state.clear()

    kb = build_chats_keyboard(session)
    text = format_chats_menu_text(session)
    success_text = t("rename_success", session.language, title=active_chat.title)
    await message.answer(
        f"{success_text}\n\n",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("chat_switch:"))
async def cb_chat_switch(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    chat_id = callback.data.split(":")[1]

    target_chat = session.switch_chat(chat_id)
    if target_chat:
        session_manager.save_to_disk()
        kb = build_chats_keyboard(session)
        text = format_chats_menu_text(session)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        switched_msg = t("chat_switched", session.language, title=target_chat.title)
        await callback.answer(switched_msg)
    else:
        await callback.answer("Chat not found", show_alert=True)


@router.callback_query(F.data == "chat_action:new")
async def cb_chat_new(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    session.create_new_chat()
    session_manager.save_to_disk()

    kb = build_chats_keyboard(session)
    text = format_chats_menu_text(session)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer(t("chat_created", session.language))


@router.callback_query(F.data == "chat_action:del")
async def cb_chat_del(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    if len(session.chats) <= 1:
        await callback.answer(t("chat_cannot_delete_only", session.language), show_alert=True)
        return

    del_id = session.active_chat_id
    session.delete_chat(del_id)
    session_manager.save_to_disk()

    kb = build_chats_keyboard(session)
    text = format_chats_menu_text(session)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer(t("chat_deleted", session.language))


@router.callback_query(F.data == "chat_action:close")
async def cb_chat_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()
