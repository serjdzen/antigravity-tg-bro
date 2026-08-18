import asyncio
import logging
import time
from typing import List, Optional
from aiogram import Bot, types
from src.bot.utils.formatter import (
    format_markdown_to_telegram_html,
    split_message
)

logger = logging.getLogger(__name__)


class LiveStreamer:
    """
    Плавный потоковый стример сообщений в Telegram:
    - Создает сообщение-заполнитель на месте.
    - В реальном времени плавно обновляет текст в том же сообщении (edit_message_text).
    - Исключает любые визуальные скачки, дергания вниз и конфликты с черновиками.
    """
    def __init__(self, bot: Bot, chat_id: int, reply_to_message_id: Optional[int] = None):
        self.bot = bot
        self.chat_id = chat_id
        self.reply_to_message_id = reply_to_message_id
        self.message_id: Optional[int] = None
        self.accumulated_text = ""
        self.last_edit_time = 0.0
        self.last_sent_text = ""
        self.is_finalized = False
        self._edit_lock = asyncio.Lock()

    async def start(self):
        try:
            msg = await self.bot.send_message(
                chat_id=self.chat_id,
                text="⚡ <i>Генерирую ответ...</i>",
                reply_to_message_id=self.reply_to_message_id,
                parse_mode="HTML"
            )
            self.message_id = msg.message_id
            self.last_sent_text = msg.text
            self.last_edit_time = time.time()
        except Exception as e:
            logger.warning(f"Не удалось отправить начальное сообщение стримера: {e}")

    async def update_text(self, new_chunk: str):
        self.accumulated_text += new_chunk
        now = time.time()

        # Троттлинг: редактируем сообщение не чаще одного раза в 1.4 секунды
        if self.message_id and not self.is_finalized and (now - self.last_edit_time >= 1.4):
            async with self._edit_lock:
                formatted_preview = format_markdown_to_telegram_html(self.accumulated_text.strip())
                if formatted_preview and formatted_preview != self.last_sent_text:
                    # Ограничиваем превью лимитом сообщения
                    cut_preview = formatted_preview[:3800]
                    try:
                        await self.bot.edit_message_text(
                            chat_id=self.chat_id,
                            message_id=self.message_id,
                            text=cut_preview + " ▌",
                            parse_mode="HTML"
                        )
                        self.last_sent_text = cut_preview
                        self.last_edit_time = now
                    except Exception as e:
                        # Игнорируем ошибки MessageNotModified
                        if "message is not modified" not in str(e).lower():
                            logger.debug(f"Ошибка инлайн-редактирования стрима: {e}")

    async def finalize(
        self,
        extra_blocks: Optional[List[str]] = None,
        reply_markup: Optional[types.InlineKeyboardMarkup] = None
    ):
        self.is_finalized = True
        full_html_parts = []

        # Блоки мыслей или вызовов инструментов
        if extra_blocks:
            for block in extra_blocks:
                if block.strip():
                    full_html_parts.append(block.strip())

        # Основной текст
        if self.accumulated_text.strip():
            formatted_body = format_markdown_to_telegram_html(self.accumulated_text.strip())
            full_html_parts.append(formatted_body)
        elif not extra_blocks:
            full_html_parts.append("<i>✅ Задача выполнена.</i>")

        combined_text = "\n\n".join(full_html_parts)
        chunks = split_message(combined_text, max_chars=3900)

        if not chunks:
            chunks = ["<i>✅ Ответ получен.</i>"]

        # Редактируем первое сообщение на месте (без прыжков и курсора!)
        first_chunk = chunks[0]
        # Если частей несколько, прикрепляем клавиатуру к последней, иначе к первой
        first_kb = reply_markup if len(chunks) == 1 else None

        if self.message_id:
            try:
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=first_chunk,
                    reply_markup=first_kb,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Ошибка финального HTML редактирования ({e}), fallback на чистый текст...")
                import re
                clean_chunk = re.sub(r"<[^>]+>", "", first_chunk)
                try:
                    await self.bot.edit_message_text(
                        chat_id=self.chat_id,
                        message_id=self.message_id,
                        text=clean_chunk,
                        reply_markup=first_kb
                    )
                except Exception:
                    pass
        else:
            # Если начальное сообщение не создалось
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=first_chunk,
                reply_to_message_id=self.reply_to_message_id,
                reply_markup=first_kb,
                parse_mode="HTML"
            )

        # Если текст превысил 4000 символов, отправляем оставшиеся части
        for idx, chunk in enumerate(chunks[1:]):
            is_last = (idx == len(chunks[1:]) - 1)
            kb_for_chunk = reply_markup if is_last else None
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk,
                    reply_markup=kb_for_chunk,
                    parse_mode="HTML"
                )
            except Exception:
                import re
                clean_chunk = re.sub(r"<[^>]+>", "", chunk)
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=clean_chunk,
                    reply_markup=kb_for_chunk
                )
