# Technology Stack & Build System

## Core Technologies
- **Python 3**: Main programming language
- **PyQt6**: GUI framework with modern Qt6 interface
- **aiohttp**: Async HTTP client for WebSocket communication
- **asyncio**: Asynchronous programming support

## Dependencies
See `requirements.txt` for exact versions:
- PyQt6 (6.10.1) - GUI framework
- aiohttp (3.13.2) - WebSocket client
- asyncio - Built-in async support
- Additional support libraries (aiohappyeyeballs, aiosignal, etc.)

## Build System
This is a Python application with no traditional build process. Setup involves:

### Environment Setup
```bash
# Create virtual environment
python3 -m venv harmony_env
source harmony_env/bin/activate
pip install -r requirements.txt
```

### Configuration
```bash
# Auto-discover and configure hub
python harmony.py discover
python harmony.py export-config
```

### Common Commands

#### Development & Testing
```bash
# CLI testing
./harmony.py status
./harmony.py tv
./harmony.py vol+

# GUI testing
./start_harmony_gui.sh

# Discovery and configuration
python harmony.py discover
python harmony.py show-activity <id>
python harmony.py show-device <id>
python harmony.py export-config
```

#### Installation & Deployment
```bash
# Desktop integration
./install_to_menu.sh

# CLI aliases setup
./setup_aliases.sh

# Manual GUI launch
./start_harmony_gui.sh
```

## Performance Optimization
- **WebSocket Connection Reuse**: Persistent connections for speed
- **Press/Release Simulation**: 0.05s delay for IR command precision
- **Fire-and-forget**: Optimized for speed over reliability
- **Command Queueing**: Sequential processing with visual feedback
- **Network Retry**: Exponential backoff for reliability

## Configuration Files
- `config.py`: Main configuration (auto-generated from discovery)
- `config.sample.py`: Template for manual configuration
- `harmony-hub-controller.desktop`: Desktop integration file

## Architecture Patterns
- **Async/Await**: All network operations are asynchronous
- **State Management**: Centralized state coordination via StateManager
- **Command Pattern**: Commands are queued and processed sequentially
- **Observer Pattern**: Qt signals for UI updates
- **Retry Pattern**: Network operations with exponential backoff