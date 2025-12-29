#!/usr/bin/env python3
"""
Integration tests for Harmony State Management system
Tests complete system with rapid button presses and state consistency under load
Feature: harmony-state-management
"""

import pytest
import time
import asyncio
import threading
from unittest.mock import Mock, patch, AsyncMock
from PyQt6.QtCore import QCoreApplication, QTimer, QThread
from PyQt6.QtTest import QTest
import sys

from state_manager import StateManager, CommandType
from harmony_gui import HarmonyWorker, GUI

# Ensure QApplication exists for Qt signals
if not QCoreApplication.instance():
    app = QCoreApplication(sys.argv)


class TestRapidButtonPresses:
    """Test system behavior with rapid button presses"""
    
    def setup_method(self):
        """Setup fresh components for each test"""
        self.state_manager = StateManager()
        
        # Mock the FastHarmonyHub to avoid actual network calls
        self.mock_hub = AsyncMock()
        self.mock_hub.connect = AsyncMock()
        self.mock_hub.close = AsyncMock()
        self.mock_hub.start_activity_fast = AsyncMock(return_value={"result": "success"})
        self.mock_hub.send_device_fast = AsyncMock(return_value={"result": "success"})
        self.mock_hub.get_current_fast = AsyncMock(return_value={"data": {"result": "-1"}})
        
        # Create worker with mocked hub
        self.worker = HarmonyWorker(state_manager=self.state_manager)
        
        # Track all signals for verification
        self.status_signals = []
        self.button_signals = []
        self.queue_signals = []
        self.activity_signals = []
        
        # Connect to all StateManager signals
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
    
    def test_rapid_volume_commands_acceptance(self):
        """
        Test that rapid volume commands are all accepted and processed sequentially
        Requirements: 1.1 (sequential processing), 2.2 (rapid command acceptance)
        """
        # Clear any initial signals
        self.status_signals.clear()
        self.button_signals.clear()
        self.queue_signals.clear()
        
        # Simulate rapid volume button presses (10 commands in quick succession)
        volume_commands = ['vol+', 'vol+', 'vol-', 'vol+', 'vol-', 'vol-', 'vol+', 'vol+', 'vol-', 'vol+']
        
        # Queue all commands rapidly
        queued_count = 0
        for cmd in volume_commands:
            if self.state_manager.queue_command(cmd):
                queued_count += 1
        
        # All volume commands should be accepted (Requirement 2.2)
        assert queued_count == len(volume_commands), \
            f"All {len(volume_commands)} volume commands should be accepted, got {queued_count}"
        
        # Verify queue size signals were emitted for each command
        assert len(self.queue_signals) >= len(volume_commands), \
            f"Queue size signals should be emitted for each command, expected >= {len(volume_commands)}, got {len(self.queue_signals)}"
        
        # Verify final queue size matches expected
        final_queue_size = self.queue_signals[-1] if self.queue_signals else 0
        assert final_queue_size == len(volume_commands), \
            f"Final queue size should be {len(volume_commands)}, got {final_queue_size}"
        
        # Process all commands sequentially and verify order
        processed_commands = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Verify sequential processing order (FIFO)
                processed_commands.append(next_cmd.command)
                
                # Start and complete processing
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                
                # Verify sequential processing is maintained
                assert self.state_manager.ensure_sequential_processing(), \
                    f"Sequential processing order violated after processing {next_cmd.command}"
        
        # Verify all commands were processed in correct order (FIFO)
        assert processed_commands == volume_commands, \
            f"Commands should be processed in FIFO order: expected {volume_commands}, got {processed_commands}"
        
        # Verify final state is clean
        assert self.state_manager.pending_commands == 0, "Queue should be empty after processing all commands"
        assert not self.state_manager.is_processing, "Should not be processing after all commands complete"
    
    def test_rapid_device_commands_with_throttling(self):
        """
        Test that rapid device commands are accepted with minimal throttling
        Requirements: 2.3 (device command throttling), 1.1 (sequential processing)
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        
        # Simulate rapid device commands (Samsung TV commands)
        device_commands = [
            ('samsung', 'PowerOn'),
            ('samsung', 'VolumeUp'),
            ('samsung', 'VolumeDown'),
            ('samsung', 'ChannelUp'),
            ('samsung', 'ChannelDown'),
            ('samsung', 'Menu'),
            ('samsung', 'Home'),
            ('samsung', 'Back')
        ]
        
        # Queue all commands rapidly
        start_time = time.time()
        queued_count = 0
        for device, action in device_commands:
            if self.state_manager.queue_command(device, action):
                queued_count += 1
        end_time = time.time()
        
        # All device commands should be accepted (Requirement 2.3)
        assert queued_count == len(device_commands), \
            f"All {len(device_commands)} device commands should be accepted, got {queued_count}"
        
        # Queueing should be fast (no artificial delays during queueing)
        queue_time = end_time - start_time
        assert queue_time < 0.1, \
            f"Queueing {len(device_commands)} commands should be fast, took {queue_time:.3f}s"
        
        # Verify all commands are classified as device commands
        for device, action in device_commands:
            cmd_type = self.state_manager.classify_command(device, action)
            assert cmd_type == CommandType.DEVICE, \
                f"Command {device} {action} should be classified as DEVICE, got {cmd_type}"
        
        # Process commands and verify sequential order
        processed_commands = []
        processing_times = []
        
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                process_start = time.time()
                
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Simulate minimal processing time (throttling should be minimal)
                time.sleep(0.01)  # 10ms simulated processing
                
                # Complete processing
                self.state_manager.complete_command_processing(success=True)
                
                process_end = time.time()
                processing_times.append(process_end - process_start)
                processed_commands.append((next_cmd.command, next_cmd.action))
        
        # Verify sequential processing order
        assert processed_commands == device_commands, \
            f"Device commands should be processed in FIFO order: expected {device_commands}, got {processed_commands}"
        
        # Verify processing times are reasonable (minimal throttling)
        avg_processing_time = sum(processing_times) / len(processing_times)
        assert avg_processing_time < 0.1, \
            f"Average processing time should be minimal, got {avg_processing_time:.3f}s"
    
    def test_mixed_rapid_commands_sequential_processing(self):
        """
        Test mixed rapid commands (activities, devices, audio) maintain sequential processing
        Requirements: 1.1 (sequential processing), 2.1 (activity blocking)
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        self.activity_signals.clear()
        
        # Mixed command sequence: activity, devices, audio, blocked activity, more devices
        mixed_commands = [
            ('tv', None),           # Activity command (should be accepted)
            ('samsung', 'VolumeUp'), # Device command (should be accepted)
            ('vol+', None),         # Audio command (should be accepted)
            ('music', None),        # Activity command (should be BLOCKED)
            ('samsung', 'Menu'),    # Device command (should be accepted)
            ('vol-', None),         # Audio command (should be accepted)
            ('shield', None),       # Activity command (should be BLOCKED)
            ('samsung', 'Home')     # Device command (should be accepted)
        ]
        
        # Queue commands and track which ones are accepted
        accepted_commands = []
        blocked_commands = []
        
        for cmd, action in mixed_commands:
            if self.state_manager.queue_command(cmd, action):
                accepted_commands.append((cmd, action))
            else:
                blocked_commands.append((cmd, action))
        
        # Verify activity blocking behavior (Requirement 2.1)
        # First activity should be accepted, subsequent activities should be blocked
        expected_accepted = [
            ('tv', None),           # First activity - accepted
            ('samsung', 'VolumeUp'), # Device - accepted
            ('vol+', None),         # Audio - accepted
            ('samsung', 'Menu'),    # Device - accepted
            ('vol-', None),         # Audio - accepted
            ('samsung', 'Home')     # Device - accepted
        ]
        expected_blocked = [
            ('music', None),        # Activity blocked
            ('shield', None)        # Activity blocked
        ]
        
        assert accepted_commands == expected_accepted, \
            f"Expected accepted commands: {expected_accepted}, got {accepted_commands}"
        assert blocked_commands == expected_blocked, \
            f"Expected blocked commands: {expected_blocked}, got {blocked_commands}"
        
        # Process accepted commands sequentially
        processed_commands = []
        activity_started = False
        
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Track if activity command started
                if next_cmd.command_type == CommandType.ACTIVITY:
                    activity_started = True
                    # Verify activity state signals
                    assert True in self.activity_signals, \
                        "Activity state signal should be emitted when activity starts"
                
                # Complete processing
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
                
                # Verify sequential processing order is maintained
                assert self.state_manager.ensure_sequential_processing(), \
                    f"Sequential processing violated after {next_cmd.command}"
        
        # Verify all accepted commands were processed in correct order
        assert processed_commands == expected_accepted, \
            f"Processed commands should match accepted commands in order: expected {expected_accepted}, got {processed_commands}"
        
        # Verify activity was properly managed
        assert activity_started, "Activity command should have been processed"
        assert False in self.activity_signals, \
            "Activity state should be cleared after activity completes"
    
    def test_state_consistency_under_load(self):
        """
        Test state consistency when system is under heavy load with rapid commands
        Requirements: 1.1, 1.2, 1.3 (state consistency under load)
        """
        # Clear signals
        self.status_signals.clear()
        self.queue_signals.clear()
        self.button_signals.clear()
        self.activity_signals.clear()
        
        # Generate a large number of mixed commands to simulate load
        load_commands = []
        
        # Add volume commands (should all be accepted)
        for i in range(20):
            load_commands.append(('vol+' if i % 2 == 0 else 'vol-', None))
        
        # Add device commands (should all be accepted)
        device_actions = ['VolumeUp', 'VolumeDown', 'Menu', 'Home', 'Back']
        for i in range(15):
            action = device_actions[i % len(device_actions)]
            load_commands.append(('samsung', action))
        
        # Add one activity command (should be accepted)
        load_commands.insert(10, ('tv', None))  # Insert in middle
        
        # Add more activity commands (should be blocked)
        load_commands.append(('music', None))
        load_commands.append(('shield', None))
        
        # Queue all commands rapidly
        start_time = time.time()
        accepted_count = 0
        blocked_count = 0
        
        for cmd, action in load_commands:
            if self.state_manager.queue_command(cmd, action):
                accepted_count += 1
            else:
                blocked_count += 1
        
        queue_time = time.time() - start_time
        
        # Verify queueing performance under load
        assert queue_time < 0.5, \
            f"Queueing {len(load_commands)} commands should be fast even under load, took {queue_time:.3f}s"
        
        # Verify expected acceptance/blocking behavior
        expected_accepted = len(load_commands) - 2  # All except 2 blocked activities
        assert accepted_count == expected_accepted, \
            f"Expected {expected_accepted} accepted commands, got {accepted_count}"
        assert blocked_count == 2, \
            f"Expected 2 blocked commands, got {blocked_count}"
        
        # Verify state consistency during queueing
        final_queue_size = self.state_manager.pending_commands
        assert final_queue_size == accepted_count, \
            f"Queue size ({final_queue_size}) should match accepted commands ({accepted_count})"
        
        # Process all commands and verify state consistency throughout
        processed_count = 0
        max_queue_size = final_queue_size
        
        while self.state_manager.pending_commands > 0:
            # Verify state consistency before processing
            state_info = self.state_manager.get_state_info()
            
            # Queue length should match pending commands
            assert state_info['queue_length'] == state_info['pending_commands'], \
                f"Queue length inconsistency: {state_info['queue_length']} != {state_info['pending_commands']}"
            
            # UI state should be consistent
            assert state_info['ui_state']['pending_count'] == state_info['pending_commands'], \
                f"UI pending count inconsistency: {state_info['ui_state']['pending_count']} != {state_info['pending_commands']}"
            
            # Get and process next command
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                
                # Verify processing state consistency
                assert self.state_manager.is_processing, "Should be processing when command is active"
                
                # Complete processing
                self.state_manager.complete_command_processing(success=True)
                processed_count += 1
                
                # Verify sequential processing order is maintained
                assert self.state_manager.ensure_sequential_processing(), \
                    f"Sequential processing violated during load test at command {processed_count}"
        
        # Verify all accepted commands were processed
        assert processed_count == accepted_count, \
            f"All accepted commands should be processed: expected {accepted_count}, got {processed_count}"
        
        # Verify final state is clean
        final_state = self.state_manager.get_state_info()
        assert final_state['pending_commands'] == 0, "Queue should be empty after processing"
        assert not final_state['is_processing'], "Should not be processing after completion"
        assert not final_state['is_activity_changing'], "Activity changing should be cleared"
        
        # Verify signal consistency
        if self.queue_signals:
            assert self.queue_signals[-1] == 0, "Final queue signal should indicate empty queue"


