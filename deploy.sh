#!/usr/bin/env bash
set -e

echo "=== LeetCode Bot Deploy ==="

# Check Python version
PYTHON=$(command -v python3 || true)
if [ -z "$PYTHON" ]; then
    echo "Error: Python 3 not found"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1 | grep -oP '\d+\.\d+')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    echo "Error: Python 3.11+ required, found $PY_VERSION"
    exit 1
fi
echo "Python $PY_VERSION OK"

# Project directory
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv venv
fi

# Activate and install deps
echo "Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt --quiet

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    chmod 600 .env
    echo "!!! Please fill in .env with your tokens before starting the bot !!!"
fi

# Init DB
echo "Initializing database..."
python3 -c "import asyncio; from db.database import init_db; asyncio.run(init_db())"

# Create systemd service
SERVICE_NAME="leetcode-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Creating systemd service..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=LeetCode Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo ""
echo "=== Deploy complete ==="
sudo systemctl status "$SERVICE_NAME" --no-pager
echo ""
echo "Useful commands:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  journalctl -u $SERVICE_NAME -f"
