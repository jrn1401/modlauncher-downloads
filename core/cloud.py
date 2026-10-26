"""Supabase-Client (nur Standardbibliothek): Konto, Google-Anmeldung, verschlüsseltes Profil, KI-Funktion.

Server-Gegenstück: supabase/migrations/*.sql (Tabellen + Funktionen) und supabase/functions/jopml-ai.
Der Client kennt nur die öffentliche Project-URL und den publishable key. Alles Sensible (Schlüssel für die
Verschlüsselung, Gemini-Key, Google-Client-Secret) liegt ausschließlich auf dem Server.
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

from core import oauth_loopback
from core import net
from core.version import (AI_FUNCTION, APP_ID, APP_VERSION, OAUTH_LOOPBACK_PORT, PSEUDO_EMAIL_TEMPLATE,
                          SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL)


class CloudError(Exception):
    """Fehlertext darf dem Nutzer angezeigt werden."""


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class CloudClient:
    def __init__(self, url: str = SUPABASE_URL, key: str = SUPABASE_PUBLISHABLE_KEY):
        self.url = (url or "").rstrip("/")
        self.key = key or ""
        self.session: dict | None = None      # access_token, refresh_token, expires_at

    @property
    def configured(self) -> bool:
        return self.url.startswith("https://") or self.url.startswith("http://127.0.0.1")

    # ---------- HTTP ----------
    def _request(self, method: str, path: str, body=None, token: str | None = None, timeout: float = 20):
        headers = {"apikey": self.key, "Content-Type": "application/json", "Accept": "application/json",
                   "User-Agent": f"{APP_ID}/{APP_VERSION}"}
        headers["Authorization"] = f"Bearer {token or self.key}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with net.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(2_000_000).decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                err = json.loads(exc.read().decode("utf-8"))
            except Exception:
                err = {}
            msg = err.get("error_description") or err.get("msg") or err.get("message") or err.get("error") or ""
            raise CloudError(self._friendly(str(msg), exc.code)) from None
        except (urllib.error.URLError, OSError) as exc:
            raise CloudError(f"No connection to the server: {exc}") from None
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except ValueError:
            raise CloudError("Unexpected answer from the server.") from None

    @staticmethod
    def _friendly(msg: str, status: int) -> str:
        low = msg.lower()
        if "invalid login" in low or "invalid_grant" in low or "invalid credentials" in low:
            return "Wrong username or password."
        if "already registered" in low or "already been registered" in low or "user_already_exists" in low:
            return "This username is already taken."
        if "username_taken" in low:
            return "This username is already taken."
        if "password" in low and ("short" in low or "least" in low or "weak" in low):
            return "The password is too short or too weak."
        if status == 429 or "rate limit" in low:
            return "Too many attempts. Please wait a moment."
        return msg or f"Server error ({status})."

    # ---------- Sitzung ----------
    def _set_session(self, data: dict) -> dict:
        if not isinstance(data, dict) or not data.get("access_token"):
            raise CloudError("The server did not return a session. Is 'Confirm email' still enabled in the Supabase "
                             "Auth settings? It must be turned off (see supabase/config.toml).")
        expires = data.get("expires_at") or (int(time.time()) + int(data.get("expires_in", 3600)))
        self.session = {"access_token": data["access_token"], "refresh_token": data.get("refresh_token", ""),
                        "expires_at": int(expires)}
        return self.session

    def token(self) -> str:
        if not self.session:
            raise CloudError("Not signed in.")
        if self.session["expires_at"] - time.time() < 60 and self.session.get("refresh_token"):
            self.refresh(self.session["refresh_token"])
        return self.session["access_token"]

    def refresh(self, refresh_token: str) -> dict:
        data = self._request("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": refresh_token})
        return self._set_session(data)

    def sign_out(self) -> None:
        if self.session:
            try:
                self._request("POST", "/auth/v1/logout", {}, token=self.session["access_token"], timeout=8)
            except CloudError:
                pass
        self.session = None

    # ---------- Anmelden / Registrieren ----------
    @staticmethod
    def pseudo_email(username: str) -> str:
        return PSEUDO_EMAIL_TEMPLATE.format(u=username.strip().lower())

    def sign_up(self, username: str, password: str) -> dict:
        data = self._request("POST", "/auth/v1/signup", {"email": self.pseudo_email(username), "password": password})
        return self._set_session(data)

    def sign_in(self, username: str, password: str) -> dict:
        data = self._request("POST", "/auth/v1/token?grant_type=password",
                             {"email": self.pseudo_email(username), "password": password})
        return self._set_session(data)

    def sign_in_google(self, cancel: threading.Event | None = None) -> dict:
        """Google über Supabase Auth (PKCE). Der Browser öffnet Supabase -> Google -> zurück auf 127.0.0.1."""
        verifier = secrets.token_urlsafe(64)
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())

        def build(redirect: str) -> str:
            return f"{self.url}/auth/v1/authorize?" + urllib.parse.urlencode({
                "provider": "google", "redirect_to": redirect,
                "code_challenge": challenge, "code_challenge_method": "s256"})

        try:
            got = oauth_loopback.capture_redirect(build, port=OAUTH_LOOPBACK_PORT, cancel=cancel)
        except oauth_loopback.LoopbackError as exc:
            raise CloudError(str(exc)) from None
        if "error" in got:
            raise CloudError("Sign-in cancelled." if got.get("error") == "access_denied"
                             else f"Google sign-in failed: {got.get('error_description', got['error'])}")
        data = self._request("POST", "/auth/v1/token?grant_type=pkce",
                             {"auth_code": got["code"], "code_verifier": verifier})
        return self._set_session(data)

    # ---------- Profil (verschlüsselt in der Datenbank, nur über RPC) ----------
    def rpc(self, name: str, args: dict | None = None):
        return self._request("POST", f"/rest/v1/rpc/{name}", args or {}, token=self.token())

    def ensure_profile(self, username: str | None, display_name: str | None) -> dict:
        prof = self.rpc("jopml_ensure_profile", {"p_username": username, "p_display_name": display_name})
        if not isinstance(prof, dict):
            raise CloudError("Profile could not be created.")
        return prof

    def get_profile(self) -> dict | None:
        return self.rpc("jopml_get_profile")

    def save_profile(self, display_name: str | None = None, email: str | None = None, settings: dict | None = None) -> dict:
        """Sendet nur die übergebenen Felder; der Server mischt sie in das verschlüsselte Profil."""
        p = {k: v for k, v in (("display_name", display_name), ("email", email), ("settings", settings)) if v is not None}
        return self.rpc("jopml_save_profile", {"p": p})

    def delete_account(self) -> None:
        self.rpc("jopml_delete_account")
        self.session = None

    # ---------- KI (Supabase Edge Function -> Gemini) ----------
    def ai(self, kind: str, messages: list[dict], lang: str = "en") -> str:
        data = self._request("POST", f"/functions/v1/{AI_FUNCTION}",
                             {"kind": kind, "messages": messages[-10:], "lang": lang}, token=self.token(), timeout=60)
        reply = data.get("reply") if isinstance(data, dict) else None
        if not isinstance(reply, str) or not reply.strip():
            raise CloudError((data or {}).get("error", "Empty answer from the AI.") if isinstance(data, dict) else "Empty answer.")
        return reply.strip()
