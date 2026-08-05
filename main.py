import sys
import time
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSlider, QFrame, QTextEdit
)
from PyQt6.QtGui import QKeySequence, QShortcut, QRegion
import mss
from PIL import Image

class ScreenTipMasterOverlay(QWidget):
    def __init__(self):
        super().__init__()

        # Full-Screen Always-On-Top Translucent Overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Screen Tip AI — Desktop Overlay")

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

        # Initial Coordinates for Box 1, Box 2, and Box 3
        start_y = max(80, int(screen.height() * 0.10))
        box1_x = max(60, int(screen.width() * 0.05))
        box2_x = box1_x + 540

        if box2_x + 480 > screen.width():
            box2_x = max(20, screen.width() - 500)

        self.box1_rect = QRect(box1_x, start_y, 500, 320)
        self.box2_rect = QRect(box2_x, start_y, 480, 520)
        self.box3_rect = QRect(box2_x, start_y + 535, 480, 160)

        # Drag & Resize state
        self.dragging_box1 = False
        self.dragging_box2 = False
        self.dragging_box3 = False
        self.resizing_box1 = False

        self.drag_start_pos = QPoint()
        self.box1_start_rect = QRect()
        self.box2_start_rect = QRect()
        self.box3_start_rect = QRect()

        self.opacity_val = 0.92
        self.active_preset = "coding"
        self.settings_visible = False

        self.init_ui()

    def init_ui(self):
        # Container
        self.container = QWidget(self)
        self.container.setGeometry(self.rect())

        # ==========================================
        # BOX 1: SCANNER LENS WIDGETS
        # ==========================================
        self.box1_bar = QFrame(self.container)
        self.box1_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 240);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 8px;
            }
            QLabel {
                color: #38bdf8;
                font-family: 'Inter', sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #38bdf8;
                color: #0f172a;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #7dd3fc;
            }
        """)

        bar_layout = QHBoxLayout(self.box1_bar)
        bar_layout.setContentsMargins(10, 4, 10, 4)

        self.move_handle = QLabel("⠿ Drag to Move")
        self.move_handle.setCursor(Qt.CursorShape.SizeAllCursor)

        self.box1_title = QLabel(f"[{self.box1_rect.width()}x{self.box1_rect.height()-38}px]")
        self.box1_title.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: normal;")

        self.scan_btn = QPushButton("Scan & Solve (Ctrl+G)")
        self.scan_btn.clicked.connect(self.trigger_scan)

        # Global Shortcut: Ctrl+G
        self.scan_shortcut = QShortcut(QKeySequence("Ctrl+G"), self)
        self.scan_shortcut.activated.connect(self.trigger_scan)

        self.close_btn = QPushButton("✕ Exit (Esc)")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.85);
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ef4444;
            }
        """)
        self.close_btn.clicked.connect(QApplication.instance().quit)

        bar_layout.addWidget(self.move_handle)
        bar_layout.addWidget(self.box1_title)
        bar_layout.addStretch()
        bar_layout.addWidget(self.scan_btn)
        bar_layout.addWidget(self.close_btn)

        self.box1_lens = QFrame(self.container)
        self.box1_lens.setStyleSheet("""
            QFrame {
                background: transparent;
                border: 3px solid #ffffff;
                border-radius: 14px;
            }
        """)

        # Box 1 Resize Handle Grip (Discrete exterior corner)
        self.box1_grip = QLabel("", self.container)
        self.box1_grip.setStyleSheet("""
            QLabel {
                background-color: #38bdf8;
                border: 2px solid #ffffff;
                border-radius: 4px;
            }
            QLabel:hover {
                background-color: #ffffff;
                border: 2px solid #38bdf8;
            }
        """)
        self.box1_grip.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.box1_grip.setToolTip("Drag to Resize Box 1")

        # ==========================================
        # BOX 2: SOLUTION HUD WIDGET
        # ==========================================
        self.box2_card = QFrame(self.container)
        self.update_card_styles()

        box2_layout = QVBoxLayout(self.box2_card)
        box2_layout.setContentsMargins(16, 12, 16, 16)

        # Clean Header Bar (No stealth slider cluttering!)
        box2_header = QHBoxLayout()
        title_lbl = QLabel("Box 2: Solution HUD")
        title_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        title_lbl.setCursor(Qt.CursorShape.SizeAllCursor)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 200);
                color: #38bdf8;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 6px;
                border: 1px solid rgba(56, 189, 248, 0.4);
            }
            QPushButton:hover {
                background-color: #38bdf8;
                color: #0f172a;
            }
        """)
        self.settings_btn.clicked.connect(self.toggle_settings)

        self.box2_close_btn = QPushButton("✕")
        self.box2_close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.85);
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #ef4444;
            }
        """)
        self.box2_close_btn.setToolTip("Exit App (Esc)")
        self.box2_close_btn.clicked.connect(QApplication.instance().quit)

        box2_header.addWidget(title_lbl)
        box2_header.addStretch()
        box2_header.addWidget(self.settings_btn)
        box2_header.addWidget(self.box2_close_btn)
        box2_layout.addLayout(box2_header)

        # Preset Buttons
        preset_layout = QHBoxLayout()
        self.btn_coding = QPushButton("Coding")
        self.btn_design = QPushButton("Design")
        self.btn_mcq = QPushButton("MCQ")

        for btn in (self.btn_coding, self.btn_design, self.btn_mcq):
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(30, 41, 59, 200);
                    color: #cbd5e1;
                    font-size: 11px;
                    border-radius: 6px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: rgba(51, 65, 85, 240);
                    color: #ffffff;
                }
            """)

        self.btn_coding.clicked.connect(lambda: self.set_preset("coding"))
        self.btn_design.clicked.connect(lambda: self.set_preset("system-design"))
        self.btn_mcq.clicked.connect(lambda: self.set_preset("mcq"))

        preset_layout.addWidget(self.btn_coding)
        preset_layout.addWidget(self.btn_design)
        preset_layout.addWidget(self.btn_mcq)
        preset_layout.addStretch()
        box2_layout.addLayout(preset_layout)

        # Result View Text Widget
        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 15, 29, 220);
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                padding: 10px;
                font-family: 'JetBrains Mono', 'Inter', monospace;
                font-size: 12px;
            }
        """)
        self.result_view.setHtml("<p style='color: #94a3b8;'>Slide <b>Box 1</b> over your question and press <b>Ctrl+G</b> or click <b>Scan & Solve</b></p>")
        box2_layout.addWidget(self.result_view)

        # ==========================================
        # BOX 3: SETTINGS WINDOW WIDGET
        # ==========================================
        self.box3_card = QFrame(self.container)
        box3_layout = QVBoxLayout(self.box3_card)
        box3_layout.setContentsMargins(16, 12, 16, 14)

        # Box 3 Header
        box3_header = QHBoxLayout()
        settings_lbl = QLabel("Box 3: Settings")
        settings_lbl.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: bold;")
        settings_lbl.setCursor(Qt.CursorShape.SizeAllCursor)

        self.box3_close_btn = QPushButton("✕")
        self.box3_close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(51, 65, 85, 200);
                color: #cbd5e1;
                font-weight: bold;
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
            }
        """)
        self.box3_close_btn.clicked.connect(self.hide_settings)

        box3_header.addWidget(settings_lbl)
        box3_header.addStretch()
        box3_header.addWidget(self.box3_close_btn)
        box3_layout.addLayout(box3_header)

        # Stealth Opacity Control Row
        slider_row = QHBoxLayout()
        op_title = QLabel("Stealth Opacity:")
        op_title.setStyleSheet("color: #e2e8f0; font-size: 12px;")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(15, 100)
        self.slider.setValue(int(self.opacity_val * 100))
        self.slider.valueChanged.connect(self.on_opacity_change)

        self.op_badge = QLabel(f"{int(self.opacity_val * 100)}%")
        self.op_badge.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px; min-width: 36px;")

        slider_row.addWidget(op_title)
        slider_row.addWidget(self.slider)
        slider_row.addWidget(self.op_badge)
        box3_layout.addLayout(slider_row)

        # Shortcuts Info Row
        info_lbl = QLabel("Shortcuts:  Scan = Ctrl+G  |  Quit = Esc / Q")
        info_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; margin-top: 4px;")
        box3_layout.addWidget(info_lbl)

        # Hide Settings by default
        self.box3_card.hide()

        self.reposition_widgets()

    def update_card_styles(self):
        alpha = int(self.opacity_val * 240)
        style = f"""
            QFrame {{
                background-color: rgba(15, 23, 42, {alpha});
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 16px;
            }}
        """
        if hasattr(self, "box2_card"):
            self.box2_card.setStyleSheet(style)
        if hasattr(self, "box3_card"):
            self.box3_card.setStyleSheet(style)

    def on_opacity_change(self, val):
        self.opacity_val = val / 100.0
        self.op_badge.setText(f"{val}%")
        self.update_card_styles()

    def toggle_settings(self):
        if self.settings_visible:
            self.hide_settings()
        else:
            self.show_settings()

    def show_settings(self):
        self.settings_visible = True
        self.box3_card.show()
        self.update_window_mask()

    def hide_settings(self):
        self.settings_visible = False
        self.box3_card.hide()
        self.update_window_mask()

    def set_preset(self, preset):
        self.active_preset = preset

    def update_window_mask(self):
        """
        Input mask for OS pass-through clicks:
        - Box 1 Header Bar, Box 1 Border, Box 1 Grip, Box 2 Card, and Box 3 Card (if visible) accept clicks.
        - All other screen space passes clicks straight to underlying windows!
        """
        mask = QRegion(self.box1_bar.geometry())
        mask = mask.united(QRegion(self.box1_grip.geometry()))
        mask = mask.united(QRegion(self.box2_card.geometry()))

        if self.settings_visible:
            mask = mask.united(QRegion(self.box3_card.geometry()))

        # Add 4px border ring for Box 1 lens
        lens_geom = self.box1_lens.geometry()
        outer_ring = QRegion(lens_geom)
        inner_ring = QRegion(lens_geom.adjusted(4, 4, -4, -4))
        border_ring = outer_ring.subtracted(inner_ring)

        mask = mask.united(border_ring)
        self.setMask(mask)

    def reposition_widgets(self):
        # Position Box 1 Header Bar
        self.box1_bar.setGeometry(
            self.box1_rect.x(),
            self.box1_rect.y(),
            self.box1_rect.width(),
            36
        )
        self.box1_title.setText(f"[{self.box1_rect.width()}x{self.box1_rect.height()-38}px]")

        # Position Box 1 Lens Frame
        self.box1_lens.setGeometry(
            self.box1_rect.x(),
            self.box1_rect.y() + 38,
            self.box1_rect.width(),
            self.box1_rect.height() - 38
        )

        # Position Discrete Resize Grip OUTSIDE bottom-right corner of Box 1 Lens
        self.box1_grip.setGeometry(
            self.box1_rect.x() + self.box1_rect.width() - 4,
            self.box1_rect.y() + self.box1_rect.height() - 4,
            12,
            12
        )

        # Position Box 2 Solution HUD Window
        self.box2_card.setGeometry(self.box2_rect)

        # Position Box 3 Settings Window
        self.box3_card.setGeometry(self.box3_rect)

        # Apply OS input pass-through mask
        self.update_window_mask()

    def trigger_scan(self):
        self.scan_btn.setText("Scanning...")
        QApplication.processEvents()

        # Capture Desktop screen under Box 1 lens
        lens_y = self.box1_rect.y() + 38
        lens_h = self.box1_rect.height() - 38

        with mss.MSS() as sct:
            monitor = {
                "top": lens_y,
                "left": self.box1_rect.x(),
                "width": self.box1_rect.width(),
                "height": lens_h
            }
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        time.sleep(0.3)

        if self.active_preset == "coding":
            html = """
            <h3 style='color: #38bdf8;'>Two Sum Problem</h3>
            <p><b>Question:</b> Given an array of integers <code>nums</code> and an integer <code>target</code>, return indices of the two numbers such that they add up to target.</p>
            <hr style='border: 1px solid rgba(255,255,255,0.1);'>
            <h4 style='color: #a855f7;'>Solution Code (Python):</h4>
            <pre style='background: #090d16; padding: 8px; border-radius: 6px; color: #38bdf8;'>
