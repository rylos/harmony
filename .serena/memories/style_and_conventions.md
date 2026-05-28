# Code Style & Conventions

## Naming Conventions
- **snake_case**: Python modules, functions, variables (e.g., `state_manager.py`, `find_device_by_type`)
- **PascalCase**: Classes and Qt components (e.g., `FastHarmonyHub`, `StateManager`, `GUI`, `ModernBtn`)
- **kebab-case**: Shell scripts and desktop files (e.g., `start_harmony_gui.sh`, `harmony-hub-controller.desktop`)
- **UPPERCASE**: Constants and configuration keys (e.g., `HUB_IP`, `REMOTE_ID`, `ACTIVITIES`, `DEVICES`, `AUDIO_COMMANDS`)

## Code Patterns
- Dataclasses with `from_dict()` class methods for parsing (HubInfo, Command, Device, Activity)
- Enums for state management (CommandType, CommandState, UIState)
- Async context managers for hub connections
- Decorator pattern for retry logic (`network_retry`, `discovery_retry`)
- Private methods prefixed with `_` (e.g., `_send_ws_fast`, `_show_error`)
- Logger per module (`logger = logging.getLogger(...)`)
- Shared constants/helpers in `device_helpers.py` (no duplication across modules)
- Device finder functions take `DEVICES` dict as parameter (not global access)

## Error Handling
- Network retry with exponential backoff
- Graceful degradation for connection issues
- User-friendly error messages with recovery options
- Dedicated error handlers: `handle_network_error`, `handle_timeout_error`, `handle_command_error`

## GUI Patterns
- Qt signals for component communication
- Worker thread pattern (HarmonyWorker) for async operations
- Tokyo Night color theme via STYLESHEET constant
- Custom button class (ModernBtn) for consistent styling

## No Formal Linting/Formatting/Testing
- No configured linter, formatter, or test framework
- No type hints enforcement
- No docstring standard enforced
