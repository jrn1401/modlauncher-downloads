"""Hauptfenster des Launchers: Seitenleiste, Dashboard, Plugin-Seiten, Update-Dialog."""
import queue
import threading

import customtkinter as ctk

from core import updater
from core.plugin_manager import discover
from core.version import APP_NAME, APP_VERSION

ACCENT = "#4f8cff"
BG_SIDEBAR = "#14161b"
BG_MAIN = "#1b1e25"
BG_CARD = "#242831"


class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, app, info: updater.UpdateInfo):
        super().__init__(app)
        self.app, self.info = app, info
        self.title("Update verfügbar")
        self.geometry("440x300")
        self.resizable(False, False)
        self.transient(app)
        ctk.CTkLabel(self, text=f"Version {info.version} ist verfügbar",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 4))
        ctk.CTkLabel(self, text=f"Installiert: {APP_VERSION}", text_color="gray").pack()
        notes = ctk.CTkTextbox(self, height=100, width=380)
        notes.insert("1.0", info.notes or "Keine Release-Notes.")
        notes.configure(state="disabled")
        notes.pack(pady=12)
        self.bar = ctk.CTkProgressBar(self, width=380)
        self.bar.set(0)
        self.status = ctk.CTkLabel(self, text="")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=4)
        self.btn = ctk.CTkButton(row, text="Jetzt aktualisieren", command=self._start)
        self.btn.pack(side="left", padx=6)
        ctk.CTkButton(row, text="Später", fg_color="gray30", command=self.destroy).pack(side="left", padx=6)

    def _start(self):
        self.btn.configure(state="disabled")
        self.bar.pack(pady=4)
        self.status.pack()
        self.status.configure(text="Lade herunter ...")

        def work():
            try:
                path = updater.download(self.info, lambda p: self.app.call_soon(self.bar.set, p))
                self.app.call_soon(self.status.configure, text="Installiere ...")
                restart = updater.apply(path)
                self.app.call_soon(self._done, restart, None)
            except Exception as exc:
                self.app.call_soon(self._done, False, str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, restart: bool, error: str | None):
        if error:
            self.status.configure(text=f"Fehler: {error}", text_color="#ff6b6b")
            self.btn.configure(state="normal")
        elif restart:
            self.app.close()
        else:
            self.status.configure(text="Heruntergeladen – bitte manuell ersetzen.")


class DashboardPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_MAIN)
        self.app = app
        ctk.CTkLabel(self, text="Dashboard", font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w", padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text=f"{APP_NAME} {APP_VERSION}", text_color="gray").pack(anchor="w", padx=24)

        upd = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        upd.pack(fill="x", padx=24, pady=(18, 8))
        self.update_label = ctk.CTkLabel(upd, text="Update-Status: noch nicht geprüft", anchor="w")
        self.update_label.pack(side="left", padx=16, pady=14)
        ctk.CTkButton(upd, text="Nach Updates suchen", width=170,
                      command=lambda: app.check_updates(manual=True)).pack(side="right", padx=16)

        ctk.CTkLabel(self, text="Module", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=24, pady=(14, 6))
        for p in app.plugins:
            card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
            card.pack(fill="x", padx=24, pady=5)
            text = ctk.CTkFrame(card, fg_color="transparent")
            text.pack(side="left", padx=16, pady=12)
            ctk.CTkLabel(text, text=f"{p.name}  ·  v{p.version}", font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(anchor="w")
            ctk.CTkLabel(text, text=p.dashboard_summary(), text_color="gray", anchor="w", wraplength=520, justify="left").pack(anchor="w")
            ctk.CTkButton(card, text="Öffnen", width=90, command=lambda pid=p.id: app.show(pid)).pack(side="right", padx=16)
        for name, err in app.failed:
            ctk.CTkLabel(self, text=f"Modul '{name}' konnte nicht geladen werden: {err}",
                         text_color="#ff6b6b", wraplength=640, justify="left").pack(anchor="w", padx=24, pady=4)

    def set_update_text(self, text: str):
        self.update_label.configure(text=text)


class LauncherApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        super().__init__(fg_color=BG_MAIN)
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1040x680")
        self.minsize(900, 600)
        self._ui_q: queue.Queue = queue.Queue()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.plugins, self.failed = discover(self)
        self.plugin_by_id = {p.id: p for p in self.plugins}

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(self.sidebar, text=APP_NAME, font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(24, 20), anchor="w")
        self.nav = {}
        self._add_nav("dashboard", "⌂  Dashboard")
        for p in self.plugins:
            self._add_nav(p.id, f"{p.icon}  {p.name}")
        ctk.CTkLabel(self.sidebar, text=f"v{APP_VERSION}", text_color="gray").pack(side="bottom", pady=14)

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_MAIN)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.pages, self.current = {}, None
        self.dashboard = DashboardPage(self.content, self)
        self.pages["dashboard"] = self.dashboard

        for p in self.plugins:
            try:
                p.on_load()
            except Exception as exc:
                self.failed.append((p.id, str(exc)))

        self.show("dashboard")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(50, self._drain)
        self.after(1500, self.check_updates)

    # ---------- Navigation ----------
    def _add_nav(self, pid: str, label: str):
        btn = ctk.CTkButton(self.sidebar, text=label, anchor="w", height=40, corner_radius=8,
                            fg_color="transparent", hover_color="#262b36", command=lambda: self.show(pid))
        btn.pack(fill="x", padx=12, pady=2)
        self.nav[pid] = btn

    def show(self, pid: str):
        if self.current:
            self.pages[self.current].grid_forget()
        if pid not in self.pages:
            self.pages[pid] = self.plugin_by_id[pid].create_page(self.content)
        self.pages[pid].grid(row=0, column=0, sticky="nsew")
        self.current = pid
        for k, b in self.nav.items():
            b.configure(fg_color=ACCENT if k == pid else "transparent")

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
                except Exception as exc:
                    print("UI-Callback-Fehler:", exc)
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

    def _on_update_result(self, info, err, manual):
        if err:
            self.dashboard.set_update_text(f"Update-Prüfung fehlgeschlagen: {err}")
        elif info:
            self.dashboard.set_update_text(f"Neue Version {info.version} verfügbar")
            UpdateDialog(self, info)
        else:
            self.dashboard.set_update_text("Du hast die aktuelle Version.")

    # ---------- Beenden ----------
    def close(self):
        for p in self.plugins:
            try:
                p.on_shutdown()
            except Exception as exc:
                print("Shutdown-Fehler:", exc)
        self.destroy()
