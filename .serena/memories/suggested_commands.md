# Suggested Commands

## Environment Setup
```bash
cd /home/marco/dev/harmony
source harmony_env/bin/activate
pip install -r requirements.txt
```

## Running the Application
```bash
# CLI - main entry point
./harmony.py status                  # Check current hub status
./harmony.py <activity_name>         # Start an activity (e.g., guarda_tv, shield, off)
./harmony.py <device> <command>      # Send device command (e.g., tv_samsung PowerOn)
./harmony.py vol+                    # Volume up
./harmony.py vol-                    # Volume down
./harmony.py mute                    # Mute/unmute

# GUI
./start_harmony_gui.sh               # Launch GUI via script
python harmony_gui.py                # Launch GUI directly
```

## Discovery & Configuration
```bash
python harmony.py discover           # Show complete hub overview
python harmony.py show-activity <name>  # Show activity details
python harmony.py show-device <name>    # Show device details
python harmony.py show-hub           # Show hub information
python harmony.py export-config      # Generate config.py file
python harmony.py benchmark          # Run WebSocket performance benchmark
```

## Desktop Integration
```bash
./install_to_menu.sh                 # Add to KDE menu
./setup_aliases.sh                   # Setup CLI aliases
```

## System Utilities (Linux)
```bash
git status / git log / git diff      # Version control
ls -la                               # List files
grep -r "pattern" .                  # Search in files
find . -name "*.py"                  # Find files
```

## No Test/Lint/Format Commands
This project has no configured test suite, linter, or formatter.
