"""Modul "Add macros": eigene Makros schreiben, prüfen, speichern und ausführen; KI-Generator."""
import re
import threading
import traceback
from pathlib import Path

from core.config import profiles_dir
from core.plugin_api import BasePlugin

from . import dsl

HOTKEY = "<f7>"


class Plugin(BasePlugin):
    id = "macros"
    name = "Add macros"
    icon = "✎"
    version = "1.1.0"
    order = 20
    description = "Write your own macros or let the AI create them from a description. Start/stop with F7."

    def on_load(self):
        self.runner = None
        self.state = "idle"          # idle | running
        self.last = ""
        self.hotkey_error = ""
        self.current_text = ""
        self._listener = None
        self._register_hotkey()

    def on_shutdown(self):
        self.stop()
        if self._listener:
            self._listener.stop()
            self._listener = None

    def create_page(self, parent):
        from .page import MacroPage
        return MacroPage(parent, self)

    # ---- Dateien
    def folder(self) -> Path:
        return profiles_dir(self.id)

    @staticmethod
    def safe_name(name: str) -> str:
        n = re.sub(r"[^\w\- .]", "", name.strip(), flags=re.U).strip(" .")[:60]
        if not n:
            raise ValueError("Please enter a name.")
        return n

    def list_macros(self) -> list[str]:
        return sorted(p.stem for p in self.folder().glob("*.jopm"))

    def save(self, name: str, text: str) -> None:
        dsl.parse(text)                                     # nur gültige Makros speichern
        (self.folder() / f"{self.safe_name(name)}.jopm").write_text(text, encoding="utf-8")

    def load(self, name: str) -> str:
        return (self.folder() / f"{self.safe_name(name)}.jopm").read_text(encoding="utf-8")

    def delete(self, name: str) -> None:
        try:
            (self.folder() / f"{self.safe_name(name)}.jopm").unlink()
        except OSError:
            pass

    # ---- Ausführen
    def run(self, text: str, backend=None) -> str:
        """Gibt '' bei Erfolg oder eine Fehlermeldung zurück."""
        if self.state == "running":
            return ""
        try:
            cmds = dsl.parse(text)
            backend = backend or dsl.PynputBackend()
        except dsl.MacroError as exc:
            return str(exc)
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        self.current_text = text
        self.runner = dsl.Runner(backend)
        self.state, self.last = "running", ""

        def work():
            try:
                self.last = self.runner.run(cmds)
            except Exception as exc:
                traceback.print_exc()
                self.last = f"error: {exc}"
            finally:
                self.state = "idle"

        threading.Thread(target=work, daemon=True).start()
        return ""

    def stop(self):
        if self.runner:
            self.runner.stop()

    def toggle(self):
        if self.state == "running":
            self.stop()
        elif self.current_text:
            self.run(self.current_text)

    def _register_hotkey(self):
        try:
            from pynput import keyboard
            self._listener = keyboard.GlobalHotKeys({HOTKEY: lambda: self.app.call_soon(self.toggle)})
            self._listener.daemon = True
            self._listener.start()
        except Exception as exc:
            self.hotkey_error = str(exc)
