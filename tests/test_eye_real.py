"""M-01 on REAL eye signals: Tobii Pro Glasses 2 recordings (100 Hz) from the LaborTrack dataset
(CC BY 4.0 raw / MIT preprocessed; participants consented), fetched and sha256-checked by
scripts/fetch_eye_reference_data.py (CI does this; locally the test skips if not fetched).

What this does and does not show: it runs eye.blinks() on real tracker signals (eye-lost =
closed) and scores it against the tracker's own blink events. It does NOT test the O Iris eye
camera / ROI pipeline on real video: no licensed real eye video exists in the project yet.
Thresholds below are the measured agreement on these two recordings, with a small margin,
recorded so a regression is caught; they are not a claim about any other camera."""
import csv, os
from pathlib import Path

import pytest

from oiris.features import eye_recordings as R

DATA = Path(__file__).resolve().parents[1] / "training-library/external/labortrack"
SUBJECTS = ["3ShqB", "VVCFR"]
# measured 2026-10-29 (precision, recall on reference blinks 50-500 ms): 3ShqB 0.63/0.86, VVCFR 0.62/0.83
MIN_RECALL, MIN_PRECISION = 0.80, 0.55


def _have() -> bool:
    return all((DATA / k / "session_1" / f"{s}.csv").exists() for s in SUBJECTS for k in ("pupil", "blinks"))


pytestmark = pytest.mark.skipif(not _have() and os.environ.get("OIRIS_REQUIRE_REAL_EYE") != "1",
                                reason="real eye recordings not fetched (scripts/fetch_eye_reference_data.py)")


@pytest.mark.parametrize("subject", SUBJECTS)
def test_blinks_agree_with_tracker_events_on_real_recordings(subject):
    pupil = DATA / "pupil/session_1" / f"{subject}.csv"
    rec = R.load_tobii_labortrack(pupil)
    t0 = float(next(csv.DictReader(open(pupil, encoding="utf-8")))["timestamp"])
    ref = [b for b in R.load_reference_blinks(DATA / "blinks/session_1" / f"{subject}.csv", t0) if 50 <= b[1] - b[0] <= 500]
    det = R.detected_blinks_ms(rec)
    a = R.agreement(det, ref)
    s = R.summary(rec, det)
    print(subject, a, s)
    assert 95 <= s["fps"] <= 105 and s["minutes"] > 5
    assert len(ref) > 100 and a["recall"] >= MIN_RECALL and a["precision"] >= MIN_PRECISION
    assert 2 <= s["pupil_median"] <= 8            # mm, physiological range
    assert 5 <= s["blink_rate_per_min"] <= 60


def test_generic_recording_loader(tmp_path):
    p = tmp_path / "r.csv"
    rows = ["t_ms,openness,pupil"] + [f"{i * 10},{0.0 if 100 <= i < 112 else 1.0},4.0" for i in range(300)]
    p.write_text("\n".join(rows))
    rec = R.load_generic(p)
    assert rec.fps == 100 and R.detected_blinks_ms(rec) == [(1000.0, 1120.0)]
