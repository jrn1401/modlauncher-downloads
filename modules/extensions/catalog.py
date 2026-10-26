"""Vorgegebene Erweiterungen (lokal, ohne Netzwerkzugriff beim Start) und ihre Zustandsverwaltung."""
import re
import urllib.parse

from core.i18n import tr

SEARCH_ENGINES = {
    "DuckDuckGo": "https://duckduckgo.com/?q={q}",
    "Google": "https://www.google.com/search?q={q}",
    "Bing": "https://www.bing.com/search?q={q}",
    "Ecosia": "https://www.ecosia.org/search?q={q}",
    "Startpage": "https://www.startpage.com/do/search?q={q}",
}

CATALOG = [
    {"id": "quicklinks", "name": "Quick links", "icon": "🔗",
     "desc": "Your favourite websites one click away. Opens in your normal browser.",
     "config": {"links": [["Google", "https://www.google.com"], ["YouTube", "https://www.youtube.com"],
                          ["GitHub", "https://github.com"]]}},
    {"id": "websearch", "name": "Web search", "icon": "🔎",
     "desc": "Search the web from the launcher with the search engine of your choice.",
     "config": {"engine": "DuckDuckGo"}},
    {"id": "notes", "name": "Notes", "icon": "🗒",
     "desc": "A small notepad that is saved automatically (stays on this computer).",
     "config": {"text": ""}},
]
BY_ID = {e["id"]: e for e in CATALOG}


def safe_url(url: str) -> str:
    """Nur http(s)-Adressen mit Host. Gibt die bereinigte Adresse zurück oder wirft ValueError."""
    url = (url or "").strip()
    bad = ValueError(tr("Please enter a valid web address (http or https)."))
    if "://" not in url:
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:(?!\d+(/|$))", url):      # javascript:, mailto:, data: ...
            raise bad
        url = "https://" + url
    try:
        p = urllib.parse.urlparse(url)
        p.port                                                          # prüft die Portangabe
    except ValueError:
        raise bad from None
    if p.scheme not in ("http", "https") or not p.hostname or any(c.isspace() for c in url):
        raise bad
    return url


def search_url(engine: str, query: str) -> str:
    tpl = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["DuckDuckGo"])
    return tpl.replace("{q}", urllib.parse.quote_plus(query.strip()))


class Store:
    """Arbeitet auf settings['extensions'] = {id: {"enabled": bool, "config": {...}}}; save() speichert."""

    def __init__(self, settings: dict, save):
        self.settings, self._save = settings, save
        if not isinstance(settings.get("extensions"), dict):
            settings["extensions"] = {}

    @property
    def data(self) -> dict:
        return self.settings["extensions"]

    def added(self, ext_id: str) -> bool:
        return ext_id in self.data

    def enabled(self, ext_id: str) -> bool:
        return bool(self.data.get(ext_id, {}).get("enabled"))

    def config(self, ext_id: str) -> dict:
        base = dict(BY_ID[ext_id]["config"])
        cfg = self.data.get(ext_id, {}).get("config")
        if isinstance(cfg, dict):
            base.update(cfg)
        return base

    def add(self, ext_id: str) -> None:
        if ext_id not in BY_ID:
            raise ValueError("unknown extension")
        self.data.setdefault(ext_id, {"enabled": True, "config": {}})
        self._save()

    def remove(self, ext_id: str) -> None:
        self.data.pop(ext_id, None)
        self._save()

    def set_enabled(self, ext_id: str, on: bool) -> None:
        if ext_id in self.data:
            self.data[ext_id]["enabled"] = bool(on)
            self._save()

    def set_config(self, ext_id: str, **values) -> None:
        if ext_id not in self.data:
            raise ValueError("not added")
        cfg = self.data[ext_id].setdefault("config", {})
        if ext_id == "quicklinks" and "links" in values:
            links = []
            for item in values["links"][:20]:
                name, url = str(item[0]).strip()[:30], safe_url(item[1])
                links.append([name or urllib.parse.urlparse(url).hostname, url])
            values["links"] = links
        if ext_id == "websearch" and values.get("engine") not in SEARCH_ENGINES:
            raise ValueError("unknown search engine")
        if ext_id == "notes" and "text" in values:
            values["text"] = str(values["text"])[:20000]
        cfg.update(values)
        self._save()
