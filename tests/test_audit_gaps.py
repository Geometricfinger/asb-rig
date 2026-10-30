"""Tests for the O Iris audit gap build (M-02 digits, M-04 rotation/anchors, M-07 ArUco,
M-03 registries, M-06 Flite, M-15 Keychain gate, M-16 glasses mini-guide, shared vectors)."""
import json, os, stat, subprocess, sys, wave
from pathlib import Path

import numpy as np
import pytest
from nacl.signing import SigningKey

from oiris.features import aruco, baseline, rf
from oiris.modules import liveness
from oiris.modules.appgate import AppGate
from oiris.modules.mac_gate import GateCancelled, GateError, GateUnavailable, KeychainBiometricGate
from oiris.security import hashchain as hc
from oiris.security.channel import ChannelError, SecureChannel, fingerprint, from_pairing, new_static, pub_from_priv
from oiris.security.keys import KeyStore, KeyStoreError, StaticKeyManager, static_key_status, STATIC_MAX_AGE_S
from oiris.security.panic import PanicController
from oiris.ui import glasses

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self, t=0.0): self.t = t
    def __call__(self): return self.t


# ---------------- M-02 spoken-digit challenge ----------------
def test_digit_challenge_live_answer_observed():
    c = Clock(); ch = liveness.DigitChallenge(clock=c)
    p = ch.issue()
    assert len(p.digits) == 4 and p.digits.isdigit() and "say" in p.text
    words = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}
    c.t = 1.5
    r = ch.verify(p.nonce, " ".join(words[d] for d in p.digits), speech_start=0.9)
    assert r.state == "observed" and r.as_score_value() == 0.0
    s = liveness.digit_score(r)
    assert s.module == "S_voice" and s.value == 0.0


def test_digit_challenge_rejects_replay_wrong_early_slow_timeout():
    c = Clock(); ch = liveness.DigitChallenge(clock=c)
    p = ch.issue(); c.t = 1
    assert ch.verify(p.nonce, p.digits, 0.8).state == "observed"
    assert ch.verify(p.nonce, p.digits, 0.8).state == "rejected"            # replay of a used nonce
    assert ch.verify("nope", p.digits, 0.8).state == "rejected"
    p = ch.issue(); c.t += 1
    wrong = "".join(str((int(d) + 1) % 10) for d in p.digits)
    assert ch.verify(p.nonce, wrong, p.issued_at + 0.6).reason == "digits did not match"
    p = ch.issue()
    assert "before the prompt" in ch.verify(p.nonce, p.digits, p.issued_at + 0.05).reason   # pre-recorded audio started early
    p = ch.issue()
    assert ch.verify(p.nonce, p.digits, p.issued_at + 6).reason == "answer too slow"
    p = ch.issue(); c.t += 11
    assert ch.verify(p.nonce, p.digits, p.issued_at + 1).reason == "timeout"
    p = ch.issue(); c.t += 11
    assert ch.expire() == 1 and ch.verify(p.nonce, p.digits, 1).state == "rejected"


def test_digit_prompts_are_random_and_feed_a11():
    ch = liveness.DigitChallenge()
    assert len({ch.issue().digits for _ in range(50)}) > 40
    assert liveness.normalise_digits("Four, 7 - nine oh") == "4790"
    from oiris.schema import Score
    out = liveness.indicators([liveness.digit_score(liveness.DigitResult("not observed", "timeout")), Score("S_live", 0.9, 0.8)])
    assert out["a11"] and "voice" in out["families_absent"]
    with pytest.raises(ValueError):
        liveness.DigitChallenge(n_digits=2)


# ---------------- M-04 static-key rotation, re-pair, anchor timer ----------------
def test_static_key_status_windows():
    assert static_key_status(0, 10 * 86400) == "ok"
    assert static_key_status(0, 85 * 86400) == "rotate_soon"
    assert static_key_status(0, STATIC_MAX_AGE_S) == "expired"


