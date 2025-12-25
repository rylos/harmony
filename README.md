# Logitech Harmony Hub Controller (CLI + GUI)

> **Status**: Stable, Production Ready
> **Description**: High-performance, hybrid controller (CLI + GUI) for Logitech Harmony Hub featuring async WebSocket communication and a modern Qt6 interface.

## 📋 Overview
A fast, hybrid controller (CLI + GUI) designed for the [Logitech Harmony Hub](https://support.myharmony.com/it-it/hub).
This project provides an ultra-fast Python interface to control your home automation and entertainment devices directly from your Linux desktop.

### 🔌 Compatible Hardware
This controller works with any **Logitech Harmony Hub** based system, including:
- **Harmony Elite**
- **Harmony Companion**
- **Harmony Smart Control**
- **Harmony Ultimate Home**
- **Harmony Pro**
- **Harmony Hub** (Standalone)

### 🏗 Architecture
The system is divided into two layers:
1.  **Backend (CLI - `harmony.py`)**: Handles asynchronous WebSocket communication with the Hub. Optimized for speed using `aiohttp` and a "fire-and-forget" logic with precise timeouts.
2.  **Frontend (GUI - `harmony_gui.py`)**: Qt6 interface acting as a wrapper. It contains no business logic but invokes the CLI in separate threads (`QThread`) to avoid blocking the UI.

---

## 🔧 Technical Details & Development

### 1. Backend (`harmony.py`)
- **Libraries**: `aiohttp`, `asyncio`, `argparse`.
- **Configuration**: Uses `config.py` for Hub IP, Remote ID, and mappings (see `config.sample.py`).
- **Smart CLI Logic**:
  - If called as `./harmony.py <name>` (e.g., `shield`) → Starts **ACTIVITY**.
  - If called as `./harmony.py <name> <command>` (e.g., `shield DirectionUp`) → Sends command to **DEVICE**.
- **Optimized Timings**:
  - Activity Timeout: 3.0s
  - Status Timeout: 2.0s
  - IR Timeout (Press/Release): 0.2s (total ~0.45s per cycle)
  - **Press/Release**: Implements physical button simulation (sends "press", waits 0.05s, sends "release").

### 2. Frontend (`harmony_gui.py`)
- **Libraries**: `PyQt6` (Core, Widgets, Gui).
- **Layout System**:
  - Main `QVBoxLayout`.
  - **Smart Remote Section**: Unified, context-aware interface.
    - **Smart D-Pad (Left)**: Routes navigation commands (Up/Down/OK/Back) to the active device based on current Activity (e.g., Samsung TV vs Shield).
    - **TV Controls (Right)**: Dedicated Numpad and color keys for TV control.
    - **Compact Design**: Highly optimized layout for minimal screen footprint.
- **Helper**: `create_btn(text, cmd, icon)` handles creation and signal binding.
- **Styling**: Inline CSS with Python dictionary `C` for consistent theming.

---

## 🎨 Design System (Tokyo Night Modern)

The GUI implements the "Tokyo Night" aesthetic for a modern look. The file `harmony_gui.py` uses a dictionary `C` to centralize colors.

```python
C = {
    'bg':      '#1a1b26',  # Deep Night (Window Background)
    'surface': '#24283b',  # Storm (Cards, Buttons)
    'active':  '#7aa2f7',  # Blue (Focus, TV Activity, OK Button)
    'accent':  '#bb9af7',  # Purple (Music, Shield, Borders)
    'danger':  '#f7768e',  # Red (Power Off)
    'text':    '#c0caf5',  # White-ish (Main Text)
    'subtext': '#565f89',  # Grey (Labels, OFF state)
    'border':  '#414868',  # Highlight (Thin borders)
}
```

---

## 🚀 Quick Start

### 1. Installation
Clone the repository and install dependencies:

```bash
git clone git@github.com:rylos/harmony.git
cd harmony
python3 -m venv harmony_env
source harmony_env/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
Copy the sample configuration and edit it with your Hub details:

```bash
cp config.sample.py config.py
nano config.py
```
*You will need your Hub IP and Remote ID. You can find these in your router settings or by using a discovery tool.*

### 3. Usage

**GUI:**
```bash
./start_harmony_gui.sh
```

**CLI Examples:**
```bash
./harmony.py tv                    # Start "Watch TV" Activity
./harmony.py shield DirectionUp    # Send "Up" to Shield
./harmony.py samsung 1             # Send "1" to Samsung TV
./harmony.py off                   # Power Off Everything
./harmony.py list                  # List all available commands
```

---

## 📂 File Structure
- `harmony.py`: Core CLI logic.
- `harmony_gui.py`: PyQt6 Interface.
- `config.py`: User configuration (Ignored by Git).
- `DEVICE_COMMANDS.md`: Reference for all available commands.

---

**Note**: This is a personal project optimized for a specific setup but built to be easily adaptable.
