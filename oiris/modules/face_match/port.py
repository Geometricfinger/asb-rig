"""FaceMatchPort (spec section 12): the only interface a face backend implements.
Backends compute; they never store, log or export."""
from __future__ import annotations
import enum, math
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

import numpy as np

from ...schema import Health


class Angle(str, enum.Enum):
    FRONT = "front"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


REQUIRED_ANGLES = (Angle.FRONT, Angle.LEFT, Angle.RIGHT, Angle.UP, Angle.DOWN)


@dataclass
class FaceBox:
    x: int
    y: int
    w: int
    h: int
    score: float = 1.0
    pose: Angle | None = None          # backend's head-pose estimate, if it has one
    landmarks: Any = None              # backend-private (e.g. 5 points for alignment)


class Embedding:
    """RAM-only feature vector. `zero()` overwrites it in place; core calls it after use."""
    __slots__ = ("vec",)

    def __init__(self, vec: np.ndarray):
        self.vec = np.ascontiguousarray(vec, dtype=np.float32).ravel()

    def zero(self) -> None:
        self.vec.fill(0.0)

    def valid(self, dim: int | None = None) -> bool:
        v = self.vec
        if v.ndim != 1 or v.size == 0 or (dim is not None and v.size != dim):
            return False
        return bool(np.all(np.isfinite(v))) and float(np.linalg.norm(v)) > 1e-6


@dataclass
class Template:
    person_id: str
    vec: np.ndarray                    # decrypted only inside the module core, in RAM


@dataclass
class MatchResult:
    person_id: str
    confidence: float                  # [0, 1]


@dataclass
class TemplateStatus:
    complete: bool
    missing_angles: list = field(default_factory=list)
    good_shots: int = 0
    needed_shots: int = 0
    message: str = ""


class FaceMatchPort(Protocol):
    name: str
    license: str
    model_id: str
    model_version: str
    test_only: bool

    def open(self, cfg: dict) -> None: ...
    def close(self) -> None: ...
    def health(self) -> tuple[Health, str]: ...
    def detect(self, frame: Any, timeout_s: float) -> list[FaceBox]: ...
    def embed(self, frame: Any, box: FaceBox) -> Embedding: ...
    def compare(self, e: Embedding, templates: Sequence[Template]) -> MatchResult | None: ...


def unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).ravel()
    n = float(np.linalg.norm(v))
    return v / n if n > 0 and math.isfinite(n) else v


def cosine_best(e: Embedding, templates: Sequence[Template]) -> MatchResult | None:
    """Shared compare: cosine similarity mapped to [0, 1]; best template wins."""
    if not templates:
        return None
    q = unit(e.vec)
    best: MatchResult | None = None
    for t in templates:
        s = float(np.dot(q, unit(t.vec)))
        c = max(0.0, min(1.0, (s + 1.0) / 2.0))
        if best is None or c > best.confidence:
            best = MatchResult(t.person_id, c)
    return best
