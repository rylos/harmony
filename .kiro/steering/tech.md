# Technology Stack

## Core Technologies
- **Python 3**: Main programming language
- **PyQt6**: GUI framework with modern Qt6 interface
- **aiohttp**: Async HTTP client for WebSocket communication
- **asyncio**: Asynchronous programming support

## Key Dependencies
```
aiohttp==3.13.2     # WebSocket communication
PyQt6==6.10.1       # GUI framework
asyncio             # Async operations (built-in)
```

## Development Environment
- **Virtual Environment**: `harmony_env/` (Python venv)
- **Configuration**: Python-based config system (`config.py`)
- **Shell**: Bash scripts for setup and execution

## Common Commands

### Setup
```bash
# Initial setup
python3 -m venv harmony_env
source harmony_env/bin/activate
pip install -r requirements.txt

# Configuration
cp config.sample.py config.py
# Edit config.py with your Hub IP and device IDs
```

### Running
```bash
# GUI Application
./start_harmony_gui.sh

# CLI Usage
./harmony.py <activity>              # Start activity
./harmony.py <device> <command>      # Send device command
./harmony.py status                  # Check status
./harmony.py list                    # List available commands
```

### Installation
```bash
# Desktop integration
./install_to_menu.sh                 # Add to KDE menu

# CLI aliases
./setup_aliases.sh                   # Add shell aliases
```

## Performance Optimizations
- **Timeouts**: Activity (3.0s), Status (2.0s), IR commands (0.2s)
- **Press/Release Simulation**: 0.05s delay between press/release
- **Fire-and-forget**: Optimized for speed over reliability
- **Persistent Connections**: WebSocket connection reuse