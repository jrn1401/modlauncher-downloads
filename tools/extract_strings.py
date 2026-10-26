"""Sammelt alle übersetzbaren Texte (tr(...) und Hilfsfunktionen) aus dem Quellcode.
Aufruf: python tools/extract_strings.py  -> gibt die Liste aus; Test: tests/test_i18n.py"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPERS = {"muted": (1,), "page_title": (1, 2), "card": (1,), "banner": (1,), "_card": (0,)}
ERRORS = {"AccountError", "CloudError", "AiUnavailable", "ValueError", "GenerateError", "LoopbackError", "RuntimeError", "TotpRequired"}
SKIP_DIRS = {"tests", "tools", "csharp", "supabase", ".github", "server_examples"}


def _lit(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def from_calls() -> set[str]:
    found: set[str] = set()
    for path in ROOT.rglob("*.py"):
        if SKIP_DIRS & set(path.relative_to(ROOT).parts) or "lang" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if name == "tr" and node.args and _lit(node.args[0]):
                found.add(_lit(node.args[0]))
            elif name in ERRORS and node.args and _lit(node.args[0]):
                found.add(_lit(node.args[0]))
            elif name in HELPERS and name != "card" or (name == "card" and isinstance(f, ast.Attribute)):
                for i in HELPERS.get(name, ()):
                    if i < len(node.args) and _lit(node.args[i]):
                        found.add(_lit(node.args[i]))
        if path.name == "cloud.py":
            for node in ast.walk(tree):
                if isinstance(node, ast.Return) and _lit(node.value):
                    found.add(_lit(node.value))
    return found


def from_constants() -> set[str]:
    sys.path.insert(0, str(ROOT))
    out: set[str] = set()
    from core import assistant, credits, firstrun_view, identity, settings_view, theme
    from core import contact_view
    from modules.extensions import catalog
    from modules.recoil import plugin as recoil
    from modules.macros import page as macro_page
    for keys, answer in assistant.FAQ:
        out.add(answer)
    out.add(assistant.FALLBACK)
    out.update(contact_view.CATEGORIES)
    out.update(label for label, _ in identity.REMEMBER_CHOICES)
    out.update(settings_view.SECTIONS)
    out.update(theme.MODES)
    out.update(theme.PRESETS)
    out.update(label for label, _ in theme.COLOR_KEYS)
    out.update(role for _, role, _, _ in credits.CREDITS)
    for e in catalog.CATALOG:
        out.update((e["name"], e["desc"]))
    out.add(recoil.WARNING)
    out.update(["Left mouse button", "Right mouse button", "Middle mouse button"])
    from modules.autoclicker import keys as ak
    out.update(ak.MOUSE_BUTTONS.values())
    from core.assistant_view import GREETING
    out.add(GREETING)
    from modules.recoil.page import FIELDS
    out.update(label for _, label, _ in FIELDS)
    from modules.recoil.engine import PRESETS as RP
    out.update(RP)
    import importlib
    for mod in ("autoclicker", "macros", "extensions", "recoil"):
        p = importlib.import_module(f"modules.{mod}.plugin").Plugin
        out.update((p.name, p.description))
    return out


def all_strings() -> list[str]:
    return sorted(from_calls() | from_constants())


if __name__ == "__main__":
    for s in all_strings():
        print(repr(s))
