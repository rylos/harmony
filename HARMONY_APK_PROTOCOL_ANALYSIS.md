# Analisi protocollo dall'app Android ufficiale (Harmony.apk)

Data: 2026-09-13
Fonte: `Harmony.apk` (app Logitech Harmony 5.x, package `com.logitech.harmonyhub`), decompilata con jadx 1.5.6.
Il DEX non è offuscato: le classi SDK sono leggibili (`com.logitech.harmonyhub.sdk.*`).

Classi chiave:
- `sdk/core/transport/WebSocketLocalTransport.java` → trasporto WS locale (porta 8088)
- `sdk/Request.java` → formato JSON delle richieste
- `sdk/core/hub/BaseHub.java` → tutti i comandi `cmd` e i loro parametri
- `sdk/imp/StateDigestProcessor.java` → parsing dello stato push
- `sdk/core/discovery/WiFiDiscovery.java` → discovery UDP
- `sdk/core/util/HarmonyWebServices.java` → ping/provision via HTTP POST

## 1. Trasporto WebSocket locale

| Parametro | Valore nell'app | Nostro `harmony.py` |
|---|---|---|
| URL | `ws://IP:8088?domain=svcs.myharmony.com&hubId=REMOTE_ID` | identico |
| Keepalive | frame WS **PING** ogni 45 s (`PING_INTERVAL`) | ping ogni 30 s (ok) |
| Socket timeout | 60 s (`SO_TIMEOUT`) | — |
| Connection timeout | 20 s, handshake 10 s | — |
| Request timeout default | **3 s** | 10 s |
| Timeout attività | 60 s | 30 s (campo `timeout`) |
| Header custom | nessuno | nessuno |

L'app locale **non** invia `hubId` nel JSON (lo mette solo con `connectionType == 201`, cioè cloud) e mette `timeout` a top-level solo se impostato esplicitamente. Il nostro `hubId` top-level è quindi superfluo ma innocuo.

### Formato richiesta (`Request.getJsonRequest`)

```json
{
  "timeout": 30,                 // opzionale, top-level
  "hbus": {
    "id": "<modello>-<rnd>-<contatore>",
    "cmd": "…",
    "token": "…",               // solo se presente authToken (hub FW ≥ 4 con OOH)
    "params": { … }             // oppure il JSON completo al posto di params
  }
}
```

Nota: se il comando usa `setFullJSONData`, il JSON viene messo **direttamente come `hbus`** (senza chiave `params`). Vale per `runactivity`, `automation?setState`, `hid.report`.

### Formato risposta / evento (`HarmonyWebSocket.processMessage`)

- Se il messaggio **ha `id`** → è una risposta: `{id, code, msg, data}`. Se manca `code` si assume 200.
- Se il messaggio **non ha `id`** → è un **evento push**: `{type, data}` → dispatch su `type`.

Codici `code` gestiti dall'app:

| code | Significato |
|---|---|
| `200` | OK |
| `100` | Continue (progress, altre risposte seguiranno con lo stesso id) |
| `200.1` | Challenge OK (auth) |
| `200.2` | **Richiesta asincrona accettata** (attività): l'esito arriva poi come evento |
| `401` | Non autorizzato |
| `505` | Dispositivo BT non raggiungibile |
| `506` | (errore hub) |
| `510` | **Hub in inizializzazione** (riprovare) |
| `5504` | **Request timed out lato hub** |
| `1000` | Errore generico lato client |

I messaggi WS possono arrivare **frammentati**: l'app accumula i frammenti in un buffer e fa il parse solo sull'ultimo (`onFragment` con `fin`). aiohttp lo fa già in automatico.

## 2. Eventi push (il "vero" modo di ricevere lo stato)

Tipi evento (`BaseHub.EVENT_*`):

| `type` | Contenuto `data` |
|---|---|
| `connect.statedigest?notify` | vedi §3 |
| `harmony.engine?startActivityFinished` | `{activityId, …}` — `-1` = tutto spento |
| `automation.state?notify` | stato device home-automation |
| `harmonyengine.metadata?notify` | metadati (favoriti/canali) |

**L'app ufficiale non usa mai `getCurrentActivity`.** Lo stato iniziale lo ottiene con:

```json
{"hbus": {"id": "…", "cmd": "connect.statedigest?get", "params": {"format": "json"}}}
```

e poi vive solo di eventi `connect.statedigest?notify`.

## 3. State digest (campi letti da `StateDigestProcessor`)

