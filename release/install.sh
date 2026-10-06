#!/bin/sh
# HWS — Higashi Web Stats. Installer.
#
#   curl -fsSL https://hws.jotnotes.com/releases/install.sh | sudo sh
#
# or, having downloaded a release yourself:
#
#   sudo sh install.sh
#
# WHAT IT NEEDS: Python 3.9 or newer, and systemd. That is all. The frontend
# arrives already built, so there is no Node, no npm and no build step here; the
# release is a signed tarball on our own host, so there is no git either.
#
# WHAT IT DOES
#   1. downloads the release and VERIFIES it - SHA-256 and a signature
#   2. unpacks it to /opt/hws
#   3. makes a Python virtual environment and installs the dependencies
#   4. writes settings.env with a freshly generated SECRET_KEY
#   5. installs and starts a systemd service
#   6. configures nginx as a reverse proxy, if nginx is present
#
# It does not run database migrations, because the application applies its own at
# startup. An earlier version of this script ran `alembic upgrade head`, which
# was never how this works.
#
# Re-running it upgrades in place: settings.env and the database are left alone.
set -eu

BASE="${HWS_BASE_URL:-https://hws.jotnotes.com/releases}"
VERSION="${HWS_VERSION:-latest}"
DIR="${HWS_DIR:-/opt/hws}"
PORT="${HWS_PORT:-8000}"
SERVICE="${HWS_SERVICE:-hws}"
SKIP_VERIFY="${HWS_SKIP_VERIFY:-0}"
# For a machine that already has a web server configured by hand - Caddy, Apache,
# an existing nginx - and for installing a second copy alongside a first.
SKIP_NGINX="${HWS_SKIP_NGINX:-0}"

info()  { printf '\033[0;32m▶\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m⚠\033[0m  %s\n' "$*"; }
die()   { printf '\033[0;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo sh install.sh"

for cmd in python3 curl tar openssl; do
  command -v "$cmd" >/dev/null 2>&1 || die "$cmd is required but is not installed."
done
python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,9) else 1)' \
  || die "Python 3.9+ is required. Found: $(python3 --version 2>&1)"

# python3 being present does not mean `python3 -m venv` can finish. Debian and
# Ubuntu ship the venv module but split ensurepip into a separate package, so a
# stock server passes every check above and then dies partway through the
# install with a pip traceback, having already written files. Check it here,
# before anything is created, and say exactly what to run.
if ! python3 -c 'import ensurepip, venv' >/dev/null 2>&1; then
  pyver=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
  if command -v apt-get >/dev/null 2>&1; then
    die "python3 -m venv cannot complete here: the ensurepip module is missing.
  Debian and Ubuntu ship it separately. Install it, then run this again:

      sudo apt-get install -y python${pyver}-venv

  If that exact version is unavailable, python3-venv pulls in the right one."
  fi
  die "python3 -m venv cannot complete here: the ensurepip module is missing.
  Install your distribution's Python venv package, then run this again."
fi

command -v systemctl >/dev/null 2>&1 || die "This installer expects systemd."

WORK=$(mktemp -d)
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT INT TERM

if [ "$VERSION" = latest ]; then
  info "Asking $BASE which version is current..."
  VERSION=$(curl -fsSL "$BASE/latest" 2>/dev/null | tr -d ' \t\r\n') \
    || die "Could not reach $BASE/latest. Set HWS_VERSION=x.y.z to install a known version."
  echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$' \
    || die "$BASE/latest did not name a version (got: $VERSION)"
fi
info "Installing HWS $VERSION"

TGZ="hws-$VERSION.tgz"
for f in "$TGZ" "$TGZ.sha256" "$TGZ.sig.txt" "$TGZ.sig" hws-release-pubkey.pem; do
  curl -fsSL -o "$WORK/$f" "$BASE/$VERSION/$f" \
    || die "Could not download $f from $BASE/$VERSION/"
done

# ── Verify before unpacking, not after ───────────────────────────────────────
#
# The order matters: a tarball is unpacked as root, so anything checked after
# unpacking is checked too late.
if [ "$SKIP_VERIFY" = 1 ]; then
  warn "HWS_SKIP_VERIFY=1 - installing WITHOUT checking the download. Do not do this."
