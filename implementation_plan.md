# Implementation Plan - Screen Tip AI (Native Desktop HUD Overlay App)

## Goal Description
Build **Screen Tip AI** as a **Native Desktop Application (Electron + React + TypeScript)** that runs directly on your desktop environment (Linux, Windows, macOS). It renders an **always-on-top, transparent desktop overlay** containing:

1. **Scanner Lens (Box 1)**:
   - A floating, resizable, movable transparent box with a crisp white outline (`2px solid #ffffff`), rounded corners, and corner/edge resize handles.
   - Positionable over **any** native application GUI (browsers, IDEs, code editors, PDF readers, video apps).
   - **Click Pass-Through**: Optional toggle to pass mouse clicks directly through the transparent interior of Box 1 to underlying apps.
2. **Answer HUD (Box 2)**:
   - A floating glassmorphism window attached/docked next to Box 1 (or positionable independently).
   - Renders formatted AI solutions, code syntax highlighting, step-by-step reasoning, time complexity, and stealth opacity controls.
3. **Desktop Screen Capture & ROI Cropping**:
   - Uses Electron's native `desktopCapturer` and Node/Canvas APIs to instantly take a high-resolution desktop screenshot when triggered.
   - Mathematically crops the exact pixel region directly beneath Box 1's desktop coordinates (`{ x, y, width, height }`).
4. **System-Wide Global Hotkeys**:
   - `Alt + S` / `Space`: Instant desktop screenshot scan of Box 1 region.
   - `Alt + H`: Toggle overlay visibility (stealth mode).
   - `Alt + Lock`: Lock/unlock box positions.

---

## Technology Stack

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **Desktop Shell** | **Electron** | Creates transparent, frameless, always-on-top desktop windows (`transparent: true`, `alwaysOnTop: true`, `frame: false`). |
| **UI Frontend** | **React + Vite + TypeScript** | High-performance 60fps HUD rendering, drag/resize physics, and Markdown formatting. |
| **Styling** | **Modern Vanilla CSS & Glassmorphism** | White rounded borders (`2px solid #ffffff`), dark glass background blur, stealth transparency sliders. |
| **Native IPC & Capture** | **Electron IPC + DesktopCapturer / Canvas API** | System-wide screen capture, ROI cropping of Box 1 coordinates, global shortcuts. |
| **Vision AI Engine** | **Google Gemini Vision API + Local Mock Generator** | Multi-modal question analysis (code reading, text extraction, MCQ solving) with offline demo mode. |

---

## System Architecture & IPC Flow

```mermaid
flowchart TD
    subgraph Electron Main Process
        A[Native Desktop Shell] -->|Global Hotkey Alt+S| B[desktopCapturer / Screen Snapshot]
        B --> C[Crop Image to Box 1 Screen Coordinates]
        C --> D[Gemini Vision API Request]
    end

    subgraph Renderer Process (React Overlay UI)
        E["Box 1: Movable Magnifying Lens (Transparent + White Outline)"]
        F["Box 2: Floating Answer HUD Card"]
    end

    E -->|IPC Send Bounds {x, y, w, h}| B
    D -->|IPC Send AI Response| F
```

---

## Proposed Changes

### Project Structure & Files

#### [NEW] `package.json`
Electron, Vite, React, TypeScript, Lucide React icons, and Electron Builder setup.

#### [NEW] `vite.config.ts`
Vite configuration tailored for Electron renderer integration.

#### [NEW] `electron/main.ts`
- Electron main process configuration.
- Creates transparent, frameless, `alwaysOnTop` overlay window (`win.setAlwaysOnTop(true, 'screen-saver')`).
- Registers IPC handlers for `capture-region`, `toggle-click-through`, and global shortcuts (`Alt+S`, `Alt+H`).

#### [NEW] `electron/preload.ts`
- Secure IPC bridge exposing native desktop APIs (`electronAPI.scanRegion`, `electronAPI.onGlobalScan`, `electronAPI.setIgnoreMouse`).

#### [NEW] `src/index.css`
- Design system for desktop HUD: transparent lens window, crisp white border lines (`#ffffff`), glowing handles, dark glassmorphism card.

#### [NEW] `src/types/index.ts`
- Interfaces for `BoxBounds`, `ScanPayload`, `AIResponse`, and system preferences.

#### [NEW] `src/hooks/useDesktopCapture.ts`
- React hook communicating with Electron main process to send Box 1's screen bounds and receive AI solutions.

#### [NEW] `src/hooks/useDraggableBox.ts`
- Handles smooth drag and corner/edge resizing for Box 1 and Box 2 across screen resolution space.

#### [NEW] `src/services/aiService.ts`
- Gemini Vision API integration for multi-modal desktop screenshot analysis.
- Built-in Mock AI generator for instant offline testing without an API key.

#### [NEW] `src/components/ScannerBox1.tsx`
- **Box 1 Implementation**:
  - Transparent resizable rectangular overlay with rounded corners and glowing white outline (`2px solid #ffffff`).
  - Attached floating header with "Scan & Solve (Alt+S)" button and dimension badge.
  - Corner and edge resize handles with drag header.

#### [NEW] `src/components/AnswerBox2.tsx`
- **Box 2 Implementation**:
  - Floating glassmorphism HUD panel (`backdrop-filter: blur(16px)`).
  - Rich Markdown renderer for code solutions, time/space complexity analysis, and step-by-step guidance.
  - Controls: Opacity slider, Click-through toggle, Copy code, Audio text-to-speech reader.

#### [NEW] `src/components/HeaderBar.tsx`
- Compact titlebar/control bar for app settings, API key configuration, and hotkey info.

#### [NEW] `src/App.tsx`
- Main React application binding Electron IPC, overlay state, and HUD components.

---

## Verification Plan

### Automated Verification
- Verify TypeScript compilation and Vite build via `npm run build`.
- Verify Electron main & renderer process bundling without path or IPC errors.

### Manual Verification
1. **Launch Desktop App Overlay**:
   - Run `npm run dev` / `npm start`.
   - Verify the transparent Electron window appears over all desktop windows with `alwaysOnTop` priority.
2. **Position & Resize Box 1**:
   - Drag Box 1 over any desktop application (e.g. VS Code, Chrome browser, PDF reader).
   - Verify the area inside Box 1 is completely transparent and shows the underlying desktop app clearly inside the white outline.
3. **Trigger Desktop Scan (`Alt+S` or "Scan & Solve" Button)**:
   - Click "Scan & Solve" or press `Alt+S`.
   - Verify Electron captures the screen region under Box 1 and passes it to the AI.
4. **Inspect Solution in Box 2**:
   - Confirm Box 2 displays the extracted question and formatted code solution.
   - Adjust opacity slider to verify stealth background blending.
