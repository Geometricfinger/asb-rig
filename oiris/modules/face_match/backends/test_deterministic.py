"""TEST-ONLY backend. Deterministic, dependency-free, for CI and the headless suite.

It does NOT recognise real faces. It works on synthetic frames made by
`synth_face_frame()`: each "face" is a bright textured square (pixels 100..230) on a dark
background with one 255-valued marker pixel whose offset from the square's centre encodes
head pose. Detection = connected bright regions; embedding = 8x8 mean-pooled, centred,
L2-normalised crop; compare = cosine. The module core refuses to open it unless
`allow_test_backend` is set (tests only)."""
from __future__ import annotations
from collections import deque
from typing import Any, Sequence

import numpy as np

from ....schema import Health
from ..port import Angle, Embedding, FaceBox, MatchResult, Template, cosine_best

POSE_OFFSET = {Angle.FRONT: (0, 0), Angle.LEFT: (-1, 0), Angle.RIGHT: (1, 0), Angle.UP: (0, -1), Angle.DOWN: (0, 1)}


class TestDeterministicBackend:
    name = "test_deterministic"
    license = "Apache-2.0"
    model_id = "test-deterministic"
    model_version = "1"
    test_only = True
    __test__ = False   # not a pytest class

    def __init__(self) -> None:
        self._health = (Health.OK, "")
        self.cfg: dict = {}

    def open(self, cfg: dict) -> None:
        self.cfg = dict(cfg or {})

    def close(self) -> None:
        pass

    def health(self) -> tuple[Health, str]:
        return self._health

    def detect(self, frame: Any, timeout_s: float) -> list[FaceBox]:
        g = np.asarray(frame)
        if g.ndim != 2:
            raise ValueError("test backend expects a 2-D grayscale frame")
        mask = g >= 20
        seen = np.zeros_like(mask)
        boxes: list[FaceBox] = []
        H, W = mask.shape
        for y0, x0 in zip(*np.nonzero(mask)):
            if seen[y0, x0]:
                continue
            q = deque([(y0, x0)]); seen[y0, x0] = True
            ys, xs = [y0], [x0]
            while q:
                y, x = q.popleft()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True; q.append((ny, nx)); ys.append(ny); xs.append(nx)
            if len(ys) < 16:
                continue
            x, y, w, h = int(min(xs)), int(min(ys)), int(max(xs) - min(xs) + 1), int(max(ys) - min(ys) + 1)
            boxes.append(FaceBox(x, y, w, h, 1.0, self._pose(g, x, y, w, h)))
        return boxes

    @staticmethod
    def _pose(g: np.ndarray, x: int, y: int, w: int, h: int) -> Angle | None:
        c = g[y:y + h, x:x + w]
        hits = np.argwhere(c == 255)
        if len(hits) != 1:
            return None
        ny, nx = hits[0]
        dx, dy = (nx - w / 2) / w, (ny - h / 2) / h
        if abs(dx) < 0.15 and abs(dy) < 0.15:
            return Angle.FRONT
        if abs(dx) >= abs(dy):
            return Angle.RIGHT if dx > 0 else Angle.LEFT
        return Angle.DOWN if dy > 0 else Angle.UP

    def embed(self, frame: Any, box: FaceBox) -> Embedding:
        g = np.asarray(frame, dtype=np.float32)[box.y:box.y + box.h, box.x:box.x + box.w].copy()
        g[g >= 255] = np.median(g)              # drop the pose marker
        n = 8
        hs, ws = g.shape[0] // n, g.shape[1] // n
        if hs == 0 or ws == 0:
            raise ValueError("face too small to embed")
        pooled = g[:hs * n, :ws * n].reshape(n, hs, n, ws).mean(axis=(1, 3)).ravel()
        pooled -= pooled.mean()
        e = Embedding(pooled / (np.linalg.norm(pooled) or 1.0))
        g.fill(0)
        return e

    def compare(self, e: Embedding, templates: Sequence[Template]) -> MatchResult | None:
        return cosine_best(e, templates)


def synth_face_frame(person_seed: int, pose: Angle = Angle.FRONT, *, size: int = 64, frame: int = 160,
                     at: tuple[int, int] = (40, 40), blur: bool = False, brightness: float = 1.0,
                     extra_faces: Sequence[tuple[int, tuple[int, int]]] = (), noise_seed: int = 0) -> np.ndarray:
    """Synthetic test frame (no real person). Same seed = same synthetic 'face'."""
    img = np.zeros((frame, frame), dtype=np.float32)

    def put(seed: int, xy: tuple[int, int], p: Angle) -> None:
        rng = np.random.default_rng(seed)
        coarse = rng.uniform(100, 230, size=(8, 8))
        tex = np.kron(coarse, np.ones((size // 8, size // 8)))
        tex += np.random.default_rng(seed * 7919 + noise_seed + 1).uniform(-6, 6, tex.shape)
        if blur:
            k = 9
            pad = np.pad(tex, k // 2, mode="edge")
            tex = np.mean([pad[i:i + size, j:j + size] for i in range(k) for j in range(k)], axis=0)
        tex = np.clip(tex * brightness, 0, 254)
        tex[tex < 20] = 20
        dx, dy = POSE_OFFSET[p]
        tex[size // 2 + dy * size // 3, size // 2 + dx * size // 3] = 255
        x, y = xy
        img[y:y + size, x:x + size] = tex

    put(person_seed, at, pose)
    for seed, xy in extra_faces:
        put(seed, xy, Angle.FRONT)
    return img.astype(np.uint8)
