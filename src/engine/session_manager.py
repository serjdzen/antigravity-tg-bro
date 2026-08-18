import os
import json
import uuid
import time
import asyncio
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional
from src.config import settings

logger = logging.getLogger(__name__)

SESSIONS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "sessions.json"


@dataclass
class ChatThread:
    id: str
    title: str
    project_dir: str
    model: str = "gemini-3.7-flash"
    effort: str = "low"
    agy_conversation_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages_count: int = 0


@dataclass
class UserSession:
    user_id: int
    current_project_dir: Path = field(default_factory=lambda: Path(settings.DEFAULT_PROJECTS_DIR))
    navigation_dir: Path = field(default_factory=lambda: Path(settings.DEFAULT_PROJECTS_DIR))
    navigation_page: int = 0
    current_model: str = "gemini-3.7-flash"
    reasoning_effort: str = "low"  # "low" | "medium" | "high" | "off"
    engine_mode: str = "cli"  # "cli" | "sdk"
    safety_approval: bool = True  # Inline confirmation for destructive commands
    language: str = field(default_factory=lambda: settings.BOT_LANGUAGE)  # "en" | "ru"
    active_chat_id: Optional[str] = None
    chats: Dict[str, ChatThread] = field(default_factory=dict)
    is_busy: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    conversation_history: List[dict] = field(default_factory=list)

    def get_active_chat(self) -> ChatThread:
        if not self.active_chat_id or self.active_chat_id not in self.chats:
            chat_id = str(uuid.uuid4())[:8]
            default_title = f"💬 Main ({self.current_project_dir.name or 'work'})"
            new_chat = ChatThread(
                id=chat_id,
                title=default_title,
                project_dir=str(self.current_project_dir),
                model=self.current_model,
                effort=self.reasoning_effort
            )
            self.chats[chat_id] = new_chat
            self.active_chat_id = chat_id
        return self.chats[self.active_chat_id]

    def create_new_chat(self, title: Optional[str] = None) -> ChatThread:
        chat_id = str(uuid.uuid4())[:8]
        chat_title = title or f"💬 Thread #{len(self.chats) + 1} ({self.current_project_dir.name or 'work'})"
        new_chat = ChatThread(
            id=chat_id,
            title=chat_title,
            project_dir=str(self.current_project_dir),
            model=self.current_model,
            effort=self.reasoning_effort
        )
        self.chats[chat_id] = new_chat
        self.active_chat_id = chat_id
        self.conversation_history.clear()
        return new_chat

    def switch_chat(self, chat_id: str) -> Optional[ChatThread]:
        if chat_id in self.chats:
            self.active_chat_id = chat_id
            target_chat = self.chats[chat_id]
            p = Path(target_chat.project_dir)
            if p.exists():
                self.current_project_dir = p
                self.navigation_dir = p
            self.current_model = target_chat.model
            self.reasoning_effort = target_chat.effort
            return target_chat
        return None

    def delete_chat(self, chat_id: str) -> bool:
        if chat_id in self.chats:
            del self.chats[chat_id]
            if self.active_chat_id == chat_id:
                self.active_chat_id = next(iter(self.chats.keys())) if self.chats else None
            return True
        return False

    def reset_conversation(self):
        self.conversation_history.clear()
        self.create_new_chat()
        logger.info(f"Reset conversation history and created new chat thread for user {self.user_id}")


class SessionManager:
    def __init__(self):
        self._sessions: Dict[int, UserSession] = {}
        self._load_from_disk()

    def get_session(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            default_path = Path(settings.DEFAULT_PROJECTS_DIR)
            if not default_path.exists():
                default_path = Path.home() / "Documents" / "work"
                default_path.mkdir(parents=True, exist_ok=True)

            session = UserSession(
                user_id=user_id,
                current_project_dir=default_path,
                navigation_dir=default_path,
                navigation_page=0,
                current_model="gemini-3.7-flash",
                reasoning_effort="low",
                engine_mode="cli",
                safety_approval=True,
                language=settings.BOT_LANGUAGE
            )
            session.get_active_chat()
            self._sessions[user_id] = session
            self.save_to_disk()

        return self._sessions[user_id]

    def save_to_disk(self):
        try:
            SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for uid, s in self._sessions.items():
                chats_dict = {}
                for cid, c in s.chats.items():
                    chats_dict[cid] = asdict(c)

                data[str(uid)] = {
                    "current_project_dir": str(s.current_project_dir),
                    "current_model": s.current_model,
                    "reasoning_effort": s.reasoning_effort,
                    "engine_mode": s.engine_mode,
                    "safety_approval": s.safety_approval,
                    "language": s.language,
                    "active_chat_id": s.active_chat_id,
                    "chats": chats_dict
                }

            temp_file = SESSIONS_FILE.with_suffix(".tmp")
            temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_file.replace(SESSIONS_FILE)
            logger.debug(f"User sessions successfully saved to {SESSIONS_FILE}")
        except Exception as e:
            logger.error(f"Error saving sessions to disk: {e}")

    def _load_from_disk(self):
        if not SESSIONS_FILE.exists():
            return
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            for uid_str, s_data in data.items():
                uid = int(uid_str)
                p_dir = Path(s_data.get("current_project_dir", settings.DEFAULT_PROJECTS_DIR))
                if not p_dir.exists():
                    p_dir = Path.home() / "Documents" / "work"

                chats = {}
                for cid, c_data in s_data.get("chats", {}).items():
                    chats[cid] = ChatThread(**c_data)

                session = UserSession(
                    user_id=uid,
                    current_project_dir=p_dir,
                    navigation_dir=p_dir,
                    navigation_page=0,
                    current_model=s_data.get("current_model", "gemini-3.7-flash"),
                    reasoning_effort=s_data.get("reasoning_effort", "low"),
                    engine_mode=s_data.get("engine_mode", "cli"),
                    safety_approval=s_data.get("safety_approval", True),
                    language=s_data.get("language", settings.BOT_LANGUAGE),
                    active_chat_id=s_data.get("active_chat_id"),
                    chats=chats
                )
                session.get_active_chat()
                self._sessions[uid] = session
            logger.info(f"Loaded {len(self._sessions)} persistent user sessions from disk")
        except Exception as e:
            logger.error(f"Error loading sessions from disk: {e}")


session_manager = SessionManager()
