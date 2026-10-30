"""M-16 face matching (spec section 15). Uses the TEST-ONLY deterministic backend on
synthetic frames (no real faces); the real OpenCV backend test skips if weights are absent."""
import json, os, re, subprocess, sys, time
from pathlib import Path

import numpy as np
import pytest
from nacl.signing import SigningKey

from oiris.config import Config, validate_face_match
from oiris.guard.consent import ConsentError, ConsentRecord, ConsentRegistry
from oiris.guard.privacy import PrivacyError, check_persist
from oiris.guard.retention import purge as nightly_purge
from oiris.guard.vocabulary import VocabularyViolation, check_output, check_text
from oiris.modules.face_match import optin
from oiris.modules.face_match.backends.test_deterministic import TestDeterministicBackend, synth_face_frame
from oiris.modules.face_match.core import ExportBlocked, FaceMatchConfig, FaceMatchLocked, FaceMatchModule
from oiris.modules.face_match.port import REQUIRED_ANGLES, Angle
from oiris.security.aead import Sealer
from oiris.security.hashchain import HashChain, verify
from oiris.security.keys import KeyStore
from oiris.store.db import DB

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path):
    ks = KeyStore(tmp_path / "keys.json"); ks.create("pw")
    db = DB(tmp_path / "asb.db", ks.subkey("db"))
    sk = SigningKey.generate()
    chain = HashChain(ks.subkey("face-chain"), sk)
    consents = ConsentRegistry()
    consents.add(ConsentRecord("c-ok", "s1", {"face_enrollment"}))
    consents.add(ConsentRecord("c-guardian", "s2", {"face_enrollment", "guardian"}))
    yield {"ks": ks, "db": db, "chain": chain, "sk": sk, "consents": consents, "dir": tmp_path}
    db.close()


def opt_in(env, modes=("personal",), jurisdiction="us-other"):
    return optin.record_opt_in(env["db"], env["chain"], "I UNDERSTAND", list(modes), "dev1", jurisdiction,
                               warning_shown=optin.warning_for(jurisdiction))


def make(env, modes=("personal",), jurisdiction="us-other", **cfg):
    opt_in(env, modes, jurisdiction)
    c = FaceMatchConfig(modes=list(modes), allow_test_backend=True, **cfg)
    return FaceMatchModule(env["db"], env["ks"], env["dir"], TestDeterministicBackend(), env["chain"], c, env["consents"],
                           timeout_s=1.0, breaker_threshold=3, breaker_cooldown_s=60)


def enroll(m, sid, seed, name="Alex", consent="c-ok", **kw):
    pid = m.add_person(sid, name, consent, **kw)
    for a in REQUIRED_ANGLES:
        assert m.submit_shot(pid, synth_face_frame(seed, a, noise_seed=hash(a.value) % 97), a).ok
    st = m.finish_person(pid)
    assert st.complete, st.message
    return pid


# ---- default off / opt-in ----------------------------------------------------------------
def test_default_off_not_imported_and_no_port_instance():
    code = ("import sys; from oiris.config import Config; from oiris.engine import Engine; from oiris.headless import run_scenario;"
            "c=Config(); assert not c.enabled('M-16'); e=Engine(c); assert e.face_match is None;"
            "run_scenario('quiet',1,config=c);"
            "from oiris.modules import face_match_gate; assert face_match_gate.load(c,None,None,None) is None;"
            "assert not any(k.startswith('oiris.modules.face_match.') or k=='oiris.modules.face_match' for k in sys.modules), "
            "[k for k in sys.modules if 'face_match.' in k]")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr


def test_m16_flag_default_off_and_not_locked():
    from oiris.config import DEFAULT_OFF, LOCKED_ON, MODULES
    assert MODULES["M-16"] == "face_match" and "M-16" in DEFAULT_OFF and "M-16" not in LOCKED_ON
    c = Config(); c.flags["M-16"] = True; c.validate()
    assert c.enabled("M-16")


