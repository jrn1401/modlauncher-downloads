"""Anmeldeseite: Anmelden, Registrieren, Google, 'Angemeldet bleiben', 2FA-Code."""
import threading

import tkinter

import customtkinter as ctk

from core import accounts, google_auth, theme
from core.version import APP_NAME, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET


class LoginView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"), corner_radius=0)
        self.app = app
        self._busy = False
        self._cancel_google: threading.Event | None = None
        self.remember = tkinter.BooleanVar(value=True)

        card = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=16, width=440)
        card.place(relx=0.5, rely=0.5, anchor="center")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=36, pady=30)

        ctk.CTkLabel(inner, text=APP_NAME, font=ctk.CTkFont(size=26, weight="bold")).pack()
        ctk.CTkLabel(inner, text="Melde dich an, um fortzufahren", text_color=theme.MUTED).pack(pady=(2, 14))
        self.tabs = ctk.CTkSegmentedButton(inner, values=["Anmelden", "Registrieren"], command=self._switch)
        self.tabs.set("Anmelden")
        self.tabs.pack(fill="x", pady=(0, 14))

        self.body = ctk.CTkFrame(inner, fg_color="transparent", width=340)
        self.body.pack(fill="x")
        self._build_login()
        self._build_register()
        self.form_login.pack(fill="x")

        self.status = ctk.CTkLabel(inner, text="", wraplength=340, justify="left", text_color=theme.DANGER)
        self.status.pack(fill="x", pady=(10, 0))

    # ---------- Formulare ----------
    def _entry(self, parent, placeholder, secret=False):
        e = ctk.CTkEntry(parent, placeholder_text=placeholder, width=340, height=36, show="•" if secret else "")
        e.pack(pady=4)
        return e

    def _build_login(self):
        f = self.form_login = ctk.CTkFrame(self.body, fg_color="transparent")
        self.l_user = self._entry(f, "Benutzername")
        self.l_pass = self._entry(f, "Passwort", secret=True)
        self.l_code = ctk.CTkEntry(f, placeholder_text="2FA-Code (6 Ziffern)", width=340, height=36)   # erst bei Bedarf sichtbar
        self.l_remember = ctk.CTkCheckBox(f, text="Angemeldet bleiben", variable=self.remember)
        self.l_remember.pack(anchor="w", pady=(8, 4))
        self.l_btn = ctk.CTkButton(f, text="Anmelden", width=340, height=38, command=self._do_login)
        self.l_btn.pack(pady=(6, 4))
        ctk.CTkLabel(f, text="— oder —", text_color=theme.MUTED).pack(pady=2)
        self.g_btn = ctk.CTkButton(f, text="Mit Google anmelden", width=340, height=38, fg_color=("#ffffff", "#ffffff"),
                                   hover_color=("#e8e8e8", "#e8e8e8"), text_color="#202124", command=self._do_google)
        self.g_btn.pack(pady=(4, 0))
        for e in (self.l_user, self.l_pass, self.l_code):
            e.bind("<Return>", lambda _e: self._do_login())

    def _build_register(self):
        f = self.form_register = ctk.CTkFrame(self.body, fg_color="transparent")
        self.r_user = self._entry(f, "Benutzername (a–z, 0–9, . _ -)")
        self.r_name = self._entry(f, "Anzeigename (wird im Programm gezeigt)")
        self.r_mail = self._entry(f, "E-Mail-Adresse")
        self.r_pass = self._entry(f, "Passwort (mind. 8 Zeichen)", secret=True)
        self.r_pass2 = self._entry(f, "Passwort wiederholen", secret=True)
        ctk.CTkCheckBox(f, text="Angemeldet bleiben", variable=self.remember).pack(anchor="w", pady=(8, 4))
        self.r_btn = ctk.CTkButton(f, text="Konto erstellen", width=340, height=38, command=self._do_register)
        self.r_btn.pack(pady=(6, 0))
        ctk.CTkLabel(f, text="Dein Konto wird nur auf diesem PC gespeichert.", text_color=theme.MUTED).pack(pady=(8, 0))
        self.r_pass2.bind("<Return>", lambda _e: self._do_register())

    def _switch(self, label):
        self._say("")
        self.form_login.pack_forget()
        self.form_register.pack_forget()
        (self.form_login if label == "Anmelden" else self.form_register).pack(fill="x")

    # ---------- Hilfen ----------
    def _say(self, text, ok=False):
        self.status.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.l_btn.configure(state=state)
        self.r_btn.configure(state=state)

    def _async(self, work, on_ok, on_err=None):
        """Führt work() in einem Thread aus (Passwort-Hashing dauert einen Moment) und meldet das Ergebnis im UI-Thread."""
        self._set_busy(True)

        def run():
            try:
                res, err = work(), None
            except Exception as exc:
                res, err = None, exc
            self.app.call_soon(self._finish, res, err, on_ok, on_err)

        threading.Thread(target=run, daemon=True).start()

    def _finish(self, res, err, on_ok, on_err):
        if not self.winfo_exists():
            return
        self._set_busy(False)
        if err is None:
            on_ok(res)
        elif on_err and on_err(err):
            return
        else:
            self._say(str(err) if isinstance(err, (accounts.AccountError, google_auth.GoogleAuthError))
                      else f"Unerwarteter Fehler: {err}")

    # ---------- Aktionen ----------
    def _do_login(self):
        if self._busy:
            return
        user, pw, code = self.l_user.get(), self.l_pass.get(), self.l_code.get()
        if not user.strip() or not pw:
            self._say("Bitte Benutzername und Passwort eingeben.")
            return
        self._say("Prüfe ...", ok=True)

        def need_code(err):
            if isinstance(err, accounts.TotpRequired):
                self.l_code.pack(pady=4, before=self.l_remember)   # über der Checkbox einblenden
                self.l_code.focus_set()
                self._say(str(err), ok=True)
                return True
            return False

        self._async(lambda: self.app.accounts.authenticate(user, pw, code),
                    lambda u: self.app.login_done(u, self.remember.get()), need_code)

    def _do_register(self):
        if self._busy:
            return
        if self.r_pass.get() != self.r_pass2.get():
            self._say("Die Passwörter stimmen nicht überein.")
            return
        self._say("Erstelle Konto ...", ok=True)
        self._async(lambda: self.app.accounts.register(self.r_user.get(), self.r_name.get(), self.r_mail.get(), self.r_pass.get()),
                    lambda u: self.app.login_done(u, self.remember.get()))

    def _do_google(self):
        if self._cancel_google is not None:          # läuft schon -> abbrechen
            self._cancel_google.set()
            return
        if not GOOGLE_CLIENT_ID:
            self._say("Die Google-Anmeldung ist noch nicht eingerichtet (GOOGLE_CLIENT_ID in core/version.py, siehe README).")
            return
        cancel = self._cancel_google = threading.Event()
        self.g_btn.configure(text="Abbrechen (warte auf Browser ...)")
        self._say("Der Browser wurde geöffnet. Bitte dort bei Google anmelden.", ok=True)

        def work():
            info = google_auth.sign_in(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, cancel=cancel)
            return self.app.accounts.google_login(info["sub"], info["email"], info["name"], info["email_verified"])

        def done(user):
            self._cancel_google = None
            self.app.login_done(user, self.remember.get())

        def failed(err):
            self._cancel_google = None
            if self.winfo_exists():
                self.g_btn.configure(text="Mit Google anmelden")
            return False

        self._async(work, done, failed)
