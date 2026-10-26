"""Tasten-/Maus-Handling auf Basis von pynput.

Ziel-Tasten werden als String gespeichert:
    "mouse:left" | "mouse:right" | "mouse:middle" | "key:e" | "key:space" | "key:f5"
Hotkeys im pynput-Format:  "<f6>"  oder  "<ctrl>+<alt>+p"
"""
import threading

from pynput import keyboard, mouse

from core.i18n import tr

MOUSE_BUTTONS = {"left": "Left mouse button", "right": "Right mouse button", "middle": "Middle mouse button"}
MODIFIERS = {"ctrl", "alt", "shift", "cmd"}
COMMON_KEYS = (
    [chr(c) for c in range(ord("a"), ord("z") + 1)]
    + [str(i) for i in range(10)]
    + [f"f{i}" for i in range(1, 13)]
    + ["space", "enter", "tab", "backspace", "esc", "up", "down", "left", "right",
       "shift", "ctrl", "alt", "home", "end", "page_up", "page_down", "delete", "insert"]
)


def resolve_key(name: str):
    """'e' -> KeyCode, 'space' -> Key.space. Wirft ValueError bei unbekannten Namen."""
    name = name.strip()
    if not name:
        raise ValueError(tr("No key selected"))
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    try:
        return keyboard.Key[name.lower()]
    except KeyError:
        raise ValueError(tr("Unknown key: {t}", t=name)) from None


def validate_target(spec: str) -> None:
    kind, _, name = spec.partition(":")
    if kind == "mouse":
        if name not in MOUSE_BUTTONS:
            raise ValueError(tr("Unknown mouse button: {t}", t=name))
    elif kind == "key":
        resolve_key(name)
    else:
        raise ValueError(tr("Invalid target: {t}", t=spec))


def make_action(spec: str):
    """Baut eine Funktion, die den Tastendruck/Klick einmal ausführt."""
    validate_target(spec)
    kind, _, name = spec.partition(":")
    if kind == "mouse":
        ctrl, btn = mouse.Controller(), getattr(mouse.Button, name)
        return lambda: ctrl.click(btn)
    ctrl, key = keyboard.Controller(), resolve_key(name)
    return lambda: ctrl.tap(key)


def validate_hotkey(hk: str) -> None:
    try:
        keyboard.HotKey.parse(hk)
    except Exception as exc:
        raise ValueError(tr("Invalid hotkey '{hk}': {e}", hk=hk, e=exc)) from None


def pretty_hotkey(hk: str) -> str:
    return " + ".join(p.strip("<>").upper() for p in hk.split("+")) if hk else "–"


def _key_name(key) -> str | None:
    """Normalisiert eine pynput-Taste zu einem Namen (Buchstabe oder Key-Name)."""
    if isinstance(key, keyboard.Key):
        name = key.name
        for mod in MODIFIERS:
            if name.startswith(mod):   # ctrl_l -> ctrl, cmd_r -> cmd
                return mod
        return name
    char = getattr(key, "char", None)
    if char and char.isprintable():
        return char.lower()
    vk = getattr(key, "vk", None)   # z.B. Strg+P liefert ein Steuerzeichen als char
    if vk and 32 <= vk < 127:
        return chr(vk).lower()
    return None


class KeyCapture:
    """Nimmt die nächste Taste (bzw. Tastenkombination) auf. Esc bricht ab.

    on_done(result: str | None) wird im Listener-Thread aufgerufen – im UI per
    app.call_soon weiterreichen. combo=True liefert pynput-Hotkey-Syntax,
    combo=False einen einzelnen Tastennamen.
    """

    def __init__(self, on_done, combo: bool = False):
        self.on_done, self.combo = on_done, combo
        self._held: list[str] = []
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)
        self._finished = threading.Event()

    def start(self):
        self._listener.daemon = True
        self._listener.start()

    def cancel(self):
        self._finish(None)

    def _finish(self, result):
        if self._finished.is_set():
            return
        self._finished.set()
        self._listener.stop()
        self.on_done(result)

    def _press(self, key):
        name = _key_name(key)
        if name is None:
            return
        if name == "esc":
            self._finish(None)
            return
        if not self.combo:
            self._finish(name)
            return
        if name in MODIFIERS:
            if name not in self._held:
                self._held.append(name)
            return
        parts = [f"<{m}>" for m in self._held]
        parts.append(f"<{name}>" if len(name) > 1 else name)
        self._finish("+".join(parts))

    def _release(self, key):
        name = _key_name(key)
        if self.combo and name in self._held and name in MODIFIERS:
            # Nur-Modifier-Hotkey (z. B. nur Shift) ist nicht erlaubt -> weiter warten
            self._held.remove(name)
