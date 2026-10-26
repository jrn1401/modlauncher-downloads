APP_NAME = "Jaron's OP Makro"      # Anzeigename (Fenstertitel, Seitenleiste)
APP_ID = "JaronsOPMakro"           # Dateiname der EXE und Ordnername für Einstellungen (ohne Sonderzeichen)
APP_VERSION = "1.1.1"              # bei jedem Update erhöhen (löst den automatischen Build aus)
SHORT_NAME = "JOPML"               # Kürzel, das im App-Icon immer sichtbar bleibt

# Hier liegt die version.json (GitHub-Release "latest")
UPDATE_MANIFEST_URL = "https://github.com/jrn1401/modlauncher-downloads/releases/latest/download/version.json"

# Feedback-Formular: Ohne CONTACT_ENDPOINT öffnet sich das Mailprogramm des Nutzers (mailto:).
FEEDBACK_EMAIL = "jrnwle@gmail.com"
CONTACT_ENDPOINT = ""     # optional: https-Adresse eines Formular-Dienstes, der an FEEDBACK_EMAIL weiterleitet

# ---------------------------------------------------------------- Google / Supabase
# Die Google-Client-ID ist öffentlich (kein Geheimnis). Sie gehört in die Supabase-Auth-Einstellungen
# (siehe supabase/config.toml); das zugehörige Client-SECRET gehört NIE in dieses Programm.
GOOGLE_CLIENT_ID = "473834634054-ipmvjinmo40ik00jf9trspvqniugi8q8.apps.googleusercontent.com"

# Nach dem Anlegen des Supabase-Projekts hier eintragen (Project URL und "publishable"/anon key; beide sind
# für Clients gedacht und öffentlich, die Sicherheit kommt von den RLS-Regeln in supabase/migrations).
SUPABASE_URL = "https://blerllyyxryqcjvcqvdw.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_zSZT7Ir_PFjTdzPZc99A0Q_DcVordOo"   # öffentlich, kein Geheimnis
PSEUDO_EMAIL_DOMAIN = "users.jopml.invalid"   # Supabase Auth braucht eine E-Mail; es wird nie eine Mail dahin gesendet
OAUTH_LOOPBACK_PORT = 53682        # lokaler Rückkehr-Port der Google-Anmeldung (in Supabase als Redirect erlauben)
AI_FUNCTION = "jopml-ai"           # Name der Supabase Edge Function mit dem KI-Zugang (Gemini)

# Optionaler eigener KI-Proxy statt Supabase (siehe server_examples/). Niemals einen API-Schlüssel eintragen!
ASSISTANT_URL = ""

# ---------------------------------------------------------------- Werbung
# Platzhalter für die Werbefläche (siehe core/ads.py). Wird derzeit nicht ausgewertet.
AD_UNIT_ID = ""                    # z. B. "ca-app-pub-xxxxxxxxxxxxxxxx/yyyyyyyyyy" (nur mobil, siehe Hinweis in ads.py)

# Version der Nutzungsbedingungen. Wird sie erhöht, muss jeder Nutzer erneut zustimmen.
LEGAL_VERSION = "2026-10-26"
