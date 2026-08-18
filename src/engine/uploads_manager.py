import os
import shutil
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def ensure_uploads_dir() -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOADS_DIR


def get_uploads_stats() -> Tuple[int, float]:
    """
    Возвращает (количество файлов, общий размер в MB) в папке data/uploads.
    """
    ensure_uploads_dir()
    files = [f for f in UPLOADS_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]
    total_bytes = sum(f.stat().st_size for f in files)
    return len(files), total_bytes / (1024 * 1024)


def clean_uploads_dir() -> int:
    """
    Удаляет все временные файлы из data/uploads. Возвращает количество удаленных файлов.
    """
    ensure_uploads_dir()
    count = 0
    for item in UPLOADS_DIR.iterdir():
        if item.name.startswith("."):
            continue
        try:
            if item.is_file() or item.is_symlink():
                item.unlink(missing_ok=True)
                count += 1
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                count += 1
        except Exception as e:
            logger.warning(f"Не удалось удалить {item}: {e}")
    logger.info(f"🧹 Очищена папка uploads: удалено {count} объектов.")
    return count
