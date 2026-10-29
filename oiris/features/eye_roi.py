"""M-01 eye ROI finding on live NIR frames (replaces the pre-extracted-features stub).

Two paths, both commercial-OK and dependency-free at import time:
  * landmarks: when a face detector already ran (e.g. YuNet, MIT, 5-point landmarks where
    points 0/1 are the eyes), crop a box around each eye scaled by inter-ocular distance;
  * dark-pupil + glint (numpy only): under 850 nm illumination the pupil is the darkest
    compact round blob and, on LED-on frames, carries a tiny bright corneal reflection.
The output feeds the existing M-01 features (pupil_diameter_px, glint_code_follow, blinks).
Eye ROIs are transient: never stored, never matched, never an identity (ADR-0013)."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass

import numpy as np

from .eye import blinks, pupil_diameter_px


@dataclass
class EyeRoi:
    x: int
    y: int
    w: int
    h: int
    score: float

    def crop(self, img: np.ndarray) -> np.ndarray:
        return img[self.y:self.y + self.h, self.x:self.x + self.w]


def rois_from_landmarks(shape: tuple, landmarks, scale: float = 0.45) -> list[EyeRoi]:
    """Boxes around landmark points 0 and 1 (YuNet order), side = scale * inter-ocular distance * 2."""
    pts = np.asarray(landmarks, float).reshape(-1, 2)
    if len(pts) < 2:
        return []
    iod = float(np.linalg.norm(pts[0] - pts[1]))
    half = max(4, int(round(scale * iod)))
    out = []
    for cx, cy in pts[:2]:
        x0, y0 = max(0, int(cx) - half), max(0, int(cy) - half)
        x1, y1 = min(shape[1], int(cx) + half), min(shape[0], int(cy) + half)
        if x1 > x0 and y1 > y0:
            out.append(EyeRoi(x0, y0, x1 - x0, y1 - y0, 1.0))
    return out


def _components(mask: np.ndarray) -> list[np.ndarray]:
    """4-connected components as arrays of (y, x). Iterative; fine for downsampled frames."""
    seen = np.zeros_like(mask, bool)
    comps = []
    H, W = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, pix = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop(); pix.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        comps.append(np.array(pix))
    return comps


def find_eye_rois(frame_off: np.ndarray, frame_on: np.ndarray | None = None, landmarks=None, max_eyes: int = 2,
                  min_d: int = 4, max_d: int = 60, step: int = 2) -> list[EyeRoi]:
    """Locate up to `max_eyes` eye regions in a grayscale frame (LED-off; optional LED-on for glints)."""
    g = np.asarray(frame_off, float)
    if g.ndim == 3:
        g = g.mean(axis=2)
    if landmarks is not None:
        return rois_from_landmarks(g.shape, landmarks)[:max_eyes]
    s = g[::step, ::step]
    if s.size == 0:
        return []
    t = np.percentile(s, 2) + 0.25 * (np.median(s) - np.percentile(s, 2))
    diff = None
    if frame_on is not None:
        on = np.asarray(frame_on, float)
        diff = (on.mean(axis=2) if on.ndim == 3 else on) - g
    cands = []
    for c in _components(s <= t):
        ys, xs = c[:, 0], c[:, 1]
        h, w = (int(np.ptp(ys)) + 1) * step, (int(np.ptp(xs)) + 1) * step
        d = max(h, w)
        if not (min_d <= d <= max_d):
            continue
        roundness = min(h, w) / max(h, w)
        fill = len(c) * step * step / (h * w)
        if roundness < 0.6 or fill < 0.5:
            continue
        cy, cx = int(ys.mean()) * step, int(xs.mean()) * step
        r = d  # surround ring: iris/sclera must be brighter than the pupil
        y0, y1, x0, x1 = max(0, cy - r), min(g.shape[0], cy + r), max(0, cx - r), min(g.shape[1], cx + r)
        ring = g[y0:y1, x0:x1]
        contrast = (float(np.median(ring)) - float(g[cy, cx])) / 255.0
        score = float(np.clip(contrast, 0, 1)) * roundness
        if diff is not None:
            patch = diff[max(0, cy - d):cy + d, max(0, cx - d):cx + d]
            if patch.size and patch.max() > 60:
                score += 0.5   # a corneal glint that follows the LED
        cands.append(EyeRoi(x0, y0, x1 - x0, y1 - y0, score))
    cands.sort(key=lambda e: -e.score)
    out: list[EyeRoi] = []
    for e in cands:   # non-overlapping
        if all(abs((e.x + e.w / 2) - (o.x + o.w / 2)) > (e.w + o.w) / 4 or abs((e.y + e.h / 2) - (o.y + o.h / 2)) > (e.h + o.h) / 4 for o in out):
            out.append(e)
        if len(out) == max_eyes:
            break
    return out


def glint_in_roi(roi: EyeRoi, frame_on: np.ndarray, frame_off: np.ndarray, thresh: float = 60) -> bool:
    d = roi.crop(np.asarray(frame_on, float)) - roi.crop(np.asarray(frame_off, float))
    return bool(d.size and d.max() > thresh)


class EyeTracker:
    """Rolling live-frame state -> the `eye` sample consumed by S_eye (led_code, glint_present, blink_rate, pupil_q)."""

    def __init__(self, fps: float, window: int = 30):
        self.fps = fps
        self.code: deque = deque(maxlen=window)
        self.glint: deque = deque(maxlen=window)
        self.open: deque = deque(maxlen=int(fps * 60))
        self.pupil_q: deque = deque(maxlen=window)
        self._ref_area: float | None = None

    def update(self, led_bit: int, frame_on: np.ndarray, frame_off: np.ndarray) -> dict | None:
        rois = find_eye_rois(frame_off, frame_on if led_bit else None)
        self.code.append(int(led_bit))
        if not rois:
            self.glint.append(0); self.open.append(0.0); self.pupil_q.append(0.0)
        else:
            r = rois[0]
            self.glint.append(int(bool(led_bit) and glint_in_roi(r, frame_on, frame_off)))
            px, q = pupil_diameter_px(r.crop(np.asarray(frame_off, float)))
            area = px * px
            self._ref_area = area if self._ref_area is None else max(self._ref_area * 0.99, area)
            self.open.append(float(np.clip(area / (self._ref_area or 1), 0, 1)))
            self.pupil_q.append(q)
        if len(self.code) < self.code.maxlen:  # type: ignore[operator]
            return None
        mins = len(self.open) / self.fps / 60
        rate = len(blinks(np.array(self.open), self.fps)) / mins if mins > 0 else None
        return {"led_code": list(self.code), "glint_present": list(self.glint), "blink_rate": rate,
                "pupil_q": float(np.mean(self.pupil_q))}