class TestActivityAndDeviceScenarios:
    """Test all activity and device command scenarios"""
    
    def setup_method(self):
        """Setup fresh components for each test"""
        self.state_manager = StateManager()
        
        # Track signals
        self.status_signals = []
        self.button_signals = []
        self.activity_signals = []
        
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.buttons_state_changed.connect(
            lambda enabled: self.button_signals.append(enabled)
        )
        self.state_manager.activity_state_changed.connect(
            lambda active: self.activity_signals.append(active)
        )
    
    def test_all_activity_commands_blocking(self):
        """
        Test that all activity commands properly block subsequent activities
        Requirements: 2.1 (activity blocking), 4.3 (button state management)
        """
        # Test each activity type
        activities = ['tv', 'music', 'shield', 'off']
        
        for primary_activity in activities:
            # Clear state and signals
            self.state_manager = StateManager()
            self.status_signals.clear()
            self.button_signals.clear()
            self.activity_signals.clear()
            
            # Reconnect signals
            self.state_manager.status_changed.connect(
                lambda text, color: self.status_signals.append((text, color))
            )
            self.state_manager.buttons_state_changed.connect(
                lambda enabled: self.button_signals.append(enabled)
            )
            self.state_manager.activity_state_changed.connect(
                lambda active: self.activity_signals.append(active)
            )
            
            # Queue primary activity
            assert self.state_manager.queue_command(primary_activity), \
                f"Primary activity {primary_activity} should be accepted"
            
            # Start processing primary activity
            next_cmd = self.state_manager.get_next_command()
            assert next_cmd is not None, f"Should have command to process for {primary_activity}"
            assert next_cmd.command_type == CommandType.ACTIVITY, \
                f"Command {primary_activity} should be classified as ACTIVITY"
            
            self.state_manager.start_command_processing(next_cmd)
            
            # Verify activity blocking state is active
            assert self.state_manager.is_activity_changing, \
                f"Activity changing should be True when processing {primary_activity}"
            
            # Verify button disable signal was emitted (Requirement 4.3)
            assert False in self.button_signals, \
                f"Button disable signal should be emitted for activity {primary_activity}"
            
            # Verify activity state signal was emitted
            assert True in self.activity_signals, \
                f"Activity state signal should be emitted for activity {primary_activity}"
            
            # Try to queue other activities - they should all be blocked
            other_activities = [act for act in activities if act != primary_activity]
            for blocked_activity in other_activities:
                assert not self.state_manager.can_accept_command(blocked_activity), \
                    f"Activity {blocked_activity} should be blocked when {primary_activity} is in progress"
                
                assert not self.state_manager.queue_command(blocked_activity), \
                    f"Activity {blocked_activity} should not be queued when {primary_activity} is in progress"
            
            # Device commands should still be accepted
            assert self.state_manager.can_accept_command('samsung', 'VolumeUp'), \
                f"Device commands should be accepted when {primary_activity} is in progress"
            assert self.state_manager.queue_command('samsung', 'VolumeUp'), \
                f"Device commands should be queued when {primary_activity} is in progress"
            
            # Audio commands should still be accepted
            assert self.state_manager.can_accept_command('vol+'), \
                f"Audio commands should be accepted when {primary_activity} is in progress"
            assert self.state_manager.queue_command('vol+'), \
                f"Audio commands should be queued when {primary_activity} is in progress"
            
            # Complete the primary activity
            self.state_manager.complete_command_processing(success=True)
            
            # Verify activity blocking is cleared
            assert not self.state_manager.is_activity_changing, \
                f"Activity changing should be False after {primary_activity} completes"
            
            # Verify button enable signal was emitted
            assert True in self.button_signals, \
                f"Button enable signal should be emitted after {primary_activity} completes"
            
            # Verify activity state cleared signal was emitted
            assert False in self.activity_signals, \
                f"Activity state cleared signal should be emitted after {primary_activity} completes"
            
            # Now other activities should be accepted again
            for other_activity in other_activities[:1]:  # Test one to avoid too many iterations
                assert self.state_manager.can_accept_command(other_activity), \
                    f"Activity {other_activity} should be accepted after {primary_activity} completes"
    
    def test_all_device_command_types(self):
        """
        Test all types of device commands are properly classified and processed
        Requirements: 3.4 (command classification), 2.2 (rapid acceptance)
        """
        # Test different device command patterns
        device_commands = [
            # Samsung TV commands
            ('samsung', 'PowerOn'),
            ('samsung', 'PowerOff'),
            ('samsung', 'VolumeUp'),
            ('samsung', 'VolumeDown'),
            ('samsung', 'ChannelUp'),
            ('samsung', 'ChannelDown'),
            ('samsung', 'Menu'),
            ('samsung', 'Home'),
            ('samsung', 'Back'),
            ('samsung', 'Select'),
            ('samsung', 'DirectionUp'),
            ('samsung', 'DirectionDown'),
            ('samsung', 'DirectionLeft'),
            ('samsung', 'DirectionRight'),
            
            # Shield commands
            ('shield', 'Home'),
            ('shield', 'Back'),
            ('shield', 'Select'),
            ('shield', 'Menu'),
            
            # Audio device commands
            ('onkyo', 'PowerOn'),
            ('onkyo', 'PowerOff'),
            ('onkyo', 'VolumeUp'),
            ('onkyo', 'VolumeDown'),
            
            # Smart commands (should be classified as device)
            ('smart_DirectionUp', 'DirectionUp'),
            ('smart_DirectionDown', 'DirectionDown'),
            ('smart_Select', 'Select'),
            ('smart_Home', 'Home'),
        ]
        
        # Test classification
        for device, action in device_commands:
            cmd_type = self.state_manager.classify_command(device, action)
            
            # All should be classified as DEVICE or AUDIO (not ACTIVITY)
            assert cmd_type in [CommandType.DEVICE, CommandType.AUDIO], \
                f"Command {device} {action} should be classified as DEVICE or AUDIO, got {cmd_type}"
            
            # Should be accepted (not blocked)
            assert self.state_manager.can_accept_command(device, action), \
                f"Device command {device} {action} should be accepted"
        
        # Test rapid acceptance - queue all commands quickly
        start_time = time.time()
        queued_count = 0
        
        for device, action in device_commands:
            if self.state_manager.queue_command(device, action):
                queued_count += 1
        
        queue_time = time.time() - start_time
        
        # All device commands should be accepted rapidly
        assert queued_count == len(device_commands), \
            f"All {len(device_commands)} device commands should be accepted, got {queued_count}"
        
        assert queue_time < 0.1, \
            f"Queueing {len(device_commands)} device commands should be fast, took {queue_time:.3f}s"
        
        # Verify queue size
        assert self.state_manager.pending_commands == len(device_commands), \
            f"Queue should contain all {len(device_commands)} commands"
    
    def test_audio_command_classification(self):
        """
        Test audio commands are properly classified and handled
        Requirements: 3.4 (command classification), 2.2 (rapid acceptance)
        """
        # Test different audio command patterns
        audio_commands = [
            # Direct audio commands
            ('vol+', None),
            ('vol-', None),
            ('mute', None),
            
            # Audio device power commands
            ('audio-on', None),
            ('audio-off', None),
            
            # Onkyo-specific commands (if available)
            ('onkyo', 'PowerOn'),
            ('onkyo', 'VolumeUp'),
            ('onkyo', 'VolumeDown'),
        ]
        
        # Test classification and acceptance
        for cmd, action in audio_commands:
            cmd_type = self.state_manager.classify_command(cmd, action)
            
            # Should be classified as AUDIO or DEVICE (audio devices)
            assert cmd_type in [CommandType.AUDIO, CommandType.DEVICE], \
                f"Audio command {cmd} {action} should be classified as AUDIO or DEVICE, got {cmd_type}"
            
            # Should be accepted rapidly
            assert self.state_manager.can_accept_command(cmd, action), \
                f"Audio command {cmd} {action} should be accepted"
            
            assert self.state_manager.queue_command(cmd, action), \
                f"Audio command {cmd} {action} should be queued"
        
        # Verify all audio commands were queued
        assert self.state_manager.pending_commands == len(audio_commands), \
            f"All {len(audio_commands)} audio commands should be queued"
        
        # Process commands and verify they maintain sequential order
        processed_commands = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
        
        # Verify sequential processing
        assert len(processed_commands) == len(audio_commands), \
            f"All audio commands should be processed: expected {len(audio_commands)}, got {len(processed_commands)}"
        
        assert processed_commands == audio_commands, \
            f"Audio commands should be processed in FIFO order: expected {audio_commands}, got {processed_commands}"


