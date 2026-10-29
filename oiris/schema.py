"""Contracts C1 (score), C2 sample, C3 event. No field names a class of person."""
from __future__ import annotations
import enum, time, uuid
from dataclasses import dataclass, field, asdict
from typing import Any

from . import SCHEMA_VERSION


class Health(str, enum.Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class Sample:
    adapter_id: str
    t_mono_ns: int
    t_wall: float
    seq: int
    units: str
    quality: float
    data: Any
    replay: bool = False


@dataclass
class Score:
    """C1: value and confidence are clamped to [0, 1]."""
    module: str
    value: float
    confidence: float
    health: Health = Health.OK
    evidence: dict = field(default_factory=dict)
    t_mono_ns: int = field(default_factory=time.monotonic_ns)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        self.value = clamp01(self.value)
        self.confidence = clamp01(self.confidence)
        self.health = Health(self.health)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["health"] = self.health.value
        return d


def clamp01(x: float) -> float:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    if x != x:  # NaN
        return 0.0
    return 0.0 if x < 0 else 1.0 if x > 1 else x


class Level(str, enum.Enum):
    FYI = "fyi"            # low
    ATTENTION = "attention"  # medium
    CONFIRMED = "confirmed"  # only after operator confirmation


SIGNATURES = {
    "A1": "Lens-glint candidate",
    "A2": "Active near-IR emitter",
    "A3": "Thermal pattern atypical vs baseline",
    "A4": "Radio emitter near",
    "A5": "Expected vital motion absent at close range",
    "A6": "Motion pattern irregular",
    "A7": "Eye-dynamics atypical",
    "A8": "Voice-liveness indicators not observed",
    "A9": "Known emitter changed vs its baseline",
    "A10": "New fixed emitter or object at a known anchor",
    "A11": "Expected liveness indicators absent across two or more families",
}

BENIGN_CAUSES = {
    "A1": ["phones", "webcams", "eyeglasses", "watches", "jewelry", "human eyes"],
    "A2": ["security cameras", "remotes", "face-unlock emitters", "night-vision rings"],
    "A3": ["cold hands", "coats", "hot drinks", "fever", "heaters", "sun-warmed objects"],
    "A4": ["phones", "watches", "earbuds", "medical devices", "beacons"],
    "A5": ["subject moving", "wet clothing", "radar blocked"],
    "A6": ["ordinary movement", "children"],
    "A7": ["sunglasses", "contact lenses", "eye drops", "fatigue", "medication", "glare", "prosthetic eye"],
    "A8": ["poor mic placement", "noise", "speakerphone", "a cold", "recording device in use"],
    "A9": ["firmware update", "battery", "temperature", "relocated device"],
    "A10": ["guests' devices", "moved furniture", "new appliance"],
    "A11": ["photo or video on a screen", "mask on a stand", "mannequin", "subject outside sensor range"],
}


@dataclass
class Event:
    """C3 alert event."""
    signature: str
    level: Level
    score: float
    contributing: list[str]
    families: list[str]
    location_id: str | None = None
    health_snapshot: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    t_wall: float = field(default_factory=time.time)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if self.signature not in SIGNATURES:
            raise ValueError(f"unknown signature {self.signature}")
        self.level = Level(self.level)
        self.score = clamp01(self.score)

    @property
    def description(self) -> str:
        return SIGNATURES[self.signature]

    @property
    def benign_causes(self) -> list[str]:
        return BENIGN_CAUSES[self.signature]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level"] = self.level.value
        d["description"] = self.description
        d["benign_causes"] = self.benign_causes
        return d
