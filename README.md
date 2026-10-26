# Jaron's OP Makro

Modularer Desktop-Launcher (Python · CustomTkinter · pynput) mit Konten, Auto-Update und dem
ersten Modul **Jaron Op Makro** (Auto-Clicker & Keyer).

**Download (Windows):** https://github.com/jrn1401/modlauncher-downloads/releases/latest/download/JaronsOPMakro.exe

Windows warnt bei unbekannten Programmen: *Weitere Informationen → Trotzdem ausführen*.

## Funktionen

- Anmeldung mit Benutzername/Passwort, „Angemeldet bleiben“, optional Google, optional 2FA (Authenticator-App)
- Dashboard mit Willkommensnachricht, Update-Prüfung, Modulübersicht
- Einstellungen: Konto (Anzeigename, E-Mail, Passwort, 2FA), Aussehen (Dunkel/Hell/System, Akzentfarbe),
  Leistung (Download-Limit, CPU-Priorität, CPU-Kerne, RAM-Limit unter Windows)
- Hilfe-Assistent (eingebaute FAQ, optional KI über eigenen Server) und Kontaktformular
- Modul „Jaron Op Makro“: jede Maus-/Tastaturtaste, Intervall (min/s/ms), X-mal oder unendlich, Timer,
  globale Start/Stop-Hotkeys, Profile als JSON

## Wichtig zu den Konten

Konten und Passwörter liegen **nur lokal auf dem PC des Nutzers** (`%APPDATA%\JaronsOPMakro\accounts.json`,
Passwörter als PBKDF2-Hash). Es gibt keinen Server, also auch kein „Passwort vergessen“ und keine Daten, die du als
Betreiber einsehen kannst. Ein gemeinsames Konto-System auf einem Server (z. B. Supabase/Firebase) ist bewusst nicht
eingebaut: GitHub eignet sich dafür nicht, weil man dort ohne Schlüssel im Programm nicht schreiben kann, und ein
Schlüssel im Programm würde jedem Nutzer Zugriff auf dein Repository geben.

## Starten (zum Entwickeln)

```bash
pip install -r requirements.txt
python main.py
```
Windows ohne Kommandozeile: `START.bat` doppelklicken. Python 3.11–3.13 empfohlen.
macOS: Terminal/App unter *Systemeinstellungen → Datenschutz* für Bedienungshilfen und Eingabeüberwachung freigeben.
Linux: nur X11 (kein reines Wayland).

## Veröffentlichen und Updates (automatisch über GitHub)

Im Repository liegt `.github/workflows/release.yml`. Es baut die `JaronsOPMakro.exe` auf einem Windows-Server von GitHub.

1. In `core/version.py` die Zahl bei `APP_VERSION` erhöhen (z. B. `1.0.1`).
2. Optional: Neuigkeiten in `RELEASE_NOTES.txt` schreiben.
3. Beide Dateien auf `main` hochladen (per `git push` oder auf github.com über *Add file → Upload files*).
4. GitHub baut automatisch (Reiter *Actions*, dauert einige Minuten) und veröffentlicht `JaronsOPMakro.exe` und
   `version.json` als Release `v<Version>`. Danach sehen alle Nutzer beim Start den Update-Dialog.

Manuell ohne GitHub-Build: `EXE_BAUEN.bat`, dann `RELEASE.bat`, dann beide Dateien aus `dist` an ein Release hängen.

## Google-Anmeldung einrichten (optional)

1. console.cloud.google.com → Projekt anlegen → *APIs & Dienste → OAuth-Zustimmungsbildschirm* einrichten
   (Extern; Testnutzer eintragen, solange die App nicht verifiziert ist).
2. *Anmeldedaten → Anmeldedaten erstellen → OAuth-Client-ID → Typ „Desktop-App“*.
3. `GOOGLE_CLIENT_ID` und `GOOGLE_CLIENT_SECRET` in `core/version.py` eintragen (bei Desktop-Apps ist das Secret
   nicht geheim, Google verlangt es trotzdem) und neu veröffentlichen.

## KI-Assistent einrichten (optional)

Ohne Einrichtung antwortet die eingebaute FAQ. Für KI: `server_examples/assistant_worker.js` als Cloudflare Worker
bereitstellen (API-Schlüssel als Secret im Worker, Ausgabenlimit setzen) und die Worker-Adresse bei `ASSISTANT_URL`
in `core/version.py` eintragen. **Niemals einen API-Schlüssel in das Programm schreiben.**

## Kontaktformular

Standardmäßig öffnet sich das Mailprogramm des Nutzers mit einer fertigen Mail an `FEEDBACK_EMAIL`
(`core/version.py`). Für direktes Senden ohne Mailprogramm: bei einem Formular-Dienst (z. B. Formspree) ein
Formular anlegen, das an deine Adresse weiterleitet, und dessen https-Adresse bei `CONTACT_ENDPOINT` eintragen.

## Neues Modul hinzufügen

1. Ordner `modules/mein_tool/` mit leerer `__init__.py` und einer `plugin.py` mit `class Plugin(BasePlugin)`
   (siehe `core/plugin_api.py`; `create_page(parent)` liefert die Seite).
2. Ordnernamen in `modules/__init__.py` bei `BUILTIN_MODULES` eintragen (damit er auch in der EXE steckt)
   und in der Build-Zeile `--hidden-import modules.mein_tool.plugin` ergänzen.

## Profil-Format (Jaron Op Makro)

```json
{"name": "Standard", "target": "key:e", "interval": {"ms": 100, "s": 0, "min": 0},
 "repeat_mode": "count", "repeat_count": 10, "timer_enabled": true, "timer_value": 5, "timer_unit": "min",
 "start_delay": 3, "hotkey_start": "<f6>", "hotkey_stop": "<f6>"}
```
`target`: `mouse:left|right|middle` oder `key:<name>`. Hotkeys im pynput-Format, z. B. `<ctrl>+<alt>+p`.
