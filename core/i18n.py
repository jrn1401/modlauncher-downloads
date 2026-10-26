"""Mehrsprachigkeit: Quelltexte sind Englisch, Übersetzungen liegen in core/lang/<code>.py.

tr("Settings")                       -> "Einstellungen" (bei Deutsch)
tr("Welcome, {name}!", name="Jaron") -> mit Platzhalter-Ersetzung
Fehlt eine Übersetzung, wird der englische Text angezeigt.
"""
LANGS = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "ru": "Русский",
    "fr": "Français",
    "zh": "中文 (简体)",
}
DEFAULT_LANG = "en"
_current = DEFAULT_LANG
_table: dict = {}


def _load(code: str) -> dict:
    # Statische Imports, damit PyInstaller die Sprachdateien sicher einpackt.
    if code == "de":
        from core.lang import de as m
    elif code == "es":
        from core.lang import es as m
    elif code == "ru":
        from core.lang import ru as m
    elif code == "fr":
        from core.lang import fr as m
    elif code == "zh":
        from core.lang import zh as m
    else:
        return {}
    return m.T


def set_language(code: str) -> str:
    global _current, _table
    _current = code if code in LANGS else DEFAULT_LANG
    _table = _load(_current)
    return _current


def get_language() -> str:
    return _current


def tr(text: str, **kw) -> str:
    out = _table.get(text, text)
    if kw:
        try:
            out = out.format(**kw)
        except (KeyError, IndexError, ValueError):
            out = text.format(**kw) if "{" in text else text
    return out
