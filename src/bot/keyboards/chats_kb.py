from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.engine.session_manager import UserSession
from src.bot.locales import t


def build_chats_keyboard(session: UserSession) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    lang = session.language

    sorted_chats = sorted(
        session.chats.values(),
        key=lambda c: c.updated_at,
        reverse=True
    )

    for chat in sorted_chats:
        prefix = "✅ " if chat.id == session.active_chat_id else ""
        short_title = chat.title if len(chat.title) <= 24 else chat.title[:21] + "..."
        count_label = f"({chat.messages_count} 💬)"
        btn_text = f"{prefix}{short_title} {count_label}"
        builder.button(
            text=btn_text,
            callback_data=f"chat_switch:{chat.id}"
        )

    builder.adjust(1)

    builder.row(
        InlineKeyboardButton(text=t("btn_new_chat", lang), callback_data="chat_action:new"),
        InlineKeyboardButton(text=t("btn_rename_chat", lang), callback_data="chat_action:rename")
    )
    builder.row(
        InlineKeyboardButton(text=t("btn_delete_chat", lang), callback_data="chat_action:del"),
        InlineKeyboardButton(text=t("btn_close", lang), callback_data="chat_action:close")
    )

    return builder.as_markup()
