"""Einstellungen in Bereichen: Konto, Aussehen, Sprache, System, Leistung, Rechtliches & Quellen.
Jeder Bereich wird erst beim Öffnen aufgebaut (spart Speicher und Startzeit)."""
import datetime
import json
import threading
import tkinter as tk
import webbrowser
from tkinter import colorchooser, filedialog, messagebox

import customtkinter as ctk

from core import accounts, appicon, config, i18n, shortcuts, system_limits, theme, ui
from core.credits import CREDITS
from core.i18n import LANGS, tr
from core.identity import REMEMBER_CHOICES
from core.legal_text import legal_text
from core.login_view import days_to_setting, default_days, remember_label, remember_value
from core.version import APP_NAME, APP_VERSION, LEGAL_VERSION

SECTIONS = ["Account", "Appearance", "Language", "System", "Performance", "Legal & sources"]


class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"))
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ui.page_title(self, "Settings").grid(row=0, column=0, sticky="w", padx=24, pady=(20, 8))
        self.seg = ctk.CTkSegmentedButton(self, values=[tr(s) for s in SECTIONS], command=self._open)
        self.seg.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 6))
        self.area = None
        start = app.settings_section if app.settings_section in SECTIONS else "Account"
        self.seg.set(tr(start))
        self._open(tr(start))

    def _open(self, label):
        name = next((s for s in SECTIONS if tr(s) == label), "Account")
        self.app.settings_section = name
        if self.area is not None:
            self.area.destroy()
        self.area = ctk.CTkScrollableFrame(self, fg_color=theme.c("main"))
        self.area.grid(row=2, column=0, sticky="nsew")
        self.area.columnconfigure(0, weight=1)
        self._row = 0
        getattr(self, "_s_" + {"Legal & sources": "legal"}.get(name, name.lower()))()

    # ---------- Bausteine
    def _card(self, title):
        c = ui.card(self.area, title)
        c.grid(row=self._row, column=0, sticky="ew", padx=24, pady=6)
        self._row += 1
        body = ctk.CTkFrame(c, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))
        return body

    @staticmethod
    def _field(parent, label, value="", secret=False, width=260, lw=170):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=label, width=lw, anchor="w").pack(side="left")
        e = ctk.CTkEntry(r, width=width, show="•" if secret else "")
        e.pack(side="left")
        if value:
            e.insert(0, value)
        return e

    def _msg(self, parent):
        lab = ctk.CTkLabel(parent, text="", anchor="w", justify="left", wraplength=620)
        lab.pack(fill="x", pady=(4, 0))
        return lab

    @staticmethod
    def _say(label, text, ok=True):
        if label.winfo_exists():
            label.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _me(self):
        return self.app.user

    def _threaded(self, work, done, label):
        def run():
            try:
                res, err = work(), None
            except accounts.AccountError as exc:
                res, err = None, str(exc)
            except Exception as exc:
                res, err = None, f"{type(exc).__name__}: {exc}"
            self.app.call_soon(lambda: self.winfo_exists() and (self._say(label, tr(err), False) if err else done(res)))
        threading.Thread(target=run, daemon=True).start()

    # ======================= Konto =======================
    def _s_account(self):
        me, ident = self._me(), self.app.identity
        body = self._card("Profile")
        where = tr("Cloud account (Supabase, encrypted)") if me.get("backend") == "cloud" else tr("Local account (only on this computer)")
        ui.muted(body, "{u}  ·  {w}", u=me["username"] or "Google", w=where).pack(fill="x", pady=(0, 6))
        self.e_display = self._field(body, tr("Display name"), me["display_name"])
        self.e_mail = self._field(body, tr("E-mail (optional)"), me["email"])
        ui.muted(body, "E-mail and real name are optional. Leave the e-mail empty to stay anonymous.").pack(fill="x")
        self.m_prof = self._msg(body)
        ctk.CTkButton(body, text=tr("Save"), width=120, command=self._save_profile).pack(anchor="w", pady=(4, 0))

        body = self._card("Password")
        ui.banner(body, "🔒 " + tr("The password cannot be changed after the account has been created (security rule). "
                                   "There is no recovery – if you lose it, create a new account."), color="#92400e").pack(fill="x")

        body = self._card("Stay signed in")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkLabel(r, text=tr("Default duration"), width=170, anchor="w").pack(side="left")
        om = ctk.CTkOptionMenu(r, values=[tr(l) for l, _ in REMEMBER_CHOICES], width=190, command=self._set_remember)
        om.set(remember_label(default_days(self.app.settings)))
        om.pack(side="left")

        if ident.supports_2fa:
            body = self._card("Two-factor sign-in (2FA)")
            self.f2fa = ctk.CTkFrame(body, fg_color="transparent")
            self.f2fa.pack(fill="x")
            self.store = self.app.accounts
            self._render_2fa()

        body = self._card("Your data")
        ui.muted(body, "You can download everything stored about you, or delete the account for good.").pack(fill="x", pady=(0, 6))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkButton(r, text=tr("Export my data"), width=170, command=self._export).pack(side="left")
        self.e_del = self._field(body, tr("Password (to delete)"), secret=True) if me.get("has_password") and me.get("backend") == "local" else None
        self.m_del = self._msg(body)
        ctk.CTkButton(body, text=tr("Delete account"), width=170, fg_color="#b91c1c", hover_color="#7f1d1d",
                      command=self._delete_account).pack(anchor="w", pady=(6, 0))

    def _set_remember(self, label):
        self.app.settings["remember"] = days_to_setting(remember_value(label))
        self.app.save_settings()

    def _save_profile(self):
        d, m = self.e_display.get(), self.e_mail.get()
        me = self._me()

        def done(user):
            self.app.user = user
            self.app.refresh_user_labels()
            self._say(self.m_prof, tr("Saved."))
        self._threaded(lambda: self.app.identity.update_profile(me, d, m), done, self.m_prof)

    def _export(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="jopml-data.json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return

        def done(data):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            self._say(self.m_del, tr("Exported."))
        self._threaded(lambda: self.app.identity.export(self._me()), done, self.m_del)

    def _delete_account(self):
        if not messagebox.askyesno(tr("Delete account"), tr("Your account will be deleted permanently. This cannot be undone.\nContinue?")):
            return
        pw = self.e_del.get() if self.e_del else ""
        me = self._me()
        self._threaded(lambda: self.app.identity.delete(me, pw), lambda _: self.app.logout(forget=False), self.m_del)

    # ---- 2FA (nur lokale Konten)
    def _render_2fa(self, secret=None):
        for w in self.f2fa.winfo_children():
            w.destroy()
        me = self._me()
        self.m_2fa = self._msg(self.f2fa)
        if me["totp_enabled"]:
            ctk.CTkLabel(self.f2fa, text="✔ " + tr("2FA is active."), text_color=theme.OK, anchor="w").pack(fill="x")
            self.e_2fa_pw = self._field(self.f2fa, tr("Password"), secret=True) if me["has_password"] else None
            ctk.CTkButton(self.f2fa, text=tr("Turn off 2FA"), width=160, fg_color="gray35", hover_color="gray25",
                          command=self._disable_2fa).pack(anchor="w", pady=(4, 0))
        elif secret:
            pretty = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))
            ctk.CTkLabel(self.f2fa, anchor="w", justify="left", wraplength=600,
                         text=tr("1. Open an authenticator app.\n2. Choose 'Enter key manually' and type this key:")).pack(fill="x")
            key = ctk.CTkEntry(self.f2fa, width=420, font=ctk.CTkFont(family="Consolas", size=15))
            key.insert(0, pretty)
            key.configure(state="readonly")
            key.pack(anchor="w", pady=4)
            ctk.CTkButton(self.f2fa, text=tr("Copy key"), width=160, command=lambda: self._copy(secret)).pack(anchor="w", pady=(0, 6))
            self.e_2fa_code = self._field(self.f2fa, tr("6-digit code"))
            r = ctk.CTkFrame(self.f2fa, fg_color="transparent")
            r.pack(anchor="w", pady=(4, 0))
            ctk.CTkButton(r, text=tr("Confirm"), width=120, command=self._confirm_2fa).pack(side="left")
            ctk.CTkButton(r, text=tr("Cancel"), width=120, fg_color="gray35", hover_color="gray25",
                          command=self._render_2fa).pack(side="left", padx=8)
        else:
            ui.muted(self.f2fa, "Protects your account additionally with a code from an authenticator app.").pack(fill="x")
            ctk.CTkButton(self.f2fa, text=tr("Set up 2FA"), width=160, command=self._start_2fa).pack(anchor="w", pady=(6, 0))

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._say(self.m_2fa, tr("Copied."))

    def _start_2fa(self):
        try:
            self._render_2fa(self.store.begin_totp(self._me()["username"]))
        except accounts.AccountError as exc:
            self._say(self.m_2fa, tr(str(exc)), False)

    def _confirm_2fa(self):
        try:
            self.store.confirm_totp(self._me()["username"], self.e_2fa_code.get())
        except accounts.AccountError as exc:
            self._say(self.m_2fa, tr(str(exc)), False)
            return
        self.app.user = self.store.public(self.store.users[self._me()["username"]])
        self._render_2fa()
        self._say(self.m_2fa, tr("2FA is now active. The code is asked at the next sign-in."))

    def _disable_2fa(self):
        pw = self.e_2fa_pw.get() if self.e_2fa_pw else ""

        def done(_):
            self.app.user = self.store.public(self.store.users[self._me()["username"]])
            self._render_2fa()
            self._say(self.m_2fa, tr("2FA was turned off."))
        self._threaded(lambda: self.store.disable_totp(self._me()["username"], pw), done, self.m_2fa)

    # ======================= Aussehen =======================
    def _s_appearance(self):
        s = self.app.settings
        body = self._card("Theme")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("Mode"), width=170, anchor="w").pack(side="left")
        seg = ctk.CTkSegmentedButton(r, values=[tr(k) for k in theme.MODES],
                                     command=lambda lab: self.app.apply_look({"appearance_mode": next(v for k, v in theme.MODES.items() if tr(k) == lab)}))
        seg.set(tr(next((k for k, v in theme.MODES.items() if v == s["appearance_mode"]), "Dark")))
        seg.pack(side="left")

        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkLabel(r, text=tr("Presets"), width=170, anchor="w").pack(side="left")
        for name in theme.PRESETS:
            ctk.CTkButton(r, text=tr(name), width=80, height=28, fg_color=theme.c("hover"), text_color=theme.TEXT,
                          command=lambda n=name: self._preset(n)).pack(side="left", padx=3)

        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkLabel(r, text=tr("Accent colour"), width=170, anchor="w").pack(side="left")
        for name, hx in theme.ACCENTS.items():
            ring = "white" if hx.lower() == s["accent"].lower() else hx
            ctk.CTkButton(r, text="✔" if ring == "white" else "", width=30, height=30, corner_radius=15, fg_color=hx,
                          hover_color=theme.shade(hx, 0.8), border_width=2, border_color=ring,
                          command=lambda h=hx: self.app.apply_look({"accent": h})).pack(side="left", padx=2)
        ctk.CTkButton(r, text=tr("Pick …"), width=70, height=30, command=lambda: self._pick("accent")).pack(side="left", padx=8)

        body = self._card("Your own colours (colour picker)")
        colors = s.get("colors") or {}
        defaults = {"main": theme.DEFAULT_PALETTE["main"][1], "sidebar": theme.DEFAULT_PALETTE["sidebar"][1],
                    "card": theme.DEFAULT_PALETTE["card"][1], "inset": theme.DEFAULT_PALETTE["inset"][1],
                    "hover": theme.DEFAULT_PALETTE["hover"][1], "text": "#e6e6e6"}
        for label, key in theme.COLOR_KEYS:
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=tr(label), width=170, anchor="w").pack(side="left")
            cur = colors.get(key) or defaults[key]
            ctk.CTkButton(r, text="", width=44, height=26, fg_color=cur, hover_color=cur, border_width=1,
                          border_color="gray50", command=lambda k=key: self._pick(k)).pack(side="left")
            e = ctk.CTkEntry(r, width=100, placeholder_text="#rrggbb")
            e.insert(0, colors.get(key, ""))
            e.pack(side="left", padx=8)
            e.bind("<Return>", lambda _e, k=key, ent=e: self._set_hex(k, ent.get()))
            ctk.CTkButton(r, text=tr("Reset"), width=70, height=26, fg_color="gray35", hover_color="gray25",
                          command=lambda k=key: self._reset_color(k)).pack(side="left")
        self.m_look = self._msg(body)
        ctk.CTkButton(body, text=tr("Reset all colours"), width=170, fg_color="gray35", hover_color="gray25",
                      command=lambda: self._preset("Default")).pack(anchor="w", pady=(8, 0))

        body = self._card("App icon")
        self.icon_preview = ctk.CTkLabel(body, text="")
        self.icon_preview.pack(side="left", padx=(0, 16))
        col = ctk.CTkFrame(body, fg_color="transparent")
        col.pack(side="left", fill="x")
        ui.muted(col, "Change the background of the icon. The letters JOPML always stay visible.", wrap=440).pack(fill="x")
        r = ctk.CTkFrame(col, fg_color="transparent")
        r.pack(fill="x", pady=6)
        ctk.CTkButton(r, text=tr("Background colour …"), width=170, command=lambda: self._pick("icon_bg")).pack(side="left")
        ctk.CTkButton(r, text=tr("Background image …"), width=170, command=self._icon_image).pack(side="left", padx=6)
        ctk.CTkButton(r, text=tr("Reset"), width=80, fg_color="gray35", hover_color="gray25",
                      command=self._icon_reset).pack(side="left")
        self._draw_icon_preview()

    def _preset(self, name):
        p = theme.PRESETS[name]
        self.app.apply_look({"appearance_mode": p["mode"], "accent": p["accent"], "colors": dict(p["colors"])})

    def _pick(self, key):
        s = self.app.settings
        start = {"accent": s["accent"], "icon_bg": s.get("icon_bg", "#4f8cff")}.get(key) or (s.get("colors") or {}).get(key)
        rgb, hx = colorchooser.askcolor(color=start if theme.is_hex(start) else None, parent=self, title=tr("Pick a colour"))
        if hx:
            self._set_hex(key, hx)

    def _set_hex(self, key, value):
        value = (value or "").strip()
        if value and not value.startswith("#"):
            value = "#" + value
        if not theme.is_hex(value):
            if hasattr(self, "m_look") and self.m_look.winfo_exists():
                self._say(self.m_look, tr("Please enter a colour like #4f8cff."), False)
            return
        value = value.lower()
        if key == "accent":
            self.app.apply_look({"accent": value})
        elif key == "icon_bg":
            self.app.settings["icon_bg"], self.app.settings["icon_image"] = value, ""
            self._apply_icon()
        else:
            colors = dict(self.app.settings.get("colors") or {})
            colors[key] = value
            self.app.apply_look({"colors": colors})

    def _reset_color(self, key):
        colors = dict(self.app.settings.get("colors") or {})
        colors.pop(key, None)
        self.app.apply_look({"colors": colors})

    def _icon_image(self):
        path = filedialog.askopenfilename(filetypes=[(tr("Images"), "*.png *.jpg *.jpeg *.bmp *.gif")])
        if path:
            self.app.settings["icon_image"] = path
            self._apply_icon()

    def _icon_reset(self):
        self.app.settings.update({"icon_bg": "#4f8cff", "icon_image": ""})
        self._apply_icon()

    def _apply_icon(self):
        self.app.save_settings()
        appicon.apply_to_window(self.app, self.app.settings)
        self._draw_icon_preview()

    def _draw_icon_preview(self):
        try:
            img = appicon.render(96, self.app.settings.get("icon_bg"), self.app.settings.get("icon_image") or None)
            self._icon_img = ctk.CTkImage(light_image=img, dark_image=img, size=(72, 72))
            self.icon_preview.configure(image=self._icon_img)
        except Exception as exc:
            self.icon_preview.configure(text=str(exc))

    # ======================= Sprache =======================
    def _s_language(self):
        body = self._card("Language")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        ctk.CTkLabel(r, text=tr("Language"), width=170, anchor="w").pack(side="left")
        om = ctk.CTkOptionMenu(r, values=list(LANGS.values()), width=190,
                               command=lambda lab: self.app.set_language(next(c for c, n in LANGS.items() if n == lab)))
        om.set(LANGS[i18n.get_language()])
        om.pack(side="left")
        ui.muted(body, "Menus and buttons are translated. The long legal text exists in German (authoritative) and English only.").pack(fill="x", pady=(8, 0))

    # ======================= System =======================
    def _s_system(self):
        body = self._card("Shortcut and autostart")
        self.m_sys = self._msg(body)
        v1 = tk.BooleanVar(value=self._safe(shortcuts.has_desktop_shortcut))
        v2 = tk.BooleanVar(value=self._safe(shortcuts.is_autostart))

        def toggle_short():
            try:
                shortcuts.create_desktop_shortcut() if v1.get() else shortcuts.remove_desktop_shortcut()
                self._say(self.m_sys, tr("Done."))
            except Exception as exc:
                v1.set(not v1.get())
                self._say(self.m_sys, str(exc), False)

        def toggle_auto():
            try:
                shortcuts.set_autostart(v2.get())
                self._say(self.m_sys, tr("Done."))
            except Exception as exc:
                v2.set(not v2.get())
                self._say(self.m_sys, str(exc), False)

        ctk.CTkSwitch(body, text=tr("Desktop shortcut"), variable=v1, command=toggle_short).pack(anchor="w", pady=4)
        ctk.CTkSwitch(body, text=tr("Start with the computer (autostart)"), variable=v2, command=toggle_auto).pack(anchor="w", pady=4)

        body = self._card("About")
        ctk.CTkLabel(body, text=f"{APP_NAME}  ·  {tr('Version')} {APP_VERSION}", anchor="w").pack(fill="x")
        ui.muted(body, "Data folder: {p}", p=str(config.app_dir())).pack(fill="x", pady=(2, 8))
        ctk.CTkButton(body, text=tr("Check for updates"), width=170, command=lambda: self.app.check_updates(manual=True)).pack(anchor="w")

    @staticmethod
    def _safe(fn):
        try:
            return bool(fn())
        except Exception:
            return False

    # ======================= Leistung =======================
    def _s_performance(self):
        body = self._card("Performance & throttling")
        s = self.app.settings
        ram, cores = system_limits.total_ram_mb(), system_limits.cpu_count()
        self.info = ctk.CTkLabel(body, text_color=theme.MUTED, anchor="w", justify="left", wraplength=620)
        self.info.pack(fill="x", pady=(0, 6))
        self._refresh_info(cores, ram)
        ui.muted(body, "These limits apply only to this program, not to other programs or the whole PC. There is no GPU limit because the program does not use the graphics card.").pack(fill="x", pady=(0, 8))
        self.e_dl = self._field(body, tr("Download limit (KB/s)"), str(s["dl_limit_kbps"]), width=100)
        ui.muted(body, "0 = unlimited. Applies to program updates.").pack(fill="x")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("CPU priority"), width=170, anchor="w").pack(side="left")
        self.o_prio = ctk.CTkOptionMenu(r, values=[tr("Normal"), tr("Low")], width=120)
        self.o_prio.set(tr("Low") if s["cpu_priority"] == "low" else tr("Normal"))
        self.o_prio.pack(side="left")
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=tr("CPU cores"), width=170, anchor="w").pack(side="left")
        self.o_cores = ctk.CTkOptionMenu(r, values=[tr("All")] + [str(i) for i in range(1, cores)], width=120)
        self.o_cores.set(str(s["cpu_cores"]) if 0 < s["cpu_cores"] < cores else tr("All"))
        self.o_cores.pack(side="left")
        self.e_ram = self._field(body, tr("RAM limit (MB)"), str(s["ram_limit_mb"]), width=100)
        if not system_limits.IS_WIN:
            self.e_ram.configure(state="disabled")
        ui.muted(body, "0 = no limit. Windows only, at least {n} MB. Too low values can crash the program.", n=system_limits.MIN_RAM_MB).pack(fill="x")
        self.m_perf = self._msg(body)
        ctk.CTkButton(body, text=tr("Save & apply"), width=180, command=self._save_perf).pack(anchor="w", pady=(6, 0))

    def _refresh_info(self, cores, ram):
        used = system_limits.process_ram_mb()
        text = tr("Your PC: {c} CPU cores", c=cores) + (f", {ram / 1024:.1f} GB RAM" if ram else "")
        if used:
            text += "  ·  " + tr("This program currently uses {n} MB", n=used)
        self.info.configure(text=text)

    def _save_perf(self):
        try:
            dl = float(self.e_dl.get().strip() or 0)
            ram = int(float(self.e_ram.get().strip() or 0))
            if dl < 0 or ram < 0:
                raise ValueError
        except ValueError:
            self._say(self.m_perf, tr("Please enter numbers from 0."), False)
            return
        cores_txt = self.o_cores.get()
        s = self.app.settings
        s.update({"dl_limit_kbps": dl if dl % 1 else int(dl), "cpu_priority": "low" if self.o_prio.get() == tr("Low") else "normal",
                  "cpu_cores": int(cores_txt) if cores_txt.isdigit() else 0, "ram_limit_mb": ram})
        self.app.save_settings()
        notes = self.app.apply_limits()
        self._refresh_info(system_limits.cpu_count(), system_limits.total_ram_mb())
        self._say(self.m_perf, tr("Saved and applied.") + ("\n" + "\n".join(notes) if notes else ""), not notes)

    # ======================= Rechtliches & Quellen =======================
    def _s_legal(self):
        s = self.app.settings
        body = self._card("Your agreement")
        when = datetime.datetime.fromtimestamp(s.get("legal_accepted_at") or 0).strftime("%Y-%m-%d %H:%M") if s.get("legal_accepted_at") else "–"
        ui.banner(body, "✔ " + tr("You have legally bindingly agreed to the terms of use and the disclaimer on {d} (version {v}).",
                                  d=when, v=s.get("legal_version") or LEGAL_VERSION) + "\n" + tr("No copyright / public domain."),
                  color="#166534").pack(fill="x")
        ctk.CTkButton(body, text=tr("Read the terms again"), width=190, command=self._show_terms).pack(anchor="w", pady=(10, 0))

        body = self._card("Credits & sources")
        ui.muted(body, "There is no imprint and no contact person (anonymous project). The following technologies are used; all names belong to their owners. None of these companies supports, endorses or is liable for this project.").pack(fill="x", pady=(0, 6))
        for name, role, lic, url in CREDITS:
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x")
            ctk.CTkLabel(r, text=f"{name} – {tr(role)} · {lic}", font=ctk.CTkFont(size=11), text_color=theme.MUTED,
                         anchor="w", wraplength=520, justify="left").pack(side="left")
            ctk.CTkButton(r, text="↗", width=26, height=20, fg_color="transparent", text_color=theme.accent(),
                          hover_color=theme.c("hover"), command=lambda u=url: webbrowser.open(u)).pack(side="right")

    def _show_terms(self):
        top = ctk.CTkToplevel(self)
        top.title(tr("Terms of use and disclaimer"))
        top.geometry("820x640")
        box = ctk.CTkTextbox(top, font=ctk.CTkFont(family="Consolas", size=12), wrap="word")
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", legal_text(i18n.get_language()))
        box.configure(state="disabled")
        top.after(80, top.lift)
