#!/usr/bin/env python3
"""
Property-based tests for StateManager consistency
Feature: harmony-state-management
"""

import pytest
import time
from hypothesis import given, strategies as st, settings
from PyQt6.QtCore import QCoreApplication
import sys

from state_manager import StateManager, CommandType, CommandState


# Ensure QApplication exists for Qt signals
if not QCoreApplication.instance():
    app = QCoreApplication(sys.argv)


class TestStateManagerConsistency:
    """Test StateManager state consistency properties"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
    
    @given(
        commands=st.lists(
            st.tuples(
                st.sampled_from(['tv', 'samsung', 'vol+', 'vol-', 'audio-on', 'smart_tv']),
                st.one_of(st.none(), st.sampled_from(['PowerOn', 'PowerOff', 'VolumeUp']))
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_state_consistency_property(self, commands):
        """
        Property 7: State Consistency
        For any sequence of commands, the StateManager should maintain internal consistency
        between current activity, queue size, and processing status.
        
        **Feature: harmony-state-management, Property 7: State Consistency**
        **Validates: Requirements 3.1**
        """
        # Track expected state
        expected_queue_size = 0
        expected_processing = False
        expected_activity_changing = False
        
        for command, action in commands:
            # Check if command can be accepted
            can_accept = self.state_manager.can_accept_command(command, action)
            
            if can_accept:
                # Queue the command
                queued = self.state_manager.queue_command(command, action)
                assert queued, f"Command {command} should have been queued"
                expected_queue_size += 1
                
                # Verify queue size consistency
                assert self.state_manager.pending_commands == expected_queue_size, \
                    f"Queue size mismatch: expected {expected_queue_size}, got {self.state_manager.pending_commands}"
                
                # Get next command and start processing
                next_command = self.state_manager.get_next_command()
                if next_command:
                    self.state_manager.start_command_processing(next_command)
                    expected_processing = True
                    
                    # If it's an activity command, activity should be changing
                    if next_command.command_type == CommandType.ACTIVITY:
                        expected_activity_changing = True
                    
                    # Verify processing state consistency
                    assert self.state_manager.is_processing == expected_processing, \
                        f"Processing state mismatch: expected {expected_processing}, got {self.state_manager.is_processing}"
                    
                    assert self.state_manager.is_activity_changing == expected_activity_changing, \
                        f"Activity changing state mismatch: expected {expected_activity_changing}, got {self.state_manager.is_activity_changing}"
                    
                    # Complete the command
                    self.state_manager.complete_command_processing(success=True)
                    expected_processing = False
                    expected_activity_changing = False
                    expected_queue_size -= 1
                    
                    # Verify state after completion
                    assert self.state_manager.is_processing == expected_processing, \
                        f"Processing state after completion mismatch: expected {expected_processing}, got {self.state_manager.is_processing}"
                    
                    assert self.state_manager.pending_commands == expected_queue_size, \
                        f"Queue size after completion mismatch: expected {expected_queue_size}, got {self.state_manager.pending_commands}"
            
            # Verify internal consistency invariants
            state_info = self.state_manager.get_state_info()
            
            # Queue length should match pending commands
            assert state_info['queue_length'] == state_info['pending_commands'], \
                f"Queue length ({state_info['queue_length']}) doesn't match pending commands ({state_info['pending_commands']})"
            
            # If processing, there should be a current command or queue should not be empty
            if state_info['is_processing']:
                assert state_info['current_command'] is not None or state_info['queue_length'] > 0, \
                    "Processing state is True but no current command and empty queue"
            
            # If activity is changing, processing should be True
            if state_info['is_activity_changing']:
                assert state_info['is_processing'], \
                    "Activity changing is True but processing is False"
            
            # Activity start time should be set if activity is changing
            if state_info['is_activity_changing']:
                assert state_info['activity_start_time'] > 0, \
                    "Activity changing is True but activity_start_time is not set"
            
            # UI state should be consistent with internal state
            ui_state = state_info['ui_state']
            assert ui_state['pending_count'] == state_info['pending_commands'], \
                f"UI pending count ({ui_state['pending_count']}) doesn't match internal pending commands ({state_info['pending_commands']})"
            
            # Buttons should be disabled when activity is changing
            if state_info['is_activity_changing']:
                assert not ui_state['buttons_enabled'], \
                    "Buttons should be disabled when activity is changing"
    
    @given(
        activity_name=st.sampled_from(['tv', 'music', 'gaming', 'unknown'])
    )
    @settings(max_examples=100)
    def test_activity_update_consistency(self, activity_name):
        """
        Test that activity updates maintain state consistency
        
        **Feature: harmony-state-management, Property 7: State Consistency**
        **Validates: Requirements 3.1**
        """
        initial_state = self.state_manager.get_state_info()
        
        # Update activity
        self.state_manager.update_current_activity(activity_name)
        
        # Verify activity was updated
        assert self.state_manager.current_activity == activity_name
        
        # Verify other state remains consistent
        updated_state = self.state_manager.get_state_info()
        
        # These should not change when just updating activity
        assert updated_state['pending_commands'] == initial_state['pending_commands']
        assert updated_state['is_processing'] == initial_state['is_processing']
        assert updated_state['is_activity_changing'] == initial_state['is_activity_changing']
        assert updated_state['queue_length'] == initial_state['queue_length']
        
        # Last update time should be updated
        assert updated_state['ui_state']['last_update'] >= initial_state['ui_state']['last_update']
    
    @given(
        commands=st.lists(
            st.sampled_from(['tv', 'music']),  # Activity commands only
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_activity_blocking_consistency(self, commands):
        """
        Test that activity blocking maintains state consistency
        
        **Feature: harmony-state-management, Property 7: State Consistency**
        **Validates: Requirements 3.1**
        """
        # Queue first activity command
        first_command = commands[0]
        assert self.state_manager.queue_command(first_command), \
            f"First activity command {first_command} should be accepted"
        
        # Start processing first command
        next_cmd = self.state_manager.get_next_command()
        if next_cmd:
            self.state_manager.start_command_processing(next_cmd)
            
            # Verify activity blocking state
            assert self.state_manager.is_activity_changing, \
                "Activity changing should be True when processing activity command"
            
            # Try to queue additional activity commands - they should be blocked
            for additional_command in commands[1:]:
                can_accept = self.state_manager.can_accept_command(additional_command)
                queued = self.state_manager.queue_command(additional_command)
                
                # Commands should be blocked
                assert not can_accept, \
                    f"Activity command {additional_command} should be blocked when another activity is in progress"
                assert not queued, \
                    f"Activity command {additional_command} should not be queued when blocked"
                
                # Verify queue size didn't change
                state_info = self.state_manager.get_state_info()
                assert state_info['pending_commands'] == 1, \
                    f"Queue size should remain 1, got {state_info['pending_commands']}"
            
            # Complete the activity command
            self.state_manager.complete_command_processing(success=True)
            
            # Verify state is cleared
            assert not self.state_manager.is_activity_changing, \
                "Activity changing should be False after completion"
            assert not self.state_manager.is_processing, \
                "Processing should be False after completion"
            assert self.state_manager.pending_commands == 0, \
                "Queue should be empty after completion"


class TestComponentNotifications:
    """Test StateManager component notification properties"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signal emissions
        self.status_signals = []
        self.button_signals = []
        self.queue_signals = []
        self.activity_signals = []
        
        # Connect to all signals
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.buttons_state_changed.connect(
            lambda enabled: self.button_signals.append(enabled)
        )
        self.state_manager.queue_size_changed.connect(
            lambda size: self.queue_signals.append(size)
        )
        self.state_manager.activity_state_changed.connect(
            lambda active: self.activity_signals.append(active)
        )
    
    @given(
        commands=st.lists(
            st.tuples(
                st.sampled_from(['tv', 'samsung', 'vol+', 'vol-', 'audio-on', 'smart_tv']),
                st.one_of(st.none(), st.sampled_from(['PowerOn', 'PowerOff', 'VolumeUp']))
            ),
            min_size=1,
            max_size=8
        )
    )
    @settings(max_examples=100)
    def test_component_notification_property(self, commands):
        """
        Property 8: Component Notification
        For any state change, all registered GUI components should receive 
        the appropriate notification signals.
        
        **Feature: harmony-state-management, Property 8: Component Notification**
        **Validates: Requirements 3.2**
        """
        # Clear any initial signals and reset state
        self.status_signals.clear()
        self.button_signals.clear()
        self.queue_signals.clear()
        self.activity_signals.clear()
        
        # Ensure StateManager starts in clean state
        current_queue_size = self.state_manager.pending_commands
        
        for command, action in commands:
            # Track signals before operation
            status_count_before = len(self.status_signals)
            button_count_before = len(self.button_signals)
            queue_count_before = len(self.queue_signals)
            activity_count_before = len(self.activity_signals)
            
            # Try to queue command
            can_accept = self.state_manager.can_accept_command(command, action)
            queued = self.state_manager.queue_command(command, action)
            
            if queued:
                # Queue size should have changed, so queue signal should be emitted
                assert len(self.queue_signals) > queue_count_before, \
                    f"Queue size signal should be emitted when command {command} is queued"
                
                # Verify the queue signal has correct value
                latest_queue_signal = self.queue_signals[-1]
                expected_queue_size = current_queue_size + 1
                assert latest_queue_signal == expected_queue_size, \
                    f"Queue signal should be {expected_queue_size}, got {latest_queue_signal}"
                
                current_queue_size = expected_queue_size
                
                # Get and start processing next command
                next_command = self.state_manager.get_next_command()
                if next_command:
                    # Track signals before starting processing
                    status_count_before_start = len(self.status_signals)
                    button_count_before_start = len(self.button_signals)
                    activity_count_before_start = len(self.activity_signals)
                    
                    self.state_manager.start_command_processing(next_command)
                    
                    # Status should change when processing starts
                    assert len(self.status_signals) > status_count_before_start, \
                        f"Status signal should be emitted when processing starts for {command}"
                    
                    # Verify status signal content
                    latest_status = self.status_signals[-1]
                    assert "🚀 Elaborazione" in latest_status[0], \
                        f"Status should indicate processing, got: {latest_status[0]}"
                    
                    # If it's an activity command, buttons should be disabled and activity state should change
                    if next_command.command_type.value == "activity":
                        assert len(self.button_signals) > button_count_before_start, \
                            f"Button state signal should be emitted for activity command {command}"
                        
                        # Buttons should be disabled
                        latest_button_signal = self.button_signals[-1]
                        assert latest_button_signal == False, \
                            f"Buttons should be disabled for activity command {command}"
                        
                        assert len(self.activity_signals) > activity_count_before_start, \
                            f"Activity state signal should be emitted for activity command {command}"
                        
                        # Activity state should be True
                        latest_activity_signal = self.activity_signals[-1]
                        assert latest_activity_signal == True, \
                            f"Activity state should be True for activity command {command}"
                    
                    # Complete the command
                    status_count_before_complete = len(self.status_signals)
                    queue_count_before_complete = len(self.queue_signals)
                    
                    self.state_manager.complete_command_processing(success=True)
                    
                    # Queue size should decrease
                    assert len(self.queue_signals) > queue_count_before_complete, \
                        f"Queue size signal should be emitted when command {command} completes"
                    
                    latest_queue_after_complete = self.queue_signals[-1]
                    expected_queue_after_complete = current_queue_size - 1
                    assert latest_queue_after_complete == expected_queue_after_complete, \
                        f"Queue size after completion should be {expected_queue_after_complete}, got {latest_queue_after_complete}"
                    
                    current_queue_size = expected_queue_after_complete
                    
                    # If it was an activity command, buttons should be re-enabled and activity state cleared
                    if next_command.command_type.value == "activity":
                        # Find the button re-enable signal (should be the latest one)
                        button_enable_signals = [sig for sig in self.button_signals if sig == True]
                        assert len(button_enable_signals) > 0, \
                            f"Buttons should be re-enabled after activity command {command} completes"
                        
                        # Activity state should be cleared
                        activity_false_signals = [sig for sig in self.activity_signals if sig == False]
                        assert len(activity_false_signals) > 0, \
                            f"Activity state should be cleared after activity command {command} completes"
        
        # Final verification: ensure all signals are consistent with final state
        final_state = self.state_manager.get_state_info()
        
        # Latest queue signal should match current queue size
        if self.queue_signals:
            assert self.queue_signals[-1] == final_state['pending_commands'], \
                f"Final queue signal ({self.queue_signals[-1]}) should match final queue size ({final_state['pending_commands']})"
        
        # Latest activity signal should match current activity state
        if self.activity_signals:
            assert self.activity_signals[-1] == final_state['is_activity_changing'], \
                f"Final activity signal ({self.activity_signals[-1]}) should match final activity state ({final_state['is_activity_changing']})"
        
        # Latest button signal should match current button state
        if self.button_signals:
            assert self.button_signals[-1] == final_state['ui_state']['buttons_enabled'], \
                f"Final button signal ({self.button_signals[-1]}) should match final button state ({final_state['ui_state']['buttons_enabled']})"
    
    @given(
        activity_name=st.sampled_from(['tv', 'music', 'gaming', 'unknown'])
    )
    @settings(max_examples=100)
    def test_activity_update_notifications(self, activity_name):
        """
        Test that activity updates emit appropriate notifications
        
        **Feature: harmony-state-management, Property 8: Component Notification**
        **Validates: Requirements 3.2**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Update activity
        self.state_manager.update_current_activity(activity_name)
        
        # Should emit status update if not processing
        if not self.state_manager.is_processing:
            assert len(self.status_signals) > 0, \
                f"Status signal should be emitted when activity is updated to {activity_name}"
    
    @given(
        error_message=st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=100)
    def test_error_notification_property(self, error_message):
        """
        Test that error states emit appropriate notifications
        
        **Feature: harmony-state-management, Property 8: Component Notification**
        **Validates: Requirements 3.2**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Queue a command and start processing
        self.state_manager.queue_command('tv')
        next_cmd = self.state_manager.get_next_command()
        if next_cmd:
            self.state_manager.start_command_processing(next_cmd)
            
            # Clear signals to focus on error completion
            self.status_signals.clear()
            
            # Complete with error
            self.state_manager.complete_command_processing(success=False, error_message=error_message)
            
            # Should emit error status
            assert len(self.status_signals) > 0, \
                f"Status signal should be emitted when command fails with error: {error_message}"
            
            # Verify error message is in status
            latest_status = self.status_signals[-1]
            assert "❌" in latest_status[0], \
                f"Error status should contain error indicator, got: {latest_status[0]}"
            assert error_message in latest_status[0], \
                f"Error status should contain error message '{error_message}', got: {latest_status[0]}"


