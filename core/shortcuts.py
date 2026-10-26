"""Desktop-Verknüpfung und Autostart (Windows, Linux, macOS)."""
import os
import subprocess
import sys
from pathlib import Path

from core.version import APP_ID, APP_NAME

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
FROZEN = getattr(sys, "frozen", False)
MAIN_PY = Path(__file__).resolve().parent.parent / "main.py"


def command() -> list[str]:
    """Der Befehl, mit dem sich die App starten lässt (EXE oder python main.py)."""
    if FROZEN:
        return [sys.executable]
    exe = sys.executable
    if IS_WIN and exe.lower().endswith("python.exe"):          # ohne Konsolenfenster starten
        pyw = exe[:-10] + "pythonw.exe"
        if os.path.exists(pyw):
            exe = pyw
    return [exe, str(MAIN_PY)]


def _quote_win(args: list[str]) -> str:
    return " ".join(f'"{a}"' for a in args)


def _desktop_dir() -> Path:
    if IS_WIN:
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                                 capture_output=True, text=True, timeout=15, creationflags=0x08000000)
            if out.stdout.strip():
                return Path(out.stdout.strip())
        except Exception:
            pass
        return Path.home() / "Desktop"
    try:
        out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except Exception:
        pass
    return Path.home() / "Desktop"


def _desktop_entry(args: list[str]) -> str:
    exec_line = " ".join('"' + a.replace('"', '\\"') + '"' for a in args)
    return ("[Desktop Entry]\nType=Application\nVersion=1.0\n"
            f"Name={APP_NAME}\nComment={APP_NAME}\nExec={exec_line}\nTerminal=false\nCategories=Utility;\n")


# ---------------------------------------------------------------- Desktop-Verknüpfung
def desktop_shortcut_path() -> Path:
    d = _desktop_dir()
    return d / (f"{APP_NAME}.lnk" if IS_WIN else f"{APP_ID}.desktop" if not IS_MAC else APP_ID)


def has_desktop_shortcut() -> bool:
    return desktop_shortcut_path().exists()


def create_desktop_shortcut() -> Path:
    args = command()
    target = desktop_shortcut_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if IS_WIN:
        icon = args[0] if FROZEN else ""
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{exe}';"
              "$s.Arguments='{arg}';$s.WorkingDirectory='{wd}';{icon}$s.Save()").format(
            lnk=str(target).replace("'", "''"), exe=args[0].replace("'", "''"),
            arg=(" ".join(f'"{a}"' for a in args[1:])).replace("'", "''"),
            wd=str(Path(args[0]).parent).replace("'", "''"),
            icon=f"$s.IconLocation='{icon},0';".replace("\\", "\\") if icon else "")
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=30, creationflags=0x08000000)
        if res.returncode != 0:
            raise OSError(res.stderr.strip() or "PowerShell failed")
    elif IS_MAC:
        if target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(args[0])
    else:
        target.write_text(_desktop_entry(args), encoding="utf-8")
        target.chmod(0o755)
    return target


def remove_desktop_shortcut() -> None:
    try:
        desktop_shortcut_path().unlink()
    except OSError:
        pass


# ---------------------------------------------------------------- Autostart
def _linux_autostart() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "autostart" / f"{APP_ID}.desktop"


def _mac_agent() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"app.{APP_ID.lower()}.plist"


def is_autostart() -> bool:
    if IS_WIN:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                winreg.QueryValueEx(k, APP_ID)
                return True
        except OSError:
            return False
    return (_mac_agent() if IS_MAC else _linux_autostart()).exists()


def set_autostart(enabled: bool) -> None:
    args = command()
    if IS_WIN:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                            winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, _quote_win(args))
            else:
                try:
                    winreg.DeleteValue(k, APP_ID)
                except FileNotFoundError:
                    pass
        return
    path = _mac_agent() if IS_MAC else _linux_autostart()
    if not enabled:
        try:
            path.unlink()
        except OSError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if IS_MAC:
        items = "".join(f"<string>{a}</string>" for a in args)
        path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>'
                        f"<key>Label</key><string>app.{APP_ID.lower()}</string>"
                        f"<key>ProgramArguments</key><array>{items}</array>"
                        "<key>RunAtLoad</key><true/></dict></plist>\n", encoding="utf-8")
    else:
        path.write_text(_desktop_entry(args), encoding="utf-8")
