#!/usr/bin/env bash

# Bloom DPA Manager (GCP-friendly)
# Single-file installer + service manager for this Flask app.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

show_progress() { echo -e "${CYAN}[$(date +'%H:%M:%S')]${NC} $1"; }
show_success() { echo -e "${GREEN}✓${NC} $1"; }
show_error() { echo -e "${RED}✗${NC} $1"; }
show_info() { echo -e "${BLUE}ℹ${NC} $1"; }
show_warning() { echo -e "${YELLOW}⚠${NC} $1"; }

CURRENT_USER="${SUDO_USER:-$USER}"
if [ "$CURRENT_USER" = "root" ]; then
  CURRENT_USER=$(who am i | awk '{print $1}' || echo "ubuntu")
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
PYTHON_EXEC="$VENV_DIR/bin/python3"
SERVICE_NAME="bloom-weighment"
ENV_FILE="/etc/${SERVICE_NAME}.env"
LOG_DIR="/var/log/bloom_dpa"
GUNICORN_BIND="127.0.0.1:8000"
NGINX_SITE="/etc/nginx/sites-available/${SERVICE_NAME}"

require_root() {
  if [ "$EUID" -ne 0 ]; then
    show_error "Run with sudo: sudo bash bloom_manager.sh <install|restart|status|logs>"
    exit 1
  fi
}

install_packages() {
  show_progress "Installing required apt packages"
  apt update -qq
  apt install -y python3 python3-pip python3-venv nginx sqlite3 curl git
  show_success "System packages installed"
}

setup_venv_and_deps() {
  show_progress "Creating/updating virtual environment"
  if [ ! -d "$VENV_DIR" ]; then
    sudo -u "$CURRENT_USER" python3 -m venv "$VENV_DIR"
  fi
  sudo -u "$CURRENT_USER" "$PYTHON_EXEC" -m pip install --upgrade pip
  sudo -u "$CURRENT_USER" "$PYTHON_EXEC" -m pip install -r "$APP_DIR/requirements.txt"
  sudo -u "$CURRENT_USER" "$PYTHON_EXEC" -m pip install gunicorn
  show_success "Python dependencies installed"
}

setup_logs_and_permissions() {
  show_progress "Configuring log directories and permissions"
  mkdir -p "$LOG_DIR"
  touch "$LOG_DIR/app.log" "$LOG_DIR/error.log" "$LOG_DIR/access.log"
  chown -R "$CURRENT_USER":"$CURRENT_USER" "$APP_DIR"
  chown -R "$CURRENT_USER":"$CURRENT_USER" "$LOG_DIR"
  chmod 755 "$APP_DIR"
  chmod 755 "$LOG_DIR"
  chmod 664 "$LOG_DIR"/*.log
  show_success "Log files ready under $LOG_DIR"
}

init_database() {
  show_progress "Initializing SQLite database schema"
  sudo -u "$CURRENT_USER" "$PYTHON_EXEC" - <<'PY'
from app import app, init_db
with app.app_context():
    init_db()
print("Database initialized")
PY
  show_success "Database initialized"
}

write_env_file() {
  if [ ! -f "$ENV_FILE" ]; then
    show_progress "Creating environment file at $ENV_FILE"
    cat > "$ENV_FILE" <<EOF
FLASK_SECRET_KEY=change-me-now
APP_USER=admin
APP_PASSWORD=admin123
EOF
    chmod 600 "$ENV_FILE"
    show_warning "Update credentials in $ENV_FILE before production use"
  else
    show_info "Using existing env file: $ENV_FILE"
  fi
}

write_systemd_service() {
  show_progress "Writing systemd service: ${SERVICE_NAME}.service"
  cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Bloom Weighment Flask (Gunicorn)
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn --workers 2 --bind ${GUNICORN_BIND} app:app
Restart=always
RestartSec=5
StandardOutput=append:${LOG_DIR}/app.log
StandardError=append:${LOG_DIR}/error.log

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "/etc/systemd/system/${SERVICE_NAME}.service"
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}.service"
  show_success "Systemd service configured"
}

write_nginx_config() {
  show_progress "Configuring Nginx reverse proxy"
  cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    server_name _;

    access_log ${LOG_DIR}/access.log;
    error_log ${LOG_DIR}/error.log;

    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://${GUNICORN_BIND};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

  ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable nginx
  systemctl restart nginx
  show_success "Nginx configured and running"
}

start_services() {
  show_progress "Starting Bloom service"
  systemctl restart "${SERVICE_NAME}.service"
  sleep 2
  if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    show_success "${SERVICE_NAME}.service is running"
  else
    show_error "${SERVICE_NAME}.service failed to start"
    journalctl -u "${SERVICE_NAME}.service" -n 40 --no-pager || true
    exit 1
  fi
}

print_summary() {
  local local_ip
  local_ip="$(hostname -I | awk '{print $1}')"
  echo ""
  echo "=========================================="
  echo -e "${GREEN}Bloom DPA setup complete${NC}"
  echo "=========================================="
  echo -e "App URL:      ${BLUE}http://${local_ip}${NC}"
  echo -e "Local URL:    ${BLUE}http://localhost${NC}"
  echo -e "Service:      sudo systemctl status ${SERVICE_NAME}"
  echo -e "App logs:     tail -f ${LOG_DIR}/app.log"
  echo -e "Error logs:   tail -f ${LOG_DIR}/error.log"
  echo -e "Nginx logs:   tail -f ${LOG_DIR}/access.log"
  echo ""
  show_info "On GCP, allow inbound HTTP in VPC firewall for port 80."
}

full_install() {
  require_root
  install_packages
  setup_venv_and_deps
  setup_logs_and_permissions
  write_env_file
  init_database
  write_systemd_service
  write_nginx_config
  start_services
  print_summary
}

restart_all() {
  require_root
  systemctl restart "${SERVICE_NAME}.service"
  systemctl restart nginx
  show_success "Services restarted"
}

status_all() {
  require_root
  systemctl status "${SERVICE_NAME}.service" --no-pager || true
  systemctl status nginx --no-pager || true
}

show_logs() {
  require_root
  echo "1) App log"
  echo "2) Error log"
  echo "3) Nginx access log"
  echo "4) Service journal"
  read -r -p "Select log (1-4): " choice
  case "$choice" in
    1) tail -n 80 "$LOG_DIR/app.log" ;;
    2) tail -n 80 "$LOG_DIR/error.log" ;;
    3) tail -n 80 "$LOG_DIR/access.log" ;;
    4) journalctl -u "${SERVICE_NAME}.service" -n 80 --no-pager ;;
    *) show_error "Invalid choice" ;;
  esac
}

usage() {
  cat <<EOF
Usage:
  sudo bash bloom_manager.sh install   # Full install + setup + start
  sudo bash bloom_manager.sh restart   # Restart app + nginx
  sudo bash bloom_manager.sh status    # Show service status
  sudo bash bloom_manager.sh logs      # View logs
EOF
}

main() {
  local cmd="${1:-install}"
  case "$cmd" in
    install) full_install ;;
    restart) restart_all ;;
    status) status_all ;;
    logs) show_logs ;;
    *) usage; exit 1 ;;
  esac
}

main "${1:-}"
