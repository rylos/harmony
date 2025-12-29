# 🌃 Harmony Hub Controller - Tokyo Night Edition

A high-performance hybrid controller (CLI + GUI) for Logitech Harmony Hub devices featuring async WebSocket communication and a modern Qt6 interface.

## ✨ Features

- **🎯 Dual Interface**: Both command-line and graphical user interface
- **⚡ Async Performance**: WebSocket-based communication optimized for speed  
- **🌃 Modern UI**: Tokyo Night themed Qt6 interface
- **🧠 Smart Commands**: Context-aware device control based on active activities
- **🐧 Linux Desktop Integration**: Menu shortcuts, aliases, and desktop file support
- **🔍 Auto-Discovery**: Automatically discover and configure your Harmony Hub

## 🚀 Getting Started

**New users start here!** This guide will get you up and running in 3 simple steps.

### Step 1: Install Dependencies

```bash
# Clone the repository
git clone https://github.com/rylos/harmony.git
cd harmony

# Create virtual environment
python3 -m venv harmony_env
source harmony_env/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Step 2: Create Your Configuration (IMPORTANT!)

**You MUST create a `config.py` file before using the application.** Use the built-in discovery system:

```bash
# Discover your Harmony Hub automatically
python harmony.py discover

# This will show you all available activities and devices
# Then export the configuration to config.py
python harmony.py export-config
```

**What this does:**
- Scans your network for Harmony Hubs
- Shows all your activities (Watch TV, Listen to Music, etc.)
- Shows all your devices (TV, Receiver, etc.) and their commands
- Creates a `config.py` file with your specific setup

### Step 3: Start Using It!

```bash
# Launch the GUI (recommended for beginners)
./start_harmony_gui.sh

# Or use CLI commands directly
./harmony.py status                  # Check current status
./harmony.py <activity_name>         # Start an activity
./harmony.py <device> <command>      # Send device command
```

## 🎮 Usage Examples

### Activities

```bash
./harmony.py guarda_tv        # Start "Watch TV" activity
./harmony.py shield           # Start "Shield" activity  
./harmony.py ascolta_musica   # Start "Listen to Music" activity
./harmony.py off              # Power off everything
```

### Device Commands

```bash
./harmony.py tv_samsung PowerOn
./harmony.py onkyo_av_receiver VolumeUp
./harmony.py nvidia_game_console Home
```

### Quick Audio Controls

```bash
./harmony.py vol+             # Volume up
./harmony.py vol-             # Volume down
./harmony.py mute             # Mute/unmute
```

## 🔧 Discovery & Configuration Commands

Need to reconfigure or explore your setup? Use these commands:

```bash
python harmony.py discover                    # Show complete hub overview
python harmony.py show-activity <name>        # Show activity details
python harmony.py show-device <name>          # Show device details  
python harmony.py show-hub                    # Show hub information
python harmony.py export-config               # Generate config.py file
```

## 🖥️ Desktop Integration

```bash
# Add to KDE menu
./install_to_menu.sh

# Setup CLI aliases
./setup_aliases.sh
```

## 📁 Project Structure

```text
harmony/
├── harmony.py                    # Core CLI backend
├── harmony_gui.py                # Qt6 GUI frontend
├── state_manager.py              # State management system
├── config_models.py              # Configuration data models
├── config_exporter.py            # Configuration export functionality
├── discovery_handlers.py         # Discovery command handlers
├── display_formatter.py          # Output formatting
├── config.py                     # Your hub configuration (auto-generated)
├── config.sample.py              # Configuration template
├── start_harmony_gui.sh          # GUI launcher
├── install_to_menu.sh            # Desktop integration
├── setup_aliases.sh              # CLI aliases setup
├── harmony-hub-controller.desktop # Desktop entry
├── requirements.txt              # Python dependencies
└── harmony_env/                  # Python virtual environment
```

## 🎯 Compatible Hardware

- Harmony Elite, Companion, Smart Control
- Harmony Ultimate Home, Pro  
- Standalone Harmony Hub

## ⚡ Performance Features

- **Timeouts**: Activity (3.0s), Status (2.0s), IR commands (0.2s)
- **Press/Release Simulation**: 0.05s delay between press/release
- **Fire-and-forget**: Optimized for speed over reliability
- **Persistent Connections**: WebSocket connection reuse
- **Command Queueing**: Sequential processing with visual feedback

## 🛠️ Tech Stack

- **Python 3** - Main programming language
- **PyQt6** - GUI framework with modern Qt6 interface
- **aiohttp** - Async HTTP client for WebSocket communication
- **asyncio** - Asynchronous programming support

## 🆘 Troubleshooting

### "No config.py found" Error

This is the most common issue for new users. You need to create the configuration file:

```bash
# Make sure your Harmony Hub is on and connected to your network
python harmony.py discover
python harmony.py export-config
```

### Hub Not Found During Discovery

- Ensure your Harmony Hub is powered on and connected to the same network
- Check that your computer can reach the hub's IP address
- Try running discovery multiple times (sometimes takes a moment)

### GUI Won't Start

```bash
# Check if PyQt6 is properly installed
pip install --upgrade PyQt6

# Try launching directly
python harmony_gui.py
```

### Permission Issues with Scripts

```bash
# Make scripts executable
chmod +x start_harmony_gui.sh
chmod +x install_to_menu.sh
chmod +x setup_aliases.sh
```

## 📄 License

See LICENSE file for details.

---

Built with ❤️ for the Logitech Harmony Hub community