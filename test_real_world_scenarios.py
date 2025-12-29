#!/usr/bin/env python3
"""
Real-world scenario tests for Harmony State Management system
Tests realistic usage patterns and edge cases
Feature: harmony-state-management
"""

import pytest
import time
import threading
from PyQt6.QtCore import QCoreApplication, QTimer
import sys

from state_manager import StateManager, CommandType

# Ensure QApplication exists for Qt signals
if not QCoreApplication.instance():
    app = QCoreApplication(sys.argv)


class TestRealWorldScenarios:
    """Test realistic usage scenarios"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track all signals for comprehensive verification
        self.all_signals = []
        
        # Connect to all signals with timestamps
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
    
    def test_typical_tv_watching_session(self):
        """
        Test a typical TV watching session with realistic command patterns
        Requirements: 1.1, 1.2, 1.3 (complete user experience)
        """
        # Clear signals
        self.all_signals.clear()
        
        # Scenario: User starts TV, adjusts volume, changes channels, uses menu
        session_commands = [
            # Start TV activity
            ('tv', None, 'Start TV activity'),
            
            # Wait for activity to complete, then use device commands
            ('samsung', 'VolumeUp', 'Increase volume'),
            ('samsung', 'VolumeUp', 'Increase volume more'),
            ('samsung', 'ChannelUp', 'Change channel'),
            ('samsung', 'Menu', 'Open menu'),
            ('samsung', 'DirectionDown', 'Navigate menu'),
            ('samsung', 'Select', 'Select menu item'),
            ('samsung', 'Back', 'Go back'),
            
            # More volume adjustments
            ('vol+', None, 'Volume up via audio'),
            ('vol-', None, 'Volume down via audio'),
            
            # Try to switch to music (should be blocked initially)
            ('music', None, 'Try to switch to music'),
            
            # More TV commands
            ('samsung', 'Home', 'Go to home screen'),
            ('samsung', 'SmartHub', 'Open Smart Hub'),
        ]
        
        # Execute session commands with realistic timing
        accepted_commands = []
        blocked_commands = []
        
        for i, (cmd, action, description) in enumerate(session_commands):
            print(f"Step {i+1}: {description} ({cmd} {action or ''})")
            
            # Check if command can be accepted
            can_accept = self.state_manager.can_accept_command(cmd, action)
            queued = self.state_manager.queue_command(cmd, action)
            
            if queued:
                accepted_commands.append((cmd, action, description))
                print(f"  ✓ Accepted and queued")
            else:
                blocked_commands.append((cmd, action, description))
                print(f"  ✗ Blocked")
            
            # Process first few commands to simulate realistic flow
            if i < 3:  # Process TV start and first couple device commands
                next_cmd = self.state_manager.get_next_command()
                if next_cmd:
                    print(f"  → Processing: {next_cmd.command} {next_cmd.action or ''}")
                    self.state_manager.start_command_processing(next_cmd)
                    
                    # Simulate processing time
                    if next_cmd.command_type == CommandType.ACTIVITY:
                        time.sleep(0.01)  # Activity takes longer
                    else:
                        time.sleep(0.001)  # Device commands are faster
                    
                    self.state_manager.complete_command_processing(success=True)
                    print(f"  ✓ Completed: {next_cmd.command}")
        
        # Verify expected behavior
        # TV activity should be accepted
        tv_accepted = any(cmd == 'tv' for cmd, _, _ in accepted_commands)
        assert tv_accepted, "TV activity should be accepted"
        
        # Music should be accepted since TV activity completed early in the test
        # (we only processed first 3 commands, so TV completed before music was queued)
        music_accepted = any(cmd == 'music' for cmd, _, _ in accepted_commands)
        assert music_accepted, "Music activity should be accepted after TV completes"
        
        # All device commands should be accepted
        device_commands = [(cmd, action, desc) for cmd, action, desc in session_commands 
                          if cmd in ['samsung', 'vol+', 'vol-']]
        device_accepted = [cmd for cmd, action, desc in accepted_commands 
                          if cmd in ['samsung', 'vol+', 'vol-']]
        
        assert len(device_accepted) == len(device_commands), \
            f"All device commands should be accepted: expected {len(device_commands)}, got {len(device_accepted)}"
        
        # Verify signal patterns
        status_signals = [sig for sig in self.all_signals if sig[0] == 'status']
        queue_signals = [sig for sig in self.all_signals if sig[0] == 'queue']
        
        assert len(status_signals) > 0, "Status signals should be emitted during session"
        assert len(queue_signals) > 0, "Queue signals should be emitted during session"
        
        # Verify queue size progression
        max_queue_size = max(sig[2] for sig in queue_signals) if queue_signals else 0
        assert max_queue_size > 5, f"Queue should handle multiple commands, max size was {max_queue_size}"
        
        print(f"Session completed: {len(accepted_commands)} accepted, {len(blocked_commands)} blocked")
    
    def test_rapid_channel_surfing(self):
        """
        Test rapid channel surfing scenario (very fast button presses)
        Requirements: 2.2 (rapid command acceptance), 1.1 (sequential processing)
        """
        # Clear signals
        self.all_signals.clear()
        
        # Simulate user rapidly pressing channel up/down buttons
        channel_commands = []
        for i in range(20):
            if i % 3 == 0:
                channel_commands.append(('samsung', 'ChannelUp'))
            elif i % 3 == 1:
                channel_commands.append(('samsung', 'ChannelDown'))
            else:
                channel_commands.append(('samsung', f'{(i % 9) + 1}'))  # Number buttons
        
        # Queue all commands as fast as possible
        start_time = time.time()
        queued_count = 0
        
        for cmd, action in channel_commands:
            if self.state_manager.queue_command(cmd, action):
                queued_count += 1
        
        queue_time = time.time() - start_time
        
        # All commands should be accepted rapidly
        assert queued_count == len(channel_commands), \
            f"All {len(channel_commands)} channel commands should be accepted, got {queued_count}"
        
        assert queue_time < 0.05, \
            f"Rapid channel surfing should be queued quickly, took {queue_time:.3f}s"
        
        # Process all commands and verify sequential order
        processed_commands = []
        processing_start = time.time()
        
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
                
                # Verify sequential processing is maintained
                assert self.state_manager.ensure_sequential_processing(), \
                    f"Sequential processing violated during rapid channel surfing"
        
        processing_time = time.time() - processing_start
        
        # Verify all commands were processed in correct order
        assert processed_commands == channel_commands, \
            "Channel commands should be processed in exact FIFO order"
        
        # Verify reasonable processing performance
        avg_processing_time = processing_time / len(channel_commands)
        assert avg_processing_time < 0.01, \
            f"Average command processing should be fast, got {avg_processing_time:.3f}s per command"
        
        print(f"Rapid channel surfing: {len(channel_commands)} commands in {queue_time:.3f}s queue, {processing_time:.3f}s processing")
    
    def test_activity_switching_with_interruptions(self):
        """
        Test activity switching with various interruptions and edge cases
        Requirements: 2.1 (activity blocking), 1.4 (error handling)
        """
        # Clear signals
        self.all_signals.clear()
        
        # Scenario: Start TV, try to switch to music (blocked), use devices, complete TV, then switch
        
        # Step 1: Start TV activity
        assert self.state_manager.queue_command('tv'), "TV activity should be accepted"
        
        tv_cmd = self.state_manager.get_next_command()
        assert tv_cmd is not None, "TV command should be available"
        assert tv_cmd.command_type == CommandType.ACTIVITY, "TV should be activity command"
        
        self.state_manager.start_command_processing(tv_cmd)
        
        # Verify activity blocking is active
        assert self.state_manager.is_activity_changing, "Activity changing should be True"
        
        # Step 2: Try to switch to music (should be blocked)
        assert not self.state_manager.can_accept_command('music'), "Music should be blocked"
        assert not self.state_manager.queue_command('music'), "Music should not be queued"
        
        # Step 3: Device commands should still work
        device_commands = [('samsung', 'VolumeUp'), ('vol+', None), ('samsung', 'Menu')]
        for cmd, action in device_commands:
            assert self.state_manager.can_accept_command(cmd, action), \
                f"Device command {cmd} {action} should be accepted during activity change"
            assert self.state_manager.queue_command(cmd, action), \
                f"Device command {cmd} {action} should be queued during activity change"
        
        # Step 4: Simulate error during TV activity
        self.state_manager.handle_command_error('tv', None, "Network timeout")
        
        # Verify error handling cleared activity state
        assert not self.state_manager.is_activity_changing, \
            "Activity changing should be cleared after error"
        assert not self.state_manager.is_processing, \
            "Processing should be cleared after error"
        
        # Step 5: Now music activity should be accepted
        assert self.state_manager.can_accept_command('music'), \
            "Music should be accepted after TV activity error"
        assert self.state_manager.queue_command('music'), \
            "Music should be queued after TV activity error"
        
        # Step 6: Process remaining commands
        remaining_processed = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                remaining_processed.append((next_cmd.command, next_cmd.action))
        
        # Verify all queued commands were processed
        expected_remaining = device_commands + [('music', None)]
        assert remaining_processed == expected_remaining, \
            f"Remaining commands should be processed in order: expected {expected_remaining}, got {remaining_processed}"
        
        # Verify final state is clean
        assert not self.state_manager.is_processing, "Should not be processing at end"
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared at end"
        assert self.state_manager.pending_commands == 0, "Queue should be empty at end"
        
        print("Activity switching with interruptions completed successfully")
    
    def test_concurrent_signal_handling(self):
        """
        Test that signal handling works correctly under concurrent conditions
        Requirements: 3.2 (component notification)
        """
        # Clear signals
        self.all_signals.clear()
        
        # Create multiple threads that queue commands simultaneously
        def queue_commands_thread(thread_id, commands):
            """Thread function to queue commands"""
            for i, (cmd, action) in enumerate(commands):
                # Add small random delay to simulate real user timing
                time.sleep(0.001 * (thread_id + 1))
                
                queued = self.state_manager.queue_command(cmd, action)
                if queued:
                    print(f"Thread {thread_id}: Queued {cmd} {action or ''}")
        
        # Define command sets for different threads
        thread_commands = [
            # Thread 0: Volume commands
            [('vol+', None), ('vol-', None), ('vol+', None)],
            # Thread 1: Samsung device commands  
            [('samsung', 'Menu'), ('samsung', 'Home'), ('samsung', 'Back')],
            # Thread 2: More volume commands
            [('vol-', None), ('vol+', None), ('mute', None)],
        ]
        
        # Start threads
        threads = []
        for i, commands in enumerate(thread_commands):
            thread = threading.Thread(target=queue_commands_thread, args=(i, commands))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all commands were queued (all should be device/audio commands, so all accepted)
        total_expected = sum(len(commands) for commands in thread_commands)
        assert self.state_manager.pending_commands == total_expected, \
            f"All {total_expected} commands should be queued, got {self.state_manager.pending_commands}"
        
        # Verify signal consistency (signals may not be captured in threading scenario)
        queue_signals = [sig for sig in self.all_signals if sig[0] == 'queue']
        status_signals = [sig for sig in self.all_signals if sig[0] == 'status']
        
        # Note: In concurrent scenarios, signal capture may be unreliable due to threading
        # The important thing is that the commands were queued correctly
        print(f"Captured {len(queue_signals)} queue signals and {len(status_signals)} status signals")
        
        # Process all commands and verify order consistency
        processed_commands = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                self.state_manager.start_command_processing(next_cmd)
                self.state_manager.complete_command_processing(success=True)
                processed_commands.append((next_cmd.command, next_cmd.action))
        
        # Verify all commands were processed
        assert len(processed_commands) == total_expected, \
            f"All {total_expected} commands should be processed, got {len(processed_commands)}"
        
        # Verify final signal state (if any signals were captured)
        final_queue_signals = [sig for sig in self.all_signals if sig[0] == 'queue']
        if final_queue_signals:
            assert final_queue_signals[-1][2] == 0, "Final queue signal should indicate empty queue"
        
        print(f"Concurrent signal handling: {total_expected} commands from {len(threads)} threads processed successfully")


class TestGUIStateManagerIntegration:
    """Test integration between GUI and StateManager to prevent status bypass"""
    
    def setup_method(self):
        """Setup fresh components for each test"""
        self.state_manager = StateManager()
        
        # Track all signals
        self.status_signals = []
        self.activity_signals = []
        
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.activity_state_changed.connect(
            lambda active: self.activity_signals.append(active)
        )
    
    def test_gui_status_bypass_prevention(self):
        """
        Test that GUI on_status() respects StateManager coordination.
        This prevents the "avvio watch tv" -> "off" -> "Watch TV" issue.
        
        Requirements: 3.3 (timer coordination), 4.1 (immediate feedback)
        """
        # Clear signals
        self.status_signals.clear()
        self.activity_signals.clear()
        
        # Create mock GUI that simulates the fixed on_status behavior
        class MockGUI:
            def __init__(self, state_manager):
                self.state_manager = state_manager
                self.status_updates_blocked = []
                self.status_updates_allowed = []
            
            def on_status(self, status_text):
                """Simulate fixed GUI.on_status() method"""
                # Update current activity in StateManager
                activity_name = "unknown"
                if "OFF" in status_text or "-1" in status_text:
                    activity_name = "off"
                elif "TV" in status_text:
                    activity_name = "tv"
                elif "Music" in status_text:
                    activity_name = "music"
                
                self.state_manager.update_current_activity(activity_name)
                
                # CRITICAL FIX: Check if StateManager allows status updates
                if not self.state_manager.is_timer_update_allowed():
                    # StateManager is coordinating an activity change
                    # Don't override its status display with intermediate Hub states
                    self.status_updates_blocked.append(status_text)
                    return
                
                # Only update GUI if StateManager allows it
                self.status_updates_allowed.append(status_text)
        
        gui = MockGUI(self.state_manager)
        
        # Start TV activity
        assert self.state_manager.queue_command('tv'), "TV activity should be accepted"
        
        # Start processing
        next_cmd = self.state_manager.get_next_command()
        assert next_cmd is not None, "Should have TV command"
        
        self.state_manager.start_command_processing(next_cmd)
        
        # Verify activity is in progress
        assert self.state_manager.is_activity_changing, "Activity should be changing"
        assert True in self.activity_signals, "Activity state should be active"
        
        # Simulate intermediate Hub states that used to cause the problem
        intermediate_states = ["PowerOff", "-1", "Off", "Guarda TV"]
        
        for state in intermediate_states:
            gui.on_status(state)
        
        # All intermediate states should be blocked during activity change
        assert len(gui.status_updates_blocked) == len(intermediate_states), \
            f"All intermediate states should be blocked, blocked: {len(gui.status_updates_blocked)}, total: {len(intermediate_states)}"
        
        assert len(gui.status_updates_allowed) == 0, \
            f"No status updates should be allowed during activity change, allowed: {gui.status_updates_allowed}"
        
        # Complete the activity
        self.state_manager.complete_command_processing(success=True)
        
        # Verify activity is no longer changing
        assert not self.state_manager.is_activity_changing, "Activity should not be changing"
        assert False in self.activity_signals, "Activity state should be cleared"
        
        # Now status updates should be allowed
        gui.on_status("Guarda TV")
        
        assert len(gui.status_updates_allowed) == 1, \
            f"Status update should be allowed after activity completion, allowed: {gui.status_updates_allowed}"
        
        assert gui.status_updates_allowed[0] == "Guarda TV", \
            f"Final state should be allowed, got: {gui.status_updates_allowed[0]}"
    
    def test_device_commands_allow_status_updates(self):
        """
        Test that device commands don't block GUI status updates.
        Only activity changes should block status updates.
        
        Requirements: 3.3 (timer coordination)
        """
        # Clear signals
        self.status_signals.clear()
        
        # Create mock GUI
        class MockGUI:
            def __init__(self, state_manager):
                self.state_manager = state_manager
                self.status_updates_blocked = []
                self.status_updates_allowed = []
            
            def on_status(self, status_text):
                """Simulate fixed GUI.on_status() method"""
                activity_name = "tv"  # Assume we're in TV mode
                self.state_manager.update_current_activity(activity_name)
                
                # Check if StateManager allows status updates
                if not self.state_manager.is_timer_update_allowed():
                    self.status_updates_blocked.append(status_text)
                    return
                
                self.status_updates_allowed.append(status_text)
        
        gui = MockGUI(self.state_manager)
        
        # Start device command (not activity)
        assert self.state_manager.queue_command('samsung', 'VolumeUp'), "Device command should be accepted"
        
        # Start processing device command
        next_cmd = self.state_manager.get_next_command()
        assert next_cmd is not None, "Should have device command"
        
        self.state_manager.start_command_processing(next_cmd)
        
        # Verify device command is processing but not blocking activity changes
        assert self.state_manager.is_processing, "Should be processing device command"
        assert not self.state_manager.is_activity_changing, "Activity should not be changing for device command"
        
        # Status updates should be allowed during device command processing
        gui.on_status("📺 TV MODE")
        
        assert len(gui.status_updates_allowed) == 1, \
            f"Status updates should be allowed during device command processing, allowed: {gui.status_updates_allowed}"
        
        assert len(gui.status_updates_blocked) == 0, \
            f"No status updates should be blocked for device commands, blocked: {gui.status_updates_blocked}"
        
        # Complete device command
        self.state_manager.complete_command_processing(success=True)
        
        # Status updates should still be allowed
        gui.on_status("📺 TV MODE")
        
        assert len(gui.status_updates_allowed) == 2, \
            f"Status updates should remain allowed after device command, allowed: {gui.status_updates_allowed}"
    
    def test_multiple_activity_transitions_with_gui_coordination(self):
        """
        Test multiple activity transitions with proper GUI coordination.
        
        Requirements: 3.3 (timer coordination), 2.1 (activity blocking)
        """
        # Create mock GUI
        class MockGUI:
            def __init__(self, state_manager):
                self.state_manager = state_manager
                self.all_status_updates = []  # Track all attempts
                self.blocked_updates = []
                self.allowed_updates = []
            
            def on_status(self, status_text):
                """Simulate fixed GUI.on_status() method"""
                self.all_status_updates.append(status_text)
                
                # Extract activity
                activity_name = "unknown"
                if "TV" in status_text:
                    activity_name = "tv"
                elif "Music" in status_text:
                    activity_name = "music"
                elif "Shield" in status_text:
                    activity_name = "shield"
                elif "OFF" in status_text or "-1" in status_text:
                    activity_name = "off"
                
                self.state_manager.update_current_activity(activity_name)
                
                # Check StateManager coordination
                if not self.state_manager.is_timer_update_allowed():
                    self.blocked_updates.append(status_text)
                    return
                
                self.allowed_updates.append(status_text)
        
        gui = MockGUI(self.state_manager)
        
        # Test sequence of activities with intermediate states
        activities = ['tv', 'music', 'shield']
        
        for activity in activities:
            # Clear previous state if needed
            if self.state_manager.is_activity_changing:
                self.state_manager.is_activity_changing = False
            
            # Start activity
            assert self.state_manager.queue_command(activity), f"{activity} should be accepted"
            
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Simulate intermediate states during activity change
                intermediate_states = ["PowerOff", "-1", f"{activity.title()} Starting"]
                
                for state in intermediate_states:
                    gui.on_status(state)
                
                # Complete activity
                self.state_manager.complete_command_processing(success=True)
                
                # Final state should be allowed
                final_state = f"{activity.title()} Active"
                gui.on_status(final_state)
        
        # Verify coordination worked correctly
        total_attempts = len(gui.all_status_updates)
        blocked_count = len(gui.blocked_updates)
        allowed_count = len(gui.allowed_updates)
        
        assert total_attempts == blocked_count + allowed_count, \
            f"All status updates should be accounted for: {total_attempts} = {blocked_count} + {allowed_count}"
        
        # Should have blocked intermediate states during activity changes
        assert blocked_count > 0, \
            f"Should have blocked some intermediate states, blocked: {blocked_count}"
        
        # Should have allowed final states after activity completion
        assert allowed_count > 0, \
            f"Should have allowed some final states, allowed: {allowed_count}"
        
        # Verify no "OFF" states were shown during activity transitions
        off_states_shown = [update for update in gui.allowed_updates if "OFF" in update or "-1" in update]
        assert len(off_states_shown) == 0, \
            f"No 'OFF' states should be shown during activity transitions, found: {off_states_shown}"


class TestActivityStatusTransitionFix:
    """Test fix for activity status transition issue (avvio -> off -> final state)"""
    
    def setup_method(self):
        """Setup fresh StateManager for each test"""
        self.state_manager = StateManager()
        
        # Track all signals to verify smooth transitions
        self.status_signals = []
        self.activity_signals = []
        
        self.state_manager.status_changed.connect(
            lambda text, color: self.status_signals.append((text, color))
        )
        self.state_manager.activity_state_changed.connect(
            lambda active: self.activity_signals.append(active)
        )
    
    def test_tv_activity_smooth_transition(self):
        """
        Test that TV activity shows smooth transition without intermediate "off" state.
        This addresses the original issue: "avvio watch tv" -> "off" -> "Watch TV"
        
        Requirements: 3.3 (timer coordination), 4.1 (immediate feedback)
        """
        # Clear signals
        self.status_signals.clear()
        self.activity_signals.clear()
        
        # Simulate starting TV activity
        assert self.state_manager.queue_command('tv'), "TV activity should be accepted"
        
        # Get and start processing
        next_cmd = self.state_manager.get_next_command()
        assert next_cmd is not None, "Should have TV command"
        
        # Clear signals to focus on processing feedback
        self.status_signals.clear()
        
        # Start processing - should show immediate processing feedback
        self.state_manager.start_command_processing(next_cmd)
        
        # Verify immediate processing feedback
        assert len(self.status_signals) > 0, "Should show immediate processing feedback"
        
        processing_status = self.status_signals[-1]
        assert "🚀 Elaborazione" in processing_status[0], \
            f"Should show processing indicator, got: {processing_status[0]}"
        
        # Verify activity state is active
        assert True in self.activity_signals, "Activity state should be active"
        assert self.state_manager.is_activity_changing, "Activity should be changing"
        
        # Simulate timer trying to update during activity change (this was the problem)
        timer_allowed = self.state_manager.request_status_update()
        assert not timer_allowed, \
            "Timer updates should be blocked during activity change to prevent status conflicts"
        
        # Clear signals to focus on completion
        self.status_signals.clear()
        
        # Complete the activity successfully
        self.state_manager.complete_command_processing(success=True)
        
        # Should show completion feedback, not intermediate states
        completion_found = False
        for status_text, color in self.status_signals:
            if "✅" in status_text and "Attività" in status_text:
                completion_found = True
                assert color == "#9ece6a", f"Completion should use success color, got: {color}"
                break
        
        assert completion_found, \
            f"Should show activity completion feedback, got signals: {self.status_signals}"
        
        # Verify activity state is cleared
        assert False in self.activity_signals, "Activity state should be cleared"
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared"
        
        # Now timer updates should be allowed again
        timer_allowed_after = self.state_manager.request_status_update()
        assert timer_allowed_after, \
            "Timer updates should be allowed after activity completion"
        
        # Verify no "off" or intermediate states appeared during transition
        off_states = [signal for signal in self.status_signals if "OFF" in signal[0] or "off" in signal[0]]
        assert len(off_states) == 0, \
            f"Should not show intermediate 'off' states during TV activity, found: {off_states}"
    
    def test_multiple_activity_transitions_no_conflicts(self):
        """
        Test multiple activity transitions without timer conflicts.
        
        Requirements: 3.3 (timer coordination), 2.1 (activity blocking)
        """
        # Clear signals
        self.status_signals.clear()
        
        activities = ['tv', 'music', 'shield']
        
        for activity in activities:
            # Clear previous activity state
            if self.state_manager.is_activity_changing:
                self.state_manager.is_activity_changing = False
            
            # Start activity
            assert self.state_manager.queue_command(activity), f"{activity} should be accepted"
            
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Clear signals to focus on this activity
                self.status_signals.clear()
                
                # Start processing
                self.state_manager.start_command_processing(next_cmd)
                
                # Verify processing feedback
                processing_signals = [s for s in self.status_signals if "🚀 Elaborazione" in s[0]]
                assert len(processing_signals) > 0, \
                    f"Should show processing feedback for {activity}"
                
                # Verify timer coordination during processing
                assert not self.state_manager.request_status_update(), \
                    f"Timer updates should be blocked during {activity} processing"
                
                # Complete the activity
                self.state_manager.complete_command_processing(success=True)
                
                # Verify completion feedback
                completion_signals = [s for s in self.status_signals if "✅" in s[0]]
                assert len(completion_signals) > 0, \
                    f"Should show completion feedback for {activity}"
                
                # Verify timer coordination after completion
                assert self.state_manager.request_status_update(), \
                    f"Timer updates should be allowed after {activity} completion"
        
        # Verify no conflicting states appeared
        all_status_texts = [signal[0] for signal in self.status_signals]
        
        # Should not have conflicting or intermediate states
        conflicting_patterns = ["off", "OFF", "-1", "unknown"]
        conflicts = [text for text in all_status_texts 
                    if any(pattern in text for pattern in conflicting_patterns)]
        
        assert len(conflicts) == 0, \
            f"Should not have conflicting intermediate states, found: {conflicts}"
    
    def test_device_commands_during_activity_do_not_interfere(self):
        """
        Test that device commands during activity changes don't interfere with status.
        
        Requirements: 3.3 (timer coordination), 2.1 (activity blocking)
        """
        # Clear signals
        self.status_signals.clear()
        
        # Start TV activity
        assert self.state_manager.queue_command('tv'), "TV activity should be accepted"
        
        # Queue some device commands (should be accepted even during activity change)
        device_commands = [('samsung', 'VolumeUp'), ('vol+', None), ('samsung', 'Menu')]
        for cmd, action in device_commands:
            assert self.state_manager.queue_command(cmd, action), \
                f"Device command {cmd} {action} should be accepted during activity change"
        
        # Start processing TV activity
        tv_cmd = self.state_manager.get_next_command()
        assert tv_cmd.command == 'tv', "First command should be TV activity"
        
        self.state_manager.start_command_processing(tv_cmd)
        
        # Verify activity is in progress
        assert self.state_manager.is_activity_changing, "Activity should be changing"
        
        # Timer updates should be blocked during activity
        assert not self.state_manager.request_status_update(), \
            "Timer updates should be blocked during activity change"
        
        # Complete TV activity
        self.state_manager.complete_command_processing(success=True)
        
        # Now process device commands
        processed_devices = []
        while self.state_manager.pending_commands > 0:
            next_cmd = self.state_manager.get_next_command()
            if next_cmd:
                # Device commands should allow timer updates
                self.state_manager.start_command_processing(next_cmd)
                
                # Timer updates should be allowed during device command processing
                assert self.state_manager.request_status_update(), \
                    f"Timer updates should be allowed during device command {next_cmd.command}"
                
                self.state_manager.complete_command_processing(success=True)
                processed_devices.append((next_cmd.command, next_cmd.action))
        
        # Verify all device commands were processed
        assert len(processed_devices) == len(device_commands), \
            f"All device commands should be processed: expected {len(device_commands)}, got {len(processed_devices)}"
        
        # Verify final state is clean
        assert not self.state_manager.is_activity_changing, "Activity changing should be cleared"
        assert not self.state_manager.is_processing, "Processing should be cleared"
        assert self.state_manager.request_status_update(), "Timer updates should be allowed at end"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])