import numpy as np

from asb.features import optical, thermal, eye, vital, rf, baseline
from asb.fusion import stack
from asb.schema import Health, Score


def test_glint_found_only_with_led_difference():
    off = np.zeros((48, 64), np.uint8); on = off.copy(); on[10:12, 10:12] = 240
    c = optical.glint_candidates(on, off)
    assert len(c) == 1 and c[0]["area"] == 4
    assert optical.glint_candidates(off, off) == []
    big = off.copy(); big[0:20, 0:20] = 240           # large reflector, not a lens
    assert optical.glint_candidates(big, off) == []


def test_nir_emitter():
    f = np.zeros((10, 10), np.uint8); f[0, 0:5] = 255
    assert optical.nir_emitter_score(f)[0] > 0
    assert optical.nir_emitter_score(np.zeros((10, 10), np.uint8))[0] == 0


def test_thermal_render_default_and_toggle():
    f = np.linspace(10, 45, 24 * 32).reshape(24, 32)
    g = thermal.render(f)
    assert g["legend"]["palette"] == "grayscale" and (g["rgb"][..., 0] == g["rgb"][..., 1]).all()
    assert g["tag"] == thermal.NOT_MEDICAL
    c = thermal.render(f, "inferno")
    assert not (c["rgb"][..., 0] == c["rgb"][..., 2]).all()
    assert np.array_equal(f, np.linspace(10, 45, 24 * 32).reshape(24, 32))   # raw untouched
    ov = thermal.overlay(np.zeros((24, 32), np.uint8), c["rgb"])
    assert ov.shape == (24, 32, 3)


def test_skin_band():
    assert thermal.skin_range_score(np.full((5, 5), 34.0))[0] == 0
    assert thermal.skin_range_score(np.full((5, 5), 50.0))[0] == 1


def test_pupil_diameter_synthetic():
    img = np.full((100, 100), 200, np.uint8)
    yy, xx = np.mgrid[:100, :100]
    img[(yy - 50) ** 2 + (xx - 50) ** 2 <= 10 ** 2] = 10
    d, q = eye.pupil_diameter_px(img)
    assert abs(d - 20) < 1.5 and q > 0.7


def test_blinks_and_saccades():
    o = np.ones(300); o[50:56] = 0; o[200:209] = 0
    assert len(eye.blinks(o, 60)) == 2
    g = np.zeros((120, 2)); g[60:, 0] = 10
    assert len(eye.saccades(g, 120)) == 1


def test_microsaccades_report_only():
    r = eye.microsaccades_report(np.random.default_rng(0).normal(0, 0.01, (600, 2)), 120)
    assert r["report_only"] and "not resolvable" in r["note"]


def test_glint_code_follow():
    code = np.random.default_rng(1).integers(0, 2, 60)
    assert eye.glint_code_follow(code, code) == 1.0
    assert eye.glint_code_follow(code, np.roll(code, 1)) >= 0.98
    assert eye.glint_code_follow(code, np.zeros(60)) < 0.7


def test_plr():
    d = np.r_[np.full(60, 5.0), np.linspace(5, 4, 30), np.full(90, 4.0)]
    r = eye.pupil_light_response(d, 60, 60)
    assert 0.15 < r["constriction"] < 0.25 and r["latency_s"] is not None


def test_rppg_detects_pulse():
    fps, n = 30, 300
    t = np.arange(n) / fps
    rgb = np.array([150, 110, 90.]) * (1 + np.outer(0.004 * np.sin(2 * np.pi * 1.2 * t), [0.33, 0.77, 0.53]))
    snr, hz = vital.band_snr(vital.pos_pulse(rgb, fps), fps, 0.7, 3.0)
    assert abs(hz - 1.2) < 0.15 and snr > 3
    flat = np.tile([150, 110, 90.], (n, 1)) + np.random.default_rng(0).normal(0, 0.05, (n, 3))
    assert vital.absence_score(vital.band_snr(vital.pos_pulse(flat, fps), fps, 0.7, 3.0)[0]) > 0.3


