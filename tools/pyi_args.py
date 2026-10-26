"""Gibt die PyInstaller-Argumente für alle eingebauten Module aus (aus modules/__init__.py).
Grund: --collect-submodules findet die Plugins in der gebauten Datei nicht zuverlässig; ohne diese Zeilen
fehlen die Module ("No module named 'modules.autoclicker'")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import modules  # noqa: E402

args = ["--paths", "."]
for name in modules.BUILTIN_MODULES:
    args += ["--hidden-import", f"modules.{name}.plugin", "--collect-submodules", f"modules.{name}"]
args += ["--hidden-import", "modules", "--collect-submodules", "core"]
print(" ".join(args))