else
  info "Checking the download..."
  WANT=$(awk '{print $1}' "$WORK/$TGZ.sha256")
  GOT=$(openssl dgst -sha256 -r "$WORK/$TGZ" | awk '{print $1}')
  [ "$WANT" = "$GOT" ] || die "The download does not match its checksum. Delete it and try again."

  # The signature covers sig.txt, which NAMES the sha256 above. So: the signature
  # proves the statement is ours, and the statement pins the bytes. Checking the
  # signature alone would prove only that we once signed something.
  grep -qx "sha256 $GOT" "$WORK/$TGZ.sig.txt" \
    || die "The signed statement does not name this file's checksum."
  grep -q '^UNSIGNED' "$WORK/$TGZ.sig.txt" \
    && die "This is an unsigned developer build and must not be installed."
  openssl pkeyutl -verify -rawin -pubin -inkey "$WORK/hws-release-pubkey.pem" \
    -sigfile "$WORK/$TGZ.sig" -in "$WORK/$TGZ.sig.txt" >/dev/null 2>&1 \
    || die "The signature on this release is not valid. Do not install it."
  info "Checksum and signature are good."
fi

tar -C "$WORK" -xzf "$WORK/$TGZ"
SRC="$WORK/hws-$VERSION"
[ -f "$SRC/backend/main.py" ] || die "The release does not look complete."

UPGRADE=0
[ -d "$DIR/backend" ] && UPGRADE=1

info "$([ "$UPGRADE" = 1 ] && echo Upgrading || echo Installing) at $DIR"
mkdir -p "$DIR"
# The database and settings live here and must survive an upgrade, so the code
# directories are replaced individually rather than the whole of $DIR.
rm -rf "$DIR/backend.replacing" "$DIR/frontend.replacing"
cp -R "$SRC/backend" "$DIR/backend.replacing"
cp -R "$SRC/frontend" "$DIR/frontend.replacing"
[ -d "$DIR/backend" ] && mv "$DIR/backend" "$DIR/backend.previous.$$"
[ -d "$DIR/frontend" ] && mv "$DIR/frontend" "$DIR/frontend.previous.$$"
mv "$DIR/backend.replacing" "$DIR/backend"
mv "$DIR/frontend.replacing" "$DIR/frontend"
rm -rf "$DIR/backend.previous.$$" "$DIR/frontend.previous.$$"
cp "$SRC/VERSION" "$SRC/COMMIT" "$DIR/" 2>/dev/null || true

info "Python environment..."
[ -d "$DIR/.venv" ] || python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --quiet --upgrade pip
"$DIR/.venv/bin/pip" install --quiet -r "$DIR/backend/requirements-minimal.txt"

SETTINGS="$DIR/settings.env"
if [ -f "$SETTINGS" ]; then
  info "Keeping the settings and database already here."
  # An earlier installer wrote HIGASHI_ENV_PATH into this file, which stops the
  # application starting. Take it out rather than leaving an upgrade broken.
  if grep -q '^HIGASHI_ENV_PATH=' "$SETTINGS"; then
    sed -i.before-upgrade '/^HIGASHI_ENV_PATH=/d' "$SETTINGS"
    chmod 600 "$SETTINGS" "$SETTINGS.before-upgrade" 2>/dev/null || true
    info "Removed a HIGASHI_ENV_PATH line that would have stopped it starting."
  fi
else
  info "Generating settings.env with a new SECRET_KEY..."
  SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
  # HIGASHI_ENV_PATH is a PROCESS variable, set in the unit below, not a line in
  # this file. pydantic reads this file into Settings, which forbids unknown
  # fields, so a HIGASHI_ENV_PATH line here stops the application starting:
  #   ValidationError: higashi_env_path - Extra inputs are not permitted
  # The old installer wrote it here, which is one reason it could never have
  # worked. The already-running install sets it with systemd Environment=.
  cat > "$SETTINGS" <<SETTINGSEOF
SECRET_KEY=$SECRET
DATABASE_URL=sqlite+aiosqlite:///$DIR/hws.db
SETTINGSEOF
  chmod 600 "$SETTINGS"
fi