def test_rotation_requires_repair_and_channel_refuses_expired(tmp_path):
    ks = KeyStore(tmp_path / "k.json"); ks.create("pw")
    c = Clock(1_000_000.0)
    m = StaticKeyManager(ks, tmp_path / "static.json", clock=c)
    r = m.create()
    assert m.status() == "unpaired"
    with pytest.raises(ChannelError):
        from_pairing(True, r)
    peer = new_static()
    m.complete_repair(fingerprint(pub_from_priv(peer)))
    assert m.status() == "ok"
    assert b"static" not in (tmp_path / "static.json").read_bytes() or r.static_priv.hex() not in (tmp_path / "static.json").read_text()
    c.t += 89 * 86400
    assert m.status() == "rotate_soon" and not m.rotate_if_due()
    c.t += 2 * 86400
    rec = m.load()
    with pytest.raises(ChannelError, match="90 days"):
        SecureChannel(True, rec.static_priv, rec.peer_fp, static_created=rec.created, wall_clock=c)
    assert m.rotate_if_due()
    new = m.load()
    assert new.static_priv != rec.static_priv and new.peer_fp is None and new.previous_peer_fp == rec.peer_fp
    assert m.status() == "unpaired"
    m.complete_repair(fingerprint(pub_from_priv(peer)))
    ch = from_pairing(True, m.load(), wall_clock=c)
    assert not ch.ready
    ks.lock()
    with pytest.raises(KeyStoreError):
        m.load()


def test_anchor_every_60_seconds_as_well_as_every_100_records():
    c = Clock()
    chain = hc.HashChain(os.urandom(32), SigningKey.generate(), clock=c)
    for i in range(5):
        chain.append({"i": i})
    assert chain.anchors == []
    c.t = 61
    chain.append({"i": 5})
    assert [a.idx for a in chain.anchors] == [6]
    c.t = 200
    assert chain.tick() is None           # nothing new since the last anchor: no growth while idle
    chain.append({"i": 6}); c.t = 270
    a = chain.tick()
    assert a is not None and a.idx == 7
    for i in range(93):
        chain.append({"i": 7 + i})
    assert chain.anchors[-1].idx == 100   # the every-100 rule still holds
    assert hc.verify(chain.entries, chain.key, chain.anchors, chain.signer.verify_key) == 100


# ---------------- M-07 ArUco anchors ----------------
def _warp(src: np.ndarray, H: np.ndarray, shape, fill=255) -> np.ndarray:
    """Inverse-map warp (nearest), numpy only: dst(x) = src(H^-1 x)."""
    hh, ww = shape
    ys, xs = np.mgrid[:hh, :ww]
    p = np.stack([xs.ravel(), ys.ravel(), np.ones(xs.size)])
    q = np.linalg.inv(H) @ p
    sx, sy = np.round(q[0] / q[2]).astype(int), np.round(q[1] / q[2]).astype(int)
    ok = (sx >= 0) & (sy >= 0) & (sx < src.shape[1]) & (sy < src.shape[0])
    out = np.full(xs.size, fill, np.uint8)
    out[ok] = src[sy[ok], sx[ok]]
    return out.reshape(hh, ww)


def test_label_matches_flood_fill_reference():
    rng = np.random.default_rng(3)
    m = rng.random((40, 50)) < 0.45
    lab = aruco.label(m)
    # reference: BFS components
    ref = np.zeros(m.shape, int); n = 0
    for y in range(m.shape[0]):
        for x in range(m.shape[1]):
            if m[y, x] and not ref[y, x]:
                n += 1; st = [(y, x)]; ref[y, x] = n
                while st:
                    a, b = st.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        u, v = a + dy, b + dx
                        if 0 <= u < m.shape[0] and 0 <= v < m.shape[1] and m[u, v] and not ref[u, v]:
                            ref[u, v] = n; st.append((u, v))
    pairs = {(a, b) for a, b in zip(lab[m], ref[m])}
    assert len(pairs) == n == len({a for a, _ in pairs}) == len({b for _, b in pairs})
    assert (lab[~m] == 0).all()


