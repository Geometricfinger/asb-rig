"""Model port (C9). A model package = manifest + weights file. Loading is guarded: on any
failure the slot keeps its last-good model or becomes disabled; it never raises."""
from __future__ import annotations
import hashlib, json, logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .registry import ALLOWED_LICENSES

log = logging.getLogger(__name__)
REQUIRED = {"name", "version", "license", "file", "sha256", "hypothesis", "output_range", "data_tier"}
DATA_TIERS = {"own_recorded", "synthetic", "restricted_licensed"}


class ModelPort(Protocol):
    name: str
    def predict(self, features: Any) -> float: ...   # must return a value in [0,1]


@dataclass
class ModelSlot:
    name: str
    model: Any = None
    manifest: dict | None = None
    status: str = "disabled"   # active | last_good | disabled
    error: str = ""

    def predict(self, features: Any) -> float | None:
        if self.model is None:
            return None
        try:
            v = float(self.model.predict(features))
            if not 0.0 <= v <= 1.0 or v != v:
                raise ValueError(f"model output {v} outside [0,1]")
            return v
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            log.warning("model %s predict failed: %s", self.name, e)
            return None


def validate_manifest(m: dict, root: Path) -> None:
    missing = REQUIRED - set(m)
    if missing:
        raise ValueError(f"manifest missing {sorted(missing)}")
    if m["license"] not in ALLOWED_LICENSES:
        raise ValueError(f"model license {m['license']} not allowed")
    if m["data_tier"] not in DATA_TIERS:
        raise ValueError("bad data_tier")
    if list(m["output_range"]) != [0, 1]:
        raise ValueError("output_range must be [0,1]")
    f = root / m["file"]
    if hashlib.sha256(f.read_bytes()).hexdigest() != m["sha256"]:
        raise ValueError("model file hash mismatch")


def load_into(slot: ModelSlot, manifest_path: str | Path, loader) -> ModelSlot:
    p = Path(manifest_path)
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
        validate_manifest(m, p.parent)
        model = loader(p.parent / m["file"], m)
        slot.model, slot.manifest, slot.status, slot.error = model, m, "active", ""
    except Exception as e:  # noqa: BLE001
        slot.error = f"load failed: {e}"
        slot.status = "last_good" if slot.model is not None else "disabled"
        log.error("model %s %s", slot.name, slot.error)
    return slot
