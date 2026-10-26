# Jaron's OP Makro Launcher (JOPML) – v1.1

Modularer Launcher (Python, CustomTkinter, pynput) mit Auto-Clicker, Makro-Editor, Extensions und Recoil-Modul.
Download der fertigen Windows-EXE: <https://github.com/jrn1401/modlauncher-downloads/releases/latest/download/JaronsOPMakro.exe>

## Entwickeln
```
pip install -r requirements.txt
python main.py            # Programm starten
python tests/test_all.py  # Tests (laufen ohne Fenster, mit Attrappen)
```
EXE lokal bauen: `EXE_BAUEN.bat` (Windows).

## Automatische Veröffentlichung (GitHub Actions)
- `.github/workflows/release.yml`: Tests, Windows-EXE bauen, GitHub-Release `v<APP_VERSION>` anlegen, Spiegel im Supabase-Bucket `releases`.
  Neue Version = `APP_VERSION` in `core/version.py` erhöhen und auf `main` pushen.
- `.github/workflows/supabase.yml`: rollt Migrationen, Auth-Konfiguration und die KI-Funktion nach Supabase aus (nur mit Secrets).
- `.github/workflows/build-protected.yml`: optionaler Nuitka-Build (manuell, ungetestet).

## Supabase einrichten (einmalig)
1. Kostenloses Projekt auf supabase.com anlegen.
2. `SUPABASE_URL` und den **publishable key** in `core/version.py` eintragen (nie den service_role-Key).
3. Google: Im Google-Cloud-Client (Typ "Webanwendung", Client-ID steht in `core/version.py`) die Redirect-URI
   `https://<projekt>.supabase.co/auth/v1/callback` erlauben; das Client-Secret nur in Supabase eintragen.
4. Repository-Secrets setzen: `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_REF`, `SUPABASE_DB_PASSWORD`,
   `SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET`, `GEMINI_API_KEY` (aus Google AI Studio; die OAuth-Client-ID ist kein Gemini-Schlüssel),
   optional `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` für den Download-Spiegel.
5. Push auf `main` unter `supabase/` rollt alles aus. In Auth muss "Confirm email" aus sein (Konten ohne E-Mail).

## Struktur
`core/` Kern (Konten, Cloud, Design, Sprachen, Rechtstext), `modules/` Plugins (autoclicker, macros, extensions, recoil),
`supabase/` Datenbank + Edge Function, `csharp/` ungetestete Avalonia-Vorlage, `tools/` Hilfsskripte, `tests/` Tests.

## Hinweise
Das Recoil-Modul ist nur für Offline-Spiele gedacht; moderne Anti-Cheat-Systeme können es erkennen. Der Rechtstext wurde nicht anwaltlich geprüft.
`server_examples/assistant_worker.js` ist ein optionaler eigener KI-Endpunkt (Anthropic, ungetestet); der Standard ist die Supabase-Funktion mit Gemini.
