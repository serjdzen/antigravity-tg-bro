import os
from pathlib import Path
from typing import Set
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    ALLOWED_USER_IDS: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    DEFAULT_PROJECTS_DIR: str = str(Path.home() / "Documents" / "work")
    DEFAULT_MODEL: str = "gemini-3.1-flash-lite"
    MCP_CONFIG_PATH: str = str(Path.home() / ".gemini" / "config" / "mcp_config.json")
    SKILLS_DIR_PATH: str = str(Path.home() / ".gemini" / "config" / "skills")

    model_config = SettingsConfigDict(
        env_file=(".bot.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def allowed_ids_set(self) -> Set[int]:
        if not self.ALLOWED_USER_IDS.strip():
            return set()
        ids = set()
        for item in self.ALLOWED_USER_IDS.split(","):
            item = item.strip()
            if item.isdigit():
                ids.add(int(item))
        return ids


settings = Settings()

# Очищаем os.environ от переменных бота, чтобы дочерние MCP серверы
# со строгим pydantic (extra='forbid') не падали при запуске
for key in ["BOT_TOKEN", "ALLOWED_USER_IDS", "DEFAULT_PROJECTS_DIR", "DEFAULT_MODEL", "MCP_CONFIG_PATH", "SKILLS_DIR_PATH", "GROQ_API_KEY"]:
    if key in os.environ:
        del os.environ[key]
