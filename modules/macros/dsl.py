"""Makro-Sprache (DSL), Prüfer, Ausführer und Offline-Generator. Kein pynput/GUI-Import (gut testbar).

Befehle (eine pro Zeile, Groß-/Kleinschreibung egal, '#' beginnt einen Kommentar):
  click [left|right|middle] [X Y]        Klick (optional an Position)
  doubleclick [left|right|middle] [X Y]  Doppelklick
  move X Y                               Maus bewegen (Bildschirmkoordinaten)
  key NAME                               Taste drücken (a, 5, f5, space, enter, ctrl, ...)
  hold NAME DAUER                        Taste halten
  type "Text"                            Text eintippen
  scroll N                               Scrollen (positiv = hoch, negativ = runter)
  wait DAUER                             Warten (50ms, 1.5s, 2m; ohne Einheit = ms)
  repeat N | repeat forever   ...   end  Wiederholen (bis zu 3 Ebenen; 'forever' nur ganz außen)
"""
import re
import threading
import time
from dataclasses import dataclass, field

from core.i18n import tr

MAX_LINES = 400
MAX_DEPTH = 3
MAX_STEPS = 2_000_000          # geplante Aktionen insgesamt (bei endlichen Schleifen)
MAX_COORD = 20000
MAX_TEXT = 500
MAX_WAIT_S = 3600
BUTTONS = ("left", "right", "middle")
KEY_NAMES = set([chr(c) for c in range(ord("a"), ord("z") + 1)] + [str(i) for i in range(10)] +
                [f"f{i}" for i in range(1, 13)] +
                ["space", "enter", "tab", "backspace", "esc", "up", "down", "left", "right", "shift", "ctrl", "alt",
                 "home", "end", "page_up", "page_down", "delete", "insert"])


class MacroError(Exception):
    def __init__(self, line: int, message: str):
        super().__init__(f"{tr('Line')} {line}: {message}" if line else message)
        self.line, self.message = line, message


@dataclass
class Cmd:
    op: str
    args: tuple = ()
    line: int = 0
    body: list = field(default_factory=list)       # nur für repeat


_DUR = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(ms|s|m|min)?$", re.I)


def parse_duration(text: str, line: int = 0) -> float:
    m = _DUR.match(text.strip())
    if not m:
        raise MacroError(line, tr("Invalid duration: {t}", t=text))
    value = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "ms").lower()
    sec = value / 1000 if unit == "ms" else value if unit == "s" else value * 60
    if sec > MAX_WAIT_S:
        raise MacroError(line, tr("Duration too long (max. 1 hour)."))
    return sec


def _tokens(line: str, n: int) -> list[str]:
    """Teilt eine Zeile; Text in Anführungszeichen bleibt ein Token."""
    out = re.findall(r'"[^"]*"|\S+', line)
    return out


def _int(tok: str, line: int, lo=-MAX_COORD, hi=MAX_COORD) -> int:
    try:
        v = int(tok)
    except ValueError:
        raise MacroError(line, tr("Number expected, found: {t}", t=tok)) from None
    if not lo <= v <= hi:
        raise MacroError(line, tr("Number out of range: {t}", t=tok))
    return v