def test_optin_requires_typed_phrase_and_warning(env):
    db, chain = env["db"], env["chain"]
    for typed in ("", "yes", "i understand please", "OK"):
        with pytest.raises(optin.OptInError):
            optin.record_opt_in(db, chain, typed, ["personal"], "d", warning_shown=optin.WARNING_TEXT)
    with pytest.raises(optin.OptInError):
        optin.record_opt_in(db, chain, "I UNDERSTAND", ["personal"], "d", warning_shown="short")
    assert optin.opt_in_record(db) is None and len(chain.entries) == 0
    rec = opt_in(env)
    assert rec["warning_version"] == "v1" and chain.entries[-1][0]["kind"] == "opt_in"
    assert verify(chain.entries, chain.key, chain.anchors, env["sk"].verify_key) == 1


def test_module_and_enrollment_locked_without_optin(env):
    with pytest.raises(FaceMatchLocked):
        FaceMatchModule(env["db"], env["ks"], env["dir"], TestDeterministicBackend(), env["chain"],
                        FaceMatchConfig(modes=["personal"], allow_test_backend=True))


def test_test_backend_refused_outside_tests(env):
    opt_in(env)
    with pytest.raises(FaceMatchLocked):
        FaceMatchModule(env["db"], env["ks"], env["dir"], TestDeterministicBackend(), env["chain"], FaceMatchConfig(modes=["personal"]))
    assert validate_face_match({"allow_test_backend": True})


def test_research_mode_unlocks_on_optin_in_any_jurisdiction(env):
    m = make(env, ("research",), jurisdiction="us-il")
    assert m.process_frame(synth_face_frame(5), place="Store")["unrecognized"] == 1


def test_mode_changes_and_db_chain_are_tamper_evident(env):
    chain = optin.DbChain(env["db"], env["ks"].subkey("face-chain"))
    optin.record_opt_in(env["db"], chain, "I UNDERSTAND", ["personal"], "d", warning_shown=optin.WARNING_TEXT)
    optin.set_modes(env["db"], chain, ["personal", "research"])
    assert chain.verify() == 2 and [r["kind"] for r in chain.records()] == ["opt_in", "mode_change"]
    env["db"].execute("UPDATE audit_log SET detail=replace(detail,'research','persona') WHERE kind='face_match.chain'")
    with pytest.raises(Exception):
        chain.verify()


# ---- enrollment ----------------------------------------------------------------------------
def test_guided_capture_reports_missing_angles(env):
    m = make(env)
    sid = m.start_session(); pid = m.add_person(sid, "Mom", "c-ok")
    assert m.needed_angles(pid) == set(REQUIRED_ANGLES)
    for a in (Angle.FRONT, Angle.LEFT):
        r = m.submit_shot(pid, synth_face_frame(1, a), a)
        assert r.ok
    assert set(r.needed_angles) == {"right", "up", "down"}
    st = m.finish_person(pid)
    assert not st.complete and set(st.missing_angles) == {"right", "up", "down"}
    assert m.db.execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0] == 0


def test_template_needs_min_five_good_shots_and_max_ten(env):
    m = make(env, enroll_required_angles=["front", "left"])
    sid = m.start_session(); pid = m.add_person(sid, "Coach", "c-ok")
    for i in range(4):
        assert m.submit_shot(pid, synth_face_frame(2, Angle.FRONT if i % 2 else Angle.LEFT, noise_seed=i), Angle.FRONT if i % 2 else Angle.LEFT).ok
    st = m.finish_person(pid)
    assert not st.complete and st.good_shots == 4
    for i in range(6):
        assert m.submit_shot(pid, synth_face_frame(2, Angle.FRONT, noise_seed=10 + i), Angle.FRONT).ok
    r = m.submit_shot(pid, synth_face_frame(2, Angle.FRONT, noise_seed=99), Angle.FRONT)
    assert not r.ok and r.code == "enough"
    assert m.finish_person(pid).complete


