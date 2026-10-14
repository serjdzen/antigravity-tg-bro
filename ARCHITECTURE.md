# 🏛️ Architecture & System Design: Antigravity Telegram

This document details the internal design, concurrency patterns, and data flow of the **Antigravity Telegram Bot**.

---

## 1. High-Level Architecture

The bot bridges Telegram's asynchronous event loop with the local execution environment of **Google Antigravity**:

```
[ Telegram App ]
       │
       ▼ (Long Polling / Webhook)
[ aiogram 3.x Dispatcher ]
       │
       ├──► [ AuthMiddleware ] ─── (Blocks unauthorized user IDs)
       │
       ├──► [ VoiceTranscriber ] ── (Groq Whisper Large v3 Turbo)
       │
       └──► [ AntigravityBridge ]
                  │
                  ├──► Subprocess `agy` CLI (Google AI Pro/Ultra Quotas)
                  │          │
                  │          ├── In-Place Live Streamer (1.4s throttle)
                  │          ├── Incremental UTF-8 Codec
                  │          └── Attachment Regex Extractor
                  │
                  └──► Python SDK Fallback (Gemini API Key)
```

---

## 2. Dual-Engine Bridge

### 2.1 CLI Mode (`Antigravity CLI`)
* Invokes `~/.local/bin/agy` via `asyncio.create_subprocess_exec`.
* Preserves user's local Google AI Pro / Ultra subscription quotas without requiring paid external API endpoints.
* Runs multi-turn conversations through `--conversation <ID>`, keeping brain artifacts in `~/.gemini/antigravity-cli/brain/<ID>/`.

### 2.2 SDK Mode (`Python SDK`)
* Invokes `google-antigravity` package directly.
* Acts as a cloud fallback when running in containerized environments (Docker/Cloud VPS) without local CLI binaries.

---

## 3. Real-Time Streaming & Formatting

1. **Chunk Splitting Problem**: LLMs stream token fragments as raw bytes. If a multi-byte UTF-8 character (e.g. Cyrillic or emojis) is split across chunks, standard `.decode('utf-8')` throws errors.
   - **Solution**: The engine uses `codecs.getincrementaldecoder('utf-8')` to decode streaming stdout cleanly.
2. **FloodWait Throttling**: Telegram limits message edits to ~1-2 edits per second per chat.
   - **Solution**: `LiveStreamer` buffers tokens and updates Telegram messages via `edit_message_text` with an adaptive 1.4-second rate limit.
3. **Expandable Thought Blocks**: Reasoning steps and tool executions are styled with HTML blockquotes (`<blockquote expandable>`).
4. **Native Rich Messages («Статья») & Table Handling**: Markdown tables are rendered natively as Telegram Rich Messages (`InputRichMessage`) with up to 32,768 characters. If rejected by Telegram clients, a 3-tier fallback automatically converts tables into responsive mobile Card Layout blocks (`<blockquote>`), preventing broken tables on smartphones.

---

## 4. 2-Tier Security Model

| Layer | Mechanism | Scope |
| :--- | :--- | :--- |
| **Tier 1: Deny List** | `"deny": ["command(rm*)", "command(sudo*)", ...]` in `settings.json` | Active by default for all turns. Blocked actions return error messages to the agent. |
| **Tier 2: Interactive Override** | `temporary_deny_override` context manager | Temporarily lifts rules for 1 turn on explicit user tap (`/force`), restoring rules in `finally:`. |
| **Integrity Guard** | `ensure_deny_integrity()` | Runs on `main.py` startup to repair missing deny rules. |

---

## 5. Storage & Multi-Session Management

* **`data/sessions.json`**: Stores user chat trees, active directories, selected models, and thinking effort settings.
* **Atomic Writes**: Uses temporary files (`.tmp`) and `os.replace` to prevent corrupted JSON writes in case of abrupt termination.
* **Concurrency Lock**: `async with session.lock:` enforces single-turn execution per user, eliminating race conditions.

---

## 6. Context Management & Stateful Handover (/compact)

* **Automatic Context Monitoring**: Monitors conversation transcript size and message count (`> 2.0 MB` or `> 80` messages). Displays an unobtrusive visual footer warning with a divider `───────────────` suggesting compaction.
* **Stateful Handover Protocol**: `/compact` triggers a native in-session high-effort summarization (`agy --conversation <conv_id> --effort high -p "..."`). It generates a structured handover summary (current goal, architectural decisions, modified files, active state, and next steps) before switching to a fresh conversation ID.
* **Seamless Context Injection**: The summary is injected into `<previous_context_summary>` on the first turn of the new session, ensuring 0% loss of continuity while shrinking transcript payload back to zero.
* **Streamer Honesty**: Prevents misleading "done" completions on failed or empty agent runs, rendering an honest warning banner instead.
