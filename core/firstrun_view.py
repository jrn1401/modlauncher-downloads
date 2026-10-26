"""Erststart: Sprache -> Rechtstext (Zustimmung zwingend, sonst Beenden) -> Verknüpfung/Autostart-Angebot."""
import time
import tkinter as tk

import customtkinter as ctk

from core import config, i18n, shortcuts, theme
from core.i18n import LANGS, tr
from core.legal_text import legal_hash, legal_text
from core.version import APP_NAME, LEGAL_VERSION

SMALL, LARGE = 10, 14          # Schriftgröße des Rechtstextes (Vorgabe: 10; per Knopf vergrößerbar)


def record_acceptance(settings: dict) -> None:
    settings.update({"legal_version": LEGAL_VERSION, "legal_hash": legal_hash(), "legal_accepted_at": int(time.time())})
    config.save_settings(settings)


def needs_legal(settings: dict) -> bool:
    return settings.get("legal_version") != LEGAL_VERSION


def at_bottom(first_last: tuple) -> bool:
    """Textfeld nachweislich ganz unten? (yview() liefert (oben, unten) als Anteile 0..1.)"""
    return float(first_last[1]) >= 0.999


class FirstRunView(ctk.CTkFrame):
    """mode='full': Sprache + Recht + Extras (erster Start). mode='legal': nur Recht (neue Fassung)."""

    def __init__(self, parent, app, mode: str, on_done):
        super().__init__(parent, fg_color=theme.c("main"), corner_radius=0)
        self.app, self.mode, self.on_done = app, mode, on_done
        self.bottom_reached = False
        self.big = False
        self._polling = True
        self._legal_step()

    # ---------- Schritt 1: Sprache + Rechtstext
    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _legal_step(self):
        self._clear()
        self.bottom_reached = False
        s = self.app.settings
        wrap = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=16, border_width=2, border_color=theme.accent())
        wrap.pack(fill="both", expand=True, padx=28, pady=24)
        head = ctk.CTkFrame(wrap, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=(18, 4))
        ctk.CTkLabel(head, text=f"{APP_NAME}", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        lang = ctk.CTkOptionMenu(head, values=list(LANGS.values()), width=150, command=self._lang_changed)
        lang.set(LANGS.get(i18n.get_language(), "English"))
        lang.pack(side="right")
        ctk.CTkLabel(head, text=tr("Language") + ":", text_color=theme.MUTED).pack(side="right", padx=8)

        ctk.CTkLabel(wrap, text="⚖  " + tr("Terms of use and disclaimer – please read to the end"),
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="#f59e0b").pack(anchor="w", padx=24, pady=(6, 2))
        self.hint = ctk.CTkLabel(wrap, text=tr("The checkbox unlocks after you scrolled to the end of the text. "
                                               "If you decline, the program closes immediately."),
                                 text_color=theme.MUTED, anchor="w", wraplength=900, justify="left")
        self.hint.pack(fill="x", padx=24)

        self.box = ctk.CTkTextbox(wrap, font=ctk.CTkFont(family="Consolas", size=SMALL), wrap="word",
                                  fg_color=theme.c("inset"), border_width=1, border_color=("gray60", "gray30"))
        self.box.pack(fill="both", expand=True, padx=24, pady=10)
        self.box.insert("1.0", legal_text(i18n.get_language()))
        self.box.configure(state="disabled")
        self.box.bind("<MouseWheel>", lambda _e: self.after(30, self._check_bottom))
        self.box.bind("<Button-4>", lambda _e: self.after(30, self._check_bottom))
        self.box.bind("<Button-5>", lambda _e: self.after(30, self._check_bottom))
        self.box.bind("<KeyRelease>", lambda _e: self._check_bottom())
        self.box.bind("<ButtonRelease-1>", lambda _e: self.after(30, self._check_bottom))

        self.agree = tk.BooleanVar(value=False)
        self.check = ctk.CTkCheckBox(wrap, text=tr("I have read the terms completely and agree to them (legally binding)."),
                                     variable=self.agree, command=self._agree_changed, state="disabled")
        self.check.pack(anchor="w", padx=24, pady=(2, 10))
        bar = ctk.CTkFrame(wrap, fg_color="transparent")
        bar.pack(fill="x", padx=24, pady=(0, 18))
        ctk.CTkButton(bar, text=tr("Decline and exit"), width=170, fg_color="#b91c1c", hover_color="#7f1d1d",
                      command=self.app.exit_now).pack(side="left")
        ctk.CTkButton(bar, text="A+", width=44, fg_color="gray35", hover_color="gray25", command=self._bigger).pack(side="left", padx=10)
        self.accept = ctk.CTkButton(bar, text=tr("Accept"), width=170, state="disabled", command=self._accept)
        self.accept.pack(side="right")
        self.after(300, self._poll)

    def _lang_changed(self, label):
        code = next((c for c, n in LANGS.items() if n == label), "en")
        i18n.set_language(code)
        self.app.settings["language"] = code
        config.save_settings(self.app.settings)
        self._legal_step()

    def _bigger(self):
        self.big = not self.big
        self.box.configure(font=ctk.CTkFont(family="Consolas", size=LARGE if self.big else SMALL))
        self.after(50, self._check_bottom)

    def _check_bottom(self):
        if self.bottom_reached or not self.winfo_exists():
            return
        try:
            if self.box.winfo_height() > 20 and at_bottom(self.box.yview()):
                self.bottom_reached = True
                self.check.configure(state="normal")
                self.hint.configure(text=tr("You reached the end. Tick the checkbox to enable 'Accept'."), text_color=theme.OK)
        except Exception:
            pass

    def _poll(self):
        if not self.winfo_exists() or self.bottom_reached:
            return
        self._check_bottom()
        self.after(400, self._poll)

    def _agree_changed(self):
        ok = self.agree.get() and self.bottom_reached
        self.accept.configure(state="normal" if ok else "disabled")

    def _accept(self):
        if not (self.agree.get() and self.bottom_reached):
            return
        record_acceptance(self.app.settings)
        if self.mode == "full":
            self._extras_step()
        else:
            self.on_done()

    # ---------- Schritt 2: Verknüpfung + Autostart
    def _extras_step(self):
        self._clear()
        wrap = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=16)
        wrap.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(wrap, text=tr("Almost done"), font=ctk.CTkFont(size=24, weight="bold")).pack(padx=40, pady=(28, 4))
        ctk.CTkLabel(wrap, text=tr("Both options are optional and can be changed later in Settings → System."),
                     text_color=theme.MUTED, wraplength=420).pack(padx=30)
        self.v_short = tk.BooleanVar(value=False)
        self.v_auto = tk.BooleanVar(value=False)
        ctk.CTkSwitch(wrap, text=tr("Create a desktop shortcut"), variable=self.v_short).pack(anchor="w", padx=50, pady=(22, 6))
        ctk.CTkSwitch(wrap, text=tr("Start with the computer (autostart)"), variable=self.v_auto).pack(anchor="w", padx=50, pady=6)
        self.extra_msg = ctk.CTkLabel(wrap, text="", text_color=theme.DANGER, wraplength=420)
        self.extra_msg.pack(padx=30)
        ctk.CTkButton(wrap, text=tr("Continue"), width=200, command=self._finish_extras).pack(pady=(14, 28))

    def _finish_extras(self):
        errors = []
        try:
            if self.v_short.get():
                shortcuts.create_desktop_shortcut()
        except Exception as exc:
            errors.append(f"{tr('Desktop shortcut')}: {exc}")
        try:
            if self.v_auto.get():
                shortcuts.set_autostart(True)
        except Exception as exc:
            errors.append(f"{tr('Autostart')}: {exc}")
        self.app.settings["first_run_done"] = True
        config.save_settings(self.app.settings)
        if errors:
            self.extra_msg.configure(text="\n".join(errors) + "\n" + tr("You can try again in Settings → System."))
            self.after(2500, self.on_done)
        else:
            self.on_done()
