"""M-07 site anchors: ArUco marker detection in numpy only (no OpenCV needed at runtime).

Dictionary: ArUco DICT_4X4_50 (50 markers, 4x4 bits, 1-bit correction), the same code words as
OpenCV's predefined dictionary (opencv/opencv, Apache-2.0; code words listed in THIRD_PARTY.md).
Pipeline: Otsu threshold -> dark connected components -> quad corners -> homography -> 6x6 cell
sampling (black border + 4x4 bits) -> dictionary match in 4 rotations. Pose from the planar
homography when camera intrinsics and the printed marker size are given.
Markers are printed by the owner and stuck at fixed spots; they identify places, never people."""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

DICT_4X4_50 = (46386, 3994, 13101, 39238, 21662, 31181, 40494, 50418, 65242, 53078, 63889, 4519, 3767, 10767,
               9393, 9790, 18021, 26112, 27742, 30383, 34443, 45099, 52437, 56706, 65095, 38001, 44260, 42324,
               8483, 13423, 17429, 22450, 40655, 61643, 2222, 2345, 6261, 1279, 3574, 7258, 5912, 10792, 12940,
               14514, 9448, 12011, 11583, 19300, 20526, 20499)
BITS = 4
MAX_CORRECTION = 1


@dataclass(frozen=True)
class Marker:
    id: int
    corners: np.ndarray        # (4,2) x,y: marker top-left, top-right, bottom-right, bottom-left
    hamming: int

    @property
    def centre(self) -> tuple[float, float]:
        c = self.corners.mean(axis=0)
        return float(c[0]), float(c[1])

    @property
    def side_px(self) -> float:
        c = self.corners
        return float(np.mean([np.linalg.norm(c[i] - c[(i + 1) % 4]) for i in range(4)]))


def code_bits(code: int) -> np.ndarray:
    return np.array([(code >> (15 - i)) & 1 for i in range(16)], np.uint8).reshape(4, 4)


def render(marker_id: int, cell_px: int = 10, quiet_cells: int = 1) -> np.ndarray:
    """uint8 image of a marker (bit 1 = white) with a white quiet zone, for printing and tests."""
    g = np.zeros((6, 6), np.uint8)
    g[1:5, 1:5] = code_bits(DICT_4X4_50[marker_id])
    g = np.pad(g, quiet_cells, constant_values=1)
    return (np.kron(g, np.ones((cell_px, cell_px), np.uint8)) * 255).astype(np.uint8)


def otsu(gray: np.ndarray) -> float:
    h = np.bincount(gray.astype(np.uint8).ravel(), minlength=256).astype(float)
    p = h / h.sum(); w = np.cumsum(p); mu = np.cumsum(p * np.arange(256)); mt = mu[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (mt * w - mu) ** 2 / (w * (1 - w))
    if not np.isfinite(s).any():
        return -1.0                                # uniform image: nothing is "dark"
    return float(np.nanargmax(s))


def label(mask: np.ndarray) -> np.ndarray:
    """4-connected component labels (0 = background) by vectorised min-propagation with
    pointer jumping; numpy only."""
    h, w = mask.shape
    big = h * w + 1
    lab = np.where(mask, np.arange(1, h * w + 1).reshape(h, w), big)
    while True:
        m = lab.copy()
        m[1:, :] = np.minimum(m[1:, :], lab[:-1, :]); m[:-1, :] = np.minimum(m[:-1, :], lab[1:, :])
        m[:, 1:] = np.minimum(m[:, 1:], lab[:, :-1]); m[:, :-1] = np.minimum(m[:, :-1], lab[:, 1:])
        m = np.where(mask, m, big)
        flat = np.concatenate([[0], m.ravel()])          # pointer jumping: label -> label of that pixel
        flat[flat > h * w] = big
        idx = np.where(m < big, m, 0)
        jumped = np.where(mask, np.minimum(m, np.concatenate([flat, [big]])[idx]), big)
        if np.array_equal(jumped, lab):
            break
        lab = jumped
    out = np.where(mask, lab, 0)
    return out


def _quad(ys: np.ndarray, xs: np.ndarray) -> np.ndarray | None:
    pts = np.stack([xs, ys], 1).astype(float)
    c = pts.mean(0)
    p1 = pts[np.argmax(((pts - c) ** 2).sum(1))]
    p3 = pts[np.argmax(((pts - p1) ** 2).sum(1))]
    d = p3 - p1
    n = np.array([-d[1], d[0]]) / (np.hypot(*d) or 1)
    s = (pts - p1) @ n
    if s.max() <= 1 or s.min() >= -1:
        return None
    p2, p4 = pts[np.argmax(s)], pts[np.argmin(s)]
    q = np.array([p1, p2, p3, p4])
    # order clockwise in image coordinates (y down), starting anywhere
    ang = np.arctan2(q[:, 1] - q[:, 1].mean(), q[:, 0] - q[:, 0].mean())
    return q[np.argsort(ang)]


def homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """DLT, 4+ point correspondences (N,2) -> 3x3 mapping src to dst."""
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u]); A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(np.asarray(A, float))
    H = vt[-1].reshape(3, 3)
    return H / H[2, 2]


