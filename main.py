"""Einstiegspunkt des ModLaunchers."""
import datetime
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _report_crash(text: str) -> None:
    """Schreibt Startfehler in crash.log und zeigt sie an (die EXE hat keine Konsole)."""
    log = None
    try:
        from core.config import app_dir
        log = app_dir() / "crash.log"
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} | Python {sys.version.split()[0]} "
                     f"| {sys.platform} ===\n{text}\n")
    except Exception:
        pass
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(
            "Jaron's OP Makro – startup error",
            f"The launcher could not start:\n\n{text[-1500:]}\n\nLog file: {log}")
        root.destroy()
    except Exception:
        pass


def _selftest(out: str) -> int:
    """Lädt alle Module und Kernteile und schreibt das Ergebnis in eine Datei (für CI und Fehlersuche)."""
    import importlib
    lines, bad = [], 0
    names = ["pynput.keyboard", "pynput.mouse", "customtkinter", "PIL.Image", "core.cloud", "core.oauth_loopback",
             "core.identity", "core.updater", "core.shortcuts", "core.appicon", "core.legal_text"]
    import modules
    from core import plugin_manager
    names += [f"modules.{n}.plugin" for n in plugin_manager._module_names()]
    for n in names:
        try:
            importlib.import_module(n)
            lines.append(f"ok    {n}")
        except BaseException:
            bad += 1
            lines.append(f"FAIL  {n}\n{traceback.format_exc()}")
    from core.version import APP_VERSION
    lines.append(f"version {APP_VERSION} platform {sys.platform} frozen {getattr(sys, 'frozen', False)}")
    Path(out).write_text("\n".join(lines), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        sys.exit(_selftest(sys.argv[2]))
    try:
        from core.app import LauncherApp
        LauncherApp().mainloop()
    except Exception:
        _report_crash(traceback.format_exc())
        sys.exit(1)
