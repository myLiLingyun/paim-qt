#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Install paim for the current user.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "paim: python3 was not found; install Python 3 first." >&2
  exit 1
fi

# Prefer an existing virtual environment.  If the system Python already has
# PyQt6 and Pillow, use it directly instead of downloading wheels into a venv.
if [ -x "$PY" ]; then
  printf '%s\n' "Using the existing virtual environment in $VENV"
elif python3 -c 'import PyQt6, PIL' >/dev/null 2>&1; then
  printf '%s\n' "Using the system PyQt6 and Pillow"
  PY=python3
else
  if [ -n "${PAIM_PIP_INDEX_URL:-}" ]; then
    PIP_INDEX_URL=$PAIM_PIP_INDEX_URL
    export PIP_INDEX_URL
  elif [ -z "${PIP_INDEX_URL:-}" ]; then
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
    export PIP_INDEX_URL
  fi
  printf '%s\n' "Creating virtual environment in $VENV"
  python3 -m venv "$VENV"
  printf '%s\n' "Installing Python dependencies from $PIP_INDEX_URL"
  "$PY" -m pip install --disable-pip-version-check --no-input -r "$ROOT/requirements.txt"
fi

if ! "$PY" -c 'import PyQt6, PIL' >/dev/null 2>&1; then
  printf '%s\n' "paim: dependencies were installed, but importing PyQt6/Pillow failed." >&2
  printf '%s\n' "Install PyQt6 (and the Qt6 runtime) for your Python interpreter." >&2
  exit 1
fi

mkdir -p "$BIN" "$APPS" "$ICONS"
ln -sf "$ROOT/paim" "$BIN/paim"
install -m 644 "$ROOT/assets/paim.png" "$ICONS/paim.png"

# GUI sessions often do not include ~/.local/bin in PATH.  Write an absolute
# Exec path (and an absolute icon path) into the installed desktop entry.
TMP_DESKTOP=$(mktemp)
trap 'rm -f "$TMP_DESKTOP"' EXIT HUP INT TERM
awk -v exec_line="Exec=\"$BIN/paim\" %F" -v icon_line="Icon=$ICONS/paim.png" '
  /^Exec=/ { print exec_line; next }
  /^Icon=/ { print icon_line; next }
  { print }
' "$ROOT/paim.desktop" > "$TMP_DESKTOP"
install -m 644 "$TMP_DESKTOP" "$APPS/paim.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi
printf '%s\n' "paim installed to $BIN/paim"
printf '%s\n' "Desktop entry: $APPS/paim.desktop"
printf '%s\n' "The desktop entry uses an absolute Exec path; no PATH setup is required."
