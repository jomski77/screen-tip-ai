# Workspace Memory & Guidelines - Screen Tip AI

## 🐙 Git & GitHub Configuration
- **GitHub Username**: `jomski77`
- **Remote Origin URL**: `git@github.com:jomski77/screen-tip-ai.git`
- **Default Branch**: `main`
- **Git User Config**:
  - `user.name`: `joms`
  - `user.email`: `joms.madhousetech@gmail.com`
- **SSH Key**: `~/.ssh/id_ed25519.pub` (`jom@Desk`)
- **Commit Rule**: ⚠️ ONLY run `git commit` or `git push` when EXPLICITLY instructed by the user!

## 🛠️ Environment & Stack Specs
- **Language**: Python 3.14 (`./venv/bin/python3`)
- **UI Framework**: PyQt6 (`QWidget`, `WA_TranslucentBackground`, `setMask(QRegion)`)
- **Screen Capture**: `mss` + `Pillow`
- **Desktop Environment**: KDE Plasma on Wayland (`WAYLAND_DISPLAY: wayland-0`)

## 🚀 Key Commands
- **Run App**: `./venv/bin/python3 main.py`
- **Git Commit**: `git add . && git commit -m "..."`
- **Git Push**: `git push -u origin main`
