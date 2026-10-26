# ModLauncher

**Download (Windows):** https://github.com/jrn1401/modlauncher-downloads/releases/latest/download/ModLauncher.exe

# ModLauncher

Modularer Desktop-Launcher (Python · CustomTkinter · pynput) mit Auto-Update.
Erstes Modul: **Jaron Op Makro** (Auto-Clicker & Keyer).

**Windows, ohne Kommandozeile:** `START.bat` doppelklicken (installiert beim ersten Mal alles
Nötige und startet den Launcher). `EXE_BAUEN.bat` doppelklicken, um eine `ModLauncher.exe`
zu erzeugen. Voraussetzung: Python 3.10+ ist installiert (beim Installer "Add Python to PATH" anhaken).

## Starten

```bash
pip install -r requirements.txt
python main.py
```

Python 3.10+ wird benötigt. Unter macOS müssen Terminal bzw. die App in
*Systemeinstellungen → Datenschutz → Bedienungshilfen* und *Eingabeüberwachung*
freigegeben werden, sonst funktionieren Tastensimulation und globale Hotkeys nicht.
Unter Linux funktioniert pynput nur mit X11, nicht unter reinem Wayland.

## Projektstruktur

```
main.py                      Einstieg
core/app.py                  Fenster, Seitenleiste, Dashboard, Update-Dialog
core/plugin_api.py           BasePlugin (Schnittstelle für Module)
core/plugin_manager.py       findet modules/<name>/plugin.py automatisch
core/updater.py              Auto-Update (version.json, SHA-256, Installation)
core/config.py               Pfade, Einstellungen, Profile
modules/autoclicker/         erstes Modul (engine, keys, plugin, page)
tools/make_release.py        erzeugt Update-ZIP + version.json
```

## Neues Modul hinzufügen

1. Ordner `modules/mein_tool/` mit leerer `__init__.py` anlegen.
2. `modules/mein_tool/plugin.py` mit einer Klasse `Plugin(BasePlugin)`:

```python
import customtkinter as ctk
from core.plugin_api import BasePlugin

class Plugin(BasePlugin):
    id = "mein_tool"
    name = "Mein Tool"
    icon = "★"
    description = "Kurzbeschreibung fürs Dashboard"

    def create_page(self, parent):
        page = ctk.CTkFrame(parent)
        ctk.CTkLabel(page, text="Hallo").pack(pady=40)
        return page
```

Beim nächsten Start erscheint es in der Seitenleiste und im Dashboard.
Zustand, Hotkeys und Threads gehören ins Plugin-Objekt (`on_load` / `on_shutdown`),
die Seite ist nur die Ansicht und wird erst beim ersten Öffnen erzeugt.
Aus Hintergrund-Threads die UI immer über `self.app.call_soon(fn, ...)` ansprechen.

## Auto-Update einrichten

1. In `core/version.py` die `UPDATE_MANIFEST_URL` auf deinen Server setzen.
2. Version in `core/version.py` erhöhen und ein Release bauen:
   ```bash
   python tools/make_release.py --base-url https://deine-domain.de/modlauncher --notes "Was neu ist"
   ```
3. `dist/version.json` und das ZIP in `dist/` auf den Server hochladen.

Beim Start prüft der Launcher die `version.json`. Ist die Version höher, erscheint ein
Dialog; das Paket wird heruntergeladen, per SHA-256 geprüft und installiert.

- Quellcode-Betrieb: ZIP wird über den Programmordner entpackt, Launcher startet neu.
- Windows-EXE: eine Hilfsdatei ersetzt die EXE und startet sie neu. Dafür einen
  `windows`-Eintrag unter `packages` in der `version.json` ergänzen (url + sha256).
- macOS/Linux-Binary: Die Datei wird heruntergeladen und der Ordner geöffnet; der
  Austausch erfolgt manuell.

Die `version.json` sollte nur über HTTPS und von einem Server ausgeliefert werden, dem du
vertraust. Wer sie ändern kann, kann Code auf den Rechnern deiner Nutzer ausführen.
Für den produktiven Einsatz empfiehlt sich zusätzlich eine Signaturprüfung.

## Als Programm bauen (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name ModLauncher \
  --collect-all customtkinter --collect-submodules modules \
  --collect-submodules pynput main.py
```

Jeweils auf dem Zielsystem bauen (Windows → .exe, macOS → .app). Neue Module
liegen dann in der Binary; für sie ist ein neuer Build nötig.

## Auto-Clicker: Profile

Profile sind JSON-Dateien (Standardordner: `<Config-Ordner>/ModLauncher/profiles/autoclicker`).
Der zuletzt verwendete Zustand wird beim Beenden gespeichert und beim Start geladen.

```json
{
  "name": "Standard",
  "target": "key:e",
  "interval": {"ms": 100, "s": 0, "min": 0},
  "repeat_mode": "count",
  "repeat_count": 10,
  "timer_enabled": true,
  "timer_value": 5,
  "timer_unit": "min",
  "start_delay": 3,
  "hotkey_start": "<f6>",
  "hotkey_stop": "<f6>"
}
```

`target`: `mouse:left|right|middle` oder `key:<name>` (Buchstabe, Ziffer, `space`, `enter`, `f5` ...).
Hotkeys im pynput-Format, z. B. `<ctrl>+<alt>+p`. Sind Start und Stop gleich, schaltet die Taste um.

## Updates für alle Nutzer (Windows-EXE)

Einmalig:
1. Entscheide, wo die Downloads liegen (eigener Webspace oder GitHub Releases) und trage in
   `core/version.py` die Adresse der `version.json` ein, z. B. `https://deine-domain.de/modlauncher/version.json`.
2. `EXE_BAUEN.bat` ausführen und die fertige `dist\ModLauncher.exe` an deine Nutzer verteilen.
   Diese erste Version müssen sie einmal selbst herunterladen.

Für jedes Update:
1. `APP_VERSION` in `core/version.py` erhöhen (z. B. 1.0.0 -> 1.1.0).
2. `EXE_BAUEN.bat` ausführen.
3. `RELEASE.bat` ausführen (erzeugt `dist\version.json`; die Basis-Adresse wird beim ersten Mal abgefragt).
4. `dist\ModLauncher.exe` und `dist\version.json` hochladen und die alten Dateien ersetzen.

Beim nächsten Start sehen deine Nutzer einen Update-Dialog und klicken einmal auf "Jetzt aktualisieren".
