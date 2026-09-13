# Harmony Hub protocol & transport (from official Android APK reverse-engineering)

Reference doc: `HARMONY_APK_PROTOCOL_ANALYSIS.md` (repo). Read it before touching `FastHarmonyHub`.

## FastHarmonyHub (harmony.py) design
- Single reader task `_reader_loop`: messages WITH `id` → resolve future in `_pending`; WITHOUT `id` → push event `{type, data}` → `_dispatch_event` (lowercases type) → `event_callback(type, data)` + `wait_for_event(predicate, timeout)`.
- Request format = app's `Request.getJsonRequest`: `{"hbus": {"id", "cmd", "params": {...}}}` (or full JSON merged into hbus via `full=`), optional top-level `timeout`. No `hubId` needed locally.
- `_request()` handles codes: 200/200.1/200.2 ok, 100 = continue (keep waiting), 510 = hub booting (retry once), 5504 = hub-side timeout, others → `HubError(code, msg)`.
- Status: `get_state_digest()` (`connect.statedigest?get`, `{format:"json"}`) → `parse_digest()` → `{activity_id, status, running, transitioning,...}`; `describe_status()` gives the UI text ("⚫ OFF", "🟢 name", "⏳ Avvio: name"). `activityStatus`: 0 idle, 1 starting, 2 started, 3 stopping. The official app never uses `getCurrentActivity` (kept only for compatibility/benchmark).
- Events: `connect.stateDigest?notify` (mixed case! constants are lowercase), `harmony.engine?startActivityFinished`, plus synthetic `client.connected` / `client.disconnected` (not emitted on intentional close).
- Device commands: press + release fire-and-forget, SAME id, `timestamp` = ms since connect. Hub does NOT reply to valid commands; replies to errors within ~75ms (565 device not found, 566 command not found). `ack_timeout` (default 0.1s) waits only for such errors. `send_device_hold()` = press, repeated `hold`, release. `pressrelease` used with `--no-press-release`.
- Activities: `start_activity_fast(id, wait=True, timeout=60, progress=cb)` sends `…engine?startactivity` then awaits statedigest status==2 (or -1 idle) / startActivityFinished. `run_activity_rule()` (`harmony.activityengine?runactivity`) exists but is UNTESTED.
- Keepalive: aiohttp `heartbeat=45` (app pings every 45s). Socket timeout on hub side 60s.
- Sleep timer: `set_sleep_timer(seconds)`, -1 cancels; **0 powers everything off immediately** (verified, caused an accidental shutdown once). CLI: `sleep <min>` / `sleep off`.
- `ping_http()`: HTTP POST `:8088` with `Origin: http://localhost.nebula.myharmony.com`; fw 4.15 answers 417 to `connect.ping` but that still means reachable.
- Discovery: `hub_discovery.discover_hubs()` — TCP server on 5446, UDP broadcast `_logitech-reverse-bonjour._tcp.local.\n5446` to port 5224, hub connects back with `k:v;k:v` string. CLI `find-hub` works without config.py (config import is lazy; `require_config()` guards other commands).

## GUI (harmony_gui.py)
- `HarmonyWorker` creates `FastHarmonyHub(event_callback=self._on_hub_event)`; statedigest events → `_publish_status()` → `status_updated` signal; `startActivityFinished`/connected → queue "status"; disconnected → queue "reconnect". `hub_event` signal also exposed.
- `GUI.on_status` shows "⏳ …" transitional text directly (accent color) without touching StateManager. QTimer 60s is fallback only.

## Safe testing on the real hub
Read-only: `status`, `digest`, `sysinfo`, `ping`, `events`, `find-hub`, `benchmark` step 1-2. Everything else moves real devices (the user's system is in daily use).