def test_aruco_detects_ids_and_corners_under_perspective_noise_and_rotation():
    rng = np.random.default_rng(11)
    ok, errs = 0, []
    for _trial in range(40):
        mid = int(rng.integers(50)); cell = int(rng.integers(7, 16))
        mk = aruco.render(mid, cell_px=cell, quiet_cells=0)
        side = mk.shape[0]
        canvas = np.full((360, 480), 255, np.uint8)
        x0, y0 = 150, 100
        canvas[y0:y0 + side, x0:x0 + side] = mk
        src = np.array([[x0, y0], [x0 + side, y0], [x0 + side, y0 + side], [x0, y0 + side]], float)
        ang = rng.uniform(0, 2 * np.pi); c = src.mean(0)
        R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
        dst = (src + rng.normal(0, side * 0.08, (4, 2)) - c) @ R.T + c
        H = aruco.homography(src, dst)
        img = _warp(canvas, H, canvas.shape).astype(float)
        img = np.clip(img * rng.uniform(0.5, 1.0) + rng.normal(0, 6, img.shape), 0, 255).astype(np.uint8)
        found = aruco.detect(img)
        if len(found) == 1 and found[0].id == mid:
            ok += 1
            errs.append(np.abs(found[0].corners - dst).max())
    assert ok >= 38, ok                           # measured: 40/40 on this seed
    assert np.median(errs) < 2.5 and max(errs) < 4.0


def test_aruco_rejects_blank_and_non_markers():
    assert aruco.detect(np.full((100, 100), 200, np.uint8)) == []
    img = np.full((120, 120), 255, np.uint8); img[30:90, 30:90] = 0   # solid square: border ok but bits all black
    assert aruco.detect(img) == []


def test_aruco_pose_recovers_distance():
    K = np.array([[600.0, 0, 320], [0, 600.0, 240], [0, 0, 1]])
    s, t = 0.05, np.array([0.02, -0.01, 0.8])
    obj = np.array([[-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]])
    a = 0.4; Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    cam = (Rx @ obj.T).T + t
    px = (K @ cam.T).T; px = px[:, :2] / px[:, 2:3]
    R, tt = aruco.pose(aruco.Marker(0, px, 0), 2 * s, K)
    assert np.allclose(tt, t, atol=1e-6) and np.allclose(R, Rx, atol=1e-6)


def test_baseline_anchors_are_detected_marker_ids():
    view = np.full((240, 400), 220, np.uint8)
    m1, m2 = aruco.render(3, 8), aruco.render(17, 6)
    view[20:20 + m1.shape[0], 20:20 + m1.shape[1]] = m1
    view[120:120 + m2.shape[0], 250:250 + m2.shape[1]] = m2
    b = baseline.SiteBaseline("home")
    K = np.array([[500.0, 0, 200], [0, 500.0, 120], [0, 0, 1]])
    assert baseline.register_anchors(b, view, K, 0.10) == [3, 17]
    assert b.anchors == [3, 17] and set(b.anchor_poses) == {3, 17}
    assert baseline.anchor_in_view(b, view) == 3            # the larger marker in view
    only17 = np.full((240, 400), 220, np.uint8); only17[50:50 + m2.shape[0], 50:50 + m2.shape[1]] = m2
    bg = np.full((8, 8), 20.0)
    assert baseline.pass_from_view(b, only17, {"e1"}, bg, [(1, 1)]) == 17
    hot = bg.copy(); hot[2:5, 2:5] = 35
    assert baseline.new_thermal_blobs(b, 17, hot) == 1 and baseline.new_thermal_blobs(b, 3, hot) == 0
    assert baseline.pass_from_view(b, np.full((240, 400), 220, np.uint8), set(), bg, []) is None


