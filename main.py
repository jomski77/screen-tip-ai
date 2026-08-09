"""
Screen Tip AI — Desktop Overlay Application

Main entry point for Screen Tip AI PyQt6 desktop overlay.
Provides a resizable transparent scanner box (Box 1), a solution HUD (Box 2),
and settings controls (Box 3). Integrated with automated web Gemini scraping
without requiring an API key.

Design Patterns Used:
- Worker Thread & Task Queue Pattern (QThread + queue.Queue): 
  Enforces single-thread ownership of the Playwright browser instance. This prevents 
  multiple browser windows from opening and guarantees zero profile lock conflicts.
- Observer Pattern (pyqtSignal): Connects worker thread events to UI display updates.
"""

import sys
import os
import time
import tempfile
import queue
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSlider, QFrame, QTextEdit
)
from PyQt6.QtGui import QKeySequence, QShortcut, QRegion
import mss
from PIL import Image, ImageGrab

from gemini_api_engine import GeminiAPIEngine, GeminiAPIError
from gemini_web_automation import GeminiWebAutomator, GeminiAutomationError
from logger_config import get_logger

# Configure structured UI logger
logger = get_logger("OverlayUI")


class GeminiBridgeThread(QThread):
    """
    Worker QThread managing AI query tasks using the official Gemini Vision API
    (powered by gemini_key in .env). Provides ultra-fast ~1s responses with zero
    browser popups or window locks.
    """
    status_updated = pyqtSignal(str)
    answer_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    init_finished = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.task_queue = queue.Queue()
        self._running = True
        logger.info("[GeminiBridgeThread] Initialized Gemini API query task thread.")

    def enqueue_scan(self, image_path: str, preset: str):
        """Enqueue a new scan task for the worker thread to process."""
        logger.info(f"[GeminiBridgeThread] Enqueueing scan task: {image_path} | preset: {preset}")
        self.task_queue.put(("SCAN", image_path, preset))

    def stop(self):
        """Signal the worker thread to stop and exit loop cleanly."""
        logger.info("[GeminiBridgeThread] Stop signal received.")
        self._running = False
        self.task_queue.put(("STOP", None, None))

    def run(self):
        """Execution loop initializing Gemini API Engine and processing tasks."""
        logger.info("[GeminiBridgeThread] API worker thread started.")
        api_engine = None

        # 1. Initialize API Engine ONCE from .env
        try:
            self.status_updated.emit("Initializing Gemini Vision API Engine...")
            api_engine = GeminiAPIEngine.get_instance()
            self.init_finished.emit(True)
            self.status_updated.emit("Gemini Vision API Ready (Ctrl+G to Scan)")
        except Exception as e:
            logger.error(f"[GeminiBridgeThread] API Engine initialization warning: {e}")
            self.status_updated.emit(f"API Notice: {str(e)}")
            self.init_finished.emit(False)

        # 2. Continuous Task Loop
        while self._running:
            try:
                task = self.task_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            action, image_path, preset = task
            if action == "STOP" or not self._running:
                break

            if action == "SCAN":
                try:
                    logger.info(f"[GeminiBridgeThread] Processing API scan task: {image_path} ({preset})")
                    
                    prompt_map = {
                        "coding": (
                            "Analyze this screenshot containing a programming question or code snippet. "
                            "Provide a clean, formatted solution with code, step-by-step logic, and time/space complexity."
                        ),
                        "system-design": (
                            "Analyze this screenshot of a system design prompt. "
                            "Outline key architecture components, data flows, database choices, and trade-offs."
                        ),
                        "mcq": (
                            "Analyze this multiple-choice question screenshot. "
                            "Identify the correct option (A/B/C/D) and provide a concise explanation."
                        )
                    }
                    prompt = prompt_map.get(
                        preset, 
                        "Analyze this screenshot problem. Provide a concise, accurate solution with formatted code."
                    )
                    # Execute query via official Gemini API Engine
                    if not api_engine:
                        api_engine = GeminiAPIEngine.get_instance()

                    # Verify screenshot file exists on disk
                    if not os.path.exists(image_path):
                        time.sleep(0.05)  # Brief pause for OS disk flush
                        if not os.path.exists(image_path):
                            raise GeminiAPIError(f"Screenshot file capture failed: {image_path}")

                    answer_html = api_engine.query_image(
                        image_input=image_path,
                        prompt_text=prompt,
                        status_callback=lambda msg: self.status_updated.emit(msg)
                    )
                    self.answer_received.emit(answer_html)
                except Exception as e:
                    logger.error(f"[GeminiBridgeThread] Gemini Vision API Query failed: {e}", exc_info=True)
                    self.error_occurred.emit(f"Gemini API Error: {str(e)}")
                finally:
                    self.task_queue.task_done()

        logger.info("[GeminiBridgeThread] Worker thread shutdown complete.")



