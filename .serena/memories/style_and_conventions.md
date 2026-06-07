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
- Decorator pattern for retry logic: single shared `retry_utils.async_retry`; `network_retry` (harmony.py) and `discovery_retry` (discovery_handlers.py) are thin wrappers configuring it. Do NOT duplicate retry logic — extend `async_retry` instead.
- Private methods prefixed with `_` (e.g., `_send_ws_fast`, `_show_error`)
- Logger per module (`logger = logging.getLogger(...)`)
- Shared constants/helpers in `device_helpers.py` (no duplication across modules)
- Device finder functions take `DEVICES` dict as parameter (not global access)

## Known Tech Debt (intentionally not refactored)
- Command dispatch logic is duplicated between `harmony.py main()` and `harmony_gui.py HarmonyWorker._handle_command()`. Unifying it is risky without a test suite (controls real hardware), so it is left as-is and annotated in code comments.
- `harmony.py list`/`help` output is ~150 lines of hardcoded print statements (cosmetic).

## Error Handling
- Network retry with exponential backoff (shared `async_retry`); retries network errors only (by exception type in CLI, by message keywords in discovery), propagates non-network errors immediately.
- Device/IR commands are NOT wrapped in retry (avoid double-firing IR on real devices). Only `connect()` (CLI) and discovery operations retry.
- Graceful degradation for connection issues; dedicated handlers: `handle_network_error`, `handle_timeout_error`, `handle_command_error`

## GUI Patterns
- Qt signals for component communication
- Worker thread pattern (HarmonyWorker) for async operations
- Tokyo Night color theme via STYLESHEET constant
- Custom button class (ModernBtn) for consistent styling

## No Formal Linting/Formatting/Testing
- No configured linter, formatter, or test framework; no type-hint enforcement
- `ruff`/`pyflakes`/`pytest` are NOT installed in `harmony_env`
- Smoke-check changes with: `python3 -m py_compile *.py` and runtime imports via `harmony_env/bin/python`
