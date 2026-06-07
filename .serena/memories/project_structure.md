# Project Structure

```
harmony/
├── harmony.py                    # Core CLI backend (main entry point)
│   ├── FastHarmonyHub            # WebSocket client class (connect, send commands, get status/config)
│   ├── network_retry             # Thin wrapper over retry_utils.async_retry (network exceptions)
│   ├── find_device_by_type/find_audio_device/find_tv_device/find_shield_device  # imported from device_helpers
│   └── main()                    # CLI entry point (includes benchmark command)
├── retry_utils.py                # Shared async retry decorator (NEW)
│   ├── async_retry               # Configurable exponential-backoff retry decorator
│   └── NETWORK_KEYWORDS          # Keywords to recognize retryable network errors
├── device_helpers.py             # Shared device detection and constants
│   ├── TV_ACTIONS, TV_KEYWORDS, AUDIO_KEYWORDS, etc.  # Shared constants
│   ├── find_device_by_type/find_audio_device/find_tv_device/find_shield_device
│   └── is_tv_device/is_tv_action/get_tv_success_message/get_tv_error_message
├── harmony_gui.py                # Qt6 GUI frontend
│   ├── HarmonyWorker             # Async worker thread (command/status handling)
│   ├── ModernBtn                 # Custom styled button
│   ├── GUI                       # Main window (buttons, status, events)
│   ├── C                         # Color constants
│   ├── STYLESHEET                # Tokyo Night theme CSS
│   └── main()                    # GUI entry point
├── state_manager.py              # Centralized state management
│   ├── CommandType / CommandState / UIState  # Enums + dataclasses
│   └── StateManager              # Queue, classify, process commands; error handling
├── config_models.py              # Configuration data models
│   ├── HubInfo, Command, Device, Activity  # Dataclasses with from_dict()
│   └── ConfigurationParser       # Parse hub config/info/provision responses
├── config_exporter.py            # Configuration export
│   └── ConfigExporter            # Generate config.py from discovered data
├── discovery_handlers.py         # Discovery command handlers
│   ├── discovery_retry           # Thin wrapper over retry_utils.async_retry (message-based)
│   ├── PerformanceMonitor        # Measure operation timing
│   └── DiscoveryHandlers         # discover, show-activity, show-device, show-hub, export-config
├── display_formatter.py          # Output formatting (DisplayFormatter)
├── config.py                     # Hub configuration (auto-generated, NOT in git / gitignored)
├── config.sample.py              # Configuration template
├── .mcp.json                     # Serena MCP server config (committed)
├── start_harmony_gui.sh          # GUI launcher script
├── install_to_menu.sh            # KDE desktop integration
├── setup_aliases.sh              # CLI aliases setup
├── harmony-hub-controller.desktop # Desktop entry file
├── harmony-icon.png              # Application icon
├── requirements.txt              # Python dependencies
└── harmony_env/                  # Python virtual environment
```

## Import Dependencies
- GUI (`harmony_gui.py`) imports from core CLI (`harmony.py`) and `device_helpers`/`state_manager`
- `harmony.py` and `discovery_handlers.py` both import `async_retry` from `retry_utils` (no duplicated retry code)
- Discovery system + config exporter import from `config_models`
- State manager is standalone (used by GUI)
- Circular imports avoided through careful dependency management

## Notes
- No test files in the repo. A prior test suite (test_tv_*.py, test_gui_tv_controls.py, etc.) was removed; leftover `.pytest_cache/`/`.hypothesis/` dirs were deleted (both are gitignored).