| Campo | Tipo | Note |
|---|---|---|
| `activityId` | str | `-1` = nessuna |
| `activityStatus` | int | **0** = idle/off, **1** = starting, **2** = started, **3** = stopping |
| `runningActivityList` | str | id separati da virgola (FW recenti); multi-attività |
| `runningZoneList` | str/json | zone Sonos |
| `syncStatus` | int | 0 ok, 1 sync in corso, 2/3 errore, 4 in corso |
| `stateVersion` | int | cambia a ogni variazione di stato |
| `hubConfigVersion` / `configVersion` | int | se cambia → riscaricare `?config` |
| `contentVersion` | int | |
| `sleepTimerId` | int | -1 = nessuno |
| `hubSwVersion` | str | firmware |
| `activitySetupState` | bool | |
| `IRIPTimer` | str | |

Regola pratica per la GUI: `activityStatus in (1,3)` → mostra "in transizione", `2` → attivo, `0` → spento; usa `runningActivityList` se presente, altrimenti `activityId`.

## 4. Comandi (`cmd`) e parametri esatti

### Comando dispositivo — `vnd.logitech.harmony/vnd.logitech.harmony.engine?holdAction`

```json
"params": {"action": "{\"command\":\"VolumeUp\",\"type\":\"IRCommand\",\"deviceId\":\"123\"}",
           "status": "press", "timestamp": "<ms dalla connessione>"}
```

Stati: `press`, `hold`, `release`, `pressrelease`. Dettagli importanti:
- Il **`timestamp`** è `System.currentTimeMillis() - connectionTimestamp` (ms trascorsi dalla connessione), non 0. Serve all'hub per ordinare press/hold/release.
- **Release e hold riusano lo stesso `id` del press** (`chainRequest`): l'hub li lega alla stessa pressione.
- La richiesta è marcata `expectNoResult = true`: **l'app non aspetta risposta né al press né al release** (fire-and-forget entrambi). Il timeout di 3 s non genera errore.
- Sequenze: `"action": "{\"sequenceId\": N}"` con `status: press`.
- L'app non manda `verb: render` (il nostro lo manda, innocuo).

### Avvio attività — due API

Legacy (la nostra): `vnd.logitech.harmony/vnd.logitech.harmony.engine?startactivity` con `params: {activityId}`.

Nuova (`REQUEST_START_ACTIVITY`) — JSON diretto in `hbus`, timeout 60 s:

```json
{"hbus": {"id": "…", "cmd": "harmony.activityengine?runactivity",
          "activityId": "123", "timestamp": "<ms>", "async": true,
          "args": {"rule": "start"}}}
```

`rule` = `start` oppure `end`. Con `async: true` la risposta è `code: 200.2` e la conclusione arriva come evento `startActivityFinished` + `statedigest?notify`.

### Altri comandi utili scoperti

| `cmd` | Parametri | Uso |
|---|---|---|
| `connect.statedigest?get` | `{format: "json"}` | stato completo |
| `connect.statedigest?update` | — | forza refresh |
| `connect.ping` | — | ping (anche via HTTP POST, vedi §6) |
| `connect.discoveryinfo?get` | — | `accountId, email, hubId, remoteId, isSetupComplete` |
| `vnd.logitech.harmony/vnd.logitech.harmony.system?systeminfo` | — | info sistema (`unit_id`, fw…) |
| `vnd.logitech.connect/vnd.logitech.deviceinfo?get` | — | info hub |
| `harmony.engine?changeChannel` | `{channel: "…"}` | cambio canale/favorito nell'attività corrente |
| `harmony.engine?setsleeptimer` | `{interval: <secondi>}` (-1 annulla, **0 spegne subito**) → risposta `{timerId}` | sleep timer |
| `harmony.engine?gettimerinterval` | — | legge sleep timer |
| `harmony.automation?getState` | `{deviceIds: [...], forceUpdate: true}` (JSON diretto) | stato device HA |
| `harmony.automation?setState` | `{state: {...}}` (JSON diretto) | comanda device HA |
| `vnd.logitech.harmony/vnd.logitech.harmony.engine?helpSync` | `{value, smartInput…}` | "Help"/Fix-it |
| `hid.report` | `{code, value, relevent}` (JSON diretto) | tastiera/mouse BT |
| `proxy.resource?get` | `{uri, encode: true}` | risorse (icone favoriti) |
| `setup.content?syncChannels` | — | |
| `setup.sync` | — | sync con cloud (timeout 300 s) |
| `vnd.logtech.setup/vnd.logitech.firmware?check/status/update` | — | firmware |

## 5. Discovery UDP (senza conoscere l'IP)

1. Apri un TCP server su porta **5446**.
2. Invia in broadcast UDP alla porta **5224** il testo:
   ```
   _logitech-reverse-bonjour._tcp.local.\n5446
   ```
   (opzionale: `\n<IP client>\nstring`). Ripeti ogni 3 s.
