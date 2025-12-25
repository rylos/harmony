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
        margin-top: 0px;
        margin-bottom: 0px;
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
        background-color: {C['surface']};
        color: {C['danger']};
        border: 1px solid {C['danger']}40;
        outline: none;
    }}
    QPushButton#PowerOff:hover {{
        background-color: {C['danger']};
        color: {C['bg']};
        border-color: {C['danger']};
    }}
    QPushButton#PowerOff:pressed {{
        background-color: {C['danger']}cc;
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
            # 0. SMART COMMANDS (Routing dinamico basato sull'attività)
            if cmd.startswith("smart_"):
                real_cmd = cmd.replace("smart_", "")
                # Recupera attività corrente
                curr = await self.hub.get_current_fast()
                act_id = "-1"
                if "data" in curr and "result" in curr["data"]:
                    act_id = curr["data"]["result"]
                
                # Determina il target device in base all'attività
                target_dev = None
                
                # Mappa ID Attività -> Device ID
                # (Recupera gli ID dal config ACTIVITIES e DEVICES)
                tv_act_id = ACTIVITIES.get("tv", {}).get("id")
                shield_act_id = ACTIVITIES.get("shield", {}).get("id")
                music_act_id = ACTIVITIES.get("music", {}).get("id")
                
                if act_id == tv_act_id and "samsung" in DEVICES:
                    target_dev = DEVICES["samsung"]["id"]
                elif act_id == shield_act_id and "shield" in DEVICES:
                    target_dev = DEVICES["shield"]["id"]
                elif act_id == music_act_id and "onkyo" in DEVICES:
                    target_dev = DEVICES["onkyo"]["id"]
                # Fallback: se siamo in Watch TV o indefinito, prova Samsung se comando compatibile
                elif "samsung" in DEVICES:
                     target_dev = DEVICES["samsung"]["id"]

                if target_dev:
                    # Mappature comandi specifici per device se necessario (es. "Select" vs "OK")
                    # Per ora assumiamo che Harmony usi nomi standard (DirectionUp, Select, ecc.)
                    res = await self.hub.send_device_fast(target_dev, action)
                else:
                    res = {"error": "No target device for smart command"}

            # Logica duplicata da harmony.py main() ma adattata
            # 1. ATTIVITÀ (Priorità Alta per catturare 'off')
            elif cmd in ACTIVITIES:
                res = await self.hub.start_activity_fast(ACTIVITIES[cmd]["id"])
            
            # 2. AUDIO ONKYO
            elif cmd in AUDIO_COMMANDS and "onkyo" in DEVICES:
                res = await self.hub.send_device_fast(DEVICES["onkyo"]["id"], AUDIO_COMMANDS[cmd])
            
            # 3. DISPOSITIVI
            elif cmd in DEVICES and action:
                device = DEVICES[cmd]
                res = await self.hub.send_device_fast(device["id"], action)
                
            elif cmd == "audio-on" and "onkyo" in DEVICES:
                res = await self.hub.send_device_fast(DEVICES["onkyo"]["id"], "PowerOn")
            elif cmd == "audio-off" and "onkyo" in DEVICES:
                res = await self.hub.send_device_fast(DEVICES["onkyo"]["id"], "PowerOff")
            
            # Fallback per 'off' se non definito in ACTIVITIES ma richiesto esplicitamente come attività di sistema
            elif cmd == "off":
                 # PowerOff activity is typically -1
                res = await self.hub.start_activity_fast("-1")

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
        self.setFixedWidth(420)
        # Altezza minima garantita per evitare schiacciamenti
        # self.setMinimumHeight(600)  <-- RIMOSSO (lasciamo auto-size)
        
        c = QWidget()
        self.setCentralWidget(c)
        main_layout = QVBoxLayout(c)
        main_layout.setSpacing(6)
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
        remote_layout.setSpacing(16) 
        remote_layout.setContentsMargins(12, 12, 12, 12)
        
        # --- LEFT: SMART D-PAD & NAV ---
        smart_col = QVBoxLayout()
        smart_col.setSpacing(8) # Ridotto da 10
        
        lbl_smart = QLabel("NAVIGATION (Auto)")
        lbl_smart.setStyleSheet(f"color: {C['active']}; font-weight: bold; font-size: 10px;")
        lbl_smart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        smart_col.addWidget(lbl_smart)
        
        # D-Pad
        dpad = QGridLayout()
        dpad.setSpacing(8)
        
        # Smart commands: "smart_ " + action
        d_up = self.create_btn("", "smart_ DirectionUp", "▴")
        d_down = self.create_btn("", "smart_ DirectionDown", "▾")
        d_left = self.create_btn("", "smart_ DirectionLeft", "◂")
        d_right = self.create_btn("", "smart_ DirectionRight", "▸")
        d_ok = self.create_btn("OK", "smart_ Select", "")
        
        for b in [d_up, d_down, d_left, d_right, d_ok]:
            b.setFixedSize(40, 40)
            if b != d_ok: b.setStyleSheet(b.styleSheet() + "font-size: 18px;")
            else: b.setStyleSheet(b.styleSheet() + f"background: {C['active']}; color: {C['bg']}; font-weight: bold; font-size: 12px;")

        dpad.addWidget(d_up, 0, 1)
        dpad.addWidget(d_left, 1, 0)
        dpad.addWidget(d_ok, 1, 1)
        dpad.addWidget(d_right, 1, 2)
        dpad.addWidget(d_down, 2, 1)
        
        smart_col.addLayout(dpad)
        
        # Smart Nav Actions (Home, Back, Menu, Exit)
        nav_acts = QGridLayout()
        nav_acts.setSpacing(8)
        
        # Questi potrebbero essere smart o fissi. Home/Back spesso variano.
        # Usiamo smart per coerenza
        n_home = self.create_btn("Home", "smart_ Home", "🏠")
        n_back = self.create_btn("Back", "smart_ Return", "↩️") # Return/Back (Harmony often uses Return or Back)
        n_menu = self.create_btn("Menu", "smart_ Menu", "☰")
        n_exit = self.create_btn("Exit", "smart_ Exit", "✖️")
        
        for b in [n_home, n_back, n_menu, n_exit]:
            b.setFixedSize(70, 36)
            
        nav_acts.addWidget(n_menu, 0, 0)
        nav_acts.addWidget(n_home, 0, 1)
        nav_acts.addWidget(n_back, 1, 0)
        nav_acts.addWidget(n_exit, 1, 1)
        
        smart_col.addLayout(nav_acts)
        smart_col.addStretch()
        
        remote_layout.addLayout(smart_col)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background: {C['border']}; width: 1px;")
        remote_layout.addWidget(line)

        # --- RIGHT: TV NUMPAD & EXTRA ---
        tv_col = QVBoxLayout()
        tv_col.setSpacing(8) # Ridotto da 10
        
        lbl_tv = QLabel("TV CONTROLS")
        lbl_tv.setStyleSheet(f"color: {C['active']}; font-weight: bold; font-size: 10px;")
        lbl_tv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tv_col.addWidget(lbl_tv)
        
        numpad = QGridLayout()
        numpad.setSpacing(10) # Aumentato spaziatura verticale/orizzontale
        
        # 1-9
        for i in range(1, 10):
            b = self.create_btn(str(i), f"samsung {i}")
            b.setFixedSize(56, 36)
            numpad.addWidget(b, (i-1)//3, (i-1)%3)
            
        # 0 & others
        b_list = self.create_btn("List", "samsung List", "📑")
        b_0 = self.create_btn("0", "samsung 0")
        
        for b in [b_list, b_0]: b.setFixedSize(56, 36)
        
        numpad.addWidget(b_list, 3, 0)
        numpad.addWidget(b_0, 3, 1)
        # PrevChannel rimosso
        
        tv_col.addLayout(numpad)
        
        # Color Keys & Info
        colors = QHBoxLayout()
        colors.setSpacing(6)
        for col, cmd in [("#f7768e", "Red"), ("#9ece6a", "Green"), ("#e0af68", "Yellow"), ("#7aa2f7", "Blue")]:
            b = self.create_btn("", f"samsung {cmd}")
            b.setFixedSize(24, 24)
            b.setStyleSheet(f"background-color: {col}; border: none; border-radius: 12px;")
            colors.addWidget(b)
            
        tv_col.addLayout(colors)
        
        # Extra TV
        extra_tv = QHBoxLayout()
        b_info = self.create_btn("Info", "samsung Info")
        b_guide = self.create_btn("Guide", "samsung Guide")
        b_hub = self.create_btn("Hub", "samsung SmartHub")
        
        for b in [b_info, b_guide, b_hub]: 
            b.setFixedHeight(30)
            extra_tv.addWidget(b)
            
        tv_col.addLayout(extra_tv)
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
                b.setToolTip(cmd)
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
    # Fix per icona KDE/Wayland/X11
    app.setDesktopFileName("harmony-hub-controller") 
    app.setStyleSheet(STYLESHEET)
    
    # Imposta icona applicazione e finestra
    icon_path = str(Path(__file__).parent / "harmony-icon.png")
    app.setWindowIcon(QIcon(icon_path))
    
    w = GUI()
    w.setWindowIcon(QIcon(icon_path))
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