def test_ap_clock_skew():
    local = np.arange(0, 100, 1.0)
    tsf = (local * (1 + 25e-6) * 1e6).astype(np.int64)
    assert abs(rf.clock_skew_ppm(tsf.tolist(), local.tolist()) - 25) < 1


def test_drift_detector_and_type():
    rng = np.random.default_rng(0)
    w = [{"interval_mean": 0.1 + rng.normal(0, 0.001), "tx_power": -4.0, "payload_len": 20.0} for _ in range(10)]
    d = rf.DriftDetector(rf.build_baseline(w))
    for _ in range(5):
        assert not d.update({"interval_mean": 0.1, "tx_power": -4.0, "payload_len": 20.0})[0]
    changed = {"interval_mean": 0.5, "tx_power": 4.0, "payload_len": 20.0}
    res = [d.update(changed)[0] for _ in range(3)]
    assert res == [False, False, True]
    assert rf.device_type(0x004C) == "phone_or_wearable"
    assert rf.device_type(service_uuids=["0000180d-0000-1000-8000-00805f9b34fb"]) == "fitness_wearable"
    assert rf.device_type(is_ap=True) == "access_point" and rf.device_type() == "unknown"


def test_fingerprint_tracker():
    from asb.modules.fingerprint import FingerprintTracker
    t = FingerprintTracker(baseline_windows=5)
    for _ in range(5):
        t.observe("k1", {"interval_mean": 1.0, "tx_power": 0.0})
    for _ in range(3):
        r = t.observe("k1", {"interval_mean": 2.0, "tx_power": 8.0})
    assert r["state"] == "drift" and t.drifted() == ["k1"] and "tampering" in r["note"]


def test_site_baseline_new_objects():
    b = baseline.SiteBaseline("home", [1])
    bg = np.full((24, 32), 21.0)
    for _ in range(3):
        b.add_pass({"e1", "e2"}, {1: bg}, {1: [(10, 10)]})
    assert baseline.new_emitters(b, {"e1", "e3"}) == {"e3"}
    hot = bg.copy(); hot[5:7, 5:7] = 30
    assert baseline.new_thermal_blobs(b, 1, hot) == 1 and baseline.new_thermal_blobs(b, 1, bg) == 0
    assert baseline.new_glints(b, 1, [(11, 11), (40, 40)]) == [(40, 40)]


def S(m, v, c=0.9, h=Health.OK):
    return Score(m, v, c, h)


def test_single_family_is_fyi_two_is_attention():
    assert stack.fuse([S("S_glint", 0.9), S("S_nir_emit", 0.9)])["level"] == "fyi"
    assert stack.fuse([S("S_glint", 0.9), S("S_rf", 0.9)])["level"] == "attention"
    assert stack.fuse([S("S_glint", 0.1)])["level"] is None


def test_no_class_fields_in_fusion_output():
    from asb.guard.vocabulary import check_output
    check_output(stack.fuse([S("S_glint", 0.9), S("S_rf", 0.9)]))


def test_missing_family_mask_and_training():
    rng = np.random.default_rng(0)
    n = 400
    y = rng.integers(0, 2, n)
    X = np.clip(rng.normal(0.3 + 0.4 * y[:, None], 0.15, (n, 6)), 0, 1)
    M = (rng.random((n, 6)) < 0.2).astype(float)
    m = stack.train(X, M, y.astype(float))
    p = np.array([m.predict(x, mm) for x, mm in zip(X, M)])
    assert stack.auc(y, p) > 0.85
    again = stack.FusionModel.from_json(m.to_json())
    assert np.allclose(again.w, m.w)


def test_auc_edge():
    assert np.isnan(stack.auc(np.array([1, 1]), np.array([0.2, 0.3])))
    assert stack.auc(np.array([0, 1]), np.array([0.1, 0.9])) == 1.0


def test_liveness_indicators():
    from asb.modules.liveness import indicators
    r = indicators([S("S_live", 0.9), S("S_eye", 0.8), S("S_voice", 0.1)])
    assert r["a11"] and set(r["families_absent"]) == {"vital", "eye"}
    assert "silicone mask" in r["limit"]
    assert not indicators([S("S_live", 0.9)])["a11"]
