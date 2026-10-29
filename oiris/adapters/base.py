"""C2 sensor adapter interface (M-11) plus sim and replay variants."""
from __future__ import annotations
import json, math, random, time
from pathlib import Path
from typing import Callable, Iterator, Literal, Protocol, runtime_checkable

from ..schema import Health, Sample

Bus = Literal["i2c", "csi", "usb", "uart", "i2s", "gpio", "ble", "wifi", "android", "sim", "replay"]


@runtime_checkable
class SensorAdapter(Protocol):
    id: str
    bus: str
    caps: set
    license: str

    def open(self, cfg: dict) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
    def read(self, timeout_s: float) -> Sample | None: ...
    def health(self) -> tuple[Health, str]: ...


class AdapterBase:
    id = "base"
    bus = "sim"
    caps: set = set()
    license = "Apache-2.0"
    units = ""

    def __init__(self, adapter_id: str | None = None):
        if adapter_id:
            self.id = adapter_id
        self._seq = 0
        self._health = (Health.OK, "")
        self._running = False
        self.cfg: dict = {}

    def open(self, cfg: dict) -> None:
        self.cfg = dict(cfg or {})

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def close(self) -> None:
        self._running = False

    def health(self):
        return self._health

    def set_health(self, h: Health, reason: str = "") -> None:
        self._health = (h, reason)

    def _sample(self, data, quality: float = 1.0, t_mono_ns: int | None = None, replay=False) -> Sample:
        self._seq += 1
        return Sample(self.id, t_mono_ns if t_mono_ns is not None else time.monotonic_ns(),
                      time.time(), self._seq, self.units, quality, data, replay)

    def read(self, timeout_s: float) -> Sample | None:  # pragma: no cover - abstract
        raise NotImplementedError


class SimAdapter(AdapterBase):
    """Synthetic generator: produce(t, rng) -> data. Deterministic with a seed."""
    bus = "sim"

    def __init__(self, adapter_id: str, caps: set, produce: Callable, period_s: float = 0.0,
                 seed: int = 0, units: str = "", fail_after: int | None = None):
        super().__init__(adapter_id)
        self.caps = set(caps)
        self.produce = produce
        self.period_s = period_s
        self.rng = random.Random(seed)
        self.units = units
        self.fail_after = fail_after
        self.t = 0.0

    def read(self, timeout_s: float) -> Sample | None:
        if self.fail_after is not None and self._seq >= self.fail_after:
            raise RuntimeError("simulated adapter crash")
        if self.period_s:
            time.sleep(min(self.period_s, timeout_s))
        self.t += self.period_s or 0.1
        return self._sample(self.produce(self.t, self.rng))


class ReplayAdapter(AdapterBase):
    """Replays a JSON-lines clip; recorded t_mono_ns preserved so fusion cannot tell."""
    bus = "replay"

    def __init__(self, adapter_id: str, path: str | Path, caps: set | None = None):
        super().__init__(adapter_id)
        self.path = Path(path)
        self.caps = set(caps or {"replay"})
        self._it: Iterator | None = None

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        self._it = iter(self.path.read_text(encoding="utf-8").splitlines())

    def read(self, timeout_s: float) -> Sample | None:
        assert self._it is not None, "open() first"
        for line in self._it:
            if not line.strip():
                continue
            rec = json.loads(line)
            return self._sample(rec["data"], rec.get("quality", 1.0), int(rec["t_mono_ns"]), replay=True)
        return None


def sine(freq_hz: float, amp: float = 1.0, offset: float = 0.0, noise: float = 0.0):
    def f(t, rng):
        return offset + amp * math.sin(2 * math.pi * freq_hz * t) + rng.gauss(0, noise)
    return f