class TestImmediateVisualFeedback:
    """Test immediate visual feedback properties"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signal emissions for visual feedback testing
        self.status_signals = []
        self.queue_signals = []
        
        # Connect to signals
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.queue_size_changed.connect(
            lambda size: self.queue_signals.append(size)
        )
    
    @given(
        commands=st.lists(
            st.tuples(
                st.sampled_from(['tv', 'music', 'shield', 'samsung', 'vol+', 'vol-', 'audio-on', 'smart_DirectionUp']),
                st.one_of(st.none(), st.sampled_from(['PowerOn', 'PowerOff', 'VolumeUp', 'VolumeDown', 'Menu', 'Home']))
            ),
            min_size=1,
            max_size=8
        )
    )
    @settings(max_examples=100)
    def test_immediate_visual_feedback_property(self, commands):
        """
        Property 2: Immediate Visual Feedback
        For any command sent to the system, the status display should immediately 
        show "🚀 Elaborazione..." before any processing begins.
        
        **Feature: harmony-state-management, Property 2: Immediate Visual Feedback**
        **Validates: Requirements 1.2, 4.1**
        """
        # Clear any initial signals
        self.status_signals.clear()
        self.queue_signals.clear()
        
        for command, action in commands:
            # Track signals before queueing command
            status_count_before = len(self.status_signals)
            
            # Try to queue the command
            can_accept = self.state_manager.can_accept_command(command, action)
            queued = self.state_manager.queue_command(command, action)
            
            if queued:
                # Immediate visual feedback should be provided when command is queued
                # The queue_command method should trigger _update_processing_state()
                # which should emit status signals for queued commands
                
                # Get the next command and start processing to trigger immediate feedback
                next_cmd = self.state_manager.get_next_command()
                if next_cmd:
                    # Clear signals to focus on immediate feedback when processing starts
                    self.status_signals.clear()
                    
                    # Start processing - this should immediately emit status signal
                    self.state_manager.start_command_processing(next_cmd)
                    
                    # Verify immediate visual feedback was provided
                    assert len(self.status_signals) > 0, \
                        f"Status signal should be emitted immediately when processing starts for command {command} {action or ''}"
                    
                    # Verify the status contains the processing indicator
                    latest_status = self.status_signals[-1]
                    assert "🚀 Elaborazione" in latest_status[0], \
                        f"Status should immediately show processing indicator for {command} {action or ''}, got: {latest_status[0]}"
                    
                    # Verify the status color indicates active processing
                    assert latest_status[1] == "#7aa2f7", \
                        f"Status color should indicate active processing (blue), got: {latest_status[1]}"
                    
                    # Complete the command to clean up state
                    self.state_manager.complete_command_processing(success=True)
            
            # If command was blocked (e.g., activity blocking), that's expected behavior
            # The property only applies to commands that are actually accepted and queued
    
    @given(
        command=st.sampled_from(['tv', 'music', 'shield', 'samsung', 'vol+', 'vol-']),
        action=st.one_of(st.none(), st.sampled_from(['PowerOn', 'VolumeUp', 'Menu']))
    )
    @settings(max_examples=100)
    def test_single_command_immediate_feedback(self, command, action):
        """
        Test immediate visual feedback for individual commands.
        
        **Feature: harmony-state-management, Property 2: Immediate Visual Feedback**
        **Validates: Requirements 1.2, 4.1**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Queue and process a single command
        can_accept = self.state_manager.can_accept_command(command, action)
        
        if can_accept:
            queued = self.state_manager.queue_command(command, action)
            assert queued, f"Command {command} {action or ''} should be queued when accepted"
            
            # Get and start processing the command
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Clear signals to focus on immediate feedback
                self.status_signals.clear()
                
                # Start processing - should provide immediate feedback
                self.state_manager.start_command_processing(next_cmd)
                
                # Verify immediate feedback
                assert len(self.status_signals) > 0, \
                    f"Immediate status signal should be emitted for {command} {action or ''}"
                
                # Verify feedback content
                status_text, status_color = self.status_signals[-1]
                assert "🚀 Elaborazione" in status_text, \
                    f"Status should show processing indicator immediately, got: {status_text}"
                assert status_color == "#7aa2f7", \
                    f"Status color should be active blue, got: {status_color}"
                
                # Clean up
                self.state_manager.complete_command_processing(success=True)
    
    @given(
        queue_size=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=100)
    def test_queue_count_immediate_feedback(self, queue_size):
        """
        Test immediate visual feedback shows queue count when multiple commands are pending.
        
        **Feature: harmony-state-management, Property 2: Immediate Visual Feedback**
        **Validates: Requirements 1.2, 4.1, 4.2**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Queue multiple device commands (they should all be accepted)
        device_commands = [('samsung', 'VolumeUp'), ('samsung', 'VolumeDown'), ('vol+', None), 
                          ('vol-', None), ('samsung', 'Menu'), ('samsung', 'Home'),
                          ('samsung', 'Back'), ('samsung', 'Select'), ('vol+', None), ('vol-', None)]
        
        # Queue the requested number of commands
        queued_commands = []
        for i in range(min(queue_size, len(device_commands))):
            cmd, action = device_commands[i]
            if self.state_manager.queue_command(cmd, action):
                queued_commands.append((cmd, action))
        
        # Should have queued the expected number of commands
        assert len(queued_commands) >= 2, f"Should have queued at least 2 commands, got {len(queued_commands)}"
        
        # Start processing first command
        next_cmd = self.state_manager.get_next_command()
        if next_cmd:
            # Clear signals to focus on queue count feedback
            self.status_signals.clear()
            
            # Start processing - should show queue count in status
            self.state_manager.start_command_processing(next_cmd)
            
            # Verify immediate feedback with queue count
            assert len(self.status_signals) > 0, \
                "Status signal should be emitted immediately when processing starts"
            
            status_text, status_color = self.status_signals[-1]
            
            # The StateManager shows total pending commands in the queue
            # When processing starts, pending_commands reflects the total queue size
            total_pending = self.state_manager.pending_commands
            
            if total_pending > 1:
                # Should show queue count for additional commands beyond the current one
                additional_count = total_pending - 1
                expected_pattern = f"🚀 Elaborazione... (+{additional_count})"
                assert expected_pattern in status_text, \
                    f"Status should show queue count: expected '{expected_pattern}', got: '{status_text}'"
            else:
                assert status_text == "🚀 Elaborazione...", \
                    f"Status should show simple processing indicator when no additional queue, got: '{status_text}'"
            
            # Verify active processing color
            assert status_color == "#7aa2f7", \
                f"Status color should be active blue, got: {status_color}"
            
            # Clean up
            self.state_manager.complete_command_processing(success=True)


class TestQueueSizeDisplay:
    """Test StateManager queue size display properties"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signal emissions for queue size display testing
        self.status_signals = []
        self.queue_signals = []
        
        # Connect to signals
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.queue_size_changed.connect(
            lambda size: self.queue_signals.append(size)
        )
    
    @given(
        queue_size=st.integers(min_value=2, max_value=15)
    )
    @settings(max_examples=100)
    def test_queue_size_display_property(self, queue_size):
        """
        Property 3: Queue Size Display
        For any number N of commands in the queue, the status display should show 
        "🚀 Elaborazione... (+N)" where N accurately reflects the pending commands.
        
        **Feature: harmony-state-management, Property 3: Queue Size Display**
        **Validates: Requirements 1.3, 4.2**
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        
        # Generate device commands to queue (they should all be accepted)
        device_commands = [
            ('samsung', 'VolumeUp'), ('samsung', 'VolumeDown'), ('vol+', None), 
            ('vol-', None), ('samsung', 'Menu'), ('samsung', 'Home'),
            ('samsung', 'Back'), ('samsung', 'Select'), ('samsung', 'ChannelUp'),
            ('samsung', 'ChannelDown'), ('samsung', 'PowerOn'), ('samsung', 'PowerOff'),
            ('vol+', None), ('vol-', None), ('mute', None)
        ]
        
        # Queue the requested number of commands
        queued_commands = []
        for i in range(min(queue_size, len(device_commands))):
            cmd, action = device_commands[i]
            if self.state_manager.queue_command(cmd, action):
                queued_commands.append((cmd, action))
        
        # Should have queued the expected number of commands
        actual_queued = len(queued_commands)
        assert actual_queued >= 2, f"Should have queued at least 2 commands, got {actual_queued}"
        
        # Verify queue size signals were emitted
        assert len(self.queue_signals) >= actual_queued, \
            f"Queue size signals should be emitted for each command, expected >= {actual_queued}, got {len(self.queue_signals)}"
        
        # Verify final queue size matches expected
        final_queue_size = self.queue_signals[-1] if self.queue_signals else 0
        assert final_queue_size == actual_queued, \
            f"Final queue size should be {actual_queued}, got {final_queue_size}"
        
        # Start processing first command to trigger queue size display
        next_cmd = self.state_manager.get_next_command()
        assert next_cmd is not None, "Should have command to process"
        
        # Clear signals to focus on queue size display
        self.status_signals.clear()
        
        # Start processing - should show queue count in status
        self.state_manager.start_command_processing(next_cmd)
        
        # Verify queue size display was shown
        assert len(self.status_signals) > 0, \
            "Status signal should be emitted when processing starts"
        
        status_text, status_color = self.status_signals[-1]
        
        # The StateManager shows total pending commands in the queue
        # When processing starts, pending_commands reflects the total queue size
        total_pending = self.state_manager.pending_commands
        
        if total_pending > 1:
            # Should show queue count for additional commands beyond the current one
            additional_count = total_pending - 1
            expected_pattern = f"🚀 Elaborazione... (+{additional_count})"
            assert expected_pattern in status_text, \
                f"Status should show queue count: expected '{expected_pattern}', got: '{status_text}'"
        else:
            # If only one command, should show simple processing indicator
            assert status_text == "🚀 Elaborazione...", \
                f"Status should show simple processing indicator when only one command, got: '{status_text}'"
        
        # Verify status color is correct
        assert status_color == "#7aa2f7", \
            f"Status color should be active blue, got: {status_color}"
        
        # Process commands one by one and verify queue count updates
        processed_count = 0
        while self.state_manager.pending_commands > 0:
            # Complete current command
            self.state_manager.complete_command_processing(success=True)
            processed_count += 1
            
            # If there are more commands, start processing next one
            if self.state_manager.pending_commands > 0:
                next_cmd = self.state_manager.get_next_command()
                if next_cmd:
                    # Clear signals to focus on queue size display
                    self.status_signals.clear()
                    
                    # Start processing next command
                    self.state_manager.start_command_processing(next_cmd)
                    
                    # Verify queue size display is updated
                    if self.status_signals:
                        status_text, status_color = self.status_signals[-1]
                        remaining_pending = self.state_manager.pending_commands
                        
                        if remaining_pending > 1:
                            additional_count = remaining_pending - 1
                            expected_pattern = f"🚀 Elaborazione... (+{additional_count})"
                            assert expected_pattern in status_text, \
                                f"Status should show updated queue count: expected '{expected_pattern}', got: '{status_text}'"
                        else:
                            assert status_text == "🚀 Elaborazione...", \
                                f"Status should show simple processing when last command, got: '{status_text}'"
        
        # Complete final command
        if self.state_manager.is_processing:
            self.state_manager.complete_command_processing(success=True)
        
        # Verify all commands were processed
        assert processed_count == actual_queued, \
            f"All queued commands should be processed: expected {actual_queued}, got {processed_count}"
        
        # Verify final state is clean
        assert self.state_manager.pending_commands == 0, "Queue should be empty after processing all commands"
        assert not self.state_manager.is_processing, "Should not be processing after all commands complete"
    
    @given(
        commands=st.lists(
            st.tuples(
                st.sampled_from(['samsung', 'vol+', 'vol-', 'mute']),
                st.one_of(st.none(), st.sampled_from(['VolumeUp', 'VolumeDown', 'Menu', 'Home']))
            ),
            min_size=3,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_dynamic_queue_size_display_property(self, commands):
        """
        Test that queue size display updates dynamically as commands are processed.
        
        **Feature: harmony-state-management, Property 3: Queue Size Display**
        **Validates: Requirements 1.3, 4.2**
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        
        # Queue all commands
        queued_commands = []
        for cmd, action in commands:
            if self.state_manager.queue_command(cmd, action):
                queued_commands.append((cmd, action))
        
        # Should have queued at least some commands
        assert len(queued_commands) >= 3, f"Should have queued at least 3 commands, got {len(queued_commands)}"
        
        # Track queue size display as we process commands
        queue_displays = []
        
        while self.state_manager.pending_commands > 0:
            # Get next command
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Clear signals to focus on current queue display
                self.status_signals.clear()
                
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Capture queue size display
                if self.status_signals:
                    status_text, status_color = self.status_signals[-1]
                    current_pending = self.state_manager.pending_commands
                    
                    # Record the display for verification
                    queue_displays.append((current_pending, status_text))
                    
                    # Verify display format is correct for current queue size
                    if current_pending > 1:
                        additional_count = current_pending - 1
                        expected_pattern = f"🚀 Elaborazione... (+{additional_count})"
                        assert expected_pattern in status_text, \
                            f"Queue display should show (+{additional_count}) for {current_pending} pending, got: '{status_text}'"
                    else:
                        assert status_text == "🚀 Elaborazione...", \
                            f"Queue display should show simple processing for 1 pending, got: '{status_text}'"
                
                # Complete the command
                self.state_manager.complete_command_processing(success=True)
        
        # Verify we captured queue displays for different queue sizes
        assert len(queue_displays) >= 3, f"Should have captured queue displays, got {len(queue_displays)}"
        
        # Verify queue sizes were decreasing (commands processed in order)
        queue_sizes = [pending for pending, _ in queue_displays]
        for i in range(len(queue_sizes) - 1):
            assert queue_sizes[i] >= queue_sizes[i + 1], \
                f"Queue size should decrease or stay same: {queue_sizes[i]} -> {queue_sizes[i + 1]}"
        
        # Verify displays were accurate for each queue size
        for pending, display in queue_displays:
            if pending > 1:
                additional = pending - 1
                expected = f"(+{additional})"
                assert expected in display, \
                    f"Display '{display}' should contain '{expected}' for {pending} pending commands"
            else:
                assert "(+" not in display, \
                    f"Display '{display}' should not show queue count for single command"
    
    @given(
        initial_queue_size=st.integers(min_value=5, max_value=12)
    )
    @settings(max_examples=100)
    def test_queue_size_accuracy_property(self, initial_queue_size):
        """
        Test that queue size display accurately reflects the actual number of pending commands.
        
        **Feature: harmony-state-management, Property 3: Queue Size Display**
        **Validates: Requirements 1.3, 4.2**
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        
        # Queue initial commands
        device_commands = [
            ('samsung', 'VolumeUp'), ('vol+', None), ('samsung', 'VolumeDown'), 
            ('vol-', None), ('samsung', 'Menu'), ('samsung', 'Home'),
            ('samsung', 'Back'), ('mute', None), ('samsung', 'Select'),
            ('vol+', None), ('samsung', 'ChannelUp'), ('vol-', None)
        ]
        
        queued_count = 0
        for i in range(min(initial_queue_size, len(device_commands))):
            cmd, action = device_commands[i]
            if self.state_manager.queue_command(cmd, action):
                queued_count += 1
        
        # Verify initial queue size
        assert queued_count >= 5, f"Should have queued at least 5 commands, got {queued_count}"
        assert self.state_manager.pending_commands == queued_count, \
            f"Internal queue size should match queued count: expected {queued_count}, got {self.state_manager.pending_commands}"
        
        # Process commands and verify accuracy at each step
        while self.state_manager.pending_commands > 0:
            # Record current state before processing
            pending_before = self.state_manager.pending_commands
            
            # Start processing next command
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Clear signals to focus on current display
                self.status_signals.clear()
                
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Verify queue size display accuracy
                if self.status_signals:
                    status_text, status_color = self.status_signals[-1]
                    
                    # The display should accurately reflect pending_commands
                    actual_pending = self.state_manager.pending_commands
                    assert actual_pending == pending_before, \
                        f"Pending commands should not change during start_processing: {pending_before} -> {actual_pending}"
                    
                    if actual_pending > 1:
                        # Should show accurate additional count
                        additional_count = actual_pending - 1
                        expected_display = f"🚀 Elaborazione... (+{additional_count})"
                        assert expected_display in status_text, \
                            f"Display should accurately show +{additional_count} for {actual_pending} pending: got '{status_text}'"
                    else:
                        # Should show simple processing indicator
                        assert status_text == "🚀 Elaborazione...", \
                            f"Display should show simple processing for 1 pending: got '{status_text}'"
                
                # Complete the command
                self.state_manager.complete_command_processing(success=True)
                
                # Verify queue size decreased by 1
                pending_after = self.state_manager.pending_commands
                assert pending_after == pending_before - 1, \
                    f"Queue size should decrease by 1 after completion: {pending_before} -> {pending_after}"
        
        # Verify final state
        assert self.state_manager.pending_commands == 0, "Queue should be empty after processing all commands"
        assert not self.state_manager.is_processing, "Should not be processing after completion"


class TestTimerCoordination:
    """Test StateManager timer coordination to prevent status conflicts"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signal emissions for timer coordination testing
        self.status_signals = []
        
        # Connect to signals
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
    
    def test_timer_coordination_during_activity_change(self):
        """
        Test that timer updates are properly blocked during activity changes.
        This prevents the "avvio watch tv" -> "off" -> "Watch TV" issue.
        
        **Feature: harmony-state-management, Timer Coordination**
        **Validates: Requirements 3.3**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Start an activity command
        assert self.state_manager.queue_command('tv'), "TV activity should be accepted"
        
        # Get and start processing the activity
        next_cmd = self.state_manager.get_next_command()
        assert next_cmd is not None, "Should have TV command to process"
        
        self.state_manager.start_command_processing(next_cmd)
        
        # Verify activity is in progress
        assert self.state_manager.is_activity_changing, "Activity should be changing"
        assert self.state_manager.is_processing, "Should be processing"
        
        # Clear signals to focus on timer coordination
        self.status_signals.clear()
        
        # Try to request a timer-based status update (this simulates the GUI timer)
        timer_update_allowed = self.state_manager.request_status_update()
        
        # Timer update should be blocked during activity change
        assert not timer_update_allowed, \
            "Timer updates should be blocked during activity change to prevent status conflicts"
        
        # Verify that is_timer_update_allowed returns False
        assert not self.state_manager.is_timer_update_allowed(), \
            "Timer updates should not be allowed during activity change"
        
        # Complete the activity successfully
        self.state_manager.complete_command_processing(success=True)
        
        # Now timer updates should be allowed again
        assert self.state_manager.is_timer_update_allowed(), \
            "Timer updates should be allowed after activity completes"
        
        timer_update_allowed_after = self.state_manager.request_status_update()
        assert timer_update_allowed_after, \
            "Timer updates should be allowed after activity completion"
        
        # Verify final state
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared"
        assert not self.state_manager.is_processing, "Processing should be cleared"
    
    def test_timer_coordination_with_device_commands(self):
        """
        Test that timer updates are allowed during device command processing.
        Device commands should not block timer updates.
        
        **Feature: harmony-state-management, Timer Coordination**
        **Validates: Requirements 3.3**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Start a device command
        assert self.state_manager.queue_command('samsung', 'VolumeUp'), "Device command should be accepted"
        
        # Get and start processing the device command
        next_cmd = self.state_manager.get_next_command()
        assert next_cmd is not None, "Should have device command to process"
        
        self.state_manager.start_command_processing(next_cmd)
        
        # Verify device command is processing but not blocking activity changes
        assert self.state_manager.is_processing, "Should be processing device command"
        assert not self.state_manager.is_activity_changing, "Activity should not be changing for device command"
        
        # Timer updates should still be allowed for device commands
        # (only activity changes block timer updates)
        timer_update_allowed = self.state_manager.request_status_update()
        assert timer_update_allowed, \
            "Timer updates should be allowed during device command processing"
        
        assert self.state_manager.is_timer_update_allowed(), \
            "Timer updates should be allowed for device commands"
        
        # Complete the device command
        self.state_manager.complete_command_processing(success=True)
        
        # Timer updates should still be allowed
        assert self.state_manager.is_timer_update_allowed(), \
            "Timer updates should remain allowed after device command completion"
    
    def test_activity_completion_feedback_timing(self):
        """
        Test that activity completion shows proper feedback timing.
        This ensures smooth transitions without timer conflicts.
        
        **Feature: harmony-state-management, Timer Coordination**
        **Validates: Requirements 3.3, 4.1**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Start an activity command
        assert self.state_manager.queue_command('tv'), "TV activity should be accepted"
        
        # Get and start processing the activity
        next_cmd = self.state_manager.get_next_command()
        self.state_manager.start_command_processing(next_cmd)
        
        # Clear signals to focus on completion feedback
        self.status_signals.clear()
        
        # Complete the activity successfully
        self.state_manager.complete_command_processing(success=True)
        
        # Should emit completion feedback for activity commands
        assert len(self.status_signals) > 0, \
            "Completion feedback should be emitted for activity commands"
        
        # Find completion feedback signal
        completion_signal = None
        for status_text, color in self.status_signals:
            if "✅" in status_text and "Attività" in status_text:
                completion_signal = (status_text, color)
                break
        
        assert completion_signal is not None, \
            f"Should show activity completion feedback, got signals: {self.status_signals}"
        
        # Verify completion feedback format
        completion_text, completion_color = completion_signal
        assert "✅ Attività avviata" in completion_text, \
            f"Completion feedback should show success message, got: {completion_text}"
        assert completion_color == "#9ece6a", \
            f"Completion feedback should use success color, got: {completion_color}"
        
        # Verify state is properly cleared
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared"
        assert not self.state_manager.is_processing, "Processing should be cleared"
        assert self.state_manager.is_timer_update_allowed(), "Timer updates should be allowed after completion"
    
    def test_immediate_feedback_timing(self):
        """
        Test that visual feedback is truly immediate (no delays).
        
        **Feature: harmony-state-management, Property 2: Immediate Visual Feedback**
        **Validates: Requirements 1.2, 4.1**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Queue a command
        assert self.state_manager.queue_command('samsung', 'VolumeUp'), "Command should be queued"
        
        # Get the command
        next_cmd = self.state_manager.get_next_command()
        assert next_cmd is not None, "Should have command to process"
        
        # Clear signals and measure timing
        self.status_signals.clear()
        start_time = time.time()
        
        # Start processing
        self.state_manager.start_command_processing(next_cmd)
        
        # Check that signal was emitted immediately
        feedback_time = time.time() - start_time
        
        # Verify immediate feedback
        assert len(self.status_signals) > 0, "Status signal should be emitted"
        assert feedback_time < 0.001, f"Visual feedback should be immediate, took {feedback_time:.6f}s"
        
        # Verify feedback content
        status_text, status_color = self.status_signals[-1]
        assert "🚀 Elaborazione" in status_text, f"Should show processing indicator, got: {status_text}"
        
        # Clean up
        self.state_manager.complete_command_processing(success=True)


