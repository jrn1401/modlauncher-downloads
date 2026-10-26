"""Hilfe-Assistent: eingebaute FAQ-Antworten (offline) + optional ein KI-Endpunkt.

Der KI-Endpunkt ist eine https-Adresse DEINES Servers (siehe server_examples/assistant_worker.js).
Dort liegt der API-Schlüssel. Er darf nie im Programm stehen, weil jeder Nutzer ihn auslesen könnte.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from core.version import APP_ID, APP_VERSION

# (Stichwörter, Antwort). Es gewinnt der Eintrag mit den meisten Treffern.
FAQ = [
    (("start", "stop", "hotkey", "f6", "tastenkombination", "global", "hintergrund"),
     "Start/Stop-Hotkeys stellst du bei „Jaron Op Makro“ unter „Globale Hotkeys“ ein: auf „Aufnehmen“ klicken und die Taste "
     "oder Kombination (z. B. F6 oder Strg+Alt+P) drücken. Sind Start und Stop gleich, schaltet die Taste um. "
     "Die Hotkeys funktionieren auch, wenn das Fenster im Hintergrund ist."),
    (("intervall", "geschwindigkeit", "millisekunden", "schnell", "langsam", "cps", "pause"),
     "Das Klick-Intervall setzt du aus Minuten, Sekunden und Millisekunden zusammen (Minimum 1 ms). "
     "Sehr kurze Intervalle hängen von Windows und dem Zielprogramm ab. Manche Programme verarbeiten nicht jeden Klick."),
    (("taste", "tasten", "buchstabe", "leertaste", "maus", "ziel", "welche"),
     "Als Ziel kannst du die linke, rechte oder mittlere Maustaste oder jede Tastaturtaste wählen "
     "(Buchstaben, Ziffern, F-Tasten, Leertaste, Enter ...). Mit „Taste aufnehmen“ drückst du die gewünschte Taste einfach selbst."),
    (("wiederholen", "wiederholung", "unendlich", "mal", "timer", "laufzeit", "begrenzen"),
     "Unter „Wiederholungen & Timer“ wählst du „Unendlich“ oder „X-mal“. Mit „Laufzeit begrenzen“ stoppt der Klicker "
     "nach genau der eingestellten Zeit, z. B. 5 Minuten."),
    (("profil", "profile", "speichern", "laden", "json", "sichern"),
     "Profile speicherst und lädst du oben auf der Seite „Jaron Op Makro“ mit „Speichern …“ und „Laden …“. "
     "Sie sind normale JSON-Dateien, die du auch weitergeben kannst. Der zuletzt benutzte Zustand wird automatisch gemerkt."),
    (("update", "aktualisieren", "version", "neue version"),
     "Beim Start wird automatisch nach Updates gesucht. Gibt es eins, erscheint ein Fenster mit „Jetzt aktualisieren“. "
     "Manuell geht es auf dem Dashboard über „Nach Updates suchen“."),
    (("smartscreen", "windows geschützt", "blockiert", "virus", "antivirus", "defender", "startet nicht"),
     "Windows warnt bei unbekannten Programmen: Auf „Weitere Informationen“ klicken, dann „Trotzdem ausführen“. "
     "Fehlt der Knopf, in den Dateieigenschaften unten „Zulassen“ anhaken. Auto-Clicker werden von manchen Virenscannern "
     "fälschlich gemeldet. Bei anhaltenden Problemen schreib uns über „Kontakt“."),
    (("passwort", "kennwort", "ändern", "vergessen", "reset"),
     "Das Passwort änderst du unter Einstellungen → Konto. Es gibt keinen Server und daher kein „Passwort vergessen“: "
     "Die Konten liegen nur auf diesem PC. Wenn du es vergisst, kannst du ein neues Konto anlegen."),
    (("2fa", "zwei", "faktor", "authenticator", "code", "totp"),
     "Die Zwei-Faktor-Anmeldung aktivierst du unter Einstellungen → Konto → „2FA einrichten“. Den angezeigten Schlüssel "
     "gibst du in einer Authenticator-App ein (z. B. Google Authenticator, Aegis, Microsoft Authenticator) und bestätigst "
     "mit dem 6-stelligen Code. Die Uhrzeit des Handys muss stimmen."),
    (("google", "anmelden mit", "gmail"),
     "Die Google-Anmeldung braucht eine einmalige Einrichtung durch den Betreiber der App. Ist sie nicht aktiv, "
     "melde dich mit Benutzername und Passwort an."),
    (("angemeldet bleiben", "login", "anmelden", "abmelden", "logout", "konto"),
     "Mit „Angemeldet bleiben“ bleibst du bis zu 30 Tage angemeldet. Abmelden kannst du unten in der Seitenleiste."),
    (("farbe", "design", "dunkel", "hell", "dark", "light", "akzent", "theme"),
     "Farbe und Design stellst du unter Einstellungen → Aussehen ein: Dunkel, Hell oder System und eine Akzentfarbe."),
    (("download", "drosseln", "bandbreite", "internet", "langsam laden"),
     "Die Download-Geschwindigkeit für Updates kannst du unter Einstellungen → Leistung in KB/s begrenzen (0 = unbegrenzt)."),
    (("ram", "cpu", "gpu", "prozessor", "arbeitsspeicher", "hardware", "leistung", "kerne", "grafikkarte"),
     "Unter Einstellungen → Leistung kannst du die Priorität, die Anzahl der CPU-Kerne und (nur Windows) den Arbeitsspeicher "
     "dieses Programms begrenzen. Das gilt nur für den Launcher selbst. Eine GPU-Begrenzung gibt es nicht, da das Programm die "
     "Grafikkarte nicht nutzt."),
    (("kontakt", "feedback", "fehler melden", "bug", "idee", "vorschlag"),
     "Feedback und Fehlermeldungen schickst du über „Kontakt“ in der Seitenleiste."),
]

FALLBACK = ("Dazu habe ich keine passende Antwort. Versuch es mit anderen Stichwörtern (z. B. „Hotkey“, „Profil“, „Update“) "
            "oder schreib uns über „Kontakt“.")


def _words(text: str) -> str:
    return re.sub(r"[^\wäöüß+ ]", " ", text.lower())


def answer_local(question: str) -> str:
    q = _words(question)
    best, best_score = None, 0
    for keys, answer in FAQ:
        score = sum(1 for k in keys if k in q)
        if score > best_score:
            best, best_score = answer, score
    return best or FALLBACK


def _check_url(url: str) -> None:
    p = urllib.parse.urlparse(url)
    local = p.hostname in ("127.0.0.1", "localhost")
    if p.scheme != "https" and not (p.scheme == "http" and local):
        raise ValueError("Die Assistenten-Adresse muss mit https:// beginnen.")


def ask_remote(url: str, history: list[dict], timeout: float = 30) -> str:
    """history = [{"role": "user"|"assistant", "content": str}, ...]. Gibt die Antwort zurück oder wirft Exception."""
    _check_url(url)
    payload = {"app": APP_ID, "version": APP_VERSION,
               "messages": [{"role": m["role"], "content": m["content"][:1000]} for m in history[-10:]]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": f"{APP_ID}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read(200_000).decode("utf-8"))
    reply = data.get("reply") if isinstance(data, dict) else None
    if not isinstance(reply, str) or not reply.strip():
        raise ValueError("Leere Antwort vom Assistenten-Server.")
    return reply.strip()


def reply(question: str, history: list[dict], url: str) -> tuple[str, bool]:
    """Gibt (Antwort, kam_von_ki) zurück. Ohne URL oder bei Fehlern antwortet die FAQ."""
    if url:
        try:
            return ask_remote(url, history), True
        except (ValueError, OSError, urllib.error.URLError):
            return answer_local(question) + "\n\n(Der KI-Assistent ist gerade nicht erreichbar, das ist die Standard-Antwort.)", False
    return answer_local(question), False
