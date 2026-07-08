# app_icon.py
import platform
import sys
from pathlib import Path
from PIL import Image, ImageTk


def _project_root():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def set_window_icon(window):
    root = _project_root()

    ico_path = root / "assets" / "icons" / "CamComposite.ico"
    png_path = root / "assets" / "icons" / "CamComposite.png"

    try:
        if platform.system() == "Windows" and ico_path.exists():
            window.iconbitmap(str(ico_path))
            return

        if png_path.exists():
            image = Image.open(png_path).convert("RGBA")
            icon = ImageTk.PhotoImage(image)
            window._camcomposite_icon_ref = icon
            window.iconphoto(True, icon)

    except Exception as e:
        print(f"Window icon warning: {e}")