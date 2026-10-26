"""Erzeugt dist/modlauncher-source-<version>.zip und dist/version.json.

Aufruf:
    python tools/make_release.py --base-url https://example.com/modlauncher --notes "Neu: ..."

Danach beide Dateien aus dist/ auf den Webserver hochladen. Für Binary-Releases
(EXE etc.) die zusätzlichen Einträge unter "packages" in der version.json von
Hand ergänzen (url + sha256).
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.version import APP_VERSION  # noqa: E402

INCLUDE_DIRS = ["core", "modules"]
INCLUDE_FILES = ["main.py", "requirements.txt"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    zip_name = f"modlauncher-source-{APP_VERSION}.zip"
    zip_path = dist / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in INCLUDE_DIRS:
            for f in sorted((ROOT / d).rglob("*.py")):
                zf.write(f, f.relative_to(ROOT).as_posix())
        for f in INCLUDE_FILES:
            zf.write(ROOT / f, f)

    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    manifest = {
        "version": APP_VERSION,
        "notes": args.notes,
        "packages": {"source": {"url": f"{args.base_url.rstrip('/')}/{zip_name}", "sha256": sha}},
    }
    (dist / "version.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"OK: {zip_path}  sha256={sha}")


if __name__ == "__main__":
    main()
