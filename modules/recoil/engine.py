"""Anti-Recoil-Engine: gleicht Rückstoß durch kleine Mausbewegungen aus, solange die linke Taste gehalten wird.

Universell: kennt weder Spiel noch Waffe, liest keinen Spielspeicher. Es bewegt nur die Maus nach den Einstellungen.
Grenzen: Spiele mit "Raw Input" ignorieren oft simulierte Mausbewegungen; Anti-Cheat erkennt dieses Muster leicht.
Das Modul enthält bewusst keine Tarnung (kein Zufallsrauschen, keine Treiber, keine Umgehung).
"""
import threading
import time
from dataclasses import dataclass

PRESETS = {                      # Pixel pro Schritt (vertikal, horizontal), Schrittabstand in ms
    "Light": {"y": 1.0, "x": 0.0, "interval_ms": 12, "ramp_pct": 0, "ramp_ms": 400, "delay_ms": 0},
    "Medium": {"y": 2.0, "x": 0.0, "interval_ms": 10, "ramp_pct": 25, "ramp_ms": 600, "delay_ms": 0},
    "Heavy": {"y": 3.5, "x": 0.0, "interval_ms": 8, "ramp_pct": 40, "ramp_ms": 900, "delay_ms": 0},
}
LIMITS = {"y": (-20.0, 20.0), "x": (-20.0, 20.0), "interval_ms": (4, 100), "ramp_pct": (0, 100),
          "ramp_ms": (50, 5000), "delay_ms": (0, 2000)}


@dataclass
class RecoilConfig:
    y: float = 2.0
    x: float = 0.0
    interval_ms: int = 10
    ramp_pct: int = 25
    ramp_ms: int = 600
    delay_ms: int = 0

    def clamp(self) -> "RecoilConfig":
        for k, (lo, hi) in LIMITS.items():
            setattr(self, k, type(getattr(self, k))(min(hi, max(lo, getattr(self, k)))))
        return self

    @classmethod
    def from_dict(cls, d: dict | None) -> "RecoilConfig":
        base = cls()
        for k in LIMITS:
            try:
                if d and k in d:
                    setattr(base, k, type(getattr(base, k))(float(d[k])))
            except (TypeError, ValueError):
                pass
        return base.clamp()


def step(cfg: RecoilConfig, held_ms: float) -> tuple[float, float]:
    """Soll-Bewegung (dx, dy) in Pixeln für einen Schritt, wenn die Taste seit held_ms gehalten wird."""
    if held_ms < cfg.delay_ms:
        return 0.0, 0.0
    t = held_ms - cfg.delay_ms
    factor = 1.0 + (cfg.ramp_pct / 100.0) * min(1.0, t / cfg.ramp_ms)
    return cfg.x * factor, cfg.y * factor


class Compensator:
    """Sammelt Bruchteile von Pixeln, damit auch Werte wie 1.4 px im Mittel stimmen."""

    def __init__(self):
        self.rx = self.ry = 0.0

    def feed(self, dx: float, dy: float) -> tuple[int, int]:
        self.rx = round(self.rx + dx, 6)
        self.ry = round(self.ry + dy, 6)
        ix, iy = int(self.rx), int(self.ry)
        self.rx -= ix
        self.ry -= iy
        return ix, iy


class RecoilEngine:
    """backend.move_relative(dx, dy). Läuft nur, solange enabled und die Taste gehalten wird."""

    def __init__(self, backend, cfg: RecoilConfig, clock=time.perf_counter):
        self.backend, self.cfg, self.clock = backend, cfg, clock
        self.enabled = False
        self._held = threading.Event()
        self._quit = threading.Event()
        self._thread: threading.Thread | None = None
        self.moves = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._quit.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        self._quit.set()
        self._held.set()

    def set_pressed(self, pressed: bool) -> None:
        self._held.set() if pressed else self._held.clear()

    def _loop(self) -> None:
        comp = Compensator()
        while not self._quit.is_set():
            if not (self.enabled and self._held.is_set()):
                comp = Compensator()
                self._held.wait(0.2) if not self._held.is_set() else self._quit.wait(0.05)
                continue
            t0 = self.clock()
            while self.enabled and self._held.is_set() and not self._quit.is_set():
                dx, dy = step(self.cfg, (self.clock() - t0) * 1000)
                ix, iy = comp.feed(dx, dy)
                if ix or iy:
                    self.backend.move_relative(ix, iy)
                    self.moves += 1
                self._quit.wait(self.cfg.interval_ms / 1000)
