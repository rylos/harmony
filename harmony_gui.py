#!/usr/bin/env python3
"""🌃 Harmony Hub - Modern Tokyo Night 2025"""

import sys
import asyncio
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QObject, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QIcon, QPainter, QPen

# Import diretto (assumendo che harmony.py sia nello stesso path)
import harmony
from harmony import FastHarmonyHub, DEVICES, ACTIVITIES, AUDIO_COMMANDS

# 🎨 Palette Tokyo Night Modern (Minimal)
C = {
    'bg':      '#1a1b26',  # Deep Night
    'surface': '#24283b',  # Storm
    'active':  '#7aa2f7',  # Blue
    'accent':  '#bb9af7',  # Purple
    'danger':  '#f7768e',  # Red (muted usage)
    'text':    '#c0caf5',  # White-ish
    'subtext': '#565f89',  # Grey
    'border':  '#414868',  # Highlight
}

STYLESHEET = f"""
    QMainWindow {{
        background-color: {C['bg']};
    }}
    
    QLabel {{
        color: {C['text']};
        font-family: 'Noto Sans', 'Segoe UI', sans-serif;
    }}
    
    QLabel#Header {{
        color: {C['active']};
        font-weight: bold;
        font-size: 11px;
        text-transform: uppercase;
        padding-left: 2px;
        margin-top: 8px;
    }}

    QFrame#Card {{
        background-color: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 12px;
    }}

    QPushButton {{
        background-color: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        color: {C['text']};
        padding: 6px;
        font-family: 'Noto Sans', sans-serif;
        font-size: 13px;
    }}
    
    QPushButton:hover {{
        background-color: {C['border']};
        border-color: {C['active']};
        color: #ffffff;
    }}
    
    QPushButton:pressed {{
        background-color: {C['active']};
        border-color: {C['active']};
        color: {C['bg']};
    }}

    QPushButton#PowerOff {{
        color: {C['danger']};
        border-color: {C['danger']}40;
    }}
    QPushButton#PowerOff:hover {{
        background-color: {C['danger']};
        color: {C['bg']};
        border-color: {C['danger']};
    }}

    QLabel#Status {{
        background-color: {C['surface']};
        border: 1px solid {C['border']};
        border-radius: 8px;
        color: {C['active']};
        padding: 8px;
        font-weight: bold;
        font-size: 14px;
    }}
"""

