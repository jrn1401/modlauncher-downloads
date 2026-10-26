"""Kleine UI-Bausteine, damit alle Seiten gleich aussehen (clean, flach, ohne Animationen)."""
import customtkinter as ctk

from core import theme
from core.i18n import tr


def page_title(parent, text: str, subtitle: str = "") -> ctk.CTkFrame:
    box = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(box, text=tr(text), font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w")
    if subtitle:
        ctk.CTkLabel(box, text=tr(subtitle), text_color=theme.MUTED, justify="left", wraplength=700).pack(anchor="w")
    return box


def card(parent, title: str = "") -> ctk.CTkFrame:
    f = ctk.CTkFrame(parent, fg_color=theme.c("card"), corner_radius=12)
    if title:
        ctk.CTkLabel(f, text=tr(title), font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=16, pady=(12, 6))
    return f


def muted(parent, text: str, wrap: int = 640, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=tr(text, **kw) if kw else tr(text), text_color=theme.MUTED, justify="left",
                        anchor="w", wraplength=wrap)


def banner(parent, text: str, color: str = "#b45309", wrap: int = 640) -> ctk.CTkFrame:
    """Auffälliger Hinweiskasten (z. B. Anti-Cheat-Warnung)."""
    f = ctk.CTkFrame(parent, fg_color=color, corner_radius=10)
    ctk.CTkLabel(f, text=tr(text), text_color="white", wraplength=wrap, justify="left",
                 font=ctk.CTkFont(size=14, weight="bold")).pack(padx=16, pady=12, anchor="w")
    return f


def row(parent) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color="transparent")
