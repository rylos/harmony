# Implementation Plan: Spegni Tutto Button

## Overview

Il piano di implementazione si concentra sulla verifica e correzione del tasto "SPEGNI TUTTO" esistente nella GUI per garantire che esegua correttamente l'attività con ID -1. Il sistema è già largamente implementato, quindi i task si concentrano su verifica, test e eventuali correzioni.

## Tasks

- [x] 1. Analisi e verifica del codice esistente
  - Verificare che il tasto "SPEGNI TUTTO" sia correttamente configurato per inviare il comando "off"
  - Verificare che il HarmonyWorker gestisca correttamente il comando "off" con activity ID "-1"
  - Verificare l'integrazione con StateManager per la gestione sequenziale
  - _Requirements: 1.1, 1.2, 3.1_

- [ ]* 1.1 Write property test for button click command transmission
  - **Property 1: Button Click Command Transmission**
  - **Validates: Requirements 1.1**

- [x] 2. Verifica e correzione della gestione del comando "off"
  - Assicurarsi che il comando "off" nel HarmonyWorker chiami start_activity_fast("-1")
  - Verificare che il fallback per il comando "off" sia presente e corretto
  - Testare manualmente il comando per verificare il comportamento
  - _Requirements: 1.2, 1.3_

- [ ]* 2.1 Write property test for off command activity execution
  - **Property 2: Off Command Activity Execution**
  - **Validates: Requirements 1.2**

- [ ] 3. Verifica della gestione dello stato GUI
  - Verificare che lo stato GUI si aggiorni correttamente a "⚫ OFF" dopo il comando
  - Verificare che il tasto sia disabilitato quando il sistema è già spento
  - Verificare l'integrazione con StateManager per il feedback visivo
  - _Requirements: 1.4, 1.5, 2.4_

- [ ]* 3.1 Write property test for successful completion status update
  - **Property 3: Successful Completion Status Update**
  - **Validates: Requirements 1.4**

- [ ]* 3.2 Write property test for button state management when off
  - **Property 4: Button State Management When Off**
  - **Validates: Requirements 1.5**

- [ ]* 3.3 Write property test for immediate visual feedback
  - **Property 8: Immediate Visual Feedback**
  - **Validates: Requirements 2.4**

- [ ] 4. Checkpoint - Verifica funzionalità base
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implementazione gestione errori
  - Verificare che gli errori di rete siano gestiti correttamente con retry automatico
  - Verificare che i timeout siano gestiti con notifica all'utente
  - Verificare che gli errori di comando mostrino messaggi appropriati
  - _Requirements: 2.1, 2.2, 2.3_

- [ ]* 5.1 Write property test for error display on command failure
  - **Property 5: Error Display on Command Failure**
  - **Validates: Requirements 2.1**

- [ ]* 5.2 Write property test for network error retry mechanism
  - **Property 6: Network Error Retry Mechanism**
  - **Validates: Requirements 2.2**

- [ ]* 5.3 Write property test for timeout error notification
  - **Property 7: Timeout Error Notification**
  - **Validates: Requirements 2.3**

- [ ] 6. Verifica integrazione con sistema esistente
  - Verificare che il comando "off" utilizzi le stesse impostazioni di timeout e retry
  - Verificare che il tasto sia disabilitato durante l'esecuzione di altre attività
  - Verificare che lo stile visivo sia coerente con il tema Tokyo Night
  - _Requirements: 3.2, 3.4, 3.5_

- [ ]* 6.1 Write property test for StateManager queue integration
  - **Property 9: StateManager Queue Integration**
  - **Validates: Requirements 3.1**

- [ ]* 6.2 Write property test for consistent timeout and retry settings
  - **Property 10: Consistent Timeout and Retry Settings**
  - **Validates: Requirements 3.2**

- [ ]* 6.3 Write property test for button disabled during activity execution
  - **Property 11: Button Disabled During Activity Execution**
  - **Validates: Requirements 3.5**

- [ ] 7. Test di integrazione e validazione finale
  - Eseguire test manuali completi del tasto "SPEGNI TUTTO"
  - Verificare il comportamento in scenari reali con dispositivi connessi
  - Validare che tutti i requisiti siano soddisfatti
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.5_

- [ ]* 7.1 Write integration tests for complete off command flow
  - Test end-to-end flow from button click to status update
  - Test error scenarios and recovery
  - _Requirements: All_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Most functionality is already implemented, focus is on verification and testing
- Manual testing with real devices should be done carefully to avoid disrupting the system