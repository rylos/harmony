#!/usr/bin/env python3
"""
Configuration Data Models and Parsing for Harmony Hub Discovery

This module provides dataclasses and parsing functionality for Harmony Hub
configuration data retrieved via WebSocket commands.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class HubInfo:
    """Represents basic Harmony Hub information"""
    ip: str
    remote_id: str
    name: str = ""
    firmware_version: str = ""
    model: str = ""
    serial_number: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HubInfo':
        """Create HubInfo from dictionary with graceful handling of missing fields"""
        return cls(
            ip=data.get('ip', ''),
            remote_id=data.get('remote_id', ''),
            name=data.get('name', ''),
            firmware_version=data.get('firmware_version', ''),
            model=data.get('model', ''),
            serial_number=data.get('serial_number', '')
        )


@dataclass
class Command:
    """Represents a device command"""
    name: str
    label: str = ""
    category: str = ""
    action: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Command':
        """Create Command from dictionary with graceful handling of missing fields"""
        return cls(
            name=data.get('name', ''),
            label=data.get('label', data.get('name', '')),
            category=data.get('category', ''),
            action=data.get('action', '')
        )


@dataclass
class Device:
    """Represents a Harmony Hub device"""
    id: str
    name: str
    label: str = ""
    manufacturer: str = ""
    model: str = ""
    device_type: str = ""
    commands: List[Command] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Device':
        """Create Device from dictionary with graceful handling of missing fields"""
        # Parse commands from controlGroup structure
        commands = []
        control_groups = data.get('controlGroup', [])
        
        for group in control_groups:
            if isinstance(group, dict):
                category = group.get('name', '')
                functions = group.get('function', [])
                
                for func in functions:
                    if isinstance(func, dict):
                        command = Command.from_dict({
                            'name': func.get('label', ''),
                            'label': func.get('label', ''),
                            'category': category,
                            'action': func.get('action', '')
                        })
                        commands.append(command)
        
        return cls(
            id=data.get('id', ''),
            name=data.get('label', ''),
            label=data.get('label', ''),
            manufacturer=data.get('manufacturer', ''),
            model=data.get('model', ''),
            device_type=data.get('type', ''),
            commands=commands
        )


@dataclass
class Activity:
    """Represents a Harmony Hub activity"""
    id: str
    name: str
    label: str = ""
    activity_type: str = ""
    devices: List[str] = field(default_factory=list)  # Device IDs
    control_group: List[Dict] = field(default_factory=list)
    startup_sequence: List[Dict] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Activity':
        """Create Activity from dictionary with graceful handling of missing fields"""
        # Extract device IDs from controlGroup or sequences
        device_ids = []
        
        # Try to extract from controlGroup
        control_groups = data.get('controlGroup', [])
        for group in control_groups:
            if isinstance(group, dict):
                functions = group.get('function', [])
                for func in functions:
                    if isinstance(func, dict) and 'action' in func:
                        try:
                            action_data = json.loads(func['action'])
                            if 'deviceId' in action_data:
                                device_id = action_data['deviceId']
                                if device_id not in device_ids:
                                    device_ids.append(device_id)
                        except (json.JSONDecodeError, TypeError):
                            # Skip malformed action data
                            continue
        
        # Try to extract from sequences
        sequences = data.get('sequences', [])
        for sequence in sequences:
            if isinstance(sequence, dict):
                for seq_item in sequence.get('sequence', []):
                    if isinstance(seq_item, dict) and 'command' in seq_item:
                        device_id = seq_item['command'].get('deviceId')
                        if device_id and device_id not in device_ids:
                            device_ids.append(device_id)
        
        return cls(
            id=data.get('id', ''),
            name=data.get('label', ''),
            label=data.get('label', ''),
            activity_type=data.get('type', ''),
            devices=device_ids,
            control_group=control_groups,
            startup_sequence=sequences
        )


class ConfigurationParser:
    """Handles parsing and validation of Harmony Hub configuration data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.ConfigurationParser')
    
    def parse_hub_config(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse full hub configuration response
        
        Args:
            response: WebSocket response containing hub configuration
            
        Returns:
            Parsed configuration dict or None if parsing fails
        """
        try:
            # Validate basic response structure
            if not self._validate_response_structure(response):
                return None
            
            data = response.get('data', {})
            
            # Parse activities
            activities = []
            activity_data = data.get('activity', [])
            if isinstance(activity_data, list):
                for activity_dict in activity_data:
                    if isinstance(activity_dict, dict):
                        try:
                            activity = Activity.from_dict(activity_dict)
                            activities.append(activity)
                        except Exception as e:
                            self.logger.warning(f"Failed to parse activity {activity_dict.get('id', 'unknown')}: {e}")
                            continue
            
            # Parse devices
            devices = []
            device_data = data.get('device', [])
            if isinstance(device_data, list):
                for device_dict in device_data:
                    if isinstance(device_dict, dict):
                        try:
                            device = Device.from_dict(device_dict)
                            devices.append(device)
                        except Exception as e:
                            self.logger.warning(f"Failed to parse device {device_dict.get('id', 'unknown')}: {e}")
                            continue
            
            return {
                'activities': activities,
                'devices': devices,
                'raw_data': data
            }
            
        except Exception as e:
            self.logger.error(f"Failed to parse hub configuration: {e}")
            return None
    
    def parse_hub_info(self, response: Dict[str, Any], ip: str = "", remote_id: str = "") -> Optional[HubInfo]:
        """
        Parse hub information response
        
        Args:
            response: WebSocket response containing hub info
            ip: Hub IP address
            remote_id: Hub remote ID
            
        Returns:
            HubInfo object or None if parsing fails
        """
        try:
            if not self._validate_response_structure(response):
                return None
            
            data = response.get('data', {})
            
            # Create hub info with available data
            hub_info_data = {
                'ip': ip,
                'remote_id': remote_id,
                'name': data.get('name', ''),
                'firmware_version': data.get('firmware_version', ''),
                'model': data.get('model', ''),
                'serial_number': data.get('serial_number', '')
            }
            
            return HubInfo.from_dict(hub_info_data)
            
        except Exception as e:
            self.logger.error(f"Failed to parse hub info: {e}")
            return None
    
    def parse_provision_info(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse provision information response
        
        Args:
            response: WebSocket response containing provision info
            
        Returns:
            Parsed provision info dict or None if parsing fails
        """
        try:
            if not self._validate_response_structure(response):
                return None
            
            data = response.get('data', {})
            
            # Extract relevant provision information
            provision_info = {
                'account_id': data.get('accountId', ''),
                'user_auth_token': data.get('userAuthToken', ''),
                'hub_id': data.get('hubId', ''),
                'hub_uuid': data.get('hubUuid', ''),
                'remote_id': data.get('remoteId', ''),
                'email': data.get('email', ''),
                'active_remote_id': data.get('activeRemoteId', '')
            }
            
            return provision_info
            
        except Exception as e:
            self.logger.error(f"Failed to parse provision info: {e}")
            return None
    
    def _validate_response_structure(self, response: Dict[str, Any]) -> bool:
        """
        Validate basic WebSocket response structure
        
        Args:
            response: WebSocket response to validate
            
        Returns:
            True if structure is valid, False otherwise
        """
        if not isinstance(response, dict):
            self.logger.error("Response is not a dictionary")
            return False
        
        # Check for error in response
        if 'error' in response:
            self.logger.error(f"Response contains error: {response['error']}")
            return False
        
        # Check for basic required fields
        if 'data' not in response:
            self.logger.error("Response missing 'data' field")
            return False
        
        return True
    
    def validate_json_structure(self, json_data: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Validate and parse JSON data with descriptive error messages
        
        Args:
            json_data: JSON string or dictionary to validate
            
        Returns:
            Parsed dictionary or None if validation fails
        """
        try:
            # If it's already a dict, validate it
            if isinstance(json_data, dict):
                return json_data
            
            # If it's a string, try to parse it
            if isinstance(json_data, str):
                parsed_data = json.loads(json_data)
                if isinstance(parsed_data, dict):
                    return parsed_data
                else:
                    self.logger.error("JSON data is not a dictionary")
                    return None
            
            self.logger.error(f"Invalid JSON data type: {type(json_data)}")
            return None
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during JSON validation: {e}")
            return None


# Convenience functions for easy usage
def parse_config_response(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a configuration response using the default parser"""
    parser = ConfigurationParser()
    return parser.parse_hub_config(response)


def parse_hub_info_response(response: Dict[str, Any], ip: str = "", remote_id: str = "") -> Optional[HubInfo]:
    """Parse a hub info response using the default parser"""
    parser = ConfigurationParser()
    return parser.parse_hub_info(response, ip, remote_id)


def parse_provision_response(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a provision info response using the default parser"""
    parser = ConfigurationParser()
    return parser.parse_provision_info(response)