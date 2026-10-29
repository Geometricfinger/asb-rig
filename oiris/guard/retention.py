"""Retention guard: nightly deletion of expired rows (default 30 days), 'keep' respected."""
from __future__ import annotations
import time

TABLES = ["session", "eye_trace", "voice_event", "sighting", "sweep", "fusion_result", "signature_event"]


def purge(db, days: int = 30, now: float | None = None) -> int:
    now = time.time() if now is None else now
    cutoff = now - days * 86400
    n = 0
    for t in TABLES:
        if not db.has_table(t):
            continue
        keep = " AND COALESCE(keep,0)=0" if db.has_column(t, "keep") else ""
        n += db.execute(f"DELETE FROM {t} WHERE t_wall < ?{keep}", (cutoff,)).rowcount
    db.execute("DELETE FROM enrollment WHERE delete_after_utc < ?", (now,)) if db.has_table("enrollment") else None
    if db.has_table("fm_encounter"):   # M-16 logs/counts expire by their own expires_at (ADR-0039)
        for t in ("fm_encounter", "fm_unrecognized_count"):
            n += db.execute(f"DELETE FROM {t} WHERE expires_at < ?", (now,)).rowcount
    db.audit("retention_purge", {"deleted": n, "days": days})
    db.commit()
    return n
