# Requirements Document

## Introduction

Miglioramento della gestione dello stato nell'interfaccia GUI del Harmony Hub Controller per risolvere i problemi di inconsistenza quando si premono rapidamente i tasti del telecomando.

## Glossary

- **GUI**: Interfaccia grafica Qt6 del Harmony Hub Controller
- **Worker**: Thread asincrono che gestisce i comandi WebSocket
- **Status_Display**: Widget che mostra lo stato corrente dell'attività
- **Command_Queue**: Coda asincrona dei comandi in attesa di esecuzione
- **State_Manager**: Sistema centralizzato per la gestione dello stato dell'interfaccia

## Requirements

### Requirement 1: Gestione Comandi Rapidi

**User Story:** Come utente, voglio premere rapidamente i tasti del telecomando senza che l'interfaccia si confonda, così posso controllare i dispositivi in modo fluido.

#### Acceptance Criteria

1. WHEN un utente preme rapidamente più tasti THEN il sistema SHALL processare i comandi in sequenza senza sovrapporre gli stati
2. WHEN un comando è in esecuzione THEN il sistema SHALL mostrare un indicatore visivo chiaro dello stato "in elaborazione"
3. WHEN più comandi sono in coda THEN il sistema SHALL mostrare il numero di comandi in attesa
4. WHEN un comando fallisce THEN il sistema SHALL mostrare l'errore per 3 secondi e poi tornare allo stato reale

### Requirement 2: Comando Blocking e Throttling

**User Story:** Come utente, voglio che il sistema gestisca intelligentemente i comandi sovrapposti, bloccando le attività duplicate ma permettendo comandi rapidi di volume/dispositivo.

#### Acceptance Criteria

1. WHEN un comando di attività è in corso THEN il sistema SHALL bloccare nuovi comandi di attività fino al completamento
2. WHEN comandi di volume o dispositivo sono inviati rapidamente THEN il sistema SHALL accettare e processare tutti i comandi
3. WHEN comandi di dispositivo sono in corso THEN il sistema SHALL permettere altri comandi simili con throttling minimo per evitare sovraccarico dell'Hub

### Requirement 3: Stato Centralizzato

**User Story:** Come sviluppatore, voglio un sistema di gestione dello stato unificato, così posso evitare race conditions e inconsistenze.

#### Acceptance Criteria

1. THE State_Manager SHALL mantenere lo stato corrente dell'attività, comandi in coda, e stato di elaborazione
2. WHEN lo stato cambia THEN il State_Manager SHALL notificare tutti i componenti interessati
3. WHEN un timer di aggiornamento scade THEN il sistema SHALL verificare se ci sono operazioni in corso prima di aggiornare
4. THE State_Manager SHALL distinguere tra comandi di attività (lenti) e comandi di dispositivo (veloci)

### Requirement 4: Feedback Visivo Migliorato

**User Story:** Come utente, voglio vedere chiaramente cosa sta succedendo quando premo i tasti, così capisco se il comando è stato ricevuto ed elaborato.

#### Acceptance Criteria

1. WHEN un comando viene inviato THEN il Status_Display SHALL mostrare immediatamente "🚀 Elaborazione..."
2. WHEN ci sono comandi in coda THEN il Status_Display SHALL mostrare "🚀 Elaborazione... (+N)" dove N è il numero di comandi in coda
3. WHEN un comando di attività è in corso THEN il sistema SHALL disabilitare temporaneamente i bottoni delle attività
4. WHEN un comando è completato THEN il Status_Display SHALL mostrare il risultato per 1 secondo prima di aggiornare lo stato reale
5. WHEN si verifica un errore THEN il Status_Display SHALL mostrare "❌ Errore" con colore rosso per 3 secondi