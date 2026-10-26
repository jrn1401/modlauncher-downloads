"""Farben und Design. Alle Farben sind (hell, dunkel)-Paare, customtkinter wählt automatisch."""
import re

import customtkinter as ctk

DEFAULT_ACCENT = "#4f8cff"
ACCENTS = {
    "Blau": "#4f8cff", "Violett": "#8b5cf6", "Pink": "#e5589f", "Rot": "#e5484d",
    "Orange": "#f08a24", "Grün": "#2e9d5b", "Türkis": "#14b8a6",
}
MODES = {"Dunkel": "dark", "Hell": "light", "System": "system"}
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

PALETTE = {
    "sidebar": ("#e6e9f1", "#14161b"),
    "main": ("#f3f5fa", "#1b1e25"),
    "card": ("#ffffff", "#242831"),
    "inset": ("#e8ebf3", "#14161b"),
    "hover": ("#d3d9e8", "#262b36"),
    "bubble": ("#e8ebf3", "#2d323d"),
}
MUTED = ("gray40", "gray60")
TEXT = ("gray10", "gray90")
DANGER = "#e5484d"
OK = "#2e9d5b"

_accent = DEFAULT_ACCENT


def c(name: str):
    return PALETTE[name]


def accent() -> str:
    return _accent


def shade(color: str, factor: float) -> str:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * factor))) for v in (r, g, b))


def apply(settings: dict) -> None:
    """Setzt Hell/Dunkel und färbt die Standard-Widgets mit der Akzentfarbe ein.
    Wirkt auf Widgets, die danach erstellt werden (die App baut ihre Oberfläche dafür neu auf)."""
    global _accent
    mode = settings.get("appearance_mode", "dark")
    ctk.set_appearance_mode(mode if mode in ("dark", "light", "system") else "dark")
    acc = settings.get("accent", DEFAULT_ACCENT)
    _accent = acc if isinstance(acc, str) and HEX_RE.match(acc) else DEFAULT_ACCENT
    hover = shade(_accent, 0.82)
    patches = {
        "CTkButton": {"fg_color": _accent, "hover_color": hover},
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
