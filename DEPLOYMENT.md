# 🚀 Deployment Guide (For Developers)

This guide covers deployment options for **Antigravity Telegram Bot** across macOS, Linux servers, and containerized environments.

---

## 📋 Prerequisites

Before starting, ensure you have:
1. **Python 3.10+** (Python 3.11, 3.12, 3.13, 3.14 supported).
2. **Telegram Bot Token**: Create a new bot with [@BotFather](https://t.me/BotFather) and obtain the HTTP API token.
3. **Your Telegram User ID**: Get your numeric ID from [@userinfobot](https://t.me/userinfobot) or [@raw_data_bot](https://t.me/raw_data_bot).
4. **Google Antigravity Engine** (One or both):
   * **Antigravity CLI (`agy`)**: Installed locally via `npm install -g @google/antigravity` or official installer, and authenticated with your Google Account (`agy auth`).
   * **Gemini API Key**: From [Google AI Studio](https://aistudio.google.com/apikey).
5. **Groq API Key (Optional)**: Free key from [Groq Console](https://console.groq.com/keys) for Whisper voice transcription.

---

## 🌐 Language & Localization Configuration

Antigravity Telegram Bot includes a built-in i18n localization engine (`src/bot/locales.py`):

1. **Default Global Language**:
   Set `BOT_LANGUAGE` in your `.env` file:
   ```env
   BOT_LANGUAGE=en    # English (Default)
   # BOT_LANGUAGE=ru  # Russian
   ```
2. **Runtime In-Bot Switching**:
   Users can switch between English and Russian at any time via the `/settings` menu by tapping the **`🌐 Language`** button. The preference is persisted across restarts in `data/sessions.json`.
3. **Adding New Languages**:
   Translations are organized as simple key-value dictionaries in `src/bot/locales.py`. To add another language (e.g. Spanish, German, Chinese), simply add the language code to the message mappings.

---

## 🛠️ Method 1: macOS Background Daemon (Recommended for Mac)

Use the built-in `service.sh` script to install the bot as a persistent macOS `LaunchAgent`. The script automatically configures dynamic paths and creates a named binary alias.

### 1. Installation
```bash
git clone https://github.com/serjdzen/antigravity-tg-bro.git
cd antigravity-tg-bro

cp .env.example .env
# Edit .env with your BOT_TOKEN and ALLOWED_USER_IDS

./scripts/service.sh install
```

### 2. Service Management Commands
```bash
./scripts/service.sh status     # Check if the service is running
./scripts/service.sh logs       # Follow logs in real-time
./scripts/service.sh restart    # Restart after configuration changes
./scripts/service.sh stop       # Temporarily stop the service
./scripts/service.sh uninstall  # Remove from macOS LaunchAgents
```

---

## 🐧 Method 2: Linux Server (Systemd Service)

To deploy the bot on an Ubuntu/Debian/CentOS server or VPS:

### 1. Clone and Setup
```bash
cd /opt
sudo git clone https://github.com/serjdzen/antigravity-tg-bro.git
sudo chown -R $USER:$USER /opt/antigravity-tg-bro
cd /opt/antigravity-tg-bro

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in .env credentials
```

### 2. Create Systemd Unit
Create `/etc/systemd/system/antigravity-tg.service`:
```ini
[Unit]
Description=Antigravity Telegram Bot Daemon
After=network.target

[Service]
Type=simple
User=your_linux_user
WorkingDirectory=/opt/antigravity-tg-bro
ExecStart=/opt/antigravity-tg-bro/.venv/bin/python main.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/antigravity-tg-bro/.env

[Install]
WantedBy=multi-user.target
```

### 3. Enable and Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable antigravity-tg
sudo systemctl start antigravity-tg
sudo journalctl -u antigravity-tg -f
```

---

## 🐳 Method 3: Docker Deployment

You can containerize the SDK mode of the bot for standalone cloud deployment:

### `Dockerfile`
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### `docker-compose.yml`
```yaml
version: '3.8'

services:
  antigravity-bot:
    build: .
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

---

## ❓ Troubleshooting & FAQ

### 1. `Telegram API Error: 403 Forbidden`
* **Cause**: The bot was stopped or blocked by the user in Telegram.
* **Fix**: Send `/start` to the bot in Telegram.

### 2. Voice messages are not transcribing
* **Cause**: `GROQ_API_KEY` is missing or invalid in `.env`.
* **Fix**: Obtain a free API key from [console.groq.com](https://console.groq.com/keys) and paste it into `.env`.

### 3. `Permission Denied` when deleting files
* **Cause**: The 2-Tier Security Model blocks destructive commands by default.
* **Fix**: Tap `[ ⚡ Force Override ]` under the inline approval message or use `/force` in your prompt.

### 4. Pydantic Settings Conflict in Child MCP Servers
* **Solution**: Handled automatically in `src/config.py` via `del os.environ[key]` cleanup, preventing child processes with `extra='forbid'` from failing.
