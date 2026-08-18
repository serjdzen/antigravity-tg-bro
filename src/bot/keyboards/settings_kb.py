from typing import Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.engine.models_loader import (
    FEATURED_MODELS,
    get_all_models,
    get_model_emoji
)

MODELS_PER_PAGE = 6


def build_featured_models_keyboard(
    current_model: str,
    reasoning_effort: str = "low"
) -> InlineKeyboardMarkup:
    """
    Клавиатура меню /model: только выбор модели и уровня размышлений (Thinking Effort).
    """
    builder = InlineKeyboardBuilder()

    for model_id, display_name in FEATURED_MODELS:
        prefix = "✅ " if model_id == current_model else ""
        builder.button(
            text=f"{prefix}{display_name}",
            callback_data=f"set_model:{model_id}"
        )

    builder.adjust(1)

    # Лейблы для уровней размышлений
    effort_labels = {
        "high": "🧠 Размышления: Высокий (High)",
        "medium": "⚡ Размышления: Средний (Medium)",
        "low": "🚀 Размышления: Низкий (Low)",
        "off": "⏱ Размышления: Выкл (Off)"
    }
    cur_effort_label = effort_labels.get(reasoning_effort, "🚀 Размышления: Low")

    # Кнопка переключения уровня размышлений
    builder.row(
        InlineKeyboardButton(text=cur_effort_label, callback_data="toggle_effort")
    )

    # Кнопки дополнительных списков моделей
    builder.row(
        InlineKeyboardButton(text="📂 Все модели API", callback_data="mod_view:all:0"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="mod_refresh")
    )
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="settings_close"))

    return builder.as_markup()


def build_all_models_keyboard(
    current_model: str,
    page: int = 0,
    force_refresh: bool = False
) -> Tuple[InlineKeyboardMarkup, int, int]:
    models = get_all_models(force_refresh=force_refresh)
    total_models = len(models)
    total_pages = max(1, (total_models + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE)

    page = max(0, min(page, total_pages - 1))
    start_idx = page * MODELS_PER_PAGE
    end_idx = start_idx + MODELS_PER_PAGE
    page_models = models[start_idx:end_idx]

    builder = InlineKeyboardBuilder()

    for model_id, display_name in page_models:
        prefix = "✅ " if model_id == current_model else ""
        emoji = get_model_emoji(model_id)
        short_label = display_name if len(display_name) <= 26 else display_name[:23] + "..."
        builder.button(
            text=f"{prefix}{emoji} {short_label}",
            callback_data=f"set_model:{model_id}"
        )

    builder.adjust(1)

    # Пагинация
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"mod_page:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="mod_noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"mod_page:{page + 1}"))

    if nav_row:
        builder.row(*nav_row)

    # Кнопка возврата к избранным
    builder.row(
        InlineKeyboardButton(text="⭐️ Топ-флагманы", callback_data="mod_view:featured"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="mod_refresh")
    )
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="settings_close"))

    return builder.as_markup(), page, total_pages


def build_system_settings_keyboard(
    safety_approval: bool,
    engine_mode: str,
    uploads_count: int,
    uploads_mb: float
) -> InlineKeyboardMarkup:
    """
    Клавиатура меню /settings: системные настройки, безопасность, движок, очистка файлов.
    """
    builder = InlineKeyboardBuilder()

    # 1. Кнопка переключения безопасности (Safety)
    safety_text = "🛡 Защита: ВКЛ (Ask) ✅" if safety_approval else "🛡 Защита: ВЫКЛ (Full Auto) ⚡"
    builder.row(
        InlineKeyboardButton(text=safety_text, callback_data="toggle_safety")
    )

    # 2. Кнопка переключения движка (CLI vs SDK)
    if engine_mode == "cli":
        engine_btn = InlineKeyboardButton(
            text="🟣 Движок: CLI (Google AI Pro) ⚡",
            callback_data="toggle_engine:sdk"
        )
    else:
        engine_btn = InlineKeyboardButton(
            text="🟢 Движок: SDK (API Key / $300) ☁️",
            callback_data="toggle_engine:cli"
        )
    builder.row(engine_btn)

    # 3. Кнопка очистки временных файлов
    clean_btn_text = f"🧹 Очистить uploads ({uploads_count} шт, {uploads_mb:.1f} MB)"
    builder.row(
        InlineKeyboardButton(text=clean_btn_text, callback_data="clean_uploads")
    )

    # 4. Закрыть
    builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="settings_close"))

    return builder.as_markup()
