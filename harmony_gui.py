#!/usr/bin/env python3
"""🌃 Harmony Hub - Modern Tokyo Night 2025"""

import sys
import time
import asyncio
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QObject, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QIcon, QPainter, QPen

# Import diretto (assumendo che harmony.py sia nello stesso path)
import harmony
from harmony import FastHarmonyHub, DEVICES, ACTIVITIES, AUDIO_COMMANDS

# 🎨 Palette Tokyo Night Modern (Minimal)
C = {
    'bg':      '#1a1b26',  # Deep Night
    'surface': '#24283b',  # Storm
    'active':  '#7aa2f7',  # Blue
    'accent':  '#bb9af7',  # Purple
    'danger':  '#f7768e',  # Red (muted usage)
    'text':    '#c0caf5',  # White-ish
    'subtext': '#565f89',  # Grey
    'border':  '#414868',  # Highlight
}

# 🔧 Device Helper Functions for flexible device detection
def find_device_by_type(device_type_keywords):
    """Find device by type keywords (case insensitive)"""
    for alias, device_info in DEVICES.items():
        device_name = device_info.get('name', '').lower()
        for keyword in device_type_keywords:
            if keyword.lower() in device_name:
                return alias, device_info
    return None, None

def find_audio_device():
    """Find the primary audio device (receiver, amplifier, etc.)"""
    audio_keywords = ['receiver', 'amplifier', 'amp', 'audio', 'stereo', 'soundbar', 'onkyo']
    return find_device_by_type(audio_keywords)

def find_tv_device():
    """Find the primary TV device"""
    tv_keywords = ['tv', 'television', 'samsung', 'lg', 'sony']
    return find_device_by_type(tv_keywords)

def find_shield_device():
    """Find NVIDIA Shield or similar streaming device"""
    shield_keywords = ['shield', 'nvidia', 'streaming']
    return find_device_by_type(shield_keywords)

def find_climate_device():
    """Find climate/air conditioning device"""
    climate_keywords = ['clima', 'air conditioner', 'conditioner', 'climatizzatore']
    return find_device_by_type(climate_keywords)

STYLESHEET = f"""
    QMainWindow {{
        background-color: {C['bg']};
    }}
    
    QLabel {{
        color: {C['text']};
        font-family: 'Noto Sans', 'Segoe UI', sans-serif;
    }}
    
    QLabel#Header {{
        color: {C['active']};
        font-weight: bold;
        font-size: 11px;
        text-transform: uppercase;
        padding-left: 2px;
        margin-top: 0px;
        margin-bottom: 0px;
    }}

    QFrame#Card {{
        background-color: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 12px;
    }}

    QPushButton {{
        background-color: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        color: {C['text']};
        padding: 6px;
        font-family: 'Noto Sans', sans-serif;
        font-size: 13px;
    }}
    
    QPushButton:hover {{
        background-color: {C['border']};
        border-color: {C['active']};
        color: #ffffff;
    }}
    
    QPushButton:pressed {{
        background-color: {C['active']};
        border-color: {C['active']};
        color: {C['bg']};
    }}



    QLabel#Status {{
        background-color: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        color: {C['active']};
        padding: 8px;
        font-weight: bold;
        font-size: 14px;
    }}
"""