class TestErrorHandlingIntegration:
    """Test error handling in integration scenarios"""
    
    def setup_method(self):
        """Setup fresh components for each test"""
        self.state_manager = StateManager()
        
        # Track error-related signals
        self.status_signals = []
        self.button_signals = []
        
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.buttons_state_changed.connect(
            lambda enabled: self.button_signals.append(enabled)
        )
    
    def test_error_recovery_during_rapid_commands(self):
        """
        Test error recovery when errors occur during rapid command processing
        Requirements: 1.4 (error handling)
        """
        # Clear signals
        self.status_signals.clear()
        self.button_signals.clear()
        
        # Queue several commands
        commands = [('tv', None), ('samsung', 'VolumeUp'), ('vol+', None), ('samsung', 'Menu')]
        
        for cmd, action in commands:
            self.state_manager.queue_command(cmd, action)
        
        # Process first command successfully
        next_cmd = self.state_manager.get_next_command()
        self.state_manager.start_command_processing(next_cmd)
        self.state_manager.complete_command_processing(success=True)
        
        # Process second command with error
        next_cmd = self.state_manager.get_next_command()
        self.state_manager.start_command_processing(next_cmd)
        
        # Clear signals to focus on error handling
        self.status_signals.clear()
        
        # Simulate command error
        error_message = "Device not responding"
        self.state_manager.handle_command_error(next_cmd.command, next_cmd.action, error_message)
        
        # Verify error status was emitted
        assert len(self.status_signals) > 0, "Error status should be emitted"
        
        # Find error status signal
        error_status = None
        for status_text, color in self.status_signals:
            if "❌" in status_text:
                error_status = (status_text, color)
                break
        
        assert error_status is not None, "Error status signal should be found"
        # Error handling shows user-friendly messages, not raw error messages
        assert "❌" in error_status[0], f"Error status should contain error indicator: {error_status[0]}"
        assert error_status[1] == "#f7768e", "Error status should use danger color"
        
        # Verify processing state was cleared
        assert not self.state_manager.is_processing, "Processing should be cleared after error"
        
        # Verify remaining commands can still be processed
        remaining_commands = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                remaining_commands.append((next_cmd.command, next_cmd.action))
        
        # Should have processed remaining commands
        expected_remaining = [('vol+', None), ('samsung', 'Menu')]
        assert remaining_commands == expected_remaining, \
            f"Remaining commands should be processed after error: expected {expected_remaining}, got {remaining_commands}"
    
    def test_network_error_during_activity_change(self):
        """
        Test network error handling during activity change
        Requirements: 1.4 (error handling), 4.3 (button state recovery)
        """
        # Clear signals
        self.status_signals.clear()
        self.button_signals.clear()
        
        # Start activity change
        self.state_manager.queue_command('tv')
        next_cmd = self.state_manager.get_next_command()
        self.state_manager.start_command_processing(next_cmd)
        
        # Verify activity change state
        assert self.state_manager.is_activity_changing, "Activity should be changing"
        assert False in self.button_signals, "Buttons should be disabled during activity change"
        
        # Clear signals to focus on error handling
        self.status_signals.clear()
        self.button_signals.clear()
        
        # Simulate network error
        self.state_manager.handle_network_error("Connection lost")
        
        # Verify error handling
        assert len(self.status_signals) > 0, "Network error status should be emitted"
        
        # Find network error status
        network_error_status = None
        for status_text, color in self.status_signals:
            if "❌" in status_text and ("Connessione" in status_text or "rete" in status_text):
                network_error_status = (status_text, color)
                break
        
        assert network_error_status is not None, "Network error status should be found"
        
        # Verify state was cleared
        assert not self.state_manager.is_processing, "Processing should be cleared after network error"
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared after network error"
        
        # Verify buttons were re-enabled (recovery)
        # The handle_network_error should complete command processing, which should re-enable buttons
        final_state = self.state_manager.get_state_info()
        assert final_state['ui_state']['buttons_enabled'], "Buttons should be re-enabled after error recovery"
    
    def test_timeout_error_recovery(self):
        """
        Test timeout error handling and recovery
        Requirements: 1.4 (error handling)
        """
        # Clear signals
        self.status_signals.clear()
        
        # Start command processing
        self.state_manager.queue_command('tv')
        next_cmd = self.state_manager.get_next_command()
        self.state_manager.start_command_processing(next_cmd)
        
        # Clear signals to focus on timeout handling
        self.status_signals.clear()
        
        # Simulate timeout error
        operation = "start activity"
        timeout_duration = 5.0
        self.state_manager.handle_timeout_error(operation, timeout_duration)
        
        # Verify timeout error status was emitted
        assert len(self.status_signals) > 0, "Timeout error status should be emitted"
        
        # Find timeout error status
        timeout_status = None
        for status_text, color in self.status_signals:
            if "❌" in status_text and ("Timeout" in status_text or "lenta" in status_text):
                timeout_status = (status_text, color)
                break
        
        assert timeout_status is not None, f"Timeout error status should be found in: {self.status_signals}"
        
        # Verify state consistency after timeout
        final_state = self.state_manager.get_state_info()
        assert not final_state['is_processing'], "Processing should be cleared after timeout"
        assert final_state['pending_commands'] == 0, "Queue should be cleared after timeout error"
    
    def test_error_recovery_method(self):
        """
        Test the explicit error recovery method
        Requirements: 1.4 (error handling)
        """
        # Clear signals
        self.status_signals.clear()
        self.button_signals.clear()
        
        # Put system in error state
        self.state_manager.is_processing = True
        self.state_manager.is_activity_changing = True
        
        # Call recovery method
        self.state_manager.recover_from_error()
        
        # Verify recovery status was emitted
        recovery_status = None
        for status_text, color in self.status_signals:
            if "🔄" in status_text and "Ripristino" in status_text:
                recovery_status = (status_text, color)
                break
        
        assert recovery_status is not None, "Recovery status should be emitted"
        assert recovery_status[1] == "#e0af68", "Recovery status should use warning color"
        
        # Verify button enable signal was emitted
        assert True in self.button_signals, "Button enable signal should be emitted during recovery"
        
        # Verify state was cleared
        assert not self.state_manager.is_processing, "Processing should be cleared after recovery"
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared after recovery"


