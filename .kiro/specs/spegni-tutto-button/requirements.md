# Requirements Document

## Introduction

Il sistema Harmony Hub Controller GUI ha già un tasto "SPEGNI TUTTO" esistente che deve essere configurato correttamente per eseguire l'attività con ID -1 per spegnere tutti i dispositivi del sistema multimediale.

## Glossary

- **Harmony_Hub**: Il dispositivo centrale che controlla tutti i dispositivi multimediali
- **Activity_ID**: Identificatore numerico univoco per ogni attività del sistema (-1 indica spegnimento)
- **Spegni_Tutto_Button**: Il pulsante rosso "SPEGNI TUTTO" già presente nella GUI
- **GUI_System**: L'interfaccia grafica PyQt6 del controller Harmony Hub
- **HarmonyWorker**: Il thread worker che gestisce i comandi asincroni verso l'hub

## Requirements

### Requirement 1: Funzionalità Tasto Spegni Tutto

**User Story:** Come utente, voglio che il tasto "SPEGNI TUTTO" esistente nella GUI esegua correttamente l'attività con ID -1, così posso spegnere rapidamente tutti i dispositivi multimediali con un singolo click.

#### Acceptance Criteria

1. WHEN l'utente clicca il tasto "SPEGNI TUTTO", THE GUI_System SHALL inviare il comando "off" al HarmonyWorker
2. WHEN il HarmonyWorker riceve il comando "off", THE System SHALL eseguire l'attività con ID "-1" tramite start_activity_fast
3. WHEN l'attività con ID "-1" viene eseguita con successo, THE Harmony_Hub SHALL spegnere tutti i dispositivi attivi
4. WHEN il comando di spegnimento è completato, THE GUI_System SHALL aggiornare lo stato per mostrare "⚫ OFF"
5. THE Spegni_Tutto_Button SHALL essere disabilitato quando il sistema è già spento (stato "OFF")

### Requirement 2: Gestione Errori e Feedback

**User Story:** Come utente, voglio essere informato se il comando di spegnimento fallisce, così posso capire se i dispositivi sono stati spenti correttamente.

#### Acceptance Criteria

1. IF il comando di spegnimento fallisce, THEN THE GUI_System SHALL mostrare un messaggio di errore tramite il StateManager
2. WHEN si verifica un errore di rete, THE HarmonyWorker SHALL tentare di riconnettersi automaticamente usando il meccanismo di retry
3. IF il tentativo di spegnimento non riceve risposta entro il timeout, THEN THE GUI_System SHALL informare l'utente dello stato incerto
4. WHEN il tasto viene premuto, THE GUI_System SHALL fornire feedback visivo immediato tramite il StateManager

### Requirement 3: Integrazione con Sistema Esistente

**User Story:** Come sviluppatore, voglio che il tasto "spegni tutto" si integri perfettamente con il sistema esistente, così manteniamo coerenza nell'interfaccia e nel comportamento.

#### Acceptance Criteria

1. THE Spegni_Tutto_Button SHALL utilizzare il sistema di code del StateManager per la gestione sequenziale dei comandi
2. THE Spegni_Tutto_Button SHALL rispettare le impostazioni di timeout e retry del HarmonyWorker esistente
3. WHEN il tasto viene utilizzato, THE GUI_System SHALL mantenere la stessa velocità di esecuzione degli altri comandi attività
4. THE Spegni_Tutto_Button SHALL essere coerente con lo stile visivo Tokyo Night esistente
5. THE Spegni_Tutto_Button SHALL essere disabilitato durante l'esecuzione di altre attività per prevenire conflitti