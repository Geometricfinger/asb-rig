"""M-16 module core: storage, modes, enrollment, review log, retention and wipe.
Backends only compute (port.py); everything that touches disk is here.

Keys (spec section 9): a random face key is kept in `<data_dir>/face_match.key`, sealed with
`keys.subkey("face-template")`. Each enrolled person has a random data key (DEK) sealed
with the face key; their name and template are sealed with the DEK. Deleting a person
destroys their DEK row; disabling destroys the face key file and every row, then VACUUMs.
Logs (places) are sealed with a separate log key in `<data_dir>/face_match_log.key`."""
from __future__ import annotations
import logging, os, statistics, time, uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ...guard.consent import ConsentError, ConsentRegistry
from ...guard.privacy import check_persist, round_gps
from ...guard.vocabulary import check_output, check_text
from ...schema import Health
from ...security.aead import Sealer
from .optin import STRICT, OptInError, log_change, opt_in_record

from .port import REQUIRED_ANGLES, Angle, Embedding, FaceBox, Template, TemplateStatus, unit
from .quality import QualityLimits, check_shot
from .supervisor import Guarded

log = logging.getLogger(__name__)

KEY_FILE, LOG_KEY_FILE = "face_match.key", "face_match_log.key"
REENROLL_MARGIN = 0.02
HINT = "recognition getting weaker, re-enroll?"


class FaceMatchLocked(PermissionError):
    pass


class ExportBlocked(PermissionError):
    pass


@dataclass
class FaceMatchConfig:
    """Spec section 13. There is deliberately no setting for the number of enrolled people."""
    modes: list = field(default_factory=list)
    jurisdiction: str = "strictest"
    require_enrollment_consent: bool = True
    match_threshold: float = 0.8
    encounter_retention_days: int = 30
    place_source: str = "named"
    time_bucket_minutes: int = 60
    allow_log_export: bool = False
    enroll_min_shots: int = 5
    enroll_max_shots: int = 10
    enroll_required_angles: list = field(default_factory=lambda: [a.value for a in REQUIRED_ANGLES])
    reenroll_confidence_drop: float = 0.1
    reenroll_window_matches: int = 20
    adapter: str = "opencv_zoo"
    model_dir: str = ""
    allow_test_backend: bool = False   # tests only; the test backend is refused otherwise

    def validate(self) -> "FaceMatchConfig":
        errs = []
        if any(m not in ("personal", "research") for m in self.modes): errs.append("face_match.modes: personal/research only")
        if not 0.5 <= self.match_threshold < 1.0: errs.append("face_match.match_threshold must be in [0.5, 1)")
        if not 1 <= self.encounter_retention_days <= 365: errs.append("face_match.encounter_retention_days must be 1..365")
        if self.place_source not in ("named", "gps_0.01"): errs.append("face_match.place_source must be named|gps_0.01")
        if not 1 <= self.time_bucket_minutes <= 1440: errs.append("face_match.time_bucket_minutes must be 1..1440")
        if not 5 <= self.enroll_min_shots <= self.enroll_max_shots: errs.append("face_match.enroll_min_shots must be >= 5 and <= enroll_max_shots")
        if any(a not in [x.value for x in Angle] for a in self.enroll_required_angles): errs.append("face_match.enroll_required_angles: unknown angle")
        if not 0 < self.reenroll_confidence_drop < 1 or self.reenroll_window_matches < 1: errs.append("face_match.reenroll_* out of range")
        if errs:
            raise ValueError("; ".join(errs))
        return self

    @classmethod
    def from_dict(cls, d: dict | None) -> "FaceMatchConfig":
        d = dict(d or {})
        unknown = set(d) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"face_match: unknown keys {sorted(unknown)}")
        return cls(**d).validate()


@dataclass
class ShotResult:
    ok: bool
    code: str
    reason: str
    needed_angles: list = field(default_factory=list)


