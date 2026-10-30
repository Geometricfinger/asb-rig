"""Consent guard: a human-subject session requires a recorded, unexpired consent ID."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any


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
    """In memory, or durable when given the local encrypted store (`DB`): every grant, withdrawal and
    expiry is written (sealed) to `consent_record` and reloaded on construction, so withdrawals
    survive a restart."""

    def __init__(self, db: Any = None) -> None:
        self._r: dict[str, ConsentRecord] = {}
        self.withdraw_hooks: list = []
        self.db = db
        if db is not None:
            for cid, body in db.execute("SELECT consent_id, body FROM consent_record").fetchall():
                d = db.open_json(body, b"consent:" + cid.encode())
                self._r[cid] = ConsentRecord(cid, d["subject_code"], set(d["scopes"]), float(d["expires_utc"]),
                                             bool(d["withdrawn"]))

    def _persist(self, rec: ConsentRecord) -> None:
        if self.db is None:
            return
        body = self.db.seal_json({"subject_code": rec.subject_code, "scopes": sorted(rec.scopes),
                                  "expires_utc": rec.expires_utc, "withdrawn": rec.withdrawn},
                                 b"consent:" + rec.consent_id.encode())
        self.db.execute("INSERT OR REPLACE INTO consent_record(consent_id, body, updated_utc) VALUES(?,?,?)",
                        (rec.consent_id, body, time.time()))

    def known(self, consent_id: str) -> bool:
        return consent_id in self._r

    def get(self, consent_id: str) -> ConsentRecord | None:
        return self._r.get(consent_id)

    def add(self, rec: ConsentRecord) -> None:
        self._r[rec.consent_id] = rec
        self._persist(rec)

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
            self._persist(rec)   # durable before any hook runs
            for h in self.withdraw_hooks:
                h(consent_id)
