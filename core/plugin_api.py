"""Basisklasse für alle Launcher-Module (Plugins).

Ein Modul ist ein Paket unter modules/<name>/ mit einer plugin.py, die eine
Klasse `Plugin(BasePlugin)` exportiert. Der Launcher findet es automatisch.

Wichtig: Der Zustand (Engine, Hotkeys, Profil) gehört ins Plugin-Objekt, nicht
in die Seite. Seiten werden erst beim ersten Öffnen erzeugt, Hotkeys sollen
aber ab Programmstart funktionieren.
"""


class BasePlugin:
    id = "base"
    name = "Base"
    icon = "•"
    version = "1.0.0"
    description = ""
    order = 100  # Reihenfolge in der Seitenleiste

    def __init__(self, app):
        self.app = app

    def on_load(self) -> None:
        """Beim Programmstart (Hotkeys registrieren, Profile laden ...)."""

    def create_page(self, parent):
        """Gibt ein CTk-Widget (Seite) zurück, das in `parent` gelegt wird."""
        raise NotImplementedError

    def on_shutdown(self) -> None:
        """Beim Beenden (Threads stoppen, Zustand speichern)."""

    def dashboard_summary(self) -> str:
        return self.description