def parse(text: str) -> list[Cmd]:
    raw = text.replace("\r\n", "\n").split("\n")
    if len(raw) > MAX_LINES:
        raise MacroError(0, tr("Too many lines (max. {n}).", n=MAX_LINES))
    root: list[Cmd] = []
    stack: list[tuple[Cmd | None, list[Cmd]]] = [(None, root)]
    for no, orig in enumerate(raw, start=1):
        line = orig.split("#", 1)[0].strip() if '"' not in orig else _strip_comment(orig)
        if not line:
            continue
        tok = _tokens(line, 0)
        op, rest = tok[0].lower(), tok[1:]
        cur = stack[-1][1]
        if op == "end":
            if len(stack) == 1:
                raise MacroError(no, tr("'end' without 'repeat'."))
            stack.pop()
        elif op == "repeat":
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: repeat N  or  repeat forever"))
            if len(stack) > MAX_DEPTH:
                raise MacroError(no, tr("Loops may be nested at most {n} levels deep.", n=MAX_DEPTH))
            if rest[0].lower() == "forever":
                if len(stack) > 1:
                    raise MacroError(no, tr("'repeat forever' is only allowed on the outermost level."))
                count = 0
            else:
                count = _int(rest[0], no, 1, 1_000_000)
            c = Cmd("repeat", (count,), no)
            cur.append(c)
            stack.append((c, c.body))
        elif op in ("click", "doubleclick"):
            btn, xy = "left", None
            r = list(rest)
            if r and r[0].lower() in BUTTONS:
                btn = r.pop(0).lower()
            if r:
                if len(r) != 2:
                    raise MacroError(no, tr("Usage: {op} [left|right|middle] [X Y]", op=op))
                xy = (_int(r[0], no, 0), _int(r[1], no, 0))
            cur.append(Cmd(op, (btn, xy), no))
        elif op == "move":
            if len(rest) != 2:
                raise MacroError(no, tr("Usage: move X Y"))
            cur.append(Cmd("move", (_int(rest[0], no, 0), _int(rest[1], no, 0)), no))
        elif op == "key":
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: key NAME"))
            cur.append(Cmd("key", (_key(rest[0], no),), no))
        elif op == "hold":
            if len(rest) != 2:
                raise MacroError(no, tr("Usage: hold NAME DURATION"))
            cur.append(Cmd("hold", (_key(rest[0], no), parse_duration(rest[1], no)), no))
        elif op == "type":
            if len(rest) != 1 or not rest[0].startswith('"') or not rest[0].endswith('"') or len(rest[0]) < 2:
                raise MacroError(no, tr('Usage: type "text"'))
            s = rest[0][1:-1]
            if len(s) > MAX_TEXT:
                raise MacroError(no, tr("Text too long."))
            cur.append(Cmd("type", (s,), no))
        elif op == "scroll":
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: scroll N"))
            cur.append(Cmd("scroll", (_int(rest[0], no, -1000, 1000),), no))
        elif op == "wait":
            if len(rest) != 1:
                raise MacroError(no, tr("Usage: wait DURATION"))
            cur.append(Cmd("wait", (parse_duration(rest[0], no),), no))
        else:
            raise MacroError(no, tr("Unknown command: {op}", op=tok[0]))
    if len(stack) > 1:
        raise MacroError(stack[-1][0].line, tr("'repeat' without 'end'."))
    if not root:
        raise MacroError(0, tr("The macro is empty."))
    check(root)
    return root


def _strip_comment(orig: str) -> str:
    out, quoted = [], False
    for ch in orig:
        if ch == '"':
            quoted = not quoted
        if ch == "#" and not quoted:
            break
        out.append(ch)
    return "".join(out).strip()


def _key(tok: str, line: int) -> str:
    k = tok.lower() if len(tok) > 1 else tok
    if k.lower() not in KEY_NAMES:
        raise MacroError(line, tr("Unknown key: {t}", t=tok))
    return k.lower()


def _wait_in(cmds: list[Cmd]) -> float:
    total = 0.0
    for c in cmds:
        if c.op == "wait":
            total += c.args[0]
        elif c.op == "hold":
            total += c.args[1]
        elif c.op == "repeat":
            total += _wait_in(c.body) * (c.args[0] or 1)
    return total


def _steps(cmds: list[Cmd]) -> int:
    n = 0
    for c in cmds:
        n += (c.args[0] or 1) * max(1, _steps(c.body)) if c.op == "repeat" else 1
        if n > MAX_STEPS * 10:
            break
    return n


def check(cmds: list[Cmd]) -> None:
    """Schutzregeln: keine Endlosschleife ohne Pause, begrenzte Gesamtmenge."""
    for c in cmds:
        if c.op == "repeat":
            if not c.body:
                raise MacroError(c.line, tr("The loop is empty."))
            if c.args[0] == 0 and _wait_in(c.body) < 0.001:
                raise MacroError(c.line, tr("'repeat forever' needs at least a 'wait 1ms' inside."))
            check(c.body)
    if _steps(cmds) > MAX_STEPS:
        raise MacroError(0, tr("The macro would run too many actions."))