@dataclass
class WipeReport:
    templates_destroyed: int
    verified: bool
    checks: dict = field(default_factory=dict)
    message: str = ""


@dataclass
class _Capture:
    session_id: str
    label: str
    consent_id: str | None
    guardian: bool
    consent_note: str
    replaces: bool = False
    shots: list = field(default_factory=list)   # (Angle, Embedding)

    def wipe(self) -> None:
        for _, e in self.shots:
            e.zero()
        self.shots.clear()


def _overwrite_unlink(p: Path) -> None:
    if p.exists():
        n = p.stat().st_size
        with open(p, "r+b") as f:
            f.write(os.urandom(max(n, 1))); f.flush(); os.fsync(f.fileno())
        p.unlink()


class FaceMatchModule:
    def __init__(self, db, keys, data_dir: str | Path, backend: Any, chain=None, cfg: FaceMatchConfig | None = None,
                 consents: ConsentRegistry | None = None, clock: Callable[[], float] = time.time,
                 timeout_s: float = 2.0, breaker_threshold: int = 5, breaker_cooldown_s: float = 30.0):
        self.cfg = (cfg or FaceMatchConfig()).validate()
        if getattr(backend, "test_only", False) and not self.cfg.allow_test_backend:
            raise FaceMatchLocked("the deterministic test backend is test-only")
        self.db, self.keys, self.chain, self.clock = db, keys, chain, clock
        db.execute("PRAGMA secure_delete=ON")   # deleted rows are zeroed in the file, not just unlinked
        self.data_dir = Path(data_dir).expanduser()
        self.consents = consents if consents is not None else ConsentRegistry(db)   # durable by default
        rec = opt_in_record(db)
        if rec is None:
            raise FaceMatchLocked("M-16 is off or not opted in; enable it with the typed opt-in first")
        self.modes = set(rec["modes"])
        self.strict = rec.get("jurisdiction", "strictest") in STRICT
        self.limits = QualityLimits()
        backend.open({"model_dir": self.cfg.model_dir or str(self.data_dir / "models" / "face_match")})
        self.backend = backend
        self.guard = Guarded(backend, timeout_s, breaker_threshold, breaker_cooldown_s)
        self._fk = Sealer(self._face_key(KEY_FILE, "face-template"))
        self._lk = Sealer(self._face_key(LOG_KEY_FILE, "face-log"))
        self._captures: dict[str, _Capture] = {}
        self._sessions: dict[str, set] = {}
        self._templates: list[Template] | None = None
        self._tpl_consent: dict[str, str | None] = {}
        self.consents.withdraw_hooks.append(self._on_consent_withdrawn)
        self._withdrawn_purged = 0
        self._purge_revoked()   # load-time: templates whose (persisted) consent is withdrawn/expired are erased
        self.stats = {"frames": 0, "matched": 0, "unrecognized": 0, "faces": 0}

    # ---- keys --------------------------------------------------------------------------
    def _face_key(self, fname: str, purpose: str) -> bytes:
        p = self.data_dir / fname
        wrap = Sealer(self.keys.subkey(purpose))
        aad = b"m16:" + purpose.encode()
        if p.exists():
            return wrap.open(p.read_bytes(), aad)
        k = Sealer.new_key()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(wrap.seal(k, aad)); os.chmod(tmp, 0o600); tmp.replace(p)
        return k

    def _dek(self, person_id: str, blob: bytes) -> Sealer:
        return Sealer(self._fk.open(blob, person_id.encode()))

    # ---- health ------------------------------------------------------------------------
    def health(self) -> tuple[Health, str]:
        return self.guard.health, self.guard.reason

    # ---- templates (RAM) ---------------------------------------------------------------
    def _consent_revoked(self, consent_id: str | None) -> bool:
        """Forge F3: True when a known consent record is withdrawn or expired. Templates enrolled under a
        recorded no-consent override (consent_id None) and ids this registry has never seen are kept;
        the registry is not persisted, so absence is not evidence of withdrawal."""
        if not consent_id:
            return False
        rec = self.consents.get(consent_id)
        if rec is None:
            return False
        try:
            self.consents.require(consent_id, "face_enrollment", now=self.clock())
        except ConsentError:
            return True
        return False

    def _purge_revoked(self) -> int:
        rows = self.db.execute("SELECT person_id, consent_id FROM fm_enrolled").fetchall()
        gone = [pid for pid, cid in rows if self._consent_revoked(cid)]
        for pid in gone:
            rep = self.delete_person(pid)   # same crypto-erase + verification path as a user deletion
            log_change(self.db, self.chain, "consent_withdrawn", {"templates_destroyed": 1, "verified": rep.verified})
        self._withdrawn_purged += len(gone)
        return len(gone)

    def consent_review(self) -> dict:
        """Templates whose consent ID has no record here are kept but listed for review."""
        missing = [{"person_id": pid, "consent_id": cid, "status": "consent record missing"}
                   for pid, cid in self.db.execute("SELECT person_id, consent_id FROM fm_enrolled ORDER BY enrolled_at")
                   if cid and not self.consents.known(cid)]
        return {"missing": missing, "withdrawn_purged": self._withdrawn_purged}

    def _on_consent_withdrawn(self, consent_id: str) -> None:
        try:
            self._purge_revoked()
        except Exception as e:  # noqa: BLE001 - a hook must not break the withdrawing caller
            log.error("purge after consent withdrawal failed: %s", e)
            self._drop_templates()

    def _load_templates(self) -> list[Template]:
        # Forge F3: consent is rechecked on every load/match, not only at enrollment.
        if self._templates is not None and any(self._consent_revoked(c) for c in self._tpl_consent.values()):
            self._purge_revoked()
        if self._templates is None:
            self._purge_revoked()
            out, cons = [], {}
            for pid, dek, tpl, mid, cid in self.db.execute(
                    "SELECT person_id, dek, template, model_id, consent_id FROM fm_enrolled"):
                if mid != self.backend.model_id:
                    continue   # a template is only valid with the model that made it
                vec = np.frombuffer(self._dek(pid, dek).open(tpl, b"tpl:" + pid.encode()), dtype=np.float32).copy()
                out.append(Template(pid, vec)); cons[pid] = cid
            self._templates, self._tpl_consent = out, cons
        return self._templates

    def _drop_templates(self) -> None:
        for t in self._templates or []:
            t.vec.fill(0)
        self._templates = None

    # ---- live processing (no output about anyone; review log only) ---------------------
    def _place(self, place: str | None, gps: tuple | None) -> str:
        if self.cfg.place_source == "gps_0.01" and gps:
            lat, lon = round_gps(gps[0], gps[1], 2)
            return f"{lat:.2f},{lon:.2f}"
        return check_text(place or "unnamed place")

    def process_frame(self, frame: Any, place: str | None = None, gps: tuple | None = None, now: float | None = None) -> dict:
        """Returns counts only. Never names, never an event, never a notification (spec 6)."""
        now = self.clock() if now is None else now
        self.stats["frames"] += 1
        ok, boxes = self.guard.call("detect", frame, self.guard.timeout_s,
                                    validate=lambda v: isinstance(v, list) and all(isinstance(b, FaceBox) for b in v))
        if not ok:
            return {"faces": 0, "matched": 0, "unrecognized": 0, "health": self.guard.health.value}
        where = self._place(place, gps)
        templates = self._load_templates() if "personal" in self.modes else []
        matched = unrec = 0
        for b in boxes:
            ok, e = self.guard.call("embed", frame, b, validate=lambda v: isinstance(v, Embedding) and v.valid())
            if not ok:
                continue
            try:
                m = None
                if templates:
                    ok, m = self.guard.call("compare", e, templates, validate=lambda v: v is None or (0.0 <= v.confidence <= 1.0))
                    m = m if ok else None
                if m is not None and m.confidence >= self.cfg.match_threshold:
                    self._log_encounter(m.person_id, m.confidence, where, now); matched += 1
                elif "research" in self.modes:
                    self._count_unrecognized(where, now); unrec += 1
            finally:
                e.zero()   # embeddings never outlive the frame cycle
        self.stats["faces"] += len(boxes); self.stats["matched"] += matched; self.stats["unrecognized"] += unrec
        return {"faces": len(boxes), "matched": matched, "unrecognized": unrec, "health": self.guard.health.value}

    def _log_encounter(self, person_id: str, conf: float, place: str, now: float) -> None:
        seen = round(now / 60) * 60
        exp = seen + self.cfg.encounter_retention_days * 86400
        self.db.execute("INSERT INTO fm_encounter(entry_id, person_id, seen_at, place, confidence, expires_at) VALUES(?,?,?,?,?,?)",
                        (uuid.uuid4().hex, person_id, seen, self._lk.seal(place.encode(), b"place"), round(conf, 4), exp))

    def _place_tag(self, place: str) -> str:
        import hashlib, hmac
        return hmac.new(self._lk_tag_key(), place.encode(), hashlib.sha256).hexdigest()[:24]

    def _lk_tag_key(self) -> bytes:
        return self.keys.subkey("face-log-tag")

    def _count_unrecognized(self, place: str, now: float) -> None:
        """Research mode: (place, date, time bucket) -> count. No face data of any kind."""
        b = self.cfg.time_bucket_minutes * 60
        bucket = int(now // b) * b
        date = time.strftime("%Y-%m-%d", time.gmtime(now))
        exp = bucket + self.cfg.encounter_retention_days * 86400
        tag = self._place_tag(place)
        cur = self.db.execute("UPDATE fm_unrecognized_count SET count = count + 1 WHERE place_tag=? AND date=? AND time_bucket=?",
                              (tag, date, bucket))
        if cur.rowcount == 0:
            self.db.execute("INSERT INTO fm_unrecognized_count(place_tag, place, date, time_bucket, count, expires_at) VALUES(?,?,?,?,1,?)",
                            (tag, self._lk.seal(place.encode(), b"place"), date, bucket, exp))

    # ---- enrollment (EnrollmentPort, spec 7.3) -----------------------------------------
    def _require_personal(self) -> None:
        if opt_in_record(self.db) is None:
            raise FaceMatchLocked("M-16 is off or not opted in")
        if "personal" not in self.modes:
            raise FaceMatchLocked("enrollment needs personal mode")

    def start_session(self) -> str:
        self._require_personal()
        sid = uuid.uuid4().hex
        self._sessions[sid] = set()
        return sid

    def add_person(self, session_id: str, label: str, consent_id: str | None = None, guardian: bool = False,
                   no_consent_override: bool = False, person_id: str | None = None) -> str:
        self._require_personal()
        if session_id not in self._sessions:
            raise KeyError("unknown session")
        label = check_text(label.strip())
        if not label:
            raise ValueError("give the person a name or label")
        # the previous person's buffer in this session is cleared when the next one starts
        for prev in list(self._sessions[session_id]):
            cap = self._captures.pop(prev, None)
            if cap:
                cap.wipe()   # an unfinished previous person is discarded, never mixed in
            self._sessions[session_id].discard(prev)
        must = self.cfg.require_enrollment_consent or self.strict or guardian
        note = "recorded"
        if consent_id is not None or must and not no_consent_override:
            rec = self.consents.require(consent_id, "face_enrollment")
            if guardian and "guardian" not in rec.scopes:
                raise ConsentError("a minor's enrollment needs the guardian's recorded agreement (scope 'guardian')")
        elif must and no_consent_override:
            if self.strict:
                raise ConsentError("your jurisdiction setting requires a consent record for enrollment")
            note = "none (user override)"
            log_change(self.db, self.chain, "consent_override", {"session": session_id})
        else:
            note = "none"
        pid = person_id or uuid.uuid4().hex
        self._captures[pid] = _Capture(session_id, label, consent_id, guardian, note, replaces=person_id is not None)
        self._sessions[session_id].add(pid)
        return pid

    def _cap(self, pid: str) -> _Capture:
        if pid not in self._captures:
            raise KeyError("person is not in an open capture")
        return self._captures[pid]

    def needed_angles(self, pid: str) -> set:
        have = {a for a, _ in self._cap(pid).shots}
        return {Angle(a) for a in self.cfg.enroll_required_angles} - have

    def submit_shot(self, pid: str, frame: Any, angle: Angle | str) -> ShotResult:
        self._require_personal()
        c, angle = self._cap(pid), Angle(angle)
        if len(c.shots) >= self.cfg.enroll_max_shots:
            return ShotResult(False, "enough", "enough shots for this person, finish to save", sorted(a.value for a in self.needed_angles(pid)))
        ok, boxes = self.guard.call("detect", frame, self.guard.timeout_s,
                                    validate=lambda v: isinstance(v, list) and all(isinstance(b, FaceBox) for b in v))
        if not ok:
            return ShotResult(False, "backend", "face engine unavailable, try again", sorted(a.value for a in self.needed_angles(pid)))
        good, code, reason = check_shot(frame, boxes, angle, self.limits)
        if good:
            ok, e = self.guard.call("embed", frame, boxes[0], validate=lambda v: isinstance(v, Embedding) and v.valid())
            if not ok:
                good, code, reason = False, "backend", "face engine unavailable, try again"
            else:
                c.shots.append((angle, e))
        return ShotResult(good, code, reason, sorted(a.value for a in self.needed_angles(pid)))

    def finish_person(self, pid: str, now: float | None = None) -> TemplateStatus:
        c = self._cap(pid)
        missing = sorted(a.value for a in self.needed_angles(pid))
        need = self.cfg.enroll_min_shots
        if missing or len(c.shots) < need:
            return TemplateStatus(False, missing, len(c.shots), need,
                                  f"still needed: {', '.join(missing) or 'more shots'} ({len(c.shots)}/{need} good shots)")
        check_persist("face_template", True, source="M-16", m16_enabled=True)
        vec = unit(np.mean([unit(e.vec) for _, e in c.shots], axis=0)).astype(np.float32)
        now = self.clock() if now is None else now
        if c.replaces:
            self._erase_person_key(pid)   # old template crypto-erased; encounter history kept
        dek_raw = Sealer.new_key()
        dek = Sealer(dek_raw)
        row = (pid, dek.seal(c.label.encode(), b"name:" + pid.encode()), dek.seal(vec.tobytes(), b"tpl:" + pid.encode()),
               self._fk.seal(dek_raw, pid.encode()), self.backend.model_id, self.backend.model_version, c.consent_id,
               c.consent_note, int(c.guardian), len(c.shots), ",".join(sorted({a.value for a, _ in c.shots})), now, None)
        self.db.execute("INSERT INTO fm_enrolled(person_id, display_name, template, dek, model_id, model_version, consent_id, consent_note, "
                        "guardian_enrolled, shot_count, angles_covered, enrolled_at, expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        vec.fill(0)
        n = len(c.shots)
        c.wipe(); del self._captures[pid]
        self._sessions.get(c.session_id, set()).discard(pid)
        self._drop_templates()
        log_change(self.db, self.chain, "reenrolled" if c.replaces else "enrolled", {"shots": n})
        return TemplateStatus(True, [], n, need, f"Template complete for {c.label}")

    def end_session(self, session_id: str) -> None:
        for pid in self._sessions.pop(session_id, set()):
            cap = self._captures.pop(pid, None)
            if cap:
                cap.wipe()

    def capture_buffer_size(self) -> int:
        return sum(len(c.shots) for c in self._captures.values())

    def reenroll(self, pid: str) -> str:
        self._require_personal()
        if self.db.execute("SELECT 1 FROM fm_enrolled WHERE person_id=?", (pid,)).fetchone() is None:
            raise KeyError("unknown person")
        label, consent_id, guardian = self._person_meta(pid)
        sid = self.start_session()
        self._captures[pid] = _Capture(sid, label, consent_id, guardian, "recorded" if consent_id else "none", replaces=True)
        self._sessions[sid].add(pid)
        return sid

    def _person_meta(self, pid: str) -> tuple[str, str | None, bool]:
        dek, name, consent_id, guardian = self.db.execute(
            "SELECT dek, display_name, consent_id, guardian_enrolled FROM fm_enrolled WHERE person_id=?", (pid,)).fetchone()
        return self._dek(pid, dek).open(name, b"name:" + pid.encode()).decode(), consent_id, bool(guardian)

    def _erase_person_key(self, pid: str) -> None:
        self.db.execute("DELETE FROM fm_enrolled WHERE person_id=?", (pid,))
        self._drop_templates()

    def delete_person(self, pid: str, keep_history: bool = False) -> WipeReport:
        row = self.db.execute("SELECT template FROM fm_enrolled WHERE person_id=?", (pid,)).fetchone()
        if row is None:
            raise KeyError("unknown person")
        old_tpl = row[0]
        self._erase_person_key(pid)
        if not keep_history:
            self.db.execute("DELETE FROM fm_encounter WHERE person_id=?", (pid,))
        self._compact()
        gone = self.db.execute("SELECT 1 FROM fm_enrolled WHERE person_id=?", (pid,)).fetchone() is None
        undecryptable = not self._can_open_with_any(old_tpl, b"tpl:" + pid.encode())
        absent = not self._bytes_on_disk(old_tpl)
        ok = gone and undecryptable and absent
        log_change(self.db, self.chain, "person_deleted", {"templates_destroyed": 1, "verified": ok})
        return WipeReport(1, ok, {"row_absent": gone, "undecryptable": undecryptable, "ciphertext_absent": absent},
                          "1 template destroyed, verified" if ok else "wipe NOT verified")

    def _compact(self) -> None:
        self.db.execute("VACUUM")
        if self.db.path != ":memory:":
            self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def _bytes_on_disk(self, blob: bytes) -> bool:
        if self.db.path == ":memory:":
            return False
        for suffix in ("", "-wal", "-journal"):
            p = Path(self.db.path + suffix)
            if p.exists() and blob in p.read_bytes():
                return True
        return False

    def _candidate_keys(self) -> list[bytes]:
        """Every key still reachable from what is stored on this device."""
        ks: list[bytes] = []
        for purpose in ("face-template", "face-log", "face-log-tag"):
            try:
                ks.append(self.keys.subkey(purpose))
            except Exception:  # noqa: BLE001 - locked/erased key store
                pass
        try:
            ks.append(self.keys.master)
        except Exception:  # noqa: BLE001
            pass
        face_keys = []
        for f, purpose in ((KEY_FILE, "face-template"), (LOG_KEY_FILE, "face-log")):
            p = self.data_dir / f
            if p.exists():
                try:
                    face_keys.append(Sealer(self.keys.subkey(purpose)).open(p.read_bytes(), b"m16:" + purpose.encode()))
                except Exception:  # noqa: BLE001
                    pass
        ks += face_keys
        for pid, dek in self.db.execute("SELECT person_id, dek FROM fm_enrolled").fetchall():
            for fk in face_keys:
                try:
                    ks.append(Sealer(fk).open(dek, pid.encode()))
                except Exception:  # noqa: BLE001
                    pass
        return ks

    def _can_open_with_any(self, blob: bytes, aad: bytes) -> bool:
        for k in self._candidate_keys():
            try:
                Sealer(k).open(blob, aad)
                return True
            except Exception:  # noqa: BLE001
                pass
        return False

    # ---- review log --------------------------------------------------------------------
    def _open_place(self, blob: bytes) -> str:
        return self._lk.open(blob, b"place").decode()

    def review_log(self, days: int | None = None, now: float | None = None) -> dict:
        now = self.clock() if now is None else now
        since = now - (days or self.cfg.encounter_retention_days) * 86400
        people = []
        for pid, dek, name, consent_note, guardian, enrolled_at in self.db.execute(
                "SELECT person_id, dek, display_name, consent_note, guardian_enrolled, enrolled_at FROM fm_enrolled ORDER BY enrolled_at").fetchall():
            nm = self._dek(pid, dek).open(name, b"name:" + pid.encode()).decode()
            places: dict[str, int] = {}
            entries = []
            for eid, seen, place, conf in self.db.execute(
                    "SELECT entry_id, seen_at, place, confidence FROM fm_encounter WHERE person_id=? AND seen_at>=? ORDER BY seen_at",
                    (pid, since)).fetchall():
                pl = self._open_place(place)
                places[pl] = places.get(pl, 0) + 1
                entries.append({"entry_id": eid, "seen_at": seen, "place": pl, "confidence": conf})
            summary = [f"{nm}: possible match at {pl}, {n} time{'s' if n != 1 else ''} in the last {days or self.cfg.encounter_retention_days} days"
                       for pl, n in sorted(places.items())]
            people.append({"person_id": pid, "name": nm, "consent": consent_note, "guardian_enrolled": bool(guardian),
                           "no_consent_badge": consent_note != "recorded", "hint": HINT if self._weaker(pid, enrolled_at) else "",
                           "summary": summary, "entries": entries})
        counts = [{"place": self._open_place(p), "date": d, "time_bucket": tb, "count": c}
                  for p, d, tb, c in self.db.execute(
                      "SELECT place, date, time_bucket, count FROM fm_unrecognized_count WHERE time_bucket>=? ORDER BY time_bucket", (since,)).fetchall()]
        out = {"people": people, "unrecognized_counts": counts}
        return check_output(out)

    def _weaker(self, pid: str, enrolled_at: float) -> bool:
        confs = [r[0] for r in self.db.execute("SELECT confidence FROM fm_encounter WHERE person_id=? ORDER BY seen_at", (pid,))]
        n = self.cfg.reenroll_window_matches
        if len(confs) < n:
            return False
        first_week = [c for (c,) in self.db.execute("SELECT confidence FROM fm_encounter WHERE person_id=? AND seen_at<?",
                                                     (pid, enrolled_at + 7 * 86400))]
        recent = statistics.median(confs[-n:])
        if first_week and recent <= statistics.median(first_week) - self.cfg.reenroll_confidence_drop:
            return True
        return recent < self.cfg.match_threshold + REENROLL_MARGIN

    def delete_entry(self, entry_id: str) -> bool:
        n = self.db.execute("DELETE FROM fm_encounter WHERE entry_id=?", (entry_id,)).rowcount
        if n:
            log_change(self.db, self.chain, "entry_deleted", {"entries": n})
        return bool(n)

    def export_log(self, explicit_user_action: bool = False) -> dict:
        """Encounter logs/counts only, by explicit per-export action. Templates: never."""
        if not (self.cfg.allow_log_export and explicit_user_action):
            raise ExportBlocked("log export is off; enable allow_log_export and confirm the export")
        log = self.review_log()
        for p in log["people"]:
            p.pop("person_id", None)
        log_change(self.db, self.chain, "log_exported", {"people": len(log["people"])})
        return log

    def purge_expired(self, now: float | None = None) -> int:
        return purge(self.db, self.clock() if now is None else now)

    # ---- disable + verified wipe (spec 14) ---------------------------------------------
    def disable(self, keep_logs: bool = False) -> WipeReport:
        self._drop_templates()
        for c in self._captures.values():
            c.wipe()
        self._captures.clear(); self._sessions.clear()
        try:
            self.backend.close()
        except Exception:  # noqa: BLE001
            pass
        sample = self.db.execute("SELECT person_id, dek, template FROM fm_enrolled").fetchall()
        n = len(sample)
        _overwrite_unlink(self.data_dir / KEY_FILE)
        self.db.execute("DELETE FROM fm_enrolled")
        if not keep_logs:
            self.db.execute("DELETE FROM fm_encounter")
            self.db.execute("DELETE FROM fm_unrecognized_count")
            _overwrite_unlink(self.data_dir / LOG_KEY_FILE)
        self.db.execute("DELETE FROM fm_state WHERE k='opt_in'")
        self._compact()
        rows = self.db.execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0]
        undecryptable = all(not self._can_open_with_any(t, b"tpl:" + pid.encode()) and not self._can_open_with_any(d, pid.encode())
                            for pid, d, t in sample)
        absent = not any(self._bytes_on_disk(t) for _, _, t in sample)
        key_gone = not (self.data_dir / KEY_FILE).exists()
        ok = rows == 0 and undecryptable and absent and key_gone
        log_change(self.db, self.chain, "disabled_wiped", {"templates_destroyed": n, "verified": ok, "logs_kept": keep_logs})
        self._fk = self._lk = None  # type: ignore[assignment]
        self.modes = set()
        return WipeReport(n, ok, {"rows": rows, "undecryptable": undecryptable, "ciphertext_absent": absent, "key_file_absent": key_gone},
                          f"{n} templates destroyed, verified" if ok else "wipe NOT verified")


def purge(db, now: float) -> int:
    """Retention (ADR-0039): expired encounters/counts, and templates past a set end date."""
    n = 0
    for t in ("fm_encounter", "fm_unrecognized_count"):
        if db.has_table(t):
            n += db.execute(f"DELETE FROM {t} WHERE expires_at < ?", (now,)).rowcount
    if db.has_table("fm_enrolled"):
        ids = [r[0] for r in db.execute("SELECT person_id FROM fm_enrolled WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))]
        for pid in ids:
            db.execute("DELETE FROM fm_encounter WHERE person_id=?", (pid,))
        n += db.execute("DELETE FROM fm_enrolled WHERE expires_at IS NOT NULL AND expires_at < ?", (now,)).rowcount
    return n


def disabled_wipe_without_module(db, data_dir: str | Path) -> int:
    """Used when the flag is turned off while the module isn't loaded (e.g. CLI/config):
    same destruction, no backend needed."""
    d = Path(data_dir).expanduser()
    n = db.execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0] if db.has_table("fm_enrolled") else 0
    _overwrite_unlink(d / KEY_FILE); _overwrite_unlink(d / LOG_KEY_FILE)
    for t in ("fm_enrolled", "fm_encounter", "fm_unrecognized_count"):
        if db.has_table(t):
            db.execute(f"DELETE FROM {t}")
    if db.has_table("fm_state"):
        db.execute("DELETE FROM fm_state WHERE k='opt_in'")
    db.execute("VACUUM")
    if db.path != ":memory:":
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return n


__all__ = ["FaceMatchModule", "FaceMatchConfig", "FaceMatchLocked", "ExportBlocked", "ShotResult", "WipeReport",
           "OptInError", "purge"]


def consent_review_db(db) -> list[dict]:
    """Status helper without loading templates: enrolled people whose consent record is missing."""
    known = {r[0] for r in db.execute("SELECT consent_id FROM consent_record")}
    return [{"person_id": pid, "consent_id": cid, "status": "consent record missing"}
            for pid, cid in db.execute("SELECT person_id, consent_id FROM fm_enrolled ORDER BY enrolled_at")
            if cid and cid not in known]
