"""Fault injection: crashing, hanging, garbage-emitting, failing-to-open adapters and
crashing/NaN score modules must never take down the process; fusion degrades."""
import asyncio, math, threading, time
import pytest

from oiris.adapters import sim
from oiris.adapters.base import AdapterBase, SimAdapter
from oiris.bus import SensorBus
from oiris.config import Config
from oiris.engine import Engine
from oiris.schema import Health, Score
from oiris.scores.base import safe_update


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
    from oiris.fusion.stack import fuse
    r = fuse([Score("S_thermal", 0, 0, Health.FAILED), Score("S_rf", 0, 0, Health.FAILED),
              Score("S_glint", 0.9, 0.9), Score("S_radar", 0.9, 0.9)])
    assert r["suppressed"] and r["level"] is None and r["anomaly_index"] == 0.0


def test_event_handler_crash_does_not_stop_loop():
    e = Engine(Config())
    for a in sim.make("camera_lens"):
        a.open({}); e.add_adapter(a)
    e.on_event = lambda ev: 1 / 0
    from oiris.headless import run_sync
    out = run_sync(e, 3)
    assert len(out) == 3 and e.events


def test_model_load_failure_falls_back(tmp_path):
    from oiris.fusion.stack import load_weights, FusionModel
    good = FusionModel(version="last-good")
    p = tmp_path / "w.json"
    for content in ["{not json", '{"w":[1,2],"w_mask":[0],"b":0}', '{"w":[1,1,1,1,1,1],"w_mask":[0,0,0,0,0,0],"b":NaN}']:
        p.write_text(content)
        assert load_weights(p, good).version == "last-good"
    assert load_weights(tmp_path / "missing.json").version == "prior-0"


# ---- M-16 face backend fault injection (ADR-0048, face-matching spec section 15) ----------
class _FaceBad:
    name, license, model_id, model_version, test_only = "bad", "Apache-2.0", "bad", "1", True
    def __init__(self, mode): self.mode = mode
    def open(self, cfg): pass
    def close(self): pass
    def health(self): return (Health.OK, "")
    def detect(self, frame, timeout_s):
        if self.mode == "raise": raise RuntimeError("detector exploded")
        if self.mode == "exit": raise SystemExit("plugin called exit()")
        if self.mode == "hang": time.sleep(30)
        if self.mode == "garbage": return [{"x": "nope"}]
        return []
    def embed(self, frame, box): raise AssertionError("never reached")
    def compare(self, e, t): return None


@pytest.mark.parametrize("mode", ["raise", "exit", "hang", "garbage"])
def test_face_backend_faults_isolated(tmp_path, mode):
    from oiris.modules.face_match import optin
    from oiris.modules.face_match.backends.test_deterministic import synth_face_frame
    from oiris.modules.face_match.core import FaceMatchConfig, FaceMatchModule
    from oiris.security.keys import KeyStore
    from oiris.store.db import DB
    ks = KeyStore(tmp_path / "k.json"); ks.create("pw")
    db = DB(tmp_path / "a.db", ks.subkey("db"))
    optin.record_opt_in(db, None, "I UNDERSTAND", ["personal", "research"], "d", warning_shown=optin.WARNING_TEXT)
    m = FaceMatchModule(db, ks, tmp_path, _FaceBad(mode), None, FaceMatchConfig(modes=["personal", "research"], allow_test_backend=True),
                        timeout_s=0.2, breaker_threshold=3, breaker_cooldown_s=60)
    e = Engine(Config(), face_match=m, face_place="P")
    for a in sim.make("quiet"):
        e.add_adapter(a)

    class Cam(AdapterBase):
        id, caps = "cam", {"face_frame"}
        def read(self, t):
            time.sleep(0.01); return self._sample(synth_face_frame(1))
    e.add_adapter(Cam())
    e.bus.start()
    try:
        results = []
        for _ in range(3):
            time.sleep(0.15); results.append(e.step())
    finally:
        e.bus.stop()
    assert len(results) == 3 and all("anomaly_index" in r for r in results)          # fusion unaffected
    assert m.guard.health == Health.FAILED and m.guard.breaker_open_until > 0         # breaker open
    calls = m.guard.calls
    r = m.process_frame(synth_face_frame(1), place="P")
    assert r["health"] == "failed" and m.guard.calls == calls                          # no calls while open
    assert e.bus.health()["cam"]["health"] == "ok"                                     # the camera adapter is fine
    db.close()
