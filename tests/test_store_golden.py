import os, sqlite3
import pytest
from nacl.signing import SigningKey

from asb.security.hashchain import HashChain, verify
from asb.store.db import DB, MigrationError
from asb.store.migrations import LATEST
from asb.store.sightings import SightingLog, SweepTimeline, GpsFix, OSM_ATTRIBUTION
from asb.modules import golden as g


def test_migrations_fresh_and_incremental(tmp_path, key):
    d = DB(tmp_path / "a.db", key)
    assert d.version == LATEST and d.has_table("golden_clip")
    d.close()
    p = tmp_path / "b.db"
    d = DB.__new__(DB)
    d.path = str(p); d.conn = sqlite3.connect(str(p), isolation_level=None)
    import threading; d.lock = threading.RLock()
    from asb.security.aead import Sealer; d.sealer = Sealer(key)
    assert d.migrate(1) == 1 and not d.has_table("sighting")
    d.execute("INSERT INTO audit_log(t_wall,kind,detail) VALUES(1,'x','{}')")
    assert d.migrate() == LATEST
    assert d.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 1


def test_refuses_newer_schema(tmp_path, key):
    p = tmp_path / "c.db"
    c = sqlite3.connect(p); c.execute(f"PRAGMA user_version={LATEST + 5}"); c.commit(); c.close()
    with pytest.raises(MigrationError):
        DB(p, key)


def test_sightings_gps_policy_and_export(db):
    log = SightingLog(db, HashChain(os.urandom(32), SigningKey.generate()))
    a = log.add({"signature": "A1"}, GpsFix(38.256789, -85.751234, "3d"))
    b = log.add({"signature": "A4"}, GpsFix(1.0, 2.0, "no_fix"))
    assert log.get(b)["lat"] is None                     # never guessed
    ex = {s["sighting_id"]: s for s in log.export(2)}
    assert ex[a]["lat"] == 38.26 and ex[a]["lon"] == -85.75
    pins = log.map_pins()
    assert pins["attribution"] == OSM_ATTRIBUTION and len(pins["pins"]) == 1
    log.set_verdict(a, "confirmed")
    assert log.get(a)["verdict"] == "confirmed"
    with pytest.raises(ValueError):
        log.set_verdict(a, "is_robot")
    assert verify(log.chain.entries, log.chain.key, log.chain.anchors, log.chain.signer.verify_key) == 3


def test_db_unreadable_with_wrong_key(tmp_path, key):
    from asb.security.aead import Sealer
    d = DB(tmp_path / "x.db", key)
    log = SightingLog(d, HashChain(os.urandom(32), SigningKey.generate()))
    sid = log.add({"signature": "A1"}, GpsFix(1, 2, "3d"))
    d.close()
    d2 = DB(tmp_path / "x.db", Sealer.new_key())
    with pytest.raises(Exception):
        SightingLog(d2, HashChain(os.urandom(32), SigningKey.generate())).get(sid)


def test_sweep_timeline(db):
    t = SweepTimeline(db)
    s1 = t.start("home"); t.finish(s1, {"A4": 2}, [])
    s2 = t.start("home"); t.finish(s2, {"A4": 3}, ["e9"])
    h = t.history("home")
    assert [x["sweep_id"] for x in h] == [s1, s2] and h[1]["new_since_last"] == ["e9"]


def _clip(tmp_path, cid, split="train", **kw):
    p = tmp_path / f"{cid}.npy"; p.write_bytes(os.urandom(64))
    return g.Clip(cid, p.name, g.sha256_file(p), kw.pop("label", "camera_device"), split, "own_recorded", **kw)


def test_golden_manifest_rules(tmp_path):
    m = g.Manifest()
    m.add(_clip(tmp_path, "t1", "test"))
    m.add(_clip(tmp_path, "a1"))
    m.freeze()
    with pytest.raises(g.ManifestError):
        m.add(_clip(tmp_path, "t2", "test"))
    with pytest.raises(g.ManifestError):
        m.add(_clip(tmp_path, "p1", contains_person=True))
    with pytest.raises(g.ManifestError):
        m.add(_clip(tmp_path, "r1", label="robot"))
    assert m.verify(tmp_path) == []
    (tmp_path / "a1.npy").write_bytes(b"tampered")
    assert m.verify(tmp_path) == ["a1"]
    m.save(tmp_path / "manifest.json")
    assert g.Manifest.load(tmp_path / "manifest.json").frozen_test_hash == m.frozen_test_hash


def test_golden_withdrawal_bumps_version(tmp_path):
    m = g.Manifest()
    m.add(_clip(tmp_path, "v1", label="volunteer_consented", consent_id="c9", contains_person=True))
    v = m.version
    assert m.withdraw("c9") == 1 and m.version == v + 1 and not m.clips


def test_golden_format_migration():
    d = {"version": 3, "clips": [{"clip_id": "x", "path": "x", "sha256": "0", "label": "benign", "split": "dev",
                                  "tier": "synthetic"}]}
    out = g.migrate(d)
    assert out["format_version"] == 2 and out["clips"][0]["source_tier"] == "synthetic"
    with pytest.raises(g.ManifestError):
        g.migrate({"format_version": 99})


def test_feedback_loop_never_touches_test(tmp_path):
    m = g.Manifest(); m.add(_clip(tmp_path, "t1", "test")); h = m.freeze()
    fb = g.FeedbackLoop(m, tmp_path)
    f = tmp_path / "feat.npy"; f.write_bytes(b"x")
    for i in range(20):
        fb.propose(f"s{i}", f, "camera_device", "confirmed", None, False)
    for i in range(20, 40):
        fb.propose(f"s{i}", f, "camera_device", "benign", None, False)
    assert all(c.split == "quarantine" for c in m.clips if c.clip_id.startswith("fb-"))
    with pytest.raises(g.ManifestError):
        fb.promote("fb-s0", "test")
    fb.promote("fb-s0")
    assert m.test_hash() == h
    with pytest.raises(g.ManifestError):
        fb.propose("sx", f, "camera_device", "unresolved", None, False)
    with pytest.raises(g.ManifestError):
        fb.propose("sp", f, "volunteer_consented", "confirmed", None, True)
