"""
Localization (i18n) strings for Antigravity Telegram Bot.
Supports English ('en', default) and Russian ('ru').
Easily extensible for additional languages.
"""

from typing import Dict, Any

MESSAGES: Dict[str, Dict[str, str]] = {
    # -------------------------------------------------------------
    # COMMON COMMANDS (/start, /help, /status)
    # -------------------------------------------------------------
    "start_welcome": {
        "en": (
            "👋 <b>Welcome to Antigravity Telegram!</b>\n\n"
            "Control your local development environment directly from Telegram using voice, text, and screenshots.\n\n"
            "<b>Main Commands:</b>\n"
            "💬 /chats — Dialog branches & session history\n"
            "📁 /project — Local workspace explorer\n"
            "🧠 /model — Model selection & Thinking Effort\n"
            "⚙️ /settings — Security, engine & language\n"
            "🧹 /compact — Compress session context & refresh speed\n"
            "📊 /quota — 5-hour limits & account status\n"
            "📊 /status — Current session overview\n"
            "❓ /help — Detailed manual\n\n"
            "🎙 <i>Tip: Send voice messages for instant Groq Whisper transcription, upload screenshots, or download files via <code>/get path/to/file</code>.</i>"
        ),
        "ru": (
            "👋 <b>Добро пожаловать в Antigravity TG!</b>\n\n"
            "Управляйте локальной разработкой прямо из Telegram голосом, текстом и скриншотами.\n\n"
            "<b>Главные команды:</b>\n"
            "💬 /chats — Ветки диалогов и история\n"
            "📁 /project — Навигатор по папкам\n"
            "🧠 /model — Выбор модели и Thinking Effort\n"
            "⚙️ /settings — Безопасность, движок и язык\n"
            "🧹 /compact — Сжатие контекста и ускорение агента\n"
            "📊 /quota — 5-часовые лимиты и аккаунт\n"
            "📊 /status — Текущий статус сессии\n"
            "❓ /help — Подробная справка\n\n"
            "🎙 <i>Вы можете надиктовывать задачи голосовыми сообщениями, присылать скриншоты или скачивать файлы через <code>/get путь/к/файлу</code>.</i>"
        )
    },
    "help_text": {
        "en": (
            "📖 <b>Antigravity TG Feature Guide:</b>\n\n"
            "• <b>💬 Dialog Branches:</b> /chats — create, switch, and rename conversation threads.\n"
            "• <b>📁 Project Navigator:</b> /project — browse and select local project folders.\n"
            "• <b>🧹 Context Compaction:</b> /compact — safely archive bloated conversation and start clean thread.\n"
            "• <b>📊 Quotas & Limits:</b> /quota — check remaining 5-hour limits and reset timers across models.\n"
            "• <b>🎙 Voice Control:</b> Send voice messages for instant transcription (~300ms) via Groq Whisper.\n"
            "• <b>📸 Vision & Screenshots:</b> Send UI designs or bug screenshots — Gemini analyzes them instantly.\n"
            "• <b>📥 File Downloader:</b> <code>/get path/to/file.ext</code> — directly download project files to Telegram.\n"
            "• <b>🛡 Security:</b> /settings — toggle 2-Tier approval for destructive operations.\n"
            "• <b>🧠 Models:</b> /model — switch models (Gemini 3.7 Flash, Pro, Claude) and thinking depth."
        ),
        "ru": (
            "📖 <b>Справка по возможностям Antigravity TG:</b>\n\n"
            "• <b>💬 Ветки диалогов:</b> /chats — создание новых веток, история и переименование.\n"
            "• <b>📁 Выбор проекта:</b> /project — проводник по папкам на компьютере.\n"
            "• <b>🧹 Сжатие контекста:</b> /compact — безопасная архивация раздутой сессии и запуск чистого контекста.\n"
            "• <b>📊 Лимиты и квоты:</b> /quota — проверка остатка 5-часовых лимитов и времени сброса.\n"
            "• <b>🎙 Голосовые задачи:</b> Отправляйте голосовые сообщения — мгновенная расшифровка через Groq Whisper.\n"
            "• <b>📸 Фото и скриншоты:</b> Отправьте скриншот ошибки или макет с подписью — модель Gemini сразу проанализирует изображение.\n"
            "• <b>📥 Скачивание файлов:</b> <code>/get path/to/file.ext</code> — бот пришлет файл из проекта в Telegram.\n"
            "• <b>🛡 Безопасность:</b> /settings — включение/выключение подтверждений на опасные команды.\n"
            "• <b>🧠 Модели:</b> /model — выбор моделей (Gemini 3.7 Flash, Pro, Claude) и уровня Thinking."
        )
    },
    "status_title": {
        "en": (
            "📊 <b>Current Session Status:</b>\n\n"
            "💬 <b>Active Branch:</b> <code>{chat_title}</code>\n"
            "📁 <b>Project Directory:</b> <code>{project_dir}</code>\n"
            "🤖 <b>Active Model:</b> <code>{model}</code> (Effort: <code>{effort}</code>)\n"
            "⚙️ <b>Engine:</b> {engine_label}\n"
            "🛡 <b>Security:</b> {safety_label}\n"
            "🌐 <b>Language:</b> {language_label}\n"
            "📁 <b>Uploads Cache:</b> {files_count} files ({files_mb:.1f} MB)\n"
            "🟢 <b>Status:</b> Ready 🚀"
        ),
        "ru": (
            "📊 <b>Текущий статус сессии:</b>\n\n"
            "💬 <b>Активная ветка:</b> <code>{chat_title}</code>\n"
            "📁 <b>Рабочий проект:</b> <code>{project_dir}</code>\n"
            "🤖 <b>Модель:</b> <code>{model}</code> (Effort: <code>{effort}</code>)\n"
            "⚙️ <b>Движок:</b> {engine_label}\n"
            "🛡 <b>Безопасность:</b> {safety_label}\n"
            "🌐 <b>Язык:</b> {language_label}\n"
            "📁 <b>Папка uploads:</b> {files_count} файлов ({files_mb:.1f} MB)\n"
            "🟢 <b>Статус:</b> Готов к работе 🚀"
        )
    },

    # -------------------------------------------------------------
    # SETTINGS & MODEL MENUS
    # -------------------------------------------------------------
    "settings_title": {
        "en": (
            "⚙️ <b>System Settings & Maintenance:</b>\n\n"
            "🛡 <b>Security Mode:</b>\n{safety_desc}\n\n"
            "📥 <b>Message Queue:</b>\n{queue_desc}\n\n"
            "⚙️ <b>Execution Engine:</b>\n{engine_desc}\n\n"
            "🌐 <b>Language:</b> {lang_name}\n\n"
            "📁 <b>Temporary Uploads:</b>\n"
            "• Cached files: <b>{uploads_count}</b> ({uploads_mb:.1f} MB)\n\n"
            "<i>Use buttons below to configure parameters:</i>"
        ),
        "ru": (
            "⚙️ <b>Системные Настройки & Обслуживание:</b>\n\n"
            "🛡 <b>Режим безопасности:</b>\n{safety_desc}\n\n"
            "📥 <b>Очередь сообщений:</b>\n{queue_desc}\n\n"
            "⚙️ <b>Движок выполнения:</b>\n{engine_desc}\n\n"
            "🌐 <b>Язык интерфейса:</b> {lang_name}\n\n"
            "📁 <b>Временные загрузки (uploads):</b>\n"
            "• Файлов в очереди: <b>{uploads_count} шт.</b> ({uploads_mb:.1f} MB)\n\n"
            "<i>Используйте кнопки для управления параметрами:</i>"
        )
    },
    "safety_ask_desc": {
        "en": "🔒 <b>ENABLED (Ask)</b> — Destructive commands require explicit inline confirmation.",
        "ru": "🔒 <b>ВКЛЮЧЕНА (Ask)</b> — опасные команды блокируются и требуют подтверждения кнопкой."
    },
    "safety_auto_desc": {
        "en": "⚡ <b>DISABLED (Full Auto)</b> — Commands execute immediately without prompts.",
        "ru": "⚡ <b>ВЫКЛЮЧЕНА (Full Auto)</b> — все команды выполняются сразу без вопросов."
    },
    "queue_on_desc": {
        "en": "⏳ <b>ENABLED (Queue)</b> — Incoming messages are queued and processed sequentially.",
        "ru": "⏳ <b>ВКЛЮЧЕНА (Queue)</b> — входящие сообщения накапливаются в очереди и выполняются по порядку."
    },
    "queue_off_desc": {
        "en": "🚫 <b>DISABLED (Block)</b> — Incoming messages are rejected while an agent task is active.",
        "ru": "🚫 <b>ВЫКЛЮЧЕНА (Block)</b> — входящие сообщения отклоняются, пока агент выполняет задачу."
    },
    "engine_cli_desc": {
        "en": "🟣 <b>Antigravity CLI</b> <i>(Local Google account subscription)</i>",
        "ru": "🟣 <b>Antigravity CLI</b> <i>(Подписка Google One AI Pro)</i>"
    },
    "engine_sdk_desc": {
        "en": "🟢 <b>Python SDK</b> <i>(Google Gemini API Key)</i>",
        "ru": "🟢 <b>Python SDK</b> <i>(API-ключ / Cloud)</i>"
    },
    "btn_safety_on": {
        "en": "🛡 Security: ON (Ask) ✅",
        "ru": "🛡 Защита: ВКЛ (Ask) ✅"
    },
    "btn_safety_off": {
        "en": "🛡 Security: OFF (Full Auto) ⚡",
        "ru": "🛡 Защита: ВЫКЛ (Full Auto) ⚡"
    },
    "btn_queue_on": {
        "en": "📥 Queue: ON (Queue) ⏳",
        "ru": "📥 Очередь: ВКЛ (Queue) ⏳"
    },
    "btn_queue_off": {
        "en": "📥 Queue: OFF (Block) 🚫",
        "ru": "📥 Очередь: ВЫКЛ (Block) 🚫"
    },
    "btn_engine_cli": {
        "en": "🟣 Engine: CLI (Google Account) ⚡",
        "ru": "🟣 Движок: CLI (Google AI Pro) ⚡"
    },
    "btn_engine_sdk": {
        "en": "🟢 Engine: SDK (API Key) ☁️",
        "ru": "🟢 Движок: SDK (API Key) ☁️"
    },
    "btn_clean_uploads": {
        "en": "🧹 Clean uploads ({count} files, {mb:.1f} MB)",
        "ru": "🧹 Очистить uploads ({count} шт, {mb:.1f} MB)"
    },
    "btn_lang_toggle": {
        "en": "🌐 Language: English 🇬🇧",
        "ru": "🌐 Язык: Русский 🇷🇺"
    },
    "alert_uploads_cleaned": {
        "en": "🧹 Removed {count} temporary files!",
        "ru": "🧹 Удалено {count} временных файлов!"
    },
    "btn_close": {
        "en": "❌ Close",
        "ru": "❌ Закрыть"
    },
    "btn_back": {
        "en": "⬅️ Back",
        "ru": "⬅️ Назад"
    },
    "btn_forward": {
        "en": "Next ➡️",
        "ru": "Вперед ➡️"
    },
    "btn_refresh": {
        "en": "🔄 Refresh",
        "ru": "🔄 Обновить"
    },
    "featured_models_title": {
        "en": (
            "🧠 <b>AI Model & Thinking Effort Selection:</b>\n\n"
            "🎯 <b>Active Model:</b> <code>{model}</code>\n"
            "💭 <b>Thinking Effort:</b> <code>{effort}</code>\n\n"
            "⭐️ <b>Featured Models (Google Gemini 3.x & Claude):</b>\n"
            "<i>Tap any model to switch instantly:</i>"
        ),
        "ru": (
            "🧠 <b>Выбор AI-модели & Уровня Размышлений:</b>\n\n"
            "🎯 <b>Активная модель:</b> <code>{model}</code>\n"
            "💭 <b>Thinking Effort:</b> <code>{effort}</code>\n\n"
            "⭐️ <b>Топ-модели (Google Gemini 3.x & Claude):</b>\n"
            "<i>Нажмите на нужную модель для немедленного переключения:</i>"
        )
    },
    "all_models_title": {
        "en": (
            "🧠 <b>All API Models Catalog ({count}):</b>\n\n"
            "🎯 <b>Active Model:</b> <code>{model}</code>\n\n"
            "<i>Browse pages with the buttons below:</i>"
        ),
        "ru": (
            "🧠 <b>Полный список моделей API ({count}):</b>\n\n"
            "🎯 <b>Активная модель:</b> <code>{model}</code>\n\n"
            "<i>Листайте страницы кнопками ниже:</i>"
        )
    },

    # -------------------------------------------------------------
    # CHAT THREADS & SESSIONS (/chats)
    # -------------------------------------------------------------
    "chats_menu_title": {
        "en": (
            "💬 <b>Antigravity Dialog Branches Manager</b>\n\n"
            "🎯 <b>Active Thread:</b> <code>{title}</code>\n"
            "📁 <b>Project:</b> <code>{project_dir}</code>\n"
            "🧠 <b>Model:</b> <code>{model}</code> (Effort: <code>{effort}</code>)\n"
            "📊 <b>Messages:</b> {count}\n\n"
            "<i>Select a branch to switch, or use the actions below:</i>"
        ),
        "ru": (
            "💬 <b>Менеджер веток и чатов Antigravity</b>\n\n"
            "🎯 <b>Активная ветка:</b> <code>{title}</code>\n"
            "📁 <b>Проект ветки:</b> <code>{project_dir}</code>\n"
            "🧠 <b>Модель:</b> <code>{model}</code> (Effort: <code>{effort}</code>)\n"
            "📊 <b>Сообщений:</b> {count}\n\n"
            "<i>Выберите ветку для переключения или используйте кнопки управления:</i>"
        )
    },
    "btn_new_chat": {
        "en": "➕ New Chat",
        "ru": "➕ Новый чат"
    },
    "btn_rename_chat": {
        "en": "✏️ Rename",
        "ru": "✏️ Переименовать"
    },
    "btn_delete_chat": {
        "en": "🗑 Delete",
        "ru": "🗑 Удалить"
    },
    "rename_prompt": {
        "en": (
            "✏️ <b>Rename Chat Thread:</b>\n"
            "Current title: <code>{title}</code>\n\n"
            "<i>Send the new title in reply (or /cancel to abort):</i>"
        ),
        "ru": (
            "✏️ <b>Переименование чата:</b>\n"
            "Текущее имя: <code>{title}</code>\n\n"
            "<i>Отправьте новое название для этого чата ответным сообщением (или /cancel для отмены):</i>"
        )
    },
    "rename_cancelled": {
        "en": "❌ Renaming cancelled.",
        "ru": "❌ Переименование отменено."
    },
    "rename_success": {
        "en": "✅ <b>Chat renamed!</b>\nNew title: <b>{title}</b>",
        "ru": "✅ <b>Чат переименован!</b>\nНовое название: <b>{title}</b>"
    },
    "chat_switched": {
        "en": "Switched to: {title}",
        "ru": "Переключено на: {title}"
    },
    "chat_created": {
        "en": "Created new dialog branch!",
        "ru": "Создана новая ветка диалога!"
    },
    "chat_cannot_delete_only": {
        "en": "⚠️ Cannot delete the only active chat!",
        "ru": "⚠️ Нельзя удалить единственный активный чат!"
    },
    "chat_deleted": {
        "en": "Branch deleted!",
        "ru": "Ветка удалена!"
    },

    # -------------------------------------------------------------
    # PROJECT NAVIGATOR (/project)
    # -------------------------------------------------------------
    "navigator_title": {
        "en": (
            "📁 <b>Project Filesystem Explorer</b>\n\n"
            "🎯 <b>Active Project:</b>\n<code>{current_project}</code>\n\n"
            "🔍 <b>Browsing Folder:</b>\n<code>{browse_dir}</code>\n\n"
            "<i>Select a subfolder or tap «Select this folder»:</i>"
        ),
        "ru": (
            "📁 <b>Файловый проводник проектов</b>\n\n"
            "🎯 <b>Активный проект:</b>\n<code>{current_project}</code>\n\n"
            "🔍 <b>Просмотр папки:</b>\n<code>{browse_dir}</code>\n\n"
            "<i>Выберите подпапку или нажмите «Выбрать эту папку»:</i>"
        )
    },
    "btn_choose_dir": {
        "en": "✅ Select this folder",
        "ru": "✅ Выбрать эту папку"
    },
    "btn_up_dir": {
        "en": "⬆️ Up",
        "ru": "⬆️ Вверх"
    },
    "project_chosen_success": {
        "en": (
            "✅ <b>Workspace selected!</b>\n\n"
            "📁 <b>Active Project:</b>\n<code>{project_dir}</code>\n\n"
            "<i>All agent operations will now execute within this directory.</i>"
        ),
        "ru": (
            "✅ <b>Рабочая папка успешно выбрана!</b>\n\n"
            "📁 <b>Активный проект:</b>\n<code>{project_dir}</code>\n\n"
            "<i>Теперь все задачи и команды агента будут выполняться в этой директории. Контекст диалога обновлен.</i>"
        )
    },
    "nav_permission_denied": {
        "en": "⚠️ Permission denied for this folder!",
        "ru": "⚠️ Нет прав доступа к этой папке!"
    },

    # -------------------------------------------------------------
    # CHAT, STREAMING & SECURITY APPROVALS
    # -------------------------------------------------------------
    "thought_block_header": {
        "en": "💭 <b>Agent Thoughts:</b>",
        "ru": "💭 <b>Мысли агента:</b>"
    },
    "tool_call_header": {
        "en": "🛠️ <b>Tool Call:</b>",
        "ru": "🛠️ <b>Вызов инструмента:</b>"
    },
    "voice_processing": {
        "en": "🎙 <i>Transcribing voice message via Groq Whisper...</i>",
        "ru": "🎙 <i>Распознаю голосовое сообщение через Groq Whisper...</i>"
    },
    "voice_error": {
        "en": "❌ <b>Voice Transcription Failed:</b>\n{error}",
        "ru": "❌ <b>Ошибка распознавания голоса:</b>\n{error}"
    },
    "task_stopped": {
        "en": "🛑 <b>Current task halted by user.</b>",
        "ru": "🛑 <b>Текущая задача остановлена пользователем.</b>"
    },
    "task_stopped_with_queue": {
        "en": "🛑 <b>Current task halted by user.</b>\nCleared <b>{count}</b> pending request(s) from queue.",
        "ru": "🛑 <b>Текущая задача остановлена пользователем.</b>\nОчищено <b>{count}</b> отложенных запросов из очереди."
    },
    "msg_queued": {
        "en": "📥 <b>Message added to queue (position #{pos}).</b>\n<i>Will execute immediately once the current task completes.</i>",
        "ru": "📥 <b>Запрос добавлен в очередь (позиция #{pos}).</b>\n<i>Выполню сразу после завершения текущей задачи.</i>"
    },
    "queue_full": {
        "en": "⚠️ <b>Queue is full (max {limit} messages).</b>\nPlease wait for active tasks to complete before sending more.",
        "ru": "⚠️ <b>Очередь сообщений переполнена (макс. {limit} запросов).</b>\nПожалуйста, дождитесь завершения текущих задач."
    },
    "task_nothing_to_stop": {
        "en": "ℹ️ No active task is currently executing.",
        "ru": "ℹ️ Сейчас нет активных выполняющихся задач."
    },
    "approval_title": {
        "en": (
            "⚠️ <b>Security Guard Blocked Operation</b>\n\n"
            "The model requested a destructive operation that matched deny rules:\n"
            "<code>{cmd}</code>\n\n"
            "Do you want to grant a <b>one-time force override</b>?"
        ),
        "ru": (
            "⚠️ <b>Защита безопасности заблокировала операцию</b>\n\n"
            "Модель запросила деструктивную команду из deny-списка:\n"
            "<code>{cmd}</code>\n\n"
            "Хотите выдать <b>разовый допуск</b>?"
        )
    },
    "btn_force_override": {
        "en": "⚡ Allow Once (Force Override)",
        "ru": "⚡ Разрешить разово (Force Override)"
    },
    "btn_deny_override": {
        "en": "🛑 Cancel Action",
        "ru": "🛑 Отклонить действие"
    },
    "get_file_usage": {
        "en": "📥 <b>Usage:</b> <code>/get path/to/file.ext</code> (relative to project or absolute)",
        "ru": "📥 <b>Использование:</b> <code>/get путь/к/файлу.расширение</code> (относительно проекта или абсолютный)"
    },
    "get_file_not_found": {
        "en": "❌ File not found: <code>{path}</code>",
        "ru": "❌ Файл не найден: <code>{path}</code>"
    },
    "get_file_too_large": {
        "en": "⚠️ File is too large ({size_mb:.1f} MB). Telegram limit is 50 MB.",
        "ru": "⚠️ Файл слишком большой ({size_mb:.1f} MB). Лимит Telegram — 50 MB."
    },
    "quota_alert_footer": {
        "en": (
            "\n\n---\n"
            "⚠️ **Antigravity 5h Quota Alert ({percent} left)!**\n"
            "📧 **Account:** `{email}`\n"
            "⏳ **Remaining:** {percent} ({model})\n"
            "🔄 **Reset:** in {time_left} (at {reset_time})"
        ),
        "ru": (
            "\n\n---\n"
            "⚠️ **Лимит Antigravity подходит к концу ({percent})!**\n"
            "📧 **Аккаунт:** `{email}`\n"
            "⏳ **Осталось:** {percent} ({model})\n"
            "🔄 **Обновление:** через {time_left} (в {reset_time})"
        )
    }
}


def t(key: str, lang: str = "en", **kwargs: Any) -> str:
    """
    Retrieve localized string by key and language code.
    Falls back to English ('en') if translation is missing.
    """
    lang_key = lang if lang in ("en", "ru") else "en"
    key_entry = MESSAGES.get(key, {})
    template = key_entry.get(lang_key) or key_entry.get("en", f"[{key}]")

    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
