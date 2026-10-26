"""Auto-Update über eine version.json auf einem Webserver.

Format der version.json:
{
  "version": "1.1.0",
  "notes": "Was ist neu ...",
  "packages": {
    "source":  {"url": "https://.../modlauncher-source-1.1.0.zip", "sha256": "..."},
    "windows": {"url": "https://.../ModLauncher.exe",             "sha256": "..."},
    "macos":   {"url": "https://.../ModLauncher-mac.zip",         "sha256": "..."},
    "linux":   {"url": "https://.../ModLauncher-linux",           "sha256": "..."}
  }
}

- Läuft der Launcher aus dem Quellcode ("source"), wird das ZIP über den
  Programmordner entpackt und der Launcher neu gestartet.
- Läuft er als PyInstaller-Binary, wird unter Windows die EXE per Hilfsskript
  ausgetauscht. Unter macOS/Linux wird die heruntergeladene Datei geöffnet
  (manuelle Installation).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path

from core.version import APP_ID, APP_VERSION, UPDATE_MANIFEST_URL

FROZEN = getattr(sys, "frozen", False)
APP_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class UpdateInfo:
    version: str
    notes: str
    url: str
    sha256: str


def parse_version(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def platform_key() -> str:
    if not FROZEN:
        return "source"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _open(url: str, timeout: float = 10):
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_ID}/{APP_VERSION}"})
    return urllib.request.urlopen(req, timeout=timeout)


def check() -> UpdateInfo | None:
    """Gibt UpdateInfo zurück, wenn eine neuere Version existiert, sonst None."""
    with _open(UPDATE_MANIFEST_URL) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if parse_version(data["version"]) <= parse_version(APP_VERSION):
        return None
    pkg = data.get("packages", {}).get(platform_key())
    if not pkg:
        raise RuntimeError(f"Kein Update-Paket für '{platform_key()}' in der version.json")
    return UpdateInfo(data["version"], data.get("notes", ""), pkg["url"], pkg.get("sha256", ""))


def download(info: UpdateInfo, progress=None, max_kbps: float = 0) -> Path:
    """Lädt das Paket herunter (optional gedrosselt auf max_kbps KB/s) und prüft die SHA-256-Summe."""
    tmp = Path(tempfile.mkdtemp(prefix="launcher_update_"))
    target = tmp / (info.url.rsplit("/", 1)[-1] or "update.bin")
    sha = hashlib.sha256()
    limit = max(0.0, float(max_kbps or 0)) * 1024      # Bytes pro Sekunde, 0 = unbegrenzt
    with _open(info.url, timeout=30) as resp, open(target, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        t0 = time.monotonic()
        chunk_size = 8 * 1024 if 0 < limit < 256 * 1024 else 64 * 1024
        while chunk := resp.read(chunk_size):
            fh.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if limit:
                ahead = done / limit - (time.monotonic() - t0)
                if ahead > 0:
                    time.sleep(ahead)
            if progress and total:
                progress(done / total)
    if info.sha256 and sha.hexdigest().lower() != info.sha256.lower():
        target.unlink(missing_ok=True)
        raise RuntimeError("Prüfsumme stimmt nicht – Update abgebrochen.")
    return target


def _apply_source_zip(path: Path) -> None:
    root = APP_ROOT.resolve()
    with zipfile.ZipFile(path) as zf:
        for member in zf.namelist():
            dest = (root / member).resolve()
            if root not in dest.parents and dest != root:
                raise RuntimeError(f"Unsicherer Pfad im Update-Archiv: {member}")
        zf.extractall(root)


def _apply_windows_exe(path: Path) -> None:
    exe = Path(sys.executable)
    bat = path.parent / "update.bat"
    bat.write_text(
        "@echo off\r\n"
        "set /a n=0\r\n"
        ":retry\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        f'move /y "{path}" "{exe}" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "  set /a n+=1\r\n"
        "  if %n% lss 30 goto retry\r\n"
        "  exit /b 1\r\n"
        ")\r\n"
        f'start "" "{exe}"\r\n'
        'del "%~f0"\r\n',
        encoding="utf-8",
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags, close_fds=True)


def apply(path: Path) -> bool:
    """Installiert das Update. True = Launcher muss sich jetzt beenden/neu starten."""
    key = platform_key()
    if key == "source":
        _apply_source_zip(path)
        subprocess.Popen([sys.executable, *sys.argv], cwd=str(APP_ROOT))
        return True
    if key == "windows":
        _apply_windows_exe(path)
        return True
    # macOS / Linux: Datei im Dateimanager öffnen, Nutzer ersetzt sie manuell
    webbrowser.open(path.parent.as_uri())
    return False
