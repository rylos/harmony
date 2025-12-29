# Product Overview

## Logitech Harmony Hub Controller

A high-performance hybrid controller (CLI + GUI) for Logitech Harmony Hub devices featuring async WebSocket communication and a modern Qt6 interface.

### Key Features
- **Dual Interface**: Both command-line and graphical user interface
- **Async Performance**: WebSocket-based communication optimized for speed
- **Modern UI**: Tokyo Night themed Qt6 interface
- **Smart Commands**: Context-aware device control based on active activities
- **Linux Desktop Integration**: Menu shortcuts, aliases, and desktop file support

### Target Hardware
Compatible with all Logitech Harmony Hub-based systems:
- Harmony Elite, Companion, Smart Control
- Harmony Ultimate Home, Pro
- Standalone Harmony Hub

### Architecture
- **Backend (`harmony.py`)**: Async CLI handling WebSocket communication
- **Frontend (`harmony_gui.py`)**: Qt6 GUI wrapper with threaded CLI calls
- **Configuration**: Python-based config system with device/activity mappings