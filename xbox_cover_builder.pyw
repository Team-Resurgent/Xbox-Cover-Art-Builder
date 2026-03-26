#!/usr/bin/env python3
"""
Xbox Cover Art Builder — Team Resurgent / Darkone83
Dependencies are installed automatically on first run.
"""

import os, sys, subprocess
from pathlib import Path

# ── Dependency bootstrapper ───────────────────────────────────────────────────
# Runs before anything else. Installs missing packages via pip, then re-launches
# the script so all imports resolve cleanly in a fresh process.

_REQUIRED = [("PIL", "Pillow"), ("PySide6", "PySide6")]

def _alert(title, msg):
    """Show a GUI alert using tkinter (stdlib) — works even with no Qt/Pillow."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror(title, msg)
        root.destroy()
    except Exception:
        print(f"{title}: {msg}", file=sys.stderr)

def _bootstrap():
    missing = []
    for import_name, pkg_name in _REQUIRED:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)

    if not missing:
        return  # all good

    # Try to install
    pip = [sys.executable, "-m", "pip", "install", "--upgrade"] + missing
    try:
        result = subprocess.run(pip, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "pip failed")
    except Exception as ex:
        _alert("Dependency Install Failed",
               f"Could not install: {', '.join(missing)}\n\n{ex}\n\n"
               f"Please run manually:\n  pip install {' '.join(missing)}")
        sys.exit(1)

    # Re-launch with a clean process so the new packages are importable
    os.execv(sys.executable, [sys.executable] + sys.argv)

_bootstrap()

# ── Imports (guaranteed present after bootstrap) ──────────────────────────────
import math, uuid, platform, json, shutil

from PIL import Image, ImageDraw, ImageFont

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QSlider, QComboBox, QFileDialog, QMessageBox,
    QHBoxLayout, QVBoxLayout, QGridLayout, QFrame, QScrollArea,
    QSpinBox, QDoubleSpinBox, QFontComboBox, QMenuBar, QMenu,
    QDialog, QDialogButtonBox, QTextEdit, QColorDialog,
    QLineEdit, QCheckBox, QRubberBand, QSizePolicy
)
from PySide6.QtCore import Qt, QPointF, QRect, QSize, Signal
from PySide6.QtGui  import (
    QPixmap, QImage, QColor, QFont, QCursor, QAction,
    QDragEnterEvent, QDropEvent, QLinearGradient, QPainter, QPen
)


# ── Frame profiles ────────────────────────────────────────────────────────────
FRAMES = {
    "Only on XBOX": {
        "file":       "bg.png",
        "art_box":    (0, 0, 600, 900),
        "inner_slot": (0, 120, 600, 780),
        "frame_wh":   (600, 900),
        "sep_y":      119,
        "behind":     True,
    },
    "Team Resurgent": {
        "file":       "bg2.png",
        "art_box":    (0, 0, 1350, 2100),
        "inner_slot": (0, 0, 1350, 2210),
        "frame_wh":   (1342, 2000),
        "sep_y":      None,
        "behind":     True,
    },
    "Team Resurgent 2": {
        "file":       "bg3.png",
        "art_box":    (0, 0, 1350, 2100),
        "inner_slot": (0, 0, 1350, 2100),
        "frame_wh":   (1342, 2000),
        "sep_y":      None,
        "behind":     True,
    },
}

DISP_H    = 660
UI_SCALE  = 1.0   # set to 1.5 on macOS Retina in main()
SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".gif"}

FONT_MONO  = "Courier New"
C_GREEN    = "#5dbb00"
C_MAGENTA  = "#ff00cc"   # Team Resurgent
C_PURPLE   = "#aa00ff"   # Darkone83
C_BG       = "#0d0d0d"
C_BTN      = "#1c1c1c"
C_BTN_HOV  = "#2a2a2a"
C_DIM      = "#555"
C_HDR      = "#080808"

# Traditional pt → pixel at 96 DPI
PT_SIZES   = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 28, 32,
              36, 40, 48, 56, 64, 72, 80, 96, 112, 128, 144]

def pt_to_px(pt, dpi=96):
    return int(round(pt * dpi / 72))

def px_to_pt(px, dpi=96):
    return int(round(px * 72 / dpi))


# ── Text box data ─────────────────────────────────────────────────────────────
class TextBox:
    def __init__(self, text="GAME TITLE", x=0, y=0,
                 font_family="Arial", font_pt=36,
                 color=(255, 255, 255), bold=False, italic=False,
                 rotation=0.0, scale=1.0):
        self.id          = str(uuid.uuid4())[:8]
        self.text        = text
        self.x           = x          # full-res centre-x
        self.y           = y          # full-res centre-y
        self.font_family = font_family
        self.font_pt     = font_pt    # traditional pt size
        self.color       = color
        self.bold        = bold
        self.italic      = italic
        self.rotation    = rotation   # degrees
        self.scale       = scale      # 0.1 – 5.0

    @property
    def font_px(self):
        return max(4, int(pt_to_px(self.font_pt) * self.scale))

    def color_hex(self):
        return "#{:02x}{:02x}{:02x}".format(*self.color)

    def label(self):
        t = self.text[:16] + ("…" if len(self.text) > 16 else "")
        return f'"{t}"  {self.font_pt}pt'


# ── Font loader ───────────────────────────────────────────────────────────────
def find_font(family, bold=False, italic=False, size_px=48):
    """Try to find a system TTF for the given family."""
    system = platform.system()
    variants = []
    if bold and italic: variants = [" Bold Italic", "BoldItalic", "bi"]
    elif bold:          variants = [" Bold", "Bold", "b"]
    elif italic:        variants = [" Italic", "Italic", "i"]
    variants += ["", "Regular", "r"]

    if system == "Windows":
        dirs = ["C:/Windows/Fonts/"]
    elif system == "Darwin":
        dirs = ["/System/Library/Fonts/", "/Library/Fonts/",
                os.path.expanduser("~/Library/Fonts/")]
    else:
        dirs = ["/usr/share/fonts/", "/usr/local/share/fonts/",
                os.path.expanduser("~/.fonts/")]

    fam_clean = family.replace(" ", "")
    for d in dirs:
        if not Path(d).exists(): continue
        for v in variants:
            for ext in [".ttf", ".otf", ".TTF", ".OTF"]:
                for name in [family + v, fam_clean + v,
                             family.lower() + v.lower(),
                             fam_clean.lower() + v.lower()]:
                    p = Path(d) / (name + ext)
                    if p.exists():
                        try: return ImageFont.truetype(str(p), size_px)
                        except: pass
        # Also scan recursively
        for p in Path(d).rglob("*.ttf"):
            stem = p.stem.lower()
            if fam_clean.lower() in stem:
                try: return ImageFont.truetype(str(p), size_px)
                except: pass

    try: return ImageFont.truetype(family + ".ttf", size_px)
    except: pass
    return ImageFont.load_default()


# ── Image helpers ─────────────────────────────────────────────────────────────
def auto_fit(art_w, art_h, slot_w, slot_h):
    # Image larger than slot in either dimension → contain (shrink to show whole image)
    # Image smaller than slot in both dimensions → cover (zoom up to fill slot)
    if art_w > slot_w or art_h > slot_h:
        scale = min(slot_w / art_w, slot_h / art_h)   # contain
    else:
        scale = max(slot_w / art_w, slot_h / art_h)   # cover
    return round(scale, 4)


def render_slot(art, zoom, off_x, off_y, slot_w, slot_h):
    nw = max(1, math.ceil(art.width  * zoom))
    nh = max(1, math.ceil(art.height * zoom))
    scaled = art.resize((nw, nh), Image.LANCZOS)
    px = int(slot_w / 2 - off_x); py = int(slot_h / 2 - off_y)
    out = Image.new("RGBA", (slot_w, slot_h), (0, 0, 0, 255))
    sx = max(0,-px); sy = max(0,-py); dx = max(0,px); dy = max(0,py)
    cw = min(nw-sx, slot_w-dx); ch = min(nh-sy, slot_h-dy)
    if cw > 0 and ch > 0:
        out.paste(scaled.crop((sx,sy,sx+cw,sy+ch)), (dx,dy))
    return out


def composite(frame_img, art_img, zoom, off_x, off_y, art_box, behind=False):
    ax, ay, aw, ah = art_box
    fw, fh = frame_img.size
    slot = render_slot(art_img.convert("RGBA"), zoom, off_x, off_y, aw, ah)
    if behind:
        # Art behind frame: paste art first, alpha-composite frame on top
        out = Image.new("RGBA", (fw, fh), (0,0,0,255))
        out.paste(slot, (ax, ay))
        out = Image.alpha_composite(out, frame_img.convert("RGBA"))
    else:
        # Art on top of frame: start with frame, paste art over it
        out = frame_img.convert("RGBA").copy()
        out.paste(slot, (ax, ay), slot)
    return out


def render_text_overlays(img: Image.Image, text_boxes: list) -> Image.Image:
    if not text_boxes:
        return img
    out = img.copy().convert("RGBA")
    for tb in text_boxes:
        font = find_font(tb.font_family, tb.bold, tb.italic, tb.font_px)

        # Measure exact glyph bounds including ascenders/descenders
        tmp   = Image.new("RGBA", (1, 1))
        tdraw = ImageDraw.Draw(tmp)
        bbox  = tdraw.textbbox((0, 0), tb.text, font=font)
        # bbox = (left, top, right, bottom) — top/left can be non-zero
        PAD   = 8   # padding on all sides to ensure nothing clips
        tw    = bbox[2] - bbox[0] + PAD * 2
        th    = bbox[3] - bbox[1] + PAD * 2

        # Draw offset so glyph top-left lands exactly at (PAD, PAD)
        draw_x = PAD - bbox[0]
        draw_y = PAD - bbox[1]

        txt_layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        tl_draw   = ImageDraw.Draw(txt_layer)
        # Drop shadow
        tl_draw.text((draw_x + 3, draw_y + 3), tb.text, font=font,
                     fill=(0, 0, 0, 160))
        # Main text
        tl_draw.text((draw_x, draw_y), tb.text, font=font,
                     fill=(*tb.color, 255))

        # Rotate around centre if needed
        if tb.rotation != 0:
            txt_layer = txt_layer.rotate(-tb.rotation, expand=True,
                                          resample=Image.BICUBIC)

        # Paste centred at tb.x, tb.y
        paste_x = int(tb.x - txt_layer.width  / 2)
        paste_y = int(tb.y - txt_layer.height / 2)
        out.paste(txt_layer, (paste_x, paste_y), txt_layer)

    return out


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


def load_frame_img(profile: dict):
    here = Path(__file__).parent
    for p in (here / profile["file"], Path(profile["file"])):
        if p.exists():
            img = Image.open(str(p)).convert("RGBA")
            if profile.get("sep_y") is not None:
                fw = profile["frame_wh"][0]
                sy = profile["sep_y"]
                ImageDraw.Draw(img).line([(0,sy),(fw-1,sy)], fill=(0,0,0,255))
            return img
    return None


# ── Color wheel picker ────────────────────────────────────────────────────────
class ColorPickerDialog(QDialog):
    """Full-featured color picker using Qt's built-in + hex input."""
    def __init__(self, initial: QColor, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick Color")
        self.setStyleSheet(f"background: {C_BG}; color: #ccc;")
        self.setMinimumWidth(340)
        self._color = initial

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Preset swatches — common cover art colors
        presets = [
            "#ffffff", "#000000", "#ff0000", "#00ff00", "#0000ff",
            "#ffff00", "#ff00ff", "#00ffff", "#ff8800", "#ff0088",
            "#88ff00", "#aa00ff", "#5dbb00", "#ff4444", "#4488ff",
            "#ffcc00", "#cccccc", "#888888", "#444444", "#ff6600",
        ]
        grid = QWidget(); grid.setStyleSheet("background: transparent;")
        g_layout = QGridLayout(grid)
        g_layout.setSpacing(4); g_layout.setContentsMargins(0,0,0,0)
        for i, hex_c in enumerate(presets):
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(f"background: {hex_c}; border: 1px solid #444; border-radius: 2px;")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda checked, c=hex_c: self._set_hex(c))
            g_layout.addWidget(btn, i // 10, i % 10)
        layout.addWidget(QLabel("PRESETS:", styleSheet=f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;"))
        layout.addWidget(grid)

        # Full color wheel button
        btn_full = QPushButton("Open Full Color Wheel...")
        btn_full.setStyleSheet(f"background:{C_BTN};color:#ccc;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;border:none;padding:{sc(6)}px;")
        btn_full.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_full.clicked.connect(self._open_wheel)
        layout.addWidget(btn_full)

        # Hex input
        hex_row = QWidget(); hex_row.setStyleSheet("background:transparent;")
        hex_h = QHBoxLayout(hex_row); hex_h.setContentsMargins(0,0,0,0); hex_h.setSpacing(sc(6))
        from PySide6.QtWidgets import QLineEdit
        self.hex_input = QLineEdit(initial.name().upper())
        self.hex_input.setMaxLength(7)
        self.hex_input.setStyleSheet(f"background:#1a1a1a;color:#fff;border:1px solid #333;padding:{sc(4)}px;font-family:'{FONT_MONO}';font-size:{sc(10)}pt;")
        self.hex_input.textChanged.connect(self._on_hex_changed)
        hex_h.addWidget(QLabel("HEX:", styleSheet=f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;min-width:{sc(40)}px;"))
        hex_h.addWidget(self.hex_input)

        # Preview swatch
        self.preview_swatch = QLabel()
        self.preview_swatch.setFixedSize(50, 30)
        self._update_swatch()
        hex_h.addWidget(self.preview_swatch)
        layout.addWidget(hex_row)

        # RGB sliders
        layout.addWidget(QLabel("RGB:", styleSheet=f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;"))
        self.r_slider = self._make_rgb_slider("R", initial.red(),   "#ff4444")
        self.g_slider = self._make_rgb_slider("G", initial.green(), "#44ff44")
        self.b_slider = self._make_rgb_slider("B", initial.blue(),  "#4488ff")
        layout.addWidget(self.r_slider[0])
        layout.addWidget(self.g_slider[0])
        layout.addWidget(self.b_slider[0])

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.setStyleSheet(f"QPushButton{{background:{C_BTN};color:#ccc;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;border:none;padding:{sc(6)}px {sc(20)}px;}} QPushButton:hover{{background:{C_BTN_HOV};color:#fff;}}")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _make_rgb_slider(self, label, value, color):
        row = QWidget(); row.setStyleSheet("background:transparent;")
        h = QHBoxLayout(row); h.setContentsMargins(0,0,0,0); h.setSpacing(sc(6))
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{color};font-family:'{FONT_MONO}';font-size:{sc(9)}pt;font-weight:bold;min-width:{sc(16)}px;")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 255); slider.setValue(value)
        sh = sc(14)
        slider.setStyleSheet(f"QSlider::groove:horizontal{{background:#1a1a1a;height:{sc(4)}px;border-radius:2px;}} QSlider::handle:horizontal{{background:{color};width:{sh}px;height:{sh}px;margin:{-sh//2+1}px 0;border-radius:{sh//2}px;}} QSlider::sub-page:horizontal{{background:{color};border-radius:2px;}}")
        val_lbl = QLabel(str(value))
        val_lbl.setStyleSheet(f"color:#aaa;font-family:'{FONT_MONO}';font-size:{sc(8)}pt;min-width:{sc(28)}px;")
        slider.valueChanged.connect(lambda v: (val_lbl.setText(str(v)), self._on_rgb_changed()))
        h.addWidget(lbl); h.addWidget(slider); h.addWidget(val_lbl)
        return row, slider

    def _on_rgb_changed(self):
        r = self.r_slider[1].value()
        g = self.g_slider[1].value()
        b = self.b_slider[1].value()
        self._color = QColor(r, g, b)
        self.hex_input.blockSignals(True)
        self.hex_input.setText(self._color.name().upper())
        self.hex_input.blockSignals(False)
        self._update_swatch()

    def _on_hex_changed(self, text):
        if len(text) == 7 and text.startswith("#"):
            c = QColor(text)
            if c.isValid():
                self._color = c
                self.r_slider[1].blockSignals(True); self.r_slider[1].setValue(c.red());   self.r_slider[1].blockSignals(False)
                self.g_slider[1].blockSignals(True); self.g_slider[1].setValue(c.green()); self.g_slider[1].blockSignals(False)
                self.b_slider[1].blockSignals(True); self.b_slider[1].setValue(c.blue());  self.b_slider[1].blockSignals(False)
                self._update_swatch()

    def _set_hex(self, hex_c):
        self.hex_input.setText(hex_c.upper())

    def _open_wheel(self):
        c = QColorDialog.getColor(self._color, self, "Color Wheel")
        if c.isValid():
            self._set_hex(c.name())

    def _update_swatch(self):
        self.preview_swatch.setStyleSheet(
            f"background:{self._color.name()};border:1px solid #555;border-radius:2px;")

    def selected_color(self) -> QColor:
        return self._color


# ── Text Editor Dialog ────────────────────────────────────────────────────────
class TextBoxDialog(QDialog):
    def __init__(self, tb: TextBox, parent=None):
        super().__init__(parent)
        self.tb = tb
        self.setWindowTitle("Text Overlay")
        self.setStyleSheet(f"background:{C_BG};color:#ccc;")
        self.setMinimumWidth(sc(420))

        L = QVBoxLayout(self); L.setSpacing(sc(8))

        def row(lbl_txt, widget, lbl_w=100):
            r = QWidget(); r.setStyleSheet("background:transparent;")
            h = QHBoxLayout(r); h.setContentsMargins(0,0,0,0); h.setSpacing(sc(8))
            l = QLabel(lbl_txt)
            l.setStyleSheet(f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;min-width:{sc(lbl_w)}px;")
            h.addWidget(l); h.addWidget(widget,1)
            return r

        # Text
        L.addWidget(QLabel("TEXT:", styleSheet=f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;"))
        self.txt_edit = QTextEdit()
        self.txt_edit.setPlainText(tb.text)
        self.txt_edit.setStyleSheet(f"background:#1a1a1a;color:#fff;font-size:{sc(11)}pt;border:1px solid #333;")
        self.txt_edit.setMaximumHeight(sc(70))
        L.addWidget(self.txt_edit)

        # Font
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(tb.font_family))
        self.font_combo.setStyleSheet(f"background:#1a1a1a;color:#fff;border:1px solid #333;padding:{sc(3)}px;")
        L.addWidget(row("FONT:", self.font_combo))

        # Size (pt) — dropdown of traditional sizes
        self.size_combo = QComboBox()
        self.size_combo.addItems([str(s) for s in PT_SIZES])
        closest = min(PT_SIZES, key=lambda s: abs(s - tb.font_pt))
        self.size_combo.setCurrentText(str(closest))
        self.size_combo.setStyleSheet(f"background:#1a1a1a;color:#fff;border:1px solid #333;padding:{sc(3)}px;")
        L.addWidget(row("SIZE (pt):", self.size_combo))

        # Scale & Rotate info note
        hint = QLabel("Scale & rotate: drag handles on canvas in Text Move mode\n"
                       "  Green square = resize   |   Magenta circle = rotate")
        hint.setStyleSheet(f"color:#555;font-family:'{FONT_MONO}';font-size:{sc(8)}pt;background:transparent;")
        hint.setWordWrap(True)
        L.addWidget(hint)

        # Bold / Italic
        style_w = QWidget(); style_w.setStyleSheet("background:transparent;")
        style_h = QHBoxLayout(style_w); style_h.setContentsMargins(0,0,0,0); style_h.setSpacing(sc(6))
        self.bold_btn   = QPushButton("Bold")
        self.italic_btn = QPushButton("Italic")
        for btn, active in [(self.bold_btn, tb.bold), (self.italic_btn, tb.italic)]:
            btn.setCheckable(True); btn.setChecked(active)
            btn.setStyleSheet(f"""
                QPushButton{{background:#1c1c1c;color:#ccc;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;font-weight:bold;border:none;padding:{sc(6)}px {sc(18)}px;}}
                QPushButton:checked{{background:{C_GREEN};color:#000;}}
                QPushButton:hover{{background:#2a2a2a;}}
            """)
            style_h.addWidget(btn)
        style_h.addStretch()
        L.addWidget(row("STYLE:", style_w))

        # Color
        self._color = QColor(*tb.color)
        self.color_btn = QPushButton()
        self.color_btn.setFixedHeight(sc(34))
        self._refresh_color_btn()
        self.color_btn.clicked.connect(self._pick_color)
        self.color_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        L.addWidget(row("COLOR:", self.color_btn))

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.setStyleSheet(f"QPushButton{{background:{C_BTN};color:#ccc;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;border:none;padding:{sc(6)}px {sc(20)}px;}} QPushButton:hover{{background:{C_BTN_HOV};color:#fff;}}")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        L.addWidget(btns)

    def _refresh_color_btn(self):
        light = self._color.lightness() > 128
        self.color_btn.setStyleSheet(
            f"background:{self._color.name()};color:{'#000' if light else '#fff'};"
            f"font-family:'{FONT_MONO}';font-size:{sc(10)}pt;font-weight:bold;"
            f"border:1px solid #555;padding:{sc(4)}px;")
        self.color_btn.setText(self._color.name().upper())

    def _pick_color(self):
        dlg = ColorPickerDialog(self._color, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._color = dlg.selected_color()
            self._refresh_color_btn()

    def get_result(self) -> TextBox:
        self.tb.text        = self.txt_edit.toPlainText()
        self.tb.font_family = self.font_combo.currentFont().family()
        self.tb.font_pt     = int(self.size_combo.currentText())
        # scale and rotation are set via canvas handles, preserve existing values
        self.tb.bold        = self.bold_btn.isChecked()
        self.tb.italic      = self.italic_btn.isChecked()
        self.tb.color       = (self._color.red(), self._color.green(), self._color.blue())
        return self.tb


# ── Widget helpers ────────────────────────────────────────────────────────────
def sc(n):
    """Scale a pixel/pt value by UI_SCALE."""
    return int(round(n * UI_SCALE))

def make_label(text, color=C_DIM, bold=False, size=9):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{color};font-family:'{FONT_MONO}';font-size:{sc(size)}pt;"
                      f"font-weight:{'bold' if bold else 'normal'};background:transparent;")
    return lbl

def make_button(text, color=C_BTN, fg="#ccc", hover=C_BTN_HOV):
    pad_v = sc(7); pad_h = sc(10); fsize = sc(9)
    btn = QPushButton(text)
    btn.setStyleSheet(f"""
        QPushButton{{background:{color};color:{fg};font-family:'{FONT_MONO}';font-size:{fsize}pt;
            font-weight:bold;border:none;padding:{pad_v}px {pad_h}px;}}
        QPushButton:hover{{background:{hover};color:#fff;}}
        QPushButton:pressed{{background:#111;}}
    """)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    return btn

def section_label(text, color=C_GREEN):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{color};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;background:transparent;")
    return lbl


# ── Preview widget ────────────────────────────────────────────────────────────
HANDLE_R = 8   # handle radius in display pixels

class PreviewLabel(QLabel):
    file_dropped   = Signal(str)
    pan_delta      = Signal(float, float)
    text_moved     = Signal(str, float, float)      # id, cx, cy
    text_scaled    = Signal(str, float)             # id, new_scale
    text_rotated   = Signal(str, float)             # id, new_rotation_deg

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setStyleSheet("background:#000;border:2px solid #222;")
        self._drag_pos    = None
        self._disp_scale  = 1.0
        self._text_boxes  = []
        self._drag_tb_id  = None
        self._drag_tb_off = (0, 0)
        self._drag_action = None   # "move" | "scale" | "rotate"
        self._drag_start_scale = 1.0
        self._drag_start_rot   = 0.0
        self._drag_start_dist  = 1.0
        self._drag_start_angle = 0.0
        self._mode = "pan"
        self.setMouseTracking(True)

    def set_disp_scale(self, s): self._disp_scale = s
    def set_text_boxes(self, tbs): self._text_boxes = tbs
    def set_mode(self, m):
        self._mode = m
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor if m == "text"
                               else Qt.CursorShape.SizeAllCursor))

    def _tb_bounds(self, tb):
        """Return (cx, cy, hw, hh) in display pixels for a text box."""
        ew = max(len(tb.text) * tb.font_px * 0.62, 80)
        eh = tb.font_px * 1.7
        cx = tb.x * self._disp_scale
        cy = tb.y * self._disp_scale
        hw = ew * self._disp_scale / 2
        hh = eh * self._disp_scale / 2
        return cx, cy, hw, hh

    def _scale_handle(self, tb):
        """Bottom-right handle position in display pixels."""
        cx, cy, hw, hh = self._tb_bounds(tb)
        return cx + hw, cy + hh

    def _rotate_handle(self, tb):
        """Top-right handle position in display pixels."""
        cx, cy, hw, hh = self._tb_bounds(tb)
        return cx + hw, cy - hh

    def _hit_handle(self, pos, hx, hy):
        return math.hypot(pos.x() - hx, pos.y() - hy) <= HANDLE_R + 4

    def _tb_at(self, dx, dy):
        fx = dx / self._disp_scale; fy = dy / self._disp_scale
        for tb in reversed(self._text_boxes):
            ew = max(len(tb.text) * tb.font_px * 0.62, 80)
            eh = tb.font_px * 1.7
            if (tb.x - ew/2 <= fx <= tb.x + ew/2 and
                    tb.y - eh/2 <= fy <= tb.y + eh/2):
                return tb
        return None

    # ── Drag & drop ───────────────────────────────────────────────────────────
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet("background:#000;border:2px solid #5dbb00;")

    def dragLeaveEvent(self, e):
        self.setStyleSheet("background:#000;border:2px solid #222;")

    def dropEvent(self, e):
        self.setStyleSheet("background:#000;border:2px solid #222;")
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).suffix.lower() in SUPPORTED:
                self.file_dropped.emit(path)

    # ── Mouse ──────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton: return
        pos = e.position()
        if self._mode == "text":
            # Check handles first
            for tb in reversed(self._text_boxes):
                sx, sy = self._scale_handle(tb)
                rx, ry = self._rotate_handle(tb)
                if self._hit_handle(pos, sx, sy):
                    self._drag_tb_id = tb.id
                    self._drag_action = "scale"
                    self._drag_start_scale = tb.scale
                    cx, cy, _, _ = self._tb_bounds(tb)
                    self._drag_start_dist = max(1.0, math.hypot(pos.x()-cx, pos.y()-cy))
                    self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
                    return
                if self._hit_handle(pos, rx, ry):
                    self._drag_tb_id = tb.id
                    self._drag_action = "rotate"
                    self._drag_start_rot = tb.rotation
                    cx, cy, _, _ = self._tb_bounds(tb)
                    self._drag_start_angle = math.degrees(
                        math.atan2(pos.y()-cy, pos.x()-cx))
                    self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
                    return
            # Check body
            tb = self._tb_at(pos.x(), pos.y())
            if tb:
                self._drag_tb_id  = tb.id
                self._drag_action = "move"
                self._drag_tb_off = (pos.x()/self._disp_scale - tb.x,
                                     pos.y()/self._disp_scale - tb.y)
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        else:
            self._drag_pos = pos

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._mode == "text" and self._drag_tb_id:
            tb = next((t for t in self._text_boxes if t.id == self._drag_tb_id), None)
            if not tb: return
            if self._drag_action == "move":
                nx = pos.x()/self._disp_scale - self._drag_tb_off[0]
                ny = pos.y()/self._disp_scale - self._drag_tb_off[1]
                self.text_moved.emit(self._drag_tb_id, nx, ny)
            elif self._drag_action == "scale":
                cx, cy, _, _ = self._tb_bounds(tb)
                dist = max(1.0, math.hypot(pos.x()-cx, pos.y()-cy))
                new_scale = max(0.1, min(5.0,
                    self._drag_start_scale * dist / self._drag_start_dist))
                self.text_scaled.emit(self._drag_tb_id, new_scale)
            elif self._drag_action == "rotate":
                cx, cy, _, _ = self._tb_bounds(tb)
                angle = math.degrees(math.atan2(pos.y()-cy, pos.x()-cx))
                delta = angle - self._drag_start_angle
                new_rot = (self._drag_start_rot + delta) % 360
                if new_rot > 180: new_rot -= 360
                self.text_rotated.emit(self._drag_tb_id, new_rot)
        elif self._mode == "text":
            # Update cursor based on hover
            hover_handle = False
            for tb in reversed(self._text_boxes):
                sx, sy = self._scale_handle(tb)
                rx, ry = self._rotate_handle(tb)
                if self._hit_handle(pos, sx, sy):
                    self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
                    hover_handle = True; break
                if self._hit_handle(pos, rx, ry):
                    self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
                    hover_handle = True; break
            if not hover_handle:
                tb = self._tb_at(pos.x(), pos.y())
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor if tb
                                       else Qt.CursorShape.ArrowCursor))
        elif self._mode == "pan" and self._drag_pos is not None:
            d = pos - self._drag_pos; self._drag_pos = pos
            self.pan_delta.emit(-d.x()/self._disp_scale, -d.y()/self._disp_scale)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None; self._drag_tb_id = None; self._drag_action = None
        self.set_mode(self._mode)

    def wheelEvent(self, e): e.ignore()


# ── Theme Creator Dialog ──────────────────────────────────────────────────────
THEME_CANVAS_H = 480   # fixed display height for the frame preview in the dialog

class ArtBoxCanvas(QWidget):
    rect_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#111;")
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setMouseTracking(True)
        self._pixmap     = None
        self._disp_scale = 1.0
        self._rect       = None
        self._dragging   = False
        self._origin     = None

    def load_image(self, img: Image.Image):
        th = int(THEME_CANVAS_H * UI_SCALE)
        self._disp_scale = th / img.height
        dw = int(img.width * self._disp_scale)
        self.setFixedSize(dw, th)
        self._pixmap = pil_to_qpixmap(img.resize((dw, th), Image.LANCZOS))
        self._rect   = None
        self.update()

    def get_art_box(self):
        if self._rect is None: return None
        r = self._rect.normalized()
        if r.width() < 4 or r.height() < 4: return None
        s = self._disp_scale
        return (int(r.x()/s), int(r.y()/s), int(r.width()/s), int(r.height()/s))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._origin   = e.position().toPoint()
            self._rect     = QRect(self._origin, self._origin)
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._rect = QRect(self._origin, e.position().toPoint())
            self.update()
            self.rect_changed.emit()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.rect_changed.emit()
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        # Background / image
        if self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)
        else:
            p.fillRect(self.rect(), QColor("#111"))
        # Selection rect
        if self._rect:
            r = self._rect.normalized()
            # Dim overlay outside rect
            p.fillRect(0, 0, self.width(), r.top(),                            QColor(0,0,0,120))
            p.fillRect(0, r.bottom(), self.width(), self.height()-r.bottom(),  QColor(0,0,0,120))
            p.fillRect(0, r.top(), r.left(), r.height(),                       QColor(0,0,0,120))
            p.fillRect(r.right(), r.top(), self.width()-r.right(), r.height(), QColor(0,0,0,120))
            # Green border
            p.setPen(QPen(QColor("#5dbb00"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
            # Coords
            ab = self.get_art_box()
            if ab:
                p.setPen(QColor("#5dbb00"))
                p.setFont(QFont(FONT_MONO, sc(7)))
                p.drawText(r.left()+4, r.top()+sc(14),
                           f"{ab[0]},{ab[1]}  {ab[2]}×{ab[3]}")
        p.end()


class CreateThemeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Theme")
        self.setStyleSheet(f"background:{C_BG};color:#ccc;")
        self.setMinimumWidth(sc(560))

        self._img      = None   # PIL Image (full res)
        self._img_path = ""

        L = QVBoxLayout(self); L.setSpacing(sc(8)); L.setContentsMargins(sc(12),sc(12),sc(12),sc(12))

        # ── Name ──
        name_row = QWidget(); name_row.setStyleSheet("background:transparent;")
        nh = QHBoxLayout(name_row); nh.setContentsMargins(0,0,0,0); nh.setSpacing(sc(8))
        nh.addWidget(QLabel("THEME NAME:", styleSheet=f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;min-width:{sc(110)}px;"))
        self.name_edit = QLineEdit("My Theme")
        self.name_edit.setStyleSheet(f"background:#1a1a1a;color:#fff;border:1px solid #333;padding:{sc(4)}px;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;")
        nh.addWidget(self.name_edit, 1)
        L.addWidget(name_row)

        # ── Image upload ──
        img_row = QWidget(); img_row.setStyleSheet("background:transparent;")
        ih = QHBoxLayout(img_row); ih.setContentsMargins(0,0,0,0); ih.setSpacing(sc(8))
        self.img_lbl = QLabel("No frame image loaded")
        self.img_lbl.setStyleSheet(f"color:{C_DIM};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;")
        btn_img = make_button("Browse Frame Image…")
        btn_img.clicked.connect(self._browse_image)
        ih.addWidget(self.img_lbl, 1); ih.addWidget(btn_img)
        L.addWidget(img_row)

        # ── Canvas ──
        L.addWidget(QLabel("DRAG TO DEFINE ART BOX  (the region where cover art is composited):",
            styleSheet=f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;"))
        self.canvas = ArtBoxCanvas()
        scroll = QScrollArea(); scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setFixedHeight(int(THEME_CANVAS_H * UI_SCALE) + sc(4))
        scroll.setStyleSheet("QScrollArea{background:#111;border:1px solid #222;} QScrollBar:horizontal{background:#1a1a1a;height:8px;} QScrollBar::handle:horizontal{background:#333;border-radius:4px;}")
        L.addWidget(scroll)

        # ── Art box readout ──
        self.box_lbl = QLabel("Art box: not defined")
        self.box_lbl.setStyleSheet(f"color:{C_DIM};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;")
        L.addWidget(self.box_lbl)
        self.canvas.rect_changed.connect(self._update_box_lbl)

        # ── Options ──
        opt_row = QWidget(); opt_row.setStyleSheet("background:transparent;")
        oh = QHBoxLayout(opt_row); oh.setContentsMargins(0,0,0,0); oh.setSpacing(sc(16))

        # sep_y
        sep_w = QWidget(); sep_w.setStyleSheet("background:transparent;")
        sh2 = QHBoxLayout(sep_w); sh2.setContentsMargins(0,0,0,0); sh2.setSpacing(sc(6))
        sh2.addWidget(QLabel("SEP LINE Y:", styleSheet=f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;"))
        self.sep_spin = QSpinBox(); self.sep_spin.setRange(-1, 9999); self.sep_spin.setValue(-1)
        self.sep_spin.setSpecialValueText("None")
        self.sep_spin.setStyleSheet(f"background:#1a1a1a;color:#fff;border:1px solid #333;padding:{sc(3)}px;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;")
        sh2.addWidget(self.sep_spin)
        oh.addWidget(sep_w)
        oh.addStretch()
        L.addWidget(opt_row)

        # ── Buttons ──
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.setStyleSheet(f"QPushButton{{background:{C_BTN};color:#ccc;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;border:none;padding:{sc(6)}px {sc(20)}px;}} QPushButton:hover{{background:{C_BTN_HOV};color:#fff;}}")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        L.addWidget(btns)

    def _browse_image(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select Frame Image", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp);;All files (*.*)")
        if not p: return
        try:
            img = Image.open(p).convert("RGBA")
        except Exception as ex:
            QMessageBox.critical(self, "Error", str(ex)); return
        self._img      = img
        self._img_path = p
        self.img_lbl.setText(f"{Path(p).name}  ({img.width} × {img.height} px)")
        self.img_lbl.setStyleSheet(f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;")
        self.canvas.load_image(img)
        self._update_box_lbl()

    def _update_box_lbl(self):
        ab = self.canvas.get_art_box()
        if ab:
            self.box_lbl.setText(f"Art box: x={ab[0]}  y={ab[1]}  w={ab[2]}  h={ab[3]}")
            self.box_lbl.setStyleSheet(f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;")
        else:
            self.box_lbl.setText("Art box: not defined")
            self.box_lbl.setStyleSheet(f"color:{C_DIM};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;")

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a theme name."); return
        if self._img is None:
            QMessageBox.warning(self, "No image", "Please load a frame image."); return
        ab = self.canvas.get_art_box()
        if ab is None:
            QMessageBox.warning(self, "No art box", "Please drag to define the art box region."); return

        out_dir, _ = QFileDialog.getSaveFileName(self, "Save Theme JSON", f"{name}.json",
            "Theme JSON (*.json)")
        if not out_dir: return

        out_path  = Path(out_dir)
        img_dest  = out_path.parent / Path(self._img_path).name
        # Copy image alongside JSON (skip if same file)
        if Path(self._img_path).resolve() != img_dest.resolve():
            shutil.copy2(self._img_path, img_dest)

        ax, ay, aw, ah = ab
        iw, ih = self._img.size
        sep = self.sep_spin.value() if self.sep_spin.value() >= 0 else None
        theme = {
            "name":       name,
            "file":       img_dest.name,
            "art_box":    [ax, ay, aw, ah],
            "inner_slot": [ax, ay, aw, ah],   # default same as art_box; user can edit JSON
            "frame_wh":   [iw, ih],
            "sep_y":      sep,
            "behind":     False,
        }
        try:
            with open(out_path, "w") as f:
                json.dump(theme, f, indent=2)
        except Exception as ex:
            QMessageBox.critical(self, "Save error", str(ex)); return

        QMessageBox.information(self, "Theme saved",
            f"Theme '{name}' saved to:\n{out_path}\n\nImage copied to:\n{img_dest}")
        self.accept()


# ── Main window ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xbox Cover Art Builder — Team Resurgent")
        self.setStyleSheet(f"QMainWindow{{background:{C_BG};}}")
        # Fixed frame: no min/max buttons, no resize grip
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.art_img       = None
        self.result_img    = None
        self.art_path      = ""
        self.zoom          = 1.0
        self.off_x         = 0.0
        self.off_y         = 0.0
        self._frame_cache  = {}
        self._frame_label  = list(FRAMES.keys())[0]
        self.frame_img     = None
        self._disp_scale   = 1.0
        self.text_boxes    = []
        self._mode         = "pan"

        self._build_ui()
        self._switch_frame(self._frame_label)
        self._rebuild_text_list()

    def _build_ui(self):
        root = QWidget(); root.setStyleSheet(f"background:{C_BG};")
        self.setCentralWidget(root)
        main_v = QVBoxLayout(root)
        main_v.setContentsMargins(0,0,0,0); main_v.setSpacing(0)

        # ── Menu bar ──
        menubar = QMenuBar(self)
        menubar.setStyleSheet(f"""
            QMenuBar{{background:{C_HDR};color:#aaa;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;padding:{sc(2)}px {sc(6)}px;}}
            QMenuBar::item{{background:transparent;padding:{sc(4)}px {sc(10)}px;}}
            QMenuBar::item:selected{{background:{C_BTN};color:#fff;}}
            QMenu{{background:{C_BTN};color:#ccc;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;border:1px solid #333;}}
            QMenu::item{{padding:{sc(6)}px {sc(20)}px;}}
            QMenu::item:selected{{background:{C_GREEN};color:#000;}}
            QMenu::separator{{height:1px;background:#333;margin:{sc(3)}px 0;}}
        """)
        theme_menu = menubar.addMenu("Themes")
        act_create = QAction("Create Theme…", self)
        act_create.triggered.connect(self._create_theme)
        act_load   = QAction("Load Theme…",   self)
        act_load.triggered.connect(self._load_theme)
        theme_menu.addAction(act_create)
        theme_menu.addSeparator()
        theme_menu.addAction(act_load)
        self.setMenuBar(menubar)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(sc(40)); hdr.setStyleSheet(f"background:{C_HDR};")
        hdr_h = QHBoxLayout(hdr); hdr_h.setContentsMargins(sc(14),0,sc(14),0)
        title = QLabel("XBOX COVER ART BUILDER")
        title.setStyleSheet(f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(12)}pt;font-weight:bold;")

        # Coloured branding
        tr = QLabel("Team Resurgent")
        tr.setStyleSheet(f"color:{C_MAGENTA};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;")
        sep = QLabel("  |  ")
        sep.setStyleSheet(f"color:#333;font-family:'{FONT_MONO}';font-size:{sc(8)}pt;")
        d83 = QLabel("Darkone83")
        d83.setStyleSheet(f"color:{C_PURPLE};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;font-weight:bold;")

        hdr_h.addWidget(title); hdr_h.addStretch()
        hdr_h.addWidget(tr); hdr_h.addWidget(sep); hdr_h.addWidget(d83)
        main_v.addWidget(hdr)

        # Body
        body = QWidget(); body.setStyleSheet(f"background:{C_BG};")
        body_h = QHBoxLayout(body); body_h.setContentsMargins(sc(12),sc(8),sc(12),sc(8)); body_h.setSpacing(sc(12))
        main_v.addWidget(body)

        # Preview
        self.preview = PreviewLabel()
        self.preview.file_dropped.connect(self._load)
        self.preview.pan_delta.connect(self._on_pan)
        self.preview.text_moved.connect(self._on_text_moved)
        self.preview.text_scaled.connect(self._on_text_scaled)
        self.preview.text_rotated.connect(self._on_text_rotated)
        self.preview.set_text_boxes(self.text_boxes)
        self.preview.wheelEvent = self._wheel_event
        body_h.addWidget(self.preview, 0)

        # Controls
        ctrl = QWidget(); ctrl.setStyleSheet(f"background:{C_BG};"); ctrl.setFixedWidth(sc(215))
        ctrl_v = QVBoxLayout(ctrl); ctrl_v.setContentsMargins(sc(4),0,0,0); ctrl_v.setSpacing(sc(2))
        body_h.addWidget(ctrl, 0)

        # Frame
        ctrl_v.addWidget(section_label("FRAME"))
        self.frame_combo = QComboBox()
        self.frame_combo.addItems(list(FRAMES.keys()))
        self.frame_combo.setStyleSheet(f"""
            QComboBox{{background:{C_BTN};color:#ccc;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;border:none;padding:{sc(5)}px {sc(8)}px;}}
            QComboBox:hover{{background:{C_BTN_HOV};}}
            QComboBox QAbstractItemView{{background:#1c1c1c;color:#ccc;selection-background-color:{C_GREEN};selection-color:#000;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;}}
        """)
        self.frame_combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.frame_combo.currentTextChanged.connect(self._on_frame_change)
        ctrl_v.addWidget(self.frame_combo)

        # Artwork
        ctrl_v.addSpacing(sc(6)); ctrl_v.addWidget(section_label("ARTWORK"))
        self.art_lbl = make_label("No image loaded"); self.art_lbl.setWordWrap(True)
        ctrl_v.addWidget(self.art_lbl)
        bb = make_button("Browse..."); bb.clicked.connect(self._browse); ctrl_v.addWidget(bb)

        # Zoom
        ctrl_v.addSpacing(sc(6)); ctrl_v.addWidget(section_label("ZOOM"))
        zr = QWidget(); zr.setStyleSheet("background:transparent;")
        zh = QHBoxLayout(zr); zh.setContentsMargins(0,0,0,0); zh.setSpacing(sc(4))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10,400); self.zoom_slider.setValue(100)
        sh = sc(14)
        self.zoom_slider.setStyleSheet(f"QSlider::groove:horizontal{{background:#1a1a1a;height:{sc(4)}px;border-radius:2px;}} QSlider::handle:horizontal{{background:{C_GREEN};width:{sh}px;height:{sh}px;margin:{-sh//2+1}px 0;border-radius:{sh//2}px;}} QSlider::sub-page:horizontal{{background:{C_GREEN};border-radius:2px;}}")
        self.zoom_slider.valueChanged.connect(self._on_slider_changed)
        self.zoom_lbl = make_label("100%", C_GREEN, bold=True); self.zoom_lbl.setFixedWidth(sc(42))
        zh.addWidget(self.zoom_slider); zh.addWidget(self.zoom_lbl); ctrl_v.addWidget(zr)
        zbr = QWidget(); zbr.setStyleSheet("background:transparent;")
        zbh = QHBoxLayout(zbr); zbh.setContentsMargins(0,0,0,0); zbh.setSpacing(sc(4))
        for t,fn in [("−",lambda:self._zoom_by(-5)),("+",lambda:self._zoom_by(+5)),("Reset Fit",self._reset_fit)]:
            b=make_button(t,fg="#aaa",color="#1a1a1a",hover="#252525"); b.clicked.connect(fn); zbh.addWidget(b)
        ctrl_v.addWidget(zbr)

        # Position
        ctrl_v.addSpacing(sc(6)); ctrl_v.addWidget(section_label("POSITION  (drag to pan)"))
        ng = QWidget(); ng.setStyleSheet("background:transparent;")
        ng_g = QGridLayout(ng); ng_g.setSpacing(sc(2)); ng_g.setContentsMargins(0,0,0,0)
        bc = dict(color="#1a1a1a",fg="#aaa",hover="#252525")
        bu=make_button("▲",**bc); bu.clicked.connect(lambda:self._nudge(0,-10))
        bl=make_button("◀",**bc); bl.clicked.connect(lambda:self._nudge(-10,0))
        bce=make_button("●",**bc); bce.clicked.connect(self._centre)
        brr=make_button("▶",**bc); brr.clicked.connect(lambda:self._nudge(10,0))
        bdd=make_button("▼",**bc); bdd.clicked.connect(lambda:self._nudge(0,10))
        ng_g.addWidget(bu,0,1); ng_g.addWidget(bl,1,0); ng_g.addWidget(bce,1,1)
        ng_g.addWidget(brr,1,2); ng_g.addWidget(bdd,2,1)
        ctrl_v.addWidget(ng)

        # TEXT OVERLAYS
        ctrl_v.addSpacing(sc(6)); ctrl_v.addWidget(section_label("TEXT OVERLAYS"))

        mode_row = QWidget(); mode_row.setStyleSheet("background:transparent;")
        mode_h = QHBoxLayout(mode_row); mode_h.setContentsMargins(0,0,0,0); mode_h.setSpacing(sc(4))
        self.pan_mode_btn  = make_button("🖼 Art Pan",   color=C_GREEN,   fg="#000", hover="#4a9a00")
        self.text_mode_btn = make_button("✏ Text Move", color="#1a1a1a", fg="#aaa", hover="#252525")
        self.pan_mode_btn.clicked.connect(lambda: self._set_mode("pan"))
        self.text_mode_btn.clicked.connect(self._toggle_text_mode)
        mode_h.addWidget(self.pan_mode_btn); mode_h.addWidget(self.text_mode_btn)
        ctrl_v.addWidget(mode_row)

        btn_add = make_button("＋ Add Text Box", color="#1a1a1a", fg=C_GREEN, hover="#252525")
        btn_add.clicked.connect(self._add_text_box)
        ctrl_v.addWidget(btn_add)

        # Text list
        self.text_list_w = QWidget(); self.text_list_w.setStyleSheet("background:transparent;")
        self.text_list_v = QVBoxLayout(self.text_list_w)
        self.text_list_v.setContentsMargins(0,sc(2),0,sc(2)); self.text_list_v.setSpacing(sc(2))
        scroll = QScrollArea(); scroll.setWidget(self.text_list_w); scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(sc(150))
        scroll.setStyleSheet(f"QScrollArea{{background:#111;border:1px solid #222;}} QScrollBar:vertical{{background:#1a1a1a;width:{sc(8)}px;}} QScrollBar::handle:vertical{{background:#333;border-radius:{sc(4)}px;}} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")
        ctrl_v.addWidget(scroll)

        # Frame info
        ctrl_v.addSpacing(sc(4)); ctrl_v.addWidget(section_label("FRAME INFO"))
        self.info_lbl = make_label(""); self.info_lbl.setWordWrap(True)
        ctrl_v.addWidget(self.info_lbl)

        ctrl_v.addStretch()
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setStyleSheet("color:#1e1e1e;"); ctrl_v.addWidget(line)
        ctrl_v.addSpacing(sc(4))

        bs = make_button("Save Cover", color=C_GREEN, fg="#000", hover="#4a9a00"); bs.clicked.connect(self._save); ctrl_v.addWidget(bs)
        ctrl_v.addSpacing(sc(4))
        bc2 = make_button("Clear", color="#1a1a1a", fg="#555", hover="#252525"); bc2.clicked.connect(self._clear); ctrl_v.addWidget(bc2)

        self.status_lbl = QLabel("Ready — drop an image onto the preview")
        self.status_lbl.setStyleSheet(f"background:{C_HDR};color:#333;font-family:'{FONT_MONO}';font-size:{sc(8)}pt;padding:{sc(4)}px {sc(12)}px;")
        main_v.addWidget(self.status_lbl)

    # ── Mode ──────────────────────────────────────────────────────────────────
    def _toggle_text_mode(self):
        """Toggle text mode on/off — click again to return to pan and hide handles."""
        self._set_mode("pan" if self._mode == "text" else "text")

    def _set_mode(self, mode):
        self._mode = mode
        self.preview.set_mode(mode)
        active_ss   = f"QPushButton{{background:{C_GREEN};color:#000;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;font-weight:bold;border:none;padding:{sc(7)}px {sc(10)}px;}} QPushButton:hover{{background:#4a9a00;color:#000;}}"
        inactive_ss = f"QPushButton{{background:#1a1a1a;color:#aaa;font-family:'{FONT_MONO}';font-size:{sc(9)}pt;font-weight:bold;border:none;padding:{sc(7)}px {sc(10)}px;}} QPushButton:hover{{background:#252525;color:#fff;}}"
        if mode == "pan":
            self.pan_mode_btn.setStyleSheet(active_ss)
            self.text_mode_btn.setStyleSheet(inactive_ss)
        else:
            self.pan_mode_btn.setStyleSheet(inactive_ss)
            self.text_mode_btn.setStyleSheet(active_ss)
        self._redraw()   # show/hide handles immediately

    # ── Text overlay management ───────────────────────────────────────────────
    def _add_text_box(self):
        fw, fh = FRAMES[self._frame_label]["frame_wh"]
        tb = TextBox("GAME TITLE", x=fw//2, y=fh//2)  # start centred
        dlg = TextBoxDialog(tb, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tb = dlg.get_result()
            self.text_boxes.append(tb)
            self._rebuild_text_list(); self._redraw()

    def _edit_text_box(self, tb_id):
        tb = next((t for t in self.text_boxes if t.id == tb_id), None)
        if not tb: return
        dlg = TextBoxDialog(tb, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            idx = next(i for i,t in enumerate(self.text_boxes) if t.id == tb_id)
            self.text_boxes[idx] = dlg.get_result()
            self._rebuild_text_list(); self._redraw()

    def _delete_text_box(self, tb_id):
        self.text_boxes = [t for t in self.text_boxes if t.id != tb_id]
        self._rebuild_text_list(); self._redraw()

    def _on_text_moved(self, tb_id, nx, ny):
        tb = next((t for t in self.text_boxes if t.id == tb_id), None)
        if tb: tb.x = int(nx); tb.y = int(ny); self._redraw()

    def _on_text_scaled(self, tb_id, new_scale):
        tb = next((t for t in self.text_boxes if t.id == tb_id), None)
        if tb: tb.scale = round(new_scale, 2); self._rebuild_text_list(); self._redraw()

    def _on_text_rotated(self, tb_id, new_rot):
        tb = next((t for t in self.text_boxes if t.id == tb_id), None)
        if tb: tb.rotation = round(new_rot, 1); self._rebuild_text_list(); self._redraw()

    def _rebuild_text_list(self):
        while self.text_list_v.count():
            it = self.text_list_v.takeAt(0)
            if it.widget(): it.widget().deleteLater()

        if not self.text_boxes:
            self.text_list_v.addWidget(make_label("No text boxes yet", "#333")); return

        for tb in self.text_boxes:
            row = QWidget(); row.setStyleSheet("background:#161616;border-radius:2px;")
            rh  = QHBoxLayout(row); rh.setContentsMargins(sc(4),sc(3),sc(4),sc(3)); rh.setSpacing(sc(4))

            swatch = QLabel("  "); swatch.setFixedSize(sc(14), sc(14))
            swatch.setStyleSheet(f"background:{tb.color_hex()};border:1px solid #444;")
            rh.addWidget(swatch)

            lbl = QLabel(tb.label())
            lbl.setStyleSheet(f"color:#aaa;font-family:'{FONT_MONO}';font-size:{sc(8)}pt;"); lbl.setMinimumWidth(sc(80))
            rh.addWidget(lbl, 1)

            tid = tb.id
            be = QPushButton("✏"); be.setFixedSize(sc(22), sc(22))
            be.setStyleSheet(f"background:#1c1c1c;color:{C_GREEN};border:none;font-size:{sc(10)}pt;")
            be.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            be.clicked.connect(lambda c, i=tid: self._edit_text_box(i))
            rh.addWidget(be)

            bd = QPushButton("✕"); bd.setFixedSize(sc(22), sc(22))
            bd.setStyleSheet(f"background:#1c1c1c;color:#c03030;border:none;font-size:{sc(10)}pt;")
            bd.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            bd.clicked.connect(lambda c, i=tid: self._delete_text_box(i))
            rh.addWidget(bd)

            self.text_list_v.addWidget(row)

    # ── Frame management ──────────────────────────────────────────────────────
    def _get_frame(self, label):
        if label not in self._frame_cache:
            img = load_frame_img(FRAMES[label])
            if img is None:
                QMessageBox.critical(self, "Missing frame",
                    f"Cannot find '{FRAMES[label]['file']}'\nPlace it next to this script.")
                return None
            self._frame_cache[label] = img
        return self._frame_cache[label]

    def _switch_frame(self, label):
        img = self._get_frame(label)
        if img is None: return
        self.frame_img   = img
        fw, fh           = FRAMES[label]["frame_wh"]
        self._disp_scale = DISP_H / fh
        dw               = int(fw * self._disp_scale)
        self.preview.setFixedSize(dw, DISP_H)
        self.preview.set_disp_scale(self._disp_scale)
        # Lock window to exact content size — no resize in either axis
        total_w  = dw + sc(215) + sc(12)*3
        menu_h   = self.menuBar().sizeHint().height() if self.menuBar() else 0
        self.setFixedSize(total_w, DISP_H + sc(40) + sc(24) + menu_h)  # preview + header + status + menu
        self._update_info()
        if self.art_img: self._reset_fit()
        else: self._redraw()

    def _on_frame_change(self, label):
        self._frame_label = label; self._switch_frame(label); self._set_status(f"Frame: {label}")

    def _active_art_box(self):
        return FRAMES[self._frame_label]["art_box"]

    def _update_info(self):
        p = FRAMES[self._frame_label]
        ix,iy,iw,ih = p["inner_slot"]; fw,fh = p["frame_wh"]
        self.info_lbl.setText(
            "Frame:    {} x {} px".format(fw,fh) + chr(10) +
            "Art slot: {} x {} px".format(iw,ih) + chr(10) +
            "Slot pos: ({}, {})".format(ix,iy))

    # ── Load ──────────────────────────────────────────────────────────────────
    def _load(self, path):
        try: img = Image.open(path).convert("RGBA")
        except Exception as ex: QMessageBox.critical(self,"Error",str(ex)); return
        self.art_img = img; self.art_path = path
        name = Path(path).name
        self.art_lbl.setText(f"{name}\n{img.width} x {img.height} px")
        self.art_lbl.setStyleSheet(f"color:{C_GREEN};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;")
        self._set_status(f"Loaded: {name}"); self._reset_fit()

    def _browse(self):
        p,_ = QFileDialog.getOpenFileName(self,"Select artwork","",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.gif);;All files (*.*)")
        if p: self._load(p)

    # ── Zoom / pan ────────────────────────────────────────────────────────────
    def _reset_fit(self):
        if self.art_img is None: return
        ax, ay, aw, ah = FRAMES[self._frame_label]["art_box"]
        self.zoom  = auto_fit(self.art_img.width, self.art_img.height, aw, ah)
        self.off_x = (self.art_img.width  * self.zoom) / 2
        self.off_y = (self.art_img.height * self.zoom) / 2
        self._sync_zoom_ui(); self._redraw()

    def _centre(self):
        if self.art_img is None: return
        self.off_x = (self.art_img.width  * self.zoom) / 2
        self.off_y = (self.art_img.height * self.zoom) / 2; self._redraw()

    def _zoom_by(self, steps):
        if self.art_img is None: return
        self._apply_zoom_pct(max(10, min(400, round(self.zoom*100) + steps)))

    def _on_slider_changed(self, val):
        if self.art_img is None: return
        self._apply_zoom_pct(val)

    def _apply_zoom_pct(self, pct):
        nz = round(pct / 100.0, 2)
        if self.zoom > 0 and self.art_img:
            r = nz / self.zoom; self.off_x *= r; self.off_y *= r
        self.zoom = nz; self._sync_zoom_ui(); self._redraw()

    def _sync_zoom_ui(self):
        pct = max(10, min(400, round(self.zoom * 100)))
        self.zoom_lbl.setText(f"{pct}%")
        self.zoom_slider.blockSignals(True); self.zoom_slider.setValue(pct); self.zoom_slider.blockSignals(False)

    def _wheel_event(self, e): self._zoom_by(3 if e.angleDelta().y()>0 else -3)
    def _on_pan(self, dx, dy): self.off_x += dx; self.off_y += dy; self._redraw()
    def _nudge(self, dx, dy):
        if self.art_img is None: return
        self.off_x -= dx; self.off_y -= dy; self._redraw()

    # ── Redraw ────────────────────────────────────────────────────────────────
    def _redraw(self):
        if self.frame_img is None: return
        fw,fh = FRAMES[self._frame_label]["frame_wh"]
        dw    = int(fw * self._disp_scale)

        if self.art_img:
            behind = FRAMES[self._frame_label].get("behind", False)
            base   = composite(self.frame_img, self.art_img,
                               self.zoom, self.off_x, self.off_y,
                               self._active_art_box(), behind=behind)
        else:
            base = self.frame_img.copy()

        # Apply text overlays
        full = render_text_overlays(base, self.text_boxes)
        self.result_img = full

        # Scale down for preview first, then draw handles in display-pixel space
        preview_pil = full.resize((dw, DISP_H), Image.LANCZOS)

        if self._mode == "text" and self.text_boxes:
            # Draw handles directly on the downscaled preview image
            pd = ImageDraw.Draw(preview_pil)
            s  = self._disp_scale
            for tb in self.text_boxes:
                ew = max(len(tb.text)*tb.font_px*0.62, 80) * s
                eh = tb.font_px * 1.7 * s
                cx = tb.x * s; cy = tb.y * s
                x0,y0 = cx-ew/2, cy-eh/2
                x1,y1 = cx+ew/2, cy+eh/2
                # Bounding box
                pd.rectangle([x0,y0,x1,y1], outline=(93,187,0,200), width=2)
                # Centre dot (move target)
                r = HANDLE_R
                pd.ellipse([cx-r,cy-r,cx+r,cy+r], fill=(93,187,0,220), outline=(255,255,255,180), width=1)
                # Scale handle — bottom-right — green square
                pd.rectangle([x1-r,y1-r,x1+r,y1+r], fill=(93,187,0,220), outline=(255,255,255,180), width=1)
                # Rotate handle — top-right — magenta circle
                pd.ellipse([x1-r,y0-r,x1+r,y0+r], fill=(255,0,204,220), outline=(255,255,255,180), width=1)
                # Label showing current scale and rotation
                lbl = f"{tb.font_pt}pt  {tb.scale:.1f}x  {int(tb.rotation)}°"
                pd.text((x0+2, y1+4), lbl, fill=(93,187,0,200))

        self.preview.setPixmap(pil_to_qpixmap(preview_pil))

    # ── Save ──────────────────────────────────────────────────────────────────
    def _save(self):
        if not self.result_img:
            QMessageBox.warning(self,"Nothing to save","Load artwork first."); return
        stem = Path(self.art_path).stem if self.art_path else "cover"
        p,_ = QFileDialog.getSaveFileName(self,"Save cover art",
            f"{stem}_xbox_cover.jpg","JPEG (*.jpg *.jpeg);;PNG (*.png)")
        if not p: return
        fmt = "PNG" if p.lower().endswith(".png") else "JPEG"
        img = self.result_img.convert("RGB" if fmt=="JPEG" else "RGBA")
        kw  = {"quality":97,"subsampling":0} if fmt=="JPEG" else {}
        try:
            img.save(p, fmt, **kw)
            self._set_status(f"Saved: {Path(p).name}  ({os.path.getsize(p)//1024} KB)")
            QMessageBox.information(self,"Saved",f"Cover saved:\n{p}")
        except Exception as ex: QMessageBox.critical(self,"Save error",str(ex))

    # ── Clear ─────────────────────────────────────────────────────────────────
    def _clear(self):
        self.art_img = self.result_img = None; self.art_path = ""
        self.zoom = 1.0; self.off_x = self.off_y = 0.0
        self.text_boxes.clear(); self._rebuild_text_list()
        self.art_lbl.setText("No image loaded")
        self.art_lbl.setStyleSheet(f"color:{C_DIM};font-family:'{FONT_MONO}';font-size:{sc(8)}pt;")
        self._sync_zoom_ui(); self._set_status("Cleared"); self._redraw()

    def _create_theme(self):
        dlg = CreateThemeDialog(self)
        dlg.exec()

    def _load_theme(self):
        p, _ = QFileDialog.getOpenFileName(self, "Load Theme JSON", "",
            "Theme JSON (*.json);;All files (*.*)")
        if not p: return
        try:
            with open(p) as f:
                t = json.load(f)
        except Exception as ex:
            QMessageBox.critical(self, "Load error", str(ex)); return

        # Validate required keys
        for key in ("name", "file", "art_box", "frame_wh"):
            if key not in t:
                QMessageBox.critical(self, "Invalid theme",
                    f"Theme JSON is missing required key: '{key}'"); return

        name     = t["name"]
        img_path = Path(p).parent / t["file"]
        if not img_path.exists():
            QMessageBox.critical(self, "Missing image",
                f"Frame image not found:\n{img_path}"); return

        ab = tuple(t["art_box"])
        # inner_slot falls back to art_box if omitted
        sl = tuple(t.get("inner_slot", t["art_box"]))
        wh = tuple(t["frame_wh"])

        profile = {
            "file":       str(img_path),
            "art_box":    ab,
            "inner_slot": sl,
            "frame_wh":   wh,
            "sep_y":      t.get("sep_y", None),
        }
        if t.get("behind", False):
            profile["behind"] = True

        # If name already exists, overwrite silently (user reloading updated theme)
        FRAMES[name] = profile

        # Refresh combo — block signals to avoid triggering _on_frame_change mid-update
        self.frame_combo.blockSignals(True)
        if self.frame_combo.findText(name) == -1:
            self.frame_combo.addItem(name)
        self.frame_combo.blockSignals(False)

        # Evict cached frame image so it reloads fresh
        self._frame_cache.pop(name, None)

        # Switch to the loaded theme
        self.frame_combo.setCurrentText(name)
        self._on_frame_change(name)
        self._set_status(f"Theme loaded: {name}")

    def _set_status(self, msg): self.status_lbl.setText(msg)


# ── Entry ─────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # On macOS, bump logical size by 1.5x so the UI reads comfortably on Retina.
    if platform.system() == "Darwin":
        global DISP_H, UI_SCALE
        UI_SCALE = 1.5
        DISP_H   = int(DISP_H * UI_SCALE)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()