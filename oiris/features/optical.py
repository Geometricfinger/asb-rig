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


def nir_emitter_score(frame_off: np.ndarray, sat: int = 250, min_px: int = 2) -> tuple[float, float]:
    """With our LED off, saturated near-IR spots are active emitters."""
    n = int((frame_off >= sat).sum())
    return (min(1.0, n / 20.0) if n >= min_px else 0.0), 0.7
