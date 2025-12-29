#!/usr/bin/env python3
"""
Display Formatting System for Harmony Hub Configuration Discovery

This module provides consistent formatting for hub, activity, and device information
display, maintaining compatibility with the existing CLI output style.
"""

from typing import Dict, List, Optional, Any
from config_models import HubInfo, Activity, Device, Command


class DisplayFormatter:
    """Handles formatting of configuration data for console display"""
    
    def __init__(self):
        # Status indicators consistent with existing CLI
        self.status_indicators = {
            'active': '🟢',
            'inactive': '🔴', 
            'unknown': '⚫',
            'connected': '🟢',
            'disconnected': '🔴'
        }
        
        # Device type icons consistent with existing CLI
        self.device_icons = {
            'StereoReceiver': '🎵',
            'Television': '📺',
            'SetTopBox': '🎮',
            'AirConditioner': '❄️',
            'GameConsole': '🎮',
            'MediaPlayer': '📱',
            'default': '📱'
        }
        
        # Activity type icons
        self.activity_icons = {
            'VirtualTelevisionN': '📺',
            'VirtualGeneric': '🎯',
            'VirtualDvd': '💿',
            'VirtualGameConsole': '🎮',
            'VirtualMusic': '🎵',
            'PowerOff': '⚫',
            'default': '🎯'
        }
    
    def format_hub_info(self, hub_info: HubInfo, current_activity: Optional[str] = None, 
                       connectivity_status: str = "unknown", performance_metrics: Optional[Dict] = None) -> str:
        """
        Format hub information for display
        
        Args:
            hub_info: HubInfo object with hub details
            current_activity: Name of currently active activity
            connectivity_status: Connection status (connected/disconnected/unknown)
            performance_metrics: Optional performance metrics dict
            
        Returns:
            Formatted hub information string
        """
        lines = []
        
        # Header with box drawing
        lines.append("╭─────────────────────────────────────────────────────────╮")
        lines.append("│                    🏠 HARMONY HUB INFO                 │")
        lines.append("╰─────────────────────────────────────────────────────────╯")
        lines.append("")
        
        # Connection info
        status_icon = self.status_indicators.get(connectivity_status, '⚫')
        lines.append(f"🌐 CONNECTION:")
        lines.append(f"  {status_icon} Status:     {connectivity_status.title()}")
        lines.append(f"  📍 IP Address: {hub_info.ip}")
        lines.append(f"  🆔 Remote ID:  {hub_info.remote_id}")
        lines.append("")
        
        # Hub details
        lines.append("🔧 HUB DETAILS:")
        lines.append(f"  📛 Name:       {hub_info.name or 'Unknown'}")
        lines.append(f"  🏷️  Model:      {hub_info.model or 'Unknown'}")
        lines.append(f"  🔢 Serial:     {hub_info.serial_number or 'Unknown'}")
        lines.append(f"  💾 Firmware:   {hub_info.firmware_version or 'Unknown'}")
        lines.append("")
        
        # Current activity
        lines.append("🎯 CURRENT ACTIVITY:")
        if current_activity:
            if current_activity.lower() == "poweroff" or current_activity == "-1":
                lines.append(f"  ⚫ OFF")
            else:
                lines.append(f"  🟢 {current_activity}")
        else:
            lines.append(f"  ⚫ Unknown")
        lines.append("")
        
        # Performance metrics if available
        if performance_metrics:
            lines.append("⚡ PERFORMANCE METRICS:")
            for metric_name, metric_value in performance_metrics.items():
                if isinstance(metric_value, (int, float)):
                    lines.append(f"  📊 {metric_name}: {metric_value:.3f}s")
                else:
                    lines.append(f"  📊 {metric_name}: {metric_value}")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_discovery_summary(self, config: Dict[str, Any]) -> str:
        """
        Format discovery summary showing all activities and devices
        
        Args:
            config: Parsed configuration dict with activities and devices
            
        Returns:
            Formatted discovery summary string
        """
        lines = []
        
        # Header
        lines.append("╭─────────────────────────────────────────────────────────╮")
        lines.append("│                🔍 CONFIGURATION DISCOVERY              │")
        lines.append("│                   Complete Overview                    │")
        lines.append("╰─────────────────────────────────────────────────────────╯")
        lines.append("")
        
        activities = config.get('activities', [])
        devices = config.get('devices', [])
        
        # Activities section
        lines.append(f"🎯 ACTIVITIES ({len(activities)} found):")
        if activities:
            for activity in activities:
                icon = self.activity_icons.get(activity.activity_type, self.activity_icons['default'])
                device_count = len(activity.devices)
                lines.append(f"  {icon} {activity.name:<20} (ID: {activity.id}) - {device_count} devices")
        else:
            lines.append("  ⚫ No activities found")
        lines.append("")
        
        # Devices section
        lines.append(f"📱 DEVICES ({len(devices)} found):")
        if devices:
            for device in devices:
                icon = self.device_icons.get(device.device_type, self.device_icons['default'])
                command_count = len(device.commands)
                manufacturer_model = f"{device.manufacturer} {device.model}".strip()
                if manufacturer_model:
                    lines.append(f"  {icon} {device.name:<20} (ID: {device.id}) - {command_count} commands")
                    lines.append(f"     └─ {manufacturer_model}")
                else:
                    lines.append(f"  {icon} {device.name:<20} (ID: {device.id}) - {command_count} commands")
        else:
            lines.append("  ⚫ No devices found")
        lines.append("")
        
        # Summary
        lines.append("💡 NEXT STEPS:")
        lines.append("  • Use 'show-activity <name>' to view activity details")
        lines.append("  • Use 'show-device <name>' to view device details")
        lines.append("  • Use 'export-config' to generate config.py file")
        
        return "\n".join(lines)
    
    def format_activity_details(self, activity: Activity, devices: List[Device], 
                              is_current: bool = False) -> str:
        """
        Format detailed activity information
        
        Args:
            activity: Activity object to format
            devices: List of all devices (to resolve device names)
            is_current: Whether this activity is currently active
            
        Returns:
            Formatted activity details string
        """
        lines = []
        
        # Header
        icon = self.activity_icons.get(activity.activity_type, self.activity_icons['default'])
        status_icon = '🟢' if is_current else '⚫'
        
        lines.append("╭─────────────────────────────────────────────────────────╮")
        lines.append(f"│                {icon} ACTIVITY DETAILS                    │")
        lines.append("╰─────────────────────────────────────────────────────────╯")
        lines.append("")
        
        # Basic info
        lines.append("📋 BASIC INFORMATION:")
        lines.append(f"  📛 Name:       {activity.name}")
        lines.append(f"  🆔 ID:         {activity.id}")
        lines.append(f"  🏷️  Type:       {activity.activity_type}")
        lines.append(f"  {status_icon} Status:     {'Active' if is_current else 'Inactive'}")
        lines.append("")
        
        # Involved devices
        lines.append(f"📱 INVOLVED DEVICES ({len(activity.devices)}):")
        if activity.devices:
            device_dict = {d.id: d for d in devices}
            for device_id in activity.devices:
                device = device_dict.get(device_id)
                if device:
                    icon = self.device_icons.get(device.device_type, self.device_icons['default'])
                    manufacturer_model = f"{device.manufacturer} {device.model}".strip()
                    if manufacturer_model:
                        lines.append(f"  {icon} {device.name} ({manufacturer_model})")
                    else:
                        lines.append(f"  {icon} {device.name}")
                else:
                    lines.append(f"  📱 Unknown Device (ID: {device_id})")
        else:
            lines.append("  ⚫ No devices configured")
        lines.append("")
        
        # Available commands grouped by device
        lines.append("🎮 AVAILABLE COMMANDS:")
        if activity.control_group:
            device_dict = {d.id: d for d in devices}
            device_commands = {}
            
            # Group commands by device
            for group in activity.control_group:
                if isinstance(group, dict):
                    functions = group.get('function', [])
                    for func in functions:
                        if isinstance(func, dict) and 'action' in func:
                            try:
                                import json
                                action_data = json.loads(func['action'])
                                device_id = action_data.get('deviceId')
                                command_name = action_data.get('command')
                                
                                if device_id and command_name:
                                    if device_id not in device_commands:
                                        device_commands[device_id] = []
                                    device_commands[device_id].append(command_name)
                            except (json.JSONDecodeError, TypeError):
                                continue
            
            # Display commands by device
            for device_id, commands in device_commands.items():
                device = device_dict.get(device_id)
                device_name = device.name if device else f"Device {device_id}"
                icon = self.device_icons.get(device.device_type if device else 'default', self.device_icons['default'])
                
                lines.append(f"  {icon} {device_name}:")
                for cmd in sorted(set(commands))[:5]:  # Show first 5 unique commands
                    lines.append(f"     • {cmd}")
                if len(set(commands)) > 5:
                    lines.append(f"     • ... and {len(set(commands)) - 5} more")
                lines.append("")
        else:
            lines.append("  ⚫ No commands available")
            lines.append("")
        
        # Quick command examples
        lines.append("💡 QUICK COMMAND EXAMPLES:")
        activity_name_cmd = activity.name.lower().replace(' ', '-')
        lines.append(f"  ./harmony.py {activity_name_cmd}")
        if activity.devices:
            device_dict = {d.id: d for d in devices}
            example_device = device_dict.get(activity.devices[0])
            if example_device and example_device.commands:
                device_name_cmd = example_device.name.lower().replace(' ', '-')
                example_cmd = example_device.commands[0].name
                lines.append(f"  ./harmony.py {device_name_cmd} {example_cmd}")
        
        return "\n".join(lines)
    
    def format_device_details(self, device: Device, activities: List[Activity], 
                            current_activity_id: Optional[str] = None) -> str:
        """
        Format detailed device information
        
        Args:
            device: Device object to format
            activities: List of all activities (to show which use this device)
            current_activity_id: ID of currently active activity
            
        Returns:
            Formatted device details string
        """
        lines = []
        
        # Header
        icon = self.device_icons.get(device.device_type, self.device_icons['default'])
        
        lines.append("╭─────────────────────────────────────────────────────────╮")
        lines.append(f"│                {icon} DEVICE DETAILS                      │")
        lines.append("╰─────────────────────────────────────────────────────────╯")
        lines.append("")
        
        # Basic info
        lines.append("📋 BASIC INFORMATION:")
        lines.append(f"  📛 Name:         {device.name}")
        lines.append(f"  🆔 ID:           {device.id}")
        lines.append(f"  🏷️  Type:         {device.device_type}")
        lines.append(f"  🏭 Manufacturer: {device.manufacturer}")
        lines.append(f"  📦 Model:        {device.model}")
        lines.append("")
        
        # Activities that use this device
        using_activities = [a for a in activities if device.id in a.devices]
        lines.append(f"🎯 USED IN ACTIVITIES ({len(using_activities)}):")
        if using_activities:
            for activity in using_activities:
                activity_icon = self.activity_icons.get(activity.activity_type, self.activity_icons['default'])
                status_icon = '🟢' if activity.id == current_activity_id else '⚫'
                lines.append(f"  {activity_icon} {status_icon} {activity.name}")
        else:
            lines.append("  ⚫ Not used in any activities")
        lines.append("")
        
        # Commands grouped by category
        lines.append(f"🎮 AVAILABLE COMMANDS ({len(device.commands)}):")
        if device.commands:
            # Group commands by category
            categories = {}
            for cmd in device.commands:
                category = cmd.category or 'General'
                if category not in categories:
                    categories[category] = []
                categories[category].append(cmd)
            
            # Display commands by category
            for category, commands in categories.items():
                lines.append(f"  📂 {category}:")
                for cmd in commands[:8]:  # Show first 8 commands per category
                    lines.append(f"     • {cmd.name}")
                if len(commands) > 8:
                    lines.append(f"     • ... and {len(commands) - 8} more")
                lines.append("")
        else:
            lines.append("  ⚫ No commands available")
            lines.append("")
        
        # Quick command examples
        lines.append("💡 QUICK COMMAND EXAMPLES:")
        device_name_lower = device.name.lower().replace(' ', '-')
        lines.append(f"  ./harmony.py {device_name_lower} PowerOn")
        lines.append(f"  ./harmony.py {device_name_lower} PowerOff")
        if device.commands:
            example_cmd = device.commands[0].name
            lines.append(f"  ./harmony.py {device_name_lower} {example_cmd}")
        
        return "\n".join(lines)
    
    def format_error_message(self, error: str, context: str = "") -> str:
        """
        Format error messages consistently with existing CLI style
        
        Args:
            error: Error message to format
            context: Optional context information
            
        Returns:
            Formatted error message string
        """
        lines = []
        lines.append("❌ ERROR:")
        lines.append(f"   {error}")
        if context:
            lines.append(f"   Context: {context}")
        return "\n".join(lines)
    
    def format_success_message(self, message: str, details: Optional[str] = None) -> str:
        """
        Format success messages consistently with existing CLI style
        
        Args:
            message: Success message to format
            details: Optional additional details
            
        Returns:
            Formatted success message string
        """
        lines = []
        lines.append(f"✅ {message}")
        if details:
            lines.append(f"   {details}")
        return "\n".join(lines)