"""Opt-in (spec section 5): typed confirmation, plain-language warning, record in the
tamper-evident log. Every enable / disable / mode change is logged the same way."""
from __future__ import annotations
import json, time

from ...guard.vocabulary import check_text

CONFIRM_PHRASE = "I UNDERSTAND"
WARNING_VERSION = "v1"
WARNING_TEXT = """Face matching is about to be turned on.
- In personal mode, this device will store a mathematical map of each face you enroll (a "face template"). That is biometric data. It stays on this device, encrypted.
- The camera will look at every face it sees, including people who never agreed to be scanned and don't know this device exists. Personal mode only matches people you enrolled; everyone else is ignored or, in research mode, counted anonymously.
- In research mode, it keeps a count of unknown faces by time and place. It does not store their faces and cannot tell if it saw the same stranger twice.
- Laws in some places (for example Illinois, Texas, Washington, the EU/UK, California) restrict collecting face data, sometimes with heavy penalties. Biometric and recording laws vary by place, and compliance is your responsibility. Whether to use this, and how, is your decision and your risk.
- It will never alert you, block anyone, or follow anyone. It only keeps a log you can review and delete.
- You can turn it off any time. Turning it off permanently deletes all stored face templates."""  # noqa: E501 - verbatim spec 5.3 text
check_text(WARNING_TEXT)

MODES = ("personal", "research")
# Jurisdiction profiles are informational: strict ones force enrollment consent and add a
# stronger warning; none of them ever blocks research mode (ADR-0050).
STRICT = {"strictest", "us-il", "us-tx", "us-wa", "eu", "uk"}
JURISDICTIONS = STRICT | {"us-ca", "us-other", "other"}
STRICT_NOTE = ("Your jurisdiction setting has strict biometric rules: a consent record is required for every "
               "enrolled person. Research mode is still your decision.")


class OptInError(PermissionError):
    pass


def opt_in_record(db) -> dict | None:
    r = db.execute("SELECT v FROM fm_state WHERE k='opt_in'").fetchone()
    return json.loads(r[0]) if r else None


def log_change(db, chain, kind: str, detail: dict) -> None:
    rec = {"module": "M-16", "kind": kind, "t_wall": round(time.time(), 3), **detail}
    if chain is not None:
        chain.append(rec)
    if not isinstance(chain, DbChain):
        db.audit(f"face_match.{kind}", rec)


def warning_for(jurisdiction: str) -> str:
    return WARNING_TEXT + ("\n\n" + STRICT_NOTE if jurisdiction in STRICT else "")


def record_opt_in(db, chain, typed: str, modes: list[str], device_id: str, jurisdiction: str = "strictest",
                  warning_shown: str | None = None) -> dict:
    if typed.strip() != CONFIRM_PHRASE:
        raise OptInError(f'type "{CONFIRM_PHRASE}" to turn face matching on')
    if warning_shown is None or WARNING_TEXT not in warning_shown:
        raise OptInError("the full warning must be shown before opting in")
    bad = [m for m in modes if m not in MODES]
    if bad or not modes:
        raise OptInError(f"modes must be a non-empty subset of {MODES}")
    if jurisdiction not in JURISDICTIONS:
        jurisdiction = "strictest"   # unknown -> strictest (ETHICS.md)
    rec = {"modes": sorted(set(modes)), "warning_version": WARNING_VERSION, "device_id": device_id,
           "jurisdiction": jurisdiction, "t_wall": round(time.time(), 3)}
    db.execute("INSERT OR REPLACE INTO fm_state(k, v) VALUES('opt_in', ?)", (json.dumps(rec),))
    log_change(db, chain, "opt_in", rec)
    return rec


def set_modes(db, chain, modes: list[str]) -> dict:
    rec = opt_in_record(db)
    if rec is None:
        raise OptInError("M-16 is not opted in")
    if not modes or any(m not in MODES for m in modes):
        raise OptInError(f"modes must be a non-empty subset of {MODES}")
    rec["modes"] = sorted(set(modes))
    db.execute("INSERT OR REPLACE INTO fm_state(k, v) VALUES('opt_in', ?)", (json.dumps(rec),))
    log_change(db, chain, "mode_change", {"modes": rec["modes"]})
    return rec


class DbChain:
    """Tamper-evident M-16 change log persisted in audit_log (ADR-0024 scheme):
    h_i = HMAC-SHA256(k, h_{i-1} || canonical(record_i)); head kept in fm_state."""

    def __init__(self, db, key: bytes):
        self.db, self.key = db, key

    def _head(self) -> bytes:
        r = self.db.execute("SELECT v FROM fm_state WHERE k='chain_head'").fetchone()
        return bytes.fromhex(r[0]) if r else b"\x00" * 32

    def append(self, rec: dict) -> bytes:
        import hashlib, hmac
        from ...security.hashchain import canonical
        h = hmac.new(self.key, self._head() + canonical(rec), hashlib.sha256).digest()
        self.db.execute("INSERT INTO audit_log(t_wall,kind,detail) VALUES(?,?,?)",
                        (time.time(), "face_match.chain", json.dumps({"rec": rec, "h": h.hex()}, sort_keys=True)))
        self.db.execute("INSERT OR REPLACE INTO fm_state(k, v) VALUES('chain_head', ?)", (h.hex(),))
        return h

    def verify(self) -> int:
        import hashlib, hmac
        from ...security.ct import equal
        from ...security.hashchain import ChainInvalid, canonical
        prev, n = b"\x00" * 32, 0
        for (detail,) in self.db.execute("SELECT detail FROM audit_log WHERE kind='face_match.chain' ORDER BY id"):
            d = json.loads(detail)
            exp = hmac.new(self.key, prev + canonical(d["rec"]), hashlib.sha256).digest()
            if not equal(exp, bytes.fromhex(d["h"])):
                raise ChainInvalid(f"M-16 log entry {n + 1} does not chain")
            prev, n = exp, n + 1
        if n and not equal(prev, self._head()):
            raise ChainInvalid("M-16 log truncated")
        return n

    def records(self) -> list[dict]:
        return [json.loads(d)["rec"] for (d,) in self.db.execute("SELECT detail FROM audit_log WHERE kind='face_match.chain' ORDER BY id")]
