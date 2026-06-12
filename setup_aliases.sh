#!/bin/bash

echo "🚀 Setup Harmony CLI Aliases"
echo "============================"

HARMONY_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/harmony.py"

# Crea alias nel .zshrc
echo ""
echo "# 🎮 Harmony Hub Fast Aliases" >> ~/.zshrc
echo "alias h='$HARMONY_PATH'"           >> ~/.zshrc
echo "alias htv='$HARMONY_PATH tv'"      >> ~/.zshrc
echo "alias hmusic='$HARMONY_PATH music'" >> ~/.zshrc
echo "alias hshield='$HARMONY_PATH shield'" >> ~/.zshrc
echo "alias hoff='$HARMONY_PATH off'"     >> ~/.zshrc
echo "alias hstatus='$HARMONY_PATH status'" >> ~/.zshrc
echo "alias hvol+='$HARMONY_PATH vol+'"   >> ~/.zshrc
echo "alias hvol-='$HARMONY_PATH vol-'"   >> ~/.zshrc
echo "alias hmute='$HARMONY_PATH mute'"   >> ~/.zshrc

echo "✅ Alias aggiunti a ~/.zshrc"
echo ""
echo "🔄 Ricarica la shell con: source ~/.zshrc"
echo ""
echo "🎯 Comandi ultra-veloci disponibili:"
echo "  h status    # Stato"
echo "  htv         # Guarda TV"
echo "  hmusic      # Ascolta musica"
echo "  hshield     # Shield"
echo "  hoff        # Spegni"
echo "  hvol+       # Volume su"
echo "  hvol-       # Volume giù"
echo "  hmute       # Muto"
echo ""
echo "🎵 Esempi d'uso:"
echo "  h vol+ && h vol+    # Volume +2"
echo "  htv && sleep 5 && hvol+ # TV + volume"
echo "  h samsung PowerOff  # Solo TV off"
