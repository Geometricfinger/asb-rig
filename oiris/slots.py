"""Replaceable model slots (ADR-0055, docs/PLUGINS.md).

Every learned/heuristic model O Iris uses sits behind one of these Protocols. Core code only
talks to a `SlotManager`; which implementation fills a slot is ONE config setting
(`plugins.slots.<slot> = "<plugin name>"`). Empty or broken slot => the feature degrades
(returns None / "unavailable"), the rest of the system keeps running. No model weights live
in this repo; plugins fetch or point at their own, under their own licence.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence, runtime_checkable

import numpy as np

log = logging.getLogger(__name__)

SLOTS = ("speech_recognizer", "voice_antispoof", "speaker_embed", "eye_model", "fusion_weights", "face_match")


@dataclass(frozen=True)
class Transcript:
    text: str                 # what was heard, e.g. "four seven nine one"
    speech_start: float       # same clock as DigitChallenge (monotonic seconds)
    confidence: float = 1.0   # [0,1]


@runtime_checkable
class SpeechRecognizer(Protocol):
    """speech_recognizer v1.0: offline only. `audio` = mono float32 PCM in [-1,1]."""
    name: str
    def transcribe(self, audio: np.ndarray, sample_rate: int, t0: float) -> Transcript: ...


@runtime_checkable
class VoiceAntiSpoof(Protocol):
    """voice_antispoof v1.0: probability in [0,1] that audio is replayed/synthetic."""
    name: str
    def spoof_score(self, audio: np.ndarray, sample_rate: int) -> float: ...


@runtime_checkable
class SpeakerEmbed(Protocol):
    """speaker_embed v1.0: fixed-size voice embedding (RAM only; never stored by the slot)."""
    name: str
    dim: int
    def embed(self, audio: np.ndarray, sample_rate: int) -> np.ndarray: ...


@runtime_checkable
class EyeModel(Protocol):
    """eye_model v1.0: eye-feature dict -> anomaly score in [0,1] (S_eye convention)."""
    name: str
    def predict(self, features: dict) -> float: ...


@runtime_checkable
class FusionWeights(Protocol):
    """fusion_weights v1.0: returns an `oiris.fusion.stack.FusionModel`."""
    name: str
    def load(self) -> Any: ...


PROTOCOLS: dict[str, type] = {"speech_recognizer": SpeechRecognizer, "voice_antispoof": VoiceAntiSpoof,
                              "speaker_embed": SpeakerEmbed, "eye_model": EyeModel, "fusion_weights": FusionWeights}
# face_match uses oiris.modules.face_match.port.FaceMatchPort (M-16 gate, lazy import).


def _unit(x: float) -> float:
    v = float(x)
    if not 0.0 <= v <= 1.0:   # also rejects NaN
        raise ValueError(f"slot output {v} outside [0,1]")
    return v


@dataclass
class SlotManager:
    """Resolves each slot from the registry by config; isolates every call."""
    registry: Any
    slots: dict = field(default_factory=dict)      # slot -> plugin name
    options: dict = field(default_factory=dict)    # plugin name -> kwargs
    status: dict = field(default_factory=dict)     # slot -> "active" | "empty" | "failed: ..."
    _inst: dict = field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg, registry=None) -> "SlotManager":
        from .registry import default_registry
        p = getattr(cfg, "plugins", {}) or {}
        return cls(registry or default_registry(p), dict(p.get("slots", {})), dict(p.get("options", {})))

    def get(self, slot: str) -> Any | None:
        if slot in self._inst:
            return self._inst[slot]
        name = self.slots.get(slot)
        inst = None
        if not name:
            self.status[slot] = "empty"
        else:
            try:
                inst = self.registry.create(slot, name, **self.options.get(name, {}))
                proto = PROTOCOLS.get(slot)
                if proto is not None and not isinstance(inst, proto):
                    raise TypeError(f"{name} does not implement {proto.__name__}")
                self.status[slot] = "active"
            except Exception as e:  # noqa: BLE001 - fault isolation: a bad plugin empties its slot only
                log.error("slot %s (%s) unavailable: %s", slot, name, e)
                self.status[slot], inst = f"failed: {e}", None
        self._inst[slot] = inst
        return inst

    def remove(self, slot: str) -> None:
        self.slots.pop(slot, None)
        self._inst.pop(slot, None)
        self.status[slot] = "empty"

    def _call(self, slot: str, fn):
        m = self.get(slot)
        if m is None:
            return None
        try:
            return fn(m)
        except Exception as e:  # noqa: BLE001
            log.warning("slot %s call failed: %s", slot, e)
            self.status[slot] = f"failed: {e}"
            return None

    # typed helpers used by core ----------------------------------------------------------
    def transcribe(self, audio, sr: int, t0: float) -> Transcript | None:
        def f(m):
            t = m.transcribe(np.asarray(audio, np.float32), sr, t0)
            if not isinstance(t, Transcript):
                raise TypeError("transcribe must return Transcript")
            return t
        return self._call("speech_recognizer", f)

    def spoof_score(self, audio, sr: int) -> float | None:
        return self._call("voice_antispoof", lambda m: _unit(m.spoof_score(np.asarray(audio, np.float32), sr)))

    def speaker_embedding(self, audio, sr: int) -> np.ndarray | None:
        def f(m):
            v = np.asarray(m.embed(np.asarray(audio, np.float32), sr), np.float32).ravel()
            if v.size != m.dim or not np.all(np.isfinite(v)):
                raise ValueError("bad speaker embedding")
            return v
        return self._call("speaker_embed", f)

    def eye_score(self, features: dict) -> float | None:
        return self._call("eye_model", lambda m: _unit(m.predict(features)))

    def fusion_model(self):
        from .fusion.stack import FusionModel
        def f(m):
            fm = m.load()
            FusionModel.from_json(fm.to_json())   # validates shape/finite
            return fm
        return self._call("fusion_weights", f) or FusionModel()

    def face_backend(self) -> Any | None:
        """Name of the face_match plugin (M-16 gate builds it); None = M-16 cannot run."""
        return self.slots.get("face_match")


def speaker_similarity(a: np.ndarray, b: Sequence[float]) -> float:
    a, bb = np.asarray(a, float), np.asarray(b, float)
    n = float(np.linalg.norm(a) * np.linalg.norm(bb))
    return 0.0 if n == 0 else max(0.0, min(1.0, (float(a @ bb) / n + 1) / 2))
