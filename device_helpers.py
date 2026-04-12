#!/usr/bin/env python3
"""Shared device detection helpers and constants for Harmony Hub Controller."""

# TV-specific actions used for command detection and feedback
TV_ACTIONS = frozenset([
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'Red', 'Green', 'Yellow', 'Blue',
    'Info', 'Guide', 'SmartHub', 'List',
])

# Keywords for device type detection
TV_KEYWORDS = ['tv', 'television', 'samsung', 'lg', 'sony']
AUDIO_KEYWORDS = ['receiver', 'amplifier', 'amp', 'audio', 'stereo', 'soundbar', 'onkyo']
SHIELD_KEYWORDS = ['shield', 'nvidia', 'streaming']
CLIMATE_KEYWORDS = ['clima', 'air conditioner', 'conditioner', 'climatizzatore']

# TV action feedback maps
TV_SUCCESS_FEEDBACK = {
    '0': 'TV Channel 0', '1': 'TV Channel 1', '2': 'TV Channel 2',
    '3': 'TV Channel 3', '4': 'TV Channel 4', '5': 'TV Channel 5',
    '6': 'TV Channel 6', '7': 'TV Channel 7', '8': 'TV Channel 8',
    '9': 'TV Channel 9',
    'Red': 'TV Red Button', 'Green': 'TV Green Button',
    'Yellow': 'TV Yellow Button', 'Blue': 'TV Blue Button',
    'Info': 'TV Info', 'Guide': 'TV Guide',
    'SmartHub': 'TV Smart Hub', 'List': 'TV Channel List',
}


def find_device_by_type(devices, device_type_keywords):
    """Find device by type keywords (case insensitive).

    Args:
        devices: DEVICES dict from config
        device_type_keywords: list of keyword strings

    Returns:
        (alias, device_info) or (None, None)
    """
    for alias, device_info in devices.items():
        device_name = device_info.get('name', '').lower()
        for keyword in device_type_keywords:
            if keyword.lower() in device_name:
                return alias, device_info
    return None, None


def find_audio_device(devices):
    return find_device_by_type(devices, AUDIO_KEYWORDS)


def find_tv_device(devices):
    return find_device_by_type(devices, TV_KEYWORDS)


def find_shield_device(devices):
    return find_device_by_type(devices, SHIELD_KEYWORDS)


def find_climate_device(devices):
    return find_device_by_type(devices, CLIMATE_KEYWORDS)


def is_tv_device(devices, alias):
    """Check if a device alias refers to a TV device."""
    if alias not in devices:
        return False
    name = devices[alias].get('name', '').lower()
    return any(kw in name for kw in TV_KEYWORDS)


def is_tv_action(action):
    """Check if an action string is a known TV action."""
    return action in TV_ACTIONS if action else False


def get_tv_success_message(action):
    """Get user-friendly TV success message for an action."""
    if not action:
        return "TV command completed"
    return TV_SUCCESS_FEEDBACK.get(action, f"TV {action} completed")


def get_tv_error_message(error_message):
    """Get user-friendly TV error message."""
    if not error_message:
        return "TV command failed"
    msg = error_message.lower()
    if "not configured" in msg or "not found" in msg:
        return "TV device not configured in Harmony Hub"
    if "validation failed" in msg:
        return "Invalid TV command - check device configuration"
    if "network" in msg or "connection" in msg:
        return "TV connection error - check Harmony Hub network"
    if "timeout" in msg:
        return "TV response timeout - device may be off or unresponsive"
    return f"TV command error: {error_message}"
