"""Google-Anmeldung (OAuth 2.0 für Desktop-Apps, Loopback + PKCE).

Es öffnet sich der Browser, der Nutzer meldet sich bei Google an, Google leitet auf
http://127.0.0.1:<port> zurück. Ergebnis: bestätigte E-Mail-Adresse und Name.
Dafür wird eine OAuth-Client-ID (Typ "Desktop-App") aus der Google Cloud Console gebraucht.
"""
import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
open_browser = webbrowser.open     # in Tests austauschbar

_DONE_HTML = ("<html><head><meta charset='utf-8'><title>Anmeldung</title></head>"
              "<body style='font-family:sans-serif;text-align:center;margin-top:15vh'>"
              "<h2>Fertig!</h2><p>Du kannst dieses Fenster schließen und zum Programm zurückkehren.</p>"
              "</body></html>").encode("utf-8")


class GoogleAuthError(Exception):
    pass


def _post_form(url: str, fields: dict, timeout: float = 15) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error_description", "")
        except Exception:
            detail = ""
        raise GoogleAuthError(f"Google hat die Anmeldung abgelehnt ({exc.code}). {detail}".strip()) from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise GoogleAuthError(f"Keine Verbindung zu Google: {exc}") from None


def _get_json(url: str, token: str, timeout: float = 15) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise GoogleAuthError(f"Profil konnte nicht geladen werden: {exc}") from None


def sign_in(client_id: str, client_secret: str, timeout: float = 180,
            cancel: threading.Event | None = None) -> dict:
    """Blockiert bis zum Abschluss (in einem Thread aufrufen). Gibt sub/email/email_verified/name zurück."""
    if not client_id:
        raise GoogleAuthError("Google-Anmeldung ist nicht eingerichtet (GOOGLE_CLIENT_ID fehlt).")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    result: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q or "error" in q:
                result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_DONE_HTML)))
            self.end_headers()
            self.wfile.write(_DONE_HTML)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)   # nur lokal erreichbar
    server.timeout = 0.5
    redirect = f"http://127.0.0.1:{server.server_port}"
    try:
        url = AUTH_URL + "?" + urllib.parse.urlencode({
            "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
            "scope": "openid email profile", "code_challenge": challenge,
            "code_challenge_method": "S256", "state": state, "prompt": "select_account"})
        open_browser(url)
        deadline = time.time() + timeout
        while not result and time.time() < deadline:
            if cancel is not None and cancel.is_set():
                raise GoogleAuthError("Abgebrochen.")
            server.handle_request()
    finally:
        server.server_close()

    if not result:
        raise GoogleAuthError("Zeitüberschreitung: Es kam keine Antwort von Google.")
    if "error" in result:
        raise GoogleAuthError("Anmeldung abgebrochen." if result["error"] == "access_denied"
                              else f"Google-Fehler: {result['error']}")
    if not secrets.compare_digest(result.get("state", ""), state):
        raise GoogleAuthError("Ungültige Antwort (state stimmt nicht).")

    tok = _post_form(TOKEN_URL, {
        "code": result["code"], "client_id": client_id, "client_secret": client_secret,
        "code_verifier": verifier, "redirect_uri": redirect, "grant_type": "authorization_code"})
    access = tok.get("access_token")
    if not access:
        raise GoogleAuthError("Google hat kein Zugriffstoken geliefert.")
    info = _get_json(USERINFO_URL, access)
    verified = info.get("email_verified")
    return {"sub": info.get("sub", ""), "email": info.get("email", ""),
            "email_verified": verified is True or verified == "true", "name": info.get("name", "")}