class TestEndToEndRapidCommandScenarios:
    """End-to-end integration tests for rapid command scenarios"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track all signals for comprehensive verification
        self.all_signals = []
        
        # Connect to all signals with timestamps for detailed analysis
        self.state_manager.status_changed.connect(
            lambda text, color: self.all_signals.append(('status', time.time(), text, color))
        )
        self.state_manager.buttons_state_changed.connect(
            lambda enabled: self.all_signals.append(('buttons', time.time(), enabled))
        )
        self.state_manager.queue_size_changed.connect(
            lambda size: self.all_signals.append(('queue', time.time(), size))
        )
        self.state_manager.activity_state_changed.connect(
            lambda active: self.all_signals.append(('activity', time.time(), active))
        )
    
    def test_end_to_end_rapid_volume_surfing(self):
        """
        End-to-end test: User rapidly adjusts volume during TV watching
        Tests complete flow from command queueing to processing to UI feedback
        
        Requirements: 1.1 (sequential processing), 2.2 (rapid command acceptance)
        """
        # Clear signals
        self.all_signals.clear()
        
        # Simulate user rapidly pressing volume buttons (realistic scenario)
        volume_sequence = [
            ('vol+', None),  # User wants louder
            ('vol+', None),  # Still too quiet
            ('vol+', None),  # Getting there
            ('vol-', None),  # Oops, too loud
            ('vol-', None),  # Still too loud
            ('vol+', None),  # Back up a bit
            ('mute', None),  # Silence for a moment
            ('mute', None),  # Unmute
        ]
        
        # Queue all commands rapidly (simulating fast button presses)
        start_time = time.time()
        queued_commands = []
        
        for cmd, action in volume_sequence:
            if self.state_manager.queue_command(cmd, action):
                queued_commands.append((cmd, action))
        
        queue_time = time.time() - start_time
        
        # Verify all volume commands were accepted rapidly (Requirement 2.2)
        assert len(queued_commands) == len(volume_sequence), \
            f"All {len(volume_sequence)} volume commands should be accepted, got {len(queued_commands)}"
        
        assert queue_time < 0.01, \
            f"Rapid volume commands should be queued instantly, took {queue_time:.3f}s"
        
        # Verify queue size signals were emitted for each command
        queue_signals = [sig for sig in self.all_signals if sig[0] == 'queue']
        assert len(queue_signals) >= len(volume_sequence), \
            f"Queue signals should be emitted for each command, expected >= {len(volume_sequence)}, got {len(queue_signals)}"
        
        # Process all commands end-to-end and verify sequential order (Requirement 1.1)
        processed_commands = []
        processing_start = time.time()
        
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Verify immediate visual feedback
                status_signals = [sig for sig in self.all_signals if sig[0] == 'status' and sig[1] > processing_start]
                processing_feedback = [sig for sig in status_signals if "🚀 Elaborazione" in sig[2]]
                assert len(processing_feedback) > 0, \
                    f"Should show processing feedback for {next_cmd.command}"
                
                # Complete processing
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
                
                # Verify sequential processing order is maintained
                assert self.state_manager.ensure_sequential_processing(), \
                    f"Sequential processing violated during volume command {next_cmd.command}"
        
        processing_time = time.time() - processing_start
        
        # Verify end-to-end sequential processing (Requirement 1.1)
        assert processed_commands == volume_sequence, \
            f"Commands should be processed in exact FIFO order: expected {volume_sequence}, got {processed_commands}"
        
        # Verify performance is acceptable for rapid commands
        avg_processing_time = processing_time / len(volume_sequence)
        assert avg_processing_time < 0.1, \
            f"Average processing time should be fast for volume commands, got {avg_processing_time:.3f}s"
        
        # Verify final state is clean
        assert self.state_manager.pending_commands == 0, "Queue should be empty"
        assert not self.state_manager.is_processing, "Should not be processing"
        
        # Verify final queue signal indicates empty queue
        final_queue_signals = [sig for sig in self.all_signals if sig[0] == 'queue']
        if final_queue_signals:
            assert final_queue_signals[-1][2] == 0, "Final queue signal should indicate empty queue"
    
    def test_end_to_end_rapid_channel_navigation(self):
        """
        End-to-end test: User rapidly navigates channels and menus
        Tests device command processing under rapid input conditions
        
        Requirements: 1.1 (sequential processing), 2.2 (rapid command acceptance)
        """
        # Clear signals
        self.all_signals.clear()
        
        # Simulate user rapidly navigating TV interface
        navigation_sequence = [
            ('samsung', 'ChannelUp'),      # Channel up
            ('samsung', 'ChannelUp'),      # Channel up again
            ('samsung', 'ChannelDown'),    # Oops, go back
            ('samsung', 'Menu'),           # Open menu
            ('samsung', 'DirectionDown'),  # Navigate down
            ('samsung', 'DirectionDown'),  # Navigate down more
            ('samsung', 'Select'),         # Select item
            ('samsung', 'Back'),           # Go back
            ('samsung', 'Home'),           # Go to home
            ('samsung', 'SmartHub'),       # Open smart hub
        ]
        
        # Queue all commands rapidly
        start_time = time.time()
        queued_count = 0
        
        for device, action in navigation_sequence:
            if self.state_manager.queue_command(device, action):
                queued_count += 1
        
        queue_time = time.time() - start_time
        
        # Verify all device commands were accepted (Requirement 2.2)
        assert queued_count == len(navigation_sequence), \
            f"All {len(navigation_sequence)} navigation commands should be accepted, got {queued_count}"
        
        assert queue_time < 0.02, \
            f"Rapid navigation commands should be queued quickly, took {queue_time:.3f}s"
        
        # Verify all commands are classified as device commands
        for device, action in navigation_sequence:
            cmd_type = self.state_manager.classify_command(device, action)
            assert cmd_type == CommandType.DEVICE, \
                f"Command {device} {action} should be classified as DEVICE, got {cmd_type}"
        
        # Process all commands end-to-end with timing verification
        processed_commands = []
        processing_times = []
        
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                process_start = time.time()
                
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Verify processing state
                assert self.state_manager.is_processing, "Should be processing"
                assert not self.state_manager.is_activity_changing, \
                    "Device commands should not trigger activity changing state"
                
                # Complete processing
                self.state_manager.complete_command_processing(success=True)
                
                process_end = time.time()
                processing_times.append(process_end - process_start)
                processed_commands.append((next_cmd.command, next_cmd.action))
                
                # Verify sequential processing order
                assert self.state_manager.ensure_sequential_processing(), \
                    f"Sequential processing violated during navigation command {next_cmd.command} {next_cmd.action}"
        
        # Verify end-to-end sequential processing (Requirement 1.1)
        assert processed_commands == navigation_sequence, \
            f"Navigation commands should be processed in FIFO order: expected {navigation_sequence}, got {processed_commands}"
        
        # Verify processing performance for device commands
        avg_processing_time = sum(processing_times) / len(processing_times)
        assert avg_processing_time < 0.05, \
            f"Device command processing should be fast, got {avg_processing_time:.3f}s average"
        
        # Verify no commands were lost or duplicated
        assert len(processed_commands) == len(navigation_sequence), \
            f"All commands should be processed exactly once: expected {len(navigation_sequence)}, got {len(processed_commands)}"
    
    def test_end_to_end_mixed_rapid_commands_with_activity_blocking(self):
        """
        End-to-end test: Mixed rapid commands with activity blocking
        Tests complete system behavior when activities and devices are mixed
        
        Requirements: 1.1 (sequential processing), 2.1 (activity blocking), 2.2 (rapid acceptance)
        """
        # Clear signals
        self.all_signals.clear()
        
        # Simulate realistic user scenario: start TV, adjust volume, try to switch to music
        mixed_scenario = [
            ('tv', None),              # Start TV activity
            ('samsung', 'VolumeUp'),   # Adjust volume while TV starting
            ('vol+', None),            # More volume adjustment
            ('music', None),           # Try to switch to music (should be blocked)
            ('samsung', 'Menu'),       # Use TV menu (should work)
            ('vol-', None),            # Adjust volume down
            ('shield', None),          # Try another activity (should be blocked)
            ('samsung', 'Home'),       # Go to TV home (should work)
        ]
        
        # Queue all commands rapidly
        start_time = time.time()
        accepted_commands = []
        blocked_commands = []
        
        for cmd, action in mixed_scenario:
            if self.state_manager.queue_command(cmd, action):
                accepted_commands.append((cmd, action))
            else:
                blocked_commands.append((cmd, action))
        
        queue_time = time.time() - start_time
        
        # Verify rapid queueing performance
        assert queue_time < 0.02, \
            f"Mixed command queueing should be fast, took {queue_time:.3f}s"
        
        # Verify activity blocking behavior (Requirement 2.1)
        expected_accepted = [
            ('tv', None),              # First activity - accepted
            ('samsung', 'VolumeUp'),   # Device - accepted
            ('vol+', None),            # Audio - accepted  
            ('samsung', 'Menu'),       # Device - accepted
            ('vol-', None),            # Audio - accepted
            ('samsung', 'Home'),       # Device - accepted
        ]
        expected_blocked = [
            ('music', None),           # Activity blocked
            ('shield', None),          # Activity blocked
        ]
        
        assert accepted_commands == expected_accepted, \
            f"Expected accepted commands: {expected_accepted}, got {accepted_commands}"
        assert blocked_commands == expected_blocked, \
            f"Expected blocked commands: {expected_blocked}, got {blocked_commands}"
        
        # Process all accepted commands end-to-end
        processed_commands = []
        activity_processing_detected = False
        
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Track activity processing
                if next_cmd.command_type == CommandType.ACTIVITY:
                    activity_processing_detected = True
                    
                    # Verify activity blocking state is active
                    assert self.state_manager.is_activity_changing, \
                        f"Activity changing should be True for activity command {next_cmd.command}"
                    
                    # Verify button disable signal was emitted
                    button_signals = [sig for sig in self.all_signals if sig[0] == 'buttons']
                    disable_signals = [sig for sig in button_signals if sig[2] == False]
                    assert len(disable_signals) > 0, \
                        "Button disable signal should be emitted for activity command"
                
                # Complete processing
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
                
                # Verify sequential processing order
                assert self.state_manager.ensure_sequential_processing(), \
                    f"Sequential processing violated during mixed command {next_cmd.command}"
        
        # Verify end-to-end processing (Requirement 1.1)
        assert processed_commands == expected_accepted, \
            f"Processed commands should match accepted commands: expected {expected_accepted}, got {processed_commands}"
        
        # Verify activity processing was detected
        assert activity_processing_detected, "Should have processed at least one activity command"
        
        # Verify final state is clean
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared"
        assert not self.state_manager.is_processing, "Processing should be cleared"
        assert self.state_manager.pending_commands == 0, "Queue should be empty"
        
        # Verify button re-enable signal was emitted
        button_signals = [sig for sig in self.all_signals if sig[0] == 'buttons']
        enable_signals = [sig for sig in button_signals if sig[2] == True]
        assert len(enable_signals) > 0, "Button enable signal should be emitted after activity completion"


class TestActivityBlockingWithDeviceCommands:
    """Integration tests for activity blocking scenarios with device commands"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track signals for verification
        self.status_signals = []
        self.button_signals = []
        self.activity_signals = []
        self.queue_signals = []
        
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.buttons_state_changed.connect(
            lambda enabled: self.button_signals.append(enabled)
        )
        self.state_manager.activity_state_changed.connect(
            lambda active: self.activity_signals.append(active)
        )
        self.state_manager.queue_size_changed.connect(
            lambda size: self.queue_signals.append(size)
        )
    
    def test_activity_blocking_allows_device_commands_during_processing(self):
        """
        Test that device commands are accepted and processed during activity changes
        
        Requirements: 2.1 (activity blocking), 2.2 (rapid command acceptance)
        """
        # Clear signals
        self.status_signals.clear()
        self.button_signals.clear()
        self.activity_signals.clear()
        self.queue_signals.clear()
        
        # Start TV activity
        assert self.state_manager.queue_command('tv'), "TV activity should be accepted"
        
        # Start processing TV activity
        tv_cmd = self.state_manager.get_next_command()
        assert tv_cmd is not None, "Should have TV command"
        assert tv_cmd.command_type == CommandType.ACTIVITY, "TV should be activity command"
        
        self.state_manager.start_command_processing(tv_cmd)
        
        # Verify activity blocking is active
        assert self.state_manager.is_activity_changing, "Activity changing should be True"
        assert True in self.activity_signals, "Activity state signal should be emitted"
        assert False in self.button_signals, "Button disable signal should be emitted"
        
        # Now try to queue device commands - they should be accepted
        device_commands = [
            ('samsung', 'VolumeUp'),
            ('samsung', 'VolumeDown'), 
            ('vol+', None),
            ('vol-', None),
            ('samsung', 'Menu'),
            ('samsung', 'Home'),
        ]
        
        accepted_devices = []
        for device, action in device_commands:
            # Verify device command can be accepted during activity change
            assert self.state_manager.can_accept_command(device, action), \
                f"Device command {device} {action} should be accepted during activity change"
            
            # Queue the device command
            if self.state_manager.queue_command(device, action):
                accepted_devices.append((device, action))
        
        # All device commands should be accepted (Requirement 2.2)
        assert len(accepted_devices) == len(device_commands), \
            f"All {len(device_commands)} device commands should be accepted during activity change, got {len(accepted_devices)}"
        
        # Verify queue size reflects all commands
        expected_queue_size = 1 + len(device_commands)  # TV + device commands
        assert self.state_manager.pending_commands == expected_queue_size, \
            f"Queue should contain {expected_queue_size} commands, got {self.state_manager.pending_commands}"
        
        # Try to queue another activity - should be blocked
        assert not self.state_manager.can_accept_command('music'), \
            "Music activity should be blocked during TV activity"
        assert not self.state_manager.queue_command('music'), \
            "Music activity should not be queued during TV activity"
        
        # Complete TV activity
        self.state_manager.complete_command_processing(success=True)
        
        # Verify activity blocking is cleared
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared"
        assert False in self.activity_signals, "Activity cleared signal should be emitted"
        assert True in self.button_signals, "Button enable signal should be emitted"
        
        # Process all device commands
        processed_devices = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Device commands should not trigger activity changing
                self.state_manager.start_command_processing(next_cmd)
                assert not self.state_manager.is_activity_changing, \
                    f"Device command {next_cmd.command} should not trigger activity changing"
                
                self.state_manager.complete_command_processing(success=True)
                processed_devices.append((next_cmd.command, next_cmd.action))
        
        # Verify all device commands were processed in order
        assert processed_devices == device_commands, \
            f"Device commands should be processed in FIFO order: expected {device_commands}, got {processed_devices}"
    
    def test_multiple_activities_blocked_while_device_commands_flow(self):
        """
        Test that multiple activities are blocked while device commands continue to flow
        
        Requirements: 2.1 (activity blocking), 1.1 (sequential processing)
        """
        # Clear signals
        self.status_signals.clear()
        self.activity_signals.clear()
        
        # Start music activity
        assert self.state_manager.queue_command('music'), "Music activity should be accepted"
        
        # Start processing music activity
        music_cmd = self.state_manager.get_next_command()
        self.state_manager.start_command_processing(music_cmd)
        
        # Verify activity blocking is active
        assert self.state_manager.is_activity_changing, "Activity changing should be True"
        
        # Try to queue multiple other activities - all should be blocked
        blocked_activities = ['tv', 'shield', 'off']
        for activity in blocked_activities:
            assert not self.state_manager.can_accept_command(activity), \
                f"Activity {activity} should be blocked during music activity"
            assert not self.state_manager.queue_command(activity), \
                f"Activity {activity} should not be queued during music activity"
        
        # Queue many device commands - all should be accepted
        device_stream = [
            ('samsung', 'VolumeUp'), ('vol+', None), ('samsung', 'Menu'),
            ('samsung', 'DirectionUp'), ('vol-', None), ('samsung', 'Select'),
            ('samsung', 'Back'), ('vol+', None), ('samsung', 'Home'),
            ('samsung', 'VolumeDown'), ('vol-', None), ('samsung', 'SmartHub'),
        ]
        
        accepted_devices = []
        for device, action in device_stream:
            if self.state_manager.queue_command(device, action):
                accepted_devices.append((device, action))
        
        # All device commands should be accepted
        assert len(accepted_devices) == len(device_stream), \
            f"All {len(device_stream)} device commands should be accepted, got {len(accepted_devices)}"
        
        # Complete music activity
        self.state_manager.complete_command_processing(success=True)
        
        # Verify activity blocking is cleared
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared"
        
        # Now activities should be accepted again
        assert self.state_manager.can_accept_command('tv'), \
            "TV activity should be accepted after music completes"
        
        # Process all device commands and verify sequential order
        processed_devices = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_devices.append((next_cmd.command, next_cmd.action))
        
        # Verify sequential processing of device commands (Requirement 1.1)
        assert processed_devices == device_stream, \
            f"Device commands should be processed sequentially: expected {device_stream}, got {processed_devices}"
    
    def test_activity_error_recovery_unblocks_subsequent_activities(self):
        """
        Test that activity errors properly clear blocking state for subsequent activities
        
        Requirements: 2.1 (activity blocking), 1.4 (error handling)
        """
        # Clear signals
        self.status_signals.clear()
        self.activity_signals.clear()
        
        # Start shield activity
        assert self.state_manager.queue_command('shield'), "Shield activity should be accepted"
        
        # Start processing shield activity
        shield_cmd = self.state_manager.get_next_command()
        self.state_manager.start_command_processing(shield_cmd)
        
        # Verify activity blocking is active
        assert self.state_manager.is_activity_changing, "Activity changing should be True"
        
        # Try to queue other activities - should be blocked
        assert not self.state_manager.can_accept_command('tv'), \
            "TV should be blocked during shield activity"
        
        # Queue some device commands - should be accepted
        device_commands = [('samsung', 'VolumeUp'), ('vol+', None)]
        for device, action in device_commands:
            assert self.state_manager.queue_command(device, action), \
                f"Device command {device} {action} should be accepted during activity"
        
        # Simulate activity error
        error_message = "Network connection lost"
        self.state_manager.handle_command_error('shield', None, error_message)
        
        # Verify error handling cleared activity blocking state
        assert not self.state_manager.is_activity_changing, \
            "Activity changing should be cleared after error"
        assert not self.state_manager.is_processing, \
            "Processing should be cleared after error"
        
        # Verify error status was shown
        error_status_found = False
        for status_text, color in self.status_signals:
            if "❌" in status_text:
                error_status_found = True
                assert color == "#f7768e", "Error should use danger color"
                break
        assert error_status_found, "Error status should be displayed"
        
        # Now other activities should be accepted again
        assert self.state_manager.can_accept_command('tv'), \
            "TV should be accepted after shield activity error"
        assert self.state_manager.queue_command('tv'), \
            "TV should be queued after shield activity error"
        
        # Process remaining commands (device commands + new TV activity)
        processed_commands = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
        
        # Verify device commands and new activity were processed
        expected_remaining = device_commands + [('tv', None)]
        assert processed_commands == expected_remaining, \
            f"Remaining commands should be processed after error: expected {expected_remaining}, got {processed_commands}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])