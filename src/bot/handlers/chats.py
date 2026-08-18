import logging
from pathlib import Path
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from src.engine.session_manager import session_manager, UserSession
from src.bot.keyboards.chats_kb import build_chats_keyboard

logger = logging.getLogger(__name__)
router = Router(name="chats_router")


class RenameChatStates(StatesGroup):
    waiting_for_title = State()


def format_chats_menu_text(session: UserSession) -> str:
    active_chat = session.get_active_chat()
    return (
        f"💬 <b>Менеджер веток и чатов Antigravity</b>\n\n"
        f"🎯 <b>Активная ветка:</b> <code>{active_chat.title}</code>\n"
        f"📁 <b>Проект ветки:</b> <code>{active_chat.project_dir}</code>\n"
        f"🧠 <b>Модель:</b> <code>{active_chat.model}</code> (Effort: <code>{active_chat.effort}</code>)\n"
        f"📊 <b>Сообщений:</b> {active_chat.messages_count}\n\n"
        f"<i>Выберите ветку для переключения или используйте кнопки управления:</i>"
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
        await message.answer(f"✅ Чат успешно переименован в:\n<b>{active_chat.title}</b>", parse_mode="HTML")
    else:
        await message.answer(
            "✏️ <b>Как переименовать чат:</b>\n\n"
            "Наберите команду с новым названием, например:\n"
            "<code>/rename Мой проект</code>\n\n"
            "Или нажмите кнопку <b>«✏️ Переименовать»</b> в меню /chats.",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "chat_action:rename")
async def cb_chat_rename_start(callback: types.CallbackQuery, state: FSMContext):
    session = session_manager.get_session(callback.from_user.id)
    active_chat = session.get_active_chat()
    await state.set_state(RenameChatStates.waiting_for_title)

    await callback.message.answer(
        f"✏️ <b>Переименование чата:</b>\n"
        f"Текущее имя: <code>{active_chat.title}</code>\n\n"
        "<i>Отправьте новое название для этого чата ответным сообщением (или /cancel для отмены):</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(RenameChatStates.waiting_for_title, Command("cancel"))
async def cmd_cancel_rename(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Переименование отменено.")


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
    await message.answer(
        f"✅ <b>Чат переименован!</b>\nНовое название: <b>{active_chat.title}</b>\n\n",
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
        await callback.answer(f"Переключено на: {target_chat.title}")
    else:
        await callback.answer("Чат не найден", show_alert=True)


@router.callback_query(F.data == "chat_action:new")
async def cb_chat_new(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    new_chat = session.create_new_chat()
    session_manager.save_to_disk()

    kb = build_chats_keyboard(session)
    text = format_chats_menu_text(session)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

    await callback.answer("Создана новая ветка диалога!")


@router.callback_query(F.data == "chat_action:del")
async def cb_chat_del(callback: types.CallbackQuery):
    session = session_manager.get_session(callback.from_user.id)
    if len(session.chats) <= 1:
        await callback.answer("⚠️ Нельзя удалить единственный активный чат!", show_alert=True)
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

    await callback.answer("Ветка удалена!")


@router.callback_query(F.data == "chat_action:close")
async def cb_chat_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Закрыто")
