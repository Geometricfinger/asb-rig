"""Privacy guard: what may be persisted. No audio, no raw MACs, no full frames of people, no face
templates except enrolled-person templates from the opted-in M-16 module (ADR-0049)."""
from __future__ import annotations
import hashlib, hmac
import numpy as np


class PrivacyError(PermissionError):
    pass


def hash_identifier(identifier: str, site_key: bytes) -> str:
    """Raw MAC/BSSID never stored: HMAC-SHA256 with a per-site key (truncated)."""
    return hmac.new(site_key, identifier.lower().encode(), hashlib.sha256).hexdigest()[:32]


# Only the M-16 module core may persist a face template, and only while M-16 is enabled
# and opted in (ADR-0049). Every other source, and M-16 while off, is refused.
FACE_TEMPLATE_SOURCE = "M-16"


def check_persist(kind: str, contains_person: bool, payload=None, *, source: str | None = None, m16_enabled: bool = False) -> None:
    if kind in ("audio", "raw_audio", "voice_wav"):
        raise PrivacyError("audio is never written to disk")
    if kind in ("nir_frame", "eye_frame", "rgb_frame") and contains_person:
        if payload is None or getattr(payload, "shape", (999, 999))[:2] > (64, 64):
            raise PrivacyError("full frames containing a person may not be saved (64x64 crops only)")
    if kind == "face_template":
        if source != FACE_TEMPLATE_SOURCE or not m16_enabled:
            raise PrivacyError("no face templates (only the opted-in M-16 module may store enrolled templates)")
        if payload is not None:
            raise PrivacyError("M-16 stores templates sealed by its own core; no raw template payloads here")
    if kind in ("face_embedding", "face_id", "face_hash", "face_crop"):
        raise PrivacyError("no stranger face data of any kind (research mode is counts only)")
    if kind == "mac" :
        raise PrivacyError("store hashed identifiers only")


def round_gps(lat: float | None, lon: float | None, decimals: int = 2):
    if lat is None or lon is None:
        return None, None
    return round(lat, decimals), round(lon, decimals)


def crop_ok(arr: np.ndarray) -> bool:
    return arr.ndim >= 2 and arr.shape[0] <= 64 and arr.shape[1] <= 64
