"""Hilfe-Assistent: Chat mit FAQ-Antworten und optional einem KI-Server."""
import threading

import customtkinter as ctk

from core import ai_client, assistant, theme, ui
from core.i18n import tr
from core.version import ASSISTANT_URL

GREETING = ("Hello! I am the help assistant. Ask me about hotkeys, profiles, macros, extensions, updates, 2FA or the design. "
            "If I do not know something, the contact form will help.")


class AssistantView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"))
        self.app = app
        self.history: list[dict] = []
        self._waiting = False
        self.url = app.settings.get("assistant_url") or ASSISTANT_URL
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 6))
        ctk.CTkLabel(head, text=tr("Help assistant"), font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w")
        ai_on = ai_client.available(app) or bool(self.url)
        ctk.CTkLabel(head, text=tr("AI-powered") if ai_on else tr("Offline help (FAQ)"), text_color=theme.MUTED).pack(anchor="w")

        self.chat = ctk.CTkScrollableFrame(self, fg_color=theme.c("card"), corner_radius=12)
        self.chat.grid(row=1, column=0, sticky="nsew", padx=24, pady=6)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=24, pady=(6, 20))
        bar.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(bar, placeholder_text=tr("Type a question and press Enter …"), height=38)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _e: self.send())
        self.btn = ctk.CTkButton(bar, text=tr("Send"), width=100, height=38, command=self.send)
        self.btn.grid(row=0, column=1, padx=(8, 0))
        self._bubble(tr(GREETING), mine=False)

    def _bubble(self, text, mine):
        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row.pack(fill="x", pady=4, padx=6)
        box = ctk.CTkFrame(row, corner_radius=12, fg_color=theme.accent() if mine else theme.c("bubble"))
        box.pack(side="right" if mine else "left")
        lab = ctk.CTkLabel(box, text=text, wraplength=500, justify="left", anchor="w",
                           text_color="white" if mine else theme.TEXT)
        lab.pack(padx=12, pady=8)
        self.after(30, self._scroll_down)
        return lab

    def _scroll_down(self):
        try:
            self.chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def send(self):
        text = self.entry.get().strip()
        if not text or self._waiting:
            return
        self.entry.delete(0, "end")
        self._bubble(text, mine=True)
        self.history.append({"role": "user", "content": text})
        pending = self._bubble("…", mine=False)
        self._waiting = True
        self.btn.configure(state="disabled")
        history, url = list(self.history), self.url

        def work():
            answer, _ai = assistant.reply(self.app, text, history, url)
            self.app.call_soon(self._got_answer, pending, answer)

        threading.Thread(target=work, daemon=True).start()

    def _got_answer(self, label, answer):
        if not self.winfo_exists():
            return
        label.configure(text=answer)
        self.history.append({"role": "assistant", "content": answer})
        self._waiting = False
        self.btn.configure(state="normal")
        self._scroll_down()
