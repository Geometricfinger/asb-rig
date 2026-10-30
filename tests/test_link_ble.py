"""Phone<->pod BLE link: segmenting, reassembly, loss handling, and the full Noise_XX channel
over BLE-sized segments on an in-memory loopback (no radio). Shared vectors with Kotlin."""
import json, os, threading
from pathlib import Path

import numpy as np
import pytest

from oiris.link import ble
from oiris.link.pod_service import PodService, serve_once
from oiris.security.channel import Reassembler, SecureChannel, fingerprint, fragment, new_static, pub_from_priv, ChannelError

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("n,mtu", [(1, 23), (19, 23), (20, 23), (5000, 23), (65539, 247), (1000, 517)])
def test_segment_roundtrip_and_att_size(n, mtu):
    frame = os.urandom(n)
    segs = ble.segment(frame, mtu)
    assert all(len(s) <= mtu - 3 for s in segs)
    d = ble.Desegmenter()
    outs = [x for x in (d.feed(s) for s in segs) if x is not None]
    assert outs == [frame] and d.dropped == 0


def test_bad_sizes_refused():
    with pytest.raises(ble.FramingError):
        ble.segment(b"", 23)
    with pytest.raises(ble.FramingError):
        ble.segment(b"x" * (ble.MAX_FRAME + 1), 247)
    with pytest.raises(ble.FramingError):
        ble.segment(b"x", 12)


def test_lost_reordered_and_forged_segments_drop_only_that_frame():
    f1, f2 = os.urandom(900), os.urandom(400)
    s1 = ble.segment(f1, 100, 0); s2 = ble.segment(f2, 100, len(s1))
    d = ble.Desegmenter()
    got = [x for x in (d.feed(s) for s in s1[:2] + s1[3:] + s2) if x is not None]
    assert got == [f2] and d.dropped >= 1
    d = ble.Desegmenter()   # reorder
    seq = s1[:]; seq[1], seq[2] = seq[2], seq[1]
    assert [x for x in (d.feed(s) for s in seq + s2) if x is not None] == [f2]
    d = ble.Desegmenter()   # forged total length
    forged = bytearray(s1[0]); forged[2:6] = (10).to_bytes(4, "big")
    assert [x for x in (d.feed(s) for s in [bytes(forged)] + s1[1:]) if x is not None] == []


def test_shared_vectors_match_python():
    v = json.loads((ROOT / "tests/vectors/ble_framing.json").read_text())
    for c in v["cases"]:
        assert [s.hex() for s in ble.segment(bytes.fromhex(c["frame"]), c["mtu"], c["seq0"])] == c["segments"]


def _paired():
    pod_k, phone_k = new_static(), new_static()
    pod = SecureChannel(False, pod_k, fingerprint(pub_from_priv(phone_k)))
    phone = SecureChannel(True, phone_k, fingerprint(pub_from_priv(pod_k)))
    return pod, phone


@pytest.mark.parametrize("mtu", [23, 185, 247])
def test_noise_channel_over_ble_loopback(mtu):
    pod, phone = _paired()
    phone_link, pod_link = ble.loopback_pair(mtu)
    phone_link.send(phone.write_handshake()); pod.read_handshake(pod_link.receive(1))
    pod_link.send(pod.write_handshake()); phone.read_handshake(phone_link.receive(1))
    phone_link.send(phone.write_handshake()); pod.read_handshake(pod_link.receive(1))
    assert pod.ready and phone.ready
    big = os.urandom(200_000)
    rx = Reassembler(pod)
    for fr in fragment(phone, big):
        phone_link.send(fr)
    out = None
    while out is None:
        out = rx.feed(pod_link.receive(1))
    assert out == big


def test_tampered_segment_is_rejected_by_noise():
    pod, phone = _paired()
    flip = {"on": False}

    def tamper(seg):
        if flip["on"] and len(seg) > 10:
            b = bytearray(seg); b[-1] ^= 1; return bytes(b)
        return seg
    phone_link, pod_link = ble.loopback_pair(64, tamper)
    phone_link.send(phone.write_handshake()); pod.read_handshake(pod_link.receive(1))
    pod_link.send(pod.write_handshake()); phone.read_handshake(phone_link.receive(1))
    phone_link.send(phone.write_handshake()); pod.read_handshake(pod_link.receive(1))
    flip["on"] = True
    phone_link.send(phone.encrypt(b"hello pod"))
    with pytest.raises(ChannelError):
        pod.decrypt(pod_link.receive(1))


def test_pod_service_thermal_over_ble_end_to_end():
    pod, phone = _paired()
    phone_link, pod_link = ble.loopback_pair(185)
    phone_link.send(phone.write_handshake()); pod.read_handshake(pod_link.receive(1))
    pod_link.send(pod.write_handshake()); phone.read_handshake(phone_link.receive(1))
    phone_link.send(phone.write_handshake()); pod.read_handshake(pod_link.receive(1))
    frame = np.round(np.random.default_rng(1).normal(24, 3, (24, 32)), 1)
    svc = PodService(thermal=lambda: frame)
    t = threading.Thread(target=serve_once, args=(pod, Reassembler(pod), pod_link, svc))
    t.start()
    for fr in fragment(phone, b'{"op":"thermal"}'):
        phone_link.send(fr)
    rx, resp = Reassembler(phone), None
    while resp is None:
        resp = rx.feed(phone_link.receive(2))
    t.join(2)
    r = json.loads(resp)
    assert r["ok"] and (r["h"], r["w"]) == (24, 32)
    assert np.allclose(np.array(r["celsius"]).reshape(24, 32), frame)
    assert json.loads(svc.handle('{"op":"nope"}'))["ok"] is False
    assert json.loads(PodService().handle('{"op":"thermal"}'))["w"] is None


def test_gatt_uuids_shared_with_kotlin():
    kt = (ROOT / "android/core/src/main/kotlin/org/oiris/core/BleFraming.kt").read_text()
    for u in (ble.SERVICE_UUID, ble.RX_CHAR_UUID, ble.TX_CHAR_UUID):
        assert u in kt
