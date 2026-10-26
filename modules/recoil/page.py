import tkinter as tk

import customtkinter as ctk

from core import theme, ui
from core.i18n import tr

from .engine import LIMITS, PRESETS
from .plugin import WARNING

FIELDS = [("y", "Pull down (px per step)", 0.1), ("x", "Sideways (px per step, - = left)", 0.1),
          ("interval_ms", "Step interval (ms)", 1), ("ramp_pct", "Increase while held (%)", 5),
          ("ramp_ms", "Time to full increase (ms)", 50), ("delay_ms", "Start delay (ms)", 10)]


class RecoilPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color=theme.c("main"))
        self.plugin, self.app = plugin, plugin.app
        self.columnconfigure(0, weight=1)
        ui.page_title(self, "Recoil", "Universal – works with any shooter in theory, knows no game.").grid(
            row=0, column=0, sticky="w", padx=24, pady=(20, 8))
        # Unübersehbare Warnung direkt über dem Modul
        ui.banner(self, "⚠  " + WARNING, color="#b91c1c").grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))

        c = ui.card(self, "Safety")
        c.grid(row=2, column=0, sticky="ew", padx=24, pady=6)
        self.ack = tk.BooleanVar(value=plugin.acknowledged())
        ctk.CTkCheckBox(c, text=tr("I have read the warning and use this only offline for education and testing."),
                        variable=self.ack, command=self._ack_changed).pack(anchor="w", padx=16, pady=(0, 6))
        r = ui.row(c)
        r.pack(fill="x", padx=16, pady=(0, 12))
        self.on_var = tk.BooleanVar(value=plugin.enabled)
        self.sw = ctk.CTkSwitch(r, text=tr("Anti-recoil active (F8)"), variable=self.on_var, command=self._toggle)
        self.sw.pack(side="left")
        self.msg = ctk.CTkLabel(r, text="", text_color=theme.DANGER)
        self.msg.pack(side="left", padx=14)

        s = ui.card(self, "Settings")
        s.grid(row=3, column=0, sticky="ew", padx=24, pady=6)
        pr = ui.row(s)
        pr.pack(fill="x", padx=16, pady=(0, 6))
        for name in PRESETS:
            ctk.CTkButton(pr, text=tr(name), width=90, command=lambda n=name: self._preset(n)).pack(side="left", padx=(0, 6))
        self.vars = {}
        for key, label, _step in FIELDS:
            line = ui.row(s)
            line.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(line, text=tr(label), width=270, anchor="w").pack(side="left")
            v = tk.StringVar(value=str(getattr(plugin.cfg, key)))
            self.vars[key] = v
            e = ctk.CTkEntry(line, textvariable=v, width=90, justify="center")
            e.pack(side="left")
            e.bind("<FocusOut>", lambda _e: self._read())
            e.bind("<Return>", lambda _e: self._read())
            lo, hi = LIMITS[key]
            ctk.CTkLabel(line, text=f"{lo} … {hi}", text_color=theme.MUTED).pack(side="left", padx=10)
        ui.muted(s, "Games using raw mouse input may ignore simulated movement. There is no hiding or evasion in this tool.").pack(
            fill="x", padx=16, pady=(8, 12))

    def refresh(self):
        self.on_var.set(self.plugin.enabled)

    def _ack_changed(self):
        self.plugin.acknowledge(self.ack.get())
        if not self.ack.get():
            self.on_var.set(False)

    def _toggle(self):
        err = self.plugin.set_enabled(self.on_var.get())
        self.msg.configure(text=tr(err) if err else "")
        if err:
            self.on_var.set(False)

    def _preset(self, name):
        self.plugin.preset(name)
        for k, v in self.vars.items():
            v.set(str(getattr(self.plugin.cfg, k)))

    def _read(self):
        try:
            self.plugin.update(**{k: float(v.get().replace(",", ".")) for k, v in self.vars.items()})
        except ValueError:
            self.msg.configure(text=tr("Please enter numbers."))
            return
        self.msg.configure(text="")
        for k, v in self.vars.items():
            v.set(str(getattr(self.plugin.cfg, k)))
