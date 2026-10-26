"""Pfade und persistente Launcher-Einstellungen."""
import json
import os
import sys
from pathlib import Path

from core.version import APP_ID

DEFAULT_SETTINGS = {
    "appearance_mode": "dark",     # dark | light | system
    "accent": "#4f8cff",
    "dl_limit_kbps": 0,            # 0 = unbegrenzt
    "cpu_priority": "normal",      # normal | low
    "cpu_cores": 0,                # 0 = alle
    "ram_limit_mb": 0,             # 0 = kein Limit (nur Windows)
    "assistant_url": "",
    "contact_endpoint": "",
    # --- v1.1 ---
    "language": "en",              # en | de | es | ru | fr | zh
    "colors": {},                  # eigene Farben: main, sidebar, card, inset, hover, text
    "icon_bg": "#4f8cff",          # Hintergrundfarbe des App-Icons
    "icon_image": "",              # optionales Hintergrundbild des App-Icons
    "remember": "30",              # Standard für "Angemeldet bleiben": 0 | 1 | 7 | 30 | forever
    "first_run_done": False,       # Sprache/Verknüpfung/Autostart-Angebot gezeigt
    "legal_version": "",           # Fassung der Bedingungen, der zugestimmt wurde
    "legal_hash": "",
    "legal_accepted_at": 0,
    "recoil_ack": False,           # Warnhinweis im Recoil-Modul bestätigt
    "extensions": {},              # {id: {"enabled": bool, "config": {...}}}
}


def app_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def profiles_dir(module_id: str) -> Path:
    d = app_dir() / "profiles" / module_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, data) -> None:
    """Atomar schreiben: erst Temp-Datei, dann ersetzen (kein halb geschriebenes JSON bei Absturz)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_settings() -> dict:
    data = load_json(app_dir() / "settings.json", {}) or {}
    merged = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        merged.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    return merged


def save_settings(data: dict) -> None:
    save_json(app_dir() / "settings.json", {k: data[k] for k in DEFAULT_SETTINGS if k in data})
