import asyncio
import uuid
import time
import re
import logging
from typing import Dict, Optional, Tuple
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# Паттерны потенциально опасных действий (CLI-команды и русские фразы любой формы)
DANGEROUS_PATTERNS = [
    # Удаление файлов и папок (CLI и любые формы глаголов в русском языке)
    (r"\b(rm|rmdir|unlink)\b", "Удаление файлов/папок (rm)"),
    (r"\b(удали|удалить|удаление|удаляй|удалим|сотри|стереть|стирай|стирание|сноси|сносить|очисти|очистить)\b", "Запрос на удаление или очистку файлов/папок"),
    # Опасные Git-операции
    (r"\bgit\s+(reset|clean|push\s+.*-f|push\s+.*--force|branch\s+-D|checkout\s+-f)\b", "Опасная операция Git (сброс/перезапись/удаление)"),
    (r"\b(сбрось|сбросить|откати|откатить)\s+git\b", "Сброс или откат состояния Git"),
    # Базы данных
    (r"\b(drop|truncate)\s+(table|database|db)\b", "Удаление базы данных или таблицы (DROP/TRUNCATE SQL)"),
    (r"\bprisma\s+migrate\s+reset\b", "Полный сброс базы данных Prisma"),
    # Системные права
    (r"\bsudo\b", "Запуск команды с правами суперпользователя (sudo)"),
    # Удаленный запуск скриптов
    (r"curl\s+.*\|\s*(bash|sh)", "Выполнение внешнего скрипта из интернета через pipe"),
    (r"wget\s+.*\|\s*(bash|sh)", "Выполнение внешнего скрипта из интернета через pipe"),
]


def check_dangerous_action(text: str) -> Optional[str]:
    """Проверяет текст/команду на наличие опасных паттернов. Возвращает описание риска или None."""
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return description
    return None


class ApprovalRequest:
    def __init__(self, request_id: str, user_id: int, action_type: str, detail: str):
        self.request_id = request_id
        self.user_id = user_id
        self.action_type = action_type
        self.detail = detail
        self.event = asyncio.Event()
        self.is_approved: Optional[bool] = None
        self.created_at = time.time()


class ApprovalManager:
    def __init__(self):
        self._pending: Dict[str, ApprovalRequest] = {}

    def create_request(self, user_id: int, action_type: str, detail: str) -> ApprovalRequest:
        req_id = str(uuid.uuid4())[:8]
        req = ApprovalRequest(
            request_id=req_id,
            user_id=user_id,
            action_type=action_type,
            detail=detail
        )
        self._pending[req_id] = req
        return req

    def get_request(self, req_id: str) -> Optional[ApprovalRequest]:
        return self._pending.get(req_id)

    def resolve_request(self, req_id: str, approved: bool) -> bool:
        if req_id in self._pending:
            req = self._pending[req_id]
            req.is_approved = approved
            req.event.set()
            return True
        return False

    async def ask_user_approval(
        self,
        bot: Bot,
        chat_id: int,
        user_id: int,
        action_type: str,
        detail: str,
        risk_description: str,
        timeout_seconds: int = 120
    ) -> bool:
        """
        Отправляет интерактивный запрос на согласование в Telegram с кнопками и ждет ответа пользователя.
        """
        req = self.create_request(user_id=user_id, action_type=action_type, detail=detail)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Разрешить", callback_data=f"appr:yes:{req.request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"appr:no:{req.request_id}")
            ]
        ])

        escaped_detail = detail if len(detail) <= 250 else detail[:240] + "..."

        msg = await bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ <b>ТРЕБУЕТСЯ ПОДТВЕРЖДЕНИЕ ДЕЙСТВИЯ (ASK)</b>\n\n"
                f"🚨 <b>Обнаружен риск:</b> <i>{risk_description}</i>\n"
                f"⚙️ <b>Тип:</b> <code>{action_type}</code>\n"
                f"📝 <b>Запрос / Команда:</b>\n<pre>{escaped_detail}</pre>\n\n"
                "<i>Разрешить агенту выполнить эту операцию? (Таймаут: 2 мин)</i>"
            ),
            reply_markup=kb,
            parse_mode="HTML"
        )

        try:
            await asyncio.wait_for(req.event.wait(), timeout=timeout_seconds)
            approved = bool(req.is_approved)

            result_text = "✅ <b>Действие разрешено пользователем.</b>" if approved else "❌ <b>Действие отклонено пользователем.</b>"
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    text=(
                        f"{msg.text}\n\n"
                        f"{result_text}"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

            return approved

        except asyncio.TimeoutError:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    text=(
                        f"{msg.text}\n\n"
                        "⏱ <b>Время ожидания истекло. Действие автоматически заблокировано.</b>"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return False

        finally:
            self._pending.pop(req.request_id, None)


approval_manager = ApprovalManager()
