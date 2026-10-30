"""`oiris face-match ...`: opt-in, guided enrollment, review log, deletes, disable + wipe.
Only reached through an explicit `face-match` command; normal runs never import M-16.

  oiris face-match status
  oiris face-match enable --mode personal [--mode research] [--jurisdiction us-ky]
  oiris face-match fetch-models
  oiris face-match enroll [--camera 0]          guided capture, as many people as you like
  oiris face-match review
  oiris face-match delete-entry --id ENTRY | delete-person --id PERSON
  oiris face-match disable [--keep-logs]        wipes every face template, verified
"""
from __future__ import annotations
import getpass, json, os, sys, uuid
from pathlib import Path
from typing import Any, Callable

from .config import Config


def _ctx(cfg: Config):
    from .security.keys import KeyStore
    from .store.db import DB
    from .modules.face_match.optin import DbChain
    d = Path(cfg.data_dir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    ks = KeyStore(d / "keys.json")
    pw = os.environ.get("OIRIS_PASSPHRASE") or getpass.getpass("O Iris passphrase: ")
    ks.unlock(pw) if ks.exists() else ks.create(pw)
    db = DB(d / "asb.db", ks.subkey("db"))
    return d, ks, db, DbChain(db, ks.subkey("face-chain"))


def _save_flag(cfg_path: Path, cfg: Config, on: bool, modes: list[str] | None = None, jurisdiction: str | None = None) -> None:
    raw = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    raw.setdefault("flags", {})["M-16"] = on
    fm = raw.setdefault("face_match", {})
    if modes is not None:
        fm["modes"] = modes
    if jurisdiction:
        fm["jurisdiction"] = jurisdiction
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(raw, indent=1), encoding="utf-8")


def _ticks(needed: set, order: list[str]) -> str:
    return "  ".join(f"[{' ' if a in needed else 'x'}] {a}" for a in order)


def run(a, cfg: Config, cfg_path: Path, inp: Callable[[str], str] = input, out=print, backend: Any = None) -> int:
    from .modules.face_match import optin
    sub = a.sub or "status"
    if sub == "fetch-models":
        from .modules.face_match.backends.opencv_zoo import MODELS, fetch_models
        md = cfg.face_match.get("model_dir") or str(Path(cfg.data_dir).expanduser() / "models" / "face_match")
        out("Downloading face models (YuNet: MIT, SFace: Apache-2.0; see THIRD_PARTY.md) to " + md)
        for k, p in fetch_models(md).items():
            out(f"  {k}: {p.name} ({MODELS[k]['license']}) sha256 ok")
        return 0
    d, ks, db, chain = _ctx(cfg)
    try:
        if sub == "status":
            rec = optin.opt_in_record(db)
            from .modules.face_match.core import consent_review_db
            out(json.dumps({"flag_on": cfg.enabled("M-16"), "opted_in": rec is not None, "opt_in": rec,
                            "log_entries": chain.verify(), "consent_review": consent_review_db(db)}, indent=1))
            return 0
        if sub == "enable":
            modes = a.mode or ["personal"]
            jur = a.jurisdiction or "strictest"
            text = optin.warning_for(jur)
            out(text)
            typed = inp(f'\nType "{optin.CONFIRM_PHRASE}" to turn face matching on: ')
            rec = optin.record_opt_in(db, chain, typed, modes, device_id=uuid.uuid5(uuid.NAMESPACE_URL, str(d)).hex[:12],
                                      jurisdiction=jur, warning_shown=text)
            _save_flag(cfg_path, cfg, True, rec["modes"], rec["jurisdiction"])
            out(f"Face matching is on ({', '.join(rec['modes'])}). Logged. Turn it off any time: oiris face-match disable")
            return 0
        if sub == "disable":
            from .modules.face_match.core import disabled_wipe_without_module
            n = disabled_wipe_without_module(db, d)
            ok = db.execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0] == 0 and not (d / "face_match.key").exists()
            optin.log_change(db, chain, "disabled_wiped", {"templates_destroyed": n, "verified": ok, "logs_kept": False})
            _save_flag(cfg_path, cfg, False)
            out(f"Face matching is off. {n} templates destroyed, {'verified' if ok else 'NOT verified'}.")
            return 0 if ok else 1
        from .modules import face_match_gate
        from .registry import default_registry
        cfg = Config.load(cfg_path) if cfg_path.exists() else cfg
        m = face_match_gate.load(cfg, db, ks, default_registry(cfg.plugins), chain=chain, backend=backend)
        if m is None:
            out("Face matching is off. Turn it on first: oiris face-match enable"); return 2
        if sub == "review":
            log = m.review_log()
            for p in log["people"]:
                badge = " [no consent recorded]" if p["no_consent_badge"] else ""
                out(f"{p['name']}{badge} (id {p['person_id'][:8]}) {p['hint']}")
                for line in p["summary"]:
                    out("  " + line)
                for e in p["entries"]:
                    out(f"    entry {e['entry_id']}  {e['place']}  confidence {e['confidence']:.2f}")
            for c in log["unrecognized_counts"]:
                out(f"unrecognized faces: {c['count']} at {c['place']} on {c['date']}")
            return 0
        if sub == "delete-entry":
            out("deleted" if m.delete_entry(a.id) else "no such entry"); return 0
        if sub == "delete-person":
            pid = next((r[0] for r in db.execute("SELECT person_id FROM fm_enrolled") if r[0].startswith(a.id or "?")), None)
            if pid is None:
                out("no such person"); return 1
            out(m.delete_person(pid).message); return 0
        if sub == "enroll":
            return _enroll(m, a, inp, out)
        out(f"unknown face-match command {sub}"); return 2
    finally:
        db.close()


def _enroll(m, a, inp, out) -> int:
    """Guided capture (spec 7.3). No limit on people: keep going until you say stop."""
    order = list(m.cfg.enroll_required_angles)
    grab = _camera(a.camera) if a.camera is not None else _file_reader()
    sid = m.start_session()
    try:
        while True:
            name = inp("Name or label for this person (blank to stop): ").strip()
            if not name:
                break
            cid = inp("Consent record ID (blank = none recorded): ").strip() or None
            pid = m.add_person(sid, name, cid, guardian=inp("Enrolling a minor as their guardian? [y/N] ").lower() == "y",
                               no_consent_override=cid is None)
            while True:
                need = m.needed_angles(pid)
                out(_ticks(need, order))
                st = m.finish_person(pid) if not need and len(m._captures[pid].shots) >= m.cfg.enroll_min_shots else None
                if st and st.complete:
                    out(st.message); break
                angle = sorted(need, key=lambda x: order.index(x.value))[0].value if need else order[0]
                frame = grab(f"Look {angle.upper()} and hold still. ")
                if frame is None:
                    out("capture cancelled for this person; nothing saved"); break
                r = m.submit_shot(pid, frame, angle)
                out("  ok" if r.ok else f"  rejected: {r.reason}")
    finally:
        m.end_session(sid)
    return 0


def _file_reader():
    def grab(prompt: str):
        import cv2
        p = input(prompt + "Image path (blank to cancel): ").strip()
        return cv2.imread(p) if p else None
    return grab


def _camera(index: int):
    def grab(prompt: str):
        import cv2
        if input(prompt + "Press Enter to capture (q to cancel) ").strip().lower() == "q":
            return None
        cap = cv2.VideoCapture(index)
        try:
            ok, frame = cap.read()
            return frame if ok else None
        finally:
            cap.release()
    return grab


if __name__ == "__main__":  # pragma: no cover
    sys.exit(1)
