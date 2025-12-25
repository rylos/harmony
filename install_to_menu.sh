#!/bin/bash

echo "🚀 Installazione Harmony Hub Controller nel Menu KDE"
echo "===================================================="

DESKTOP_FILE="/home/marco/dev/harmony/harmony-hub-controller.desktop"
INSTALL_DIR="$HOME/.local/share/applications"

# Crea directory se non esiste
mkdir -p "$INSTALL_DIR"

# Copia file desktop
cp "$DESKTOP_FILE" "$INSTALL_DIR/"

# Rendi eseguibile
chmod +x "$INSTALL_DIR/harmony-hub-controller.desktop"

echo "✅ Applicazione installata nel menu!"
echo ""
echo "🎯 Puoi ora trovare 'Harmony Hub Controller' in:"
echo "   • Menu KDE → Multimedia"
echo "   • Krunner (Alt+Space): digita 'harmony'"
echo "   • Menu Applicazioni → AudioVideo"
echo ""
echo "🔄 Se non appare subito, riavvia KDE o esegui:"
echo "   kbuildsycoca6"
echo ""

# Aggiorna cache menu KDE
if command -v kbuildsycoca6 &> /dev/null; then
    echo "🔄 Aggiornamento cache menu KDE..."
    kbuildsycoca6
    echo "✅ Cache aggiornata!"
fi

echo ""
echo "🎮 Per avviare manualmente:"
echo "   ./start_harmony_gui.sh"
