"""Score port (C1). A ScoreModule turns a window of samples into one Score in [0,1].
`safe_update` wraps every module: exceptions, NaN/inf, wrong types -> FAILED score."""
from __future__ import annotations
import logging
import math
from typing import Protocol

from ..schema import Health, Sample, Score

log = logging.getLogger(__name__)


class ScoreModule(Protocol):
    name: str               # e.g. "S_glint"
    inputs: set             # adapter capabilities consumed, e.g. {"nir_pair"}
    module_flag: str        # feature flag, e.g. "M-01"
    def update(self, window: list[Sample]) -> Score: ...


def safe_update(mod, window: list[Sample]) -> Score:
    try:
        s = mod.update(window)
        if not isinstance(s, Score):
            raise TypeError(f"returned {type(s).__name__}, not Score")
        if not (math.isfinite(s.value) and math.isfinite(s.confidence)):
            raise ValueError("non-finite score")
        return s
    except Exception as e:  # noqa: BLE001 - fault isolation
        log.warning("score %s failed: %s", getattr(mod, "name", "?"), e)
        return Score(getattr(mod, "name", "unknown"), 0.0, 0.0, Health.FAILED, {"error": str(e)[:200]})