info "systemd service..."
cat > /etc/systemd/system/$SERVICE.service <<UNITEOF
[Unit]
Description=HWS (Higashi Web Stats)
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR/backend
Environment=HIGASHI_ENV_PATH=$SETTINGS
EnvironmentFile=$SETTINGS
ExecStart=$DIR/.venv/bin/uvicorn main:app --host 127.0.0.1 --port $PORT --workers 2
Restart=always
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNITEOF
systemctl daemon-reload
systemctl enable $SERVICE >/dev/null 2>&1 || true
systemctl restart $SERVICE

# Published crawler ranges go out of date. HWS calls an address outside a
# vendor's published range a forged identity claim, which is only fair while the
# ranges are current, so it stops making that claim once the file ages past its
# threshold. Without a refresh every install would quietly lose forgery
# detection a fortnight in, so schedule the refresh the installer already ships.
# This is the one component that makes outbound requests, and it sends no host
# or traffic data. Set HIGASHI_CRAWLER_RANGE_FETCH=0 in the settings file to
# turn it off; the verifier then reports unverified rather than forged.
info "weekly crawler-range refresh..."
cat > /etc/systemd/system/$SERVICE-refresh-crawlers.service <<UNITEOF
[Unit]
Description=HWS crawler range refresh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$DIR/backend
Environment=HIGASHI_ENV_PATH=$SETTINGS
EnvironmentFile=$SETTINGS
ExecStart=$DIR/.venv/bin/python scripts/fetch_crawler_ranges.py
NoNewPrivileges=yes
PrivateTmp=yes
StandardOutput=journal
StandardError=journal
UNITEOF
cat > /etc/systemd/system/$SERVICE-refresh-crawlers.timer <<UNITEOF
[Unit]
Description=Refresh HWS crawler ranges weekly

[Timer]
OnCalendar=Tue *-*-* 03:30:00
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
UNITEOF
systemctl daemon-reload
systemctl enable --now $SERVICE-refresh-crawlers.timer >/dev/null 2>&1 || true
# Run it once now so the bundled snapshot is replaced by current data, and is
# stamped, rather than waiting up to a week for the first scheduled run.
systemctl start $SERVICE-refresh-crawlers.service >/dev/null 2>&1 || true

# It binds to 127.0.0.1, so nginx is how anybody reaches it.
if [ "$SKIP_NGINX" = 1 ]; then
  info "Leaving the web server alone (HWS_SKIP_NGINX=1). HWS listens on 127.0.0.1:$PORT."
elif command -v nginx >/dev/null 2>&1; then
  if [ -f "/etc/nginx/sites-available/$SERVICE" ]; then
    info "Leaving the existing nginx configuration alone."
  else
    info "nginx reverse proxy..."
    cat > "/etc/nginx/sites-available/$SERVICE" <<NGINXEOF
server {
    listen 80;
    server_name _;
    client_max_body_size 200m;
    root $DIR/frontend/dist;
    index index.html;
    location /api/ {
        proxy_pass         http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
    }
    location /assets/ { expires 30d; add_header Cache-Control "public, immutable"; try_files \$uri =404; }
    location / { try_files \$uri \$uri/ /index.html; }
}
NGINXEOF
    ln -sf "/etc/nginx/sites-available/$SERVICE" "/etc/nginx/sites-enabled/$SERVICE"
    if nginx -t >/dev/null 2>&1; then systemctl reload nginx
    else warn "nginx refused the configuration; it has been left unlinked."; rm -f "/etc/nginx/sites-enabled/$SERVICE"; fi
  fi
else
  warn "nginx is not installed. HWS listens on 127.0.0.1:$PORT; put a web server in front of it."
fi

printf '\n'
i=0
while [ $i -lt 30 ]; do
  curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  i=$((i+1)); sleep 1
done
if curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
  info "HWS $VERSION is running."
else
  warn "HWS did not answer on 127.0.0.1:$PORT within 30s. Check: journalctl -u $SERVICE -n 40"
  exit 1
fi

cat <<DONEEOF

  HWS $VERSION is installed at $DIR.

  Open it in a browser and create the first account. Then, to add HWS Live:
  Intelligence -> the HWS Live card -> paste your key -> Save.

  A Live key is bought at https://shop.jotnotes.com/buy?product=hws-live&plan=monthly
  Connecting one:         https://hws.jotnotes.com/kb/your-key.html

  Logs:    journalctl -u $SERVICE -f
  Restart: systemctl restart $SERVICE
DONEEOF