class ScreenTipMasterOverlay(QWidget):
    """
    Main PyQt6 Overlay Window for Screen Tip AI.
    
    Contains:
    - Box 1: Scanner Lens (Transparent capture region)
    - Box 2: Solution HUD (Formated solution viewer)
    - Box 3: Settings Panel (Opacity slider & shortcut hints)
    """

    def __init__(self):
        super().__init__()

        # Full-Screen Always-On-Top Translucent Overlay Configuration
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Screen Tip AI — Desktop Overlay")

        # Combined Virtual Desktop Geometry spanning all connected monitors
        virtual_rect = QRect()
        for s in QApplication.screens():
            virtual_rect = virtual_rect.united(s.geometry())
        self.setGeometry(virtual_rect)

        screen = QApplication.primaryScreen().geometry()

        # Initial Coordinates for Box 1, Box 2, and Box 3
        start_y = max(80, int(screen.height() * 0.10))
        box1_x = max(60, int(screen.width() * 0.05))
        box2_x = box1_x + 540

        if box2_x + 480 > screen.width():
            box2_x = max(20, screen.width() - 500)

        self.box1_rect = QRect(box1_x, start_y, 500, 320)
        self.box2_rect = QRect(box2_x, start_y, 480, 520)
        self.box3_rect = QRect(box2_x, start_y + 535, 480, 160)

        # Drag & Resize State Variables
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

        # Single Dedicated Automation Bridge Worker Thread
        self.bridge_thread = None

        self.init_ui()

        # Start single background bridge thread for browser pre-warming & scans
        self.start_automation_bridge()

    def init_ui(self):
        """Construct all UI widgets and layout hierarchies."""
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
        self.close_btn.clicked.connect(self.close_application)

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

        # Box 1 Resize Handle Grip
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

        # Header Bar
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
        self.box2_close_btn.clicked.connect(self.close_application)

        box2_header.addWidget(title_lbl)
        box2_header.addStretch()
        box2_header.addWidget(self.settings_btn)
        box2_header.addWidget(self.box2_close_btn)
        box2_layout.addLayout(box2_header)

        # Preset Selection Buttons
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
        self.result_view.setHtml(
            "<p style='color: #38bdf8;'>Pre-warming System Chrome for Gemini Web...</p>"
        )
        box2_layout.addWidget(self.result_view)

        # ==========================================
        # BOX 3: SETTINGS WINDOW WIDGET
        # ==========================================
        self.box3_card = QFrame(self.container)
        box3_layout = QVBoxLayout(self.box3_card)
        box3_layout.setContentsMargins(16, 12, 16, 14)

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

        # Stealth Opacity Control Slider
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

        info_lbl = QLabel("Shortcuts:  Scan = Ctrl+G  |  Quit = Esc / Q")
        info_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; margin-top: 4px;")
        box3_layout.addWidget(info_lbl)

        # Hide Settings panel by default
        self.box3_card.hide()

        self.reposition_widgets()

    def start_automation_bridge(self):
        """Start the single persistent GeminiBridgeThread worker on app startup."""
        logger.info("Starting single GeminiBridgeThread worker...")
        self.bridge_thread = GeminiBridgeThread()
        self.bridge_thread.status_updated.connect(self.on_status_update)
        self.bridge_thread.init_finished.connect(self.on_init_finished)
        self.bridge_thread.answer_received.connect(self.on_answer_received)
        self.bridge_thread.error_occurred.connect(self.on_scan_error)
        self.bridge_thread.start()

    def update_card_styles(self):
        """Update opacity styling for Box 2 and Box 3 cards."""
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
        """Handle opacity slider change events."""
        self.opacity_val = val / 100.0
        self.op_badge.setText(f"{val}%")
        self.update_card_styles()

    def toggle_settings(self):
        """Toggle settings card visibility."""
        if self.settings_visible:
            self.hide_settings()
        else:
            self.show_settings()

    def show_settings(self):
        """Show settings panel and update click mask."""
        self.settings_visible = True
        self.box3_card.show()
        self.update_window_mask()

    def hide_settings(self):
        """Hide settings panel and update click mask."""
        self.settings_visible = False
        self.box3_card.hide()
        self.update_window_mask()

    def set_preset(self, preset: str):
        """Set active prompt preset mode."""
        self.active_preset = preset

    def update_window_mask(self):
        """
        Input mask for OS pass-through clicks:
        Only overlay handles, frames, and lens borders capture mouse clicks.
        All transparent screen space passes clicks directly to underlying applications.
        """
        mask = QRegion(self.box1_bar.geometry())
        mask = mask.united(QRegion(self.box1_grip.geometry()))
        mask = mask.united(QRegion(self.box2_card.geometry()))

        if self.settings_visible:
            mask = mask.united(QRegion(self.box3_card.geometry()))

        lens_geom = self.box1_lens.geometry()
        outer_ring = QRegion(lens_geom)
        inner_ring = QRegion(lens_geom.adjusted(4, 4, -4, -4))
        border_ring = outer_ring.subtracted(inner_ring)

        mask = mask.united(border_ring)
        self.setMask(mask)

    def reposition_widgets(self):
        """Position sub-widgets based on bounding rectangle geometries."""
        self.box1_bar.setGeometry(
            self.box1_rect.x(),
            self.box1_rect.y(),
            self.box1_rect.width(),
            36
        )
        self.box1_title.setText(f"[{self.box1_rect.width()}x{self.box1_rect.height()-38}px]")

        self.box1_lens.setGeometry(
            self.box1_rect.x(),
            self.box1_rect.y() + 38,
            self.box1_rect.width(),
            self.box1_rect.height() - 38
        )

        self.box1_grip.setGeometry(
            self.box1_rect.x() + self.box1_rect.width() - 4,
            self.box1_rect.y() + self.box1_rect.height() - 4,
            12,
            12
        )

        self.box2_card.setGeometry(self.box2_rect)
        self.box3_card.setGeometry(self.box3_rect)

        self.update_window_mask()

    def on_status_update(self, status_msg: str):
        """Slot to display status updates inside Box 2."""
        self.result_view.setHtml(
            f"<p style='color: #38bdf8;'><b>Status:</b> {status_msg}</p>"
        )

    def on_init_finished(self, success: bool):
        """Slot called when startup pre-warming completes."""
        if success:
            self.result_view.setHtml(
                "<p style='color: #34d399;'><b>Gemini Engine Ready!</b></p>"
                "<p style='color: #94a3b8;'>Slide <b>Box 1</b> over your question and press <b>Ctrl+G</b> or click <b>Scan & Solve</b>.</p>"
            )
        else:
            self.result_view.setHtml(
                "<p style='color: #fbbf24;'><b>Notice:</b> Pre-warming unconfirmed. Press <b>Ctrl+G</b> to scan.</p>"
            )

    def trigger_scan(self):
        """Capture screenshot region under Box 1 lens and enqueue scan task to single bridge thread."""
        self.scan_btn.setText("Scanning...")

        # 1. Map Box 1 lens frame to exact global virtual desktop pixel coordinates
        lens_global_pos = self.box1_lens.mapToGlobal(QPoint(0, 0))
        g_x1 = lens_global_pos.x()
        g_y1 = lens_global_pos.y()
        w = max(50, self.box1_lens.width())
        h = max(50, self.box1_lens.height())
        g_x2 = g_x1 + w
        g_y2 = g_y1 + h

        # 2. Detect active monitor where Box 1 is currently sitting
        center_pt = QPoint(g_x1 + w // 2, g_y1 + h // 2)
        target_screen = QApplication.screenAt(center_pt) or QApplication.primaryScreen()
        logger.info(
            f"[Box 1 Capture] Target Monitor: {target_screen.name()} "
            f"({target_screen.geometry().width()}x{target_screen.geometry().height()} at x={target_screen.geometry().x()}, y={target_screen.geometry().y()}) | "
            f"Global Box 1 BBox: ({g_x1}, {g_y1}, {g_x2}, {g_y2})"
        )

        # 3. Prepare target save filepath
        screenshots_dir = "/home/jom/projects/screen-tip-ai/screenshots"
        os.makedirs(screenshots_dir, exist_ok=True)

        from datetime import datetime
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        saved_img_path = os.path.join(screenshots_dir, f"scan_{timestamp_str}.png")

        # 4. Temporarily hide overlay window so OS compositor exposes underlying desktop applications
        self.hide()
        QApplication.processEvents()
        time.sleep(0.08)  # 80ms pause for Wayland/KDE Plasma compositor redraw

        # 5. Capture multi-monitor virtual desktop screen region via PIL ImageGrab (all_screens=True)
        try:
            img = ImageGrab.grab(bbox=(g_x1, g_y1, g_x2, g_y2), all_screens=True)
        except Exception as e:
            logger.warning(f"[Box 1 Capture] ImageGrab.grab(bbox, all_screens=True) warning: {e}. Executing fallback full grab...")
            img = ImageGrab.grab(all_screens=True)
            img = img.crop((g_x1, g_y1, g_x2, g_y2))

        # 6. Restore overlay window immediately
        self.show()
        QApplication.processEvents()

        # 7. Save high-resolution full-color PNG image
        img.save(saved_img_path)
        logger.info(f"[Box 1 Capture] Saved multi-monitor desktop screenshot ({w}x{h}px) via ImageGrab to: {saved_img_path}")

        # 8. Enqueue scan task to single persistent worker thread
        self.on_status_update("Uploading screenshot & querying Gemini AI...")
        if self.bridge_thread and os.path.exists(saved_img_path):
            self.bridge_thread.enqueue_scan(saved_img_path, self.active_preset)

    def on_answer_received(self, html_content: str):
        """Slot to display scraped solution HTML inside Box 2."""
        self.result_view.setHtml(html_content)
        self.scan_btn.setText("Scan & Solve (Ctrl+G)")

    def on_scan_error(self, error_msg: str):
        """Slot to display error message if scan fails."""
        self.result_view.setHtml(
            f"<h4 style='color: #ef4444;'>Scan Failed</h4>"
            f"<p style='color: #f8fafc;'>{error_msg}</p>"
        )
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
            self.close_application()
        elif (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_G:
            self.trigger_scan()

    def close_application(self):
        """Safely shutdown single bridge worker thread and quit application."""
        logger.info("[OverlayUI] Closing application...")
        if self.bridge_thread:
            self.bridge_thread.stop()
            self.bridge_thread.wait(2000)
        QApplication.instance().quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScreenTipMasterOverlay()
    window.show()
    sys.exit(app.exec())
