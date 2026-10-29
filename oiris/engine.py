"""The ASB runtime: one process, one thread per sensor (SensorBus), an asyncio score/fusion
loop at 1 Hz, a guard on every output. Core resolves adapters and score modules through
the registry; it never imports a concrete driver."""
from __future__ import annotations
import asyncio, logging, time
from dataclasses import dataclass, field
from typing import Any

from .bus import SensorBus
from .config import Config
from .fusion.stack import FusionModel, fuse
from .guard.vocabulary import check_output
from .modules.liveness import indicators
from .registry import Registry, default_registry
from .schema import Event, Health, Level, Score
from .scores.base import safe_update

log = logging.getLogger(__name__)


@dataclass
class Engine:
    config: Config
    registry: Registry = field(default_factory=default_registry)
    fusion_model: FusionModel = field(default_factory=FusionModel)
    bus: SensorBus = None  # type: ignore[assignment]  # built in __post_init__
    score_modules: list = field(default_factory=list)
    results: list = field(default_factory=list)
    events: list = field(default_factory=list)
    on_event: Any = None
    face_match: Any = None      # M-16 module when enabled (oiris.modules.face_match_gate.load); else None
    face_place: str | None = None

    def __post_init__(self) -> None:
        c = self.config
        self.bus = self.bus or SensorBus(c.queue_size, c.adapter_timeout_s, c.restart_backoff_max_s,
                                         c.breaker_threshold, c.breaker_cooldown_s)
        if not self.score_modules:
            for name in self.registry.names("score"):
                p = self.registry.get("score", name)
                if p.module_flag and not c.enabled(p.module_flag):
                    continue
                try:
                    self.score_modules.append(p.factory())
                except Exception as e:  # noqa: BLE001
                    log.error("score module %s failed to construct: %s", name, e)
        self._windows: dict[str, list] = {}

    def add_adapter(self, adapter: Any, cfg: dict | None = None) -> None:
        self.bus.add(adapter, cfg)

    def _collect(self) -> dict[str, list]:
        by_cap: dict[str, list] = {}
        for aid, a in self.bus.adapters.items():
            samples = self.bus.drain(aid)
            for cap in getattr(a, "caps", ()):
                by_cap.setdefault(cap, []).extend(samples)
        return by_cap

    def step(self) -> dict:
        by_cap = self._collect()
        if self.face_match is not None:
            # M-16 consumes face frames off the bus. It returns counts only, writes to its own
            # review log and never emits an event, alert or score (spec section 6).
            for s in by_cap.get("face_frame", []):
                try:
                    self.face_match.process_frame(s.data, place=self.face_place)
                except Exception as e:  # noqa: BLE001 - M-16 can never stop the loop
                    log.error("face_match failed: %s", e)
        health = self.bus.health()
        scores: list[Score] = []
        for m in self.score_modules:
            src = [aid for aid, a in self.bus.adapters.items() if set(a.caps) & set(m.inputs)]
            if not src:
                continue   # capability absent: family masked (fallback-node behaviour)
            if all(health[s]["health"] == Health.FAILED.value for s in src):
                scores.append(Score(m.name, 0, 0, Health.FAILED, {"reason": "adapter failed"}))
                continue
            window = [s for cap in m.inputs for s in by_cap.get(cap, [])][-1:]
            if not window:
                window = self._windows.get(m.name, [])
            else:
                self._windows[m.name] = window
            scores.append(safe_update(m, window))
        res = fuse(scores, self.fusion_model, self.config.min_families_for_alert, self.config.max_unhealthy_families)
        if self.config.enabled("M-02"):
            res.update(indicators(scores))
        res["scores"] = [s.to_dict() for s in scores]
        res["health"] = health
        res["t_wall"] = time.time()
        check_output({k: v for k, v in res.items() if k != "scores"})
        self.results.append(res)
        if res["level"]:
            sig = next((x for x in res["signatures"] if x != "A11"), "A11") if res["signatures"] else "A4"
            ev = Event(sig, Level(res["level"]), res["anomaly_index"],
                       [s.module for s in scores if s.value >= 0.5 and s.health != Health.FAILED],
                       res["families_active"], health_snapshot={k: v["health"] for k, v in health.items()})
            check_output(ev.to_dict())
            self.events.append(ev)
            if self.on_event:
                try:
                    self.on_event(ev)
                except Exception as e:  # noqa: BLE001
                    log.warning("on_event handler failed: %s", e)
        return res

    async def run(self, seconds: float | None = None, hz: float = 1.0, steps: int | None = None) -> list[dict]:
        self.bus.start()
        try:
            t0, n = time.monotonic(), 0
            while (seconds is None or time.monotonic() - t0 < seconds) and (steps is None or n < steps):
                await asyncio.sleep(1 / hz)
                try:
                    self.step()
                except Exception as e:  # noqa: BLE001 - the loop never dies
                    log.error("fusion step failed: %s", e)
                n += 1
        finally:
            self.bus.stop()
        return self.results