class HarmonyWorker(QThread):
    """Worker persistente che mantiene la connessione WebSocket attiva"""
    result_ready = pyqtSignal(str, object)
    status_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.loop = None
        self.hub = None
        self._cmd_queue = asyncio.Queue()
        self._running = True

    def run(self):
        """Esegue il loop asyncio in un thread separato"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._async_main())

    async def _async_main(self):
        self.hub = FastHarmonyHub()
        try:
            await self.hub.connect()
            
            while self._running:
                # Attende comandi dalla coda
                try:
                    cmd_data = await asyncio.wait_for(self._cmd_queue.get(), timeout=1.0)
                    cmd_type, args = cmd_data
                    
                    if cmd_type == "stop":
                        break
                    elif cmd_type == "command":
                        await self._handle_command(args)
                    elif cmd_type == "status":
                        await self._handle_status()
                        
                except asyncio.TimeoutError:
                    # Keepalive / status update periodico se necessario
                    pass
                except Exception as e:
                    print(f"Error in worker loop: {e}")

        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            await self.hub.close()

    async def _handle_command(self, args):
        cmd, action = args
        cmd = cmd.lower()
        res = {"error": "Unknown command"}
        
        try:
            # Logica duplicata da harmony.py main() ma adattata
            # Verifica che 'onkyo' esista nei device prima di usarlo hardcoded
            if cmd in AUDIO_COMMANDS and "onkyo" in DEVICES:
                res = await self.hub.send_device_fast(DEVICES["onkyo"]["id"], AUDIO_COMMANDS[cmd])
            elif cmd in DEVICES and action:
                device = DEVICES[cmd]
                res = await self.hub.send_device_fast(device["id"], action)
            elif cmd in ACTIVITIES:
                res = await self.hub.start_activity_fast(ACTIVITIES[cmd]["id"])
            elif cmd == "audio-on" and "onkyo" in DEVICES:
                res = await self.hub.send_device_fast(DEVICES["onkyo"]["id"], "PowerOn")
            elif cmd == "audio-off" and "onkyo" in DEVICES:
                res = await self.hub.send_device_fast(DEVICES["onkyo"]["id"], "PowerOff")
            elif cmd == "off":
                 # PowerOff activity: Get ID from config or default to -1
                off_id = ACTIVITIES.get("off", {}).get("id", "-1")
                res = await self.hub.start_activity_fast(off_id)
                
                # FORCE TV POWER OFF
                # Fix per desincronizzazione: invia esplicitamente PowerOff alla TV
                if "samsung" in DEVICES:
                     await asyncio.sleep(0.5)
                     await self.hub.send_device_fast(DEVICES["samsung"]["id"], "PowerOff")

            self.result_ready.emit(f"{cmd} {action or ''}", res)
            
        except Exception as e:
            self.result_ready.emit(f"{cmd} {action or ''}", {"error": str(e)})

    async def _handle_status(self):
        try:
            res = await self.hub.get_current_fast()
            if "data" in res and "result" in res["data"]:
                activity_id = res["data"]["result"]
                status_text = "..."
                if activity_id == "-1":
                    status_text = "⚫ OFF"
                else:
                    for name, info in ACTIVITIES.items():
                        if info["id"] == activity_id:
                            status_text = f"🟢 {info['name']}"
                            break
                    else:
                        status_text = f"🟡 ID: {activity_id}"
                self.status_updated.emit(status_text)
        except Exception as e:
            self.status_updated.emit("❌ Error")

    def queue_command(self, cmd, action=None):
        if self.loop:
            self.loop.call_soon_threadsafe(self._cmd_queue.put_nowait, ("command", (cmd, action)))

    def queue_status(self):
        if self.loop:
             self.loop.call_soon_threadsafe(self._cmd_queue.put_nowait, ("status", None))

    def stop(self):
        self._running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self._cmd_queue.put_nowait, ("stop", None))
        self.wait()

class ModernBtn(QPushButton):
    def __init__(self, text, cmd, icon=None, is_danger=False):
        super().__init__()
        if icon:
            self.setText(f"{icon}  {text}" if text else icon)
        else:
            self.setText(text)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)
        
        if is_danger:
            self.setObjectName("PowerOff")
            
        self.cmd = cmd

class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = HarmonyWorker()
        self.worker.result_ready.connect(self.on_done)
        self.worker.status_updated.connect(self.on_status)
        self.worker.start()

        self.setWindowTitle("Harmony")
        # Layout generoso e pulito
        self.setFixedWidth(540)
        # Altezza minima garantita per evitare schiacciamenti
        self.setMinimumHeight(800)
        
        c = QWidget()
        self.setCentralWidget(c)
        main_layout = QVBoxLayout(c)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # 1. Header & Status
        status_layout = QVBoxLayout()
        status_layout.setSpacing(4)
        
        title = QLabel("CURRENT ACTIVITY")
        title.setObjectName("Header")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.status = QLabel("...")
        self.status.setObjectName("Status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        status_layout.addWidget(title)
        status_layout.addWidget(self.status)
        
        # Power Off Button (Moved here for quick access)
        self.btn_off = self.create_btn("SPEGNI TUTTO", "off", "⏻", is_danger=True)
        self.btn_off.setFixedHeight(40)
        status_layout.addWidget(self.btn_off)
        
        main_layout.addLayout(status_layout)
        
        # 2. Activities Grid
        self.add_section_header(main_layout, "SCENARI")
        
        act_frame = QFrame()
        act_frame.setObjectName("Card")
        act_grid = QGridLayout(act_frame)
        act_grid.setSpacing(12)
        act_grid.setContentsMargins(16, 16, 16, 16)
        
        activities = [
            ("TV", "tv", "📺"),
            ("Music", "music", "🎵"),
            ("Shield", "shield", "🎮"),
            ("Clima", "clima", "❄️")
        ]
        
        for i, (txt, cmd, ico) in enumerate(activities):
            b = self.create_btn(txt, cmd, ico)
            act_grid.addWidget(b, i // 2, i % 2)
            
        main_layout.addWidget(act_frame)

        # 3. SMART REMOTE
        self.add_section_header(main_layout, "SMART REMOTE")
        
        remote_frame = QFrame()
        remote_frame.setObjectName("Card")
        remote_layout = QHBoxLayout(remote_frame)
        remote_layout.setSpacing(24) 
        remote_layout.setContentsMargins(20, 20, 20, 20)
        
        # --- LEFT: SHIELD ---
        shield_col = QVBoxLayout()
        shield_col.setSpacing(16)
        
        lbl_shield = QLabel("SHIELD")
        lbl_shield.setStyleSheet(f"color: {C['active']}; font-weight: bold; font-size: 10px;")
        lbl_shield.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_col.addWidget(lbl_shield)
        
        # D-Pad
        dpad = QGridLayout()
        dpad.setSpacing(8)
        
        s_up = self.create_btn("", "shield DirectionUp", "▴")
        s_down = self.create_btn("", "shield DirectionDown", "▾")
        s_left = self.create_btn("", "shield DirectionLeft", "◂")
        s_right = self.create_btn("", "shield DirectionRight", "▸")
        s_ok = self.create_btn("OK", "shield Select", "")
        
        for b in [s_up, s_down, s_left, s_right, s_ok]:
            b.setFixedSize(36, 36)
            if b != s_ok: b.setStyleSheet(b.styleSheet() + "font-size: 16px;")
            else: b.setStyleSheet(b.styleSheet() + f"background: {C['active']}; color: {C['bg']}; font-weight: bold; font-size: 11px;")

        dpad.addWidget(s_up, 0, 1)
        dpad.addWidget(s_left, 1, 0)
        dpad.addWidget(s_ok, 1, 1)
        dpad.addWidget(s_right, 1, 2)
        dpad.addWidget(s_down, 2, 1)
        
        shield_col.addLayout(dpad)
        
        # Shield Actions
        s_acts = QHBoxLayout()
        s_acts.setSpacing(8)
        for txt, cmd, icon in [("🏠", "shield Home", None), ("↩️", "shield Back", None), ("⏯", "shield Play", None), ("⏹", "shield Stop", None)]:
            b = self.create_btn(txt, cmd, icon)
            b.setFixedSize(36, 32)
            s_acts.addWidget(b)
        shield_col.addLayout(s_acts)
        shield_col.addStretch()
        
        remote_layout.addLayout(shield_col)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background: {C['border']}; width: 1px;")
        remote_layout.addWidget(line)

        # --- RIGHT: TV NUMPAD ---
        tv_col = QVBoxLayout()
        tv_col.setSpacing(16)
        
        lbl_tv = QLabel("TV NUMPAD")
        lbl_tv.setStyleSheet(f"color: {C['active']}; font-weight: bold; font-size: 10px;")
        lbl_tv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tv_col.addWidget(lbl_tv)
        
        numpad = QGridLayout()
        numpad.setSpacing(8)
        
        for i in range(1, 10):
            b = self.create_btn(str(i), f"samsung {i}")
            b.setFixedSize(36, 36)
            numpad.addWidget(b, (i-1)//3, (i-1)%3)
            
        b_0 = self.create_btn("0", "samsung 0")
        b_0.setFixedSize(36, 36)
        numpad.addWidget(b_0, 3, 1)
        
        b_ok = self.create_btn("OK", "samsung Select")
        b_ok.setFixedSize(36, 36)
        b_ok.setStyleSheet(b_ok.styleSheet() + f"border-color: {C['active']}; color: {C['active']}; font-size: 11px;")
        numpad.addWidget(b_ok, 3, 2)
        
        b_info = self.create_btn("ℹ️", "samsung Info")
        b_info.setFixedSize(36, 36)
        numpad.addWidget(b_info, 3, 0)
        
        tv_col.addLayout(numpad)
        tv_col.addStretch()
        
        remote_layout.addLayout(tv_col)
        main_layout.addWidget(remote_frame)

        # 4. Audio & System
        self.add_section_header(main_layout, "AUDIO & SYSTEM")
        
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("Card")
        ctrl_layout = QGridLayout(ctrl_frame)
        ctrl_layout.setSpacing(10)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)
        
        ctrl_layout.addWidget(self.create_btn("", "vol-", "➖"), 0, 0)
        ctrl_layout.addWidget(self.create_btn("Mute", "mute", "🔇"), 0, 1)
        ctrl_layout.addWidget(self.create_btn("", "vol+", "➕"), 0, 2)
        
        main_layout.addWidget(ctrl_frame)

        # 5. Devices
        self.add_section_header(main_layout, "DISPOSITIVI")
        
        dev_frame = QFrame()
        dev_frame.setObjectName("Card")
        dev_layout = QVBoxLayout(dev_frame)
        dev_layout.setSpacing(8)
        dev_layout.setContentsMargins(12, 12, 12, 12)
        
        # Lista dispositivi generica se presente in config, altrimenti fallback parziale
        # Usiamo DEVICES dal config se possibile per generare la lista
        devices_to_show = []
        if "samsung" in DEVICES:
             devices_to_show.append(("Samsung TV", "samsung", [("⏻", "PowerToggle"), ("⚙️", "SmartHub")]))
        if "shield" in DEVICES:
             devices_to_show.append(("NVIDIA Shield", "shield", [("🏠", "Home"), ("↩️", "Back")]))
        if "onkyo" in DEVICES:
             devices_to_show.append(("Onkyo Audio", "onkyo", [("📺", "ListeningModeTvLogic"), ("🎵", "ModeMusic")]))
             
        # Se DEVICES ha altri dispositivi non mappati qui, potremmo aggiungerli genericamente,
        # ma per ora manteniamo la UI pulita con quelli supportati specificamente se presenti.
        
        for name, dev_code, actions in devices_to_show:
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setStyleSheet(f"color: {C['subtext']}; font-weight: bold;")
            row.addWidget(lbl)
            row.addStretch()
            
            for icon, cmd in actions:
                b = self.create_btn("", f"{dev_code} {cmd}", icon)
                b.setFixedSize(38, 32)
                row.addWidget(b)
            
            dev_layout.addLayout(row)
            
        main_layout.addWidget(dev_frame)
        
        # Init
        self.update_status()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(10000)
        self.adjustSize()

    def create_btn(self, text, cmd, icon=None, is_danger=False):
        """Helper per creare bottoni già connessi"""
        b = ModernBtn(text, cmd, icon, is_danger)
        # IMPORTANTE: usa lambda con default arg c=cmd per catturare il valore corrente!
        b.clicked.connect(lambda _, c=cmd: self.run(c))
        return b

    def add_section_header(self, layout, text):
        lbl = QLabel(text)
        lbl.setObjectName("Header")
        layout.addWidget(lbl)

    def run(self, cmd):
        # Parsa il comando per separare azione se necessario
        parts = cmd.split(maxsplit=1)
        command = parts[0]
        action = parts[1] if len(parts) > 1 else None
        
        self.status.setText(f"🚀 {cmd}...")
        self.status.setStyleSheet(f"QLabel#Status {{ color: {C['active']}; border-color: {C['active']}; }}")
        self.worker.queue_command(command, action)
    
    def on_done(self, cmd, res):
        if "error" in res:
             self.status.setText(f"❌ {res['error']}")
             self.status.setStyleSheet(f"QLabel#Status {{ color: {C['danger']}; border-color: {C['danger']}; }}")
             QTimer.singleShot(3000, self.update_status)
        else:
             if "off" in cmd: self.status.setText("⚫ SPEGNIMENTO...")
             else: QTimer.singleShot(500, self.update_status)
    
    def update_status(self):
        self.worker.queue_status()
    
    def on_status(self, status_text):
        if "OFF" in status_text or "-1" in status_text: txt, col = "SYSTEM OFF", C['subtext']
        elif "Guarda TV" in status_text: txt, col = "📺 TV MODE", C['active']
        elif "Music" in status_text: txt, col = "🎵 MUSIC MODE", C['accent']
        elif "Shield" in status_text: txt, col = "🎮 SHIELD", '#7dcfff'
        elif "Condizionatore" in status_text or "Clima" in status_text: txt, col = "❄️ CLIMA", '#7dcfff'
        else:
            clean_res = status_text.replace("✅", "").strip()
            txt, col = clean_res, C['text']
            
        self.status.setText(txt)
        self.status.setStyleSheet(f"QLabel#Status {{ color: {col}; border-color: {col}; }}")

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    
    w = GUI()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
