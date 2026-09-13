# Project Structure

```
harmony/
├── harmony.py                    # Core CLI backend (main entry point)
│   ├── FastHarmonyHub            # WebSocket client: reader task, events, statedigest, press/release (see mem:protocol_and_transport)
│   ├── HubError                  # Exception for hub codes != 200
│   ├── parse_digest / describe_status / describe_digest / activity_name  # status helpers shared with GUI
│   ├── network_retry             # Thin wrapper over retry_utils.async_retry (network exceptions)
│   ├── require_config            # exits with CONFIG_MISSING_MSG if config.py missing (config import is lazy)
│   ├── _run_activity             # CLI helper: start activity, wait for completion event
│   └── main()                    # CLI router (activities, devices, audio, status/digest/sysinfo/ping/events, find-hub, sleep, channel, discovery cmds, benchmark)
├── hub_discovery.py              # LAN discovery: UDP broadcast 5224 → hub connects back on TCP 5446. No config dependency.
├── retry_utils.py                # Shared async retry decorator
├── device_helpers.py             # Shared device detection and constants
├── harmony_gui.py                # Qt6 GUI frontend
│   ├── HarmonyWorker             # QThread + asyncio loop; hub events → status (no polling); signals result_ready, status_updated, hub_event, command_*
│   ├── ModernBtn, GUI, C, STYLESHEET, main()
├── state_manager.py              # Centralized state management (StateManager, CommandType/CommandState/UIState)
├── config_models.py              # HubInfo, Command, Device, Activity, ConfigurationParser
├── config_exporter.py            # ConfigExporter → config.py
├── discovery_handlers.py         # discover, show-activity, show-device, show-hub, export-config
├── display_formatter.py          # DisplayFormatter
├── config.py                     # Hub configuration (gitignored)
├── config.sample.py              # Configuration template
├── HARMONY_APK_PROTOCOL_ANALYSIS.md      # Protocol reference from official APK + real-hub verifications
├── HARMONY_WEBSOCKET_EVENTS_ANALYSIS.md  # Historical plan for events (now implemented)
├── DEVICE_COMMANDS.md
├── .mcp.json, AGENTS.md, start_harmony_gui.sh, install_to_menu.sh, setup_aliases.sh, *.desktop, harmony-icon.png, requirements.txt
└── harmony_env/                  # venv (gitignored)
```

## Import Dependencies
- `harmony_gui.py` imports from `harmony.py` (FastHarmonyHub, config dicts, describe_status, parse_digest, EVENT_* constants) and `device_helpers`/`state_manager`
- `harmony.py` and `discovery_handlers.py` import `async_retry` from `retry_utils`
- `hub_discovery.py` is standalone (stdlib only)
- `discovery_handlers.py` uses hub.get_config_fast / get_hub_info_fast / get_provision_info_fast / get_state_digest

## Branches
- `main`: version in daily use by the user.
- `feature/apk-protocol` (2026-09-13): protocol rewrite based on the official APK (events, statedigest, discovery, sleep/channel). Keep main untouched until the user validates.

## Notes
- No test files in the repo.
