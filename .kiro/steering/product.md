# Harmony Hub Controller - Product Overview

## What is it?
A high-performance hybrid controller (CLI + GUI) for Logitech Harmony Hub devices featuring async WebSocket communication and a modern Qt6 interface with Tokyo Night theming.

## Key Features
- **Dual Interface**: Both command-line and graphical user interface
- **Async Performance**: WebSocket-based communication optimized for speed
- **Modern UI**: Tokyo Night themed Qt6 interface
- **Smart Commands**: Context-aware device control based on active activities
- **Linux Desktop Integration**: Menu shortcuts, aliases, and desktop file support
- **Auto-Discovery**: Automatically discover and configure your Harmony Hub

## Target Hardware
- Harmony Elite, Companion, Smart Control
- Harmony Ultimate Home, Pro
- Standalone Harmony Hub

## Performance Characteristics
- Activity commands: 0.4s - 1.0s (75% faster than standard CLI)
- Audio commands: 0.3s (with Press/Release precision)
- Status checks: 0.18s (18% faster)
- Device commands: 0.3s - 0.5s (Press/Release precision)
- Discovery operations: 0.5s - 2.0s

## Architecture
The application uses a hybrid architecture with:
- **CLI Backend** (`harmony.py`): Fast WebSocket-based command execution
- **GUI Frontend** (`harmony_gui.py`): Qt6-based modern interface
- **State Management** (`state_manager.py`): Centralized state coordination
- **Discovery System**: Auto-configuration and export capabilities