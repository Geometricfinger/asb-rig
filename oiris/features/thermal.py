"""A3 thermal features and M-08 rendering (grayscale default, colour overlay toggle).
Rendering never changes stored data; raw arrays are always what is saved."""
from __future__ import annotations
import numpy as np

NOT_MEDICAL = "Not a medical measurement"


def roi_stats(frame_c: np.ndarray, ambient_c: float | None = None) -> dict:
    amb = float(np.median(frame_c)) if ambient_c is None else ambient_c
    hot = frame_c > amb + 5
    return {"max": float(frame_c.max()), "p95": float(np.percentile(frame_c, 95)), "ambient": amb,
            "hot_px": int(hot.sum())}


def skin_range_score(roi_c: np.ndarray, lo: float = 30.0, hi: float = 37.5) -> tuple[float, float]:
    """Fraction of the hottest region NOT in a typical exposed-skin band. Many benign causes."""
    if roi_c.size == 0:
        return 0.0, 0.0
    top = np.sort(roi_c.ravel())[-max(1, roi_c.size // 10):]
    inband = float(((top >= lo) & (top <= hi)).mean())
    return 1.0 - inband, 0.5


PALETTES = {
    # 5-stop approximations of matplotlib's inferno/viridis (CC0/BSD-licensed colormaps)
    "inferno": [(0, 0, 4), (87, 16, 110), (188, 55, 84), (249, 142, 9), (252, 255, 164)],
    "viridis": [(68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98), (253, 231, 37)],
}


def render(frame_c: np.ndarray, palette: str = "grayscale", range_c=(10.0, 45.0), auto_range: bool = False) -> dict:
    lo, hi = (float(frame_c.min()), float(frame_c.max()) or 1.0) if auto_range else range_c
    if hi <= lo:
        hi = lo + 1.0
    norm = np.clip((frame_c - lo) / (hi - lo), 0, 1)
    g = (norm * 255).astype(np.uint8)
    if palette == "grayscale":
        img = np.stack([g, g, g], -1)
    else:
        stops = np.array(PALETTES[palette], dtype=np.float64)
        pos = norm * (len(stops) - 1)
        i = np.clip(pos.astype(int), 0, len(stops) - 2)
        f = (pos - i)[..., None]
        img = ((1 - f) * stops[i] + f * stops[i + 1]).astype(np.uint8)
    return {"rgb": img, "legend": {"min_c": lo, "max_c": hi, "palette": palette}, "tag": NOT_MEDICAL}


def overlay(nir_gray: np.ndarray, thermal_rgb: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    base = np.stack([nir_gray] * 3, -1).astype(np.float64)
    return (base * (1 - alpha) + thermal_rgb.astype(np.float64) * alpha).astype(np.uint8)
