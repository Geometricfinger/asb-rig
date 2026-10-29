"""A1 lens-glint (IR on/off differencing) and A2 active NIR emitter features."""
from __future__ import annotations
import numpy as np


def _components(mask: np.ndarray, max_blobs: int = 200) -> list[list[tuple[int, int]]]:
    """4-connected components (pure NumPy/Python, small masks only)."""
    seen = np.zeros_like(mask, dtype=bool)
    blobs = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if seen[y0, x0]:
            continue
        stack, pix = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            pix.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        blobs.append(pix)
        if len(blobs) >= max_blobs:
            break
    return blobs


def glint_candidates(frame_on: np.ndarray, frame_off: np.ndarray, thresh: float = 60, max_area: int = 30) -> list[dict]:
    """Retro-reflective lens glints appear in LED-on minus LED-off and are tiny and sharp."""
    diff = frame_on.astype(np.int32) - frame_off.astype(np.int32)
    out = []
    for pix in _components(diff > thresh):
        if len(pix) > max_area:
            continue
        ys, xs = zip(*pix)
        peak = float(max(diff[y, x] for y, x in pix))
        out.append({"y": float(np.mean(ys)), "x": float(np.mean(xs)), "area": len(pix), "peak": peak})
    return out


def glint_score(cands: list[dict]) -> tuple[float, float]:
    if not cands:
        return 0.0, 0.6
    best = max(c["peak"] / 255.0 * (1.0 if c["area"] <= 6 else 0.6) for c in cands)
    return min(1.0, best), min(1.0, 0.5 + 0.1 * len(cands))


# A2 point-emitter limits. An active near-IR emitter (LED, IR ring) images as a small, roughly
# round, saturated spot on a darker surround. Sunlit surfaces, sky and glare saturate too, but as
# large or elongated regions, or regions without a dark rim; those are rejected.
A2_SAT = 250                  # DN: saturated (8-bit)
A2_MIN_AREA_PX = 2            # below this is sensor noise / hot pixel
A2_MAX_AREA_FRAC = 0.0005     # spot area <= 0.05% of the frame (28 px at 320x180, 154 px at 640x480)
A2_MAX_AREA_FLOOR_PX = 4      # never cap below 4 px on tiny frames
A2_MIN_ASPECT = 0.5           # bounding-box short/long side: roughly round, not a streak or edge
A2_MIN_FILL = 0.5             # area / bounding-box area: compact, not a ragged patch
A2_RING_PX = 3                # width of the surround ring checked for darkness
A2_MAX_RING_MEAN = 100        # DN: surround must be clearly darker (>=150 DN below saturation); sky
                              # seen through foliage gives rings of ~120-145 DN on the panda cam
A2_NEIGHBOR_PX = 12           # half-width of the neighbourhood checked for other saturated pixels
A2_MAX_NEIGHBOR_RATIO = 2.0   # saturated px in the neighbourhood <= 2x the spot's own area
A2_MAX_SPOTS = 6              # more candidates than this in one frame = sparkle/foliage texture, not emitters
A2_SPOTS_FOR_FULL = 2         # score = n_spots / 2, capped at 1


def nir_point_spots(frame_off: np.ndarray) -> list[dict]:
    """Small, compact, isolated saturated spots (A2 candidates) in an LED-off frame."""
    f = np.asarray(frame_off)
    h, w = f.shape[:2]
    max_area = max(A2_MAX_AREA_FLOOR_PX, int(A2_MAX_AREA_FRAC * h * w))
    spots = []
    for pix in _components(f >= A2_SAT, max_blobs=500):
        area = len(pix)
        if not A2_MIN_AREA_PX <= area <= max_area:
            continue
        ys, xs = zip(*pix)
        y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
        bh, bw = y1 - y0 + 1, x1 - x0 + 1
        if min(bh, bw) / max(bh, bw) < A2_MIN_ASPECT or area / (bh * bw) < A2_MIN_FILL:
            continue
        ry0, ry1, rx0, rx1 = max(0, y0 - A2_RING_PX), min(h, y1 + A2_RING_PX + 1), max(0, x0 - A2_RING_PX), min(w, x1 + A2_RING_PX + 1)
        box = f[ry0:ry1, rx0:rx1].astype(np.float64)
        inner = np.zeros(box.shape, bool)
        inner[y0 - ry0:y1 - ry0 + 1, x0 - rx0:x1 - rx0 + 1] = True
        ring = box[~inner]
        if ring.size == 0 or ring.mean() > A2_MAX_RING_MEAN:
            continue
        ny0, ny1 = max(0, y0 - A2_NEIGHBOR_PX), min(h, y1 + A2_NEIGHBOR_PX + 1)
        nx0, nx1 = max(0, x0 - A2_NEIGHBOR_PX), min(w, x1 + A2_NEIGHBOR_PX + 1)
        if int((f[ny0:ny1, nx0:nx1] >= A2_SAT).sum()) > A2_MAX_NEIGHBOR_RATIO * area:
            continue
        spots.append({"y": float(np.mean(ys)), "x": float(np.mean(xs)), "area": area, "ring_mean": float(ring.mean())})
    return spots


def nir_emitter_score(frame_off: np.ndarray, sat: int = A2_SAT, min_px: int = A2_MIN_AREA_PX) -> tuple[float, float]:
    """With our LED off, small point-like saturated spots are active-emitter candidates (A2).
    Large saturated regions (sunlit areas, sky, glare) are ignored. `sat`/`min_px` kept for API
    compatibility; the module constants above are authoritative."""
    n = len(nir_point_spots(frame_off))
    if n > A2_MAX_SPOTS:
        return 0.0, 0.3   # texture of many small highlights; not treated as emitters
    return (min(1.0, n / A2_SPOTS_FOR_FULL) if n else 0.0), 0.7
