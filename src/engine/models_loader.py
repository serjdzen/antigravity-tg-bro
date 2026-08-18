import os
import time
import logging
from typing import List, Tuple
from google import genai
from src.config import settings

logger = logging.getLogger(__name__)

# Топ-флагманы (Featured)
FEATURED_MODELS: List[Tuple[str, str]] = [
    ("antigravity-preview-05-2026", "🛸 Antigravity Agent"),
    ("gemini-3.7-flash", "🧠 Gemini 3.7 Flash"),
    ("gemini-3.1-pro-preview", "💎 Gemini 3.1 Pro"),
    ("claude-4-6-sonnet", "🎭 Claude 4.6 Sonnet"),
    ("claude-4-6-opus", "👑 Claude 4.6 Opus"),
    ("deep-research-max-preview-04-2026", "🔬 Deep Research Max"),
]

# Кэш полного списка
_CACHED_ALL_MODELS: List[Tuple[str, str]] = []
_LAST_FETCH_TIME: float = 0.0
_CACHE_TTL: float = 600.0


def get_model_emoji(model_id: str) -> str:
    m = model_id.lower()
    if "antigravity" in m:
        return "🛸"
    if "research" in m:
        return "🔬"
    if "opus" in m:
        return "👑"
    if "claude" in m:
        return "🎭"
    if "3.7" in m:
        return "🧠"
    if "3.1-pro" in m:
        return "💎"
    if "3.6" in m or "3.5" in m or "3.1" in m:
        return "⚡"
    if "gemma" in m:
        return "✨"
    return "🤖"


def fetch_all_live_models() -> List[Tuple[str, str]]:
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    discovered = []

    # Добавляем актуальные модели Claude 4.6
    claude_models = [
        ("claude-4-6-sonnet", "Claude 4.6 Sonnet"),
        ("claude-4-6-opus", "Claude 4.6 Opus"),
    ]
    discovered.extend(claude_models)

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            raw_models = list(client.models.list())

            excluded_keywords = [
                "embedding", "tts", "audio", "video-generate", "image",
                "robotics", "aqa", "translate", "computer-use", "clip",
                "gemini-2.5", "claude-3"  # Исключаем старые версии
            ]

            for m in raw_models:
                name = getattr(m, "name", "")
                disp = getattr(m, "display_name", "") or ""
                clean_id = name.replace("models/", "").strip()

                if not clean_id or any(k in clean_id.lower() for k in excluded_keywords):
                    continue

                display_name = disp if disp else clean_id
                if clean_id not in [d[0] for d in discovered]:
                    discovered.append((clean_id, display_name))

        except Exception as e:
            logger.error(f"Ошибка получения списка моделей из Gemini API: {e}")

    # Сортировка по приоритету
    def sort_priority(item):
        mid = item[0].lower()
        if "antigravity" in mid:
            return 0
        if "3.7" in mid:
            return 1
        if "3.1-pro" in mid:
            return 2
        if "claude-4-6-sonnet" in mid:
            return 3
        if "claude-4-6-opus" in mid:
            return 4
        if "research" in mid:
            return 5
        if "claude" in mid:
            return 6
        if "3.6" in mid:
            return 7
        if "3.5" in mid:
            return 8
        if "3.1" in mid:
            return 9
        return 20

    discovered.sort(key=sort_priority)
    return discovered


def get_all_models(force_refresh: bool = False) -> List[Tuple[str, str]]:
    global _CACHED_ALL_MODELS, _LAST_FETCH_TIME
    now = time.time()

    if force_refresh or not _CACHED_ALL_MODELS or (now - _LAST_FETCH_TIME > _CACHE_TTL):
        _CACHED_ALL_MODELS = fetch_all_live_models()
        _LAST_FETCH_TIME = now

    return _CACHED_ALL_MODELS
