# Harmony Hub Controller

Controller CLI+GUI ibrido per Logitech Harmony Hub, con comunicazione WebSocket asincrona e interfaccia Qt6 (tema Tokyo Night).

## Project

- **Stack**: Python 3, PyQt6, aiohttp, asyncio
- **Entry point CLI**: `harmony.py`
- **Entry point GUI**: `harmony_gui.py`
- **Config utente**: `config.py` (generata via `discover` + `export-config`, gitignored)
- **Virtual env**: `harmony_env/` (gitignored)

## Commands

```bash
# Setup
python3 -m venv harmony_env
source harmony_env/bin/activate
pip install -r requirements.txt
./harmony.py export-config     # trova l'Hub sulla LAN e crea config.py (--ip se la discovery fallisce)

# CLI
source harmony_env/bin/activate
./harmony.py status              # Stato attività corrente
./harmony.py tv                  # Avvia attività "Guarda TV"
./harmony.py shield Home         # Comando dispositivo diretto
./harmony.py vol+                # Comando audio rapido
./harmony.py off                 # PowerOff globale
./harmony.py discover            # Scopri configurazione Hub
./harmony.py export-config       # Genera config.py
./harmony.py benchmark           # Benchmark performance
./harmony.py list                # Elenca tutti i comandi

# GUI
./start_harmony_gui.sh           # Launcher script (attiva venv + avvia)

# Desktop integration
./install_to_menu.sh             # Aggiunge a KDE menu
./setup_aliases.sh               # Crea alias CLI
```

## Architecture

```
harmony.py                  → CLI entrypoint. Class FastHarmonyHub (WebSocket).
harmony_gui.py              → GUI PyQt6. Class GUI, HarmonyWorker, ModernBtn.
state_manager.py            → Stato centralizzato. Class StateManager con Qt signals.
device_helpers.py           → Helper per trovare dispositivi per tipo (audio, TV, Shield, clima).
config_models.py            → Modelli dati: HubInfo, Command, Device, Activity, ConfigurationParser.
config_exporter.py          → Genera config.py dalla risposta Hub.
discovery_handlers.py       → Gestori comandi discovery: discover, show-activity, show-device, ecc.
display_formatter.py        → Formattazione output.
retry_utils.py              → Decoratore async_retry con backoff esponenziale.
hub_discovery.py            → Discovery LAN (UDP broadcast 5224, risposta TCP 5446). Non dipende da config.py.
HARMONY_APK_PROTOCOL_ANALYSIS.md → Protocollo ricavato dall'app Android ufficiale (riferimento per ogni modifica al trasporto).
config.py                   → Config utente (HUB_IP, REMOTE_ID, ACTIVITIES, DEVICES, AUDIO_COMMANDS).
config.sample.py            → Template di config.py.
```

**Flusso**: `harmony.py` fa da router CLI → istanzia `FastHarmonyHub` → WebSocket verso il Hub su porta 8088. La GUI usa `HarmonyWorker` (QThread) per delegare le chiamate al Hub senza bloccare l'interfaccia. `StateManager` coordina stato tra GUI e Worker tramite segnali Qt.

**Trasporto** (modellato sull'app ufficiale): `FastHarmonyHub` ha un unico reader task (`_reader_loop`): i messaggi con `id` risolvono la future in `_pending`, quelli senza `id` sono eventi push (`type`, `data`) → `event_callback` + `wait_for_event`. I tipi evento vanno confrontati in minuscolo (l'Hub manda `connect.stateDigest?notify`). Lo stato si legge con `get_state_digest()`/`get_status()` (campo `activityStatus`: 0 idle, 1 avvio, 2 attivo, 3 spegnimento), NON con `getCurrentActivity`. `_request()` gestisce i codici 510 (retry), 5504 (timeout), 100/200.2 (in corso) e solleva `HubError` per gli altri.

## Conventions

- **Lingua**: codice e commenti in italiano (messaggi utente, docstring interni). Nomi di classi/metodi in inglese (PascalCase classi, snake_case metodi).
- **Async**: tutta la comunicazione Hub via `asyncio` + `aiohttp`. Usa `async with FastHarmonyHub() as hub`.
- **Error handling**: decorator `@network_retry` su `connect()`; retry su ClientError/TimeoutError/ConnectionError. Il worker GUI non muore se il Hub è irraggiungibile: ritenta la connessione ogni 5s e si riconnette all'evento `client.disconnected`. Keepalive: heartbeat PING aiohttp ogni 45s (come l'app).
- **Stato GUI via eventi**: `HarmonyWorker._on_hub_event` riceve `connect.statedigest?notify` e aggiorna subito la label (anche "⏳ Avvio: …" per le transizioni, che `GUI.on_status` mostra senza toccare lo StateManager). Il QTimer da 60s è solo fallback.
- **Sleep timer**: `set_sleep_timer(secondi)`; -1 annulla. ATTENZIONE: interval 0 spegne tutto immediatamente (verificato sul firmware 4.15.600).
- **Config**: import diretta di `config.py` (non YAML/JSON). Se manca, i comandi in `NO_CONFIG_COMMANDS` (discover, export-config, show-*, status, digest, sysinfo, ping, events, find-hub) trovano l'Hub da soli (`resolve_hub`: discovery UDP, oppure `--ip` + remoteId via HTTP `getProvisionInfo`) e `export-config` crea `config.py` accanto a `harmony.py`; gli altri comandi escono con `CONFIG_MISSING_MSG`. I messaggi di questo percorso di primo avvio sono in inglese (utenti esterni, issue #1).
- **Press/Release**: come l'app — `press` e `release` entrambi fire-and-forget con lo STESSO id e `timestamp` = ms dalla connessione; attesa 20ms tra i due; poi al massimo 100ms (`ack_timeout`) per intercettare un errore dell'Hub (565 device/566 command not found). L'Hub non risponde ai comandi validi. `send_device_hold()` invia `hold` ripetuti (`--hold SEC`). `--no-press-release` invia `pressrelease`.
- **Attività**: `start_activity_fast(id, wait=True)` attende l'evento di fine (statedigest `activityStatus=2` o `startActivityFinished`), timeout 60s; `--no-wait` nella CLI.
- **Test sull'Hub reale**: comandi read-only sicuri: `status`, `digest`, `sysinfo`, `ping`, `events`, `find-hub`. Tutto il resto muove dispositivi veri: non lanciarlo senza motivo.
- **UI**: tema Tokyo Night definito in `harmony_gui.py` come dict `C`: bg=`#1a1b26`, surface=`#24283b`, active=`#7aa2f7`, accent=`#bb9af7`, danger=`#f7768e`, text=`#c0caf5`, subtext=`#565f89`, border=`#414868`. Bottoni con `ModernBtn` (stile custom).
- **Naming device helpers**: funzioni `find_*_device(DEVICES)` restituiscono `(alias, device_dict)`, o `(None, None)` se non trovato.

## Notes

- **Nessun test** nel progetto (nessun `tests/`, `test_*.py`, pytest config).
- Nessun `pyproject.toml`/`setup.py` — dipendenze solo via `requirements.txt`.
