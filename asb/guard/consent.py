"""Consent guard: a human-subject session requires a recorded, unexpired consent ID."""
from __future__ import annotations
import time
from dataclasses import dataclass, field


class ConsentError(PermissionError):
    pass


@dataclass
class ConsentRecord:
    consent_id: str
    subject_code: str
    scopes: set = field(default_factory=set)   # e.g. {"session","biometric_release","voice_enroll","eye_enroll","golden"}
    expires_utc: float = 0.0
    withdrawn: bool = False


class ConsentRegistry:
    def __init__(self) -> None:
        self._r: dict[str, ConsentRecord] = {}
        self.withdraw_hooks: list = []

    def add(self, rec: ConsentRecord) -> None:
        self._r[rec.consent_id] = rec

    def require(self, consent_id: str | None, scope: str = "session", now: float | None = None) -> ConsentRecord:
        now = time.time() if now is None else now
        rec = self._r.get(consent_id or "")
        if rec is None:
            raise ConsentError("human-subject session requires a consent ID")
        if rec.withdrawn:
            raise ConsentError("consent withdrawn")
        if rec.expires_utc and rec.expires_utc < now:
            raise ConsentError("consent expired")
        if scope not in rec.scopes:
            raise ConsentError(f"consent lacks scope {scope}")
        return rec

    def withdraw(self, consent_id: str) -> None:
        rec = self._r.get(consent_id)
        if rec:
            rec.withdrawn = True
            for h in self.withdraw_hooks:
                h(consent_id)
