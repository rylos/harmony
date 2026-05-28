# Project Structure

```
harmony/
├── harmony.py                    # Core CLI backend (main entry point)
│   ├── FastHarmonyHub            # WebSocket client class (connect, send commands, get status/config)
│   ├── network_retry             # Retry decorator with exponential backoff
│   ├── find_device_by_type/find_audio_device/find_tv_device/find_shield_device  # Device finders
│   └── main()                    # CLI entry point (includes benchmark command)
├── device_helpers.py              # Shared device detection and constants
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
│   ├── CommandType               # Enum: ACTIVITY, DEVICE, AUDIO
│   ├── CommandState              # Enum for command lifecycle
│   ├── UIState                   # Enum for UI states
│   └── StateManager              # Queue, classify, process commands; error handling
├── config_models.py              # Configuration data models
│   ├── HubInfo, Command, Device, Activity  # Dataclasses with from_dict()
│   └── ConfigurationParser       # Parse hub config/info/provision responses
├── config_exporter.py            # Configuration export
│   └── ConfigExporter            # Generate config.py from discovered data
├── discovery_handlers.py         # Discovery command handlers
│   ├── PerformanceMonitor        # Measure operation timing
│   └── DiscoveryHandlers         # discover, show-activity, show-device, show-hub, export-config
├── device_helpers.py              # Shared device detection helpers and constants
├── display_formatter.py          # Output formatting
│   └── DisplayFormatter          # Format hub info, discovery summary, activity/device details
├── config.py                     # Hub configuration (auto-generated, not in git)
├── config.sample.py              # Configuration template
├── start_harmony_gui.sh          # GUI launcher script
├── install_to_menu.sh            # KDE desktop integration
├── setup_aliases.sh              # CLI aliases setup
├── harmony-hub-controller.desktop # Desktop entry file
├── harmony-icon.png              # Application icon
├── requirements.txt              # Python dependencies
└── harmony_env/                  # Python virtual environment
```

## Import Dependencies
- GUI (`harmony_gui.py`) imports from core CLI (`harmony.py`)
- Discovery system imports from config models
- Config exporter imports from config models
- State manager is standalone (used by GUI)
- Circular imports avoided through careful dependency management
