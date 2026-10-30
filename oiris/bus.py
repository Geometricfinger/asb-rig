"""M-11 sensor bus: one thread per adapter, fault-isolated.

Each adapter thread is wrapped by: exception guard, per-read timeout watchdog,
restart with exponential back-off (<= restart_backoff_max_s), and a circuit
breaker that opens after N consecutive failures (adapter -> FAILED, no restarts
until cooldown). Garbage samples are rejected by a validator. Nothing an adapter
does can raise out of the bus."""
from __future__ import annotations
import collections, logging, threading, time
from dataclasses import dataclass
from typing import Any, Callable

from .schema import Health, Sample

log = logging.getLogger(__name__)


@dataclass
class AdapterState:
    health: Health = Health.OK
    reason: str = ""
    restarts: int = 0
    consecutive_failures: int = 0
    breaker_open_until: float = 0.0
    drops: int = 0
    rejected: int = 0
    samples: int = 0
    last_sample_t: float = 0.0
    timeouts: int = 0


def default_validator(s: Any) -> bool:
    if not isinstance(s, Sample):
        return False
    if not isinstance(s.t_mono_ns, int) or s.t_mono_ns < 0:
        return False
    try:
        q = float(s.quality)
    except (TypeError, ValueError):
        return False
    return 0.0 <= q <= 1.0


