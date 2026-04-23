#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/bloom_dpa"
SERVICE_NAME="bloom-weighment.service"
LOG_DIR="/var/log/bloom_dpa"

echo "[1/6] Creating app and log directories"
sudo mkdir -p "$APP_DIR" "$LOG_DIR"

echo "[2/6] Copying project files"
sudo rsync -av --delete ./ "$APP_DIR"/ --exclude ".git" --exclude ".venv"

echo "[3/6] Setting ownership"
sudo chown -R www-data:www-data "$APP_DIR" "$LOG_DIR"

echo "[4/6] Installing python dependencies"
sudo /usr/bin/python3 -m pip install -r "$APP_DIR/requirements.txt"

echo "[5/6] Installing systemd unit"
sudo cp "$APP_DIR/deploy/systemd/$SERVICE_NAME" "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo "[6/6] Starting service"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager

echo "Done. Logs:"
echo "  tail -f /var/log/bloom_dpa/app.log"
echo "  tail -f /var/log/bloom_dpa/error.log"