class HarmonyWorker(QThread):
    """Worker persistente che mantiene la connessione WebSocket attiva"""
    result_ready = pyqtSignal(str, object)
    status_updated = pyqtSignal(str)
    
    # Progress notification signals for StateManager integration
    command_started = pyqtSignal(str, str)  # (command, action)
    command_progress = pyqtSignal(str, str, str)  # (command, action, progress_message)
    command_completed = pyqtSignal(str, str, bool, str)  # (command, action, success, message)

    def __init__(self, state_manager=None):
        super().__init__()
        self.loop = None
        self.hub = None
        self._cmd_queue = asyncio.Queue()
        self._running = True
        self.state_manager = state_manager
        
        # Device command throttling state
        self._last_device_command_time = 0.0
        self._device_command_min_interval = 0.05  # 50ms minimum between device commands

    def run(self):
        """Esegue il loop asyncio in un thread separato"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._async_main())

    async def _async_main(self):
        self.hub = FastHarmonyHub()
        try:
            await self.hub.connect()
            
            while self._running:
                # Attende comandi dalla coda
                try:
                    cmd_data = await asyncio.wait_for(self._cmd_queue.get(), timeout=1.0)
                    cmd_type, args = cmd_data
                    
                    if cmd_type == "stop":
                        break
                    elif cmd_type == "command":
                        await self._handle_command(args)
                    elif cmd_type == "status":
                        await self._handle_status()
                        
                except asyncio.TimeoutError:
                    # Keepalive / status update periodico se necessario
                    pass
                except Exception as e:
                    print(f"Error in worker loop: {e}")

        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            await self.hub.close()

    async def _handle_command(self, args):
        cmd, action = args
        cmd = cmd.lower()
        res = {"error": "Unknown command"}
        
        # Import here to avoid circular imports
        try:
            from config import ACTIVITIES, DEVICES, AUDIO_COMMANDS
        except ImportError:
            ACTIVITIES = {}
            DEVICES = {}
            AUDIO_COMMANDS = {}
        
        # Emit command started signal for progress tracking
        self.command_started.emit(cmd, action or "")
        
        # Integrate with StateManager for sequential processing
        if self.state_manager:
            # Get the next command from StateManager queue in proper order
            next_command = self.state_manager.get_next_command()
            if next_command:
                # Verify this is the command we expect to process
                if (next_command.command.lower() != cmd or 
                    (next_command.action or "").lower() != (action or "").lower()):
                    error_msg = f"Command order mismatch: expected {next_command.command} {next_command.action or ''}, got {cmd} {action or ''}"
                    print(f"ERROR: {error_msg}")
                    self.command_completed.emit(cmd, action or "", False, error_msg)
                    self.result_ready.emit(f"{cmd} {action or ''}", {"error": error_msg})
                    
                    # Use enhanced error handling
                    if self.state_manager:
                        self.state_manager.handle_command_error(cmd, action, error_msg)
                    return
                
                # Ensure sequential processing order is maintained
                if not self.state_manager.ensure_sequential_processing():
                    error_msg = "Sequential processing order violation detected"
                    print(f"ERROR: {error_msg}")
                    self.command_completed.emit(cmd, action or "", False, error_msg)
                    self.result_ready.emit(f"{cmd} {action or ''}", {"error": error_msg})
                    
                    # Use enhanced error handling
                    if self.state_manager:
                        self.state_manager.handle_command_error(cmd, action, error_msg)
                    return
                
                # Start processing this command
                self.state_manager.start_command_processing(next_command)
            else:
                # No command in queue or processing blocked
                error_msg = "No command available for processing or processing blocked"
                self.command_completed.emit(cmd, action or "", False, error_msg)
                self.result_ready.emit(f"{cmd} {action or ''}", {"error": error_msg})
                
                # Use enhanced error handling
                if self.state_manager:
                    self.state_manager.handle_command_error(cmd, action, error_msg)
                return
        
        try:
            # Emit progress signal
            self.command_progress.emit(cmd, action or "", "Executing command...")
            
            # Apply minimal throttling for device commands to prevent Hub overload
            # while still accepting and queuing all commands (Requirement 2.3)
            if self.state_manager:
                command_type = self.state_manager.classify_command(cmd, action)
                if command_type.value in ['device', 'audio']:  # Device and audio commands need throttling
                    current_time = time.time()
                    time_since_last = current_time - self._last_device_command_time
                    if time_since_last < self._device_command_min_interval:
                        # Wait for the remaining time to maintain minimum interval
                        sleep_time = self._device_command_min_interval - time_since_last
                        await asyncio.sleep(sleep_time)
                    self._last_device_command_time = time.time()
            
            # 0. SMART COMMANDS (Routing dinamico basato sull'attività)
            if cmd.startswith("smart_"):
                real_cmd = cmd.replace("smart_", "")
                # Recupera attività corrente
                try:
                    curr = await self.hub.get_current_fast()
                    act_id = "-1"
                    if "data" in curr and "result" in curr["data"]:
                        act_id = curr["data"]["result"]
                except Exception as e:
                    # Handle network/timeout errors gracefully
                    if self.state_manager:
                        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                            self.state_manager.handle_timeout_error("get current activity", 2.0)
                        else:
                            self.state_manager.handle_network_error(str(e))
                    raise e
                
                # Determina il target device in base all'attività
                target_dev = None
                
                # Mappa ID Attività -> Device ID
                # Get activity IDs dynamically from config
                tv_act_id = None
                shield_act_id = None  
                music_act_id = None
                
                for alias, activity_info in ACTIVITIES.items():
                    activity_name = activity_info.get('name', '').lower()
                    if 'tv' in activity_name or 'guarda' in activity_name:
                        tv_act_id = activity_info.get('id')
                    elif 'shield' in activity_name:
                        shield_act_id = activity_info.get('id')
                    elif 'music' in activity_name or 'ascolta' in activity_name:
                        music_act_id = activity_info.get('id')
                
                # Find appropriate device based on current activity
                if act_id == tv_act_id:
                    tv_alias, tv_device = find_tv_device()
                    if tv_device:
                        target_dev = tv_device["id"]
                elif act_id == shield_act_id:
                    shield_alias, shield_device = find_shield_device()
                    if shield_device:
                        target_dev = shield_device["id"]
                elif act_id == music_act_id:
                    audio_alias, audio_device = find_audio_device()
                    if audio_device:
                        target_dev = audio_device["id"]
                
                # Fallback: if we're in TV mode or undefined, try TV device if command is compatible
                if not target_dev:
                    tv_alias, tv_device = find_tv_device()
                    if tv_device:
                        target_dev = tv_device["id"]

                if target_dev:
                    # Validate smart device command before sending (Requirement 2.2)
                    if not self._validate_device_id_command(target_dev, action):
                        error_msg = f"Invalid smart device command: device ID '{target_dev}' validation failed"
                        res = {"error": error_msg}
                    else:
                        # Mappature comandi specifici per device se necessario (es. "Select" vs "OK")
                        # Per ora assumiamo che Harmony usi nomi standard (DirectionUp, Select, ecc.)
                        res = await self.hub.send_device_fast(target_dev, action)
                else:
                    res = {"error": "No target device for smart command"}

            # Logica duplicata da harmony.py main() ma adattata
            # 1. ATTIVITÀ (Priorità Alta per catturare 'off')
            elif cmd in ACTIVITIES:
                self.command_progress.emit(cmd, action or "", "Starting activity...")
                res = await self.hub.start_activity_fast(ACTIVITIES[cmd]["id"])
            
            # 2. AUDIO COMMANDS
            elif cmd in AUDIO_COMMANDS:
                audio_alias, audio_device = find_audio_device()
                if audio_device:
                    # Validate audio device command before sending (Requirement 2.2)
                    if not self._validate_device_id_command(audio_device["id"], AUDIO_COMMANDS[cmd]):
                        error_msg = f"Invalid audio command: device validation failed for '{cmd}'"
                        res = {"error": error_msg}
                    else:
                        res = await self.hub.send_device_fast(audio_device["id"], AUDIO_COMMANDS[cmd])
                else:
                    res = {"error": "No audio device found in configuration"}
            
            # 3. DISPOSITIVI
            elif cmd in DEVICES and action:
                # Validate device exists before sending command (Requirement 2.2)
                if not self._validate_device_command(cmd, action):
                    error_msg = f"Invalid device command: device '{cmd}' not found in configuration"
                    res = {"error": error_msg}
                else:
                    device = DEVICES[cmd]
                    res = await self.hub.send_device_fast(device["id"], action)
                
            elif cmd == "audio-on":
                audio_alias, audio_device = find_audio_device()
                if audio_device:
                    # Validate audio device command before sending (Requirement 2.2)
                    if not self._validate_device_id_command(audio_device["id"], "PowerOn"):
                        error_msg = "Invalid audio-on command: device validation failed"
                        res = {"error": error_msg}
                    else:
                        res = await self.hub.send_device_fast(audio_device["id"], "PowerOn")
                else:
                    res = {"error": "No audio device found in configuration"}
            elif cmd == "audio-off":
                audio_alias, audio_device = find_audio_device()
                if audio_device:
                    # Validate audio device command before sending (Requirement 2.2)
                    if not self._validate_device_id_command(audio_device["id"], "PowerOff"):
                        error_msg = "Invalid audio-off command: device validation failed"
                        res = {"error": error_msg}
                    else:
                        res = await self.hub.send_device_fast(audio_device["id"], "PowerOff")
                else:
                    res = {"error": "No audio device found in configuration"}
            
            # Fallback per 'off' se non definito in ACTIVITIES ma richiesto esplicitamente come attività di sistema
            elif cmd == "off":
                 # PowerOff activity is typically -1
                self.command_progress.emit(cmd, action or "", "Powering off...")
                res = await self.hub.start_activity_fast("-1")

            # Determine success based on response
            success = "error" not in res
            message = res.get("error", "Command completed successfully")
            
            # Enhanced TV command feedback
            if self._is_tv_command_execution(cmd, action):
                if success:
                    # Provide TV-specific success message
                    tv_message = self._get_tv_success_message(action)
                    message = tv_message
                    print(f"TV command completed: {tv_message}")
                else:
                    # Provide TV-specific error message
                    tv_error = self._get_tv_error_message(message)
                    message = tv_error
                    print(f"TV command failed: {tv_error}")
            
            # Handle specific error types for better user experience
            if not success:
                error_msg = res.get("error", "Unknown error")
                if self.state_manager:
                    self.state_manager.handle_command_error(cmd, action, error_msg)
                else:
                    # Fallback if no StateManager
                    self.command_completed.emit(cmd, action or "", False, error_msg)
            else:
                # Emit completion signal for successful commands
                self.command_completed.emit(cmd, action or "", success, message)
            
            # Update StateManager if available - ensure sequential processing continues
            if self.state_manager:
                self.state_manager.complete_command_processing(success=success, error_message=message if not success else None)
                
                # Verify sequential processing is still maintained after completion
                if not self.state_manager.ensure_sequential_processing():
                    print("WARNING: Sequential processing order violated after command completion")
            
            self.result_ready.emit(f"{cmd} {action or ''}", res)
            
        except asyncio.TimeoutError as e:
            error_msg = f"Command timed out: {cmd} {action or ''}"
            print(f"TIMEOUT: {error_msg}")
            
            # Handle timeout error gracefully
            if self.state_manager:
                self.state_manager.handle_timeout_error(f"{cmd} {action or ''}", 10.0)
            
            # Emit completion signal with timeout error
            self.command_completed.emit(cmd, action or "", False, error_msg)
            self.result_ready.emit(f"{cmd} {action or ''}", {"error": error_msg})
            
        except (aiohttp.ClientError, ConnectionError, OSError) as e:
            error_msg = f"Network error: {str(e)}"
            print(f"NETWORK ERROR: {error_msg}")
            
            # Handle network error gracefully
            if self.state_manager:
                self.state_manager.handle_network_error(str(e))
            
            # Emit completion signal with network error
            self.command_completed.emit(cmd, action or "", False, error_msg)
            self.result_ready.emit(f"{cmd} {action or ''}", {"error": error_msg})
            
        except Exception as e:
            error_msg = str(e)
            print(f"GENERAL ERROR: {error_msg}")
            
            # Handle general error gracefully
            if self.state_manager:
                self.state_manager.handle_command_error(cmd, action, error_msg)
            
            # Emit completion signal with error
            self.command_completed.emit(cmd, action or "", False, error_msg)
            self.result_ready.emit(f"{cmd} {action or ''}", {"error": error_msg})

    async def _handle_status(self):
        try:
            # Emit progress signal for status check
            self.command_progress.emit("status", "", "Checking current status...")
            
            res = await self.hub.get_current_fast()
            if "data" in res and "result" in res["data"]:
                activity_id = res["data"]["result"]
                status_text = "..."
                if activity_id == "-1":
                    status_text = "⚫ OFF"
                else:
                    for name, info in ACTIVITIES.items():
                        if info["id"] == activity_id:
                            status_text = f"🟢 {info['name']}"
                            break
                    else:
                        status_text = f"🟡 ID: {activity_id}"
                
                # Update StateManager if available
                if self.state_manager:
                    # Extract activity name for StateManager
                    activity_name = "off" if activity_id == "-1" else activity_id
                    for name, info in ACTIVITIES.items():
                        if info["id"] == activity_id:
                            activity_name = name
                            break
                    self.state_manager.update_current_activity(activity_name)
                
                self.status_updated.emit(status_text)
                
        except asyncio.TimeoutError as e:
            print(f"Status check timed out: {e}")
            if self.state_manager:
                self.state_manager.handle_timeout_error("status check", 2.0)
            else:
                self.status_updated.emit("❌ Timeout")
                
        except (aiohttp.ClientError, ConnectionError, OSError) as e:
            print(f"Network error during status check: {e}")
            if self.state_manager:
                self.state_manager.handle_network_error(str(e))
            else:
                self.status_updated.emit("❌ Errore rete")
                
        except Exception as e:
            print(f"General error during status check: {e}")
            if self.state_manager:
                self.state_manager.handle_command_error("status", "", str(e))
            else:
                self.status_updated.emit("❌ Error")

    def queue_command(self, cmd, action=None):
        if self.loop:
            self.loop.call_soon_threadsafe(self._cmd_queue.put_nowait, ("command", (cmd, action)))

    def queue_status(self):
        if self.loop:
             self.loop.call_soon_threadsafe(self._cmd_queue.put_nowait, ("status", None))

    def _validate_device_command(self, device_alias: str, action: str) -> bool:
        """
        Validate that a device command is valid before sending.
        
        Args:
            device_alias: The device alias to validate
            action: The action to perform on the device
            
        Returns:
            bool: True if device exists and command is valid, False otherwise
            
        Requirements: 2.2 (device command validation)
        """
        if not device_alias or not action:
            return False
            
        try:
            # Import here to avoid circular imports
            from config import DEVICES
            
            # Check if device exists in configuration
            if device_alias not in DEVICES:
                return False
                
            # Validate device has required fields
            device_info = DEVICES[device_alias]
            if not isinstance(device_info, dict):
                return False
                
            # Device must have an ID to send commands
            if 'id' not in device_info or not device_info['id']:
                return False
                
            # Action must be non-empty string
            if not action.strip():
                return False
                
            return True
            
        except ImportError:
            # If config is not available, consider invalid
            return False
        except Exception as e:
            # Log validation error for debugging
            print(f"Device validation error: {e}")
            return False

    def _validate_device_id_command(self, device_id: str, action: str) -> bool:
        """
        Validate that a device ID command is valid before sending.
        
        Args:
            device_id: The device ID to validate
            action: The action to perform on the device
            
        Returns:
            bool: True if device ID exists and command is valid, False otherwise
            
        Requirements: 2.2 (device command validation)
        """
        if not device_id or not action:
            return False
            
        try:
            # Import here to avoid circular imports
            from config import DEVICES
            
            # Check if device ID exists in any device configuration
            device_found = False
            for alias, device_info in DEVICES.items():
                if isinstance(device_info, dict) and device_info.get('id') == device_id:
                    device_found = True
                    break
                    
            if not device_found:
                return False
                
            # Action must be non-empty string
            if not action.strip():
                return False
                
            return True
            
        except ImportError:
            # If config is not available, consider invalid
            return False
        except Exception as e:
            # Log validation error for debugging
            print(f"Device ID validation error: {e}")
            return False

    def _is_tv_command_execution(self, cmd: str, action: Optional[str]) -> bool:
        """
        Check if a command execution is for a TV device.
        
        Args:
            cmd: The command being executed
            action: The action being executed
            
        Returns:
            bool: True if this is a TV command execution
            
        Requirements: 3.1, 3.2 (TV command feedback detection)
        """
        if not cmd:
            return False
            
        try:
            # Import here to avoid circular imports
            from config import DEVICES
            
            # Check if cmd is a TV device alias
            if cmd in DEVICES:
                device_info = DEVICES[cmd]
                device_name = device_info.get('name', '').lower()
                tv_keywords = ['tv', 'television', 'samsung', 'lg', 'sony']
                if any(keyword in device_name for keyword in tv_keywords):
                    return True
                    
        except ImportError:
            pass
        
        # Check if action indicates TV command
        if action:
            tv_actions = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 
                         'Red', 'Green', 'Yellow', 'Blue', 
                         'Info', 'Guide', 'SmartHub', 'List']
            return action in tv_actions
            
        return False
    
    def _get_tv_success_message(self, action: Optional[str]) -> str:
        """
        Get TV-specific success message.
        
        Args:
            action: The TV action that succeeded
            
        Returns:
            str: TV-specific success message
            
        Requirements: 3.1, 3.2 (TV command success feedback)
        """
        if not action:
            return "TV command completed"
            
        # Provide user-friendly feedback for different TV actions
        feedback_map = {
            '0': 'TV Channel 0 selected',
            '1': 'TV Channel 1 selected', '2': 'TV Channel 2 selected', '3': 'TV Channel 3 selected',
            '4': 'TV Channel 4 selected', '5': 'TV Channel 5 selected', '6': 'TV Channel 6 selected',
            '7': 'TV Channel 7 selected', '8': 'TV Channel 8 selected', '9': 'TV Channel 9 selected',
            'Red': 'TV Red button pressed',
            'Green': 'TV Green button pressed',
            'Yellow': 'TV Yellow button pressed',
            'Blue': 'TV Blue button pressed',
            'Info': 'TV Info displayed',
            'Guide': 'TV Guide opened',
            'SmartHub': 'TV Smart Hub opened',
            'List': 'TV Channel List opened'
        }
        
        return feedback_map.get(action, f"TV {action} completed")
    
    def _get_tv_error_message(self, error_message: str) -> str:
        """
        Get TV-specific error message.
        
        Args:
            error_message: The original error message
            
        Returns:
            str: TV-specific error message
            
        Requirements: 3.1, 3.2 (TV command error feedback)
        """
        if not error_message:
            return "TV command failed"
            
        # Provide user-friendly TV error messages
        message_lower = error_message.lower()
        
        if "not configured" in message_lower or "not found" in message_lower:
            return "TV device not configured in Harmony Hub"
        elif "validation failed" in message_lower:
            return "Invalid TV command - check device configuration"
        elif "network" in message_lower or "connection" in message_lower:
            return "TV connection error - check Harmony Hub network"
        elif "timeout" in message_lower:
            return "TV response timeout - device may be off or unresponsive"
        else:
            return f"TV command error: {error_message}"

    def stop(self):
        self._running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self._cmd_queue.put_nowait, ("stop", None))
        self.wait()

class ModernBtn(QPushButton):
    def __init__(self, text, cmd, icon=None):
        super().__init__()
        if icon:
            self.setText(f"{icon}  {text}" if text else icon)
        else:
            self.setText(text)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)
        
        self.cmd = cmd

class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Import StateManager here to avoid circular imports
        from state_manager import StateManager
        
        # Create StateManager instance
        self.state_manager = StateManager()
        
        # Create HarmonyWorker with StateManager integration
        self.worker = HarmonyWorker(state_manager=self.state_manager)
        self.worker.result_ready.connect(self.on_done)
        self.worker.status_updated.connect(self.on_status)
        
        # Connect to new progress signals for enhanced feedback
        self.worker.command_started.connect(self.on_command_started)
        self.worker.command_progress.connect(self.on_command_progress)
        self.worker.command_completed.connect(self.on_command_completed)
        
        # Connect StateManager signals for centralized state updates
        self.state_manager.status_changed.connect(self.on_state_status_changed)
        self.state_manager.buttons_state_changed.connect(self.on_buttons_state_changed)
        self.state_manager.queue_size_changed.connect(self.on_queue_size_changed)
        
        self.worker.start()

        self.setWindowTitle("Harmony")
        # Layout generoso e pulito
        self.setFixedWidth(420)
        # Altezza minima garantita per evitare schiacciamenti
        # self.setMinimumHeight(600)  <-- RIMOSSO (lasciamo auto-size)
        
        c = QWidget()
        self.setCentralWidget(c)
        main_layout = QVBoxLayout(c)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # 1. Header & Status
        status_layout = QVBoxLayout()
        status_layout.setSpacing(4)
        
        title = QLabel("CURRENT ACTIVITY")
        title.setObjectName("Header")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.status = QLabel("...")
        self.status.setObjectName("Status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        status_layout.addWidget(title)
        status_layout.addWidget(self.status)
        
        # Power Off Button
        self.btn_off = self.create_btn("SPEGNI TUTTO", "off", "⏻")
        self.btn_off.setFixedHeight(40)
        # Usa QFont per colorare solo l'icona tramite stylesheet mirato
        self.btn_off.setStyleSheet(f"""
            QPushButton {{
                color: {C['danger']};
            }}
            QPushButton:hover {{
                color: {C['text']};
            }}
            QPushButton:disabled {{
                color: {C['subtext']};
                background-color: {C['bg']};
            }}
        """)
        status_layout.addWidget(self.btn_off)
        
        main_layout.addLayout(status_layout)
        
        # 2. Activities Grid
        self.add_section_header(main_layout, "SCENARI")
        
        act_frame = QFrame()
        act_frame.setObjectName("Card")
        act_grid = QGridLayout(act_frame)
        act_grid.setSpacing(12)
        act_grid.setContentsMargins(16, 16, 16, 16)
        
        # Generate activities dynamically from config
        activities = []
        
        # Define icons for different activity types
        activity_icons = {
            'tv': '📺', 'guarda': '📺', 'watch': '📺', 'television': '📺',
            'music': '🎵', 'ascolta': '🎵', 'listen': '🎵', 'audio': '🎵',
            'shield': '🎮', 'game': '🎮', 'gaming': '🎮', 'nvidia': '🎮',
            'clima': '❄️', 'climate': '❄️', 'air': '❄️', 'conditioner': '❄️', 'condizionatore': '❄️',
            'off': '⚫', 'poweroff': '⚫'
        }
        
        for alias, activity_info in ACTIVITIES.items():
            activity_name = activity_info.get('name', alias)
            
            # Find appropriate icon based on activity name or alias
            icon = '🎯'  # default icon
            name_lower = activity_name.lower()
            alias_lower = alias.lower()
            
            for keyword, emoji in activity_icons.items():
                if keyword in name_lower or keyword in alias_lower:
                    icon = emoji
                    break
            
            # Use the display name from config, but keep the alias for commands
            display_name = activity_name
            if len(display_name) > 12:  # Truncate long names for UI
                display_name = display_name[:12] + "..."
                
            activities.append((display_name, alias, icon))
        
        # Store activity buttons for state management (Requirement 4.3)
        self.activity_buttons = []
        
        for i, (txt, cmd, ico) in enumerate(activities):
            b = self.create_btn(txt, cmd, ico)
            act_grid.addWidget(b, i // 2, i % 2)
            self.activity_buttons.append(b)
            
        main_layout.addWidget(act_frame)

        # 3. SMART REMOTE
        self.add_section_header(main_layout, "SMART REMOTE")
        
        remote_frame = QFrame()
        remote_frame.setObjectName("Card")
        remote_layout = QHBoxLayout(remote_frame)
        remote_layout.setSpacing(16) 
        remote_layout.setContentsMargins(12, 12, 12, 12)
        
        # --- LEFT: SMART D-PAD & NAV ---
        smart_col = QVBoxLayout()
        smart_col.setSpacing(8) # Ridotto da 10
        
        lbl_smart = QLabel("NAVIGATION (Auto)")
        lbl_smart.setStyleSheet(f"color: {C['active']}; font-weight: bold; font-size: 10px;")
        lbl_smart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        smart_col.addWidget(lbl_smart)
        
        # D-Pad
        dpad = QGridLayout()
        dpad.setSpacing(8)
        
        # Smart commands: "smart_ " + action
        d_up = self.create_btn("", "smart_ DirectionUp", "▴")
        d_down = self.create_btn("", "smart_ DirectionDown", "▾")
        d_left = self.create_btn("", "smart_ DirectionLeft", "◂")
        d_right = self.create_btn("", "smart_ DirectionRight", "▸")
        d_ok = self.create_btn("OK", "smart_ Select", "")
        
        for b in [d_up, d_down, d_left, d_right, d_ok]:
            b.setFixedSize(40, 40)
            if b != d_ok: b.setStyleSheet(b.styleSheet() + "font-size: 18px;")
            else: b.setStyleSheet(b.styleSheet() + f"background: {C['active']}; color: {C['bg']}; font-weight: bold; font-size: 12px;")

        dpad.addWidget(d_up, 0, 1)
        dpad.addWidget(d_left, 1, 0)
        dpad.addWidget(d_ok, 1, 1)
        dpad.addWidget(d_right, 1, 2)
        dpad.addWidget(d_down, 2, 1)
        
        smart_col.addLayout(dpad)
        
        # Smart Nav Actions (Home, Back, Menu, Exit)
        nav_acts = QGridLayout()
        nav_acts.setSpacing(8)
        
        # Questi potrebbero essere smart o fissi. Home/Back spesso variano.
        # Usiamo smart per coerenza
        n_home = self.create_btn("Home", "smart_ Home", "🏠")
        n_back = self.create_btn("Back", "smart_ Back", "↩️") # Back command for consistency with device buttons
        n_menu = self.create_btn("Menu", "smart_ Menu", "☰")
        n_exit = self.create_btn("Exit", "smart_ Exit", "✖️")
        
        for b in [n_home, n_back, n_menu, n_exit]:
            b.setFixedSize(70, 36)
            
        nav_acts.addWidget(n_menu, 0, 0)
        nav_acts.addWidget(n_home, 0, 1)
        nav_acts.addWidget(n_back, 1, 0)
        nav_acts.addWidget(n_exit, 1, 1)
        
        smart_col.addLayout(nav_acts)
        smart_col.addStretch()
        
        remote_layout.addLayout(smart_col)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background: {C['border']}; width: 1px;")
        remote_layout.addWidget(line)

        # --- RIGHT: TV NUMPAD & EXTRA ---
        tv_col = QVBoxLayout()
        tv_col.setSpacing(8) # Ridotto da 10
        
        # Check if TV device is available for better user feedback
        tv_available = self.is_tv_device_available()
        
        lbl_tv = QLabel("TV CONTROLS")
        if not tv_available:
            lbl_tv.setText("TV CONTROLS (UNAVAILABLE)")
            lbl_tv.setStyleSheet(f"color: {C['subtext']}; font-weight: bold; font-size: 10px;")
            lbl_tv.setToolTip(self.get_tv_unavailable_message())
        else:
            lbl_tv.setStyleSheet(f"color: {C['active']}; font-weight: bold; font-size: 10px;")
        lbl_tv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tv_col.addWidget(lbl_tv)
        
        numpad = QGridLayout()
        numpad.setSpacing(10) # Aumentato spaziatura verticale/orizzontale
        
        # 1-9
        for i in range(1, 10):
            if tv_available:
                tv_cmd = self.create_tv_command(str(i))
                if tv_cmd:
                    b = self.create_btn(str(i), tv_cmd)
                else:
                    b = self.create_disabled_btn(str(i), "TV command generation failed")
            else:
                b = self.create_disabled_btn(str(i), self.get_tv_unavailable_message())
            b.setFixedSize(56, 36)
            numpad.addWidget(b, (i-1)//3, (i-1)%3)
            
        # 0 & others
        if tv_available:
            list_cmd = self.create_tv_command("List")
            zero_cmd = self.create_tv_command("0")
            
            if list_cmd:
                b_list = self.create_btn("List", list_cmd, "📑")
            else:
                b_list = self.create_disabled_btn("List", "TV command generation failed", "📑")
                
            if zero_cmd:
                b_0 = self.create_btn("0", zero_cmd)
            else:
                b_0 = self.create_disabled_btn("0", "TV command generation failed")
        else:
            b_list = self.create_disabled_btn("List", self.get_tv_unavailable_message(), "📑")
            b_0 = self.create_disabled_btn("0", self.get_tv_unavailable_message())
        
        for b in [b_list, b_0]: b.setFixedSize(56, 36)
        
        numpad.addWidget(b_list, 3, 0)
        numpad.addWidget(b_0, 3, 1)
        # PrevChannel rimosso
        
        tv_col.addLayout(numpad)
        
        # Color Keys & Info
        colors = QHBoxLayout()
        colors.setSpacing(6)
        for col, cmd in [("#f7768e", "Red"), ("#9ece6a", "Green"), ("#e0af68", "Yellow"), ("#7aa2f7", "Blue")]:
            if tv_available:
                tv_cmd = self.create_tv_command(cmd)
                if tv_cmd:
                    b = self.create_btn("", tv_cmd)
                else:
                    b = self.create_disabled_btn("", "TV command generation failed")
            else:
                b = self.create_disabled_btn("", self.get_tv_unavailable_message())
            b.setFixedSize(24, 24)
            if tv_available and tv_cmd:
                b.setStyleSheet(f"background-color: {col}; border: none; border-radius: 12px;")
            else:
                # Disabled color buttons have muted appearance
                b.setStyleSheet(f"background-color: {C['subtext']}; border: none; border-radius: 12px; opacity: 0.5;")
            colors.addWidget(b)
            
        tv_col.addLayout(colors)
        
        # Extra TV
        extra_tv = QHBoxLayout()
        
        if tv_available:
            info_cmd = self.create_tv_command("Info")
            guide_cmd = self.create_tv_command("Guide")
            hub_cmd = self.create_tv_command("SmartHub")
            
            if info_cmd:
                b_info = self.create_btn("Info", info_cmd)
            else:
                b_info = self.create_disabled_btn("Info", "TV command generation failed")
                
            if guide_cmd:
                b_guide = self.create_btn("Guide", guide_cmd)
            else:
                b_guide = self.create_disabled_btn("Guide", "TV command generation failed")
                
            if hub_cmd:
                b_hub = self.create_btn("Hub", hub_cmd)
            else:
                b_hub = self.create_disabled_btn("Hub", "TV command generation failed")
        else:
            b_info = self.create_disabled_btn("Info", self.get_tv_unavailable_message())
            b_guide = self.create_disabled_btn("Guide", self.get_tv_unavailable_message())
            b_hub = self.create_disabled_btn("Hub", self.get_tv_unavailable_message())
        
        for b in [b_info, b_guide, b_hub]: 
            b.setFixedHeight(30)
            extra_tv.addWidget(b)
            
        tv_col.addLayout(extra_tv)
        tv_col.addStretch()
        
        remote_layout.addLayout(tv_col)
        main_layout.addWidget(remote_frame)

        # 4. Audio & System
        self.add_section_header(main_layout, "AUDIO & SYSTEM")
        
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("Card")
        ctrl_layout = QGridLayout(ctrl_frame)
        ctrl_layout.setSpacing(10)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)
        
        ctrl_layout.addWidget(self.create_btn("", "vol-", "➖"), 0, 0)
        ctrl_layout.addWidget(self.create_btn("Mute", "mute", "🔇"), 0, 1)
        ctrl_layout.addWidget(self.create_btn("", "vol+", "➕"), 0, 2)
        
        main_layout.addWidget(ctrl_frame)

        # 5. Devices
        self.add_section_header(main_layout, "DISPOSITIVI")
        
        dev_frame = QFrame()
        dev_frame.setObjectName("Card")
        dev_layout = QVBoxLayout(dev_frame)
        dev_layout.setSpacing(8)
        dev_layout.setContentsMargins(12, 12, 12, 12)
        
        # Generate devices dynamically from config
        devices_to_show = []
        
        # Define common commands for different device types
        device_commands = {
            'tv': [("⏻", "PowerToggle"), ("⚙️", "SmartHub"), ("🏠", "Home")],
            'audio': [("📺", "ListeningModeTvLogic"), ("🎵", "ModeMusic"), ("🔇", "Muting")],
            'shield': [("🏠", "Home"), ("↩️", "Back"), ("⏸️", "Pause")],
            'climate': [("⏻", "PowerToggle"), ("❄️", "Cool"), ("🌡️", "Auto")],
            'game': [("🏠", "Home"), ("🎮", "Guide"), ("⏸️", "Pause")],
            'default': [("⏻", "PowerOn"), ("⏻", "PowerOff")]
        }
        
        for alias, device_info in DEVICES.items():
            device_name = device_info.get('name', alias)
            
            # Determine device type and appropriate commands
            name_lower = device_name.lower()
            alias_lower = alias.lower()
            
            commands = device_commands['default']  # fallback
            
            # Check for more specific matches first
            if any(keyword in name_lower or keyword in alias_lower 
                   for keyword in ['shield', 'nvidia']):
                commands = device_commands['shield']
            elif any(keyword in name_lower or keyword in alias_lower 
                     for keyword in ['receiver', 'audio', 'amplifier', 'onkyo', 'stereo']):
                commands = device_commands['audio']
            elif any(keyword in name_lower or keyword in alias_lower 
                     for keyword in ['xbox', 'playstation', 'ps3', 'game']):
                commands = device_commands['game']
            elif any(keyword in name_lower or keyword in alias_lower 
                     for keyword in ['clima', 'climate', 'air', 'conditioner']):
                commands = device_commands['climate']
            elif any(keyword in name_lower or keyword in alias_lower 
                     for keyword in ['tv', 'television', 'samsung', 'lg', 'sony']):
                commands = device_commands['tv']
            
            # Truncate long device names for UI
            display_name = device_name
            if len(display_name) > 15:
                display_name = display_name[:15] + "..."
                
            devices_to_show.append((display_name, alias, commands))
        
        for name, dev_code, actions in devices_to_show:
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color: {C['subtext']}; font-weight: bold;")
            row.addWidget(lbl)
            row.addStretch()
            
            for icon, cmd in actions:
                b = self.create_btn("", f"{dev_code} {cmd}", icon)
                b.setFixedSize(38, 32)
                b.setToolTip(cmd)
                row.addWidget(b)
            
            dev_layout.addLayout(row)
            
        main_layout.addWidget(dev_frame)
        
        # Init
        self.update_status()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(10000)
        self.adjustSize()

    def create_btn(self, text, cmd, icon=None):
        """Helper per creare bottoni già connessi"""
        b = ModernBtn(text, cmd, icon)
        # IMPORTANTE: usa lambda con default arg c=cmd per catturare il valore corrente!
        b.clicked.connect(lambda _, c=cmd: self.run(c))
        return b

    def create_disabled_btn(self, text, tooltip, icon=None):
        """Helper per creare bottoni disabilitati con tooltip"""
        b = ModernBtn(text, "", icon)  # Empty command for disabled buttons
        b.setDisabled(True)
        b.setToolTip(tooltip)
        
        # Enhanced styling for disabled TV control buttons
        b.setStyleSheet(f"""
            QPushButton:disabled {{
                background-color: {C['bg']};
                border: 1px solid {C['subtext']};
                color: {C['subtext']};
                opacity: 0.6;
            }}
        """)
        
        return b

    def create_tv_command(self, action):
        """Create TV command using dynamic device resolution"""
        tv_alias, tv_device = find_tv_device()
        if tv_device:
            return f"{tv_alias} {action}"
        return None

    def is_tv_device_available(self):
        """Check if TV device is available in configuration"""
        tv_alias, tv_device = find_tv_device()
        return tv_device is not None

    def get_tv_unavailable_message(self):
        """Get appropriate message when TV device is unavailable"""
        return "TV device not configured - check your Harmony Hub setup"

    def add_section_header(self, layout, text):
        lbl = QLabel(text)
        lbl.setObjectName("Header")
        layout.addWidget(lbl)

    def run(self, cmd):
        # Parsa il comando per separare azione se necessario
        parts = cmd.split(maxsplit=1)
        command = parts[0]
        action = parts[1] if len(parts) > 1 else None
        
        # Check for TV device availability before processing TV commands
        if self._is_tv_command(command, action):
            if not self.is_tv_device_available():
                # Show TV unavailable error immediately
                self.status.setText("❌ TV device not configured")
                self.status.setStyleSheet(f"QLabel#Status {{ color: {C['danger']}; border-color: {C['danger']}; }}")
                # Return to real state after 3 seconds
                QTimer.singleShot(3000, self.update_status)
                return
        
        # Queue command through StateManager for centralized coordination and sequential processing (Requirement 4.3, 1.1)
        if hasattr(self, 'state_manager'):
            # Ensure sequential processing by checking current state
            current_state = self.state_manager.get_state_info()
            
            # Log command attempt for debugging sequential processing
            print(f"Attempting to queue command: {command} {action or ''} "
                  f"(current queue: {current_state['pending_commands']}, processing: {current_state['is_processing']})")
            
            command_queued = self.state_manager.queue_command(command, action)
            if not command_queued:
                # Command was blocked - show error immediately
                self.status.setText("❌ Comando bloccato - attività in corso")
                self.status.setStyleSheet(f"QLabel#Status {{ color: {C['danger']}; border-color: {C['danger']}; }}")
                # Return to real state after 3 seconds (Requirement 4.5)
                QTimer.singleShot(3000, self.update_status)
                return
            
            # Verify sequential processing order is maintained
            if not self.state_manager.ensure_sequential_processing():
                print("WARNING: Sequential processing order issue detected after queueing command")
            
            # Log successful queueing
            updated_state = self.state_manager.get_state_info()
            print(f"Command queued successfully: {command} {action or ''} "
                  f"(new queue size: {updated_state['pending_commands']})")
        else:
            # Fallback if StateManager not available - show immediate feedback
            self.status.setText("🚀 Elaborazione...")
            self.status.setStyleSheet(f"QLabel#Status {{ color: {C['active']}; border-color: {C['active']}; }}")
        
        # Send command to worker for sequential processing
        self.worker.queue_command(command, action)

    def _is_tv_command(self, command, action):
        """Check if a command is a TV-specific command"""
        tv_alias, tv_device = find_tv_device()
        if tv_alias and command == tv_alias:
            return True
        
        # Also check for common TV command patterns
        tv_actions = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 
                     'Red', 'Green', 'Yellow', 'Blue', 
                     'Info', 'Guide', 'SmartHub', 'List']
        
        # Check if this looks like a TV command based on action
        if action and action in tv_actions:
            return True
            
        return False
    
    def _is_tv_command_result(self, cmd):
        """
        Check if a command result is from a TV command.
        
        Args:
            cmd: The command string (e.g., "tv_samsung 1")
            
        Returns:
            bool: True if this is a TV command result
            
        Requirements: 3.1, 3.2 (TV command feedback identification)
        """
        if not cmd:
            return False
            
        tv_alias, tv_device = find_tv_device()
        
        # Check if command starts with TV device alias
        if tv_alias and cmd.startswith(tv_alias):
            return True
        
        # Fallback: check for common TV command patterns
        parts = cmd.split(maxsplit=1)
        if len(parts) == 2:
            device, action = parts
            tv_actions = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 
                         'Red', 'Green', 'Yellow', 'Blue', 
                         'Info', 'Guide', 'SmartHub', 'List']
            return action in tv_actions
            
        return False
    
    def _is_tv_command_by_parts(self, command, action):
        """
        Check if a command is a TV command by its parts.
        
        Args:
            command: The device command part
            action: The action part
            
        Returns:
            bool: True if this is a TV command
            
        Requirements: 3.1, 3.2 (TV command feedback identification)
        """
        tv_alias, tv_device = find_tv_device()
        
        # Check if command matches TV device alias
        if tv_alias and command == tv_alias:
            return True
        
        # Fallback: check for common TV command patterns
        if action:
            tv_actions = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 
                         'Red', 'Green', 'Yellow', 'Blue', 
                         'Info', 'Guide', 'SmartHub', 'List']
            return action in tv_actions
            
        return False
    
    def _extract_tv_action(self, cmd):
        """
        Extract the TV action from a command string.
        
        Args:
            cmd: The command string (e.g., "tv_samsung 1")
            
        Returns:
            str: The TV action if found, None otherwise
            
        Requirements: 3.1, 3.2 (TV command feedback enhancement)
        """
        if not cmd:
            return None
            
        parts = cmd.split(maxsplit=1)
        if len(parts) == 2:
            return parts[1]
            
        return None
    
    def _get_tv_success_feedback(self, action):
        """
        Get TV-specific success feedback message.
        
        Args:
            action: The TV action that succeeded
            
        Returns:
            str: TV-specific success message
            
        Requirements: 3.1, 3.2 (TV command success feedback)
        """
        if not action:
            return "TV command completed"
            
        # Provide user-friendly feedback for different TV actions
        feedback_map = {
            '0': 'TV Channel 0',
            '1': 'TV Channel 1', '2': 'TV Channel 2', '3': 'TV Channel 3',
            '4': 'TV Channel 4', '5': 'TV Channel 5', '6': 'TV Channel 6',
            '7': 'TV Channel 7', '8': 'TV Channel 8', '9': 'TV Channel 9',
            'Red': 'TV Red Button',
            'Green': 'TV Green Button',
            'Yellow': 'TV Yellow Button',
            'Blue': 'TV Blue Button',
            'Info': 'TV Info',
            'Guide': 'TV Guide',
            'SmartHub': 'TV Smart Hub',
            'List': 'TV Channel List'
        }
        
        return feedback_map.get(action, f"TV {action}")
    
    def _get_tv_error_feedback(self, message):
        """
        Get TV-specific error feedback message.
        
        Args:
            message: The error message
            
        Returns:
            str: TV-specific error message
            
        Requirements: 3.1, 3.2 (TV command error feedback)
        """
        if not message:
            return "TV command failed"
            
        # Provide user-friendly TV error messages
        message_lower = message.lower()
        
        if "not configured" in message_lower or "not found" in message_lower:
            return "TV not configured"
        elif "validation failed" in message_lower:
            return "Invalid TV command"
        elif "network" in message_lower or "connection" in message_lower:
            return "TV connection error"
        elif "timeout" in message_lower:
            return "TV response timeout"
        else:
            return "TV command error"
    
    def _enhance_tv_status_message(self, status_text):
        """
        Enhance status messages for TV commands.
        
        Args:
            status_text: The original status text
            
        Returns:
            str: Enhanced status text with TV-specific improvements
            
        Requirements: 3.1, 3.2 (TV command status message enhancement)
        """
        if not status_text:
            return status_text
            
        # Enhance TV-related status messages
        if "TV" in status_text:
            # Already TV-specific, return as-is
            return status_text
        elif "samsung" in status_text.lower():
            # Replace generic device name with TV-specific label
            return status_text.replace("samsung", "TV").replace("Samsung", "TV")
        elif any(action in status_text for action in ['Red', 'Green', 'Yellow', 'Blue', 'Info', 'Guide', 'SmartHub', 'List']):
            # Add TV context to color/function button feedback
            return f"📺 {status_text}"
        elif any(num in status_text for num in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']) and len(status_text) < 10:
            # Add TV context to number button feedback
            return f"📺 {status_text}"
        
        return status_text
    
    def _contains_tv_feedback(self, status_text):
        """
        Check if status text contains TV-related feedback.
        
        Args:
            status_text: The status text to check
            
        Returns:
            bool: True if status contains TV feedback
            
        Requirements: 3.1, 3.2 (TV command feedback detection)
        """
        if not status_text:
            return False
            
        tv_indicators = ['TV', 'samsung', 'Red', 'Green', 'Yellow', 'Blue', 
                        'Info', 'Guide', 'SmartHub', 'List', '📺']
        
        return any(indicator in status_text for indicator in tv_indicators)
    
    def on_done(self, cmd, res):
        """
        Handle command completion with enhanced TV command feedback integration.
        
        Requirements: 3.1, 3.2 (TV command feedback integration with StateManager)
        """
        if "error" in res:
            # Enhanced error handling with specific TV command feedback
            error_msg = res.get('error', 'Unknown error')
            
            # Check if this is a TV command for specialized feedback
            if self._is_tv_command_result(cmd):
                # Provide TV-specific error feedback
                if "not found" in error_msg.lower() or "not configured" in error_msg.lower():
                    tv_error = "TV device not configured"
                elif "validation failed" in error_msg.lower():
                    tv_error = "Invalid TV command"
                elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                    tv_error = "TV connection failed"
                elif "timeout" in error_msg.lower():
                    tv_error = "TV command timeout"
                else:
                    tv_error = "TV command failed"
                
                # Log TV-specific error for debugging
                print(f"TV command failed: {cmd} - {error_msg}")
                
                # Let StateManager handle the error display with TV-specific message
                if hasattr(self, 'state_manager'):
                    # Use StateManager's enhanced error handling for TV commands
                    self.state_manager.handle_command_error(
                        cmd.split()[0] if ' ' in cmd else cmd,
                        cmd.split()[1] if ' ' in cmd else None,
                        tv_error
                    )
            else:
                # Non-TV command error - use standard error handling
                print(f"Command failed: {cmd} - {error_msg}")
                
                # StateManager will handle showing the error and returning to real state
                # We don't override StateManager's error handling with our own error display
            
        else:
            # Success - Enhanced feedback for TV commands
            if self._is_tv_command_result(cmd):
                # Provide TV-specific success feedback
                tv_action = self._extract_tv_action(cmd)
                if tv_action:
                    print(f"TV command completed successfully: {tv_action}")
                    
                    # Show brief TV-specific success feedback through StateManager
                    if hasattr(self, 'state_manager'):
                        # Update StateManager with TV command success
                        # StateManager will coordinate the feedback display timing
                        pass  # StateManager handles completion feedback automatically
                else:
                    print(f"TV command completed successfully: {cmd}")
            else:
                # Non-TV command success
                print(f"Command completed successfully: {cmd}")
            
            # The StateManager handles:
            # 1. Showing completion feedback (including TV-specific feedback)
            # 2. Coordinating timer updates
            # 3. Returning to real state at the right time
            # 4. Preventing timer conflicts during activity changes
    
    def on_command_started(self, command, action):
        """Handle command started signal from HarmonyWorker"""
        # This provides immediate feedback that command was received
        cmd_display = f"{command} {action}".strip()
        print(f"Command started: {cmd_display}")
    
    def on_command_progress(self, command, action, progress_message):
        """Handle command progress signal from HarmonyWorker"""
        # This provides intermediate progress updates
        cmd_display = f"{command} {action}".strip()
        print(f"Command progress: {cmd_display} - {progress_message}")
    
    def on_command_completed(self, command, action, success, message):
        """
        Handle command completed signal from HarmonyWorker with enhanced TV command feedback.
        
        Requirements: 3.1, 3.2 (TV command feedback integration)
        """
        # This provides final completion status with TV command specialization
        cmd_display = f"{command} {action}".strip()
        status = "completed" if success else "failed"
        
        # Enhanced feedback for TV commands
        if self._is_tv_command_by_parts(command, action):
            if success:
                # TV command success - provide specific feedback
                tv_feedback = self._get_tv_success_feedback(action)
                print(f"TV command {status}: {tv_feedback}")
                
                # Integrate with StateManager for consistent TV command feedback
                if hasattr(self, 'state_manager'):
                    # StateManager will handle the success display timing and coordination
                    # We can enhance the message if needed
                    pass
            else:
                # TV command failure - provide specific error context
                tv_error = self._get_tv_error_feedback(message)
                print(f"TV command {status}: {tv_error}")
                
                # StateManager will handle error display with TV-specific context
        else:
            # Non-TV command - standard feedback
            print(f"Command {status}: {cmd_display} - {message}")
    
    def on_state_status_changed(self, status_text, color):
        """
        Handle status changes from StateManager with enhanced TV command feedback support.
        
        Requirements: 3.1, 3.2 (TV command status messages integration)
        """
        # Update status display with centralized state information
        # This handles immediate feedback and queue size display (Requirements 4.1, 4.2)
        # Enhanced to support TV command specific status messages
        
        # If status_text is empty, it means we should update to real state
        if not status_text:
            self.update_status()
        else:
            # Check if this is TV command feedback and enhance the display
            enhanced_status = self._enhance_tv_status_message(status_text)
            
            self.status.setText(enhanced_status)
            self.status.setStyleSheet(f"QLabel#Status {{ color: {color}; border-color: {color}; }}")
            
            # Log TV command status updates for debugging
            if "TV" in enhanced_status or self._contains_tv_feedback(enhanced_status):
                print(f"TV command status update: {enhanced_status}")
    
    def on_buttons_state_changed(self, enabled):
        """Handle button state changes from StateManager"""
        # Enable/disable activity buttons based on StateManager state (Requirement 4.3)
        # Activity buttons should be disabled when an activity change is in progress
        
        if hasattr(self, 'activity_buttons'):
            for button in self.activity_buttons:
                button.setDisabled(not enabled)
        
        # Also manage the power off button - it should be disabled during activity changes
        # but not when the system is actually off
        if hasattr(self, 'btn_off'):
            # Only disable if it's due to activity blocking, not because system is off
            if not enabled and not self.status.text().startswith("⚫"):
                self.btn_off.setDisabled(True)
            elif enabled:
                self.btn_off.setDisabled(False)
    
    def on_queue_size_changed(self, queue_size):
        """Handle queue size changes from StateManager"""
        # This could be used to show queue information in the UI
        # For now, just log it for debugging
        if queue_size > 0:
            print(f"Command queue size: {queue_size}")
    
    def update_status(self):
        # Check with StateManager if timer updates are allowed (Requirement 3.3)
        if hasattr(self, 'state_manager'):
            if not self.state_manager.request_status_update():
                # Timer update blocked - reschedule for later
                QTimer.singleShot(2000, self.update_status)  # Try again in 2 seconds
                return
            
        self.worker.queue_status()
    
    def on_status(self, status_text):
        # Update current activity in StateManager
        if hasattr(self, 'state_manager'):
            # Extract activity from status text for StateManager - dynamic matching
            activity_name = "unknown"
            if "OFF" in status_text or "-1" in status_text:
                activity_name = "off"
            else:
                # Try to match status text with activity names from config
                for alias, activity_info in ACTIVITIES.items():
                    activity_display_name = activity_info.get('name', '')
                    if activity_display_name and activity_display_name in status_text:
                        activity_name = alias
                        break
                    # Also try matching with alias if no display name match
                    elif alias.lower() in status_text.lower():
                        activity_name = alias
                        break
            
            self.state_manager.update_current_activity(activity_name)
            
            # CRITICAL FIX: Check if StateManager allows status updates
            # This prevents the "avvio watch tv" -> "off" -> "Watch TV" problem
            if not self.state_manager.is_timer_update_allowed():
                # StateManager is coordinating an activity change
                # Don't override its status display with intermediate Hub states
                print(f"Status update blocked by StateManager: '{status_text}' (activity changing)")
                return
        
        # Handle button states based on system state
        is_off = "OFF" in status_text or "-1" in status_text
        
        # Power off button should be disabled when system is already off
        if hasattr(self, 'btn_off'):
            self.btn_off.setDisabled(is_off)
        
        # Update status display with proper formatting - dynamic matching
        # Only if StateManager allows it (not during activity changes)
        if is_off: 
            txt, col = "⚫ OFF", C['subtext']
        else:
            # Try to match with activities from config and assign appropriate colors/icons
            txt, col = status_text.replace("✅", "").strip(), C['text']  # default
            
            for alias, activity_info in ACTIVITIES.items():
                activity_display_name = activity_info.get('name', '')
                if activity_display_name and activity_display_name in status_text:
                    # Assign colors based on activity type
                    name_lower = activity_display_name.lower()
                    if 'tv' in name_lower or 'guarda' in name_lower:
                        txt, col = f"📺 {activity_display_name.upper()}", C['active']
                    elif 'music' in name_lower or 'ascolta' in name_lower:
                        txt, col = f"🎵 {activity_display_name.upper()}", C['accent']
                    elif 'shield' in name_lower:
                        txt, col = f"🎮 {activity_display_name.upper()}", '#7dcfff'
                    elif 'clima' in name_lower or 'condizionatore' in name_lower:
                        txt, col = f"❄️ {activity_display_name.upper()}", '#7dcfff'
                    else:
                        txt, col = f"🎯 {activity_display_name.upper()}", C['text']
                    break
            
        self.status.setText(txt)
        self.status.setStyleSheet(f"QLabel#Status {{ color: {col}; border-color: {col}; }}")

    def recover_from_error(self):
        """
        Recover from error state and restore normal operation.
        
        This method can be called to attempt recovery after an error.
        Requirements: 1.4 (error handling)
        """
        if hasattr(self, 'state_manager'):
            self.state_manager.recover_from_error()
        
        # Force a status update to get real state
        QTimer.singleShot(1500, self.update_status)
    
    def closeEvent(self, event):
        self.worker.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    # Fix per icona KDE/Wayland/X11
    app.setDesktopFileName("harmony-hub-controller") 
    app.setStyleSheet(STYLESHEET)
    
    # Imposta icona applicazione e finestra
    icon_path = str(Path(__file__).parent / "harmony-icon.png")
    app.setWindowIcon(QIcon(icon_path))
    
    w = GUI()
    w.setWindowIcon(QIcon(icon_path))
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
