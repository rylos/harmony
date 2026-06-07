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
cp config.sample.py config.py   # poi modifica con i tuoi dati
# Oppure scopri automaticamente:
python harmony.py discover
python harmony.py export-config

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
config.py                   → Config utente (HUB_IP, REMOTE_ID, ACTIVITIES, DEVICES, AUDIO_COMMANDS).
config.sample.py            → Template di config.py.
```

**Flusso**: `harmony.py` fa da router CLI → istanzia `FastHarmonyHub` → WebSocket verso il Hub su porta 8088. La GUI usa `HarmonyWorker` (QThread) per delegare le chiamate al Hub senza bloccare l'interfaccia. `StateManager` coordina stato tra GUI e Worker tramite segnali Qt.

## Conventions

- **Lingua**: codice e commenti in italiano (messaggi utente, docstring interni). Nomi di classi/metodi in inglese (PascalCase classi, snake_case metodi).
- **Async**: tutta la comunicazione Hub via `asyncio` + `aiohttp`. Usa `async with FastHarmonyHub() as hub`.
- **Error handling**: decorator `@network_retry` su `connect()`; retry su ClientError/TimeoutError/ConnectionError. Fallback fire-and-forget su comandi che l'Hub ignora (release).
- **Config**: import diretta di `config.py` (non YAML/JSON). Se manca, exit con messaggio d'errore.
- **Press/Release**: simulazione pulsante reale — invia `press`, attesa 20ms, invia `release` (fire-and-forget). `--no-press-release` per modalità legacy.
- **UI**: tema Tokyo Night definito in `harmony_gui.py` come dict `C`: bg=`#1a1b26`, surface=`#24283b`, active=`#7aa2f7`, accent=`#bb9af7`, danger=`#f7768e`, text=`#c0caf5`, subtext=`#565f89`, border=`#414868`. Bottoni con `ModernBtn` (stile custom).
- **Naming device helpers**: funzioni `find_*_device(DEVICES)` restituiscono `(alias, device_dict)`, o `(None, None)` se non trovato.

## Notes

- **Nessun test** nel progetto (nessun `tests/`, `test_*.py`, pytest config).
- Nessun `pyproject.toml`/`setup.py` — dipendenze solo via `requirements.txt`.
