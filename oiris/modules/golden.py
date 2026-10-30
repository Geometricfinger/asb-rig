"""M-09 golden dataset (C5) and M-12 feedback loop.
Manifest: per-clip SHA-256, label (object type only), source tier, consent ref, split.
The frozen test split never receives new clips; confirmed sightings enter quarantine,
a reviewer promotes them to the growth set (train/dev only)."""
from __future__ import annotations
import hashlib, hmac, json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from ..guard.vocabulary import check_text

FORMAT_VERSION = 2
SPLITS = {"train", "dev", "test", "growth", "quarantine"}
TIERS = {"own_recorded", "synthetic", "restricted_licensed"}
LABELS = {"camera_device", "ir_emitter", "warm_object", "mannequin_unheated", "mannequin_heated", "toy_robot_powered",
          "object_control", "printed_photo", "screen_replay", "glass_eye_prop", "speaker_replay", "fixed_emitter",
          "planted_object", "volunteer_consented", "benign"}


class ManifestError(ValueError):
    pass


@dataclass
class Clip:
    clip_id: str
    path: str
    sha256: str
    label: str
    split: str
    source_tier: str
    consent_id: str | None = None
    contains_person: bool = False
    rights: str = "own"


@dataclass
class Manifest:
    version: int = 1
    format_version: int = FORMAT_VERSION
    frozen_test_hash: str | None = None
    clips: list[Clip] = field(default_factory=list)

    def test_hash(self) -> str:
        t = sorted((c.clip_id, c.sha256) for c in self.clips if c.split == "test")
        return hashlib.sha256(json.dumps(t).encode()).hexdigest()

    def freeze(self) -> str:
        self.frozen_test_hash = self.test_hash()
        return self.frozen_test_hash

    def add(self, c: Clip) -> None:
        if c.split not in SPLITS or c.source_tier not in TIERS or c.label not in LABELS:
            raise ManifestError("bad split/tier/label")
        check_text(c.label)
        if c.contains_person and not c.consent_id:
            raise ManifestError("clip with a person needs a consent ID")
        if c.split == "test" and self.frozen_test_hash:
            raise ManifestError("frozen test split cannot receive clips")
        if any(x.clip_id == c.clip_id for x in self.clips):
            raise ManifestError("duplicate clip id")
        self.clips.append(c)
        self.version += 1

    def withdraw(self, consent_id: str) -> int:
        n = len(self.clips)
        if self.frozen_test_hash and any(c.consent_id == consent_id and c.split == "test" for c in self.clips):
            self.frozen_test_hash = None   # re-freeze needs a new decision; claims reset
        self.clips = [c for c in self.clips if c.consent_id != consent_id]
        if len(self.clips) != n:
            self.version += 1
        return n - len(self.clips)

    def verify(self, root: Path) -> list[str]:
        bad = []
        for c in self.clips:
            p = root / c.path
            if not p.exists() or not hmac.compare_digest(hashlib.sha256(p.read_bytes()).hexdigest(), c.sha256):
                bad.append(c.clip_id)
        if self.frozen_test_hash and self.test_hash() != self.frozen_test_hash:
            bad.append("<frozen test split changed>")
        return bad

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        d = migrate(json.loads(path.read_text(encoding="utf-8")))
        return cls(d["version"], d["format_version"], d.get("frozen_test_hash"), [Clip(**c) for c in d["clips"]])


def migrate(d: dict) -> dict:
    """Golden-manifest format migrations. v1 used `tier`; v2 renamed to `source_tier`, added `rights`."""
    fv = d.get("format_version", 1)
    if fv > FORMAT_VERSION:
        raise ManifestError(f"manifest format v{fv} newer than supported v{FORMAT_VERSION}")
    if fv == 1:
        for c in d.get("clips", []):
            c["source_tier"] = c.pop("tier", "own_recorded")
            c.setdefault("rights", "own")
        d["format_version"] = 2
    return d


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class FeedbackLoop:
    """Confirmed/benign sightings -> quarantine -> (reviewer) -> growth. Never test."""

    def __init__(self, manifest: Manifest, root: Path):
        self.m, self.root = manifest, root

    def propose(self, sighting_id: str, features_path: Path, label: str, verdict: str,
                consent_id: str | None, contains_person: bool) -> Clip:
        if verdict not in ("confirmed", "benign"):
            raise ManifestError("only confirmed or benign sightings become clips")
        lab = label if verdict == "confirmed" else "benign"
        c = Clip(f"fb-{sighting_id}", str(features_path.relative_to(self.root)), sha256_file(features_path), lab,
                 "quarantine", "own_recorded", consent_id, contains_person)
        self.m.add(c)
        return c

    def promote(self, clip_id: str, to: str = "growth") -> None:
        if to not in ("growth",):
            raise ManifestError("feedback clips may only be promoted to growth (train/dev use)")
        for c in self.m.clips:
            if c.clip_id == clip_id:
                if c.split != "quarantine":
                    raise ManifestError("not in quarantine")
                c.split = to
                self.m.version += 1
                return
        raise KeyError(clip_id)
