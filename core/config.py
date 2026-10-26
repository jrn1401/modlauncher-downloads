"""Pfade und persistente Launcher-Einstellungen."""
import json
import os
import sys
from pathlib import Path

from core.version import APP_NAME


def app_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_NAME
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
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_settings() -> dict:
    return load_json(app_dir() / "settings.json", {}) or {}


def save_settings(data: dict) -> None:
    save_json(app_dir() / "settings.json", data)