@pytest.mark.parametrize("frame_kw,want,code", [
    ({"blur": True}, Angle.FRONT, "blur"),
    ({"brightness": 0.2}, Angle.FRONT, "dark"),
    ({"size": 32}, Angle.FRONT, "size"),
    ({"extra_faces": [(77, (100, 100))], "size": 48, "at": (2, 2)}, Angle.FRONT, "faces_many"),
    ({}, Angle.LEFT, "angle"),
])
def test_shot_quality_rejections(env, frame_kw, want, code):
    m = make(env)
    sid = m.start_session(); pid = m.add_person(sid, "Alex", "c-ok")
    r = m.submit_shot(pid, synth_face_frame(3, Angle.FRONT, **frame_kw), want)
    assert not r.ok and r.code == code and r.reason
    assert m.capture_buffer_size() == 0
    r = m.submit_shot(pid, np.zeros((160, 160), np.uint8), Angle.FRONT)
    assert r.code == "faces_none"


def test_no_enrollment_cap_hundreds_of_people(env):
    m = make(env)
    n = 300
    sid = m.start_session()
    pids = [enroll(m, sid, 1000 + i, f"Person {i}") for i in range(n // 2)]
    m.end_session(sid)
    sid2 = m.start_session()
    pids += [enroll(m, sid2, 1000 + i, f"Person {i}") for i in range(n // 2, n)]
    m.end_session(sid2)
    assert m.db.execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0] == n
    for i in (0, 77, 149, 150, 299):
        before = m.db.execute("SELECT COUNT(*) FROM fm_encounter WHERE person_id=?", (pids[i],)).fetchone()[0]
        assert m.process_frame(synth_face_frame(1000 + i, noise_seed=5), place="Park")["matched"] == 1
        assert m.db.execute("SELECT COUNT(*) FROM fm_encounter WHERE person_id=?", (pids[i],)).fetchone()[0] == before + 1


def test_no_max_people_constant_in_code_or_config():
    src = "\n".join(p.read_text() for p in (ROOT / "oiris/modules/face_match").rglob("*.py"))
    src += (ROOT / "oiris/config.py").read_text() + (ROOT / "oiris/face_match_cli.py").read_text()
    assert not re.search(r"max_(people|persons|enrolled|enrollments)|people_limit|enroll(ment)?_(cap|limit)|enrollment[ _]full", src, re.I)
    assert not [k for k in FaceMatchConfig.__dataclass_fields__ if re.search("people|persons|enrolled", k)]


def test_template_isolation_multi_person_session(env):
    m = make(env)
    sid = m.start_session()
    a = enroll(m, sid, 11, "Kid A")
    assert m.capture_buffer_size() == 0
    b = enroll(m, sid, 12, "Kid B")
    # an unfinished person's buffer is discarded when the next person starts
    c = m.add_person(sid, "Kid C", "c-ok"); m.submit_shot(c, synth_face_frame(13), Angle.FRONT)
    assert m.capture_buffer_size() == 1
    d = m.add_person(sid, "Kid D", "c-ok")
    assert m.capture_buffer_size() == 0 and c not in m._captures
    m.submit_shot(d, synth_face_frame(14), Angle.FRONT)
    m.end_session(sid)
    assert m.capture_buffer_size() == 0
    t = {x.person_id: x.vec for x in m._load_templates()}
    ea = TestDeterministicBackend().embed(synth_face_frame(11), TestDeterministicBackend().detect(synth_face_frame(11), 1)[0])
    assert float(np.dot(t[a], ea.vec)) > 0.95 and float(np.dot(t[b], ea.vec)) < 0.6


def test_consent_recorded_override_and_guardian(env):
    m = make(env)
    sid = m.start_session()
    with pytest.raises(ConsentError):
        m.add_person(sid, "Alex", None)
    pid = m.add_person(sid, "Alex", None, no_consent_override=True)
    assert m._captures[pid].consent_note == "none (user override)"
    with pytest.raises(ConsentError):
        m.add_person(sid, "Little one", "c-ok", guardian=True)
    g = enroll(m, sid, 21, "Little one", "c-guardian", guardian=True)
    assert m.db.execute("SELECT guardian_enrolled, consent_id FROM fm_enrolled WHERE person_id=?", (g,)).fetchone() == (1, "c-guardian")
    assert any(r[0]["kind"] == "consent_override" for r in env["chain"].entries)


def test_strict_jurisdiction_forces_consent_but_not_research(env):
    m = make(env, ("personal", "research"), jurisdiction="us-il", require_enrollment_consent=False)
    sid = m.start_session()
    with pytest.raises(ConsentError):
        m.add_person(sid, "Alex", None, no_consent_override=True)
    assert "strict biometric rules" in optin.warning_for("us-il") and "strict biometric rules" not in optin.warning_for("us-other")
    assert m.process_frame(synth_face_frame(9), place="Mall")["unrecognized"] == 1


def test_enrollment_names_pass_vocabulary_guard(env):
    m = make(env)
    sid = m.start_session()
    with pytest.raises(VocabularyViolation):
        m.add_person(sid, "the robot", "c-ok")


# ---- matching, research mode, no action -----------------------------------------------------
def test_personal_match_review_log_and_unknown_ignored(env):
    m = make(env)
    sid = m.start_session(); pid = enroll(m, sid, 31, "Alex"); m.end_session(sid)
    for i in range(10):
        r = m.process_frame(synth_face_frame(31, noise_seed=i), place="Trader Joe's", now=time.time() + i * 120)
        assert r == {"faces": 1, "matched": 1, "unrecognized": 0, "health": "ok"}
    assert m.process_frame(synth_face_frame(32), place="Trader Joe's")["matched"] == 0
    log = m.review_log()
    person = log["people"][0]
    assert person["name"] == "Alex" and person["summary"] == ["Alex: possible match at Trader Joe's, 10 times in the last 30 days"]
    assert log["unrecognized_counts"] == []    # personal-only mode ignores unknown faces
    assert pid == person["person_id"]


def test_research_mode_stores_no_face_data_and_cannot_link(env, tmp_path):
    m = make(env, ("research",))
    for i in range(10):
        m.process_frame(synth_face_frame(41, noise_seed=i), place="Store", now=1_700_000_000 + i)
    db_a = sorted(env["db"].execute("SELECT date, time_bucket, count FROM fm_unrecognized_count").fetchall())
    env["db"].execute("DELETE FROM fm_unrecognized_count")
    for i in range(10):
        m.process_frame(synth_face_frame(500 + i), place="Store", now=1_700_000_000 + i)
    db_b = sorted(env["db"].execute("SELECT date, time_bucket, count FROM fm_unrecognized_count").fetchall())
    assert db_a == db_b and db_a[0][2] == 10   # 1 face x10 == 10 faces x1
    cols = {r[1] for r in env["db"].execute("PRAGMA table_info(fm_unrecognized_count)")}
    assert cols == {"place_tag", "place", "date", "time_bucket", "count", "expires_at"}
    assert not cols & {"template", "embedding", "face_id", "hash", "person_id", "cluster"}
    assert env["db"].execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0] == 0
    emb = TestDeterministicBackend().embed(synth_face_frame(41), TestDeterministicBackend().detect(synth_face_frame(41), 1)[0]).vec
    needles = [emb.tobytes()[:16], emb.astype(np.float64).tobytes()[:16]]
    for p in env["dir"].rglob("*"):
        if p.is_file():
            blob = p.read_bytes()
            assert not any(n in blob for n in needles), p


def test_embeddings_zeroed_after_frame(env, monkeypatch):
    m = make(env, ("research",))
    seen = []
    real = m.backend.embed
    def spy(frame, box):
        e = real(frame, box); seen.append(e); return e
    m.backend.embed = spy
    m.process_frame(synth_face_frame(51), place="X")
    assert seen and all(not e.vec.any() for e in seen)


def test_match_produces_no_event_tts_or_notification(env):
    from oiris.adapters.base import AdapterBase
    from oiris.engine import Engine
    from oiris.modules.voice import NullTts
    m = make(env)
    sid = m.start_session(); enroll(m, sid, 61, "Alex"); m.end_session(sid)

    class Cam(AdapterBase):
        id, caps = "cam", {"face_frame"}
        def read(self, t):
            time.sleep(0.01); return self._sample(synth_face_frame(61))

    events, tts = [], NullTts()
    e = Engine(Config(), on_event=events.append, face_match=m, face_place="Home")
    e.add_adapter(Cam()); e.bus.start(); time.sleep(0.2)
    try:
        res = e.step()
    finally:
        e.bus.stop()
    assert m.stats["matched"] >= 1 and not events and not e.events and not tts.spoken
    assert "face_match" not in json.dumps(res) and "Alex" not in json.dumps(res)
    from oiris.guard import phrases
    assert "face" not in json.dumps(getattr(phrases, "PHRASES", {})).lower()


def test_all_m16_strings_pass_vocabulary():
    from oiris.modules.face_match import core, quality
    check_text(optin.WARNING_TEXT); check_text(optin.STRICT_NOTE); check_text(core.HINT)
    for r in quality.REASONS.values():
        check_text(r)


# ---- privacy guard -------------------------------------------------------------------------
def test_privacy_guard_allows_templates_only_from_enabled_m16():
    with pytest.raises(PrivacyError):
        check_persist("face_template", True)
    with pytest.raises(PrivacyError):
        check_persist("face_template", True, source="M-03", m16_enabled=True)
    with pytest.raises(PrivacyError):
        check_persist("face_template", True, source="M-16", m16_enabled=False)
    check_persist("face_template", True, source="M-16", m16_enabled=True)
    for kind in ("face_embedding", "face_id", "face_hash", "face_crop"):
        with pytest.raises(PrivacyError):
            check_persist(kind, True, source="M-16", m16_enabled=True)


# ---- review log, deletes, retention, export ----------------------------------------------
def test_per_entry_delete_and_person_cascade(env):
    m = make(env)
    sid = m.start_session(); a = enroll(m, sid, 71, "A"); b = enroll(m, sid, 72, "B"); m.end_session(sid)
    for i in range(3):
        m.process_frame(synth_face_frame(71, noise_seed=i), place="P"); m.process_frame(synth_face_frame(72, noise_seed=i), place="P")
    entries = m.review_log()["people"][0]["entries"]
    assert m.delete_entry(entries[0]["entry_id"])
    assert m.db.execute("SELECT COUNT(*) FROM fm_encounter WHERE person_id=?", (a,)).fetchone()[0] == 2
    assert m.db.execute("SELECT COUNT(*) FROM fm_encounter WHERE person_id=?", (b,)).fetchone()[0] == 3
    rep = m.delete_person(a)
    assert rep.verified and rep.message == "1 template destroyed, verified"
    assert m.db.execute("SELECT COUNT(*) FROM fm_encounter WHERE person_id=?", (a,)).fetchone()[0] == 0
    assert m.db.execute("SELECT COUNT(*) FROM fm_encounter WHERE person_id=?", (b,)).fetchone()[0] == 3
    assert m.process_frame(synth_face_frame(72), place="P")["matched"] == 1     # others untouched
    assert m.process_frame(synth_face_frame(71), place="P")["matched"] == 0


def test_person_delete_makes_template_undecryptable(env):
    m = make(env)
    sid = m.start_session(); a = enroll(m, sid, 81, "A"); enroll(m, sid, 82, "B"); m.end_session(sid)
    old_tpl, old_dek = m.db.execute("SELECT template, dek FROM fm_enrolled WHERE person_id=?", (a,)).fetchone()
    dek = Sealer(m._fk.open(old_dek, a.encode()))
    m.delete_person(a)
    assert not m._can_open_with_any(old_tpl, b"tpl:" + a.encode())
    assert not m._bytes_on_disk(old_tpl)
    assert dek.open(old_tpl, b"tpl:" + a.encode())   # only the destroyed DEK could have opened it


def test_retention_purges_expired(env):
    m = make(env, ("personal", "research"), encounter_retention_days=1)
    sid = m.start_session(); enroll(m, sid, 91, "A"); m.end_session(sid)
    t0 = 1_700_000_000
    m.process_frame(synth_face_frame(91), place="P", now=t0)
    m.process_frame(synth_face_frame(92), place="P", now=t0)
    assert nightly_purge(env["db"], days=30, now=t0 + 3600) == 0
    assert nightly_purge(env["db"], days=30, now=t0 + 2 * 86400) == 2
    assert env["db"].execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0] == 1   # templates kept until withdrawal


def test_export_blocked_and_never_contains_templates(env):
    m = make(env)
    sid = m.start_session(); enroll(m, sid, 95, "A"); m.end_session(sid)
    m.process_frame(synth_face_frame(95), place="P")
    with pytest.raises(ExportBlocked):
        m.export_log(explicit_user_action=True)
    m.cfg.allow_log_export = True
    with pytest.raises(ExportBlocked):
        m.export_log()
    out = json.dumps(m.export_log(explicit_user_action=True))
    assert "template" not in out and "person_id" not in out and "dek" not in out
    assert not [n for n in dir(m) if re.search(r"export.*template|template.*export|get_template", n)]


def test_reenroll_flag_and_replace(env):
    m = make(env, reenroll_window_matches=5)
    sid = m.start_session(); pid = enroll(m, sid, 101, "A"); m.end_session(sid)
    enrolled_at = m.db.execute("SELECT enrolled_at FROM fm_enrolled").fetchone()[0]
    for i in range(5):
        m._log_encounter(pid, 0.97, "P", enrolled_at + 3600 + i)
    assert m.review_log(days=365, now=enrolled_at + 86400)["people"][0]["hint"] == ""
    for i in range(5):
        m._log_encounter(pid, 0.85, "P", enrolled_at + 30 * 86400 + i)
    assert m.review_log(days=365, now=enrolled_at + 31 * 86400)["people"][0]["hint"]
    old_tpl = m.db.execute("SELECT template FROM fm_enrolled").fetchone()[0]
    sid = m.reenroll(pid)
    for a in REQUIRED_ANGLES:
        assert m.submit_shot(pid, synth_face_frame(101, a, noise_seed=7), a).ok
    assert m.finish_person(pid).complete
    m.end_session(sid)
    assert m.db.execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0] == 1
    assert not m._can_open_with_any(old_tpl, b"tpl:" + pid.encode())
    assert m.db.execute("SELECT COUNT(*) FROM fm_encounter WHERE person_id=?", (pid,)).fetchone()[0] == 10   # history kept


