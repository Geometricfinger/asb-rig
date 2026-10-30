"""Fusion v2: scores -> six families (confidence-weighted max) -> L2 logistic regression
with a missing-family mask. Evidence rule: an alert needs >=2 independent families;
one family alone is FYI; >=2 unhealthy families suppress the index. Outputs anomaly
signatures only; no field names a class of person."""
from __future__ import annotations
import json, logging, math
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

from ..schema import Health, Level, Score

log = logging.getLogger(__name__)

FAMILIES = ["optical", "thermal", "rf", "vital", "eye_liveness", "voice"]
SCORE_FAMILY = {
    "S_glint": "optical", "S_nir_emit": "optical", "S_motion": "optical", "S_newobj": "optical",
    "S_thermal": "thermal",
    "S_rf": "rf", "S_rf_drift": "rf",
    "S_radar": "vital", "S_live": "vital",
    "S_eye": "eye_liveness",
    "S_voice": "voice",
}
SCORE_SIGNATURE = {"S_glint": "A1", "S_nir_emit": "A2", "S_thermal": "A3", "S_rf": "A4", "S_radar": "A5",
                   "S_motion": "A6", "S_eye": "A7", "S_voice": "A8", "S_rf_drift": "A9", "S_newobj": "A10",
                   "S_live": "A5"}
FAMILY_THRESHOLD = 0.5


@dataclass
class FusionModel:
    """Level-2 weights. Default = hand-set conservative prior (documented in ADR-0004);
    replaced by trained weights from the Training port (C9) when they pass validation."""
    w: np.ndarray = field(default_factory=lambda: np.array([1.2, 1.0, 0.8, 1.0, 1.0, 0.6]))
    w_mask: np.ndarray = field(default_factory=lambda: np.zeros(6))
    b: float = -2.5
    version: str = "prior-0"

    def logit(self, x: np.ndarray, m: np.ndarray) -> float:
        return float(self.b + (self.w * x * (1 - m)).sum() + (self.w_mask * m).sum())

    def predict(self, x: np.ndarray, m: np.ndarray) -> float:
        return float(1 / (1 + np.exp(-self.logit(x, m))))

    def to_json(self) -> str:
        return json.dumps({"w": self.w.tolist(), "w_mask": self.w_mask.tolist(), "b": self.b, "version": self.version})

    @classmethod
    def from_json(cls, s: str) -> "FusionModel":
        d = json.loads(s)
        w, wm, b = np.asarray(d["w"], float), np.asarray(d["w_mask"], float), float(d["b"])
        if w.shape != (6,) or wm.shape != (6,):
            raise ValueError("invalid fusion weights: shape")
        if not (np.all(np.isfinite(w)) and np.all(np.isfinite(wm)) and math.isfinite(b)):   # Forge F5
            raise ValueError("invalid fusion weights: non-finite value")
        return cls(w, wm, b, str(d.get("version", "?")))


def family_values(scores: list[Score]) -> tuple[np.ndarray, np.ndarray, dict, list[str]]:
    vals = np.zeros(6); conf = np.zeros(6); mask = np.ones(6)
    contrib: dict[str, list[str]] = {f: [] for f in FAMILIES}
    unhealthy: set[str] = set()
    for s in scores:
        fam = SCORE_FAMILY.get(s.module)
        if fam is None:
            continue
        i = FAMILIES.index(fam)
        if s.health == Health.FAILED:
            unhealthy.add(fam)
            continue
        weighted = s.value * s.confidence
        mask[i] = 0
        if conf[i] == 0 or weighted > vals[i] * conf[i]:
            vals[i], conf[i] = s.value, s.confidence
        if s.value >= FAMILY_THRESHOLD and s.confidence > 0:
            contrib[fam].append(s.module)
    # a family with at least one healthy score is not unhealthy
    unhealthy = {f for f in unhealthy if mask[FAMILIES.index(f)] == 1}
    return vals, mask, contrib, sorted(unhealthy)


def fuse(scores: list[Score], model: FusionModel | None = None, min_families: int = 2,
         max_unhealthy: int = 1) -> dict:
    model = model or FusionModel()
    x, m, contrib, unhealthy = family_values(scores)
    active = [f for f in FAMILIES if contrib[f]]
    suppressed = len(unhealthy) > max_unhealthy
    idx = 0.0 if suppressed else model.predict(x, m)
    if suppressed:
        level = None
    elif len(active) >= min_families:
        level = Level.ATTENTION
    elif len(active) == 1:
        level = Level.FYI
    else:
        level = None
    sigs = sorted({SCORE_SIGNATURE[s.module] for s in scores
                   if s.module in SCORE_SIGNATURE and s.value >= FAMILY_THRESHOLD and s.health != Health.FAILED},
                  key=lambda c: int(c[1:]))
    if len({f for f in active if f in ("vital", "eye_liveness", "voice", "thermal")}) >= 2:
        sigs.append("A11")
    return {"anomaly_index": round(idx, 6), "level": level.value if level else None, "families_active": active,
            "families_missing": [FAMILIES[i] for i in range(6) if m[i]], "families_unhealthy": unhealthy,
            "suppressed": suppressed, "signatures": sigs, "model_version": model.version}


def train(X: np.ndarray, M: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 2000, lr: float = 0.1,
          version: str = "trained") -> FusionModel:
    """L2-regularised logistic regression by gradient descent (NumPy). Inputs: family values X (n,6),
    missing mask M (n,6), labels y (n,) for lab proxies (object classes, never people)."""
    Z = np.hstack([X * (1 - M), M])
    w = np.zeros(Z.shape[1]); b = 0.0
    n = len(y)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        g = Z.T @ (p - y) / n + l2 * w / n
        w -= lr * g; b -= lr * float((p - y).mean())
    return FusionModel(w[:6], w[6:], b, version)


def auc(y: np.ndarray, s: np.ndarray) -> float:
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def load_weights(path: str | Path, fallback: FusionModel | None = None) -> FusionModel:
    """Model-load failures never crash: fall back to last-good (or the prior)."""
    try:
        return FusionModel.from_json(Path(path).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        m = fallback or FusionModel()
        log.warning("fusion weights %s rejected (%s); using %s", path, e, m.version)
        return m
