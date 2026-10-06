#!/usr/bin/env bash
# Cut a signed HWS release that a stranger can install.
#
#   ./release/release.sh 0.2.3
#   ./release/release.sh 0.2.3 --unsigned     a developer build, marked untrusted
#
# WHY THIS EXISTS
#
# HWS Live is a key you paste into your own HWS install, and until now there was
# no way for anybody to obtain HWS. The installer that existed cloned
# github.com/higashi-analytics/higashi-analytics - an organisation that is not
# Steve's - from an address advertised as get.higashi.dev, which does not
# resolve. It also ran `alembic upgrade head`, while the application applies its
# own migrations at startup. None of it could ever have worked.
#
# This produces what JDrive already has: one versioned tarball, a SHA-256, a
# detached signature and a plain-text statement of what was signed, published on
# our own host. No git and no GitHub, so a private repository is irrelevant.
#
# WHAT GOES IN, AND WHAT A CUSTOMER THEREFORE NEEDS
#
# The frontend is built HERE and shipped built, so an installing machine needs
# neither Node nor npm - only Python 3.9+ and systemd. That is the difference
# between "a hosting customer can install this" and "a developer can".
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=$ROOT/release/dist
VERSION=${1:-}
UNSIGNED=0
for arg in "$@"; do [ "$arg" = "--unsigned" ] && UNSIGNED=1; done
[ -n "$VERSION" ] && [ "$VERSION" != "--unsigned" ] || { echo "usage: release.sh <version> [--unsigned]"; exit 64; }
echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "version must look like 1.2.3"; exit 64; }

SIGNING_KEY=${HWS_RELEASE_SIGNING_KEY:-$HOME/.config/hws-release/signing-key.pem}
if [ "$UNSIGNED" = 0 ] && [ ! -r "$SIGNING_KEY" ]; then
  echo "No release signing key at $SIGNING_KEY."
  echo "Make one (it is separate from JDrive's on purpose - one key per product):"
  echo "  mkdir -p \"\$(dirname \"$SIGNING_KEY\")\" && chmod 700 \"\$(dirname \"$SIGNING_KEY\")\""
  echo "  openssl genpkey -algorithm ed25519 -out \"$SIGNING_KEY\" && chmod 600 \"$SIGNING_KEY\""
  echo "Or pass --unsigned for a developer build."
  exit 1
fi

COMMIT=$(git -C "$ROOT" rev-parse HEAD)
DIRTY=$(git -C "$ROOT" status --porcelain | grep -v '^?? ' | head -1 || true)
[ -z "$DIRTY" ] || echo "NOTE: the working tree has uncommitted changes; the commit recorded is $COMMIT"

echo "== HWS $VERSION from ${COMMIT:0:7}"

echo "-- build the frontend (shipped built, so no Node is needed to install)"
( cd "$ROOT/frontend" && npm ci --silent && npm run build >/dev/null )
[ -f "$ROOT/frontend/dist/index.html" ] || { echo "the frontend did not build"; exit 1; }

STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT
TREE=$STAGE/hws-$VERSION
mkdir -p "$TREE"

echo "-- assemble what actually runs"
# The backend source, its migrations, and the built frontend. Nothing else: no
# tests, no screenshots, no .git, no node_modules, no venv, no desktop build.
tar -C "$ROOT" -cf - \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  --exclude='*.db' --exclude='*.db-wal' --exclude='*.db-shm' \
  --exclude='settings.env' --exclude='.env' --exclude='.env.*' \
  --exclude='crawler_ranges.live.json' \
  --exclude='*.bak_*' --exclude='*.bak' --exclude='*.orig' \
  --exclude='tests' --exclude='test_*.py' --exclude='conftest.py' \
  --exclude='.pytest_cache' --exclude='dist' --exclude='build' --exclude='*.spec' \
  backend | tar -C "$TREE" -xf -
mkdir -p "$TREE/frontend"
cp -R "$ROOT/frontend/dist" "$TREE/frontend/dist"
# AGPL: the frontend assets above are COMPILED. Shipping them without the source
# they were built from leaves a recipient unable to rebuild or modify Higashi,
# which is the whole point of the licence. The source is small - no node_modules,
# that is what package-lock.json is for - so it travels with the release and a
# copy of the tarball is a complete, buildable Higashi.
for item in src public index.html package.json package-lock.json \
            vite.config.js tailwind.config.js postcss.config.js; do
  [ -e "$ROOT/frontend/$item" ] && cp -R "$ROOT/frontend/$item" "$TREE/frontend/$item"
