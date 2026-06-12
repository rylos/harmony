# Tech Stack & Dependencies

## Core Technologies
- **Python 3**: Main programming language
- **PyQt6 6.10.1**: GUI framework with modern Qt6 interface
- **aiohttp 3.13.2**: Async HTTP client for WebSocket communication
- **asyncio**: Asynchronous programming support (built-in)

## Full Dependencies (requirements.txt)
- aiohappyeyeballs==2.6.1
- aiohttp==3.13.2
- aiosignal==1.4.0
- attrs==25.4.0
- frozenlist==1.8.0
- idna==3.11
- multidict==6.7.0
- propcache==0.4.1
- PyQt6==6.10.1
- PyQt6-Qt6==6.10.1
- PyQt6_sip==13.10.3
- yarl==1.22.0

## Build System
No traditional build process. Python application with venv:
```bash
python3 -m venv harmony_env
source harmony_env/bin/activate
pip install -r requirements.txt
```

## Architecture Patterns
- **Async/Await**: All network operations are asynchronous
- **State Management**: Centralized state coordination via StateManager with Qt signals
- **Command Pattern**: Commands queued and processed sequentially (CommandType enum: ACTIVITY, DEVICE, AUDIO)
- **Observer Pattern**: Qt signals for UI updates
- **Retry Pattern**: Shared `retry_utils.async_retry` (exponential backoff). `network_retry` (harmony) and `discovery_retry` (discovery_handlers) are thin wrappers. Retries network errors only; device/IR commands are NOT retried (avoid double-firing IR).
- **Context Manager**: `FastHarmonyHub` supports async context manager (`__aenter__`/`__aexit__`)
- **Persistent Connections**: WebSocket connection reuse with keepalive ping (30s). GUI worker auto-reconnects: retries connect() every 5s if Hub unreachable (emits "❌ Hub non raggiungibile"), reconnects after failed keepalive ping. `FastHarmonyHub.close()` resets session/_ws so reconnection works.
- **Fire-and-forget Release**: IR release commands sent without awaiting response
- **Integer Message IDs**: Counter-based IDs instead of UUID for speed
- **Shared Helpers**: `device_helpers.py` (device detection/TV constants), `retry_utils.py` (retry decorator)

## No Build/Test/Lint Tools Configured
- No pyproject.toml, setup.py, or setup.cfg
- No test files present (a prior test suite was removed)
- No linting or formatting configuration; `ruff`/`pyflakes`/`pytest` not installed in `harmony_env`
