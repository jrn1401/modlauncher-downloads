import tkinter as tk
import webbrowser

import customtkinter as ctk

from core import theme, ui
from core.i18n import tr

from . import catalog


class ExtensionsPage(ctk.CTkScrollableFrame):
    def __init__(self, parent, plugin):
        super().__init__(parent, fg_color=theme.c("main"))
        self.plugin, self.app = plugin, plugin.app
        self.store = plugin.store()
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        ui.page_title(self, "Browsing / Extensions",
                      "Add an extension with one click, switch it on or off and set it up.").grid(
            row=0, column=0, sticky="w", padx=24, pady=(20, 8))
        for i, ext in enumerate(catalog.CATALOG, start=1):
            self._ext_card(i, ext)

    def _ext_card(self, row, ext):
        eid, st = ext["id"], self.store
        c = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=12)
        c.grid(row=row, column=0, sticky="ew", padx=24, pady=6)
        head = ui.row(c)
        head.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(head, text=f"{ext['icon']}  {tr(ext['name'])}", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        if st.added(eid):
            ctk.CTkButton(head, text=tr("Remove"), width=90, fg_color="gray35", hover_color="gray25",
                          command=lambda: self._do(st.remove, eid)).pack(side="right")
            var = tk.BooleanVar(value=st.enabled(eid))
            ctk.CTkSwitch(head, text=tr("On"), variable=var, width=70,
                          command=lambda: self._do(st.set_enabled, eid, var.get())).pack(side="right", padx=12)
        else:
            ctk.CTkButton(head, text="+ " + tr("Add"), width=90, command=lambda: self._do(st.add, eid)).pack(side="right")
        ui.muted(c, ext["desc"]).pack(fill="x", padx=16, pady=(0, 10))
        if st.added(eid) and st.enabled(eid):
            body = ctk.CTkFrame(c, fg_color=theme.c("inset"), corner_radius=8)
            body.pack(fill="x", padx=16, pady=(0, 14))
            getattr(self, f"_w_{eid}")(body)

    def _do(self, fn, *args):
        try:
            fn(*args)
        except ValueError as exc:
            self._error(str(exc))
            return
        self.after(10, self._build)

    def _error(self, text):
        top = ctk.CTkToplevel(self)
        top.title(tr("Notice"))
        ctk.CTkLabel(top, text=tr(text), wraplength=320).pack(padx=20, pady=20)
        ctk.CTkButton(top, text="OK", command=top.destroy).pack(pady=(0, 16))
        top.after(50, top.lift)

    @staticmethod
    def _open(url):
        try:
            webbrowser.open(catalog.safe_url(url))
        except Exception:
            pass

    # ---- Widgets der Erweiterungen
    def _w_quicklinks(self, body):
        links = self.store.config("quicklinks")["links"]
        wrap = ui.row(body)
        wrap.pack(fill="x", padx=10, pady=10)
        for name, url in links:
            r = ui.row(wrap)
            r.pack(fill="x", pady=2)
            ctk.CTkButton(r, text=name, width=160, anchor="w", command=lambda u=url: self._open(u)).pack(side="left")
            ctk.CTkLabel(r, text=url, text_color=theme.MUTED).pack(side="left", padx=10)
            ctk.CTkButton(r, text="✕", width=30, fg_color="gray35", hover_color="gray25",
                          command=lambda n=name, u=url: self._do(self._set_links, [l for l in links if l != [n, u]])).pack(side="right")
        add = ui.row(wrap)
        add.pack(fill="x", pady=(8, 0))
        n = ctk.CTkEntry(add, width=130, placeholder_text=tr("Name"))
        n.pack(side="left")
        u = ctk.CTkEntry(add, width=240, placeholder_text="https://…")
        u.pack(side="left", padx=6)
        ctk.CTkButton(add, text="+ " + tr("Add"), width=80,
                      command=lambda: self._do(self._set_links, links + [[n.get(), u.get()]])).pack(side="left")

    def _set_links(self, links):
        self.store.set_config("quicklinks", links=links)

    def _w_websearch(self, body):
        cfg = self.store.config("websearch")
        r = ui.row(body)
        r.pack(fill="x", padx=10, pady=10)
        e = ctk.CTkEntry(r, width=280, placeholder_text=tr("Search …"))
        e.pack(side="left")
        go = lambda _=None: e.get().strip() and self._open(catalog.search_url(menu.get(), e.get()))
        e.bind("<Return>", go)
        ctk.CTkButton(r, text=tr("Search"), width=80, command=go).pack(side="left", padx=6)
        menu = ctk.CTkOptionMenu(r, values=list(catalog.SEARCH_ENGINES), width=130,
                                 command=lambda v: self.store.set_config("websearch", engine=v))
        menu.set(cfg["engine"])
        menu.pack(side="left")

    def _w_notes(self, body):
        box = ctk.CTkTextbox(body, height=150, fg_color=theme.c("inset"))
        box.pack(fill="x", padx=10, pady=10)
        box.insert("1.0", self.store.config("notes")["text"])
        state = {"job": None}

        def changed(_e=None):
            if state["job"]:
                box.after_cancel(state["job"])
            state["job"] = box.after(800, lambda: self.store.set_config("notes", text=box.get("1.0", "end").rstrip("\n")))

        box.bind("<KeyRelease>", changed)
