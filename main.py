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


if __name__ == "__main__":
    try:
        from core.app import LauncherApp
        LauncherApp().mainloop()
    except Exception:
        _report_crash(traceback.format_exc())
        sys.exit(1)
