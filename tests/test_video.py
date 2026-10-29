"""Video adapter: contract, real pipeline on a generated clip, absent sensors marked."""
import numpy as np
import pytest

from asb.adapters.base import SensorAdapter
from asb.adapters.video import VideoAdapter, DriverUnavailable
from asb.bus import default_validator
from asb.headless import run_video
from asb import cli

cv2 = pytest.importorskip("cv2")


@pytest.fixture
def clip(tmp_path):
    p = str(tmp_path / "c.avi")
    w = cv2.VideoWriter(p, cv2.VideoWriter.fourcc(*"MJPG"), 10, (160, 90))
    for i in range(60):
        f = np.full((90, 160, 3), 40, np.uint8)
        f[30:60, (i * 2) % 130:(i * 2) % 130 + 30] = 220     # moving block
        w.write(f)
    w.release()
    return p


def test_contract(clip):
    a = VideoAdapter(clip)
    assert isinstance(a, SensorAdapter)
    a.open({})
    s1, s2 = a.read(1), a.read(1)
    assert default_validator(s1) and s2.seq == s1.seq + 1
    assert s1.data["source"] == "visible_video_no_ir_led" and s1.quality == 0.3
    assert s1.data["on"] is s1.data["off"] and s2.data["jerk"] > 0
    a.close()


def test_bad_source():
    with pytest.raises(DriverUnavailable):
        VideoAdapter("/nonexistent.mp4").open({})
    with pytest.raises(ValueError):
        VideoAdapter().open({})


def test_end_of_stream_degrades(clip):
    a = VideoAdapter(clip, step_s=10)
    a.open({})
    while a.read(1) is not None:
        pass
    assert a.health()[0].value == "degraded"


def test_pipeline_marks_absent_sensors(clip):
    out = run_video(clip, steps=4)
    assert len(out) == 4
    r = out[-1]
    assert set(r["inputs"]["absent_families"]) == {"thermal", "rf", "vital", "eye_liveness", "voice"}
    assert r["inputs"]["simulated"] == []
    mods = {s["module"] for s in r["scores"]}
    assert mods == {"S_glint", "S_nir_emit", "S_motion"} and r["level"] in (None, "fyi")
    assert all("health" in s for s in r["scores"])


def test_cli_video(clip, tmp_path):
    out = tmp_path / "o.json"
    assert cli.main(["--headless", "--video", clip, "--steps", "2", "--out", str(out)]) == 0