# ---------------- M-03 registries ----------------
def test_rf_tables_from_public_registries():
    t = json.loads((ROOT / "oiris/features/rf_tables.json").read_text())
    assert "Bluetooth SIG" in t["sources"]["company_identifiers"] and "IEEE" in t["sources"]["oui"]
    assert len(rf.COMPANY_TYPES) >= 50 and len(rf.CAMERA_OUI_HINTS) >= 100
    assert rf.COMPANY_TYPES[0x004C] == "phone_or_wearable" and t["company_types"]["0x004C"]["org"] == "Apple, Inc."
    assert rf.COMPANY_TYPES[0x0087] == "fitness_wearable"            # Garmin
    assert rf.COMPANY_TYPES[0x0059] == "iot_module"                  # Nordic Semiconductor
    assert set(rf.COMPANY_TYPES.values()) <= rf.TYPES
    hik = [o for o, org in t["camera_ouis"].items() if "Hikvision" in org]
    assert hik and rf.device_type(is_ap=True, oui=hik[0].upper().replace(":", "-") + "-01-02-03") == "camera_like"
    assert rf.device_type(is_ap=True, oui="00:00:00") == "access_point"
    assert rf.device_type(service_uuids=["00001810-0000-1000-8000-00805f9b34fb"]) == "medical_device"
    rf.add_camera_ouis(["AA-BB-CC"]); assert rf.device_type(is_ap=True, oui="aabbcc112233") == "camera_like"
    rf.CAMERA_OUI_HINTS.discard("aa:bb:cc")


# ---------------- M-06 Flite, really run ----------------
def test_flite_backend_synthesises_real_speech(tmp_path):
    from oiris.modules.voice import FliteTts, VoiceOutput
    try:
        tts = FliteTts(out_dir=str(tmp_path))
    except RuntimeError:
        if os.environ.get("OIRIS_REQUIRE_FLITE") == "1":
            raise
        pytest.skip("flite not installed")
    p = tts.synthesize("New signature at anchor three", str(tmp_path / "a.wav"))
    with wave.open(p) as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() >= 8000
        frames = w.readframes(w.getnframes()); dur = w.getnframes() / w.getframerate()
    pcm = np.frombuffer(frames, "<i2").astype(float)
    assert 0.8 < dur < 6 and np.sqrt(np.mean(pcm ** 2)) > 200      # audible speech, not silence
    vo = VoiceOutput(tts, min_interval_s=0)
    assert vo.announce("attention", "new_object", anchor="anchor 3") == "spoken"
    tts.wait()
    assert len(tts.files) == 1 and Path(tts.files[0]).stat().st_size > 10_000
    vo.announce("confirmed", "new_object", confirm_token=True, anchor="anchor 3")   # barge-in path with a real process
    tts.wait(); vo.acknowledge()


# ---------------- M-15 Keychain biometric gate ----------------
FAKE_HELPER = r'''#!/usr/bin/env python3
import json, os, sys
st = os.environ["FAKE_GATE_STATE"]; mode = os.environ.get("FAKE_GATE_MODE", "ok")
cmd = sys.argv[1]
if cmd == "status": print(json.dumps({"biometry": mode != "unavailable", "detail": "fake"})); sys.exit(0)
if mode == "cancel": sys.exit(2)
if mode == "unavailable": sys.exit(3)
if mode == "fail": sys.exit(5)
if cmd == "store": open(st, "w").write(sys.stdin.read().strip()); print(json.dumps({"stored": True, "binding": "la-check"}))
elif cmd == "load":
    if not os.path.exists(st): sys.exit(4)
    print(json.dumps({"secret": open(st).read(), "binding": "la-check"}))
elif cmd == "delete":
    os.path.exists(st) and os.remove(st); print("{}")
'''