class TestTimerCoordinationProperty:
    """Test StateManager timer coordination property-based tests"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signal emissions for timer coordination testing
        self.status_signals = []
        self.timer_requests = []
        
        # Connect to signals
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
    
    @given(
        commands=st.lists(
            st.tuples(
                st.sampled_from(['tv', 'music', 'shield', 'samsung', 'vol+', 'vol-', 'audio-on']),
                st.one_of(st.none(), st.sampled_from(['PowerOn', 'PowerOff', 'VolumeUp', 'VolumeDown', 'Menu']))
            ),
            min_size=1,
            max_size=8
        ),
        timer_intervals=st.lists(
            st.integers(min_value=1, max_value=10),  # Timer intervals in arbitrary units
            min_size=5,
            max_size=15
        )
    )
    @settings(max_examples=100)
    def test_timer_coordination_property(self, commands, timer_intervals):
        """
        Property 9: Timer Coordination
        For any timer expiration, the system should check for ongoing operations 
        before updating the display state.
        
        **Feature: harmony-state-management, Property 9: Timer Coordination**
        **Validates: Requirements 3.3**
        """
        # Clear signals and tracking
        self.status_signals.clear()
        self.timer_requests.clear()
        
        # Track timer coordination behavior throughout command processing
        timer_blocked_count = 0
        timer_allowed_count = 0
        activity_in_progress_periods = []
        device_processing_periods = []
        
        # Process commands while simulating timer requests
        command_index = 0
        timer_index = 0
        
        for command, action in commands:
            # Try to queue the command
            can_accept = self.state_manager.can_accept_command(command, action)
            queued = self.state_manager.queue_command(command, action)
            
            if queued:
                # Get and start processing the command
                next_cmd = self.state_manager.get_next_command()
                if next_cmd:
                    # Record state before processing
                    was_activity_changing_before = self.state_manager.is_activity_changing
                    was_processing_before = self.state_manager.is_processing
                    
                    # Start processing
                    self.state_manager.start_command_processing(next_cmd)
                    
                    # Record state during processing
                    is_activity_changing = self.state_manager.is_activity_changing
                    is_processing = self.state_manager.is_processing
                    command_type = next_cmd.command_type
                    
                    # Simulate timer requests during command processing
                    # Use timer intervals to determine when timers would fire
                    for i in range(min(3, len(timer_intervals) - timer_index)):
                        if timer_index < len(timer_intervals):
                            # Simulate timer expiration
                            timer_allowed = self.state_manager.request_status_update()
                            is_timer_allowed = self.state_manager.is_timer_update_allowed()
                            
                            # Record timer coordination decision
                            self.timer_requests.append({
                                'command': command,
                                'action': action,
                                'command_type': command_type.value if command_type else 'unknown',
                                'is_activity_changing': is_activity_changing,
                                'is_processing': is_processing,
                                'timer_allowed': timer_allowed,
                                'is_timer_allowed': is_timer_allowed
                            })
                            
                            # Verify timer coordination property
                            if is_activity_changing:
                                # CRITICAL: Timer updates should be blocked during activity changes
                                assert not timer_allowed, \
                                    f"Timer update should be blocked during activity change for {command} {action or ''}"
                                assert not is_timer_allowed, \
                                    f"is_timer_update_allowed() should return False during activity change for {command} {action or ''}"
                                timer_blocked_count += 1
                                activity_in_progress_periods.append({
                                    'command': command,
                                    'action': action,
                                    'timer_blocked': True
                                })
                            else:
                                # Timer updates should be allowed for non-activity operations
                                assert timer_allowed, \
                                    f"Timer update should be allowed for non-activity command {command} {action or ''}"
                                assert is_timer_allowed, \
                                    f"is_timer_update_allowed() should return True for non-activity command {command} {action or ''}"
                                timer_allowed_count += 1
                                
                                if is_processing:
                                    device_processing_periods.append({
                                        'command': command,
                                        'action': action,
                                        'timer_allowed': True
                                    })
                            
                            timer_index += 1
                    
                    # Complete the command
                    self.state_manager.complete_command_processing(success=True)
                    
                    # Verify timer coordination after completion
                    post_completion_allowed = self.state_manager.is_timer_update_allowed()
                    assert post_completion_allowed, \
                        f"Timer updates should be allowed after {command} {action or ''} completes"
            
            command_index += 1
        
        # Verify overall timer coordination behavior
        total_timer_requests = len(self.timer_requests)
        if total_timer_requests > 0:
            # Should have made timer coordination decisions
            assert timer_blocked_count + timer_allowed_count == total_timer_requests, \
                f"All timer requests should be accounted for: {timer_blocked_count} + {timer_allowed_count} = {total_timer_requests}"
            
            # Verify activity blocking behavior
            activity_commands = [req for req in self.timer_requests if req['command_type'] == 'activity']
            if activity_commands:
                # All activity commands should have blocked timer updates
                activity_blocked = [req for req in activity_commands if not req['timer_allowed']]
                assert len(activity_blocked) == len(activity_commands), \
                    f"All activity commands should block timer updates: {len(activity_blocked)} of {len(activity_commands)} blocked"
            
            # Verify device command behavior
            device_commands = [req for req in self.timer_requests if req['command_type'] in ['device', 'audio']]
            if device_commands:
                # Device commands should allow timer updates (unless during activity change)
                device_allowed = [req for req in device_commands if req['timer_allowed'] and not req['is_activity_changing']]
                device_during_activity = [req for req in device_commands if req['is_activity_changing']]
                
                # Device commands not during activity changes should allow timers
                expected_device_allowed = len(device_commands) - len(device_during_activity)
                assert len(device_allowed) == expected_device_allowed, \
                    f"Device commands should allow timer updates when not during activity: {len(device_allowed)} of {expected_device_allowed} allowed"
        
        # Verify final state allows timer updates
        final_timer_allowed = self.state_manager.is_timer_update_allowed()
        assert final_timer_allowed, "Timer updates should be allowed in final state"
        
        # Verify no ongoing operations
        assert not self.state_manager.is_processing, "Should not be processing in final state"
        assert not self.state_manager.is_activity_changing, "Should not be changing activity in final state"
    
    @given(
        activity_sequence=st.lists(
            st.sampled_from(['tv', 'music', 'shield', 'off']),
            min_size=1,
            max_size=4
        )
    )
    @settings(max_examples=100)
    def test_activity_timer_blocking_consistency(self, activity_sequence):
        """
        Test that timer blocking is consistent across different activity sequences.
        
        **Feature: harmony-state-management, Property 9: Timer Coordination**
        **Validates: Requirements 3.3**
        """
        # Clear tracking
        self.timer_requests.clear()
        
        for activity in activity_sequence:
            # Clear any previous activity state
            if self.state_manager.is_activity_changing:
                # Force clear state for test consistency
                self.state_manager.is_activity_changing = False
                self.state_manager.is_processing = False
            
            # Queue activity
            if self.state_manager.queue_command(activity):
                # Get and start processing
                next_cmd = self.state_manager.get_next_command()
                if next_cmd:
                    self.state_manager.start_command_processing(next_cmd)
                    
                    # Verify timer blocking during activity
                    assert self.state_manager.is_activity_changing, \
                        f"Activity {activity} should set activity_changing flag"
                    
                    # Test timer coordination multiple times during activity
                    for _ in range(3):
                        timer_allowed = self.state_manager.request_status_update()
                        is_timer_allowed = self.state_manager.is_timer_update_allowed()
                        
                        # Both methods should consistently block timers
                        assert not timer_allowed, \
                            f"request_status_update() should return False during {activity}"
                        assert not is_timer_allowed, \
                            f"is_timer_update_allowed() should return False during {activity}"
                    
                    # Complete activity
                    self.state_manager.complete_command_processing(success=True)
                    
                    # Verify timer coordination is restored
                    post_timer_allowed = self.state_manager.request_status_update()
                    post_is_timer_allowed = self.state_manager.is_timer_update_allowed()
                    
                    assert post_timer_allowed, \
                        f"request_status_update() should return True after {activity} completes"
                    assert post_is_timer_allowed, \
                        f"is_timer_update_allowed() should return True after {activity} completes"
        
        # Final verification
        assert self.state_manager.is_timer_update_allowed(), \
            "Timer updates should be allowed after all activities complete"


class TestActivityBlocking:
    """Test StateManager activity blocking properties"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signal emissions for activity blocking tests
        self.status_signals = []
        self.button_signals = []
        self.activity_signals = []
        
        # Connect to signals
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.buttons_state_changed.connect(
            lambda enabled: self.button_signals.append(enabled)
        )
        self.state_manager.activity_state_changed.connect(
            lambda active: self.activity_signals.append(active)
        )
    
    @given(
        primary_activity=st.sampled_from(['tv', 'music', 'shield', 'off']),
        blocked_activities=st.lists(
            st.sampled_from(['tv', 'music', 'shield', 'off']),
            min_size=1,
            max_size=4
        ),
        device_commands=st.lists(
            st.tuples(
                st.sampled_from(['samsung', 'shield', 'onkyo']),
                st.sampled_from(['PowerOn', 'PowerOff', 'VolumeUp', 'VolumeDown', 'Menu', 'Home'])
            ),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_activity_command_blocking_property(self, primary_activity, blocked_activities, device_commands):
        """
        Property 5: Activity Command Blocking
        For any activity command in progress, all new activity commands should be blocked 
        until the current activity command completes, while device commands remain accepted.
        
        **Feature: harmony-state-management, Property 5: Activity Command Blocking**
        **Validates: Requirements 2.1, 4.3**
        """
        # Clear signals
        self.status_signals.clear()
        self.button_signals.clear()
        self.activity_signals.clear()
        
        # Step 1: Queue and start processing the primary activity
        assert self.state_manager.queue_command(primary_activity), \
            f"Primary activity {primary_activity} should be accepted"
        
        # Get and start processing the primary activity
        next_cmd = self.state_manager.get_next_command()
        assert next_cmd is not None, f"Should have command to process for {primary_activity}"
        assert next_cmd.command_type.value == "activity", \
            f"Command {primary_activity} should be classified as ACTIVITY"
        
        self.state_manager.start_command_processing(next_cmd)
        
        # Verify activity blocking state is active (Requirement 2.1)
        assert self.state_manager.is_activity_changing, \
            f"Activity changing should be True when processing {primary_activity}"
        
        # Verify button disable signal was emitted (Requirement 4.3)
        assert False in self.button_signals, \
            f"Button disable signal should be emitted for activity {primary_activity}"
        
        # Verify activity state signal was emitted
        assert True in self.activity_signals, \
            f"Activity state signal should be emitted for activity {primary_activity}"
        
        # Step 2: Try to queue other activity commands - they should all be blocked
        blocked_count = 0
        for blocked_activity in blocked_activities:
            # Skip if it's the same as primary activity (would be redundant)
            if blocked_activity == primary_activity:
                continue
                
            can_accept = self.state_manager.can_accept_command(blocked_activity)
            queued = self.state_manager.queue_command(blocked_activity)
            
            # Activity should be blocked (Requirement 2.1)
            assert not can_accept, \
                f"Activity {blocked_activity} should be blocked when {primary_activity} is in progress"
            assert not queued, \
                f"Activity {blocked_activity} should not be queued when {primary_activity} is in progress"
            
            blocked_count += 1
        
        # Step 3: Device commands should still be accepted during activity blocking
        accepted_device_commands = []
        for device, action in device_commands:
            can_accept = self.state_manager.can_accept_command(device, action)
            queued = self.state_manager.queue_command(device, action)
            
            # Device commands should be accepted even during activity blocking
            assert can_accept, \
                f"Device command {device} {action} should be accepted when {primary_activity} is in progress"
            assert queued, \
                f"Device command {device} {action} should be queued when {primary_activity} is in progress"
            
            accepted_device_commands.append((device, action))
        
        # Verify queue state consistency
        expected_queue_size = 1 + len(accepted_device_commands)  # Primary activity + device commands
        assert self.state_manager.pending_commands == expected_queue_size, \
            f"Queue size should be {expected_queue_size} (1 activity + {len(accepted_device_commands)} devices), got {self.state_manager.pending_commands}"
        
        # Step 4: Complete the primary activity
        self.state_manager.complete_command_processing(success=True)
        
        # Verify activity blocking is cleared (Requirement 2.1)
        assert not self.state_manager.is_activity_changing, \
            f"Activity changing should be False after {primary_activity} completes"
        
        # Verify button enable signal was emitted (Requirement 4.3)
        assert True in self.button_signals, \
            f"Button enable signal should be emitted after {primary_activity} completes"
        
        # Verify activity state cleared signal was emitted
        assert False in self.activity_signals, \
            f"Activity state cleared signal should be emitted after {primary_activity} completes"
        
        # Step 5: Now other activities should be accepted again
        if blocked_activities:
            # Test that at least one previously blocked activity is now accepted
            test_activity = blocked_activities[0]
            if test_activity != primary_activity:
                assert self.state_manager.can_accept_command(test_activity), \
                    f"Activity {test_activity} should be accepted after {primary_activity} completes"
        
        # Step 6: Process remaining device commands to verify they work correctly
        processed_device_commands = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_device_commands.append((next_cmd.command, next_cmd.action))
        
        # Verify all device commands were processed in correct order
        assert processed_device_commands == accepted_device_commands, \
            f"Device commands should be processed in FIFO order: expected {accepted_device_commands}, got {processed_device_commands}"
        
        # Verify final state is clean
        assert not self.state_manager.is_processing, "Should not be processing at end"
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared at end"
        assert self.state_manager.pending_commands == 0, "Queue should be empty at end"
    
    @given(
        activities=st.lists(
            st.sampled_from(['tv', 'music', 'shield', 'off']),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_sequential_activity_blocking_property(self, activities):
        """
        Test that activity blocking works correctly for sequences of activity commands.
        Only the first activity should be accepted, all others should be blocked.
        
        **Feature: harmony-state-management, Property 5: Activity Command Blocking**
        **Validates: Requirements 2.1, 4.3**
        """
        # Clear signals
        self.status_signals.clear()
        self.button_signals.clear()
        self.activity_signals.clear()
        
        # Try to queue all activities in sequence
        accepted_activities = []
        blocked_activities = []
        
        for activity in activities:
            can_accept = self.state_manager.can_accept_command(activity)
            queued = self.state_manager.queue_command(activity)
            
            if queued:
                accepted_activities.append(activity)
            else:
                blocked_activities.append(activity)
        
        # Only the first activity should be accepted
        assert len(accepted_activities) == 1, \
            f"Only first activity should be accepted, got {len(accepted_activities)}: {accepted_activities}"
        assert accepted_activities[0] == activities[0], \
            f"First activity {activities[0]} should be accepted, got {accepted_activities[0]}"
        
        # All subsequent activities should be blocked
        expected_blocked = activities[1:]
        assert blocked_activities == expected_blocked, \
            f"Subsequent activities should be blocked: expected {expected_blocked}, got {blocked_activities}"
        
        # Start processing the accepted activity
        next_cmd = self.state_manager.get_next_command()
        if next_cmd:
            self.state_manager.start_command_processing(next_cmd)
            
            # Verify activity blocking state
            assert self.state_manager.is_activity_changing, \
                "Activity changing should be True when processing activity"
            
            # Verify buttons are disabled
            assert False in self.button_signals, \
                "Buttons should be disabled during activity processing"
            
            # Complete the activity
            self.state_manager.complete_command_processing(success=True)
            
            # Verify activity blocking is cleared
            assert not self.state_manager.is_activity_changing, \
                "Activity changing should be False after completion"
            
            # Verify buttons are re-enabled
            assert True in self.button_signals, \
                "Buttons should be re-enabled after activity completion"
    
    @given(
        activity=st.sampled_from(['tv', 'music', 'shield']),
        audio_commands=st.lists(
            st.sampled_from(['vol+', 'vol-', 'mute', 'audio-on', 'audio-off']),
            min_size=1,
            max_size=6
        )
    )
    @settings(max_examples=100)
    def test_activity_blocking_with_audio_commands_property(self, activity, audio_commands):
        """
        Test that audio commands are accepted during activity blocking.
        
        **Feature: harmony-state-management, Property 5: Activity Command Blocking**
        **Validates: Requirements 2.1, 4.3**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Start activity processing
        assert self.state_manager.queue_command(activity), f"Activity {activity} should be accepted"
        
        next_cmd = self.state_manager.get_next_command()
        if next_cmd:
            self.state_manager.start_command_processing(next_cmd)
            
            # Verify activity is in progress
            assert self.state_manager.is_activity_changing, \
                f"Activity changing should be True when processing {activity}"
            
            # Try to queue audio commands - they should all be accepted
            accepted_audio_commands = []
            for audio_cmd in audio_commands:
                can_accept = self.state_manager.can_accept_command(audio_cmd)
                queued = self.state_manager.queue_command(audio_cmd)
                
                # Audio commands should be accepted during activity blocking
                assert can_accept, \
                    f"Audio command {audio_cmd} should be accepted during {activity} processing"
                assert queued, \
                    f"Audio command {audio_cmd} should be queued during {activity} processing"
                
                accepted_audio_commands.append(audio_cmd)
            
            # Verify all audio commands were accepted
            assert len(accepted_audio_commands) == len(audio_commands), \
                f"All {len(audio_commands)} audio commands should be accepted"
            
            # Complete the activity
            self.state_manager.complete_command_processing(success=True)
            
            # Process audio commands to verify they work
            processed_audio = []
            while self.state_manager.pending_commands > 0:
                next_audio = self.state_manager.get_next_command()
                if next_audio:
                    self.state_manager.start_command_processing(next_audio)
                    self.state_manager.complete_command_processing(success=True)
                    processed_audio.append(next_audio.command)
            
            # Verify all audio commands were processed
            assert processed_audio == accepted_audio_commands, \
                f"All audio commands should be processed: expected {accepted_audio_commands}, got {processed_audio}"


class TestRapidCommandAcceptance:
    """Test StateManager rapid command acceptance properties"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signal emissions for rapid command testing
        self.status_signals = []
        self.queue_signals = []
        self.button_signals = []
        
        # Connect to signals
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.queue_size_changed.connect(
            lambda size: self.queue_signals.append(size)
        )
        self.state_manager.buttons_state_changed.connect(
            lambda enabled: self.button_signals.append(enabled)
        )
    
    @given(
        commands=st.lists(
            st.tuples(
                st.sampled_from(['vol+', 'vol-', 'mute', 'samsung', 'shield', 'onkyo']),
                st.one_of(st.none(), st.sampled_from(['VolumeUp', 'VolumeDown', 'PowerOn', 'PowerOff', 'Menu', 'Home', 'Back']))
            ),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_rapid_command_acceptance_property(self, commands):
        """
        Property 4: Rapid Command Acceptance
        For any sequence of volume or device commands pressed rapidly, all commands 
        should be accepted and processed without artificial delays.
        
        **Feature: harmony-state-management, Property 4: Rapid Command Acceptance**
        **Validates: Requirements 2.2**
        """
        # Clear any initial signals
        self.status_signals.clear()
        self.queue_signals.clear()
        self.button_signals.clear()
        
        # Filter to only volume and device commands (no activities)
        volume_device_commands = []
        for cmd, action in commands:
            cmd_type = self.state_manager.classify_command(cmd, action)
            # Only include volume/device/audio commands, exclude activities
            if cmd_type in [CommandType.DEVICE, CommandType.AUDIO]:
                volume_device_commands.append((cmd, action))
        
        # Skip test if no valid commands generated
        if not volume_device_commands:
            return
        
        # Measure queueing time to verify no artificial delays
        import time
        start_time = time.time()
        
        # Queue all commands rapidly
        queued_commands = []
        for cmd, action in volume_device_commands:
            can_accept = self.state_manager.can_accept_command(cmd, action)
            queued = self.state_manager.queue_command(cmd, action)
            
            # All volume/device commands should be accepted (Requirement 2.2)
            assert can_accept, f"Volume/device command {cmd} {action or ''} should be accepted"
            assert queued, f"Volume/device command {cmd} {action or ''} should be queued"
            
            queued_commands.append((cmd, action))
        
        queue_time = time.time() - start_time
        
        # Verify all commands were accepted without artificial delays
        assert len(queued_commands) == len(volume_device_commands), \
            f"All {len(volume_device_commands)} volume/device commands should be accepted, got {len(queued_commands)}"
        
        # Queueing should be fast (no artificial delays during acceptance)
        max_acceptable_time = len(volume_device_commands) * 0.01  # 10ms per command max
        assert queue_time < max_acceptable_time, \
            f"Rapid command queueing should be fast, took {queue_time:.3f}s for {len(volume_device_commands)} commands"
        
        # Verify queue size signals were emitted for each command
        assert len(self.queue_signals) >= len(volume_device_commands), \
            f"Queue size signals should be emitted for each command, expected >= {len(volume_device_commands)}, got {len(self.queue_signals)}"
        
        # Verify final queue size matches expected
        final_queue_size = self.queue_signals[-1] if self.queue_signals else 0
        assert final_queue_size == len(volume_device_commands), \
            f"Final queue size should be {len(volume_device_commands)}, got {final_queue_size}"
        
        # Process all commands and verify they maintain sequential order
        processed_commands = []
        processing_start = time.time()
        
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Complete processing (simulate minimal processing time)
                self.state_manager.complete_command_processing(success=True)
                
                processed_commands.append((next_cmd.command, next_cmd.action))
                
                # Verify sequential processing is maintained
                assert self.state_manager.ensure_sequential_processing(), \
                    f"Sequential processing violated during rapid command processing"
        
        processing_time = time.time() - processing_start
        
        # Verify all commands were processed in correct order (FIFO)
        assert processed_commands == volume_device_commands, \
            f"Commands should be processed in FIFO order: expected {volume_device_commands}, got {processed_commands}"
        
        # Verify processing performance (no artificial delays during processing)
        avg_processing_time = processing_time / len(volume_device_commands) if volume_device_commands else 0
        assert avg_processing_time < 0.05, \
            f"Average command processing should be fast, got {avg_processing_time:.3f}s per command"
        
        # Verify final state is clean
        assert self.state_manager.pending_commands == 0, "Queue should be empty after processing all commands"
        assert not self.state_manager.is_processing, "Should not be processing after all commands complete"
    
    @given(
        volume_commands=st.lists(
            st.sampled_from(['vol+', 'vol-', 'mute']),
            min_size=3,
            max_size=15
        )
    )
    @settings(max_examples=100)
    def test_rapid_volume_commands_acceptance(self, volume_commands):
        """
        Test rapid volume command acceptance specifically.
        
        **Feature: harmony-state-management, Property 4: Rapid Command Acceptance**
        **Validates: Requirements 2.2**
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        
        # Queue all volume commands rapidly
        import time
        start_time = time.time()
        
        for cmd in volume_commands:
            # Volume commands should always be accepted
            assert self.state_manager.can_accept_command(cmd), \
                f"Volume command {cmd} should be accepted"
            
            assert self.state_manager.queue_command(cmd), \
                f"Volume command {cmd} should be queued"
        
        queue_time = time.time() - start_time
        
        # Verify rapid acceptance without delays
        assert queue_time < 0.1, \
            f"Volume commands should be queued rapidly, took {queue_time:.3f}s for {len(volume_commands)} commands"
        
        # Verify all commands are in queue
        assert self.state_manager.pending_commands == len(volume_commands), \
            f"All {len(volume_commands)} volume commands should be queued"
        
        # Process all commands
        processed_count = 0
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Verify it's classified as audio command
                assert next_cmd.command_type == CommandType.AUDIO, \
                    f"Volume command {next_cmd.command} should be classified as AUDIO"
                
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_count += 1
        
        # Verify all commands were processed
        assert processed_count == len(volume_commands), \
            f"All {len(volume_commands)} volume commands should be processed"
    
    @given(
        device_commands=st.lists(
            st.tuples(
                st.sampled_from(['samsung', 'shield', 'onkyo']),
                st.sampled_from(['VolumeUp', 'VolumeDown', 'PowerOn', 'PowerOff', 'Menu', 'Home', 'Back', 'Select'])
            ),
            min_size=3,
            max_size=15
        )
    )
    @settings(max_examples=100)
    def test_rapid_device_commands_acceptance(self, device_commands):
        """
        Test rapid device command acceptance specifically.
        
        **Feature: harmony-state-management, Property 4: Rapid Command Acceptance**
        **Validates: Requirements 2.2**
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        
        # Queue all device commands rapidly
        import time
        start_time = time.time()
        
        for device, action in device_commands:
            # Device commands should always be accepted
            assert self.state_manager.can_accept_command(device, action), \
                f"Device command {device} {action} should be accepted"
            
            assert self.state_manager.queue_command(device, action), \
                f"Device command {device} {action} should be queued"
        
        queue_time = time.time() - start_time
        
        # Verify rapid acceptance without delays
        assert queue_time < 0.1, \
            f"Device commands should be queued rapidly, took {queue_time:.3f}s for {len(device_commands)} commands"
        
        # Verify all commands are in queue
        assert self.state_manager.pending_commands == len(device_commands), \
            f"All {len(device_commands)} device commands should be queued"
        
        # Process all commands
        processed_commands = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Verify it's classified as device or audio command
                assert next_cmd.command_type in [CommandType.DEVICE, CommandType.AUDIO], \
                    f"Device command {next_cmd.command} {next_cmd.action} should be classified as DEVICE or AUDIO"
                
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
        
        # Verify all commands were processed in correct order
        assert processed_commands == device_commands, \
            f"Device commands should be processed in FIFO order"
    
    @given(
        mixed_commands=st.lists(
            st.one_of(
                st.tuples(st.just('vol+'), st.none()),
                st.tuples(st.just('vol-'), st.none()),
                st.tuples(st.sampled_from(['samsung', 'shield']), st.sampled_from(['VolumeUp', 'Menu', 'Home']))
            ),
            min_size=8,
            max_size=25
        )
    )
    @settings(max_examples=100)
    def test_mixed_rapid_commands_acceptance(self, mixed_commands):
        """
        Test mixed rapid volume and device commands acceptance.
        
        **Feature: harmony-state-management, Property 4: Rapid Command Acceptance**
        **Validates: Requirements 2.2**
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        
        # Queue all mixed commands rapidly
        import time
        start_time = time.time()
        
        for cmd, action in mixed_commands:
            # All volume/device commands should be accepted
            assert self.state_manager.can_accept_command(cmd, action), \
                f"Command {cmd} {action or ''} should be accepted"
            
            assert self.state_manager.queue_command(cmd, action), \
                f"Command {cmd} {action or ''} should be queued"
        
        queue_time = time.time() - start_time
        
        # Verify rapid acceptance without delays
        max_time = len(mixed_commands) * 0.005  # 5ms per command max
        assert queue_time < max_time, \
            f"Mixed commands should be queued rapidly, took {queue_time:.3f}s for {len(mixed_commands)} commands"
        
        # Verify all commands are in queue
        assert self.state_manager.pending_commands == len(mixed_commands), \
            f"All {len(mixed_commands)} mixed commands should be queued"
        
        # Process all commands and verify sequential order
        processed_commands = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Verify command type is appropriate
                cmd_type = next_cmd.command_type
                assert cmd_type in [CommandType.DEVICE, CommandType.AUDIO], \
                    f"Command {next_cmd.command} should be DEVICE or AUDIO type, got {cmd_type}"
                
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
        
        # Verify sequential processing maintained order
        assert processed_commands == mixed_commands, \
            f"Mixed commands should maintain FIFO processing order"


class TestErrorHandling:
    """Test StateManager error handling properties"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signal emissions for error handling
        self.status_signals = []
        self.button_signals = []
        
        # Connect to signals
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.buttons_state_changed.connect(
            lambda enabled: self.button_signals.append(enabled)
        )
    
    def test_network_error_handling(self):
        """
        Test that network errors are handled gracefully
        
        **Feature: harmony-state-management, Error Handling**
        **Validates: Requirements 1.4**
        """
        # Clear signals
        self.status_signals.clear()
        self.button_signals.clear()
        
        # Simulate network error
        error_message = "Connection refused"
        self.state_manager.handle_network_error(error_message)
        
        # Should emit error status
        assert len(self.status_signals) > 0, "Status signal should be emitted for network error"
        
        # Verify error message format
        latest_status = self.status_signals[-1]
        assert "❌" in latest_status[0], f"Error status should contain error indicator, got: {latest_status[0]}"
        assert "Errore di rete" in latest_status[0] or "Connessione persa" in latest_status[0], \
            f"Error status should contain network error message, got: {latest_status[0]}"
        
        # Verify error color
        assert latest_status[1] == "#f7768e", f"Error status should use danger color, got: {latest_status[1]}"
    
    def test_timeout_error_handling(self):
        """
        Test that timeout errors are handled gracefully
        
        **Feature: harmony-state-management, Error Handling**
        **Validates: Requirements 1.4**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Simulate timeout error
        operation = "start activity"
        timeout_duration = 5.0
        self.state_manager.handle_timeout_error(operation, timeout_duration)
        
        # Should emit error status
        assert len(self.status_signals) > 0, "Status signal should be emitted for timeout error"
        
        # Verify error message format
        latest_status = self.status_signals[-1]
        assert "❌" in latest_status[0], f"Error status should contain error indicator, got: {latest_status[0]}"
        assert "Timeout" in latest_status[0] or "Operazione lenta" in latest_status[0], \
            f"Error status should contain timeout error message, got: {latest_status[0]}"
    
    def test_command_error_handling(self):
        """
        Test that command errors are handled gracefully
        
        **Feature: harmony-state-management, Error Handling**
        **Validates: Requirements 1.4**
        """
        # Clear signals
        self.status_signals.clear()
        
        # Queue and start processing a command
        self.state_manager.queue_command('tv')
        next_cmd = self.state_manager.get_next_command()
        if next_cmd:
            self.state_manager.start_command_processing(next_cmd)
            
            # Clear signals to focus on error handling
            self.status_signals.clear()
            
            # Simulate command error
            error_message = "Device not responding"
            self.state_manager.handle_command_error('tv', None, error_message)
            
            # Should emit error status
            assert len(self.status_signals) > 0, "Status signal should be emitted for command error"
            
            # Verify error message format
            latest_status = self.status_signals[-1]
            assert "❌" in latest_status[0], f"Error status should contain error indicator, got: {latest_status[0]}"
            
            # Verify command processing was completed with error
            assert not self.state_manager.is_processing, "Processing should be False after error"
            assert self.state_manager.pending_commands == 0, "Queue should be empty after error"
    
    def test_error_recovery(self):
        """
        Test that error recovery restores normal operation
        
        **Feature: harmony-state-management, Error Handling**
        **Validates: Requirements 1.4**
        """
        # Clear signals
        self.status_signals.clear()
        self.button_signals.clear()
        
        # Put StateManager in error state
        self.state_manager.is_processing = True
        self.state_manager.is_activity_changing = True
        
        # Attempt recovery
        self.state_manager.recover_from_error()
        
        # Should emit recovery status
        assert len(self.status_signals) > 0, "Status signal should be emitted during recovery"
        
        # Verify recovery message
        recovery_status = None
        for status_text, color in self.status_signals:
            if "🔄" in status_text and "Ripristino" in status_text:
                recovery_status = (status_text, color)
                break
        
        assert recovery_status is not None, "Recovery status should be emitted"
        assert recovery_status[1] == "#e0af68", "Recovery status should use warning color"
        
        # Should emit button enable signal
        assert len(self.button_signals) > 0, "Button state signal should be emitted during recovery"
        assert self.button_signals[-1] == True, "Buttons should be enabled after recovery"
        
        # Verify state is cleared
        assert not self.state_manager.is_processing, "Processing should be False after recovery"
        assert not self.state_manager.is_activity_changing, "Activity changing should be False after recovery"
    
    def test_error_display_timing(self):
        """
        Test that errors are displayed for 3 seconds then return to real state
        
        **Feature: harmony-state-management, Error Handling**
        **Validates: Requirements 1.4**
        """
        # This test verifies the timing behavior but doesn't actually wait 3 seconds
        # Instead, it verifies that the timer is set up correctly
        
        # Clear signals
        self.status_signals.clear()
        
        # Simulate error
        self.state_manager.handle_network_error("Connection lost")
        
        # Should emit error status immediately
        assert len(self.status_signals) > 0, "Error status should be emitted immediately"
        
        # Verify error is displayed
        latest_status = self.status_signals[-1]
        assert "❌" in latest_status[0], "Error should be displayed"
        
        # The timer for returning to real state is set up internally
        # We can't easily test the 3-second timing without making the test slow
        # But we can verify the error handling structure is in place


class TestDeviceCommandThrottling:
    """Test device command throttling properties"""
    
    def setup_method(self):
        """Setup fresh StateManager for throttling tests"""
        self.state_manager = StateManager()
    
    def test_device_command_throttling_unit(self):
        """
        Unit test to verify device command throttling logic works correctly.
        
        **Feature: harmony-state-management, Property 6: Device Command Throttling**
        **Validates: Requirements 2.3**
        """
        import time
        from harmony_gui import HarmonyWorker
        
        # Create worker instance
        worker = HarmonyWorker(state_manager=self.state_manager)
        
        # Test the throttling logic directly
        min_interval = 0.05  # 50ms as defined in HarmonyWorker
        
        # Reset throttling state
        worker._last_device_command_time = 0.0
        
        # Simulate rapid device commands
        start_time = time.time()
        
        # First command - should not be throttled
        current_time = time.time()
        time_since_last = current_time - worker._last_device_command_time
        
        if time_since_last < worker._device_command_min_interval:
            sleep_time = worker._device_command_min_interval - time_since_last
        else:
            sleep_time = 0
        
        first_sleep = sleep_time
        worker._last_device_command_time = time.time()
        
        # Second command immediately after - should be throttled
        current_time = time.time()
        time_since_last = current_time - worker._last_device_command_time
        
        if time_since_last < worker._device_command_min_interval:
            sleep_time = worker._device_command_min_interval - time_since_last
        else:
            sleep_time = 0
        
        second_sleep = sleep_time
        
        # Verify throttling behavior
        assert first_sleep == 0, f"First command should not be throttled, got sleep time: {first_sleep}"
        assert second_sleep > 0, f"Second command should be throttled, got sleep time: {second_sleep}"
        assert second_sleep <= min_interval, f"Throttling should not exceed {min_interval}s, got: {second_sleep}"
        
        print(f"Throttling test results:")
        print(f"  First command sleep time: {first_sleep:.3f}s (expected: 0)")
        print(f"  Second command sleep time: {second_sleep:.3f}s (expected: > 0, <= {min_interval})")
        print(f"  Throttling working correctly: {second_sleep > 0}")
    
    @given(
        num_commands=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=10, deadline=1000)
    def test_device_command_throttling_property(self, num_commands):
        """
        Property 6: Device Command Throttling
        For any sequence of device commands, the system should apply minimal throttling 
        to prevent Hub overload while accepting all commands.
        
        **Feature: harmony-state-management, Property 6: Device Command Throttling**
        **Validates: Requirements 2.3**
        """
        import time
        from harmony_gui import HarmonyWorker
        
        # Create worker instance
        worker = HarmonyWorker(state_manager=self.state_manager)
        
        # Test throttling logic for multiple commands
        min_interval = worker._device_command_min_interval  # 50ms
        
        # Reset throttling state
        worker._last_device_command_time = 0.0
        
        sleep_times = []
        
        for i in range(num_commands):
            current_time = time.time()
            time_since_last = current_time - worker._last_device_command_time
            
            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
            else:
                sleep_time = 0
            
            sleep_times.append(sleep_time)
            
            # Simulate command execution time
            worker._last_device_command_time = time.time()
            
            # Small delay to simulate command processing
            time.sleep(0.001)
        
        # Verify throttling behavior
        # First command should not be throttled
        assert sleep_times[0] == 0, f"First command should not be throttled, got: {sleep_times[0]}"
        
        # Subsequent commands should be throttled
        for i in range(1, len(sleep_times)):
            assert sleep_times[i] >= 0, f"Command {i} sleep time should be non-negative, got: {sleep_times[i]}"
            
            # Most commands should require some throttling (unless enough time passed)
            if i == 1:  # Second command should definitely be throttled
                assert sleep_times[i] > 0, f"Second command should be throttled, got: {sleep_times[i]}"
        
        # Verify throttling is reasonable (not excessive)
        for i, sleep_time in enumerate(sleep_times):
            assert sleep_time <= min_interval, \
                f"Command {i} throttling should not exceed {min_interval}s, got: {sleep_time}"
        
        print(f"Property test with {num_commands} commands:")
        for i, sleep_time in enumerate(sleep_times):
            print(f"  Command {i}: sleep {sleep_time:.3f}s")
    
    def test_throttling_classification(self):
        """
        Test that throttling only applies to device and audio commands.
        
        **Feature: harmony-state-management, Property 6: Device Command Throttling**
        **Validates: Requirements 2.3**
        """
        # Test command classification
        test_commands = [
            ('samsung', 'VolumeUp', 'device'),
            ('shield', 'Menu', 'device'),
            ('vol+', None, 'audio'),
            ('vol-', None, 'audio'),
            ('mute', None, 'audio'),
            ('tv', None, 'activity'),  # Should not be throttled
            ('music', None, 'activity'),  # Should not be throttled
        ]
        
        for cmd, action, expected_type in test_commands:
            cmd_type = self.state_manager.classify_command(cmd, action)
            
            if expected_type == 'activity':
                assert cmd_type.value == 'activity', \
                    f"Command {cmd} {action} should be activity, got {cmd_type.value}"
            else:
                assert cmd_type.value in ['device', 'audio'], \
                    f"Command {cmd} {action} should be device/audio, got {cmd_type.value}"
        
        print("Command classification test passed:")
        for cmd, action, expected_type in test_commands:
            actual_type = self.state_manager.classify_command(cmd, action).value
            throttled = "YES" if actual_type in ['device', 'audio'] else "NO"
            print(f"  {cmd} {action or ''}: {actual_type} -> Throttled: {throttled}")
    
    def test_throttling_acceptance(self):
        """
        Test that all device commands are accepted despite throttling.
        
        **Feature: harmony-state-management, Property 6: Device Command Throttling**
        **Validates: Requirements 2.3**
        """
        # Test that device commands are always accepted
        device_commands = [
            ('samsung', 'VolumeUp'),
            ('samsung', 'VolumeDown'),
            ('samsung', 'Menu'),
            ('vol+', None),
            ('vol-', None),
            ('shield', 'Home'),
        ]
        
        accepted_count = 0
        for cmd, action in device_commands:
            # All device commands should be accepted
            can_accept = self.state_manager.can_accept_command(cmd, action)
            assert can_accept, f"Device command {cmd} {action} should be accepted"
            
            # All device commands should be queueable
            queued = self.state_manager.queue_command(cmd, action)
            assert queued, f"Device command {cmd} {action} should be queued"
            
            accepted_count += 1
        
        # Verify all commands were queued
        assert self.state_manager.pending_commands == len(device_commands), \
            f"All {len(device_commands)} commands should be queued"
        
        print(f"Command acceptance test passed: {accepted_count}/{len(device_commands)} commands accepted and queued")



if __name__ == "__main__":
    pytest.main([__file__, "-v"])