# ---------------------------------------------------------------- Ausführung
class Runner:
    """backend: Objekt mit click(button, xy, count), move(x, y), key(name), hold(name, sec), type(text), scroll(n)."""

    def __init__(self, backend, sleep=None):
        self.backend = backend
        self.stop_event = threading.Event()
        self.steps = 0
        self._sleep = sleep or self._wait

    def _wait(self, sec: float) -> None:
        self.stop_event.wait(sec)       # lässt sich sofort abbrechen

    def stop(self) -> None:
        self.stop_event.set()

    def run(self, cmds: list[Cmd]) -> str:
        """Gibt 'done' oder 'stopped' zurück."""
        self.stop_event.clear()
        self.steps = 0
        self._block(cmds)
        return "stopped" if self.stop_event.is_set() else "done"

    def _block(self, cmds):
        for c in cmds:
            if self.stop_event.is_set():
                return
            op, a = c.op, c.args
            if op == "repeat":
                n = 0
                while (a[0] == 0 or n < a[0]) and not self.stop_event.is_set():
                    self._block(c.body)
                    n += 1
                continue
            if op == "click":
                self.backend.click(a[0], a[1], 1)
            elif op == "doubleclick":
                self.backend.click(a[0], a[1], 2)
            elif op == "move":
                self.backend.move(*a)
            elif op == "key":
                self.backend.key(a[0])
            elif op == "hold":
                self.backend.hold(a[0], a[1], self)
            elif op == "type":
                self.backend.type(a[0])
            elif op == "scroll":
                self.backend.scroll(a[0])
            elif op == "wait":
                self._sleep(a[0])
            self.steps += 1


class PynputBackend:
    def __init__(self):
        from pynput import keyboard, mouse
        self.kb, self.ms = keyboard.Controller(), mouse.Controller()
        self._Key, self._KeyCode, self._Button = keyboard.Key, keyboard.KeyCode, mouse.Button

    def _k(self, name):
        return self._KeyCode.from_char(name) if len(name) == 1 else self._Key[name]

    def click(self, button, xy, count):
        if xy:
            self.ms.position = xy
        self.ms.click(getattr(self._Button, button), count)

    def move(self, x, y):
        self.ms.position = (x, y)

    def key(self, name):
        self.kb.tap(self._k(name))

    def hold(self, name, sec, runner):
        k = self._k(name)
        self.kb.press(k)
        try:
            runner.stop_event.wait(sec)
        finally:
            self.kb.release(k)

    def type(self, text):
        self.kb.type(text)

    def scroll(self, n):
        self.ms.scroll(0, n)


# ---------------------------------------------------------------- Offline-Generator (Deutsch/Englisch)
_NUM = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"(ms|millisekunden?|milliseconds?|sekunden?|sek|s|seconds?|sec|minuten?|min|minutes?|m)"
_RE_INTERVAL = re.compile(r"(?:alle|jede[nr]?|every|each)\s+" + _NUM + r"\s*" + _UNIT + r"\b", re.I)
_RE_FOR = re.compile(r"(?:für|fuer|for|während|innerhalb)\s+" + _NUM + r"\s*" + _UNIT + r"\b", re.I)
_RE_TIMES = re.compile(r"(\d+)\s*(?:mal|x|times|malig)\b", re.I)
_RE_POS = re.compile(r"(?:position|pos\.?|at|an|auf|bei|nach|to|zu)?\s*\(?\s*(\d{1,5})\s*[,; /x]\s*(\d{1,5})\s*\)?", re.I)
_RE_WAIT = re.compile(r"(?:warte|wait|pause|sleep)\s*" + _NUM + r"\s*" + _UNIT + r"?", re.I)
_RE_TEXT = re.compile(r"(?:tippe|schreibe|eingeben|type|write|enter)\s+(?:den text\s+|the text\s+)?[\"“„']([^\"”“']+)[\"”“']", re.I)
_RE_KEY = re.compile(r"(?:drücke|druecke|drück|press|hit|tippe)\s+(?:die\s+|the\s+)?(?:taste\s+|key\s+)?([a-z0-9_]+)\b", re.I)
_RE_SCROLL = re.compile(r"(?:scrolle|scroll)\w*\s*(hoch|runter|up|down)?\s*(\d+)?", re.I)
_SPLIT = re.compile(r"\s*(?:,|;|\.\s|\bdann\b|\bund dann\b|\banschließend\b|\banschliessend\b|\bdanach\b|\bthen\b|\band then\b|\bafter that\b)\s*", re.I)
_KEYALIAS = {"leertaste": "space", "space": "space", "enter": "enter", "eingabe": "enter", "tab": "tab", "escape": "esc",
             "esc": "esc", "strg": "ctrl", "ctrl": "ctrl", "umschalt": "shift", "shift": "shift", "alt": "alt"}


