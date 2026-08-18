import logging
from pathlib import Path
from typing import List, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 6


def get_subdirectories(path: Path) -> List[Path]:
    try:
        if not path.exists() or not path.is_dir():
            return []
        subdirs = []
        for entry in path.iterdir():
            try:
                # Пропускаем скрытые папки и файлы
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    subdirs.append(entry)
            except (PermissionError, OSError):
                continue
        return sorted(subdirs, key=lambda p: p.name.lower())
    except (PermissionError, OSError) as e:
        logger.warning(f"Ошибка доступа к папке {path}: {e}")
        return []


def build_navigator_keyboard(
    current_dir: Path,
    page: int = 0
) -> Tuple[InlineKeyboardMarkup, int, int]:
    builder = InlineKeyboardBuilder()
    subdirs = get_subdirectories(current_dir)
    total_items = len(subdirs)
    total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    # Ограничиваем страницу допустимым диапазоном
    page = max(0, min(page, total_pages - 1))
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_items = subdirs[start_idx:end_idx]

    # Кнопки подпапок (по 2 в ряд для компактности на смартфоне)
    for idx, folder in enumerate(page_items):
        folder_name = folder.name
        if len(folder_name) > 24:
            folder_name = folder_name[:21] + "..."
        builder.button(
            text=f"📁 {folder_name}",
            callback_data=f"nav_sel:{idx}"
        )
    builder.adjust(2)

    # Навигационные кнопки: Пагинация
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"nav_page:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="nav_noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"nav_page:{page + 1}"))

    if nav_row:
        builder.row(*nav_row)

    # Кнопка «Вверх на уровень» (если мы не в корне системы)
    control_row = []
    if current_dir.parent != current_dir and current_dir != Path("/"):
        control_row.append(InlineKeyboardButton(text="⬆️ На уровень выше", callback_data="nav_up"))

    if control_row:
        builder.row(*control_row)

    # Главные кнопки действий
    builder.row(
        InlineKeyboardButton(text="✅ Выбрать эту папку", callback_data="nav_choose"),
        InlineKeyboardButton(text="❌ Закрыть", callback_data="nav_close")
    )

    return builder.as_markup(), page, total_pages
