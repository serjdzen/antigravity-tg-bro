import re
import asyncio
import logging
import time
from typing import List, Optional
from aiogram import Bot, types
from aiogram.types import InputRichMessage, ReplyParameters
from src.bot.utils.formatter import (
    format_markdown_to_telegram_html,
    split_message,
    has_markdown_table
)

logger = logging.getLogger(__name__)


def close_unclosed_html_tags(html_snippet: str) -> str:
    """
    Scans an HTML snippet for opened tags and automatically closes unclosed tags
    in correct LIFO order, ensuring Telegram never rejects with 'can't parse entities: Unclosed tag'.
    """
    if not html_snippet:
        return ""

    # Remove any trailing incomplete tag like "<blo" or "<b"
    html_snippet = re.sub(r"<[a-zA-Z0-9/][^>]*$", "", html_snippet)

    # Supported Telegram HTML tags
    supported_tags = ["b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "blockquote", "a"]
    tag_pattern = re.compile(r"</?([a-zA-Z0-9]+)(?:\s+[^>]*)?>")

    tag_stack = []
    for match in tag_pattern.finditer(html_snippet):
        full_tag = match.group(0)
        tag_name = match.group(1).lower()
        if tag_name not in supported_tags:
            continue

        if full_tag.startswith("</"):
            if tag_stack and tag_stack[-1] == tag_name:
                tag_stack.pop()
            elif tag_name in tag_stack:
                while tag_stack and tag_stack[-1] != tag_name:
                    tag_stack.pop()
                if tag_stack:
                    tag_stack.pop()
        else:
            tag_stack.append(tag_name)

    closing_tags = "".join(f"</{tag}>" for tag in reversed(tag_stack))
    return html_snippet + closing_tags


class LiveStreamer:
    """
    Индикатор генерации и доставки сообщений в Telegram:
    - Создает сервисное сообщение-индикатор (⚡ Генерирую ответ...).
    - Во время генерации держит компактный статус (без спама промежуточным текстом).
    - При завершении удаляет индикатор и отправляет чистый ответ новым сообщением.
    - Гарантирует появление Push-уведомления и корректный таймстемп в Telegram.
    """
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        reply_to_message_id: Optional[int] = None,
        existing_message_id: Optional[int] = None
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.reply_to_message_id = reply_to_message_id
        self.message_id: Optional[int] = existing_message_id
        self.accumulated_text = ""
        self.is_finalized = False

    async def start(self):
        if self.message_id:
            return

        try:
            msg = await self.bot.send_message(
                chat_id=self.chat_id,
                text="⚡ <i>Генерирую ответ...</i>",
                reply_to_message_id=self.reply_to_message_id,
                parse_mode="HTML"
            )
            self.message_id = msg.message_id
        except Exception as e:
            logger.warning(f"Не удалось отправить начальное сообщение стримера: {e}")

    async def update_text(self, new_chunk: str):
        self.accumulated_text += new_chunk

    async def finalize(
        self,
        extra_blocks: Optional[List[str]] = None,
        reply_markup: Optional[types.InlineKeyboardMarkup] = None
    ):
        self.is_finalized = True

        # 1. Проверяем наличие Markdown-таблиц для отправки формата «Статья» (Rich Message)
        if has_markdown_table(self.accumulated_text):
            full_md_parts = []
            if extra_blocks:
                for block in extra_blocks:
                    if block.strip():
                        full_md_parts.append(block.strip())
            if self.accumulated_text.strip():
                full_md_parts.append(self.accumulated_text.strip())
            elif not extra_blocks:
                full_md_parts.append("⚠️ _Ответ от агента пуст или был прерван._")

            rich_content = "\n\n".join(full_md_parts)
            reply_params = (
                ReplyParameters(message_id=self.reply_to_message_id)
                if self.reply_to_message_id
                else None
            )

            # Attempt 1: Отправляем новое сообщение формата «Статья» (Rich Message) и удаляем плейсхолдер
            try:
                msg = await self.bot.send_rich_message(
                    chat_id=self.chat_id,
                    rich_message=InputRichMessage(markdown=rich_content),
                    reply_parameters=reply_params,
                    reply_markup=reply_markup
                )
                placeholder_id = self.message_id
                self.message_id = msg.message_id
                if placeholder_id:
                    try:
                        await self.bot.delete_message(chat_id=self.chat_id, message_id=placeholder_id)
                    except Exception:
                        pass
                return
            except Exception as e:
                logger.info(f"send_rich_message не удался ({e}), пробуем edit_message_text с rich_message...")

            # Attempt 2: Редактируем плейсхолдер на месте в формат «Статья» (нативная таблица)
            if self.message_id:
                try:
                    await self.bot.edit_message_text(
                        chat_id=self.chat_id,
                        message_id=self.message_id,
                        rich_message=InputRichMessage(markdown=rich_content),
                        reply_markup=reply_markup
                    )
                    return
                except Exception as e:
                    logger.warning(f"edit_message_text с rich_message отклонен ({e}), fallback на Card Layout HTML...")

        # 2. Удаляем временное сервисное сообщение-индикатор (для обычных сообщений или Card Layout fallback)
        placeholder_id = self.message_id
        self.message_id = None
        if placeholder_id:
            try:
                await self.bot.delete_message(chat_id=self.chat_id, message_id=placeholder_id)
            except Exception as e:
                logger.debug(f"Не удалось удалить плейсхолдер {placeholder_id}: {e}")

        full_html_parts = []

        # Блоки мыслей или вызовов инструментов
        if extra_blocks:
            for block in extra_blocks:
                if block.strip():
                    full_html_parts.append(block.strip())

        # Основной текст
        if self.accumulated_text.strip():
            formatted_body = format_markdown_to_telegram_html(self.accumulated_text.strip(), convert_tables=True)
            full_html_parts.append(formatted_body)
        elif not extra_blocks:
            full_html_parts.append("⚠️ <i>Ответ от агента пуст или был прерван. Если выполнялась долгая операция, проверьте статус файлов или отправьте уточняющий запрос.</i>")

        combined_text = "\n\n".join(full_html_parts)
        chunks = split_message(combined_text, max_chars=3900)

        if not chunks:
            chunks = ["<i>✅ Ответ получен.</i>"]

        # Отправляем части сообщения как новые входящие сообщения
        for idx, chunk in enumerate(chunks):
            is_first = (idx == 0)
            is_last = (idx == len(chunks) - 1)
            kb_for_chunk = reply_markup if is_last else None
            reply_to = self.reply_to_message_id if is_first else None

            sent_msg = None
            try:
                sent_msg = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk,
                    reply_to_message_id=reply_to,
                    reply_markup=kb_for_chunk,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Ошибка отправки HTML ({e}), fallback на чистый текст...")
                clean_chunk = re.sub(r"<[^>]+>", "", chunk)
                try:
                    sent_msg = await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=clean_chunk,
                        reply_to_message_id=reply_to,
                        reply_markup=kb_for_chunk
                    )
                except Exception as send_err:
                    logger.error(f"Не удалось отправить сообщение: {send_err}")

            if is_first and sent_msg:
                self.message_id = sent_msg.message_id
