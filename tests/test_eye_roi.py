"""Eye ROI on live frames: synthetic NIR images (dark pupil, glint only on LED-on frames)."""
import numpy as np

from oiris.features.eye_roi import EyeTracker, find_eye_rois, glint_in_roi, rois_from_landmarks


def frame(eyes=((100, 120), (100, 200)), r=8, glint=False, closed=False, seed=0):
    g = np.random.default_rng(seed).normal(150, 3, (240, 320))
    yy, xx = np.mgrid[:240, :320]
    for cy, cx in eyes:
        g[(yy - cy) ** 2 + (xx - cx) ** 2 <= (2.5 * r) ** 2] = 110   # iris
        if not closed:
            g[(yy - cy) ** 2 + (xx - cx) ** 2 <= r * r] = 20          # pupil
            if glint:
                g[cy - 1:cy + 2, cx + 2:cx + 5] = 255
    return np.clip(g, 0, 255)


def test_finds_both_pupils():
    rois = find_eye_rois(frame())
    assert len(rois) == 2
    centres = sorted((e.y + e.h // 2, e.x + e.w // 2) for e in rois)
    for (cy, cx), (ey, ex) in zip(centres, [(100, 120), (100, 200)]):
        assert abs(cy - ey) <= 4 and abs(cx - ex) <= 4


def test_no_eyes_in_flat_frame():
    assert find_eye_rois(np.full((120, 160), 128.0)) == []


def test_glint_detected_only_on_led_frame():
    off, on = frame(), frame(glint=True)
    roi = find_eye_rois(off, on)[0]
    assert glint_in_roi(roi, on, off) and not glint_in_roi(roi, off, off)


def test_landmark_path():
    r = rois_from_landmarks((240, 320), [[120, 100], [200, 100], [160, 140], [130, 180], [190, 180]])
    assert len(r) == 2 and r[0].w == r[0].h == 72


def test_tracker_produces_eye_sample_that_follows_code_for_live_eye_and_not_for_screen():
    rng = np.random.default_rng(1)
    t_live, t_screen = EyeTracker(fps=30), EyeTracker(fps=30)
    out_live = out_screen = None
    for i in range(30):
        bit = int(rng.integers(2))
        off = frame(seed=i)
        out_live = t_live.update(bit, frame(glint=True, seed=i) if bit else off, off)
        out_screen = t_screen.update(bit, off, off)    # a display shows no corneal reflection
    from oiris.features.eye import glint_code_follow
    assert glint_code_follow(np.array(out_live["led_code"]), np.array(out_live["glint_present"])) > 0.9
    assert glint_code_follow(np.array(out_screen["led_code"]), np.array(out_screen["glint_present"])) < 0.6
    assert out_live["pupil_q"] > 0.5


def test_nir_eye_adapter_emits_eye_sample_with_injected_frames():
    from oiris.adapters.drivers import NirEyeAdapter
    a = NirEyeAdapter()
    a.open({"grab": lambda bit: ((frame(glint=True) if bit else frame()), frame()), "window": 30})
    out = None
    for _ in range(30):
        out = a.read(1.0)
    assert out is not None and set(out.data) >= {"led_code", "glint_present", "blink_rate", "pupil_q"}
    assert "eye" in a.caps
    a.close()
