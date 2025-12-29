# Implementation Plan: Harmony State Management

## Overview

Implementazione di un sistema centralizzato di gestione dello stato per risolvere i problemi di inconsistenza quando si premono rapidamente i tasti del telecomando. L'approccio si basa su un StateManager centralizzato che coordina GUI e Worker.

## Tasks

- [x] 1. Create StateManager core class
  - Implement StateManager class with Qt signals for state changes
  - Add state tracking for current activity, queue size, and processing status
  - Implement command type classification (ACTIVITY vs DEVICE)
  - _Requirements: 3.1, 3.4_

- [x] 1.1 Write property test for StateManager consistency
  - **Property 7: State Consistency**
  - **Validates: Requirements 3.1**

- [x] 2. Implement activity command blocking
- [x] 2.1 Add activity blocking logic to StateManager
  - Block new activity commands when one is in progress
  - Track activity start time and completion
  - _Requirements: 2.1_

- [x] 2.2 Write property test for activity blocking
  - **Property 5: Activity Command Blocking**
  - **Validates: Requirements 2.1, 4.3**

- [x] 3. Enhance HarmonyWorker with progress notifications
- [x] 3.1 Add progress signals to HarmonyWorker
  - Emit signals when commands start, progress, and complete
  - Integrate with StateManager for centralized state tracking
  - _Requirements: 3.2_

- [x] 3.2 Write property test for component notifications
  - **Property 8: Component Notification**
  - **Validates: Requirements 3.2**

- [x] 4. Implement improved visual feedback system
- [x] 4.1 Update GUI status display logic
  - Show immediate "🚀 Elaborazione..." feedback
  - Display queue count when multiple commands pending
  - Implement proper error display with timing
  - _Requirements: 4.1, 4.2, 4.5_

- [x] 4.2 Write property test for immediate visual feedback
  - **Property 2: Immediate Visual Feedback**
  - **Validates: Requirements 1.2, 4.1**

- [x] 4.3 Write property test for queue size display
  - **Property 3: Queue Size Display**
  - **Validates: Requirements 1.3, 4.2**

- [x] 5. Implement rapid command processing
- [x] 5.1 Remove existing debouncing logic
  - Remove _updating_activity flag and related timer logic
  - Ensure all volume/device commands are accepted immediately
  - _Requirements: 2.2_

- [x] 5.2 Add minimal device command throttling
  - Implement lightweight throttling to prevent Hub overload
  - Ensure all commands are still accepted and queued
  - _Requirements: 2.3_

- [x] 5.3 Write property test for rapid command acceptance
  - **Property 4: Rapid Command Acceptance**
  - **Validates: Requirements 2.2**

- [x] 5.4 Write property test for device command throttling
  - **Property 6: Device Command Throttling**
  - **Validates: Requirements 2.3**

- [x] 6. Integrate StateManager with GUI components
- [x] 6.1 Connect GUI buttons to StateManager
  - Replace direct worker calls with StateManager coordination
  - Implement button state management (enable/disable)
  - _Requirements: 4.3_

- [x] 6.2 Update timer coordination logic
  - Ensure status update timers check for ongoing operations
  - Prevent conflicting state updates
  - _Requirements: 3.3_

- [x] 6.3 Write property test for timer coordination
  - **Property 9: Timer Coordination**
  - **Validates: Requirements 3.3**

- [x] 7. Implement sequential command processing
- [x] 7.1 Ensure proper command ordering
  - Verify commands are processed in correct sequence
  - Maintain state consistency during rapid button presses
  - _Requirements: 1.1_

- [ ]* 7.2 Write property test for sequential processing
  - **Property 1: Sequential Command Processing**
  - **Validates: Requirements 1.1**

- [x] 8. Add error handling and recovery
- [x] 8.1 Implement error state management
  - Show errors for 3 seconds then return to real state
  - Handle network failures and timeouts gracefully
  - _Requirements: 1.4_

- [ ]* 8.2 Write unit tests for error handling
  - Test error display timing and recovery
  - Test network failure scenarios
  - _Requirements: 1.4_

- [x] 9. Implement command type classification
- [x] 9.1 Add command classification logic
  - Classify commands as ACTIVITY (slow) or DEVICE (fast)
  - Apply appropriate handling based on command type
  - _Requirements: 3.4_

- [ ]* 9.2 Write property test for command classification
  - **Property 10: Command Type Classification**
  - **Validates: Requirements 3.4**

- [x] 10. Final integration and testing
- [x] 10.1 Integration testing
  - Test complete system with rapid button presses
  - Verify no state inconsistencies under load
  - Test all activity and device command scenarios
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 10.2 Write integration tests
  - Test end-to-end rapid command scenarios
  - Test activity blocking with device commands
  - _Requirements: 1.1, 2.1, 2.2_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties
- Unit tests validate specific examples and timing requirements
- Focus on maintaining backward compatibility with existing CLI functionality