3. L'hub si connette **lui** al tuo TCP 5446 e manda una stringa `chiave:valore;chiave:valore;…` (es. `ip`, `friendlyName`, `remoteId`, `hubId`, `uuid`, `current_fw_version`, `email`, `accountId`, `discoveryServerUri`, `port`, `productId`, `hubProfiles`, `protocolVersion`).

Utile per un comando `harmony.py find-hub` che generi `HUB_IP`/`REMOTE_ID` senza ricerca manuale.

## 6. HTTP POST su :8088 (alternativa senza WebSocket)

```
POST http://IP:8088/
Origin: http://localhost.nebula.myharmony.com
Referer: http://localhost.nebula.myharmony.com/mobile-fat.html
Accept: application/json
Content-Type: application/json

{"id": "124", "cmd": "connect.ping"}
{"id": "124", "cmd": "setup.account?getProvisionInfo"}
```

`connect.ping` con read-timeout 3 s è quello che l'app usa come "hub raggiungibile?".

## 7. Verifiche sull'Hub reale (firmware 4.15.600, hubId 106 "Pimento") — 2026-09-13

Tutto verificato con il codice attuale di `main` (merge del 2026-09-13):

- `connect.statedigest?get` con `{format: "json"}` risponde in ~40 ms con il digest completo.
- Gli eventi push arrivano con il tipo **`connect.stateDigest?notify`** (D maiuscola) e
  `harmony.engine?startActivityFinished`: confrontare sempre case-insensitive.
- Avvio attività: digest `activityStatus=1` subito, `activityStatus=2` + `startActivityFinished`
  dopo ~9 s (Shield). Il flusso `wait=True` funziona.
- `holdAction` press/release: per comandi validi l'Hub **non risponde** (né al press né al
  release). Per errori risponde in <75 ms: `565 Device not found`, `566 Command not found`.
- `setsleeptimer`: `interval` è in **secondi**, `-1` annulla, **`0` spegne tutto subito**
  (`activityId=-1`). `gettimerinterval` risponde `{interval:-1, error:{code:404}}` se non attivo.
  Ogni set/cancel genera un `stateDigest?notify` (cambia `sleepTimerId`).
- `connect.statedigest?update` senza argomenti → `504 Statedigest Update Insufficient Arguments`.
- HTTP POST su :8088: `setup.account?getProvisionInfo` funziona (con header `Origin`);
  `connect.ping` risponde `HTTP 417 {"code":"417"}` — usabile comunque come "Hub vivo".
  Senza `Origin` → `400.1`.
- Discovery UDP 5224 → TCP 5446: l'Hub risponde in <1 s con `friendlyName`, `ip`, `remoteId`,
  `hubId`, `uuid`, `current_fw_version`, `email`, `accountId`, `port=5222`, `protocolVersion`…
- `harmony.activityengine?runactivity` NON è stato testato (metodo `run_activity_rule` presente
  ma non usato di default).

## 8. Cosa migliorare in `harmony.py` / GUI (ordinato per impatto) — stato

Tutti i punti sotto sono implementati in `main` (merge del 2026-09-13), tranne dove indicato.

1. **Stato via eventi, non polling** — sostituire il timer da 10 s e `getCurrentActivity` con `connect.statedigest?get` all'avvio + ascolto di `connect.statedigest?notify` e `startActivityFinished`. Richiede un reader task unico che smisti risposte (con `id`) e eventi (senza `id`), invece del `async for` dentro `_send_ws_fast` che oggi scarta gli eventi.
2. **Press/release fire-and-forget entrambi** — l'app non aspetta il press. Oggi aspettiamo fino a 0.2 s: togliendolo un comando scende a ~1 ms di latenza percepita. Usare lo stesso `id` per press e release e un `timestamp` reale (ms dalla connessione).
3. **Stato `hold`** per volume/tasti tenuti premuti (già supportato dall'hub, con lo stesso `id` del press).
4. **`runactivity` con `async: true`** al posto di `startactivity`: si riceve `200.2` subito e l'evento di fine; niente più attesa cieca di 30 s.
5. **Gestire i codici `510` e `5504`** (hub in boot / timeout hub) con retry, e `200.2`/`100` come "in corso" e non come errore.
6. **Discovery automatica** (UDP 5224 / TCP 5446) per `discover`/`export-config` senza `HUB_IP` a mano.
7. **Timeout richieste a 3 s** come default (l'app), 60 s solo per attività.
8. **Nuove funzioni**: sleep timer, `changeChannel` per favoriti, `helpSync` (Fix-it), `systeminfo` nel `show-hub`.
9. Il `hubId` top-level e `verb: render` non servono sul trasporto locale (rimuovibili, ma innocui).
