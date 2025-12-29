# Design Document

## Overview

Il design migliora la gestione dello stato nell'interfaccia GUI del Harmony Hub Controller introducendo un sistema centralizzato di state management che risolve i problemi di race conditions e inconsistenze quando si premono rapidamente i tasti del telecomando.

## Architecture

### Current Architecture Issues
- Stati gestiti in modo distribuito tra GUI e Worker
- Timer sovrapposti che causano aggiornamenti inconsistenti
- Mancanza di debouncing per comandi rapidi
- Feedback visivo inadeguato per operazioni in corso

### New Architecture
```
GUI Components
    ↓
StateManager (Centralized)
    ↓
HarmonyWorker (Enhanced)
    ↓
FastHarmonyHub (Unchanged)
```

Il nuovo `StateManager` centralizza tutta la logica di stato e coordina le interazioni tra GUI e Worker.

## Components and Interfaces

### StateManager Class
```python
class StateManager(QObject):
    # Signals
    status_changed = pyqtSignal(str, str)  # (status_text, color)
    buttons_state_changed = pyqtSignal(bool)  # enabled/disabled
    queue_size_changed = pyqtSignal(int)  # number of pending commands
    
    # State tracking
    current_activity: str
    pending_commands: int
    is_activity_changing: bool
    is_processing: bool
    activity_start_time: float  # for blocking logic
```

### Enhanced HarmonyWorker
- Mantiene la stessa interfaccia pubblica
- Aggiunge notifiche di progresso per comandi lunghi
- Implementa throttling interno per comandi di dispositivo

### GUI Integration
- Tutti i componenti GUI si collegano al StateManager
- Rimozione della logica di stato distribuita
- Feedback visivo unificato

## Data Models

### Command State
```python
@dataclass
class CommandState:
    command: str
    action: Optional[str]
    timestamp: float
    command_type: CommandType  # ACTIVITY, DEVICE, AUDIO
    estimated_duration: float
```

### UI State
```python
@dataclass
class UIState:
    current_status: str
    status_color: str
    buttons_enabled: bool
    pending_count: int
    last_update: float
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

<function_calls>
<invoke name="prework">
<parameter name="featureName">harmony-state-management

### Property Reflection

Dopo aver analizzato tutti i criteri di accettazione, ho identificato alcune proprietà che possono essere consolidate:
- Le proprietà 1.2 e 4.1 sono ridondanti (entrambe testano che l'interfaccia mostri immediatamente lo stato di elaborazione)
- Le proprietà 2.3 e 4.3 sono correlate (bloccare attività e disabilitare bottoni)
- Le proprietà 1.3 e 4.2 testano lo stesso comportamento (mostrare il numero di comandi in coda)

### Correctness Properties

**Property 1: Sequential Command Processing**
*For any* sequence of rapid button presses, the system should process all commands in the correct order without overlapping state updates
**Validates: Requirements 1.1**

**Property 2: Immediate Visual Feedback**
*For any* command sent to the system, the status display should immediately show "🚀 Elaborazione..." before any processing begins
**Validates: Requirements 1.2, 4.1**

**Property 3: Queue Size Display**
*For any* number N of commands in the queue, the status display should show "🚀 Elaborazione... (+N)" where N accurately reflects the pending commands
**Validates: Requirements 1.3, 4.2**

**Property 4: Rapid Command Acceptance**
*For any* sequence of volume or device commands pressed rapidly, all commands should be accepted and processed without artificial delays
**Validates: Requirements 2.2**

**Property 5: Activity Command Blocking**
*For any* activity command in progress, all new activity commands should be blocked until the current activity command completes
**Validates: Requirements 2.1, 4.3**

**Property 6: Device Command Throttling**
*For any* sequence of device commands, the system should apply minimal throttling to prevent Hub overload while accepting all commands
**Validates: Requirements 2.3**

**Property 7: State Consistency**
*For any* state change in the StateManager, the current activity, queue size, and processing status should remain internally consistent
**Validates: Requirements 3.1**

**Property 8: Component Notification**
*For any* state change, all registered GUI components should receive the appropriate notification signals
**Validates: Requirements 3.2**

**Property 9: Timer Coordination**
*For any* timer expiration, the system should check for ongoing operations before updating the display state
**Validates: Requirements 3.3**

**Property 10: Command Type Classification**
*For any* command sent to the system, it should be correctly classified as either ACTIVITY (slow) or DEVICE (fast) type
**Validates: Requirements 3.4**

## Error Handling

### Command Failures
- Errori di rete: Retry automatico con backoff esponenziale
- Timeout: Fallback a stato precedente dopo timeout configurabile
- Errori di validazione: Immediate feedback senza retry

### State Inconsistencies
- Periodic state reconciliation ogni 30 secondi
- Fallback a query diretta dell'Hub in caso di inconsistenze
- Logging dettagliato per debugging

### UI Responsiveness
- Timeout massimo di 5 secondi per feedback visivo
- Fallback a stato "sconosciuto" se lo stato non può essere determinato
- Graceful degradation se il Worker non risponde

## Testing Strategy

### Dual Testing Approach
Il sistema sarà testato con una combinazione di:
- **Unit tests**: Per verificare esempi specifici, edge cases e condizioni di errore
- **Property tests**: Per verificare le proprietà universali su tutti gli input possibili

### Property-Based Testing Configuration
- Framework: `pytest` con `hypothesis` per Python
- Minimum 100 iterations per property test
- Ogni test di proprietà deve essere taggato con: **Feature: harmony-state-management, Property N: [property_text]**

### Unit Testing Focus
- Timing specifici (3 secondi per errori, 1 secondo per feedback completamento)
- Integrazione tra componenti GUI e StateManager
- Condizioni di errore e recovery
- Activity blocking durante operazioni in corso
- Throttling minimo per comandi di dispositivo

### Property Testing Focus
- Sequenze casuali di comandi rapidi (specialmente volume/dispositivi)
- Activity blocking: nessuna attività sovrapposta
- Consistenza dello stato sotto carico
- Comportamento corretto con input randomizzati
- Invarianti del sistema durante operazioni concorrenti
- Accettazione di tutti i comandi volume/dispositivo senza perdite