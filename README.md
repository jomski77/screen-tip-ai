# Screen Tip AI 🎯

**Screen Tip AI** is an interactive native desktop HUD overlay designed for screen interview assistance, code analysis, and real-time contextual AI tips. 

It features a dual-box overlay system:
- **Box 1 (Scanner Lens)**: A transparent, movable target box with a glowing white border and crosshair reticle that you slide over any question on your screen.
- **Box 2 (Solution HUD)**: A floating glassmorphism window attached/docked next to Box 1 presenting formatted code solutions, step-by-step logic, and stealth opacity controls.

---

## ✨ Features

- **Translucent Desktop Overlay**: Runs frameless and always-on-top over browsers, IDEs, PDFs, and coding platforms.
- **Side-by-Side Dual Box Architecture**: Box 1 (Scanner Lens) and Box 2 (Solution HUD) positioned cleanly without overlapping.
- **Stealth Opacity Controls**: Adjust opacity from `15%` to `100%` to blend into your desktop background.
- **Sub-Millisecond Screen Capture (`mss`)**: Instantly captures desktop region coordinates under Box 1.
- **Preset Modes**: *Coding Interview*, *System Design*, *Multiple Choice (MCQ)*.
- **Quick Shortcuts**: Press `Esc` or `Q` to quit, click red `✕ Exit` button.

---

## 🛠️ Setup & Running

### 1. Create Virtual Environment & Install Dependencies

```bash
# Create virtualenv
python3 -m venv venv

# Activate virtualenv and install packages
./venv/bin/pip install -r requirements.txt
```

### 2. Run the Application

```bash
./venv/bin/python3 main.py
```

---

## 🎮 Controls

| Action | Control | Description |
| :--- | :--- | :--- |
| **Move Box 1 / Box 2** | Click & drag `⠿ Drag to Move` or header bar | Move either box independently anywhere on screen |
| **Scan & Solve** | Click **"Scan & Solve"** | Capture screen under Box 1 lens and generate AI solution in Box 2 |
| **Stealth Opacity** | Slider in Box 2 header | Adjust transparency from 15% to 100% |
| **Quit App** | Press `Esc` / `Q` or click `✕ Exit` | Close application cleanly |
