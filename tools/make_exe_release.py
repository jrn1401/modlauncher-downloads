"""Erzeugt dist/version.json für das Auto-Update der Windows-EXE.

Ablauf (macht RELEASE.bat für dich):
  1. EXE_BAUEN.bat ausführen  -> dist/ModLauncher.exe
  2. RELEASE.bat ausführen    -> dist/version.json (mit Prüfsumme)
  3. BEIDE Dateien aus dist/ auf den Server / in das GitHub-Release hochladen.

Die Basis-Adresse wird beim ersten Mal abgefragt und in release_config.json gemerkt.
Sie ist der Ordner, in dem ModLauncher.exe und version.json später liegen, z. B.
  https://deine-domain.de/modlauncher
  https://github.com/NAME/REPO/releases/latest/download
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.version import APP_VERSION, UPDATE_MANIFEST_URL  # noqa: E402

from core.version import APP_ID  # noqa: E402

EXE_NAME = f"{APP_ID}.exe"


def main() -> int:
    exe = ROOT / "dist" / EXE_NAME
    if not exe.exists():
        print(f"Fehler: {exe} nicht gefunden. Bitte zuerst EXE_BAUEN.bat ausführen.")
        return 1

    cfg_path = ROOT / "release_config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except ValueError:
            cfg = {}
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url", nargs="?", default="")
    ap.add_argument("--notes", default=None, help="Release-Notes (sonst wird gefragt)")
    args = ap.parse_args()
    base = (args.base_url or cfg.get("base_url", "")).strip()
    if not base:
        base = input("Basis-Adresse der Downloads (ohne / am Ende): ").strip()
    base = base.rstrip("/")
    if not base.startswith("https://"):
        print("Fehler: Die Adresse muss mit https:// beginnen.")
        return 1
    cfg["base_url"] = base
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    notes = args.notes if args.notes is not None else input(
        f"Was ist neu in Version {APP_VERSION}? (Enter = leer): ").strip()
    sha = hashlib.sha256(exe.read_bytes()).hexdigest()
    manifest = {
        "version": APP_VERSION,
        "notes": notes,
        "packages": {"windows": {"url": f"{base}/{EXE_NAME}", "sha256": sha}},
    }
    out = ROOT / "dist" / "version.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"Fertig: Version {APP_VERSION}")
    print(f"  {exe}")
    print(f"  {out}")
    print("Lade BEIDE Dateien hoch, damit sie unter diesen Adressen erreichbar sind:")
    print(f"  {base}/{EXE_NAME}")
    print(f"  {base}/version.json")
    expected = f"{base}/version.json"
    if UPDATE_MANIFEST_URL != expected:
        print()
        print("ACHTUNG: In core/version.py steht UPDATE_MANIFEST_URL =")
        print(f"  {UPDATE_MANIFEST_URL}")
        print(f"Sie muss {expected} sein, sonst findet die EXE keine Updates.")
        print("Nach der Änderung EXE_BAUEN.bat erneut ausführen und neu verteilen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