# ---- disable = verified wipe ---------------------------------------------------------------
def test_disable_verifiably_wipes_all_face_data(env):
    m = make(env, ("personal", "research"))
    sid = m.start_session()
    [enroll(m, sid, 200 + i, f"P{i}") for i in range(4)]
    half = m.add_person(sid, "Half", "c-ok"); m.submit_shot(half, synth_face_frame(250), Angle.FRONT)
    for i in range(4):
        m.process_frame(synth_face_frame(200 + i), place="P")
    m.process_frame(synth_face_frame(999), place="P")
    old = m.db.execute("SELECT person_id, dek, template FROM fm_enrolled").fetchall()
    templates_in_ram = list(m._load_templates())
    rep = m.disable()
    assert rep.verified and rep.templates_destroyed == 4 and rep.message == "4 templates destroyed, verified"
    db = env["db"]
    for t in ("fm_enrolled", "fm_encounter", "fm_unrecognized_count"):
        assert db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
    assert optin.opt_in_record(db) is None
    assert not (env["dir"] / "face_match.key").exists() and not (env["dir"] / "face_match_log.key").exists()
    keys = [env["ks"].master] + [env["ks"].subkey(p) for p in ("face-template", "face-log", "face-log-tag", "db")]
    for pid, dek, tpl in old:
        for k in keys:
            for blob, aad in ((dek, pid.encode()), (tpl, b"tpl:" + pid.encode())):
                with pytest.raises(Exception):
                    Sealer(k).open(blob, aad)
        for f in env["dir"].rglob("*"):
            if f.is_file():
                assert tpl not in f.read_bytes() and dek not in f.read_bytes()
    assert all(not t.vec.any() for t in templates_in_ram) and m.capture_buffer_size() == 0
    assert env["chain"].entries[-1][0]["kind"] == "disabled_wiped"
    assert "P0" not in json.dumps([r for r, _ in env["chain"].entries])   # log records counts only, no names
    with pytest.raises(FaceMatchLocked):
        m.start_session()
    with pytest.raises(FaceMatchLocked):   # re-enabling starts from zero: new opt-in needed
        FaceMatchModule(db, env["ks"], env["dir"], TestDeterministicBackend(), env["chain"], FaceMatchConfig(modes=["personal"], allow_test_backend=True))
    assert verify(env["chain"].entries, env["chain"].key, env["chain"].anchors, env["sk"].verify_key) == len(env["chain"].entries)


