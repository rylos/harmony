#!/bin/bash
# Avvia la GUI di Harmony Hub Controller usando il venv del progetto (se presente)

HARMONY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HARMONY_DIR" || exit 1

# Serve una sessione grafica (X11 o Wayland)
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
  echo "❌ No graphical session found (DISPLAY/WAYLAND_DISPLAY not set)"
  exit 1
fi

if [ ! -f "config.py" ]; then
  echo "❌ config.py not found. Create it first with: ./harmony.py export-config"
  exit 1
fi

# venv del progetto se esiste, altrimenti python3 di sistema
if [ -x "harmony_env/bin/python" ]; then
  exec harmony_env/bin/python harmony_gui.py "$@"
fi
exec python3 harmony_gui.py "$@"