def twoSum(nums: list[int], target: int) -> list[int]:
    seen = {}
    for i, num in enumerate(nums):
        diff = target - num
        if diff in seen:
            return [seen[diff], i]
        seen[num] = i
    return []
            </pre>
            <p><b>Time Complexity:</b> O(N) | <b>Space Complexity:</b> O(N)</p>
            """
        elif self.active_preset == "system-design":
            html = """
            <h3 style='color: #a855f7;'>System Design: URL Shortener</h3>
            <p><b>Key Architecture Components:</b></p>
            <ul>
                <li><b>API Gateway:</b> POST /shorten, GET /{key} (302 redirect)</li>
                <li><b>Key Generator:</b> Base62 encoding of 64-bit auto-incrementing ID</li>
                <li><b>Cache Layer:</b> Redis cluster caching top 20% hot links</li>
                <li><b>Database:</b> Cassandra / DynamoDB partitioned by hash(shortKey)</li>
            </ul>
            """
        else:
            html = """
            <h3 style='color: #34d399;'>Multiple Choice Question</h3>
            <p><b>Correct Answer:</b> Option (C) Hash Table</p>
            <p><b>Explanation:</b> Hash tables compute array indices via a hash function, providing O(1) expected time complexity for lookups.</p>
            """

        self.result_view.setHtml(html)
        self.scan_btn.setText("Scan & Solve (Ctrl+G)")

    # Mouse Dragging & Resizing Handlers
    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        if self.box1_grip.geometry().contains(pos):
            self.resizing_box1 = True
            self.drag_start_pos = pos
            self.box1_start_rect = QRect(self.box1_rect)
        elif self.box1_bar.geometry().contains(pos) or self.box1_lens.geometry().contains(pos):
            self.dragging_box1 = True
            self.drag_start_pos = pos
            self.box1_start_rect = QRect(self.box1_rect)
        elif self.box2_card.geometry().contains(pos):
            self.dragging_box2 = True
            self.drag_start_pos = pos
            self.box2_start_rect = QRect(self.box2_rect)
        elif self.settings_visible and self.box3_card.geometry().contains(pos):
            self.dragging_box3 = True
            self.drag_start_pos = pos
            self.box3_start_rect = QRect(self.box3_rect)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self.resizing_box1:
            delta = pos - self.drag_start_pos
            new_w = max(220, self.box1_start_rect.width() + delta.x())
            new_h = max(140, self.box1_start_rect.height() + delta.y())
            self.box1_rect.setWidth(new_w)
            self.box1_rect.setHeight(new_h)
            self.reposition_widgets()
        elif self.dragging_box1:
            delta = pos - self.drag_start_pos
            new_x = max(0, self.box1_start_rect.x() + delta.x())
            new_y = max(0, self.box1_start_rect.y() + delta.y())
            self.box1_rect.moveTo(new_x, new_y)
            self.reposition_widgets()
        elif self.dragging_box2:
            delta = pos - self.drag_start_pos
            new_x = max(0, self.box2_start_rect.x() + delta.x())
            new_y = max(0, self.box2_start_rect.y() + delta.y())
            self.box2_rect.moveTo(new_x, new_y)
            self.reposition_widgets()
        elif self.dragging_box3:
            delta = pos - self.drag_start_pos
            new_x = max(0, self.box3_start_rect.x() + delta.x())
            new_y = max(0, self.box3_start_rect.y() + delta.y())
            self.box3_rect.moveTo(new_x, new_y)
            self.reposition_widgets()

    def mouseReleaseEvent(self, event):
        self.dragging_box1 = False
        self.dragging_box2 = False
        self.dragging_box3 = False
        self.resizing_box1 = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape or event.key() == Qt.Key.Key_Q:
            QApplication.instance().quit()
        elif (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_G:
            self.trigger_scan()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScreenTipMasterOverlay()
    window.show()
    sys.exit(app.exec())
