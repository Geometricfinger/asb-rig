"""M-07 per-location baselines and new-object-at-known-location (A10)."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np


@dataclass
class SiteBaseline:
    site_code: str
    anchors: list[int] = field(default_factory=list)
    emitters: set = field(default_factory=set)       # HMAC'd emitter keys seen in all baseline passes
    thermal_bg: dict = field(default_factory=dict)  # anchor -> median frame
    glints: dict = field(default_factory=dict)      # anchor -> list of (x,y)
    passes: int = 0

    def add_pass(self, emitters: set, thermal: dict, glints: dict) -> None:
        self.emitters = set(emitters) if self.passes == 0 else self.emitters | set(emitters)
        for a, f in thermal.items():
            prev = self.thermal_bg.get(a)
            self.thermal_bg[a] = f if prev is None else np.median(np.stack([prev, f]), axis=0)
        for a, g in glints.items():
            self.glints.setdefault(a, []).extend(g)
        self.passes += 1


def new_emitters(base: SiteBaseline, seen: set) -> set:
    return set(seen) - base.emitters


def new_thermal_blobs(base: SiteBaseline, anchor: int, frame: np.ndarray, delta_c: float = 5.0, min_px: int = 4) -> int:
    bg = base.thermal_bg.get(anchor)
    if bg is None or bg.shape != frame.shape:
        return 0
    return int(((frame - bg) >= delta_c).sum() >= min_px)


def new_glints(base: SiteBaseline, anchor: int, cands: list[tuple[float, float]], tol_px: float = 8.0) -> list:
    known = base.glints.get(anchor, [])
    return [c for c in cands if all(np.hypot(c[0] - k[0], c[1] - k[1]) > tol_px for k in known)]


def newobj_score(n_new_emitters: int, n_thermal: int, n_glints: int) -> tuple[float, float]:
    """RF part is gated (reliable); optical parts are report-only weighted low."""
    v = min(1.0, 0.8 * min(n_new_emitters, 1) + 0.3 * min(n_thermal, 1) + 0.15 * min(n_glints, 1))
    return v, (0.8 if n_new_emitters else 0.4)
