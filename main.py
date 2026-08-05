import sys
import time
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSlider, QFrame, QTextEdit
)
from PyQt6.QtGui import QKeySequence, QShortcut
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

        # Explicit Initial Positions for Box 1 and Box 2
        start_y = max(80, int(screen.height() * 0.12))
        box1_x = max(60, int(screen.width() * 0.06))
        box2_x = box1_x + 540

        if box2_x + 480 > screen.width():
            box2_x = max(20, screen.width() - 500)

        self.box1_rect = QRect(box1_x, start_y, 500, 320)
        self.box2_rect = QRect(box2_x, start_y, 480, 560)

        # Drag & Resize state
        self.dragging_box1 = False
        self.dragging_box2 = False
        self.resizing_box1 = False
        self.drag_start_pos = QPoint()
        self.box1_start_rect = QRect()
        self.box2_start_rect = QRect()

        self.opacity_val = 0.92
        self.active_preset = "coding"

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

        # Box 1 Resize Handle Grip (Discrete & outside bottom-right corner)
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
        self.update_box2_style()

        box2_layout = QVBoxLayout(self.box2_card)
        box2_layout.setContentsMargins(16, 12, 16, 16)

        # Header Bar
        header_layout = QHBoxLayout()
        title_lbl = QLabel("Box 2: Solution HUD")
        title_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        title_lbl.setCursor(Qt.CursorShape.SizeAllCursor)

        # Opacity Slider & Box 2 Close Button
        opacity_layout = QHBoxLayout()
        op_lbl = QLabel("Stealth:")
        op_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(15, 100)
        self.slider.setValue(int(self.opacity_val * 100))
        self.slider.setFixedWidth(70)
        self.slider.valueChanged.connect(self.on_opacity_change)

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
        self.box2_close_btn.setToolTip("Close Solution HUD & Exit (Esc)")
        self.box2_close_btn.clicked.connect(QApplication.instance().quit)

        opacity_layout.addWidget(op_lbl)
        opacity_layout.addWidget(self.slider)
        opacity_layout.addWidget(self.box2_close_btn)

        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addLayout(opacity_layout)
        box2_layout.addLayout(header_layout)

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
        self.result_view.setHtml("<p style='color: #94a3b8;'>Slide <b>Box 1</b> over your question and click <b>Scan & Solve</b></p>")
        box2_layout.addWidget(self.result_view)

        self.reposition_widgets()

    def update_box2_style(self):
        alpha = int(self.opacity_val * 240)
        self.box2_card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(15, 23, 42, {alpha});
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 16px;
            }}
        """)

    def on_opacity_change(self, val):
        self.opacity_val = val / 100.0
        self.update_box2_style()

    def set_preset(self, preset):
        self.active_preset = preset

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
        self.scan_btn.setText("Scan & Solve")

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

    def mouseReleaseEvent(self, event):
        self.dragging_box1 = False
        self.dragging_box2 = False
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
