"""Kontaktformular: Feedback an FEEDBACK_EMAIL (per Formular-Dienst oder über das Mailprogramm)."""
import json
import platform
import threading
import urllib.parse
import urllib.request
import webbrowser

import tkinter

import customtkinter as ctk

from core import accounts, theme
from core.version import APP_ID, APP_VERSION, CONTACT_ENDPOINT, FEEDBACK_EMAIL

CATEGORIES = ["Feedback", "Fehler melden", "Idee / Wunsch", "Frage"]
MAILTO_LIMIT = 1800      # längere mailto-Adressen werden von Windows oft abgeschnitten


def compose(category: str, name: str, email: str, message: str, with_info: bool) -> tuple[str, str]:
    """Gibt (Betreff, Text) zurück."""
    subject = f"[{category}] {name or 'Nutzer'}"
    lines = [message.strip(), "", "—", f"Von: {name or '-'} <{email or '-'}>"]
    if with_info:
        lines.append(f"Programm: {APP_ID} {APP_VERSION} · {platform.system()} {platform.release()}")
    return subject, "\n".join(lines)


def build_mailto(subject: str, body: str) -> tuple[str, bool]:
    """Gibt (mailto-Link, wurde_gekürzt) zurück."""
    def link(b):
        return f"mailto:{FEEDBACK_EMAIL}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(b)}"
    url, cut = link(body), False
    while len(url) > MAILTO_LIMIT and len(body) > 50:
        body, cut = body[: int(len(body) * 0.8)], True
        url = link(body)
    return url, cut


def post_endpoint(url: str, payload: dict, timeout: float = 20) -> None:
    if not url.startswith("https://"):
        raise ValueError("Die Formular-Adresse muss mit https:// beginnen.")
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if not 200 <= resp.status < 300:
            raise OSError(f"Server antwortete mit {resp.status}")


class ContactView(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.c("main"))
        self.app = app
        self.endpoint = app.settings.get("contact_endpoint") or CONTACT_ENDPOINT
        me = app.user
        self.columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Kontakt & Feedback", font=ctk.CTkFont(size=26, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(self, text="Lob, Fehler, Ideen oder Fragen: Schreib uns!", text_color=theme.MUTED).grid(
            row=1, column=0, sticky="w", padx=24)

        card = ctk.CTkFrame(self, fg_color=theme.c("card"), corner_radius=12)
        card.grid(row=2, column=0, sticky="ew", padx=24, pady=12)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=14)

        self.e_name = self._field(body, "Name", me["display_name"])
        self.e_mail = self._field(body, "Deine E-Mail (für Antworten)", me["email"])
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text="Kategorie", width=190, anchor="w").pack(side="left")
        self.o_cat = ctk.CTkOptionMenu(row, values=CATEGORIES, width=200)
        self.o_cat.pack(side="left")
        ctk.CTkLabel(body, text="Nachricht", anchor="w").pack(fill="x", pady=(8, 2))
        self.txt = ctk.CTkTextbox(body, height=170, border_width=1, border_color=("gray70", "gray30"))
        self.txt.pack(fill="x")
        self.info = tkinter.BooleanVar(value=True)
        ctk.CTkCheckBox(body, text="Programmversion und Betriebssystem mitsenden", variable=self.info).pack(anchor="w", pady=8)
        self.status = ctk.CTkLabel(body, text="", anchor="w", justify="left", wraplength=540)
        self.status.pack(fill="x")
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(anchor="w", pady=(6, 0))
        self.send_btn = ctk.CTkButton(btns, text="Senden", width=140, command=self.send)
        self.send_btn.pack(side="left")
        ctk.CTkButton(btns, text="Text kopieren", width=140, fg_color="gray35", hover_color="gray25",
                      command=self.copy).pack(side="left", padx=8)
        how = ("Die Nachricht wird direkt gesendet." if self.endpoint else
               f"Es öffnet sich dein Mailprogramm mit einer fertigen Mail an {FEEDBACK_EMAIL}. Dort nur noch auf „Senden“ klicken.")
        ctk.CTkLabel(body, text=how, text_color=theme.MUTED, anchor="w", justify="left", wraplength=540).pack(fill="x", pady=(8, 0))

    @staticmethod
    def _field(parent, label, value=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=label, width=190, anchor="w").pack(side="left")
        e = ctk.CTkEntry(row, width=300)
        e.pack(side="left")
        e.insert(0, value)
        return e

    def _say(self, text, ok=True):
        self.status.configure(text=text, text_color=theme.OK if ok else theme.DANGER)

    def _collect(self):
        message = self.txt.get("1.0", "end").strip()
        if len(message) < 10:
            self._say("Bitte schreib mindestens 10 Zeichen.", False)
            return None
        mail = self.e_mail.get().strip()
        if mail and not accounts.EMAIL_RE.match(mail):
            self._say("Die E-Mail-Adresse sieht ungültig aus.", False)
            return None
        return compose(self.o_cat.get(), self.e_name.get().strip(), mail, message, self.info.get())

    def copy(self):
        data = self._collect()
        if data:
            self.clipboard_clear()
            self.clipboard_append(f"An: {FEEDBACK_EMAIL}\nBetreff: {data[0]}\n\n{data[1]}")
            self._say("Kopiert. Du kannst den Text jetzt in eine Mail an " + FEEDBACK_EMAIL + " einfügen.")

    def send(self):
        data = self._collect()
        if not data:
            return
        subject, body = data
        if not self.endpoint:
            self._open_mail(subject, body)
            return
        self.send_btn.configure(state="disabled")
        self._say("Sende ...")
        payload = {"category": self.o_cat.get(), "name": self.e_name.get().strip(), "email": self.e_mail.get().strip(),
                   "subject": subject, "message": body, "app": APP_ID, "version": APP_VERSION}

        def work():
            try:
                post_endpoint(self.endpoint, payload)
                err = None
            except Exception as exc:
                err = str(exc)
            self.app.call_soon(self._sent, err, subject, body)

        threading.Thread(target=work, daemon=True).start()

    def _sent(self, err, subject, body):
        if not self.winfo_exists():
            return
        self.send_btn.configure(state="normal")
        if err is None:
            self._say("Danke! Deine Nachricht wurde gesendet.")
            self.txt.delete("1.0", "end")
        else:
            self._say(f"Senden fehlgeschlagen ({err}). Ich öffne stattdessen dein Mailprogramm.", False)
            self._open_mail(subject, body)

    def _open_mail(self, subject, body):
        url, cut = build_mailto(subject, body)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        msg = "Dein Mailprogramm wurde geöffnet. Klicke dort auf „Senden“."
        if cut:
            msg += " Die Nachricht war lang und wurde gekürzt. Nutze sonst „Text kopieren“."
        msg += " Passiert nichts? Dann hast du kein Mailprogramm eingerichtet: Nutze „Text kopieren“."
        self._say(msg)
