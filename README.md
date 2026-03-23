# Xbox Cover Art Builder

**Team Resurgent  |  Darkone83**

A standalone desktop application for creating authentic Xbox original cover art by compositing your artwork into official-style Xbox case frames. Supports multiple frame styles, text overlays with full font control, drag-and-drop image loading, and high-quality JPEG/PNG export.

---

## Features

- **3 frame styles** — Only on XBOX, Team Resurgent, Team Resurgent 2
- **Drag & drop** image loading directly onto the preview canvas
- **Auto-fit** — artwork scales automatically to fill the art slot on load
- **Zoom & pan** — slider, scroll wheel, +/− buttons, and direct drag on the canvas
- **Text overlays** — multiple text boxes with full font, size, colour, style control
- **On-canvas text editing** — drag to move, drag handles to resize and rotate
- **Color picker** — preset swatches, RGB sliders, hex input, and full system color wheel
- **Save** as JPEG (quality 97) or PNG
- Runs on **Windows, macOS, Linux**

---

## Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.10 or newer |
| Pillow | 9.0 or newer |
| PySide6 | 6.4 or newer |

---

## Installation

### 1. Install Python

Download and install Python 3.10+ from [https://www.python.org/downloads/](https://www.python.org/downloads/)

> **Windows users:** During installation, tick **"Add Python to PATH"**

Verify your installation:
```bash
python --version
```

---

### 2. Install required packages

Open a terminal (Command Prompt, PowerShell, or Terminal) and run:

```bash
pip install Pillow PySide6
```

Or if you have both Python 2 and Python 3 installed:

```bash
pip3 install Pillow PySide6
```

---

### 3. Set up the application files

Place all of the following files in the **same folder**:

```
xbox_cover_gui.pyw    ← main application
bg.png               ← Only on XBOX frame
bg2.png              ← Team Resurgent frame
bg3.png              ← Team Resurgent 2 frame
```

> All frame files must be present. The app will show an error and refuse to switch to a frame if its PNG file is missing.

---

### 4. Launch the application

**Double-click** `xbox_cover_gui.pyw` — on most systems Python files open directly.

Or from the terminal:

```bash
python xbox_cover_gui.pyw
```

---

## Usage Guide

### Loading artwork

- **Drag & drop** any image file directly onto the preview canvas, or
- Click **Browse...** to open a file picker

Supported formats: JPG, JPEG, PNG, BMP, WEBP, TIFF, GIF

The artwork will auto-fit to the frame's art slot on load.

---

### Selecting a frame

Use the **FRAME** dropdown at the top of the controls panel to switch between:

| Frame | Description |
|-------|-------------|
| Only on XBOX | Classic Xbox case with "Only on XBOX" header badge |
| Team Resurgent | Team Resurgent branded frame, artwork fills inner slot |
| Team Resurgent 2 | Team Resurgent frame with "Only on XBOX" badge, artwork sits behind full frame |

---

### Zoom controls

| Control | Action |
|---------|--------|
| Zoom slider | Drag to set zoom level (10%–400%) |
| `+` / `−` buttons | Zoom in/out in 5% steps |
| Scroll wheel | Zoom in/out in 3% steps |
| **Reset Fit** | Return to auto-fit zoom and re-centre |

---

### Panning / positioning

In **🖼 Art Pan** mode (default):

| Control | Action |
|---------|--------|
| Drag preview canvas | Pan the artwork freely |
| ▲ ▼ ◀ ▶ nudge buttons | Move artwork 10px at a time |
| ● centre button | Re-centre artwork in the slot |

---

### Text overlays

#### Adding a text box

1. Click **＋ Add Text Box**
2. Enter your text in the dialog
3. Choose font family, size (in traditional pt), bold/italic style, and colour
4. Click **OK** — the text box is placed at the centre of the frame

#### Editing text

Click the **✏** button next to any text box in the list to reopen the editor dialog.

#### Moving, resizing, rotating

1. Click **✏ Text Move** to enter text mode — coloured handles appear on each text box
2. **Drag the text body** (green dot) to move it
3. **Drag the green square** (bottom-right corner) to resize
4. **Drag the magenta circle** (top-right corner) to rotate
5. Click **✏ Text Move** again to exit text mode and see a clean preview

#### Deleting a text box

Click the **✕** button next to any text box in the list.

---

### Color picker

The color picker dialog provides:

- **Preset swatches** — 20 common cover art colours for quick selection
- **RGB sliders** — fine-tune red, green, blue channels independently
- **Hex input** — type any hex colour code directly (e.g. `#FF00CC`)
- **Open Full Color Wheel** — opens the system color wheel for full HSV selection

---

### Saving

Click **Save Cover** to export the finished cover art.

- Choose **JPEG** for smaller file size (saved at quality 97, nearly lossless)
- Choose **PNG** for lossless with transparency support
- The filename defaults to `<artwork_name>_xbox_cover.jpg`

The saved image is the full resolution composite — the preview scale does not affect export quality.

---

### Clearing

Click **Clear** to remove the loaded artwork, reset zoom, and clear all text boxes, returning to a blank frame preview.

---

## File Structure

```
xbox_cover_gui.pyw    Main application script
bg.png               Only on XBOX frame  (600 × 900 px)
bg2.png              Team Resurgent frame (1342 × 2000 px)
bg3.png              Team Resurgent 2 frame (1342 × 2000 px)
README.md            This file
```

---

## Troubleshooting

**"ERROR: pip install Pillow"** on launch
→ Run `pip install Pillow PySide6` in your terminal and try again.

**Frame not found error**
→ Make sure `bg.png`, `bg2.png`, and `bg3.png` are in the same folder as `xbox_cover_gui.pyw`.

**Text font not rendering correctly**
→ The app searches your system fonts folder for the selected font family. If a font is not found it falls back to a default. Install the font on your system and restart the app.

**App won't open on double-click (Windows)**
→ Right-click `xbox_cover_gui.pyw` → Open with → Python. Or open Command Prompt, navigate to the folder, and run `python xbox_cover_gui.pyw`.

**App won't open on macOS**
→ Open Terminal, navigate to the folder and run `python3 xbox_cover_gui.pyw`.

---

## Credits

Developed by **Team Resurgent** and **Darkone83**

Built with [Python](https://www.pywthon.org/), [Pillow](https://python-pillow.org/), and [PySide6](https://doc.qt.io/qtforpython/)