def _apply(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    p = np.c_[pts, np.ones(len(pts))] @ H.T
    return p[:, :2] / p[:, 2:3]


def _read_cells(gray: np.ndarray, q: np.ndarray) -> np.ndarray | None:
    # snap corners outwards by half a pixel along the diagonals (pixel centres -> outer edge)
    c = q.mean(0); q = q + 0.5 * (q - c) / np.linalg.norm(q - c, axis=1, keepdims=True)
    H = homography(np.array([[0, 0], [6, 0], [6, 6], [0, 6]], float), q)
    g = np.arange(6) + 0.5
    vals = np.zeros((6, 6))
    offs = np.array([[0, 0], [0.2, 0], [-0.2, 0], [0, 0.2], [0, -0.2]])
    for r in range(6):
        for k in range(6):
            pts = _apply(H, np.array([[g[k], g[r]]]) + offs)
            xi = np.clip(np.round(pts[:, 0]).astype(int), 0, gray.shape[1] - 1)
            yi = np.clip(np.round(pts[:, 1]).astype(int), 0, gray.shape[0] - 1)
            vals[r, k] = gray[yi, xi].mean()
    lo, hi = float(np.min(vals)), float(np.max(vals))
    if hi - lo < 30:
        return None
    return (vals > (lo + hi) / 2).astype(np.uint8)


def _match(bits: np.ndarray) -> tuple[int, int, int] | None:
    best = None
    for rot in range(4):
        b = np.rot90(bits, -rot)
        code = int("".join(map(str, b.ravel())), 2)
        for i, c in enumerate(DICT_4X4_50):
            hd = bin(code ^ c).count("1")
            if hd <= MAX_CORRECTION and (best is None or hd < best[1]):
                best = (i, hd, rot)
    return best


def detect(gray: np.ndarray, min_side_px: int = 12, max_border_errors: int = 1) -> list[Marker]:
    """Detect DICT_4X4_50 markers in a grayscale uint8 image."""
    g = np.asarray(gray)
    if g.ndim == 3:
        g = g.mean(axis=2)
    g = g.astype(np.uint8)
    lab = label(g <= otsu(g))
    ids, counts = np.unique(lab[lab > 0], return_counts=True)
    out: list[Marker] = []
    for lid, n in zip(ids, counts):
        if n < min_side_px * min_side_px * 0.3:
            continue
        ys, xs = (np.asarray(a) for a in np.nonzero(lab == lid))
        if ys.min() == 0 or xs.min() == 0 or ys.max() == g.shape[0] - 1 or xs.max() == g.shape[1] - 1:
            continue                               # touches the frame edge: no quiet zone
        q = _quad(ys, xs)
        if q is None:
            continue
        sides = [np.linalg.norm(q[i] - q[(i + 1) % 4]) for i in range(4)]
        if min(sides) < min_side_px or max(sides) > 4 * min(sides):
            continue
        cells = _read_cells(g, q)
        if cells is None:
            continue
        border = np.r_[cells[0], cells[5], cells[1:5, 0], cells[1:5, 5]]
        if int(border.sum()) > max_border_errors:
            continue
        m = _match(cells[1:5, 1:5])
        if m is None:
            continue
        mid, hd, rot = m
        corners = np.roll(q, rot, axis=0)
        out.append(Marker(mid, corners, hd))
    return sorted(out, key=lambda m: m.id)


def pose(marker: Marker, side_m: float, K: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Planar pose from the homography: returns (R 3x3, t 3-vector in metres), camera frame."""
    s = side_m / 2
    obj = np.array([[-s, s], [s, s], [s, -s], [-s, -s]], float)    # marker frame, y up
    H = homography(obj, marker.corners)
    M = np.linalg.inv(K) @ H
    lam = 1.0 / np.linalg.norm(M[:, 0])
    r1, r2, t = lam * M[:, 0], lam * M[:, 1], lam * M[:, 2]
    if t[2] < 0:
        r1, r2, t = -r1, -r2, -t
    R = np.stack([r1, r2, np.cross(r1, r2)], 1)
    u, _, vt = np.linalg.svd(R)
    R = u @ vt
    return R, t