def test_cli_optin_enroll_review_disable(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from oiris.face_match_cli import run
    monkeypatch.setenv("OIRIS_PASSPHRASE", "pw")
    cfg = Config(data_dir=str(tmp_path)); cfgp = tmp_path / "config.json"
    cfgp.write_text(json.dumps({"data_dir": str(tmp_path)}))
    out: list[str] = []
    a = lambda sub, **kw: SimpleNamespace(sub=sub, mode=kw.get("mode"), jurisdiction="us-other", camera=None, id=kw.get("id"))
    with pytest.raises(optin.OptInError):
        run(a("enable", mode=["personal"]), cfg, cfgp, inp=lambda p: "nope", out=out.append)
    assert run(a("enable", mode=["personal", "research"]), cfg, cfgp, inp=lambda p: "I UNDERSTAND", out=out.append) == 0
    assert json.loads(cfgp.read_text())["flags"]["M-16"] is True
    cfg2 = Config.load(cfgp)
    assert cfg2.data_dir == str(tmp_path)
    out.clear()
    assert run(a("status"), cfg2, cfgp, out=out.append) == 0 and '"opted_in": true' in out[0]
    assert run(a("disable"), cfg2, cfgp, out=out.append) == 0
    assert "0 templates destroyed, verified" in out[-1]
    assert json.loads(cfgp.read_text())["flags"]["M-16"] is False


def test_config_validation_mirrors_module(env):
    assert validate_face_match({"modes": ["stalk"]}) and validate_face_match({"match_threshold": 0.2})
    assert validate_face_match({"max_people": 5})     # unknown keys rejected: there is no people limit setting
    assert not validate_face_match({"modes": ["personal", "research"], "match_threshold": 0.85})
    from oiris.config import FACE_MATCH_KEYS
    assert FACE_MATCH_KEYS == set(FaceMatchConfig.__dataclass_fields__)
    with pytest.raises(Exception):
        Config(face_match={"enroll_min_shots": 3}).validate()


def test_review_log_output_has_no_class_fields(env):
    m = make(env)
    sid = m.start_session(); enroll(m, sid, 111, "A"); m.end_session(sid)
    m.process_frame(synth_face_frame(111), place="P")
    check_output(m.review_log())


# ---- real backend (skips without weights) --------------------------------------------------
def _model_dir():
    return os.environ.get("OIRIS_FACE_MODEL_DIR", str(Path.home() / ".asb" / "models" / "face_match"))


def test_opencv_zoo_backend_real_weights(env):
    cv2 = pytest.importorskip("cv2")
    from oiris.modules.face_match.backends.opencv_zoo import OpenCvZooBackend, models_present, pose_from_landmarks
    if not models_present(_model_dir()):
        pytest.skip("face model weights not downloaded (oiris face-match fetch-models)")
    b = OpenCvZooBackend(); b.open({"model_dir": _model_dir()})
    assert b.license == "Apache-2.0" and not b.test_only
    assert b.detect(np.zeros((240, 320, 3), np.uint8), 1.0) == []
    # landmark pose buckets (geometry only)
    lm = np.array([[40, 50], [80, 50], [60, 72], [45, 90], [75, 90]], float)
    assert pose_from_landmarks(lm) == Angle.FRONT
    assert pose_from_landmarks(lm + np.array([[0, 0], [0, 0], [15, 0], [0, 0], [0, 0]])) == Angle.RIGHT
    assert pose_from_landmarks(lm + np.array([[0, 0], [0, 0], [-15, 0], [0, 0], [0, 0]])) == Angle.LEFT
    assert pose_from_landmarks(lm + np.array([[0, 0], [0, 0], [0, -14], [0, 0], [0, 0]])) == Angle.UP
    assert pose_from_landmarks(lm + np.array([[0, 0], [0, 0], [0, 12], [0, 0], [0, 0]])) == Angle.DOWN
    img_path = os.environ.get("OIRIS_FACE_TEST_IMAGE")
    if img_path:
        img = cv2.imread(img_path)
        faces = b.detect(img, 1.0)
        assert faces
        e1 = b.embed(img, faces[0]); e2 = b.embed(img, faces[0])
        assert e1.valid(128) and b.compare(e1, [__import__("oiris.modules.face_match.port", fromlist=["Template"]).Template("x", e2.vec)]).confidence > 0.99


def test_model_fetch_rejects_bad_checksum(tmp_path):
    import io
    from oiris.modules.face_match.backends.opencv_zoo import ModelMissing, fetch_models, models_present
    with pytest.raises(ModelMissing):
        fetch_models(tmp_path, opener=lambda url: io.BytesIO(b"not the model"))
    assert not models_present(tmp_path) and not list(tmp_path.glob("*.onnx")) and not list(tmp_path.glob("*.part"))


# ---- Forge F3: consent withdrawal invalidates templates -------------------------------------
def test_f3_withdrawn_consent_template_not_matched_and_crypto_erased(env):
    from oiris.guard.consent import ConsentRecord
    env["consents"].add(ConsentRecord("c-wd", "s9", {"face_enrollment"}))
    m = make(env)
    sid = m.start_session(); a = enroll(m, sid, 77, "A", consent="c-wd"); m.end_session(sid)
    assert m.process_frame(synth_face_frame(77), place="P")["matched"] == 1   # templates cached in RAM
    old_tpl = env["db"].execute("SELECT template FROM fm_enrolled WHERE person_id=?", (a,)).fetchone()[0]
    env["consents"]._r["c-wd"].withdrawn = True          # withdrawal without any hook firing
    assert m.process_frame(synth_face_frame(77), place="P")["matched"] == 0
    assert env["db"].execute("SELECT COUNT(*) FROM fm_enrolled WHERE person_id=?", (a,)).fetchone()[0] == 0
    assert not m._can_open_with_any(old_tpl, b"tpl:" + a.encode())


def test_f3_withdraw_hook_purges_immediately_and_keeps_others(env):
    from oiris.guard.consent import ConsentRecord
    env["consents"].add(ConsentRecord("c-wd2", "s8", {"face_enrollment"}))
    m = make(env)
    sid = m.start_session(); a = enroll(m, sid, 61, "A", consent="c-wd2"); b = enroll(m, sid, 62, "B"); m.end_session(sid)
    m.process_frame(synth_face_frame(61), place="P")
    env["consents"].withdraw("c-wd2")
    ids = {r[0] for r in env["db"].execute("SELECT person_id FROM fm_enrolled")}
    assert ids == {b}
    assert all(t.person_id != a for t in m._load_templates())
    assert m.process_frame(synth_face_frame(62), place="P")["matched"] == 1


def test_f3_expired_consent_template_purged_on_load(env):
    from oiris.guard.consent import ConsentRecord
    env["consents"].add(ConsentRecord("c-exp", "s7", {"face_enrollment"}, expires_utc=time.time() + 3600))
    m = make(env)
    sid = m.start_session(); a = enroll(m, sid, 55, "A", consent="c-exp"); m.end_session(sid)
    env["consents"]._r["c-exp"].expires_utc = 1.0
    assert m.process_frame(synth_face_frame(55), place="P")["matched"] == 0
    assert env["db"].execute("SELECT COUNT(*) FROM fm_enrolled WHERE person_id=?", (a,)).fetchone()[0] == 0
