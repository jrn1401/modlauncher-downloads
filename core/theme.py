"""Design: Hell/Dunkel, Akzentfarbe und frei einstellbare Farben (Theme-Manager).

Alle Farben sind (hell, dunkel)-Paare; eigene Farben gelten in beiden Modi.
Absichtlich schlank: Es gibt keine Animationen und keine Hintergrund-Threads.
"""
import re

import customtkinter as ctk

DEFAULT_ACCENT = "#4f8cff"
ACCENTS = {
    "Blue": "#4f8cff", "Violet": "#8b5cf6", "Pink": "#e5589f", "Red": "#e5484d",
    "Orange": "#f08a24", "Green": "#2e9d5b", "Teal": "#14b8a6",
}
MODES = {"Dark": "dark", "Light": "light", "System": "system"}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_PALETTE = {
    "sidebar": ("#e6e9f1", "#14161b"),
    "main": ("#f3f5fa", "#1b1e25"),
    "card": ("#ffffff", "#242831"),
    "inset": ("#e8ebf3", "#14161b"),
    "hover": ("#d3d9e8", "#262b36"),
    "bubble": ("#e8ebf3", "#2d323d"),
}
# Namen der frei einstellbaren Farben (Anzeigetext, Schlüssel)
COLOR_KEYS = [("Background", "main"), ("Sidebar", "sidebar"), ("Cards and menus", "card"),
              ("Input fields", "inset"), ("Hover", "hover"), ("Text", "text")]

PRESETS = {
    "Default": {"mode": "dark", "accent": DEFAULT_ACCENT, "colors": {}},
    "Light": {"mode": "light", "accent": DEFAULT_ACCENT, "colors": {}},
    "Graphite": {"mode": "dark", "accent": "#9aa4b2", "colors": {
        "main": "#202124", "sidebar": "#171717", "card": "#2b2c2f", "inset": "#161616", "hover": "#34363a", "text": "#e8eaed"}},
    "Ocean": {"mode": "dark", "accent": "#14b8a6", "colors": {
        "main": "#0f1e2b", "sidebar": "#0a1520", "card": "#16293a", "inset": "#0a1520", "hover": "#1d3549", "text": "#e6f1f7"}},
    "Forest": {"mode": "dark", "accent": "#2e9d5b", "colors": {
        "main": "#14201a", "sidebar": "#0e1712", "card": "#1c2d24", "inset": "#0e1712", "hover": "#243a2f", "text": "#e8f3ec"}},
    "Rose": {"mode": "dark", "accent": "#e5589f", "colors": {
        "main": "#241821", "sidebar": "#1a1018", "card": "#31212d", "inset": "#1a1018", "hover": "#3d2938", "text": "#f6e9f1"}},
}

PALETTE = dict(DEFAULT_PALETTE)
MUTED = ("gray40", "gray60")
TEXT = ("gray10", "gray90")
DANGER = "#e5484d"
OK = "#2e9d5b"
_accent = DEFAULT_ACCENT


def c(name: str):
    return PALETTE[name]


def accent() -> str:
    return _accent


def is_hex(value) -> bool:
    return isinstance(value, str) and bool(HEX_RE.match(value))


def shade(color: str, factor: float) -> str:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * factor))) for v in (r, g, b))


def contrast_text(bg: str) -> str:
    r, g, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5))
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def apply(settings: dict) -> None:
    """Setzt Modus, Akzent und eigene Farben. Wirkt auf danach erzeugte Widgets (die App baut ihre Oberfläche neu auf)."""
    global _accent, MUTED, TEXT
    mode = settings.get("appearance_mode", "dark")
    ctk.set_appearance_mode(mode if mode in ("dark", "light", "system") else "dark")
    acc = settings.get("accent", DEFAULT_ACCENT)
    _accent = acc if is_hex(acc) else DEFAULT_ACCENT

    PALETTE.clear()
    PALETTE.update(DEFAULT_PALETTE)
    custom = settings.get("colors") or {}
    for key in ("main", "sidebar", "card", "inset", "hover"):
        if is_hex(custom.get(key)):
            PALETTE[key] = (custom[key], custom[key])
    if is_hex(custom.get("card")) and not is_hex(custom.get("bubble")):
        PALETTE["bubble"] = (shade(custom["card"], 1.15),) * 2
    if is_hex(custom.get("text")):
        TEXT = (custom["text"], custom["text"])
        MUTED = (shade(custom["text"], 0.65),) * 2
    else:
        TEXT, MUTED = ("gray10", "gray90"), ("gray40", "gray60")

    hover = shade(_accent, 0.82)
    on_accent = contrast_text(_accent)
    patches = {
        "CTkButton": {"fg_color": _accent, "hover_color": hover, "text_color": on_accent},
        "CTkOptionMenu": {"fg_color": _accent, "button_color": hover, "button_hover_color": shade(_accent, 0.7)},
        "CTkComboBox": {"button_color": _accent, "button_hover_color": hover},
        "CTkSwitch": {"progress_color": _accent},
        "CTkRadioButton": {"fg_color": _accent, "hover_color": hover},
        "CTkCheckBox": {"fg_color": _accent, "hover_color": hover},
        "CTkSegmentedButton": {"selected_color": _accent, "selected_hover_color": hover},
        "CTkProgressBar": {"progress_color": _accent},
        "CTkSlider": {"progress_color": _accent, "button_color": _accent, "button_hover_color": hover},
    }
    try:
        for widget, keys in patches.items():
            for key, value in keys.items():
                if key in ctk.ThemeManager.theme.get(widget, {}):
                    ctk.ThemeManager.theme[widget][key] = [value, value]
    except Exception as exc:     # Farbanpassung ist nur Kosmetik
        print("Theme konnte nicht angepasst werden:", exc)
