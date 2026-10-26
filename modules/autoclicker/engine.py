"""Präzise Klick-Engine (ohne GUI- oder pynput-Abhängigkeit, daher gut testbar)."""
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class EngineConfig:
    action: Callable[[], None]
    interval_s: float = 0.1
    repeat_count: int = 0          # 0 = unendlich
    max_duration_s: float = 0.0    # 0 = kein Zeitlimit
    start_delay_s: float = 0.0


class ClickEngine:
    IDLE, WAITING, RUNNING = "idle", "waiting", "running"

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.state = self.IDLE
        self.count = 0
        self.started_at = 0.0
        self.last_reason = ""   # "stopped" | "count" | "timer" | "error: ..."

    @property
    def running(self) -> bool:
        return self.state != self.IDLE

    def elapsed(self) -> float:
        return time.perf_counter() - self.started_at if self.running else 0.0

    def start(self, cfg: EngineConfig) -> bool:
        with self._lock:
            if self.running:
                return False
            self._stop.clear()
            self.state = self.WAITING if cfg.start_delay_s > 0 else self.RUNNING
            self.count = 0
            self.last_reason = ""
            self.started_at = time.perf_counter()
            self._thread = threading.Thread(target=self._run, args=(cfg,), daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        self._stop.set()

    def toggle(self, cfg: EngineConfig) -> None:
        if self.running:
            self.stop()
        else:
            self.start(cfg)

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ---- intern ----
    def _sleep_until(self, deadline: float) -> None:
        """Wartet bis `deadline` (perf_counter). Grob per Event, die letzten ms per Spin."""
        while True:
            rem = deadline - time.perf_counter()
            if rem <= 0 or self._stop.is_set():
                return
            if rem > 0.003:
                if self._stop.wait(rem - 0.002):
                    return
            else:
                time.sleep(0)

    def _run(self, cfg: EngineConfig) -> None:
        reason = "stopped"
        try:
            if cfg.start_delay_s > 0:
                if self._stop.wait(cfg.start_delay_s):
                    return
                self.state = self.RUNNING
            t0 = time.perf_counter()
            self.started_at = t0
            next_t = t0
            while not self._stop.is_set():
                if cfg.repeat_count and self.count >= cfg.repeat_count:
                    reason = "count"
                    break
                if cfg.max_duration_s and time.perf_counter() - t0 >= cfg.max_duration_s:
                    reason = "timer"
                    break
                cfg.action()
                self.count += 1
                next_t = max(next_t + cfg.interval_s, time.perf_counter())
                deadline = next_t
                if cfg.max_duration_s:
                    deadline = min(deadline, t0 + cfg.max_duration_s)
                self._sleep_until(deadline)
        except Exception as exc:
            reason = f"error: {exc}"
        finally:
            self.last_reason = reason
            self.state = self.IDLE
