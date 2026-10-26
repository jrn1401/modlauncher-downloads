"""Lokale Konten: Registrierung, Anmeldung, 2FA (TOTP), angemeldet bleiben.

WICHTIG: Alle Daten liegen NUR auf dem PC des jeweiligen Nutzers (accounts.json im
Einstellungsordner). Passwörter werden nie im Klartext gespeichert (PBKDF2-SHA256 mit Salt).
Es gibt keinen Server, daher auch kein "Passwort vergessen"-Mail.
"""
import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from pathlib import Path

from core.config import app_dir, load_json, save_json

PBKDF2_ITER = 600_000
USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,24}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
MAX_FAILS = 5
LOCK_SECONDS = 60
SESSION_DAYS = 30


class AccountError(Exception):
    """Fehlermeldung, die dem Nutzer direkt angezeigt werden darf."""


class TotpRequired(AccountError):
    """Passwort stimmt, aber ein 2FA-Code fehlt."""


# ---------------------------------------------------------------- TOTP (RFC 6238)
def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret: str, counter: int, digits: int = 6) -> str:
    s = secret.replace(" ", "").upper()
    key = base64.b32decode(s + "=" * (-len(s) % 8))
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    num = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(num).zfill(digits)


def totp_code(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    return _hotp(secret, int((time.time() if at is None else at) // step), digits)


def verify_totp(secret: str, code: str, at: float | None = None, window: int = 1,
                min_counter: int = 0) -> int | None:
    """Gibt den passenden Zähler zurück (oder None). Zähler <= min_counter werden abgelehnt (kein Wiederverwenden)."""
    code = re.sub(r"\s", "", code or "")
    if not code.isdigit() or len(code) != 6:
        return None
    now = int((time.time() if at is None else at) // 30)
    for c in range(now - window, now + window + 1):
        if c > min_counter and hmac.compare_digest(_hotp(secret, c), code):
            return c
    return None


def totp_uri(secret: str, account: str, issuer: str) -> str:
    from urllib.parse import quote
    return (f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}"
            f"&issuer={quote(issuer)}&digits=6&period=30")


# ---------------------------------------------------------------- Passwörter
def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _hash_password(password: str, salt: bytes | None = None, iters: int = PBKDF2_ITER) -> dict:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return {"salt": _b64(salt), "hash": _b64(dk), "iter": iters}


def _check_password(password: str, rec: dict) -> bool:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(rec["salt"]), rec["iter"])
    return hmac.compare_digest(dk, base64.b64decode(rec["hash"]))


def _check_new_password(pw: str) -> None:
    if len(pw) < MIN_PASSWORD:
        raise AccountError(f"Das Passwort muss mindestens {MIN_PASSWORD} Zeichen lang sein.")


def _norm_user(name: str) -> str:
    return (name or "").strip().lower()


class AccountStore:
    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory) if directory else app_dir()
        self.path = self.dir / "accounts.json"
        self.session_path = self.dir / "session.json"
        self.data = load_json(self.path, {}) or {}
        self.data.setdefault("users", {})
        self._dummy = _hash_password("dummy")

    # ---- intern
    @property
    def users(self) -> dict:
        return self.data["users"]

    def _save(self) -> None:
        save_json(self.path, self.data)

    def _user(self, username: str) -> dict:
        u = self.users.get(_norm_user(username))
        if not u:
            raise AccountError("Konto nicht gefunden.")
        return u

    @staticmethod
    def public(u: dict) -> dict:
        return {"username": u["username"], "display_name": u["display_name"], "email": u["email"],
                "totp_enabled": bool(u["totp_enabled"]), "has_password": bool(u["pw"]),
                "google_linked": bool(u.get("google_sub"))}

    def _email_taken(self, email: str, except_user: str | None = None) -> bool:
        return any(u["email"].lower() == email.lower() and u["username"] != except_user
                   for u in self.users.values())

    @staticmethod
    def _check_email(email: str) -> str:
        email = (email or "").strip()
        if not EMAIL_RE.match(email):
            raise AccountError("Bitte eine gültige E-Mail-Adresse eingeben.")
        return email

    def _new_record(self, username, display_name, email, pw_rec, google_sub=None) -> dict:
        return {"username": username, "display_name": display_name, "email": email, "pw": pw_rec,
                "totp_secret": None, "totp_enabled": False, "totp_last": 0,
                "fails": 0, "locked_until": 0, "google_sub": google_sub,
                "session_hash": None, "created": int(time.time())}

    # ---- Registrierung / Anmeldung
    def register(self, username: str, display_name: str, email: str, password: str) -> dict:
        username = _norm_user(username)
        if not USERNAME_RE.match(username):
            raise AccountError("Benutzername: 3–24 Zeichen, nur a–z, 0–9, Punkt, Unterstrich, Bindestrich.")
        if username in self.users:
            raise AccountError("Dieser Benutzername ist schon vergeben.")
        email = self._check_email(email)
        if self._email_taken(email):
            raise AccountError("Diese E-Mail-Adresse wird schon verwendet.")
        _check_new_password(password)
        display_name = (display_name or "").strip()[:40] or username
        u = self._new_record(username, display_name, email, _hash_password(password))
        self.users[username] = u
        self._save()
        return self.public(u)

    def authenticate(self, username: str, password: str, code: str | None = None) -> dict:
        u = self.users.get(_norm_user(username))
        generic = AccountError("Benutzername oder Passwort falsch.")
        if not u:
            _check_password(password or "", self._dummy)   # gleiche Rechenzeit wie bei echten Konten
            raise generic
        now = time.time()
        if u["locked_until"] > now:
            raise AccountError(f"Zu viele Fehlversuche. Bitte in {int(u['locked_until'] - now) + 1} Sekunden erneut versuchen.")
        if not u["pw"] or not _check_password(password or "", u["pw"]):
            self._fail(u)
            raise generic
        if u["totp_enabled"]:
            if not (code or "").strip():
                raise TotpRequired("Bitte den 6-stelligen Code aus deiner Authenticator-App eingeben.")
            counter = verify_totp(u["totp_secret"], code, min_counter=u["totp_last"])
            if counter is None:
                self._fail(u)
                raise AccountError("Der 2FA-Code ist falsch oder schon benutzt.")
            u["totp_last"] = counter
        u["fails"], u["locked_until"] = 0, 0
        self._save()
        return self.public(u)

    def _fail(self, u: dict) -> None:
        u["fails"] += 1
        if u["fails"] >= MAX_FAILS:
            u["fails"], u["locked_until"] = 0, time.time() + LOCK_SECONDS
        self._save()

    # ---- Google
    def google_login(self, sub: str, email: str, name: str, email_verified: bool) -> dict:
        if not sub or not email:
            raise AccountError("Google hat keine E-Mail-Adresse geliefert.")
        for u in self.users.values():
            if u.get("google_sub") == sub:
                return self.public(u)
        if not email_verified:
            raise AccountError("Die Google-E-Mail-Adresse ist nicht bestätigt.")
        for u in self.users.values():
            if u["email"].lower() == email.lower():      # bestehendes Konto verknüpfen
                u["google_sub"] = sub
                self._save()
                return self.public(u)
        base = re.sub(r"[^a-z0-9_.-]", "", email.split("@")[0].lower())[:20] or "nutzer"
        if len(base) < 3:
            base = (base + "user")[:6]
        username, i = base, 1
        while username in self.users:
            i += 1
            username = f"{base}{i}"
        u = self._new_record(username, (name or username).strip()[:40], email, None, google_sub=sub)
        self.users[username] = u
        self._save()
        return self.public(u)

    # ---- Profil
    def update_profile(self, username: str, display_name: str, email: str) -> dict:
        u = self._user(username)
        email = self._check_email(email)
        if self._email_taken(email, except_user=u["username"]):
            raise AccountError("Diese E-Mail-Adresse wird schon verwendet.")
        u["display_name"] = (display_name or "").strip()[:40] or u["username"]
        u["email"] = email
        self._save()
        return self.public(u)

    def change_password(self, username: str, old: str | None, new: str) -> None:
        u = self._user(username)
        if u["pw"] and not _check_password(old or "", u["pw"]):
            raise AccountError("Das aktuelle Passwort ist falsch.")
        _check_new_password(new)
        u["pw"] = _hash_password(new)
        u["session_hash"] = None      # andere angemeldete Sitzungen beenden
        self._save()

    def begin_totp(self, username: str) -> str:
        u = self._user(username)
        if u["totp_enabled"]:
            raise AccountError("2FA ist schon aktiv.")
        u["totp_secret"] = new_totp_secret()
        self._save()
        return u["totp_secret"]

    def confirm_totp(self, username: str, code: str) -> None:
        u = self._user(username)
        if not u["totp_secret"]:
            raise AccountError("Bitte zuerst die Einrichtung starten.")
        counter = verify_totp(u["totp_secret"], code)
        if counter is None:
            raise AccountError("Der Code stimmt nicht. Prüfe die Uhrzeit deines Handys und versuche es erneut.")
        u["totp_enabled"], u["totp_last"] = True, counter
        self._save()

    def disable_totp(self, username: str, password: str) -> None:
        u = self._user(username)
        if u["pw"] and not _check_password(password or "", u["pw"]):
            raise AccountError("Das Passwort ist falsch.")
        u["totp_enabled"], u["totp_secret"], u["totp_last"] = False, None, 0
        self._save()

    def delete_account(self, username: str, password: str) -> None:
        u = self._user(username)
        if u["pw"] and not _check_password(password or "", u["pw"]):
            raise AccountError("Das Passwort ist falsch.")
        del self.users[u["username"]]
        self._save()
        self.clear_session()

    # ---- "Angemeldet bleiben"
    def create_session(self, username: str) -> None:
        u = self._user(username)
        token = secrets.token_urlsafe(32)
        u["session_hash"] = hashlib.sha256(token.encode()).hexdigest()
        self._save()
        save_json(self.session_path, {"username": u["username"], "token": token,
                                      "expires": int(time.time()) + SESSION_DAYS * 86400})

    def resume_session(self) -> dict | None:
        s = load_json(self.session_path)
        if not isinstance(s, dict):
            return None
        u = self.users.get(_norm_user(s.get("username", "")))
        try:
            if (u and u.get("session_hash") and s.get("expires", 0) > time.time()
                    and hmac.compare_digest(hashlib.sha256(s["token"].encode()).hexdigest(), u["session_hash"])):
                return self.public(u)
        except (KeyError, AttributeError):
            pass
        return None

    def clear_session(self) -> None:
        s = load_json(self.session_path)
        if isinstance(s, dict):
            u = self.users.get(_norm_user(s.get("username", "")))
            if u:
                u["session_hash"] = None
                self._save()
        try:
            self.session_path.unlink()
        except OSError:
            pass
