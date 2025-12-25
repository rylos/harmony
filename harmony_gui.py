#!/home/marco/dev/harmony/harmony_env/bin/python
"""🌃 Harmony Hub - Modern Tokyo Night 2025"""

import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QPainter, QPen

HARMONY_CLI = Path(__file__).parent / "harmony.py"

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

class Worker(QThread):
    done = pyqtSignal(str, str)
    fail = pyqtSignal(str, str)
    
    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
    
    def run(self):
        try:
            r = subprocess.run([str(HARMONY_CLI)] + self.cmd.split(), 
                             capture_output=True, text=True, timeout=10)
            (self.done if r.returncode == 0 else self.fail).emit(self.cmd, r.stdout.strip() or r.stderr.strip())
        except Exception as e:
            self.fail.emit(self.cmd, str(e))

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
        self.w = None
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
        
        btn_off = self.create_btn("Spegni Tutto", "off", "⏻", is_danger=True)
        ctrl_layout.addWidget(btn_off, 1, 0, 1, 3)
        
        main_layout.addWidget(ctrl_frame)

        # 5. Devices
        self.add_section_header(main_layout, "DISPOSITIVI")
        
        dev_frame = QFrame()
        dev_frame.setObjectName("Card")
        dev_layout = QVBoxLayout(dev_frame)
        dev_layout.setSpacing(8)
        dev_layout.setContentsMargins(12, 12, 12, 12)
        
        devices = [
            ("Samsung TV", "samsung", [("⏻", "PowerToggle"), ("⚙️", "SmartHub")]),
            ("NVIDIA Shield", "shield", [("🏠", "Home"), ("↩️", "Back")]),
            ("Onkyo Audio", "onkyo", [("📺", "ListeningModeTvLogic"), ("🎵", "ModeMusic")])
        ]
        
        for name, dev_code, actions in devices:
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
        if self.w and self.w.isRunning(): return
        self.status.setText(f"🚀 {cmd}...")
        self.status.setStyleSheet(f"QLabel#Status {{ color: {C['active']}; border-color: {C['active']}; }}")
        self.w = Worker(cmd)
        self.w.done.connect(self.on_done)
        self.w.fail.connect(self.on_fail)
        self.w.start()
    
    def on_done(self, cmd, res):
        if cmd in ["off"]: self.status.setText("⚫ SPEGNIMENTO...")
        else: QTimer.singleShot(500, self.update_status)
    
    def on_fail(self, cmd, err):
        self.status.setText("❌ ERROR")
        self.status.setStyleSheet(f"QLabel#Status {{ color: {C['danger']}; border-color: {C['danger']}; }}")
        QTimer.singleShot(3000, self.update_status)
    
    def update_status(self):
        if self.w and self.w.isRunning(): return
        self.w = Worker("status")
        self.w.done.connect(self.on_status)
        self.w.start()
    
    def on_status(self, cmd, res):
        if "status" in res and "sent" in res: return
        if "OFF" in res or "-1" in res: txt, col = "SYSTEM OFF", C['subtext']
        elif "Guarda TV" in res: txt, col = "📺 TV MODE", C['active']
        elif "musica" in res: txt, col = "🎵 MUSIC MODE", C['accent']
        elif "Shield" in res: txt, col = "🎮 SHIELD", '#7dcfff'
        elif "Condizionatore" in res or "Clima" in res: txt, col = "❄️ CLIMA", '#7dcfff'
        else:
            clean_res = res.replace("✅", "").strip()
            if not clean_res: return
            txt, col = clean_res, C['text']
        self.status.setText(txt)
        self.status.setStyleSheet(f"QLabel#Status {{ color: {col}; border-color: {col}; }}")

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    
    if not HARMONY_CLI.exists():
        QMessageBox.critical(None, "Errore", f"CLI non trovato: {HARMONY_CLI}")
        sys.exit(1)
    
    w = GUI()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
