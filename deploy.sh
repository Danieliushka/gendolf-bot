#!/usr/bin/env bash
# Deploy Gendolf Bot as systemd service
set -euo pipefail

BOT_DIR="/root/.openclaw/workspace/projects/gendolf-bot"
ENV_FILE="$BOT_DIR/.env"
SERVICE_FILE="/etc/systemd/system/gendolf-bot.service"

# Check .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Missing .env — copy .env.example to .env and fill in values"
    exit 1
fi

# Create data dir
mkdir -p /var/lib/gendolf-bot

# Create systemd service
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Gendolf AI Bot — Telegram Group Assistant
After=network.target

[Service]
Type=simple
WorkingDirectory=$BOT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=/usr/bin/python3 $BOT_DIR/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
systemctl daemon-reload
systemctl enable gendolf-bot.service
systemctl start gendolf-bot.service

echo "✅ Gendolf Bot deployed!"
echo "   Status: systemctl status gendolf-bot"
echo "   Logs:   journalctl -u gendolf-bot -f"
