"""M-09 headless mode: replay adapters, virtual clock (fixed steps), no network, no hardware,
LED stub that asserts it is never driven. Deterministic output for golden comparisons."""
from __future__ import annotations
import json, socket
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from ..adapters import sim
from ..adapters.base import ReplayAdapter
from ..config import Config
from ..engine import Engine


class NetworkBlocked(RuntimeError):
    pass


@contextmanager
def no_network():
    real = socket.socket.connect

    def deny(self, *a, **k):
        raise NetworkBlocked("network disabled in headless mode")
    socket.socket.connect = deny  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = real  # type: ignore[method-assign]


class LedStub:
    driven = False

    def on(self):
        raise AssertionError("LED must never be driven in headless mode")

    def off(self):
        pass


def _round(o):
    if isinstance(o, float):
        return round(o, 6)
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items() if k not in ("t_wall", "t_mono_ns", "health")}
    if isinstance(o, list):
        return [_round(v) for v in o]
    return o


def _round_keep(o):
    if isinstance(o, float):
        return round(o, 6)
    if isinstance(o, dict):
        return {k: _round_keep(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_round_keep(v) for v in o]
    return o


def run_sync(engine: Engine, steps: int, keep_health: bool = False) -> list[dict]:
    """Virtual clock: pull every adapter synchronously, one sample per step, then fuse."""
    out = []
    for _ in range(steps):
        for aid, a in engine.bus.adapters.items():
            try:
                s = a.read(0.0)
            except Exception as e:  # noqa: BLE001
                engine.bus._failure(aid, f"read error: {e}", restart=False)
                continue
            if s is not None and engine.bus.validator(s):
                engine.bus.queues[aid].append(s)
        res = engine.step()
        out.append(_round_keep(res) if keep_health else _round(res))
    return out


def run_scenario(scenario: str, steps: int = 3, seed: int = 0, config: Config | None = None) -> list[dict]:
    cfg = config or Config()
    with no_network():
        e = Engine(cfg)
        for a in sim.make(scenario, seed=seed):
            a.open({}); e.add_adapter(a)
        return run_sync(e, steps)


def run_replay(clip_dir: Path, steps: int | None = None, config: Config | None = None) -> list[dict]:
    """clip_dir contains <adapter_id>.jsonl files and caps.json {adapter_id: [caps]}."""
    caps = json.loads((clip_dir / "caps.json").read_text(encoding="utf-8"))
    with no_network():
        e = Engine(config or Config())
        n = 0
        for aid, c in caps.items():
            a = ReplayAdapter(aid, clip_dir / f"{aid}.jsonl", set(c))
            a.open({}); e.add_adapter(a)
            n = max(n, sum(1 for line in (clip_dir / f"{aid}.jsonl").read_text().splitlines() if line.strip()))
        return run_sync(e, steps or n)


def record_clip(scenario: str, out_dir: Path, steps: int = 3, seed: int = 0) -> None:
    """Write a replayable synthetic clip (derived arrays only; no person data)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    adapters = sim.make(scenario, seed=seed)
    caps = {}
    for a in adapters:
        caps[a.id] = sorted(a.caps)
        with open(out_dir / f"{a.id}.jsonl", "w", encoding="utf-8") as f:
            for i in range(steps):
                s = a.read(0.0)
                assert s is not None
                f.write(json.dumps({"t_mono_ns": i * 1_000_000_000, "quality": s.quality, "data": _jsonable(s.data)}) + "\n")
    (out_dir / "caps.json").write_text(json.dumps(caps, indent=1), encoding="utf-8")


def _jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_jsonable(v) for v in o]
    return o


ALL_FAMILIES = ["optical", "thermal", "rf", "vital", "eye_liveness", "voice"]


def run_video(url: str, steps: int = 30, config: Config | None = None, registry=None) -> list[dict]:
    """Run the real pipeline on a video file or stream URL. Only the camera is real; every other
    sensor is ABSENT (no simulated stand-ins), and each step says so in `inputs`."""
    from ..registry import default_registry
    reg = registry or default_registry()
    e = Engine(config or Config(), reg)
    a = reg.create("sensor", "video", url)
    a.open({})
    e.add_adapter(a)
    out = []
    try:
        for r in run_sync(e, steps, keep_health=True):
            r["inputs"] = {"real": {"video": {"url": url, "source": a.SOURCE, "caps": sorted(a.caps)}},
                           "simulated": [],
                           "absent_families": [f for f in ALL_FAMILIES if f in r.get("families_missing", [])],
                           "note": "nir_pair from visible video uses one frame for on/off (no IR LED): A1 glint "
                                   "cannot fire; A2 is measured on visible light. Frames are not stored."}
            out.append(r)
    finally:
        a.close()
    return out
