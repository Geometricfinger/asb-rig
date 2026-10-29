"""Fault injection: crashing, hanging, garbage-emitting, failing-to-open adapters and
crashing/NaN score modules must never take down the process; fusion degrades."""
import asyncio, math, threading, time
import pytest

from asb.adapters import sim
from asb.adapters.base import AdapterBase, SimAdapter
from asb.bus import SensorBus
from asb.config import Config
from asb.engine import Engine
from asb.schema import Health, Score
from asb.scores.base import safe_update


class Crasher(AdapterBase):
    id, caps = "crasher", {"thermal_frame"}
    def read(self, t):
        raise RuntimeError("boom")


class Hanger(AdapterBase):
    id, caps = "hanger", {"rf_adv"}
    def read(self, t):
        time.sleep(30)


class Garbage(AdapterBase):
    id, caps = "garbage", {"radar"}
    def read(self, t):
        time.sleep(0.01)
        return {"not": "a sample"}


class BadOpen(AdapterBase):
    id, caps = "badopen", {"motion"}
    def open(self, cfg):
        raise OSError("device missing")
    def read(self, t):
        return None


class SysExit(AdapterBase):
    id, caps = "sysexit", {"site_diff"}
    def read(self, t):
        raise SystemExit("driver called exit()")


def fast_bus(**kw):
    return SensorBus(timeout_s=0.2, backoff_base_s=0.01, backoff_max_s=0.05, breaker_threshold=3,
                     breaker_cooldown_s=60, **kw)


def wait_for(cond, s=5.0):
    end = time.time() + s
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_bad_adapters_isolated_good_one_keeps_running():
    bus = fast_bus()
    good = SimAdapter("good", {"nir_pair"}, lambda t, r: 1, period_s=0.01)
    for a in (Crasher(), Hanger(), Garbage(), BadOpen(), SysExit(), good):
        bus.add(a)
    bus.start()
    try:
        assert wait_for(lambda: all(bus.state[x].health == Health.FAILED for x in
                                    ("crasher", "hanger", "badopen", "sysexit")), 8)
        assert wait_for(lambda: bus.state["garbage"].rejected >= 3)
        assert bus.state["good"].samples > 5 and bus.state["good"].health == Health.OK
        assert bus.state["hanger"].timeouts >= 1
        assert "circuit open" in bus.state["crasher"].reason
    finally:
        bus.stop(0.5)
    assert threading.main_thread().is_alive()


def test_restart_with_backoff_recovers():
    calls = {"n": 0}

    def produce(t, r):
        calls["n"] += 1
        if calls["n"] in (2, 3):
            raise RuntimeError("transient")
        return 1
    bus = fast_bus()
    bus.breaker_threshold = 10
    bus.add(SimAdapter("flaky", {"x"}, produce, period_s=0.005))
    bus.start()
    try:
        assert wait_for(lambda: bus.state["flaky"].samples >= 5)
        assert bus.state["flaky"].restarts >= 2 and bus.state["flaky"].health == Health.OK
    finally:
        bus.stop(0.5)


def test_queue_drop_oldest_counts():
    bus = SensorBus(queue_size=3)
    bus.add(SimAdapter("fast", {"x"}, lambda t, r: 1))
    bus.start()
    try:
        assert wait_for(lambda: bus.state["fast"].drops > 0)
        assert len(bus.queues["fast"]) == 3
    finally:
        bus.stop(0.5)


class CrashScore:
    name, inputs, module_flag = "S_thermal", {"thermal_frame"}, None
    def update(self, w):
        raise ZeroDivisionError


class NanScore:
    name, inputs, module_flag = "S_glint", {"nir_pair"}, None
    def update(self, w):
        s = Score("S_glint", 0.5, 0.5); s.value = math.nan
        return s


class WrongType:
    name, inputs, module_flag = "S_rf", {"rf_adv"}, None
    def update(self, w):
        return 0.7


@pytest.mark.parametrize("mod", [CrashScore(), NanScore(), WrongType()])
def test_safe_update_contains_score_failures(mod):
    s = safe_update(mod, [])
    assert s.health == Health.FAILED and s.value == 0.0


def test_engine_survives_everything_and_degrades():
    c = Config()
    e = Engine(c)
    e.bus = fast_bus()
    for a in sim.make("camera_lens", period_s=0.01):
        if a.id == "sim_thermal":
            continue
        e.add_adapter(a)
    e.add_adapter(Crasher())   # thermal family source that always fails
    e.score_modules.append(CrashScore())
    res = asyncio.run(e.run(steps=8, hz=20))
    assert len(res) == 8
    last = res[-1]
    assert "thermal" in last["families_unhealthy"] or "thermal" in last["families_missing"]
    assert last["level"] == "attention"     # optical + rf still agree


def test_fusion_suppressed_when_two_families_unhealthy():
    from asb.fusion.stack import fuse
    r = fuse([Score("S_thermal", 0, 0, Health.FAILED), Score("S_rf", 0, 0, Health.FAILED),
              Score("S_glint", 0.9, 0.9), Score("S_radar", 0.9, 0.9)])
    assert r["suppressed"] and r["level"] is None and r["anomaly_index"] == 0.0


def test_event_handler_crash_does_not_stop_loop():
    e = Engine(Config())
    for a in sim.make("camera_lens"):
        a.open({}); e.add_adapter(a)
    e.on_event = lambda ev: 1 / 0
    from asb.headless import run_sync
    out = run_sync(e, 3)
    assert len(out) == 3 and e.events


def test_model_load_failure_falls_back(tmp_path):
    from asb.fusion.stack import load_weights, FusionModel
    good = FusionModel(version="last-good")
    p = tmp_path / "w.json"
    for content in ["{not json", '{"w":[1,2],"w_mask":[0],"b":0}', '{"w":[1,1,1,1,1,1],"w_mask":[0,0,0,0,0,0],"b":NaN}']:
        p.write_text(content)
        assert load_weights(p, good).version == "last-good"
    assert load_weights(tmp_path / "missing.json").version == "prior-0"
