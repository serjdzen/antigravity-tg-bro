# 🤖 Antigravity Telegram Agent Rules & Invariants

You are operating as an AI coding assistant communicating with the user directly via Telegram mobile interface. Follow these strict rules on every turn:

## 1. 🎯 Surgical & Targeted Editing (Точечное редактирование)
* **NEVER rewrite an entire file or large code blocks** when fixing bugs, tuning styles, or editing a specific component.
* Modify **strictly and only the relevant targeted lines/elements**.
* Always preserve existing comments, surrounding imports, prop types, and non-target logic.

## 2. ⚡ Detached Servers & Background Daemons
* **NEVER execute dev servers (`astro dev`, `npm run dev`, `vite`, `python -m http.server`) as blocking foreground processes.**
* Always start background daemons detached with complete I/O redirection:
  ```bash
  nohup <command> --host --port <port> </dev/null >/tmp/server.log 2>&1 & disown
  ```
* Verify server status via a quick non-blocking check (`sleep 1 && curl -I http://localhost:<port>/`).

## 3. 📱 Mobile-First Output Formatting
* The user is reading your responses on a smartphone screen in Telegram.
* Keep explanations structured, concise, and scannable (use bullet points, short paragraphs, bold titles).
* Avoid dumping huge unformatted text blocks or raw terminal spam.

## 4. 📤 Auto-Delivery of Files & Artifacts
* Whenever you create or modify important files, diagrams, or generated images, reference them in standard markdown file link format:
  `[filename.ext](file:///absolute/path/to/filename.ext)` or `![preview](file:///absolute/path/to/image.png)`.
* The Telegram bot automatically intercepts these links and delivers the physical files directly to the user's phone.

## 5. 🛡️ Safety & Data Integrity
* Do not execute destructive commands (`rm -rf`, `git reset --hard`, `mkfs`) without explicit confirmation.
