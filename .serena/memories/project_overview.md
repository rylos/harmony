# Harmony Hub Controller - Project Overview

## Purpose
High-performance hybrid controller (CLI + GUI) for Logitech Harmony Hub devices featuring async WebSocket communication and a modern Qt6 interface with Tokyo Night theming.

## Key Features
- **Dual Interface**: CLI (`harmony.py`) and GUI (`harmony_gui.py`)
- **Async Performance**: WebSocket-based communication optimized for speed
- **Modern UI**: Tokyo Night themed Qt6 interface
- **Smart Commands**: Context-aware device control based on active activities
- **Linux Desktop Integration**: Menu shortcuts, aliases, desktop file support
- **Auto-Discovery**: Automatically discover and configure Harmony Hub

## Target Hardware
- Harmony Elite, Companion, Smart Control
- Harmony Ultimate Home, Pro
- Standalone Harmony Hub

## Performance Characteristics (post-optimization)
- Device commands (vol, mute, etc.): 71ms avg (was 306ms, -77%)
- Status checks: 44ms avg
- Activity start: 240ms avg
- Raw WebSocket send: 0.1ms
- Press/Release: 20ms delay, release fire-and-forget
- Config retrieval: ~1.1s (large payload)

## Architecture
Hybrid architecture:
- **CLI Backend** (`harmony.py`): Fast WebSocket-based command execution with `FastHarmonyHub` class
- **GUI Frontend** (`harmony_gui.py`): Qt6-based modern interface with `GUI` and `HarmonyWorker` classes
- **State Management** (`state_manager.py`): Centralized state coordination via `StateManager`
- **Discovery System** (`discovery_handlers.py`): Auto-configuration and export via `DiscoveryHandlers`
- **Config Models** (`config_models.py`): Data models (`HubInfo`, `Command`, `Device`, `Activity`, `ConfigurationParser`)
- **Config Exporter** (`config_exporter.py`): Export discovered config to Python files via `ConfigExporter`
- **Display Formatter** (`display_formatter.py`): Consistent CLI output formatting via `DisplayFormatter`

## Configuration
- `config.py`: Runtime configuration (auto-generated from discovery, NOT in git)
- `config.sample.py`: Configuration template
- Discovery system auto-generates config.py from hub scan
