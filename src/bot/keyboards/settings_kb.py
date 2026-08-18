from typing import Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.engine.models_loader import (
    FEATURED_MODELS,
    get_all_models,
    get_model_emoji
)
from src.bot.locales import t

MODELS_PER_PAGE = 6


def build_featured_models_keyboard(
    current_model: str,
    reasoning_effort: str = "low",
    lang: str = "en"
) -> InlineKeyboardMarkup:
    """
    Клавиатура меню /model: выбор модели и уровня размышлений (Thinking Effort).
    """
    builder = InlineKeyboardBuilder()

    for model_id, display_name in FEATURED_MODELS:
        prefix = "✅ " if model_id == current_model else ""
        builder.button(
            text=f"{prefix}{display_name}",
            callback_data=f"set_model:{model_id}"
        )

    builder.adjust(1)

    if lang == "ru":
        effort_labels = {
            "high": "🧠 Размышления: Высокий (High)",
            "medium": "⚡ Размышления: Средний (Medium)",
            "low": "🚀 Размышления: Низкий (Low)",
            "off": "⏱ Размышления: Выкл (Off)"
        }
    else:
        effort_labels = {
            "high": "🧠 Thinking: High",
            "medium": "⚡ Thinking: Medium",
            "low": "🚀 Thinking: Low",
            "off": "⏱ Thinking: Off"
        }
    cur_effort_label = effort_labels.get(reasoning_effort, f"🚀 Thinking: {reasoning_effort.title()}")

    builder.row(
        InlineKeyboardButton(text=cur_effort_label, callback_data="toggle_effort")
    )

    all_models_label = "📂 All API Models" if lang == "en" else "📂 Все модели API"
    refresh_label = t("btn_refresh", lang)
    close_label = t("btn_close", lang)

    builder.row(
        InlineKeyboardButton(text=all_models_label, callback_data="mod_view:all:0"),
        InlineKeyboardButton(text=refresh_label, callback_data="mod_refresh")
    )
    builder.row(InlineKeyboardButton(text=close_label, callback_data="settings_close"))

    return builder.as_markup()


def build_all_models_keyboard(
    current_model: str,
    page: int = 0,
    force_refresh: bool = False,
    lang: str = "en"
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

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text=t("btn_back", lang), callback_data=f"mod_page:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="mod_noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text=t("btn_forward", lang), callback_data=f"mod_page:{page + 1}"))

    if nav_row:
        builder.row(*nav_row)

    featured_label = "⭐️ Featured Models" if lang == "en" else "⭐️ Топ-флагманы"
    refresh_label = t("btn_refresh", lang)
    close_label = t("btn_close", lang)

    builder.row(
        InlineKeyboardButton(text=featured_label, callback_data="mod_view:featured"),
        InlineKeyboardButton(text=refresh_label, callback_data="mod_refresh")
    )
    builder.row(InlineKeyboardButton(text=close_label, callback_data="settings_close"))

    return builder.as_markup(), page, total_pages


def build_system_settings_keyboard(
    safety_approval: bool,
    engine_mode: str,
    uploads_count: int,
    uploads_mb: float,
    lang: str = "en"
) -> InlineKeyboardMarkup:
    """
    Клавиатура меню /settings: системные настройки, безопасность, движок, язык, очистка файлов.
    """
    builder = InlineKeyboardBuilder()

    # 1. Безопасность (Safety)
    safety_text = t("btn_safety_on", lang) if safety_approval else t("btn_safety_off", lang)
    builder.row(
        InlineKeyboardButton(text=safety_text, callback_data="toggle_safety")
    )

    # 2. Движок (CLI vs SDK)
    if engine_mode == "cli":
        engine_text = t("btn_engine_cli", lang)
        next_mode = "sdk"
    else:
        engine_text = t("btn_engine_sdk", lang)
        next_mode = "cli"

    builder.row(
        InlineKeyboardButton(text=engine_text, callback_data=f"toggle_engine:{next_mode}")
    )

    # 3. Переключение языка (Language)
    lang_btn_text = "🌐 Language: English 🇬🇧" if lang == "en" else "🌐 Язык: Русский 🇷🇺"
    builder.row(
        InlineKeyboardButton(text=lang_btn_text, callback_data="toggle_language")
    )

    # 4. Очистка временных файлов
    clean_btn_text = t("btn_clean_uploads", lang, count=uploads_count, mb=uploads_mb)
    builder.row(
        InlineKeyboardButton(text=clean_btn_text, callback_data="clean_uploads")
    )

    # 5. Закрыть
    builder.row(InlineKeyboardButton(text=t("btn_close", lang), callback_data="settings_close"))

    return builder.as_markup()
