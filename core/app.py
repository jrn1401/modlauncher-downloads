"""Hauptfenster: Anmeldung, Seitenleiste, Dashboard, Plugin-Seiten, Einstellungen, Update-Dialog."""
import queue
import threading
import traceback

import customtkinter as ctk

from core import accounts, config, system_limits, theme, updater
from core.plugin_manager import discover
from core.version import APP_NAME, APP_VERSION


class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, app, info: updater.UpdateInfo):
        super().__init__(app, fg_color=theme.c("main"))
        self.app, self.info = app, info
        self.title("Update verfügbar")
        self.geometry("440x320")
        self.resizable(False, False)
        self.transient(app)
        ctk.CTkLabel(self, text=f"Version {info.version} ist verfügbar",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 4))
        ctk.CTkLabel(self, text=f"Installiert: {APP_VERSION}", text_color=theme.MUTED).pack()
        notes = ctk.CTkTextbox(self, height=100, width=380)
        notes.insert("1.0", info.notes or "Keine Release-Notes.")
        notes.configure(state="disabled")
        notes.pack(pady=12)
        self.bar = ctk.CTkProgressBar(self, width=380)
        self.bar.set(0)
        self.status = ctk.CTkLabel(self, text="", wraplength=380)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=4)
        self.btn = ctk.CTkButton(row, text="Jetzt aktualisieren", command=self._start)
        self.btn.pack(side="left", padx=6)
        ctk.CTkButton(row, text="Später", fg_color="gray30", hover_color="gray20", command=self.destroy).pack(side="left", padx=6)

    def _start(self):
        self.btn.configure(state="disabled")
        self.bar.pack(pady=4)
        self.status.pack()
        self.status.configure(text="Lade herunter ...", text_color=theme.TEXT)
        limit = self.app.settings.get("dl_limit_kbps", 0)

        def work():
            try:
                path = updater.download(self.info, lambda p: self.app.call_soon(self._progress, p), max_kbps=limit)
                self.app.call_soon(self.status.configure, text="Installiere ...")
                restart = updater.apply(path)
                self.app.call_soon(self._done, restart, None)
            except Exception as exc:
                self.app.call_soon(self._done, False, str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _progress(self, p):
        if self.winfo_exists():
            self.bar.set(p)

    def _done(self, restart: bool, error: str | None):
        if not self.winfo_exists():
            return
        if error:
            self.status.configure(text=f"Fehler: {error}", text_color=theme.DANGER)
            self.btn.configure(state="normal")
        elif restart:
            self.app.close()
        else:
            self.status.configure(text="Heruntergeladen – bitte manuell ersetzen.")


class DashboardPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"))
        self.app = app
        name = app.user["display_name"]
        self.welcome = ctk.CTkLabel(self, text=f"Willkommen, {name}! 👋", font=ctk.CTkFont(size=28, weight="bold"))
        self.welcome.pack(anchor="w", padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text=f"Schön, dass du da bist. Das ist {APP_NAME} · Version {APP_VERSION}.",
                     text_color=theme.MUTED).pack(anchor="w", padx=24)

        upd = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=12)
        upd.pack(fill="x", padx=24, pady=(18, 8))
        self.update_label = ctk.CTkLabel(upd, text=app.update_text, anchor="w", wraplength=480, justify="left")
        self.update_label.pack(side="left", padx=16, pady=14)
        ctk.CTkButton(upd, text="Nach Updates suchen", width=170,
                      command=lambda: app.check_updates(manual=True)).pack(side="right", padx=16)

        ctk.CTkLabel(self, text="Module", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=24, pady=(14, 6))
        for p in app.plugins:
            card = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=12)
            card.pack(fill="x", padx=24, pady=5)
            text = ctk.CTkFrame(card, fg_color="transparent")
            text.pack(side="left", padx=16, pady=12)
            ctk.CTkLabel(text, text=f"{p.name}  ·  v{p.version}", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(text, text=p.dashboard_summary(), text_color=theme.MUTED, anchor="w", wraplength=480,
                         justify="left").pack(anchor="w")
            ctk.CTkButton(card, text="Öffnen", width=90, command=lambda pid=p.id: app.show(pid)).pack(side="right", padx=16)
        for name, err in app.failed + app.load_failed:
            ctk.CTkLabel(self, text=f"Modul '{name}' konnte nicht geladen werden: {err}",
                         text_color=theme.DANGER, wraplength=640, justify="left").pack(anchor="w", padx=24, pady=4)

    def set_update_text(self, text: str):
        self.update_label.configure(text=text)


def _builtin_pages() -> dict:
    """Eingebaute Seiten (werden erst beim ersten Öffnen importiert/erzeugt)."""
    def settings(parent, app):
        from core.settings_view import SettingsView
        return SettingsView(parent, app)

    def assistant(parent, app):
        from core.assistant_view import AssistantView
        return AssistantView(parent, app)

    def contact(parent, app):
        from core.contact_view import ContactView
        return ContactView(parent, app)

    return {"settings": settings, "assistant": assistant, "contact": contact}


class LauncherApp(ctk.CTk):
    def __init__(self):
        self.settings = config.load_settings()
        theme.apply(self.settings)
        super().__init__(fg_color=theme.c("main"))
        self.title(APP_NAME)
        self.geometry("1100x720")
        self.minsize(940, 620)
        self._ui_q: queue.Queue = queue.Queue()
        self.accounts = accounts.AccountStore()
        self.user: dict | None = None
        self.update_text = "Update-Status: noch nicht geprüft"
        self.plugins, self.failed = discover(self)
        self.plugin_by_id = {p.id: p for p in self.plugins}
        self.load_failed: list = []
        self._loaded = False
        self._builtin = _builtin_pages()
        self.root_frame = None
        self.nav, self.pages, self.current = {}, {}, None
        self.dashboard = None

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(50, self._drain)
        self.apply_limits()
        user = None
        try:
            user = self.accounts.resume_session()
        except Exception:
            traceback.print_exc()
        if user:
            self.login_done(user, remember=True)
        else:
            self.show_login()

    # ---------- Rahmen ----------
    def _reset_root(self):
        if self.root_frame is not None:
            self.root_frame.destroy()
        self.root_frame = ctk.CTkFrame(self, fg_color=theme.c("main"), corner_radius=0)
        self.root_frame.pack(fill="both", expand=True)
        self.nav, self.pages, self.current, self.dashboard = {}, {}, None, None

    def show_login(self):
        from core.login_view import LoginView
        self._reset_root()
        LoginView(self.root_frame, self).pack(fill="both", expand=True)

    def login_done(self, user: dict, remember: bool):
        self.user = user
        try:
            if remember:
                self.accounts.create_session(user["username"])
            else:
                self.accounts.clear_session()
        except Exception:
            traceback.print_exc()
        if not self._loaded:          # Module (Hotkeys, Threads) erst nach der Anmeldung starten
            self.load_failed = []
            for p in self.plugins:
                try:
                    p.on_load()
                except Exception as exc:
                    traceback.print_exc()
                    self.load_failed.append((p.id, str(exc)))
            self._loaded = True
        self.build_main()
        self.show("dashboard")
        self.after(1500, self.check_updates)

    def logout(self):
        try:
            self.accounts.clear_session()
        except Exception:
            traceback.print_exc()
        self._shutdown_plugins()
        self.user = None
        self.show_login()

    def _shutdown_plugins(self):
        if self._loaded:
            for p in self.plugins:
                try:
                    p.on_shutdown()
                except Exception as exc:
                    print("Shutdown-Fehler:", exc)
            self._loaded = False

    # ---------- Hauptansicht ----------
    def build_main(self):
        self._reset_root()
        root = self.root_frame
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(root, width=235, corner_radius=0, fg_color=theme.c("sidebar"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text=APP_NAME, font=ctk.CTkFont(size=20, weight="bold"), wraplength=200,
                     justify="left").pack(padx=20, pady=(24, 18), anchor="w")

        self._add_nav("dashboard", "⌂  Dashboard")
        for p in self.plugins:
            self._add_nav(p.id, f"{p.icon}  {p.name}")
        ctk.CTkLabel(self.sidebar, text="HILFE", text_color=theme.MUTED, font=ctk.CTkFont(size=11, weight="bold")).pack(
            padx=20, pady=(16, 2), anchor="w")
        self._add_nav("assistant", "💬  Hilfe-Assistent")
        self._add_nav("contact", "✉  Kontakt")

        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=(0, 12))
        self.user_label = ctk.CTkLabel(bottom, text="", anchor="w", font=ctk.CTkFont(weight="bold"))
        self.user_label.pack(fill="x", padx=20, pady=(0, 4))
        self._add_nav("settings", "⚙  Einstellungen", parent=bottom)
        btn = ctk.CTkButton(bottom, text="⎋  Abmelden", anchor="w", height=38, corner_radius=8, fg_color="transparent",
                            text_color=theme.TEXT, hover_color=theme.c("hover"), command=self.logout)
        btn.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(bottom, text=f"v{APP_VERSION}", text_color=theme.MUTED).pack(pady=(6, 0))
        self.refresh_user_labels()

        self.content = ctk.CTkFrame(root, corner_radius=0, fg_color=theme.c("main"))
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.dashboard = DashboardPage(self.content, self)
        self.pages["dashboard"] = self.dashboard

    def _add_nav(self, pid: str, label: str, parent=None):
        btn = ctk.CTkButton(parent or self.sidebar, text=label, anchor="w", height=40, corner_radius=8,
                            fg_color="transparent", text_color=theme.TEXT, hover_color=theme.c("hover"),
                            command=lambda: self.show(pid))
        btn.pack(fill="x", padx=12, pady=2)
        self.nav[pid] = btn

    def refresh_user_labels(self):
        if self.user and getattr(self, "user_label", None) is not None and self.user_label.winfo_exists():
            self.user_label.configure(text=f"👤  {self.user['display_name']}")
        if self.dashboard is not None and self.dashboard.winfo_exists():
            self.dashboard.welcome.configure(text=f"Willkommen, {self.user['display_name']}! 👋")

    def show(self, pid: str):
        if self.current in self.pages:
            self.pages[self.current].grid_forget()
        if pid not in self.pages:
            try:
                if pid in self.plugin_by_id:
                    self.pages[pid] = self.plugin_by_id[pid].create_page(self.content)
                else:
                    self.pages[pid] = self._builtin[pid](self.content, self)
            except Exception:
                traceback.print_exc()
                box = ctk.CTkFrame(self.content, fg_color=theme.c("main"))
                ctk.CTkLabel(box, text="Diese Seite konnte nicht geladen werden:\n\n" + traceback.format_exc()[-900:],
                             text_color=theme.DANGER, justify="left", wraplength=620).pack(padx=24, pady=24, anchor="w")
                self.pages[pid] = box
        self.pages[pid].grid(row=0, column=0, sticky="nsew")
        self.current = pid
        for k, b in self.nav.items():
            active = k == pid
            b.configure(fg_color=theme.accent() if active else "transparent", text_color="white" if active else theme.TEXT)

    # ---------- Einstellungen anwenden ----------
    def change_appearance(self, mode=None, accent=None):
        if mode:
            self.settings["appearance_mode"] = mode
        if accent:
            self.settings["accent"] = accent
        config.save_settings(self.settings)
        theme.apply(self.settings)
        self.after(20, self._rebuild_keep_page)      # nicht mitten im Klick-Handler zerstören

    def _rebuild_keep_page(self):
        page = self.current or "dashboard"
        self.configure(fg_color=theme.c("main"))
        self.build_main()
        self.show(page)

    def apply_limits(self) -> list[str]:
        s = self.settings
        return system_limits.apply(s["cpu_priority"], int(s["cpu_cores"]), int(s["ram_limit_mb"]))

    # ---------- Thread-sichere UI-Aufrufe ----------
    def call_soon(self, fn, *args, **kwargs):
        """Aus beliebigen Threads aufrufbar; fn läuft im UI-Thread."""
        self._ui_q.put((fn, args, kwargs))

    def _drain(self):
        try:
            while True:
                fn, args, kwargs = self._ui_q.get_nowait()
                try:
                    fn(*args, **kwargs)
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        self.after(50, self._drain)

    # ---------- Updates ----------
    def check_updates(self, manual: bool = False):
        def work():
            try:
                info, err = updater.check(), None
            except Exception as exc:
                info, err = None, str(exc)
            self.call_soon(self._on_update_result, info, err, manual)

        threading.Thread(target=work, daemon=True).start()

    def _set_update_text(self, text):
        self.update_text = text
        if self.dashboard is not None and self.dashboard.winfo_exists():
            self.dashboard.set_update_text(text)

    def _on_update_result(self, info, err, manual):
        if self.user is None:
            return
        if err:
            self._set_update_text(f"Update-Prüfung fehlgeschlagen: {err}")
        elif info:
            self._set_update_text(f"Neue Version {info.version} verfügbar")
            UpdateDialog(self, info)
        else:
            self._set_update_text("Du hast die aktuelle Version.")

    # ---------- Beenden ----------
    def close(self):
        self._shutdown_plugins()
        self.destroy()
