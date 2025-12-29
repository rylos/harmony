# Harmony Hub WebSocket Events - Analisi e Implementazione

## Data Analisi: 29 Dicembre 2024

### Domanda Originale
"Non esiste un modo per ricevere gli eventi dall'hub senza eseguire il polling?"

## Ricerca Online - Risultati

### Capacità WebSocket Event Listening
**✅ SÌ, è possibile ricevere eventi senza polling**

#### Fonti Confermate:
1. **JordanMartin/harmonyhub-api** (GitHub)
   - API WebSocket locale supporta comunicazione bidirezionale
   - Eventi disponibili: activity changes, device commands, status updates
   - Connessione persistente richiesta con keep-alive (ping ogni ~50s)

2. **NovaGL/diy-harmonyhub** (GitHub)
   - Documentazione WebSocket API completa
   - Eventi push automatici per cambi stato
   - Formato: `ws://HUB_IP:8088/?domain=svcs.myharmony.com&hubId=REMOTE_ID`

3. **OpenHAB Community**
   - Conferma: "The binding supports bi-directional communication with the hub"
   - Eventi ricevuti automaticamente da telecomando fisico

#### Limitazioni Identificate:
- Connessione si chiude dopo 60 secondi di inattività
- Richiede gestione reconnessione automatica
- HTTP POST API limitato (solo account info)
- Eventi disponibili solo via WebSocket

## Analisi Codice Attuale

### Architettura Corrente (harmony.py)

#### WebSocket Request/Response Pattern:
```python
async def _send_ws_fast(self, command: Dict, timeout: int = 10) -> Dict:
    # Invia comando
    await self._ws.send_str(json.dumps(command))
    
    # Aspetta SOLO risposta con ID specifico
    async for msg in self._ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            if str(data.get("id")) == str(msg_id):  # ← FILTRO SPECIFICO
                return data
            # Altri messaggi vengono IGNORATI
```

#### Status Updates via Polling:
```python
# GUI: harmony_gui.py linea ~1650
self.timer = QTimer()
self.timer.timeout.connect(self.update_status)
self.timer.start(10000)  # ← POLLING OGNI 10 SECONDI

def update_status(self):
    self.worker.queue_status()  # ← QUERY ATTIVA
```

#### Performance Attuale:
- Status check: 0.18s (18% più veloce del standard)
- Latenza rilevamento cambi: 0-10 secondi
- Traffico rete: Query periodiche ogni 10s

## Implementazione Event Listening - Piano Tecnico

### 1. Modifica WebSocket Handler

#### Problema Attuale:
```python
# harmony.py linea ~150
if str(data.get("id")) == str(msg_id):
    return data
# ← Eventi non richiesti vengono scartati
```

#### Soluzione Proposta:
```python
async def _send_ws_fast(self, command: Dict, timeout: int = 10) -> Dict:
    # ... invio comando ...
    
    async for msg in self._ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            
            # Risposta al comando specifico
            if str(data.get("id")) == str(msg_id):
                return data
            
            # Evento push non richiesto
            elif self._is_hub_event(data):
                await self._handle_hub_event(data)
                continue  # Continua ad aspettare risposta comando
```

### 2. Event Handler System

```python
async def _handle_hub_event(self, event_data):
    """Gestisce eventi push dall'Hub"""
    event_type = self._classify_event(event_data)
    
    if event_type == "activity_changed":
        activity_id = self._extract_activity_id(event_data)
        await self._notify_activity_change(activity_id)
        
    elif event_type == "device_state_changed":
        device_info = self._extract_device_state(event_data)
        await self._notify_device_change(device_info)

def _is_hub_event(self, data):
    """Identifica eventi push vs risposte comando"""
    # Eventi tipici: startActivityFinished, stateDigest, etc.
    event_indicators = [
        "startActivityFinished",
        "stateDigest", 
        "activityStatus",
        "deviceStatus"
    ]
    
    cmd = data.get("cmd", "")
    return any(indicator in cmd for indicator in event_indicators)
```

### 3. Integrazione StateManager

#### Modifica state_manager.py:
```python
class StateManager(QObject):
    # Nuovo segnale per eventi Hub
    hub_event_received = pyqtSignal(str, dict)  # (event_type, event_data)
    
    def handle_hub_event(self, event_type: str, event_data: dict):
        """Gestisce eventi real-time dall'Hub"""
        if event_type == "activity_changed":
            new_activity = event_data.get("activity_id", "unknown")
            self.update_current_activity(new_activity)
            
            # Aggiorna GUI immediatamente (no timer)
            self._emit_immediate_status_update()
            
        elif event_type == "device_state_changed":
            # Gestisci cambi stato dispositivi
            self._handle_device_state_event(event_data)
```

