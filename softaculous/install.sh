#!/bin/sh
# Higashi Analytics — VPS one-liner installer
#
# Usage:
#   curl -fsSL https://get.higashi.dev | sh
#
# What it does:
#   1. Clones the repo (or uses current dir if already present)
#   2. Creates a Python venv and installs dependencies
#   3. Builds the React frontend
#   4. Generates a SECRET_KEY and writes settings.env
#   5. Runs DB migrations
#   6. Installs a systemd service (higashi.service)
#   7. Optionally installs nginx as a reverse proxy
#
# Requirements: Python 3.9+, Node 18+, git, systemd (Linux)

set -e

REPO_URL="https://github.com/higashi-analytics/higashi-analytics.git"
INSTALL_DIR="${HIGASHI_DIR:-/opt/higashi}"
PORT="${HIGASHI_PORT:-8000}"
BIND="0.0.0.0"
SERVICE="higashi"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { printf "${GREEN}▶${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}⚠${NC}  %s\n" "$*"; }
error() { printf "${RED}✗${NC} %s\n" "$*"; exit 1; }

# ── Root check ────────────────────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
  error "Please run as root: sudo sh install.sh"
fi

# ── Dependencies ──────────────────────────────────────────────────────────────
for cmd in python3 git node npm; do
  command -v "$cmd" >/dev/null 2>&1 || error "$cmd is required but not installed."
done

PYVER=$(python3 -c 'import sys; print(sys.version_info[:2] >= (3,9))' 2>/dev/null)
[ "$PYVER" = "True" ] || error "Python 3.9+ required. Found: $(python3 --version)"

# ── Clone or update ───────────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating existing installation at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  info "Cloning Higashi to $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── Python venv ───────────────────────────────────────────────────────────────
info "Setting up Python environment..."
python3 -m venv .venv
.venv/bin/pip install --quiet -r backend/requirements-minimal.txt

# ── Frontend build ────────────────────────────────────────────────────────────
info "Building frontend..."
cd frontend && npm ci --silent && npm run build && cd ..

# ── settings.env ─────────────────────────────────────────────────────────────
SETTINGS="$INSTALL_DIR/settings.env"
if [ ! -f "$SETTINGS" ]; then
  info "Generating settings.env..."
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > "$SETTINGS" <<EOF
SECRET_KEY=$SECRET
DATABASE_URL=sqlite+aiosqlite:///$INSTALL_DIR/higashi.db
HIGASHI_ENV_PATH=$SETTINGS
EOF
  chmod 600 "$SETTINGS"
fi

# ── Database migrations ───────────────────────────────────────────────────────
info "Running database migrations..."
cd backend
HIGASHI_ENV_PATH="$SETTINGS" ../.venv/bin/alembic upgrade head
cd ..

# ── systemd service ───────────────────────────────────────────────────────────
info "Installing systemd service..."
cat > /etc/systemd/system/${SERVICE}.service <<EOF
[Unit]
Description=Higashi Analytics
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR/backend
EnvironmentFile=$SETTINGS
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn main:app --host $BIND --port $PORT --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"

# ── Nginx (optional) ──────────────────────────────────────────────────────────
if command -v nginx >/dev/null 2>&1; then
  info "Configuring nginx reverse proxy..."
  cat > /etc/nginx/sites-available/higashi <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass         http://127.0.0.1:$PORT;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF
  ln -sf /etc/nginx/sites-available/higashi /etc/nginx/sites-enabled/higashi
  nginx -t && systemctl reload nginx
  warn "Add TLS: certbot --nginx -d your-domain.com"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "your-server-ip")

printf "\n${GREEN}✓ Higashi Analytics is running.${NC}\n\n"
echo "  URL:     http://$HOST_IP"
echo "  Setup:   http://$HOST_IP/setup   (first time only)"
echo "  Logs:    journalctl -u $SERVICE -f"
echo "  Restart: systemctl restart $SERVICE"
echo ""
echo "  To add TLS: certbot --nginx -d your-domain.com"
