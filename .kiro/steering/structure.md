# Project Structure & Organization

## Root Directory Layout
```
harmony/
├── harmony.py                    # Core CLI backend (main entry point)
├── harmony_gui.py                # Qt6 GUI frontend
├── state_manager.py              # Centralized state management
├── config_models.py              # Configuration data models
├── config_exporter.py            # Configuration export functionality
├── discovery_handlers.py         # Discovery command handlers
├── display_formatter.py          # Output formatting utilities
├── config.py                     # Hub configuration (auto-generated)
├── config.sample.py              # Configuration template
├── requirements.txt              # Python dependencies
├── README.md                     # Project documentation
├── LICENSE                       # License file
├── DEVICE_COMMANDS.md            # Device command reference
├── start_harmony_gui.sh          # GUI launcher script
├── install_to_menu.sh            # Desktop integration script
├── setup_aliases.sh              # CLI aliases setup script
├── harmony-hub-controller.desktop # Desktop entry file
├── harmony-icon.png              # Application icon
├── screenshot.png                # GUI screenshot
├── harmony_env/                  # Python virtual environment
└── __pycache__/                  # Python bytecode cache
```

## Core Architecture Components

### Main Entry Points
- **`harmony.py`**: CLI interface and core WebSocket communication
- **`harmony_gui.py`**: Qt6 GUI application with Tokyo Night theme

### State & Configuration Management
- **`state_manager.py`**: Centralized state coordination between GUI and CLI
- **`config_models.py`**: Data models for hub configuration parsing
- **`config.py`**: Runtime configuration (auto-generated from discovery)
- **`config_exporter.py`**: Exports discovered configuration to Python files

### Discovery & Display System
- **`discovery_handlers.py`**: Handles hub discovery and configuration commands
- **`display_formatter.py`**: Consistent formatting for CLI output

### Installation & Integration
- **Shell Scripts**: Setup and integration utilities
- **Desktop Files**: Linux desktop environment integration

## Code Organization Patterns

### Async Architecture
- All network operations use `async/await`
- WebSocket connections are persistent and reused
- Commands are queued and processed sequentially

### State Management
- `StateManager` coordinates between GUI and CLI components
- Qt signals used for component communication
- Command classification (ACTIVITY, DEVICE, AUDIO) for different handling

### Configuration System
- Hub discovery auto-generates `config.py`
- Template-based configuration with `config.sample.py`
- Data models provide structured parsing of hub responses

### Error Handling
- Network retry with exponential backoff
- Graceful degradation for connection issues
- User-friendly error messages with recovery options

## File Naming Conventions
- **Snake_case**: Python modules and functions
- **PascalCase**: Classes and Qt components
- **kebab-case**: Shell scripts and desktop files
- **UPPERCASE**: Constants and configuration keys

## Import Structure
- Core modules import from standard library and dependencies
- GUI components import from core CLI modules
- Discovery system imports from config models
- Circular imports avoided through careful dependency management

## Development Workflow
1. **Configuration**: Use discovery system to auto-configure
2. **CLI Testing**: Test commands via `harmony.py`
3. **GUI Testing**: Launch via `start_harmony_gui.sh`
4. **Integration**: Install desktop integration via scripts
5. **Deployment**: Virtual environment with requirements.txt