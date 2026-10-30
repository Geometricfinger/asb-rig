"""Regression tests for the Forge static-review findings (F1..F5)."""
from __future__ import annotations
import logging, math, threading, time

import numpy as np
import pytest

from oiris.bus import SensorBus
from oiris.config import Config
from oiris.engine import Engine
from oiris.fusion.stack import FusionModel, load_weights
from oiris.guard.privacy import PrivacyError, check_persist
from oiris.schema import Health, Sample, Score


# ---- F1: stale cached readings ------------------------------------------------------------
class _Adapter:
    id, caps, bus = "probe", ("probe_cap",), "test"

    def health(self):
        return Health.OK, ""


class _Mod:
    name, inputs, module_flag = "S_thermal", {"probe_cap"}, None

    def __init__(self):
        self.windows = []

    def update(self, window):
        self.windows.append(list(window))
        return Score(self.name, 1.0 if window else 0.0, 1.0 if window else 0.0)


def _engine(now_ns, monkeypatch):
    monkeypatch.setattr("oiris.engine.time.monotonic_ns", lambda: now_ns[0])
    c = Config(); c.sensor_max_age_s = 5.0
    mod = _Mod()
    e = Engine(c, score_modules=[mod])
    e.add_adapter(_Adapter())
    return e, mod


def _sample(t_ns):
    return Sample("probe", t_ns, time.time(), 0, "u", 1.0, {"v": 1})


def test_f1_stale_cached_reading_not_reused_for_scoring(monkeypatch):
    now = [10_000_000_000]
    e, mod = _engine(now, monkeypatch)
    e.bus.queues["probe"].append(_sample(now[0]))
    e.step()
    assert len(mod.windows[-1]) == 1
    now[0] += 6_000_000_000            # 6 s later, no new sample: cached reading is past max age
    res = e.step()
    assert mod.windows[-1] == [], "stale reading was reused for scoring"
    s = next(x for x in res["scores"] if x["module"] == "S_thermal")
    assert s["value"] == 0.0
    assert res["health"]["probe"]["health"] == Health.DEGRADED.value
    assert "stale" in res["health"]["probe"]["reason"]


def test_f1_fresh_cached_reading_still_reused_within_max_age(monkeypatch):
    now = [10_000_000_000]
    e, mod = _engine(now, monkeypatch)
    e.bus.queues["probe"].append(_sample(now[0]))
    e.step()
    now[0] += 1_000_000_000
    res = e.step()
    assert len(mod.windows[-1]) == 1
    assert res["health"]["probe"]["health"] == Health.OK.value


def test_f1_max_age_config_validated():
    c = Config(); c.sensor_max_age_s = 0
    with pytest.raises(ValueError):
        c.validate()
    assert Config().sensor_max_age_s > 0


# ---- F2: hung reads must not accumulate threads -------------------------------------------
class _Hung:
    id, caps, bus = "hung", ("x",), "test"

    def __init__(self):
        self.release = threading.Event()
        self.reads = 0

    def open(self, cfg): pass
    def start(self): pass
    def stop(self): pass
    def close(self): pass
    def health(self): return Health.OK, ""

    def read(self, timeout):
        self.reads += 1
        self.release.wait()
        return None


def _read_threads():
    return [t for t in threading.enumerate() if t.name == "read-hung" and t.is_alive()]


def test_f2_hung_read_caps_in_flight_threads_and_marks_hung():
    a = _Hung()
    bus = SensorBus(timeout_s=0.05, backoff_max_s=0.01, backoff_base_s=0.001, breaker_threshold=1000)
    bus.add(a)
    bus.start()
    try:
        time.sleep(1.0)
        assert len(_read_threads()) <= 1, f"{len(_read_threads())} read threads accumulated"
        assert a.reads == 1
        h = bus.health()["hung"]
        assert h["health"] in (Health.DEGRADED.value, Health.FAILED.value)
        assert "hung" in h["reason"]
    finally:
        a.release.set(); bus.stop()
    deadline = time.time() + 2
    while _read_threads() and time.time() < deadline:
        time.sleep(0.02)
    assert not _read_threads()


def test_f2_hung_adapter_disabled_after_limit_and_recovers_when_read_returns():
    a = _Hung()
    bus = SensorBus(timeout_s=0.05, backoff_max_s=0.01, backoff_base_s=0.001, breaker_threshold=1000,
                    hung_disable_s=0.3)
    bus.add(a)
    bus.start()
    try:
        time.sleep(0.8)
        h = bus.health()["hung"]
        assert h["health"] == Health.FAILED.value and "disabled" in h["reason"]
        a.release.set()                 # driver finally returns: the slot frees, restart path resumes
        time.sleep(0.5)
        assert len(_read_threads()) <= 1
    finally:
        a.release.set(); bus.stop()


# ---- F4: crop dimension check ---------------------------------------------------------------
@pytest.mark.parametrize("shape", [(32, 1024), (64, 65), (1024, 8), (65, 64, 3)])
def test_f4_oversize_frame_refused_per_dimension(shape):
    with pytest.raises(PrivacyError):
        check_persist("rgb_frame", True, np.zeros(shape, np.uint8))


@pytest.mark.parametrize("shape", [(64, 64), (32, 32, 3), (1, 64)])
def test_f4_crop_within_limit_allowed(shape):
    check_persist("rgb_frame", True, np.zeros(shape, np.uint8))


def test_f4_shapeless_or_1d_payload_refused():
    with pytest.raises(PrivacyError):
        check_persist("rgb_frame", True, object())
    with pytest.raises(PrivacyError):
        check_persist("rgb_frame", True, np.zeros(4096, np.uint8))


# ---- F5: non-finite fusion weights ----------------------------------------------------------
@pytest.mark.parametrize("bad", [
    {"w": [1, 1, 1, 1, 1, 1], "w_mask": [0, float("nan"), 0, 0, 0, 0], "b": -2.5},
    {"w": [1, 1, 1, 1, 1, 1], "w_mask": [0, 0, float("inf"), 0, 0, 0], "b": -2.5},
    {"w": [1, 1, float("-inf"), 1, 1, 1], "w_mask": [0] * 6, "b": -2.5},
    {"w": [1] * 6, "w_mask": [0] * 6, "b": float("nan")},
])
def test_f5_from_json_rejects_non_finite(bad):
    import json
    with pytest.raises(ValueError):
        FusionModel.from_json(json.dumps(bad))


def test_f5_load_weights_falls_back_to_default_with_warning(tmp_path, caplog):
    p = tmp_path / "w.json"
    p.write_text('{"w":[1,1,1,1,1,1],"w_mask":[0,NaN,0,0,0,0],"b":-2.5,"version":"bad"}')
    with caplog.at_level(logging.WARNING):
        m = load_weights(p)
    assert m.version == FusionModel().version
    assert np.all(np.isfinite(m.w_mask)) and math.isfinite(m.predict(np.ones(6), np.ones(6)))
    assert any("fusion weights" in r.getMessage() for r in caplog.records)