@pytest.fixture
def fake_gate(tmp_path, monkeypatch):
    h = tmp_path / "gate"; h.write_text(FAKE_HELPER.replace("/usr/bin/env python3", sys.executable))
    h.chmod(h.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FAKE_GATE_STATE", str(tmp_path / "secret"))
    return KeychainBiometricGate(h)


def test_keychain_gate_unlocks_keystore_slot(tmp_path, fake_gate, monkeypatch):
    ks = KeyStore(tmp_path / "k.json"); master = ks.create("pw")
    erased = []
    panic = PanicController(soft=lambda: None, erase=lambda: erased.append(1))
    g = AppGate(ks, panic)
    assert g.enroll_biometric(fake_gate) == "la-check" and ks.slots() == ["mac-biometric"]
    g.lock(); assert not g.unlocked
    assert g.unlock_biometric(fake_gate) and g.unlocked and ks.master == master
    g.lock()
    monkeypatch.setenv("FAKE_GATE_MODE", "cancel")
    assert not g.unlock_biometric(fake_gate) and panic.failed_unlocks == 0      # cancel is not a failed attempt
    monkeypatch.setenv("FAKE_GATE_MODE", "fail")
    assert not g.unlock_biometric(fake_gate) and panic.failed_unlocks == 1
    monkeypatch.setenv("FAKE_GATE_MODE", "ok")
    (tmp_path / "secret").write_text("00" * 32)                                  # wrong secret -> slot refuses
    assert not g.unlock_biometric(fake_gate) and not g.unlocked
    assert g.unlock("pw")                                                          # passphrase always still works
    g.remove_biometric(fake_gate); assert ks.slots() == [] and not (tmp_path / "secret").exists()


def test_keychain_gate_errors(fake_gate, monkeypatch):
    with pytest.raises(ValueError):
        fake_gate.store(b"short")
    monkeypatch.setenv("FAKE_GATE_MODE", "unavailable")
    with pytest.raises(GateUnavailable):
        fake_gate.load()
    monkeypatch.setenv("FAKE_GATE_MODE", "cancel")
    with pytest.raises(GateCancelled):
        fake_gate.load()
    monkeypatch.setenv("FAKE_GATE_MODE", "ok")
    with pytest.raises(GateError):
        fake_gate.load()       # nothing stored


def test_swift_helper_source_is_biometric_only():
    src = (ROOT / "macos/keychain_gate/main.swift").read_text()
    assert ".deviceOwnerAuthenticationWithBiometrics" in src and "deviceOwnerAuthentication)" not in src
    assert "biometryCurrentSet" in src and "localizedFallbackTitle = \"\"" in src
    assert "errSecMissingEntitlement" in src and "la-check" in src


# ---------------- M-16 glasses mini-guide ----------------
def test_glasses_enroll_guide_shows_next_angle_and_tick():
    from oiris.modules.face_match.port import Angle

    class Port:
        def needed_angles(self, pid): return {Angle.LEFT, Angle.UP}

    class Shot:
        def __init__(self, ok, reason=""): self.ok, self.reason = ok, reason
    g = glasses.guide_from_port(Port(), "P1", Shot(True))
    assert g.next_angle == "left" and g.last_ok and not g.complete
    svg = glasses.render_enroll_guide(g)
    assert "Turn head left" in svg and 'id="tick"' in svg and svg.count('class="guide"') == 5
    assert svg.count('fill="none" stroke=') >= 2                      # two angles still open
    bad = glasses.render_enroll_guide(glasses.guide_from_port(Port(), "P1", Shot(False, "too blurry, hold still")))
    assert "too blurry hold still" in bad and 'id="tick"' not in bad

    class Done:
        def needed_angles(self, pid): return set()
    assert "Template complete" in glasses.render_enroll_guide(glasses.guide_from_port(Done(), "P1", Shot(True)))
    # nothing in the clear centre, no names, vocabulary-safe
    assert "P1" not in svg and "robot" not in svg.lower()
    tok = glasses.T.load(); cx, cy, cw, ch = glasses._centre(tok)
    assert not glasses._overlap(glasses.zones(tok)["G2"], (cx, cy, cw, ch))


# ---------------- shared Android vectors stay in sync ----------------
def test_android_vectors_are_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/make_android_vectors.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
