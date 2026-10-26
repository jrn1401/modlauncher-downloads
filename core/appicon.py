"""App-Icon: Hintergrundfarbe oder -bild frei wählbar, das Kürzel JOPML bleibt immer sichtbar."""
import sys
from pathlib import Path

from core.config import app_dir
from core.version import SHORT_NAME

DEFAULT_BG = "#4f8cff"


def _font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)       # Pillow >= 10.1: skalierbar
    except TypeError:
        pass
    for name in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(size: int = 256, bg: str = DEFAULT_BG, image_path: str | None = None):
    """Gibt ein PIL-Bild zurück. Mit image_path wird das Bild mittig zugeschnitten; der Text steht immer darüber."""
    from PIL import Image, ImageDraw, ImageOps

    base = None
    if image_path:
        try:
            with Image.open(image_path) as im:
                base = ImageOps.fit(im.convert("RGBA"), (size, size), Image.LANCZOS)
        except Exception:
            base = None
    if base is None:
        base = Image.new("RGBA", (size, size), bg if bg else DEFAULT_BG)
    # abgerundete Ecken
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(base, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    fs = size // 3
    font = _font(fs)
    while fs > 8 and draw.textbbox((0, 0), SHORT_NAME, font=font)[2] > size * 0.86:
        fs -= max(1, size // 40)
        font = _font(fs)
    box = draw.textbbox((0, 0), SHORT_NAME, font=font)
    x = (size - (box[2] - box[0])) / 2 - box[0]
    y = (size - (box[3] - box[1])) / 2 - box[1]
    r, g, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5)) if (not image_path and bg and len(bg) == 7) else (0, 0, 0)
    light_bg = (not image_path) and (0.299 * r + 0.587 * g + 0.114 * b) > 170
    fill, outline = ("#111111", "#ffffff") if light_bg else ("#ffffff", "#000000")
    draw.text((x, y), SHORT_NAME, font=font, fill=fill, stroke_width=max(1, size // 64), stroke_fill=outline)
    return img


def save_files(settings: dict) -> Path | None:
    """Schreibt icon.png/icon.ico in den Datenordner und gibt den .ico-Pfad zurück."""
    try:
        img = render(256, settings.get("icon_bg") or DEFAULT_BG, settings.get("icon_image") or None)
        png, ico = app_dir() / "icon.png", app_dir() / "icon.ico"
        img.save(png)
        img.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return ico
    except Exception as exc:
        print("Icon konnte nicht erstellt werden:", exc)
        return None


def apply_to_window(window, settings: dict) -> None:
    """Setzt das Fenster-Icon. CTk setzt unter Windows nach ~200 ms sein eigenes Icon, daher verzögert."""
    ico = save_files(settings)
    if ico is None:
        return

    def _set():
        try:
            if sys.platform.startswith("win"):
                window.iconbitmap(str(ico))
            else:
                from PIL import ImageTk
                window._jopml_icon = ImageTk.PhotoImage(render(128, settings.get("icon_bg") or DEFAULT_BG,
                                                               settings.get("icon_image") or None))
                window.iconphoto(True, window._jopml_icon)
        except Exception as exc:
            print("Fenster-Icon nicht gesetzt:", exc)

    window.after(350, _set)