### 4. GUI Integration

#### Modifica harmony_gui.py:
```python
class HarmonyWorker(QThread):
    # Nuovo segnale per eventi Hub
    hub_event = pyqtSignal(str, dict)  # (event_type, event_data)
    
    def __init__(self, state_manager=None):
        super().__init__()
        self.hub = FastHarmonyHub(event_callback=self._on_hub_event)
    
    def _on_hub_event(self, event_type, event_data):
        """Callback per eventi Hub"""
        self.hub_event.emit(event_type, event_data)

class GUI(QMainWindow):
    def __init__(self):
        # ... setup esistente ...
        
        # Connetti eventi Hub
        self.worker.hub_event.connect(self.on_hub_event)
        
        # Timer ridotto o eliminato per status
        # self.timer.start(30000)  # ← Ridotto a backup ogni 30s
    
    def on_hub_event(self, event_type, event_data):
        """Gestisce eventi real-time dall'Hub"""
        if event_type == "activity_changed":
            # Aggiornamento immediato senza aspettare timer
            self.update_status_from_event(event_data)
```

## Benefici Implementazione

### Performance:
- **Latenza**: Da 0-10s a <1s per rilevamento cambi
- **Traffico Rete**: Riduzione ~90% (elimina polling periodico)
- **Reattività**: Feedback istantaneo da telecomando fisico

### User Experience:
- GUI sempre sincronizzata con stato reale
- Nessun "lag" tra azione fisica e display
- Feedback immediato per tutti i cambi stato

### Efficienza Sistema:
- Meno carico CPU (no timer frequenti)
- Meno carico rete (no query periodiche)
- Batteria migliore su dispositivi mobili

## Complessità Aggiuntiva

### 1. Gestione Concorrenza
```python
# Problema: Eventi durante esecuzione comandi
# Soluzione: Queue separate
self._event_queue = asyncio.Queue()
self._command_responses = {}  # ID -> Future
```

### 2. Parsing Eventi Harmony
```python
# Esempi formati eventi da decodificare:
# {"cmd": "harmony.engine?startActivityFinished", "data": {"activityId": "123"}}
# {"cmd": "vnd.logitech.harmony/vnd.logitech.harmony.engine?stateDigest", ...}
```

### 3. Robustezza Connessione
```python
# Fallback per eventi persi
if time.time() - self.last_event_timestamp > 30:
    await self._force_status_check()  # Backup polling

# Reconnessione automatica
if self._ws.closed:
    await self._reconnect_with_backoff()
```

### 4. Debugging Complessità
- Eventi asincroni più difficili da tracciare
- Race conditions possibili tra eventi e comandi
- Log più complessi per troubleshooting

## Raccomandazione Implementazione

### Approccio Graduale:

#### Fase 1: Event Listener Base
- Implementa `_handle_hub_event()` con logging
- Mantieni polling esistente come backup
- Testa identificazione eventi

#### Fase 2: StateManager Integration  
- Connetti eventi a StateManager
- Riduci frequenza timer (30s backup)
- Testa sincronizzazione GUI

#### Fase 3: Ottimizzazione
- Elimina polling per eventi supportati
- Implementa fallback intelligente
- Performance tuning

### Priorità Use Cases:

1. **Alta Priorità**: Sync con telecomando fisico Harmony
2. **Media Priorità**: Feedback istantaneo GUI
3. **Bassa Priorità**: Riduzione traffico rete

## Conclusioni

**Il sistema attuale funziona molto bene** (0.18s status, architettura solida).

**Event listening sarebbe utile se:**
- Usi frequentemente telecomando fisico Harmony
- Hai multiple applicazioni che controllano stesso Hub  
- Vuoi feedback sub-secondo per cambi stato
- Priorità su efficienza energetica/rete

**Mantieni approccio attuale se:**
- Sistema soddisfa requisiti performance
- Stabilità > reattività estrema
- Complessità aggiuntiva non giustificata

---

## Prossimi Passi Possibili

1. **Prototipo Event Listener** - Test base con logging eventi
2. **Benchmark Performance** - Confronto polling vs events  
3. **Implementazione Graduale** - Fase per fase con fallback
4. **Valutazione User Experience** - Test reattività vs stabilità

**Decisione**: Implementare o mantenere architettura attuale?