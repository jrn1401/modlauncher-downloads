"""Findet und lädt Module aus dem Paket `modules`."""
import importlib
import pkgutil
import traceback


def _module_names() -> list[str]:
    import modules

    names = list(getattr(modules, "BUILTIN_MODULES", []))
    try:  # automatische Suche (funktioniert im Quellcode-Betrieb zuverlässig)
        for info in pkgutil.iter_modules(modules.__path__):
            if info.ispkg and info.name not in names:
                names.append(info.name)
    except Exception:
        traceback.print_exc()
    return names


def discover(app):
    """Gibt (plugins, failed) zurück. failed = [(modulname, fehlertext)]."""
    plugins, failed = [], []
    for name in _module_names():
        try:
            mod = importlib.import_module(f"modules.{name}.plugin")
            plugins.append(mod.Plugin(app))
        except Exception as exc:  # ein kaputtes Modul darf den Launcher nicht stoppen
            traceback.print_exc()
            failed.append((name, f"{type(exc).__name__}: {exc}"))
    plugins.sort(key=lambda p: (p.order, p.name))
    return plugins, failed
