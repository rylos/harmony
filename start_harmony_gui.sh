#!/bin/bash

echo "🌃 Harmony Hub GUI - Tokyo Night Edition"
echo "========================================"

# Controlla ambiente grafico
if [ -z "$DISPLAY" ]; then
  echo "❌ Ambiente grafico non disponibile"
  exit 1
fi

# Path dinamico
HARMONY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HARMONY_DIR"

# Verifica file
if [ ! -f "harmony.py" ] || [ ! -f "harmony_gui.py" ]; then
  echo "❌ File mancanti"
  exit 1
fi

echo "✅ Avvio GUI..."

# Attiva venv e avvia
source harmony_env/bin/activate
exec ./harmony_gui.py

