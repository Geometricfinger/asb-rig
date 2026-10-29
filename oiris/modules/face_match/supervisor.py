"""Fault isolation for the face backend (ADR-0048, spec section 12). Every backend call
runs in a helper thread with a timeout. Exceptions, hangs and garbage -> DEGRADED;
N consecutive failures -> FAILED and the breaker opens for the cooldown. Nothing a
backend does can raise out of here."""
from __future__ import annotations
import logging, threading, time
from typing import Any, Callable

from ...schema import Health

log = logging.getLogger(__name__)


class Guarded:
    def __init__(self, backend: Any, timeout_s: float = 2.0, breaker_threshold: int = 5,
                 breaker_cooldown_s: float = 30.0, clock: Callable[[], float] = time.monotonic):
        self.backend = backend
        self.timeout_s = timeout_s
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown_s = breaker_cooldown_s
        self.clock = clock
        self.health: Health = Health.OK
        self.reason = ""
        self.consecutive_failures = 0
        self.breaker_open_until = 0.0
        self.calls = self.failures = self.timeouts = 0

    def _fail(self, why: str) -> None:
        self.failures += 1
        self.consecutive_failures += 1
        self.reason = why
        if self.consecutive_failures >= self.breaker_threshold:
            self.health = Health.FAILED
            self.breaker_open_until = self.clock() + self.breaker_cooldown_s
        else:
            self.health = Health.DEGRADED
        log.warning("face backend %s: %s", getattr(self.backend, "name", "?"), why)

    def call(self, method: str, *args: Any, validate: Callable[[Any], bool] | None = None) -> tuple[bool, Any]:
        if self.breaker_open_until > self.clock():
            return False, None
        self.calls += 1
        box: dict[str, Any] = {}

        def run() -> None:
            try:
                box["v"] = getattr(self.backend, method)(*args)
            except BaseException as e:  # noqa: BLE001 - SystemExit from a plugin included
                box["e"] = e

        t = threading.Thread(target=run, name=f"face-{method}", daemon=True)
        t.start()
        t.join(self.timeout_s)
        if t.is_alive():
            self.timeouts += 1
            self._fail(f"{method} timed out")
            return False, None
        if "e" in box:
            self._fail(f"{method} raised {type(box['e']).__name__}")
            return False, None
        v = box.get("v")
        try:
            ok = validate(v) if validate else True
        except Exception:  # noqa: BLE001
            ok = False
        if not ok:
            self._fail(f"{method} returned garbage")
            return False, None
        self.consecutive_failures = 0
        self.health, self.reason = Health.OK, ""
        return True, v