def _sec(num: str, unit: str | None) -> float:
    v = float(num.replace(",", "."))
    u = (unit or "ms").lower()
    if u.startswith("ms") or u.startswith("milli"):
        return v / 1000
    if u in ("m", "min") or u.startswith("minut"):
        return v * 60
    return v


def _fmt(sec: float) -> str:
    ms = round(sec * 1000)
    return f"{ms}ms" if ms % 1000 else f"{ms // 1000}s"


def generate_offline(text: str) -> tuple[str, list[str]] | None:
    """Erzeugt ein Makro aus einfachen deutschen/englischen Sätzen. None = nicht verstanden (dann KI fragen)."""
    lines: list[str] = []
    notes: list[str] = []
    for seg in [s for s in _SPLIT.split(text.strip()) if s.strip()]:
        low = seg.lower()
        interval = _RE_INTERVAL.search(seg)
        dur = _RE_FOR.search(seg)
        times = _RE_TIMES.search(seg)
        action: list[str] = []
        tm = _RE_TEXT.search(seg)
        wm = _RE_WAIT.search(seg)
        pos = _RE_POS.search(seg[:interval.start()] + " " + seg[interval.end():] if interval else seg)
        if interval and pos and interval.group(0).strip() and pos.group(0).strip().isdigit():
            pos = None
        xy = f" {pos.group(1)} {pos.group(2)}" if pos and not (dur and pos.start() >= dur.start() and pos.end() <= dur.end()) else ""
        btn = "right" if re.search(r"rechts|right", low) else "middle" if re.search(r"mittel|middle", low) else "left"
        if tm:
            action = [f'type "{tm.group(1)}"']
        elif re.search(r"doppel\s*klick|double\s*-?\s*click", low):
            action = [f"doubleclick {btn}{xy}".strip()]
        elif re.search(r"klick|click|klicke", low):
            action = [f"click {btn}{xy}".strip()]
        elif re.search(r"bewege|move|mauszeiger", low) and xy:
            action = [f"move{xy}"]
        elif _RE_SCROLL.search(seg) and re.search(r"scroll", low):
            sm = _RE_SCROLL.search(seg)
            n = int(sm.group(2) or 3) * (-1 if (sm.group(1) or "").lower() in ("runter", "down") else 1)
            action = [f"scroll {n}"]
        elif _RE_KEY.search(seg) and not (wm and not re.search(r"dr[üu]ck|press|hit", low)):
            k = _RE_KEY.search(seg).group(1).lower()
            k = _KEYALIAS.get(k, k)
            if k in KEY_NAMES:
                action = [f"key {k}"]
        if not action and wm:
            lines.append(f"wait {_fmt(_sec(wm.group(1), wm.group(2)))}")
            continue
        if not action:
            notes.append(tr("Not understood: {s}", s=seg.strip()))
            continue
        if interval:
            gap = _sec(interval.group(1), interval.group(2))
            body = action + [f"wait {_fmt(max(gap, 0.001))}"]
            if dur:
                n = max(1, round(_sec(dur.group(1), dur.group(2)) / max(gap, 0.001)))
                lines += [f"repeat {n}"] + ["  " + b for b in body] + ["end"]
            elif times:
                lines += [f"repeat {int(times.group(1))}"] + ["  " + b for b in body] + ["end"]
            else:
                lines += ["repeat forever"] + ["  " + b for b in body] + ["end"]
        elif times:
            lines += [f"repeat {int(times.group(1))}"] + ["  " + b for b in action] + ["  wait 10ms", "end"]
        else:
            lines += action
    if not lines:
        return None
    script = "\n".join(lines)
    try:
        parse(script)
    except MacroError as exc:
        notes.append(str(exc))
        return None
    return script, notes


def extract_script(ai_text: str) -> str:
    """Zieht das Skript aus einer KI-Antwort (entfernt Codezäune und Erklärungen)."""
    m = re.search(r"```(?:\w+)?\n(.*?)```", ai_text, re.S)
    body = m.group(1) if m else ai_text
    return body.strip()