done
cp "$ROOT/release/install.sh" "$TREE/install.sh"
chmod 755 "$TREE/install.sh"
cp "$ROOT/LICENSE" "$TREE/LICENSE" 2>/dev/null || true
printf '%s\n' "$VERSION" > "$TREE/VERSION"
printf '%s\n' "$COMMIT" > "$TREE/COMMIT"

# A settings file must never travel in a release: it would ship one install's
# SECRET_KEY to every other install.
#
# This is not hypothetical. The first run of this script was stopped by the check
# below, holding backend/.env.bak_portlog_20260924T073450Z - a real .env backup
# with a live SECRET_KEY, sitting untracked in the working tree. The exclusion
# list above said '.env' and did not match '.env.bak_*'. The check is what caught
# it, which is the argument for having a check as well as a list.
leaks=$(find "$TREE" \( -name 'settings.env' -o -name '.env' -o -name '*.db' \) -print)
[ -z "$leaks" ] || { echo "REFUSING, a release must carry no settings or database:"; echo "$leaks"; exit 1; }
# A SECRET_KEY with something after the '=' - the phrase on its own appears in
# the installer, which is where the value is generated rather than shipped.
secrets=$(grep -rlE 'SECRET_KEY=[A-Za-z0-9+/_-]{16}' "$TREE" 2>/dev/null || true)
[ -z "$secrets" ] || { echo "REFUSING, these carry a real secret:"; echo "$secrets"; exit 1; }
echo "   carries no settings file, no database and no secret value"

mkdir -p "$OUT/$VERSION"
TARBALL=$OUT/$VERSION/hws-$VERSION.tgz
echo "-- tar"
COPYFILE_DISABLE=1 tar -C "$STAGE" --no-xattrs -czf "$TARBALL" "hws-$VERSION"
# A server release of a web-stats app is a few megabytes. The first cut was
# 126 MB because backend/dist held the PyInstaller sidecar built for the desktop
# app - which has no business on a server. A size this wrong is easier to catch
# with a number than by reading an exclusion list.
BYTES=$(wc -c < "$TARBALL" | tr -d ' ')
MB=$((BYTES / 1048576))
echo "   tarball is ${MB} MB"
if [ "$MB" -gt 40 ]; then
  echo "REFUSING: ${MB} MB is too big for a server release. The largest things in it:"
  tar -tzvf "$TARBALL" | sort -k3 -rn | head -8 | awk '{printf "     %6.1f MB  %s\n", $3/1048576, $NF}'
  exit 1
fi
SHA=$(openssl dgst -sha256 -r "$TARBALL" | awk '{print $1}')
printf '%s  hws-%s.tgz\n' "$SHA" "$VERSION" > "$TARBALL.sha256"

echo "-- state what is being signed, in words as well as bytes"
{ printf 'HWS-RELEASE 1\n'
  printf 'file hws-%s.tgz\n' "$VERSION"
  printf 'sha256 %s\n' "$SHA"
  printf 'commit %s\n' "$COMMIT"
  printf 'version %s\n' "$VERSION"
  [ "$UNSIGNED" = 1 ] && printf 'UNSIGNED developer build - do not publish\n'
} > "$TARBALL.sig.txt"

if [ "$UNSIGNED" = 0 ]; then
  echo "-- sign"
  openssl pkeyutl -sign -rawin -inkey "$SIGNING_KEY" -in "$TARBALL.sig.txt" -out "$TARBALL.sig"
  openssl pkey -in "$SIGNING_KEY" -pubout -out "$OUT/$VERSION/hws-release-pubkey.pem"
  # Verify with the public half, the way an installer will, rather than trusting
  # that signing succeeded because openssl exited 0.
  openssl pkeyutl -verify -rawin -pubin -inkey "$OUT/$VERSION/hws-release-pubkey.pem" \
    -sigfile "$TARBALL.sig" -in "$TARBALL.sig.txt" >/dev/null \
    && echo "   signature verifies against the published public key" \
    || { echo "   the signature does not verify"; exit 1; }
else
  echo "-- UNSIGNED build; not publishable"
fi

cp "$ROOT/release/install.sh" "$OUT/$VERSION/install.sh"
chmod 644 "$OUT/$VERSION"/* 2>/dev/null || true
chmod 755 "$OUT/$VERSION/install.sh"

echo
echo "== $VERSION"
( cd "$OUT/$VERSION" && ls -lh | awk 'NR>1 {printf "   %-34s %s\n", $NF, $5}' )
echo "   sha256 $SHA"
echo "   publish with: ./release/publish.sh $VERSION"
