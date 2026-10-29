import os, re
from pathlib import Path
import pytest
from hypothesis import given, settings, strategies as st
from nacl.signing import SigningKey

from asb.security.aead import Sealer
from asb.security.keys import KeyStore, KeyStoreError
from asb.security import hashchain as hc
from asb.security.channel import SecureChannel, new_static, fingerprint, pub_from_priv, ChannelError
from asb.security.panic import PanicController


def test_aead_roundtrip_and_tamper(key):
    s = Sealer(key)
    b = s.seal(b"secret", b"aad")
    assert s.open(b, b"aad") == b"secret"
    with pytest.raises(Exception):
        s.open(b, b"other")
    bad = bytearray(b); bad[-1] ^= 1
    with pytest.raises(Exception):
        s.open(bytes(bad), b"aad")


def test_nonce_never_reused(key):
    s = Sealer(key)
    nonces = {s.seal(b"x")[1:13] for _ in range(5000)}
    assert len(nonces) == 5000


def test_keystore_unlock_and_erase(tmp_path):
    ks = KeyStore(tmp_path / "k.json")
    m = ks.create("correct horse")
    ks.lock()
    with pytest.raises(KeyStoreError):
        ks.master
    assert ks.unlock("correct horse") == m
    with pytest.raises(KeyStoreError):
        ks.unlock("wrong")
    assert b"correct" not in (tmp_path / "k.json").read_bytes()
    ks.crypto_erase()
    assert not (tmp_path / "k.json").exists()
    with pytest.raises(KeyStoreError):
        ks.unlock("correct horse")


def _chain(n=250):
    c = hc.HashChain(os.urandom(32), SigningKey.generate(), anchor_every=100)
    for i in range(n):
        c.append({"i": i, "v": f"r{i}"})
    c.anchor()
    return c


def test_chain_verifies():
    c = _chain()
    assert hc.verify(c.entries, c.key, c.anchors, c.signer.verify_key) == 250


@settings(max_examples=200, deadline=None)
@given(st.integers(0, 249), st.sampled_from(["edit", "delete", "swap", "truncate"]))
def test_chain_detects_tamper(i, op):
    c = _chain()
    e = list(c.entries)
    if op == "edit":
        rec, h = e[i]; e[i] = ({**rec, "v": "x"}, h)
    elif op == "delete":
        del e[i]
    elif op == "swap":
        j = (i + 1) % len(e); e[i], e[j] = e[j], e[i]
    else:
        e = e[: min(i, 199)]
    with pytest.raises(hc.ChainInvalid):
        hc.verify(e, c.key, c.anchors, c.signer.verify_key)


def _pair(**kw):
    a, b = new_static(), new_static()
    I = SecureChannel(True, a, fingerprint(pub_from_priv(b)), **kw)
    R = SecureChannel(False, b, fingerprint(pub_from_priv(a)), **kw)
    R.read_handshake(I.write_handshake()); I.read_handshake(R.write_handshake()); R.read_handshake(I.write_handshake())
    return I, R


def test_channel_roundtrip_rekey():
    I, R = _pair(rekey_messages=1000)
    for i in range(2500):
        assert R.decrypt(I.encrypt(b"m%d" % i)) == b"m%d" % i
    assert I.rekeys == 2


def test_channel_rekey_by_time(clock):
    a, b = new_static(), new_static()
    I = SecureChannel(True, a, fingerprint(pub_from_priv(b)), clock=clock)
    R = SecureChannel(False, b, fingerprint(pub_from_priv(a)), clock=clock)
    R.read_handshake(I.write_handshake()); I.read_handshake(R.write_handshake()); R.read_handshake(I.write_handshake())
    R.decrypt(I.encrypt(b"a")); clock.advance(601)
    assert R.decrypt(I.encrypt(b"b")) == b"b" and I.rekeys == 1


def test_channel_rejects_bitflip_and_replay():
    I, R = _pair()
    m = I.encrypt(b"hello")
    bad = bytearray(m); bad[-1] ^= 1
    with pytest.raises(ChannelError):
        R.decrypt(bytes(bad))
    I2, R2 = _pair()
    m1 = I2.encrypt(b"1"); R2.decrypt(m1)
    with pytest.raises(ChannelError):
        R2.decrypt(m1)


def test_channel_rejects_wrong_peer():
    a, b, evil = new_static(), new_static(), new_static()
    I = SecureChannel(True, a, fingerprint(pub_from_priv(b)))
    R = SecureChannel(False, evil, fingerprint(pub_from_priv(a)))
    R.read_handshake(I.write_handshake())
    with pytest.raises(ChannelError):
        I.read_handshake(R.write_handshake())


def test_panic_flows(clock):
    log = []
    p = PanicController(lambda: log.append("soft"), lambda: log.append("erase"), clock=clock)
    assert p.button_press() == "none"             # no hard panic without soft first
    assert p.button_hold(1.2) == "soft"
    p.button_press(); clock.advance(1); p.button_press(); clock.advance(1)
    assert p.button_press() == "hard" and log == ["soft", "erase"]


def test_panic_slow_presses_do_not_erase(clock):
    log = []
    p = PanicController(lambda: log.append("soft"), lambda: log.append("erase"), clock=clock)
    p.button_hold(1.0)
    for _ in range(3):
        p.button_press(); clock.advance(3)
    assert "erase" not in log


def test_volume_soft_only_and_failed_unlock_wipe(clock):
    log = []
    p = PanicController(lambda: log.append("soft"), lambda: log.append("erase"), clock=clock)
    for _ in range(5):
        p.volume_down()
    assert log == ["soft"]
    for _i in range(9):
        assert p.unlock_result(False).startswith("failed")
    assert p.unlock_result(False) == "erased" and log[-1] == "erase"


def test_remote_wipe_signed():
    k = SigningKey.generate()
    log = []
    p = PanicController(lambda: None, lambda: log.append("erase"))
    cmd = b"ASB-WIPE:" + b"n1"
    assert not p.remote_wipe(cmd, SigningKey.generate().sign(cmd).signature, k.verify_key, b"n1")
    assert not p.remote_wipe(cmd, k.sign(cmd).signature, k.verify_key, b"n2")
    assert p.remote_wipe(cmd, k.sign(cmd).signature, k.verify_key, b"n1") and log == ["erase"]


SECRET_NAMES = r"(key|tag|mac|secret|digest|token|sig)"


def test_constant_time_lint():
    """No `==`/`!=` comparisons on secret-named variables in the security/store code."""
    rx = re.compile(rf"\b\w*{SECRET_NAMES}\w*\s*[!=]=|[!=]=\s*\w*{SECRET_NAMES}\b", re.I)
    bad = []
    for p in Path("asb").rglob("*.py"):
        for n, line in enumerate(p.read_text().splitlines(), 1):
            code = line.split("#")[0]
            if rx.search(code) and "len(" not in code and "is None" not in code and '"' not in code:
                bad.append(f"{p}:{n}: {line.strip()}")
    assert not bad, bad


def test_no_plaintext_on_disk(db):
    from asb.store.sightings import SightingLog, GpsFix
    c = hc.HashChain(os.urandom(32), SigningKey.generate())
    log = SightingLog(db, c)
    log.add({"signature": "A1", "note": "CANARY-7f3a"}, GpsFix(38.123456, -85.654321, "3d"))
    raw = Path(db.path).read_bytes() + (Path(db.path + "-wal").read_bytes() if Path(db.path + "-wal").exists() else b"")
    assert b"CANARY-7f3a" not in raw and b"38.123456" not in raw
