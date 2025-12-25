# Harmony Hub Configuration Template
# Rename this file to 'config.py' and fill in your details

# HUB Connection Details
HUB_IP = "192.168.1.X"      # Your Harmony Hub IP Address
REMOTE_ID = "YOUR_ID_HERE"   # Your Remote ID (found via initial discovery or logs)

# Activities Mapping (Alias -> ID)
# Use 'harmony.py list' or inspection to find your IDs
ACTIVITIES = {
    "tv": {"id": "12345678", "name": "Watch TV"},
    "music": {"id": "87654321", "name": "Listen to Music"}, 
    "off": {"id": "-1", "name": "PowerOff"}
}

# Devices Mapping (Alias -> ID)
DEVICES = {
    "tv": {"id": "11111111", "name": "My TV"},
    "amp": {"id": "22222222", "name": "My Amplifier"},
}

# Quick Audio Commands (Alias -> Hub Command)
AUDIO_COMMANDS = {
    "vol+": "VolumeUp",
    "vol-": "VolumeDown", 
    "mute": "Mute",
    "on": "PowerOn",
    "off": "PowerOff"
}
