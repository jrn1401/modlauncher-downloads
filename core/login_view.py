"""Anmeldung: JOPMakro-Konto (Benutzername + Passwort, E-Mail freiwillig) oder Google; "Angemeldet bleiben"."""
import threading
import tkinter as tk

import customtkinter as ctk

from core import accounts, i18n, theme
from core.identity import REMEMBER_CHOICES
from core.legal_text import legal_text
from core.version import APP_NAME


def remember_label(days) -> str:
    return i18n.tr(next(l for l, d in REMEMBER_CHOICES if d == days))


def remember_value(label: str):
    return next((d for l, d in REMEMBER_CHOICES if i18n.tr(l) == label), 0)


def default_days(settings: dict):
    v = str(settings.get("remember", "30"))
    return None if v == "forever" else int(v) if v.isdigit() else 30


def days_to_setting(days) -> str:
    return "forever" if days is None else str(days)


tr = i18n.tr


class LoginView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"), corner_radius=0)
        self.app = app
        self.ident = app.identity
        self.mode = "login"
        self._cancel: threading.Event | None = None
        self.card = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=16)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.body = None
        self._build()

    def _build(self):
        if self.body is not None:
            self.body.destroy()
        b = self.body = ctk.CTkFrame(self.card, fg_color="transparent")
        b.pack(padx=40, pady=30)
        top = ctk.CTkFrame(b, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text="🌐 " + tr("Language"), text_color=theme.MUTED).pack(side="left")
        self.o_lang = ctk.CTkOptionMenu(top, values=list(i18n.LANGS.values()), width=150, command=self._lang)
        self.o_lang.set(i18n.LANGS[i18n.get_language()])
        self.o_lang.pack(side="right")
        ctk.CTkLabel(b, text=APP_NAME, font=ctk.CTkFont(size=26, weight="bold")).pack()
        ctk.CTkLabel(b, text=tr("Sign in to continue") if self.mode == "login" else tr("Create your JOPMakro account"),
                     text_color=theme.MUTED).pack(pady=(0, 14))
        seg = ctk.CTkSegmentedButton(b, values=[tr("Sign in"), tr("Create account")], command=self._switch, width=320)
        seg.set(tr("Sign in") if self.mode == "login" else tr("Create account"))
        seg.pack(pady=(0, 12))

        self.e_user = self._entry(b, tr("Username"))
        if self.mode == "register":
            self.e_display = self._entry(b, tr("Display name (optional)"))
            self.e_mail = self._entry(b, tr("E-mail (optional – leave empty to stay anonymous)"))
        self.e_pw = self._entry(b, tr("Password"), secret=True)
        if self.mode == "register":
            self.e_pw2 = self._entry(b, tr("Repeat password"), secret=True)
            ctk.CTkLabel(b, text="🔒 " + tr("The password cannot be changed after the account has been created. "
                                             "There is no recovery – keep it safe."),
                         text_color="#f59e0b", wraplength=320, justify="left").pack(pady=(2, 6))
        self.accept = tk.BooleanVar(value=False)
        if self.mode == "register":
            ctk.CTkCheckBox(b, text=tr("I have read and accept the terms of use and disclaimer."), variable=self.accept,
                            width=320).pack(anchor="w", pady=(4, 0))
            ctk.CTkButton(b, text=tr("Read the terms again"), width=190, height=24, fg_color="transparent",
                          text_color=theme.accent(), hover_color=theme.c("hover"), command=self._terms).pack(anchor="w")
        self.e_code = None
        self.code_frame = ctk.CTkFrame(b, fg_color="transparent")
        self.code_frame.pack()

        row = ctk.CTkFrame(b, fg_color="transparent")
        row.pack(fill="x", pady=(6, 2))
        ctk.CTkLabel(row, text=tr("Stay signed in:"), text_color=theme.MUTED).pack(side="left")
        self.o_remember = ctk.CTkOptionMenu(row, values=[tr(l) for l, _ in REMEMBER_CHOICES], width=170)
        self.o_remember.set(remember_label(default_days(self.app.settings)))
        self.o_remember.pack(side="right")

        self.msg = ctk.CTkLabel(b, text="", text_color=theme.DANGER, wraplength=330, justify="left")
        self.msg.pack(pady=(6, 0))
        self.btn = ctk.CTkButton(b, text=tr("Sign in") if self.mode == "login" else tr("Create account"), width=320,
                                 height=40, command=self.submit)
        self.btn.pack(pady=(8, 8))
        ctk.CTkLabel(b, text=tr("or"), text_color=theme.MUTED).pack()
        self.g_btn = ctk.CTkButton(b, text="G   " + tr("Sign in with Google"), width=320, height=40, fg_color="#ffffff",
                                   text_color="#1f1f1f", hover_color="#e8e8e8", command=self.google)
        self.g_btn.pack(pady=(8, 0))
        if not self.ident.supports_google:
            ctk.CTkLabel(b, text=tr("Google sign-in needs the cloud server (not set up yet)."), text_color=theme.MUTED,
                         wraplength=320).pack(pady=(4, 0))
        self.e_user.focus_set()
        for e in (self.e_user, self.e_pw):
            e.bind("<Return>", lambda _e: self.submit())

    @staticmethod
    def _entry(parent, placeholder, secret=False):
        e = ctk.CTkEntry(parent, width=320, height=38, placeholder_text=placeholder, show="•" if secret else "")
        e.pack(pady=4)
        return e

    def _lang(self, name):
        code = next((c for c, n in i18n.LANGS.items() if n == name), "en")
        i18n.set_language(code)
        self.app.settings["language"] = code
        self.app.save_settings()
        self.app.show_login()

    def _terms(self):
        top = ctk.CTkToplevel(self)
        top.title(tr("Terms of use and disclaimer"))
        top.geometry("820x640")
        box = ctk.CTkTextbox(top, font=ctk.CTkFont(family="Consolas", size=12), wrap="word")
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", legal_text(i18n.get_language()))
        box.configure(state="disabled")
        top.after(80, top.lift)

    def _switch(self, label):
        self.mode = "login" if label == tr("Sign in") else "register"
        self._build()

    def _say(self, text, ok=False):
        if self.winfo_exists():
            self.msg.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _busy(self, on: bool):
        state = "disabled" if on else "normal"
        self.btn.configure(state=state)

    # ---------- Anmelden / Registrieren
    def submit(self):
        user, pw = self.e_user.get().strip(), self.e_pw.get()
        code = self.e_code.get().strip() if self.e_code is not None else None
        days = remember_value(self.o_remember.get())
        if not user or not pw:
            self._say(tr("Please enter username and password."))
            return
        if self.mode == "register":
            if pw != self.e_pw2.get():
                self._say(tr("The passwords do not match."))
                return
            if not self.accept.get():
                self._say(tr("Please accept the terms of use first."))
                return
            args = (user, self.e_display.get(), self.e_mail.get(), pw)
            work = lambda: self.ident.register(*args)
        else:
            work = lambda: self.ident.login(user, pw, code)
        self._busy(True)
        self._say(tr("Please wait …"), True)

        def run():
            try:
                res, err, need_code = work(), None, False
            except accounts.TotpRequired as exc:
                res, err, need_code = None, str(exc), True
            except accounts.AccountError as exc:
                res, err, need_code = None, str(exc), False
            except Exception as exc:
                res, err, need_code = None, f"{type(exc).__name__}: {exc}", False
            self.app.call_soon(self._result, res, err, need_code, days)

        threading.Thread(target=run, daemon=True).start()

    def _result(self, user, err, need_code, days):
        if not self.winfo_exists():
            return
        self._busy(False)
        if need_code and self.e_code is None:
            self.e_code = ctk.CTkEntry(self.code_frame, width=320, height=38, placeholder_text=tr("6-digit code (2FA)"))
            self.e_code.pack(pady=4)
            self.e_code.focus_set()
        if err:
            self._say(tr(err))
            return
        self.app.login_done(user, days)

    # ---------- Google
    def google(self):
        if self._cancel is not None:                 # zweiter Klick = abbrechen
            self._cancel.set()
            return
        if self.mode == "register" and not self.accept.get():
            self._say(tr("Please accept the terms of use first."))
            return
        days = remember_value(self.o_remember.get())
        self._cancel = threading.Event()
        self.g_btn.configure(text=tr("Cancel (waiting for the browser …)"))
        self._say(tr("Your browser opens. Finish signing in there."), True)
        cancel = self._cancel

        def run():
            try:
                res, err = self.ident.google(cancel), None
            except accounts.AccountError as exc:
                res, err = None, str(exc)
            except Exception as exc:
                res, err = None, f"{type(exc).__name__}: {exc}"
            self.app.call_soon(self._google_done, res, err, days)

        threading.Thread(target=run, daemon=True).start()

    def _google_done(self, user, err, days):
        self._cancel = None
        if not self.winfo_exists():
            return
        self.g_btn.configure(text="G   " + tr("Sign in with Google"))
        if err:
            self._say(tr(err))
            return
        self.app.login_done(user, days)
