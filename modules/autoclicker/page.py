"""UI-Seite des Auto-Clickers (reine Ansicht auf das Plugin-Objekt)."""
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import theme

from . import keys
from .plugin import build_config

BG_CARD = theme.c("card")
MOUSE_LABELS = {v: k for k, v in keys.MOUSE_BUTTONS.items()}   # Anzeige -> left/right/middle
UNIT_LABELS = {"Sekunden": "s", "Minuten": "min", "Stunden": "h"}


class AutoClickerPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color=theme.c("main"))
        self.plugin, self.app = plugin, plugin.app
        self._loading = True
        self._capture = None
        self._input_error = ""
        self.columnconfigure(0, weight=1)
        v = self.v = {}
        for name in ("name", "kind", "mouse", "key", "ms", "s", "min", "repeat_mode", "repeat_count",
                     "timer_value", "timer_unit", "start_delay", "hk_start", "hk_stop"):
            v[name] = tk.StringVar()
        v["timer_enabled"] = tk.BooleanVar()

        ctk.CTkLabel(self, text="Jaron Op Makro", font=ctk.CTkFont(size=26, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(20, 8))

        self._build_profile_card(1)
        self._build_target_card(2)
        self._build_timing_card(3)
        self._build_repeat_card(4)
        self._build_hotkey_card(5)
        self._build_control_card(6)

        self.fill_from_profile(plugin.profile)
        self._loading = False
        for var in v.values():
            var.trace_add("write", lambda *_: self.apply())
        self._tick()

    # ---------- UI-Bausteine ----------
    def _card(self, row, title):
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        card.grid(row=row, column=0, sticky="ew", padx=24, pady=6)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, columnspan=8, sticky="w", padx=16, pady=(12, 6))
        return card

    def _build_profile_card(self, row):
        c = self._card(row, "Profil")
        ctk.CTkEntry(c, textvariable=self.v["name"], width=220).grid(row=1, column=0, padx=(16, 8), pady=(0, 14))
        ctk.CTkButton(c, text="Speichern …", width=110, command=self.save_profile).grid(row=1, column=1, padx=4, pady=(0, 14))
        ctk.CTkButton(c, text="Laden …", width=110, command=self.load_profile).grid(row=1, column=2, padx=4, pady=(0, 14))

    def _build_target_card(self, row):
        c = self._card(row, "Ziel-Taste")
        self.kind_seg = ctk.CTkSegmentedButton(c, values=["Maus", "Tastatur"], command=self._kind_changed)
        self.kind_seg.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")
        self.mouse_menu = ctk.CTkOptionMenu(c, values=list(MOUSE_LABELS), variable=self.v["mouse"], width=200)
        self.key_box = ctk.CTkFrame(c, fg_color="transparent")
        ctk.CTkComboBox(self.key_box, values=keys.COMMON_KEYS, variable=self.v["key"], width=120).pack(side="left")
        self.key_btn = ctk.CTkButton(self.key_box, text="Taste aufnehmen", width=140,
                                     command=lambda: self._capture_start("key"))
        self.key_btn.pack(side="left", padx=8)
        self.mouse_menu.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")
        self.key_box.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")

    def _entry(self, parent, var, width=70):
        return ctk.CTkEntry(parent, textvariable=var, width=width, justify="center")

    def _build_timing_card(self, row):
        c = self._card(row, "Klick-Intervall")
        for col, (key, label) in enumerate((("min", "Minuten"), ("s", "Sekunden"), ("ms", "Millisekunden"))):
            f = ctk.CTkFrame(c, fg_color="transparent")
            f.grid(row=1, column=col, padx=(16 if col == 0 else 6, 6), pady=(0, 6))
            self._entry(f, self.v[key]).pack()
            ctk.CTkLabel(f, text=label, text_color=theme.MUTED).pack()
        f = ctk.CTkFrame(c, fg_color="transparent")
        f.grid(row=1, column=3, padx=(24, 6), pady=(0, 6))
        self._entry(f, self.v["start_delay"]).pack()
        ctk.CTkLabel(f, text="Startverzögerung (s)", text_color=theme.MUTED).pack()
        ctk.CTkLabel(c, text="Minimum: 1 ms. Sehr kurze Intervalle sind abhängig von Betriebssystem und Zielprogramm.",
                     text_color=theme.MUTED).grid(row=2, column=0, columnspan=8, sticky="w", padx=16, pady=(0, 12))

    def _build_repeat_card(self, row):
        c = self._card(row, "Wiederholungen & Timer")
        ctk.CTkRadioButton(c, text="Unendlich wiederholen (bis Stop)", variable=self.v["repeat_mode"],
                           value="infinite").grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=4)
        ctk.CTkRadioButton(c, text="Wiederholen:", variable=self.v["repeat_mode"], value="count").grid(
            row=2, column=0, sticky="w", padx=16, pady=4)
        self._entry(c, self.v["repeat_count"]).grid(row=2, column=1, padx=4)
        ctk.CTkLabel(c, text="mal").grid(row=2, column=2, sticky="w")
        ctk.CTkSwitch(c, text="Laufzeit begrenzen:", variable=self.v["timer_enabled"]).grid(
            row=3, column=0, sticky="w", padx=16, pady=(8, 14))
        self._entry(c, self.v["timer_value"]).grid(row=3, column=1, padx=4, pady=(8, 14))
        ctk.CTkOptionMenu(c, values=list(UNIT_LABELS), variable=self.v["timer_unit"], width=110).grid(
            row=3, column=2, padx=4, pady=(8, 14))

    def _build_hotkey_card(self, row):
        c = self._card(row, "Globale Hotkeys (funktionieren auch im Hintergrund)")
        self.hk_labels = {}
        for r, (key, label) in enumerate((("hk_start", "Start"), ("hk_stop", "Stop")), start=1):
            ctk.CTkLabel(c, text=label, width=50, anchor="w").grid(row=r, column=0, padx=(16, 4), pady=4)
            lab = ctk.CTkLabel(c, text="", width=170, fg_color=theme.c("inset"), corner_radius=6)
            lab.grid(row=r, column=1, padx=4)
            self.hk_labels[key] = lab
            ctk.CTkButton(c, text="Aufnehmen", width=100,
                          command=lambda k=key: self._capture_start(k)).grid(row=r, column=2, padx=8)
        ctk.CTkLabel(c, text="Start = Stop → eine Taste schaltet um (Toggle). Beispiele: F6, Strg+Alt+P.",
                     text_color=theme.MUTED).grid(row=3, column=0, columnspan=8, sticky="w", padx=16, pady=(4, 12))
        self.hk_err = ctk.CTkLabel(c, text="", text_color=theme.DANGER, wraplength=600, justify="left")
        self.hk_err.grid(row=4, column=0, columnspan=8, sticky="w", padx=16)

    def _build_control_card(self, row):
        c = self._card(row, "Steuerung")
        ctk.CTkButton(c, text="▶  Start", width=130, fg_color="#2e9d5b", hover_color="#247a47",
                      command=self.start).grid(row=1, column=0, padx=(16, 6), pady=(0, 8))
        ctk.CTkButton(c, text="■  Stop", width=130, fg_color="#c0392b", hover_color="#962d22",
                      command=self.plugin.stop).grid(row=1, column=1, padx=6, pady=(0, 8))
        self.status = ctk.CTkLabel(c, text="Bereit", font=ctk.CTkFont(size=14, weight="bold"))
        self.status.grid(row=1, column=2, padx=20, pady=(0, 8), sticky="w")
        self.stats = ctk.CTkLabel(c, text="", text_color="gray")
        self.stats.grid(row=2, column=0, columnspan=8, sticky="w", padx=16, pady=(0, 12))

    # ---------- Formular <-> Profil ----------
    def fill_from_profile(self, p):
        self._loading = True
        v = self.v
        v["name"].set(p["name"])
        kind, _, name = p["target"].partition(":")
        v["kind"].set(kind)
        v["mouse"].set(keys.MOUSE_BUTTONS.get(name, "Linke Maustaste") if kind == "mouse" else "Linke Maustaste")
        v["key"].set(name if kind == "key" else "e")
        for k in ("ms", "s", "min"):
            v[k].set(str(p["interval"][k]))
        v["repeat_mode"].set(p["repeat_mode"])
        v["repeat_count"].set(str(p["repeat_count"]))
        v["timer_enabled"].set(bool(p["timer_enabled"]))
        v["timer_value"].set(str(p["timer_value"]))
        v["timer_unit"].set({"s": "Sekunden", "min": "Minuten", "h": "Stunden"}.get(p["timer_unit"], "Minuten"))
        v["start_delay"].set(str(p["start_delay"]))
        v["hk_start"].set(p["hotkey_start"])
        v["hk_stop"].set(p["hotkey_stop"])
        self.kind_seg.set("Maus" if kind == "mouse" else "Tastatur")
        self._show_kind(kind)
        self._refresh_hotkey_labels()
        self._loading = False

    def read_form(self) -> dict:
        v = self.v
        if self.kind_seg.get() == "Maus":
            target = f"mouse:{MOUSE_LABELS.get(v['mouse'].get(), 'left')}"
        else:
            target = f"key:{v['key'].get().strip()}"
        return {
            "name": v["name"].get().strip() or "Profil",
            "target": target,
            "interval": {k: v[k].get().strip() or "0" for k in ("ms", "s", "min")},
            "repeat_mode": v["repeat_mode"].get(),
            "repeat_count": v["repeat_count"].get().strip() or "0",
            "timer_enabled": v["timer_enabled"].get(),
            "timer_value": v["timer_value"].get().strip() or "0",
            "timer_unit": UNIT_LABELS.get(v["timer_unit"].get(), "min"),
            "start_delay": v["start_delay"].get().strip() or "0",
            "hotkey_start": v["hk_start"].get(),
            "hotkey_stop": v["hk_stop"].get(),
        }

    def apply(self) -> str:
        """Übernimmt das Formular ins Plugin. Gibt Fehlertext oder '' zurück."""
        if self._loading:
            return ""
        self._refresh_hotkey_labels()
        prof = self.read_form()
        try:
            build_config(prof)
        except ValueError as exc:
            self._input_error = f"Eingabe: {exc}"
            return str(exc)
        self._input_error = ""
        # Zahlen normalisieren, damit gespeicherte Profile saubere Werte enthalten
        prof["interval"] = {k: float(x) if "." in str(x) else int(float(x)) for k, x in prof["interval"].items()}
        prof["repeat_count"] = int(float(prof["repeat_count"]))
        prof["timer_value"] = float(prof["timer_value"])
        prof["start_delay"] = float(prof["start_delay"])
        self.plugin.set_profile(prof)
        self.hk_err.configure(text=self.plugin.hotkey_error)
        return ""

    # ---------- Interaktion ----------
    def _kind_changed(self, label):
        self._show_kind("mouse" if label == "Maus" else "key")
        self.apply()

    def _show_kind(self, kind):
        if kind == "mouse":
            self.key_box.grid_remove()
            self.mouse_menu.grid()
        else:
            self.mouse_menu.grid_remove()
            self.key_box.grid()

    def _refresh_hotkey_labels(self):
        for key, lab in self.hk_labels.items():
            lab.configure(text=keys.pretty_hotkey(self.v[key].get()))

    def _capture_start(self, what):
        """what: 'key' (einzelne Ziel-Taste) oder 'hk_start' / 'hk_stop' (Kombination)."""
        if self._capture:
            self._capture.cancel()
        combo = what != "key"
        hint = "Drücke Tastenkombination … (Esc = Abbruch)" if combo else "Drücke eine Taste … (Esc = Abbruch)"
        target = self.key_btn if what == "key" else None
        if target:
            target.configure(text="Drücke Taste …")
        else:
            self.hk_labels[what].configure(text=hint)

        def done(result):
            self.app.call_soon(self._capture_done, what, result)

        self._capture = keys.KeyCapture(done, combo=combo)
        self._capture.start()

    def _capture_done(self, what, result):
        self._capture = None
        self.key_btn.configure(text="Taste aufnehmen")
        if result:
            self.v["key" if what == "key" else what].set(result)
        self._refresh_hotkey_labels()

    def start(self):
        err = self.apply()
        if err:
            return
        err = self.plugin.start()
        if err:
            self._input_error = f"Eingabe: {err}"

    # ---------- Profile ----------
    def save_profile(self):
        if self.apply():
            return
        name = self.plugin.profile["name"]
        path = filedialog.asksaveasfilename(
            initialdir=self.plugin.profiles_dir(), initialfile=f"{name}.json",
            defaultextension=".json", filetypes=[("Profil (JSON)", "*.json")])
        if path:
            self.plugin.save_profile_file(path)

    def load_profile(self):
        path = filedialog.askopenfilename(initialdir=self.plugin.profiles_dir(),
                                          filetypes=[("Profil (JSON)", "*.json")])
        if not path:
            return
        try:
            prof = self.plugin.load_profile_file(path)
            self.fill_from_profile(prof)
        except Exception as exc:
            messagebox.showerror("Profil laden", str(exc))
            return
        self.apply()

    # ---------- Statusanzeige ----------
    def _tick(self):
        if not self.winfo_exists():
            return
        eng = self.plugin.engine
        if self._input_error and not eng.running:
            self.status.configure(text=self._input_error, text_color=theme.DANGER)
        elif eng.state == eng.RUNNING:
            self.status.configure(text="● Läuft", text_color="#2ecc71")
        elif eng.state == eng.WAITING:
            self.status.configure(text="… Startverzögerung", text_color="#f1c40f")
        else:
            reasons = {"count": "Fertig (Wiederholungen erreicht)", "timer": "Fertig (Timer abgelaufen)",
                       "stopped": "Gestoppt"}
            txt = reasons.get(eng.last_reason, eng.last_reason) or "Bereit"
            color = theme.DANGER if txt.startswith("error") else theme.TEXT
            self.status.configure(text=txt, text_color=color)
        mins, secs = divmod(int(eng.elapsed()), 60)
        self.stats.configure(text=f"Ausführungen: {eng.count}   ·   Laufzeit: {mins:02d}:{secs:02d}")
        self.hk_err.configure(text=self.plugin.hotkey_error)
        self.after(100, self._tick)
