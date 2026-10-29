"""M-01 eye-behaviour features (HYPOTHESIS module; ships disabled until E-11/E-14 pass).
Pupil diameter, blinks, saccades, corneal-glint challenge-response. Micro-saccades are
report-only: <=143 fps cameras at distance cannot resolve them (spec M-01)."""
from __future__ import annotations
import numpy as np


def pupil_diameter_px(eye_roi: np.ndarray, dark_thresh: int | None = None) -> tuple[float, float]:
    """Dark-pupil estimate: equivalent-circle diameter of the darkest blob. Returns (px, quality)."""
    if eye_roi.size == 0:
        return 0.0, 0.0
    lo, med = float(eye_roi.min()), float(np.median(eye_roi))
    t = dark_thresh if dark_thresh is not None else lo + 0.3 * (med - lo)
    mask = eye_roi <= t
    area = int(mask.sum())
    if area < 4:
        return 0.0, 0.0
    ys, xs = np.nonzero(mask)
    h, w = int(np.ptp(ys)) + 1, int(np.ptp(xs)) + 1
    roundness = min(h, w) / max(h, w)
    fill = area / (h * w)
    return float(2 * np.sqrt(area / np.pi)), float(np.clip(roundness * min(1.0, fill / 0.7), 0, 1))


def blinks(openness: np.ndarray, fps: float, closed: float = 0.2, min_ms: float = 50, max_ms: float = 500) -> list[tuple[int, int]]:
    c = openness < closed
    out, start = [], None
    for i, v in enumerate(c):
        if v and start is None:
            start = i
        elif not v and start is not None:
            dur = (i - start) / fps * 1000
            if min_ms <= dur <= max_ms:
                out.append((start, i))
            start = None
    return out


def saccades(gaze_deg: np.ndarray, fps: float, vel_thresh: float = 30.0) -> list[tuple[int, int]]:
    """Velocity-threshold saccade detection on (N,2) gaze angles."""
    v = np.linalg.norm(np.diff(gaze_deg, axis=0), axis=1) * fps
    out, start = [], None
    for i, fast in enumerate(v > vel_thresh):
        if fast and start is None:
            start = i
        elif not fast and start is not None:
            out.append((start, i)); start = None
    return out


def microsaccades_report(gaze_deg: np.ndarray, fps: float, lam: float = 6.0) -> dict:
    """Engbert-Kliegl style estimator, REPORT ONLY. Never feeds fusion."""
    if fps < 250:
        note = f"{fps:.0f} fps < 250 fps: micro-saccades not resolvable; counts are noise"
    else:
        note = "sampling adequate"
    v = np.gradient(gaze_deg, axis=0) * fps
    med = np.median(v, axis=0)
    sd = np.sqrt(np.median((v - med) ** 2, axis=0)) + 1e-9
    r = ((v / (lam * sd)) ** 2).sum(axis=1) > 1
    return {"candidates": int(np.sum(np.diff(r.astype(int)) == 1)), "note": note, "report_only": True}


def glint_code_follow(led_code: np.ndarray, glint_present: np.ndarray) -> float:
    """Fraction of frames where corneal glints follow the random LED on/off code.
    A live cornea follows within one frame; a replayed screen cannot know the code."""
    n = min(len(led_code), len(glint_present))
    if n == 0:
        return 0.0
    a, b = led_code[:n].astype(bool), glint_present[:n].astype(bool)
    same = (a == b).mean()
    lag1 = (a[:-1] == b[1:]).mean() if n > 1 else 0.0
    return float(max(same, lag1))


def pupil_light_response(diam: np.ndarray, step_idx: int, fps: float) -> dict:
    """Lab-only PLR (default OFF, D-15): constriction fraction and latency."""
    base = float(np.median(diam[max(0, step_idx - int(fps)):step_idx])) or 1.0
    post = diam[step_idx: step_idx + int(2 * fps)]
    if post.size == 0:
        return {"constriction": 0.0, "latency_s": None}
    mn = float(post.min())
    thr = base - 0.1 * (base - mn) if base > mn else base
    lat = next((i / fps for i, d in enumerate(post) if d < thr), None)
    return {"constriction": max(0.0, (base - mn) / base), "latency_s": lat}


def eye_score(glint_follow: float, blink_rate_per_min: float | None, pupil_quality: float) -> tuple[float, float]:
    """Higher = expected eye dynamics less observed. Confidence driven by measurement quality."""
    parts = [1.0 - glint_follow]
    if blink_rate_per_min is not None:
        parts.append(1.0 if blink_rate_per_min < 2 else 0.0)
    return float(np.mean(parts)), float(np.clip(pupil_quality, 0, 1))
