# 🤖 AGENTS.md — AI Coding Assistant Handbook

This document provides structured, deterministic instructions for AI coding assistants (Claude Code, Antigravity Agent, Cursor, Windsurf, Aider) operating on this repository.

---

## 🎯 Repository Purpose

`antigravity-telegram` is an asynchronous Python Telegram bot based on `aiogram 3.x` that acts as a mobile remote control for local Google Antigravity environments. It features a Dual-Engine bridge (CLI `agy` vs Python SDK), in-place live streaming, Groq Whisper voice input, multimodal file routing, and a 2-Tier Security Model.

---

## 📂 Architecture Map

```
antigravity-tg-bro/
├── main.py                     # Entry point (Safety check + Bot startup)
├── run.sh                      # Local launch script
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Build and packaging metadata
├── .env.example                # Template configuration
├── data/
│   ├── sessions.json           # Active sessions store (Git-ignored)
│   ├── uploads/                # Isolated directory for user uploads (Git-ignored)
│   └── whisper_prompt.txt      # Domain vocabulary biasing for Groq Whisper
├── scripts/
│   ├── service.sh              # macOS LaunchAgent lifecycle manager
│   └── security_check.py       # Pre-commit secret & leak scanner
├── src/
│   ├── config.py               # Pydantic-based settings with environment isolation
│   ├── bot/
│   │   ├── app.py              # Bot & Dispatcher setup
│   │   ├── handlers/           # Route handlers (chat, chats, settings, common)
│   │   ├── keyboards/          # Inline and Reply keyboards
│   │   ├── middlewares/        # Authentication & error filtering
│   │   └── utils/              # LiveStreamer and Markdown-to-HTML formatter
│   └── engine/
│       ├── antigravity_bridge.py # Dual-Engine subprocess & stream runner
│       ├── session_manager.py    # Atomic JSON persistence & multi-chat branching
│       ├── voice_transcriber.py  # Groq Whisper API client
│       ├── uploads_manager.py    # Inbound/outbound file isolate
│       ├── mcp_loader.py         # MCP discovery
│       ├── skills_loader.py      # Antigravity Skills discovery
│       └── models_loader.py      # Model catalog loader
└── tests/                      # Unit & integration tests
```

---

## ⚙️ Key Invariants & Rules for AI Agents

1. **Environment Variable Sanitization Invariant**:
   - `src/config.py` explicitly deletes bot environment variables (`del os.environ[key]`) after parsing.
   - **DO NOT REMOVE THIS LOGIC.** Child MCP servers running strict Pydantic settings with `extra='forbid'` will crash if bot environment variables are propagated.

2. **2-Tier Security Model**:
   - Destructive commands (`rm`, `sudo`, `dd`, etc.) are blocked at the engine layer in `settings.json`.
   - `temporary_deny_override` async context manager temporarily relaxes the deny list for a single turn when `force_override=True`, and **MUST** restore rules in a `finally:` block.
   - `ensure_deny_integrity()` runs at bot startup to restore any accidentally deleted deny rules.

3. **Incremental UTF-8 Decoding**:
   - Process standard pipes using `codecs.getincrementaldecoder("utf-8")` to avoid splitting multi-byte UTF-8 tokens across stream chunks.

4. **Atomic Disk Persistence**:
   - `sessions.json` is always saved via writing to a `.tmp` file and renaming via `os.replace` to prevent corrupted JSON writes.

---

## 🛠️ Verification & Test Recipes

### Run All Unit & Offline Tests
```bash
pytest tests/test_offline_components.py
```

### Run Security Pre-Flight Scan
```bash
python3 scripts/security_check.py
```

### Launch Development Server
```bash
./run.sh
```
