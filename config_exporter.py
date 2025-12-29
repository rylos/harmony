#!/usr/bin/env python3
"""
Configuration Export Functionality for Harmony Hub Discovery

This module provides the ConfigExporter class for generating config.py files
from discovered Harmony Hub configuration data.
"""

import os
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from config_models import Activity, Device, HubInfo

# Set up logging
logger = logging.getLogger(__name__)


class ConfigExporter:
    """Handles exporting discovered configuration data to config.py files"""
    
    def __init__(self, config_file_path: str = "config.py"):
        """
        Initialize ConfigExporter
        
        Args:
            config_file_path: Path to the config.py file to generate
        """
        self.config_file_path = config_file_path
        self.logger = logging.getLogger(__name__ + '.ConfigExporter')
    
    def export_to_config_file(self, config_data: Dict[str, Any], hub_info: Optional[HubInfo] = None, 
                             backup_existing: bool = True) -> bool:
        """
        Generate a valid config.py file with all discovered information
        
        Args:
            config_data: Dictionary containing 'activities' and 'devices' lists
            hub_info: Optional HubInfo object with connection details
            backup_existing: Whether to create backup of existing config file
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            # Create backup if requested and file exists
            if backup_existing and os.path.exists(self.config_file_path):
                if not self._create_backup():
                    self.logger.warning("Failed to create backup, continuing with export")
            
            # Extract data
            activities = config_data.get('activities', [])
            devices = config_data.get('devices', [])
            
            # Generate mappings
            activity_mappings = self.generate_activity_mappings(activities)
            device_mappings = self.generate_device_mappings(devices)
            audio_commands = self.generate_audio_commands(devices)
            
            # Generate config file content
            config_content = self._generate_config_content(
                hub_info, activity_mappings, device_mappings, audio_commands
            )
            
            # Write to file
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            self.logger.info(f"Successfully exported configuration to {self.config_file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            return False
    
    def generate_activity_mappings(self, activities: List[Activity]) -> Dict[str, Dict[str, str]]:
        """
        Generate activity mappings with names and IDs
        
        Args:
            activities: List of Activity objects
            
        Returns:
            Dictionary mapping activity aliases to ID and name
        """
        mappings = {}
        
        # Add PowerOff activity (standard for all hubs)
        mappings["off"] = {"id": "-1", "name": "PowerOff"}
        
        for activity in activities:
            if not activity.id or not activity.name:
                continue
            
            # Generate alias from activity name
            alias = self._generate_alias(activity.name)
            
            # Avoid conflicts with 'off' alias
            if alias == "off":
                alias = f"{alias}_activity"
            
            # Handle duplicate aliases
            original_alias = alias
            counter = 1
            while alias in mappings:
                alias = f"{original_alias}_{counter}"
                counter += 1
            
            mappings[alias] = {
                "id": activity.id,
                "name": activity.name
            }
        
        return mappings
    
    def generate_device_mappings(self, devices: List[Device]) -> Dict[str, Dict[str, str]]:
        """
        Generate device mappings with names and IDs
        
        Args:
            devices: List of Device objects
            
        Returns:
            Dictionary mapping device aliases to ID and name
        """
        mappings = {}
        
        for device in devices:
            if not device.id or not device.name:
                continue
            
            # Generate alias from device name
            alias = self._generate_alias(device.name)
            
            # Handle duplicate aliases
            original_alias = alias
            counter = 1
            while alias in mappings:
                alias = f"{original_alias}_{counter}"
                counter += 1
            
            mappings[alias] = {
                "id": device.id,
                "name": device.name
            }
        
        return mappings
    
    def generate_audio_commands(self, devices: List[Device]) -> Dict[str, str]:
        """
        Generate audio command shortcuts for compatible devices
        
        Args:
            devices: List of Device objects
            
        Returns:
            Dictionary mapping command aliases to Hub commands
        """
        # Standard audio commands to look for
        audio_command_mappings = {
            "vol+": ["VolumeUp", "Volume Up", "Vol+"],
            "vol-": ["VolumeDown", "Volume Down", "Vol-"],
            "mute": ["Mute", "Muting", "Volume Mute"],
            "on": ["PowerOn", "Power On", "On"],
            "off": ["PowerOff", "Power Off", "Off"]
        }
        
        found_commands = {}
        
        # Search through all devices for audio-related commands
        for device in devices:
            # Check if device is likely an audio device
            device_name_lower = device.name.lower()
            device_type_lower = device.device_type.lower()
            
            is_audio_device = any(keyword in device_name_lower or keyword in device_type_lower 
                                for keyword in ['receiver', 'amplifier', 'amp', 'audio', 'stereo', 'soundbar'])
            
            if is_audio_device:
                # Look for matching commands
                for command in device.commands:
                    command_name = command.name
                    for alias, possible_names in audio_command_mappings.items():
                        if alias not in found_commands:
                            for possible_name in possible_names:
                                if command_name == possible_name:
                                    found_commands[alias] = command_name
                                    break
        
        # Fill in defaults for missing commands
        default_commands = {
            "vol+": "VolumeUp",
            "vol-": "VolumeDown", 
            "mute": "Mute",
            "on": "PowerOn",
            "off": "PowerOff"
        }
        
        for alias, default_command in default_commands.items():
            if alias not in found_commands:
                found_commands[alias] = default_command
        
        return found_commands
    
    def _create_backup(self) -> bool:
        """
        Create backup of existing configuration file
        
        Returns:
            True if backup created successfully, False otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.config_file_path}.backup_{timestamp}"
            
            shutil.copy2(self.config_file_path, backup_path)
            self.logger.info(f"Created backup: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False
    
    def _generate_alias(self, name: str) -> str:
        """
        Generate a clean alias from a device/activity name
        
        Args:
            name: Original name
            
        Returns:
            Clean alias suitable for use as dictionary key
        """
        # Convert to lowercase and replace spaces/special chars with underscores
        alias = name.lower()
        alias = ''.join(c if c.isalnum() else '_' for c in alias)
        
        # Remove multiple consecutive underscores
        while '__' in alias:
            alias = alias.replace('__', '_')
        
        # Remove leading/trailing underscores
        alias = alias.strip('_')
        
        # Ensure it's not empty
        if not alias:
            alias = "device"
        
        return alias
    
    def _generate_config_content(self, hub_info: Optional[HubInfo], 
                                activity_mappings: Dict[str, Dict[str, str]],
                                device_mappings: Dict[str, Dict[str, str]],
                                audio_commands: Dict[str, str]) -> str:
        """
        Generate the complete config.py file content
        
        Args:
            hub_info: Hub connection information
            activity_mappings: Activity alias mappings
            device_mappings: Device alias mappings
            audio_commands: Audio command shortcuts
            
        Returns:
            Complete config file content as string
        """
        lines = []
        
        # Header
        lines.append("# Harmony Hub Configuration")
        lines.append("# Generated automatically by Harmony Hub Discovery")
        lines.append(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Hub connection details
        lines.append("# HUB Connection Details")
        if hub_info:
            lines.append(f'HUB_IP = "{hub_info.ip}"')
            lines.append(f'REMOTE_ID = "{hub_info.remote_id}"')
        else:
            lines.append('HUB_IP = "192.168.1.X"      # Update with your Hub IP')
            lines.append('REMOTE_ID = "YOUR_ID_HERE"   # Update with your Remote ID')
        lines.append("")
        
        # Activities mapping
        lines.append("# Activities Mapping (Alias -> ID)")
        lines.append("ACTIVITIES = {")
        for alias, info in sorted(activity_mappings.items()):
            lines.append(f'    "{alias}": {{"id": "{info["id"]}", "name": "{info["name"]}"}},')
        lines.append("}")
        lines.append("")
        
        # Devices mapping
        lines.append("# Devices Mapping (Alias -> ID)")
        lines.append("DEVICES = {")
        for alias, info in sorted(device_mappings.items()):
            lines.append(f'    "{alias}": {{"id": "{info["id"]}", "name": "{info["name"]}"}},')
        lines.append("}")
        lines.append("")
        
        # Audio commands
        lines.append("# Quick Audio Commands (Alias -> Hub Command)")
        lines.append("AUDIO_COMMANDS = {")
        for alias, command in sorted(audio_commands.items()):
            lines.append(f'    "{alias}": "{command}",')
        lines.append("}")
        lines.append("")
        
        return "\n".join(lines)


# Convenience function for easy usage
def export_config(config_data: Dict[str, Any], hub_info: Optional[HubInfo] = None,
                 config_file_path: str = "config.py", backup_existing: bool = True) -> bool:
    """
    Export configuration data to config.py file
    
    Args:
        config_data: Dictionary containing 'activities' and 'devices' lists
        hub_info: Optional HubInfo object with connection details
        config_file_path: Path to config file to generate
        backup_existing: Whether to create backup of existing file
        
    Returns:
        True if export successful, False otherwise
    """
    exporter = ConfigExporter(config_file_path)
    return exporter.export_to_config_file(config_data, hub_info, backup_existing)