"""M-07 per-location baselines and new-object-at-known-location (A10).
Anchors are printed ArUco markers (DICT_4X4_50, detected by features/aruco.py) stuck at fixed
spots; an anchor's key is its marker ID, found in the camera view, not a typed-in number."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np


@dataclass
class SiteBaseline:
    site_code: str
    anchors: list[int] = field(default_factory=list)   # registered ArUco marker IDs
    anchor_poses: dict = field(default_factory=dict)   # marker ID -> (R, t) at registration, if intrinsics known
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


def register_anchors(base: SiteBaseline, gray: np.ndarray, K: np.ndarray | None = None, side_m: float | None = None) -> list[int]:
    """Detect markers in a setup frame and register them as this site's anchors."""
    from . import aruco
    found = aruco.detect(gray)
    for m in found:
        if m.id not in base.anchors:
            base.anchors.append(m.id)
        if K is not None and side_m:
            base.anchor_poses[m.id] = aruco.pose(m, side_m, K)
    return [m.id for m in found]


def anchor_in_view(base: SiteBaseline, gray: np.ndarray) -> int | None:
    """The registered anchor marker that is most prominent (largest) in this frame, or None."""
    from . import aruco
    seen = [m for m in aruco.detect(gray) if m.id in base.anchors]
    return max(seen, key=lambda m: m.side_px).id if seen else None


def pass_from_view(base: SiteBaseline, gray: np.ndarray, emitters: set, thermal: np.ndarray | None,
                   glints: list | None) -> int | None:
    """One baseline pass at whatever anchor the camera sees; returns that anchor (None = skipped)."""
    a = anchor_in_view(base, gray)
    if a is None:
        return None
    base.add_pass(emitters, {a: thermal} if thermal is not None else {}, {a: list(glints or [])})
    return a
