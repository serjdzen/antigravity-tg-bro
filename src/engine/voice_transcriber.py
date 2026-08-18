import io
import logging
import aiohttp
from pathlib import Path
from typing import Optional
from src.config import settings

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
PROMPT_VOCABULARY_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "whisper_prompt.txt"


def get_whisper_prompt_hint() -> str:
    """
    Считывает словарь специфических IT-терминов из data/whisper_prompt.txt для модели Whisper.
    """
    if PROMPT_VOCABULARY_FILE.exists():
        try:
            content = PROMPT_VOCABULARY_FILE.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            logger.warning(f"Не удалось прочитать {PROMPT_VOCABULARY_FILE}: {e}")
    return "Antigravity, amoCRM, n8n, Astro, TypeScript, Next.js, Docker, Python, Git, Supabase, Yandex, Wordstat"


class VoiceTranscriber:
    """
    Асинхронный клиент для мгновенной транскрибации голосовых сообщений
    через Groq Whisper Large v3 Turbo с поддержкой словаря терминов.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def transcribe_audio_bytes(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        """
        Отправляет бинарные данные аудиофайла в Groq Whisper Large v3 Turbo
        и возвращает распознанный текст.
        """
        if not self.is_configured:
            raise ValueError("GROQ_API_KEY не настроен в .env файле.")

        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}"
        }

        prompt_hint = get_whisper_prompt_hint()

        data = aiohttp.FormData()
        data.add_field(
            "file",
            audio_bytes,
            filename=filename,
            content_type="audio/ogg"
        )
        data.add_field("model", GROQ_WHISPER_MODEL)
        data.add_field("response_format", "json")
        data.add_field("temperature", "0.0")
        if prompt_hint:
            data.add_field("prompt", prompt_hint)

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GROQ_TRANSCRIPTION_URL, headers=headers, data=data) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Ошибка Groq Whisper API ({resp.status}): {error_text}")
                    raise RuntimeError(f"Ошибка Groq API ({resp.status}): {error_text}")

                result = await resp.json()
                text = result.get("text", "").strip()
                logger.info(f"🎙️ Успешная транскрибация Groq ({len(audio_bytes)} байт) -> '{text[:60]}...'")
                return text


voice_transcriber = VoiceTranscriber()
