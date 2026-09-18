#!/usr/bin/env bash
# Build the PyInstaller sidecar and copy it into the Tauri binaries directory.
# Run from the repo root: ./build-backend.sh
#
# Prerequisites:
#   pip install pyinstaller   (in the backend venv)
#
# Output: src-tauri/binaries/higashi-backend-<target>
# where <target> is the Tauri triple (e.g. aarch64-apple-darwin).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
DESKTOP_DIR="$REPO_ROOT/../higashi-analytics-desktop"
BINARIES_DIR="$DESKTOP_DIR/src-tauri/binaries"
VENV="$REPO_ROOT/.venv"

# Detect Tauri target triple for the current host
TARGET_TRIPLE="$(rustc -vV 2>/dev/null | grep 'host:' | awk '{print $2}')"
if [ -z "$TARGET_TRIPLE" ]; then
  echo "Error: rustc not found. Install Rust to detect the target triple." >&2
  exit 1
fi

echo "Building backend for target: $TARGET_TRIPLE"
echo "Output: $BINARIES_DIR/higashi-backend-$TARGET_TRIPLE"

# Install PyInstaller into the venv if needed
"$VENV/bin/pip" install --quiet pyinstaller

# Run PyInstaller from the backend directory
cd "$BACKEND_DIR"
"$VENV/bin/pyinstaller" higashi.spec --distpath dist --workpath build --noconfirm

# Tauri expects: binaries/higashi-backend-<triple>  (or .exe on Windows)
mkdir -p "$BINARIES_DIR"
cp "dist/higashi-backend" "$BINARIES_DIR/higashi-backend-$TARGET_TRIPLE"
chmod +x "$BINARIES_DIR/higashi-backend-$TARGET_TRIPLE"

echo ""
echo "Done. Binary placed at:"
echo "  $BINARIES_DIR/higashi-backend-$TARGET_TRIPLE"
echo ""
echo "Now run: cd $DESKTOP_DIR && npx tauri dev"
