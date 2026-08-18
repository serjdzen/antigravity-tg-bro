#!/usr/bin/env bash
set -e

PLIST_NAME="com.antigravity.tgbot.plist"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"
BIN_DIR="$HOME/.local/bin"
DAEMON_BIN="$BIN_DIR/antigravity-tg-daemon"

mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$TARGET_DIR"
mkdir -p "$BIN_DIR"

generate_plist() {
    local py_ver
    py_ver="$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.12")"

    cat <<EOF > "$TARGET_PLIST"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.antigravity.tgbot</string>

    <key>ProgramArguments</key>
    <array>
        <string>${DAEMON_BIN}</string>
        <string>${PROJECT_DIR}/main.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/logs/bot_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/logs/bot_stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${PROJECT_DIR}/.venv/bin:${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>${HOME}</string>
        <key>VIRTUAL_ENV</key>
        <string>${PROJECT_DIR}/.venv</string>
        <key>PYTHONPATH</key>
        <string>${PROJECT_DIR}/.venv/lib/python${py_ver}/site-packages:${PROJECT_DIR}</string>
    </dict>
</dict>
</plist>
EOF
}

case "$1" in
    install)
        if [ ! -d "$PROJECT_DIR/.venv" ]; then
            echo "📦 Virtual environment not found. Creating .venv..."
            python3 -m venv "$PROJECT_DIR/.venv"
            "$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
        fi

        echo "📦 Setting up named binary alias antigravity-tg-daemon..."
        ln -sf "$PROJECT_DIR/.venv/bin/python" "$DAEMON_BIN"

        echo "📦 Generating and installing macOS LaunchAgent..."
        generate_plist

        launchctl unload "$TARGET_PLIST" 2>/dev/null || true
        launchctl load "$TARGET_PLIST"
        echo "✅ Antigravity TG Bot successfully installed as macOS LaunchAgent service!"
        echo "📊 Service process name in Activity Monitor: antigravity-tg-daemon"
        ;;
    start)
        echo "🚀 Starting service..."
        launchctl load "$TARGET_PLIST" 2>/dev/null || launchctl start com.antigravity.tgbot
        echo "✅ Service started."
        ;;
    stop)
        echo "🛑 Stopping service..."
        launchctl unload "$TARGET_PLIST" 2>/dev/null || true
        echo "✅ Service stopped."
        ;;
    restart)
        echo "🔄 Restarting service..."
        launchctl unload "$TARGET_PLIST" 2>/dev/null || true
        sleep 1
        launchctl load "$TARGET_PLIST"
        echo "✅ Service restarted."
        ;;
    status)
        echo "📊 Checking LaunchAgent status:"
        launchctl list | grep "com.antigravity.tgbot" || echo "⚠️ Service is not currently running in launchctl."
        ;;
    logs)
        echo "📄 Streaming logs (Ctrl+C to exit):"
        tail -f "$PROJECT_DIR/logs/bot_stdout.log" "$PROJECT_DIR/logs/bot_stderr.log"
        ;;
    uninstall)
        echo "🗑 Removing service..."
        launchctl unload "$TARGET_PLIST" 2>/dev/null || true
        rm -f "$TARGET_PLIST"
        rm -f "$DAEMON_BIN"
        echo "✅ Service removed from macOS LaunchAgents."
        ;;
    *)
        echo "Usage: ./scripts/service.sh {install|start|stop|restart|status|logs|uninstall}"
        exit 1
        ;;
esac
