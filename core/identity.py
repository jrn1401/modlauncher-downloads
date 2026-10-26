"""Einheitliche Konto-Schnittstelle: Cloud (Supabase) wenn eingerichtet, sonst lokale Konten auf dem PC.

Beide Varianten liefern denselben "user"-dict:
  username, display_name, email, backend ("cloud"|"local"), totp_enabled, has_password, google_linked
"""
import threading
import time

from core import accounts
from core.accounts import AccountError
from core.cloud import CloudClient, CloudError
from core.config import app_dir, load_json, save_json

REMEMBER_CHOICES = [("Don't stay signed in", 0), ("24 hours", 1), ("1 week", 7), ("30 days", 30), ("Forever", None)]
SYNC_KEYS = ["appearance_mode", "accent", "colors", "language", "dl_limit_kbps", "cpu_priority",
             "cpu_cores", "ram_limit_mb", "icon_bg"]


class LocalIdentity:
    backend = "local"
    supports_google = False
    supports_2fa = True

    def __init__(self, store: accounts.AccountStore):
        self.store = store

    def register(self, username, display, email, password):
        return self.store.register(username, display, email, password)

    def login(self, username, password, code=None):
        return self.store.authenticate(username, password, code)

    def google(self, cancel=None):
        raise AccountError("Google sign-in needs the cloud account system (Supabase), which is not set up yet.")

    def update_profile(self, user, display, email):
        return self.store.update_profile(user["username"], display, email)

    def export(self, user):
        return {"exported_at": int(time.time()), "backend": "local", "profile": {
            k: user[k] for k in ("username", "display_name", "email")}}

    def delete(self, user, password):
        self.store.delete_account(user["username"], password)

    def remember(self, user, days):
        if days == 0:
            self.store.clear_session()
        else:
            self.store.create_session(user["username"], days)

    def resume(self):
        return self.store.resume_session()

    def forget(self, user=None):
        self.store.clear_session()

    def pull_settings(self, user):
        return None

    def push_settings(self, user, settings):
        pass


class CloudIdentity:
    backend = "cloud"
    supports_google = True
    supports_2fa = False

    def __init__(self, client: CloudClient):
        self.client = client
        self.session_path = app_dir() / "session_cloud.json"
        self._kind = "password"

    # ---- Hilfen
    def _user(self, prof: dict, kind: str) -> dict:
        self._kind = kind
        return {"username": prof.get("username", ""), "display_name": prof.get("display_name") or prof.get("username", ""),
                "email": prof.get("email") or "", "backend": "cloud", "totp_enabled": False,
                "has_password": kind == "password", "google_linked": kind == "google", "settings": prof.get("settings")}

    @staticmethod
    def _wrap(fn, *a, **k):
        try:
            return fn(*a, **k)
        except CloudError as exc:
            raise AccountError(str(exc)) from None

    # ---- Konto
    def register(self, username, display, email, password):
        username = (username or "").strip().lower()
        if not accounts.USERNAME_RE.match(username):
            raise AccountError("Username: 3-24 characters, only a-z, 0-9, dot, underscore, hyphen.")
        email = accounts.AccountStore._check_email(email)
        if len(password) < accounts.MIN_PASSWORD:
            raise AccountError(f"The password must be at least {accounts.MIN_PASSWORD} characters long.")
        self._wrap(self.client.sign_up, username, password)
        try:
            prof = self.client.ensure_profile(username, (display or "").strip()[:40] or username)
            if email:
                self.client.save_profile(email=email)
                prof["email"] = email
        except CloudError as exc:
            try:
                self.client.delete_account()      # keine halb angelegten Konten zurücklassen
            except CloudError:
                pass
            raise AccountError(str(exc)) from None
        return self._user(prof, "password")

    def login(self, username, password, code=None):
        username = (username or "").strip().lower()
        self._wrap(self.client.sign_in, username, password)
        prof = self._wrap(self.client.get_profile) or self._wrap(self.client.ensure_profile, username, None)
        return self._user(prof, "password")

    def google(self, cancel: threading.Event | None = None):
        self._wrap(self.client.sign_in_google, cancel)
        prof = self._wrap(self.client.get_profile) or self._wrap(self.client.ensure_profile, None, None)
        return self._user(prof, "google")

    def update_profile(self, user, display, email):
        email = accounts.AccountStore._check_email(email)
        display = (display or "").strip()[:40] or user["username"]
        self._wrap(self.client.save_profile, display, email)
        return {**user, "display_name": display, "email": email}

    def export(self, user):
        prof = self._wrap(self.client.get_profile) or {}
        return {"exported_at": int(time.time()), "backend": "cloud", "profile": prof}

    def delete(self, user, password):
        self._wrap(self.client.delete_account)
        self.forget()

    # ---- Sitzung
    def remember(self, user, days):
        if days == 0 or not self.client.session:
            self.forget_file()
            return
        save_json(self.session_path, {
            "refresh_token": self.client.session.get("refresh_token", ""), "kind": self._kind,
            "expires": None if days is None else int(time.time() + days * 86400)})

    def resume(self):
        s = load_json(self.session_path)
        if not isinstance(s, dict) or not s.get("refresh_token"):
            return None
        if s.get("expires") is not None and s["expires"] < time.time():
            self.forget_file()
            return None
        try:
            self.client.refresh(s["refresh_token"])
            prof = self.client.get_profile()
        except CloudError:
            return None                     # offline oder abgelaufen -> normale Anmeldung
        if not prof:
            return None
        user = self._user(prof, s.get("kind", "password"))
        save_json(self.session_path, {**s, "refresh_token": self.client.session["refresh_token"]})   # Token rotiert
        return user

    def forget_file(self):
        try:
            self.session_path.unlink()
        except OSError:
            pass

    def forget(self, user=None):
        self.forget_file()
        threading.Thread(target=self.client.sign_out, daemon=True).start()

    # ---- Einstellungen in der Cloud
    def pull_settings(self, user):
        s = user.get("settings")
        return s if isinstance(s, dict) else None

    def push_settings(self, user, settings):
        data = {k: settings[k] for k in SYNC_KEYS if k in settings}
        threading.Thread(target=lambda: self._safe(self.client.save_profile, None, None, data), daemon=True).start()

    @staticmethod
    def _safe(fn, *a):
        try:
            fn(*a)
        except Exception as exc:
            print("Cloud-Synchronisierung fehlgeschlagen:", exc)


def make_identity(store: accounts.AccountStore):
    client = CloudClient()
    return CloudIdentity(client) if client.configured else LocalIdentity(store)
