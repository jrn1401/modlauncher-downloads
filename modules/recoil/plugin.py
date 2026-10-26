"""Modul "Recoil": universeller Rückstoß-Ausgleich mit deutlicher Warnung."""
import traceback

from core import config
from core.plugin_api import BasePlugin

from .engine import PRESETS, RecoilConfig, RecoilEngine

HOTKEY = "<f8>"
WARNING = ("WARNING: This tool can very easily be detected by modern anti-cheat systems. "
           "Use is expressly recommended only in offline games for educational and testing purposes!")


class PynputBackend:
    def __init__(self):
        from pynput import mouse
        self.ms = mouse.Controller()

    def move_relative(self, dx, dy):
        self.ms.move(dx, dy)


class Plugin(BasePlugin):
    id = "recoil"
    name = "Recoil"
    icon = "⌖"
    version = "1.1.0"
    order = 40
    description = "Universal anti-recoil: pulls the mouse down while the left button is held. Offline games only!"

    def on_load(self):
        self.engine = None
        self.error = ""
        self._mouse_listener = None
        self._hk = None
        self.cfg = RecoilConfig.from_dict(self._saved().get("cfg"))
        try:
            from pynput import keyboard
            self._hk = keyboard.GlobalHotKeys({HOTKEY: lambda: self.app.call_soon(self.toggle)})
            self._hk.daemon = True
            self._hk.start()
        except Exception as exc:
            self.error = str(exc)

    def _saved(self) -> dict:
        d = config.load_json(config.app_dir() / "recoil.json", {})
        return d if isinstance(d, dict) else {}

    def save_cfg(self) -> None:
        config.save_json(config.app_dir() / "recoil.json", {"cfg": self.cfg.__dict__})

    def preset(self, name: str) -> None:
        if name in PRESETS:
            self.cfg = RecoilConfig.from_dict(PRESETS[name])
            self._apply()

    def update(self, **values) -> None:
        for k, v in values.items():
            setattr(self.cfg, k, type(getattr(self.cfg, k))(v))
        self.cfg.clamp()
        self._apply()

    def _apply(self):
        if self.engine:
            self.engine.cfg = self.cfg
        self.save_cfg()

    @property
    def enabled(self) -> bool:
        return bool(self.engine and self.engine.enabled)

    def acknowledged(self) -> bool:
        return bool(self.app.settings.get("recoil_ack"))

    def acknowledge(self, yes: bool) -> None:
        self.app.settings["recoil_ack"] = bool(yes)
        config.save_settings(self.app.settings)
        if not yes:
            self.set_enabled(False)

    def set_enabled(self, on: bool) -> str:
        """Gibt '' oder eine Fehlermeldung zurück. Ohne Bestätigung des Warnhinweises bleibt das Modul aus."""
        if not on:
            if self.engine:
                self.engine.enabled = False
            self._stop_listener()
            return ""
        if not self.acknowledged():
            return "Please confirm the warning first."
        try:
            if self.engine is None:
                self.engine = RecoilEngine(PynputBackend(), self.cfg)
                self.engine.start()
            from pynput import mouse
            if self._mouse_listener is None:
                self._mouse_listener = mouse.Listener(on_click=self._on_click)
                self._mouse_listener.daemon = True
                self._mouse_listener.start()
            self.engine.enabled = True
        except Exception as exc:
            traceback.print_exc()
            return f"{type(exc).__name__}: {exc}"
        return ""

    def toggle(self):
        self.set_enabled(not self.enabled)
        page = self.app.pages.get(self.id)
        if page is not None and page.winfo_exists():
            page.refresh()

    def _on_click(self, x, y, button, pressed):
        if self.engine and str(button) == "Button.left":
            self.engine.set_pressed(pressed)

    def _stop_listener(self):
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self.engine:
            self.engine.set_pressed(False)

    def on_shutdown(self):
        self._stop_listener()
        if self.engine:
            self.engine.shutdown()
        if self._hk:
            self._hk.stop()

    def create_page(self, parent):
        from .page import RecoilPage
        return RecoilPage(parent, self)