class SensorBus:
    def __init__(self, queue_size: int = 64, timeout_s: float = 2.0, backoff_max_s: float = 10.0,
                 breaker_threshold: int = 5, breaker_cooldown_s: float = 30.0,
                 validator: Callable[[Any], bool] = default_validator, backoff_base_s: float = 0.05,
                 hung_disable_s: float = 30.0):
        self.queue_size = queue_size
        self.timeout_s = timeout_s
        self.backoff_max_s = backoff_max_s
        self.backoff_base_s = backoff_base_s
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown_s = breaker_cooldown_s
        self.validator = validator
        self.hung_disable_s = hung_disable_s
        # Forge F2: at most one in-flight read thread per adapter: (thread, result box, started_mono)
        self._inflight: dict[str, tuple[threading.Thread, dict, float]] = {}
        self.adapters: dict[str, Any] = {}
        self.state: dict[str, AdapterState] = {}
        self.queues: dict[str, collections.deque] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def add(self, adapter: Any, cfg: dict | None = None) -> None:
        aid = adapter.id
        self.adapters[aid] = adapter
        self.state[aid] = AdapterState()
        self.queues[aid] = collections.deque(maxlen=self.queue_size)
        self._cfg = getattr(self, "_cfg", {})
        self._cfg[aid] = cfg or {}

    def start(self) -> None:
        self._stop.clear()
        for aid in self.adapters:
            t = threading.Thread(target=self._run, args=(aid,), name=f"adapter-{aid}", daemon=True)
            self._threads[aid] = t
            t.start()

    def stop(self, join_s: float = 2.0) -> None:
        self._stop.set()
        for _aid, a in self.adapters.items():
            self._safe(a, "stop")
            self._safe(a, "close")
        for t in self._threads.values():
            t.join(join_s)

    @staticmethod
    def _safe(a: Any, method: str, *args: Any) -> Any:
        try:
            return getattr(a, method)(*args)
        except Exception as e:  # noqa: BLE001 - isolation is the point
            log.warning("%s.%s failed: %s", getattr(a, "id", "?"), method, e)
            return None

    def _mark(self, aid: str, h: Health, reason: str) -> None:
        with self._lock:
            st = self.state[aid]
            st.health, st.reason = h, reason

    def _read_with_timeout(self, a: Any) -> tuple[str, Any]:
        """Run read() in a helper thread so a hung driver cannot freeze the adapter loop.

        Forge F2: never more than one read thread per adapter. While a timed-out read is still
        running no new read is spawned; the call waits on the existing one and reports "hung".
        A read that finally returns after timing out reports "late" (its value is discarded)."""
        aid = a.id
        cur = self._inflight.get(aid)
        if cur is not None:
            t, _box, _t0 = cur
            t.join(self.timeout_s)
            if t.is_alive():
                return "hung", None
            del self._inflight[aid]
            return "late", None
        box: dict[str, Any] = {}

        def call() -> None:
            try:
                box["v"] = a.read(self.timeout_s)
            except BaseException as e:  # noqa: BLE001
                box["e"] = e

        t = threading.Thread(target=call, daemon=True, name=f"read-{aid}")
        self._inflight[aid] = (t, box, time.monotonic())
        t.start()
        t.join(self.timeout_s)
        if t.is_alive():
            return "timeout", None
        del self._inflight[aid]
        if "e" in box:
            return "error", box["e"]
        return "ok", box.get("v")

    def inflight_reads(self) -> int:
        return sum(1 for t, _b, _t0 in list(self._inflight.values()) if t.is_alive())

    def _run(self, aid: str) -> None:
        a, st = self.adapters[aid], self.state[aid]
        opened = False
        while not self._stop.is_set():
            now = time.monotonic()
            if st.breaker_open_until > now:
                self._stop.wait(min(0.2, st.breaker_open_until - now))
                continue
            if not opened:
                try:
                    a.open(self._cfg.get(aid, {}))
                    a.start()
                    opened = True
                except Exception as e:  # noqa: BLE001
                    self._failure(aid, f"open failed: {e}")
                    continue
            kind, v = self._read_with_timeout(a)
            if kind == "hung":
                hung_for = time.monotonic() - self._inflight[aid][2] if aid in self._inflight else 0.0
                with self._lock:
                    st.timeouts += 1
                # counts toward the circuit breaker (no restart while the read is still in flight)
                self._failure(aid, f"hung: read in flight {hung_for:.1f}s", restart=False)
                if hung_for >= self.hung_disable_s:
                    # supervisor: disabled until the driver's read returns; then the restart path runs
                    self._mark(aid, Health.FAILED, f"disabled: read hung {hung_for:.1f}s, waiting for driver")
                continue
            if kind == "late":
                # the hung read returned; restart the adapter cleanly (its late value is discarded)
                self._mark(aid, Health.DEGRADED, "recovered from hung read; restarting")
                self._safe(a, "stop")
                self._safe(a, "close")
                opened = False
                continue
            if kind == "ok":
                if v is None:  # end of stream / nothing available
                    self._stop.wait(0.01)
                    if getattr(a, "bus", "") == "replay":
                        self._mark(aid, Health.DEGRADED, "replay ended")
                        return
                    continue
                if not self.validator(v):
                    with self._lock:
                        st.rejected += 1
                    self._failure(aid, "garbage sample rejected", restart=False)
                    continue
                q = self.queues[aid]
                with self._lock:
                    if len(q) == q.maxlen:
                        st.drops += 1
                    q.append(v)
                    st.samples += 1
                    st.last_sample_t = time.monotonic()
                    st.consecutive_failures = 0
                    try:
                        h, r = a.health()
                    except Exception:  # noqa: BLE001
                        h, r = Health.DEGRADED, "health() raised"
                    st.health, st.reason = Health(h), r
            else:
                if kind == "timeout":
                    st.timeouts += 1
                self._failure(aid, f"read {kind}: {v}" if v else f"read {kind}")
                self._safe(a, "stop")
                self._safe(a, "close")
                opened = False

    def _failure(self, aid: str, reason: str, restart: bool = True) -> None:
        st = self.state[aid]
        with self._lock:
            st.consecutive_failures += 1
            n = st.consecutive_failures
            if restart:
                st.restarts += 1
        if n >= self.breaker_threshold:
            st.breaker_open_until = time.monotonic() + self.breaker_cooldown_s
            st.consecutive_failures = 0
            self._mark(aid, Health.FAILED, f"circuit open: {reason}")
            log.error("adapter %s circuit open: %s", aid, reason)
            return
        self._mark(aid, Health.DEGRADED, reason)
        if restart:
            self._stop.wait(min(self.backoff_max_s, self.backoff_base_s * 2 ** (n - 1)))

    def drain(self, aid: str) -> list[Sample]:
        with self._lock:
            q = self.queues[aid]
            out = list(q)
            q.clear()
        return out

    def health(self) -> dict[str, dict]:
        with self._lock:
            return {aid: {"health": st.health.value, "reason": st.reason, "restarts": st.restarts,
                          "drops": st.drops, "rejected": st.rejected, "samples": st.samples,
                          "timeouts": st.timeouts} for aid, st in self.state.items()}
