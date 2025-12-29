# Project Structure

## Root Directory Layout
```
harmony/
├── harmony.py              # Core CLI backend (async WebSocket)
├── harmony_gui.py          # Qt6 GUI frontend
├── config.py              # User configuration (gitignored)
├── config.sample.py       # Configuration template
├── requirements.txt       # Python dependencies
├── DEVICE_COMMANDS.md     # Command reference documentation
├── README.md              # Project documentation
└── harmony_env/           # Python virtual environment
```

## Executable Scripts
```
├── start_harmony_gui.sh   # GUI launcher script
├── install_to_menu.sh     # KDE desktop integration
├── setup_aliases.sh       # CLI alias setup
└── harmony-hub-controller.desktop  # Desktop entry file
```

## Configuration Pattern
- **Template**: `config.sample.py` - Version controlled template
- **User Config**: `config.py` - User-specific, gitignored
- **Structure**: Python dictionaries for activities, devices, and commands

## Code Organization

### Backend (`harmony.py`)
- **Class**: `FastHarmonyHub` - Main WebSocket client
- **Functions**: Activity control, device commands, status checking
- **CLI Interface**: Argparse-based command routing
- **Smart Logic**: Context-aware command interpretation

### Frontend (`harmony_gui.py`)
- **Main Class**: Qt6 application with Tokyo Night theming
- **Layout**: Card-based UI with smart remote sections
- **Threading**: QThread for non-blocking CLI calls
- **Styling**: Centralized color palette in `C` dictionary

## File Naming Conventions
- **Executables**: `.py` files with shebang for direct execution
- **Scripts**: `.sh` files for shell operations
- **Config**: `.sample.py` suffix for templates
- **Documentation**: `.md` files for markdown documentation

## Import Structure
- **Direct imports**: GUI imports CLI module directly
- **Config imports**: Both modules import from `config.py`
- **Error handling**: Graceful fallback when config missing