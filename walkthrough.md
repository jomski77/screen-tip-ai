# Walkthrough - Spanning Virtual Desktop & Global Coordinates Fix

## Implementation Summary

We updated **Screen Tip AI** in [`main.py`](file:///home/jom/projects/screen-tip-ai/main.py) to resolve the multi-monitor coordinate mapping issue:

1. **Overlay Geometry Spans All Connected Screens**:
   - `ScreenTipMasterOverlay.__init__()` now calculates the united virtual desktop rectangle across all monitors (`DP-3` + `HDMI-A-1`):
     ```python
     virtual_rect = QRect()
     for s in QApplication.screens():
         virtual_rect = virtual_rect.united(s.geometry())
     self.setGeometry(virtual_rect)
     ```
   - This extends the translucent overlay canvas across your entire multi-monitor virtual desktop (spanning `y=0` to `y=2880`).

2. **`mapToGlobal()` Coordinate Mapping**:
   - `trigger_scan()` now uses `self.box1_lens.mapToGlobal(QPoint(0, 0))` to map Box 1's lens directly to true global virtual desktop coordinates `(g_x1, g_y1, g_x2, g_y2)`.
   - `ImageGrab.grab(bbox=(g_x1, g_y1, g_x2, g_y2), all_screens=True)` captures the exact image under Box 1 on whichever monitor it is placed.

---

## Technical Verification

- **Virtual Desktop Bounds**: `DP-3` (`2560x1440` at `0,0`) + `HDMI-A-1` (`2560x1440` at `0,1440`).
- **Global Mapping Test**: Box 1 lens at `y=1600` maps to global coordinates `(500, 1600, 900, 1900)`, capturing full-color pixels directly from `HDMI-A-1`.

---

## How to Test

Run the application:
```bash
./venv/bin/python main.py
```

1. Move **Box 1** onto your **Secondary Monitor (`HDMI-A-1`)**.
2. Press **Ctrl+G**.
3. Check the log output:
   `[Box 1 Capture] Target Monitor: HDMI-A-1 (2560x1440 at x=0, y=1440) | Global Box 1 BBox: (500, 1600, 900, 1900)`
4. Open the saved PNG file in `/home/jom/projects/screen-tip-ai/screenshots`. It will contain the **exact image from your secondary monitor**!
