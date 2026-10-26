"""Modul "Browsing / Extensions"."""
from core import config
from core.plugin_api import BasePlugin

from .catalog import Store


class Plugin(BasePlugin):
    id = "extensions"
    name = "Browsing / Extensions"
    icon = "🧩"
    version = "1.1.0"
    order = 30
    description = "Ready-made extensions: add, switch on and configure them with one click."

    def store(self) -> Store:
        return Store(self.app.settings, lambda: config.save_settings(self.app.settings))

    def create_page(self, parent):
        from .page import ExtensionsPage
        return ExtensionsPage(parent, self)

    def dashboard_summary(self):
        from core.i18n import tr
        n = sum(1 for v in self.app.settings.get("extensions", {}).values() if v.get("enabled"))
        return tr(self.description) + (f"  ({n})" if n else "")
