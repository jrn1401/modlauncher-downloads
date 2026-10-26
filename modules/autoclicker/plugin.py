"""Auto-Clicker & Keyer: Plugin-Objekt (Zustand, Hotkeys, Engine).

Die Seite (page.py) ist nur eine Ansicht. Hotkeys und Engine leben hier und
funktionieren daher auch, bevor die Seite je geöffnet wurde.
"""
import copy
import traceback
from pathlib import Path

from core.config import app_dir, load_json, profiles_dir, save_json
from core.plugin_api import BasePlugin

from . import keys
from .engine import ClickEngine, EngineConfig

DEFAULT_PROFILE = {
    "name": "Standard",
    "target": "mouse:left",
    "interval": {"ms": 100, "s": 0, "min": 0},
    "repeat_mode": "infinite",      # "infinite" | "count"
    "repeat_count": 10,
    "timer_enabled": False,
    "timer_value": 5,
    "timer_unit": "min",            # "s" | "min" | "h"
    "start_delay": 0,
    "hotkey_start": "<f6>",
    "hotkey_stop": "<f6>",          # gleich wie Start = Umschalten (Toggle)
}
UNIT_SECONDS = {"s": 1, "min": 60, "h": 3600}


def merge_profile(data: dict | None) -> dict:
    """Füllt fehlende Felder mit Defaults (robust gegen alte/handgeschriebene Dateien)."""
    prof = copy.deepcopy(DEFAULT_PROFILE)
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "interval" and isinstance(v, dict):
                prof["interval"].update(v)
            elif k in prof:
                prof[k] = v
    return prof


def build_config(profile: dict) -> EngineConfig:
    """Validiert ein Profil und baut daraus die Engine-Konfiguration. Wirft ValueError."""
    keys.validate_target(profile["target"])
    iv = profile["interval"]
    try:
        interval = (float(iv["ms"]) / 1000.0 + float(iv["s"]) + float(iv["min"]) * 60.0)
        count = int(profile["repeat_count"])
        timer_val = float(profile["timer_value"])
        delay = float(profile["start_delay"])
    except (TypeError, ValueError):
        raise ValueError("Zahlenfeld enthält keinen gültigen Wert") from None
    if interval < 0.001:
        raise ValueError("Intervall muss mindestens 1 ms betragen")
    if min(count, timer_val, delay) < 0:
        raise ValueError("Negative Werte sind nicht erlaubt")
    if profile["repeat_mode"] == "count" and count < 1:
        raise ValueError("Wiederholungen müssen mindestens 1 sein")
    duration = 0.0
    if profile["timer_enabled"]:
        if timer_val <= 0:
            raise ValueError("Timer muss größer als 0 sein")
        duration = timer_val * UNIT_SECONDS.get(profile["timer_unit"], 1)
    return EngineConfig(
        action=keys.make_action(profile["target"]),
        interval_s=interval,
        repeat_count=count if profile["repeat_mode"] == "count" else 0,
        max_duration_s=duration,
        start_delay_s=delay,
    )


class Plugin(BasePlugin):
    id = "autoclicker"
    name = "Jaron Op Makro"
    icon = "◎"
    version = "1.0.0"
    order = 10
    description = ("Simuliert beliebige Maus- und Tastaturtasten mit präzisem Intervall, "
                   "Wiederholungen, Timer und globalen Start/Stop-Hotkeys.")

    def on_load(self):
        self.engine = ClickEngine()
        self.hotkey_error = ""
        self._listener = None
        self._last_file = app_dir() / "autoclicker_last.json"
        self.profile = merge_profile(load_json(self._last_file))
        self._register_hotkeys()

    def on_shutdown(self):
        self.engine.stop()
        self._unregister_hotkeys()
        save_json(self._last_file, self.profile)

    def create_page(self, parent):
        from .page import AutoClickerPage
        return AutoClickerPage(parent, self)

    # ---- Profil ----
    def profiles_dir(self) -> Path:
        return profiles_dir(self.id)

    def set_profile(self, profile: dict) -> None:
        """Übernimmt ein (vom UI validiertes) Profil; registriert Hotkeys bei Änderung neu."""
        old = (self.profile["hotkey_start"], self.profile["hotkey_stop"])
        self.profile = profile
        if old != (profile["hotkey_start"], profile["hotkey_stop"]):
            self._register_hotkeys()

    def save_profile_file(self, path) -> None:
        save_json(path, self.profile)

    def load_profile_file(self, path) -> dict:
        data = load_json(path)
        if not isinstance(data, dict):
            raise ValueError("Datei ist kein gültiges Profil")
        return merge_profile(data)

    # ---- Steuerung ----
    def start(self) -> str:
        """Gibt '' bei Erfolg zurück, sonst eine Fehlermeldung."""
        try:
            cfg = build_config(self.profile)
        except ValueError as exc:
            return str(exc)
        self.engine.start(cfg)
        return ""

    def stop(self):
        self.engine.stop()

    def toggle(self):
        if self.engine.running:
            self.stop()
        else:
            self.start()

    # ---- Globale Hotkeys ----
    def _register_hotkeys(self):
        from pynput import keyboard
        self._unregister_hotkeys()
        self.hotkey_error = ""
        hk_start, hk_stop = self.profile["hotkey_start"], self.profile["hotkey_stop"]
        try:
            keys.validate_hotkey(hk_start)
            keys.validate_hotkey(hk_stop)
            if hk_start == hk_stop:
                mapping = {hk_start: lambda: self.app.call_soon(self.toggle)}
            else:
                mapping = {hk_start: lambda: self.app.call_soon(self.start),
                           hk_stop: lambda: self.app.call_soon(self.stop)}
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.daemon = True
            self._listener.start()
        except Exception as exc:
            traceback.print_exc()
            self.hotkey_error = str(exc)

    def _unregister_hotkeys(self):
        if self._listener:
            self._listener.stop()
            self._listener = None
