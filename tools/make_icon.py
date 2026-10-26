"""Erzeugt das Standard-Icon (build/icon.ico) für den EXE-Build. Nutzt dieselbe Zeichenfunktion wie der Icon-Wechsler."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import appicon  # noqa: E402

out = ROOT / "build"
out.mkdir(exist_ok=True)
img = appicon.render(256, "#4f8cff", None)
img.save(out / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save(out / "icon.png")
print("icon geschrieben:", out / "icon.ico")
