"""Per-shot quality checks for enrollment (spec 7.3 step 4). Backend-agnostic: run on the
grayscale face crop. Each failure carries a plain-language reason."""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from .port import Angle, FaceBox

REASONS = {
    "faces_none": "no face found, please face the camera",
    "faces_many": "only one face in frame, please",
    "size": "move closer",
    "dark": "too dark",
    "bright": "too bright",
    "blur": "too blurry, hold still",
    "angle": "turn your head to the requested angle",
}


@dataclass
class QualityLimits:
    min_face_px: int = 48
    min_mean: float = 40.0
    max_mean: float = 225.0
    min_sharpness: float = 25.0      # variance of the Laplacian; per-backend calibrated


def to_gray(frame) -> np.ndarray:
    a = np.asarray(frame)
    if a.ndim == 3:
        a = a[..., :3].astype(np.float32) @ np.array([0.114, 0.587, 0.299], dtype=np.float32)  # BGR
    return a.astype(np.float32)


def crop(gray: np.ndarray, b: FaceBox) -> np.ndarray:
    h, w = gray.shape[:2]
    x0, y0 = max(0, b.x), max(0, b.y)
    return gray[y0:min(h, b.y + b.h), x0:min(w, b.x + b.w)]


def sharpness(g: np.ndarray) -> float:
    if g.shape[0] < 3 or g.shape[1] < 3:
        return 0.0
    lap = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1])
    lim = float(np.percentile(np.abs(lap), 99))   # one specular highlight must not count as "sharp"
    return float(np.clip(lap, -lim, lim).var())


def check_shot(frame, boxes: list[FaceBox], want: Angle, lim: QualityLimits) -> tuple[bool, str, str]:
    """Returns (ok, code, plain reason). Order: face count, size, light, blur, angle."""
    if not boxes:
        return False, "faces_none", REASONS["faces_none"]
    if len(boxes) > 1:
        return False, "faces_many", REASONS["faces_many"]
    b = boxes[0]
    if min(b.w, b.h) < lim.min_face_px:
        return False, "size", REASONS["size"]
    c = crop(to_gray(frame), b)
    if c.size == 0:
        return False, "size", REASONS["size"]
    m = float(c.mean())
    if m < lim.min_mean:
        return False, "dark", REASONS["dark"]
    if m > lim.max_mean:
        return False, "bright", REASONS["bright"]
    if sharpness(c) < lim.min_sharpness:
        return False, "blur", REASONS["blur"]
    if b.pose != want:   # a backend that cannot estimate pose cannot pass the angle check
        return False, "angle", REASONS["angle"]
    return True, "ok", "ok"
