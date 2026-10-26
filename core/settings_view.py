"""Einstellungen: Konto (Name, E-Mail, Passwort, 2FA), Aussehen, Leistung, Info."""
import threading
from tkinter import messagebox

import customtkinter as ctk

from core import accounts, config, system_limits, theme
from core.version import APP_NAME, APP_VERSION


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"))
        self.app = app
        self.store: accounts.AccountStore = app.accounts
        self.columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Einstellungen", font=ctk.CTkFont(size=26, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(20, 8))
        self._row = 1
        self._build_account()
        self._build_appearance()
        self._build_performance()
        self._build_about()

    # ---------- Bausteine ----------
    def _card(self, title):
        card = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=12)
        card.grid(row=self._row, column=0, sticky="ew", padx=24, pady=6)
        self._row += 1
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=(12, 6))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))
        return body

    @staticmethod
    def _field(parent, label, value="", secret=False, width=260):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
        e = ctk.CTkEntry(row, width=width, show="•" if secret else "")
        e.pack(side="left")
        if value:
            e.insert(0, value)
        return e

    def _msg(self, parent):
        lab = ctk.CTkLabel(parent, text="", anchor="w", justify="left", wraplength=560)
        lab.pack(fill="x", pady=(4, 0))
        return lab

    @staticmethod
    def _say(label, text, ok=True):
        label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _me(self) -> dict:
        return self.app.user

    def _threaded(self, work, done, label):
        """Passwort-Prüfung dauert einen Moment: im Thread ausführen, Ergebnis im UI-Thread zeigen."""
        def run():
            try:
                res, err = work(), None
            except accounts.AccountError as exc:
                res, err = None, str(exc)
            except Exception as exc:
                res, err = None, f"Unerwarteter Fehler: {exc}"
            self.app.call_soon(lambda: self.winfo_exists() and (self._say(label, err, False) if err else done(res)))
        threading.Thread(target=run, daemon=True).start()

    # ---------- Konto ----------
    def _build_account(self):
        me = self._me()
        body = self._card("Konto")
        ctk.CTkLabel(body, text=f"Benutzername: {me['username']}", text_color=theme.MUTED, anchor="w").pack(fill="x", pady=(0, 4))
        self.e_name = self._field(body, "Anzeigename", me["display_name"])
        self.e_mail = self._field(body, "E-Mail", me["email"])
        self.m_profile = self._msg(body)
        ctk.CTkButton(body, text="Profil speichern", width=160, command=self._save_profile).pack(anchor="w", pady=(4, 12))

        ctk.CTkLabel(body, text="Passwort ändern" if me["has_password"] else "Passwort festlegen",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(4, 2))
        self.e_old = self._field(body, "Aktuelles Passwort", secret=True) if me["has_password"] else None
        self.e_new = self._field(body, "Neues Passwort", secret=True)
        self.e_new2 = self._field(body, "Neues Passwort (nochmal)", secret=True)
        self.m_pw = self._msg(body)
        ctk.CTkButton(body, text="Passwort speichern", width=160, command=self._save_password).pack(anchor="w", pady=(4, 12))

        ctk.CTkLabel(body, text="Zwei-Faktor-Authentifizierung (2FA)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(4, 2))
        self.f2fa = ctk.CTkFrame(body, fg_color="transparent")
        self.f2fa.pack(fill="x")
        self._render_2fa()

        ctk.CTkLabel(body, text="Gefahrenzone", font=ctk.CTkFont(weight="bold"), text_color=theme.DANGER).pack(anchor="w", pady=(16, 2))
        self.e_del = self._field(body, "Passwort", secret=True) if me["has_password"] else None
        self.m_del = self._msg(body)
        ctk.CTkButton(body, text="Konto löschen", width=160, fg_color=theme.DANGER, hover_color="#b83a3f",
                      command=self._delete_account).pack(anchor="w", pady=(4, 0))

    def _save_profile(self):
        try:
            self.app.user = self.store.update_profile(self._me()["username"], self.e_name.get(), self.e_mail.get())
            self._say(self.m_profile, "Gespeichert.")
            self.app.refresh_user_labels()
        except accounts.AccountError as exc:
            self._say(self.m_profile, str(exc), False)

    def _save_password(self):
        if self.e_new.get() != self.e_new2.get():
            self._say(self.m_pw, "Die neuen Passwörter stimmen nicht überein.", False)
            return
        old = self.e_old.get() if self.e_old else None
        new = self.e_new.get()
        self._say(self.m_pw, "Speichere ...")

        def done(_):
            self._say(self.m_pw, "Passwort geändert. „Angemeldet bleiben“ wurde auf anderen Sitzungen beendet.")
            for e in (self.e_old, self.e_new, self.e_new2):
                if e:
                    e.delete(0, "end")
        self._threaded(lambda: self.store.change_password(self._me()["username"], old, new), done, self.m_pw)

    # ---- 2FA
    def _render_2fa(self, secret: str | None = None):
        for w in self.f2fa.winfo_children():
            w.destroy()
        me = self._me()
        self.m_2fa = self._msg(self.f2fa)
        if me["totp_enabled"]:
            ctk.CTkLabel(self.f2fa, text="✔ 2FA ist aktiv.", text_color=theme.OK, anchor="w").pack(fill="x")
            self.e_2fa_pw = self._field(self.f2fa, "Passwort", secret=True) if me["has_password"] else None
            ctk.CTkButton(self.f2fa, text="2FA deaktivieren", width=160, fg_color="gray35", hover_color="gray25",
                          command=self._disable_2fa).pack(anchor="w", pady=(4, 0))
        elif secret:
            pretty = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))
            ctk.CTkLabel(self.f2fa, anchor="w", justify="left", wraplength=560,
                         text="1. Öffne eine Authenticator-App (z. B. Google Authenticator, Aegis, Microsoft Authenticator).\n"
                              "2. Wähle „Schlüssel manuell eingeben“ und tippe diesen Schlüssel ein:").pack(fill="x")
            key = ctk.CTkEntry(self.f2fa, width=420, font=ctk.CTkFont(family="Consolas", size=15))
            key.insert(0, pretty)
            key.configure(state="readonly")
            key.pack(anchor="w", pady=4)
            ctk.CTkButton(self.f2fa, text="Schlüssel kopieren", width=160,
                          command=lambda: self._copy(secret)).pack(anchor="w", pady=(0, 6))
            self.e_2fa_code = self._field(self.f2fa, "6-stelliger Code")
            row = ctk.CTkFrame(self.f2fa, fg_color="transparent")
            row.pack(anchor="w", pady=(4, 0))
            ctk.CTkButton(row, text="Bestätigen", width=120, command=self._confirm_2fa).pack(side="left")
            ctk.CTkButton(row, text="Abbrechen", width=120, fg_color="gray35", hover_color="gray25",
                          command=self._render_2fa).pack(side="left", padx=8)
        else:
            ctk.CTkLabel(self.f2fa, text="Schützt dein Konto zusätzlich mit einem Code aus einer Authenticator-App.",
                         text_color=theme.MUTED, anchor="w").pack(fill="x")
            ctk.CTkButton(self.f2fa, text="2FA einrichten", width=160, command=self._start_2fa).pack(anchor="w", pady=(6, 0))

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._say(self.m_2fa, "Kopiert.")

    def _start_2fa(self):
        try:
            self._render_2fa(self.store.begin_totp(self._me()["username"]))
        except accounts.AccountError as exc:
            self._say(self.m_2fa, str(exc), False)

    def _confirm_2fa(self):
        try:
            self.store.confirm_totp(self._me()["username"], self.e_2fa_code.get())
        except accounts.AccountError as exc:
            self._say(self.m_2fa, str(exc), False)
            return
        self.app.user = self.store.public(self.store.users[self._me()["username"]])
        self._render_2fa()
        self._say(self.m_2fa, "2FA ist jetzt aktiv. Beim nächsten Anmelden wird der Code abgefragt.")

    def _disable_2fa(self):
        pw = self.e_2fa_pw.get() if self.e_2fa_pw else ""

        def done(_):
            self.app.user = self.store.public(self.store.users[self._me()["username"]])
            self._render_2fa()
            self._say(self.m_2fa, "2FA wurde deaktiviert.")
        self._threaded(lambda: self.store.disable_totp(self._me()["username"], pw), done, self.m_2fa)

    # ---- Konto löschen
    def _delete_account(self):
        if not messagebox.askyesno("Konto löschen", "Dein Konto wird auf diesem PC endgültig gelöscht.\nWirklich fortfahren?"):
            return
        pw = self.e_del.get() if self.e_del else ""
        self._threaded(lambda: self.store.delete_account(self._me()["username"], pw),
                       lambda _: self.app.logout(), self.m_del)

    # ---------- Aussehen ----------
    def _build_appearance(self):
        body = self._card("Aussehen")
        s = self.app.settings
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Design", width=150, anchor="w").pack(side="left")
        seg = ctk.CTkSegmentedButton(row, values=list(theme.MODES), command=lambda lab: self._set_look(mode=theme.MODES[lab]))
        seg.set(next((k for k, v in theme.MODES.items() if v == s["appearance_mode"]), "Dunkel"))
        seg.pack(side="left")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=8)
        ctk.CTkLabel(row, text="Akzentfarbe", width=150, anchor="w").pack(side="left")
        for name, hex_ in theme.ACCENTS.items():
            ring = "white" if hex_.lower() == s["accent"].lower() else hex_
            ctk.CTkButton(row, text="✔" if ring == "white" else "", width=34, height=34, corner_radius=17, fg_color=hex_,
                          hover_color=theme.shade(hex_, 0.8), border_width=2, border_color=ring,
                          command=lambda h=hex_: self._set_look(accent=h)).pack(side="left", padx=3)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Eigene Farbe (Hex)", width=150, anchor="w").pack(side="left")
        self.e_hex = ctk.CTkEntry(row, width=110, placeholder_text="#4f8cff")
        self.e_hex.pack(side="left")
        ctk.CTkButton(row, text="Übernehmen", width=110, command=self._custom_color).pack(side="left", padx=8)
        self.m_look = self._msg(body)

    def _custom_color(self):
        value = self.e_hex.get().strip()
        if not value.startswith("#"):
            value = "#" + value
        if theme.HEX_RE.match(value):
            self._set_look(accent=value.lower())
        else:
            self._say(self.m_look, "Bitte eine Farbe wie #4f8cff eingeben (6 Zeichen 0–9, a–f).", False)

    def _set_look(self, mode=None, accent=None):
        self.app.change_appearance(mode, accent)

    # ---------- Leistung ----------
    def _build_performance(self):
        body = self._card("Leistung & Drosselung")
        s = self.app.settings
        ram = system_limits.total_ram_mb()
        cores = system_limits.cpu_count()
        self.info = ctk.CTkLabel(body, text_color=theme.MUTED, anchor="w", justify="left", wraplength=560)
        self.info.pack(fill="x", pady=(0, 6))
        self._refresh_info(cores, ram)
        ctk.CTkLabel(body, text="Diese Grenzen gelten nur für dieses Programm, nicht für andere Programme oder den ganzen PC. "
                                "Eine Grafikkarten-Begrenzung gibt es nicht, weil das Programm die GPU nicht nutzt.",
                     text_color=theme.MUTED, anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(0, 8))

        self.e_dl = self._field(body, "Download-Limit (KB/s)", str(s["dl_limit_kbps"]), width=100)
        ctk.CTkLabel(body, text="0 = unbegrenzt. Gilt für Programm-Updates.", text_color=theme.MUTED, anchor="w").pack(fill="x")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="CPU-Priorität", width=150, anchor="w").pack(side="left")
        self.o_prio = ctk.CTkOptionMenu(row, values=["Normal", "Niedrig"], width=120)
        self.o_prio.set("Niedrig" if s["cpu_priority"] == "low" else "Normal")
        self.o_prio.pack(side="left")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="CPU-Kerne", width=150, anchor="w").pack(side="left")
        values = ["Alle"] + [str(i) for i in range(1, cores)]
        self.o_cores = ctk.CTkOptionMenu(row, values=values, width=120)
        self.o_cores.set(str(s["cpu_cores"]) if 0 < s["cpu_cores"] < cores else "Alle")
        self.o_cores.pack(side="left")

        self.e_ram = self._field(body, "RAM-Limit (MB)", str(s["ram_limit_mb"]), width=100)
        if not system_limits.IS_WIN:
            self.e_ram.configure(state="disabled")
        ctk.CTkLabel(body, text=f"0 = kein Limit. Nur unter Windows, mindestens {system_limits.MIN_RAM_MB} MB. "
                                "Zu niedrige Werte können zu Abstürzen führen.",
                     text_color=theme.MUTED, anchor="w", justify="left", wraplength=560).pack(fill="x")
        self.m_perf = self._msg(body)
        ctk.CTkButton(body, text="Speichern & anwenden", width=180, command=self._save_perf).pack(anchor="w", pady=(6, 0))

    def _refresh_info(self, cores, ram):
        used = system_limits.process_ram_mb()
        parts = [f"{cores} CPU-Kerne"]
        if ram:
            parts.append(f"{ram / 1024:.1f} GB RAM")
        text = "Dein PC: " + ", ".join(parts)
        if used:
            text += f"  ·  Dieses Programm belegt gerade {used} MB"
        self.info.configure(text=text)

    def _save_perf(self):
        try:
            dl = float(self.e_dl.get().strip() or 0)
            ram = int(float(self.e_ram.get().strip() or 0))
            if dl < 0 or ram < 0:
                raise ValueError
        except ValueError:
            self._say(self.m_perf, "Bitte nur Zahlen ab 0 eingeben.", False)
            return
        cores_txt = self.o_cores.get()
        s = self.app.settings
        s.update({"dl_limit_kbps": dl if dl % 1 else int(dl), "cpu_priority": "low" if self.o_prio.get() == "Niedrig" else "normal",
                  "cpu_cores": int(cores_txt) if cores_txt.isdigit() else 0, "ram_limit_mb": ram})
        config.save_settings(s)
        notes = self.app.apply_limits()
        self._refresh_info(system_limits.cpu_count(), system_limits.total_ram_mb())
        self._say(self.m_perf, "Gespeichert und angewendet." + ("\n" + "\n".join(notes) if notes else ""), not notes)

    # ---------- Info ----------
    def _build_about(self):
        body = self._card("Über")
        ctk.CTkLabel(body, text=f"{APP_NAME}  ·  Version {APP_VERSION}", anchor="w").pack(fill="x")
        ctk.CTkLabel(body, text=f"Daten liegen in: {config.app_dir()}", text_color=theme.MUTED, anchor="w",
                     wraplength=560, justify="left").pack(fill="x", pady=(2, 8))
        ctk.CTkButton(body, text="Nach Updates suchen", width=180, command=lambda: self.app.check_updates(manual=True)).pack(anchor="w")
