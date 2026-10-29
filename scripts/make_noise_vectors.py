#!/usr/bin/env python3
"""Generate tests/vectors/noise_xx.json: fixed-key Noise_XX_25519_ChaChaPoly_BLAKE2s vectors
produced by the Python side (noiseprotocol + oiris.security.channel framing). The Kotlin port
(android/core) must reproduce every byte; the Python test re-derives them too."""
from __future__ import annotations
import json, sys
from pathlib import Path

from noise.connection import Keypair, NoiseConnection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from oiris.security.channel import PROTOCOL, fingerprint, pub_from_priv  # noqa: E402

KEYS = {"init_static": "01" * 32, "resp_static": "02" * 32, "init_ephemeral": "03" * 32, "resp_ephemeral": "04" * 32}
PAYLOADS = ["", "", ""]
TRANSPORT = ["hello pod", "C3 event", "x" * 100]


def conn(initiator: bool) -> NoiseConnection:
    n = NoiseConnection.from_name(PROTOCOL)
    n.set_as_initiator() if initiator else n.set_as_responder()
    pre = "init" if initiator else "resp"
    n.set_keypair_from_private_bytes(Keypair.STATIC, bytes.fromhex(KEYS[f"{pre}_static"]))
    n.set_keypair_from_private_bytes(Keypair.EPHEMERAL, bytes.fromhex(KEYS[f"{pre}_ephemeral"]))
    n.start_handshake()
    return n


def generate() -> dict:
    i, r = conn(True), conn(False)
    m1 = i.write_message(); r.read_message(m1)
    m2 = r.write_message(); i.read_message(m2)
    m3 = i.write_message(); r.read_message(m3)
    hs_hash = i.get_handshake_hash().hex()
    msgs = []
    for t in TRANSPORT:   # initiator -> responder, gen 0
        c = i.encrypt(t.encode()); assert r.decrypt(c) == t.encode()
        msgs.append({"dir": "i2r", "gen": 0, "plain": t, "cipher": c.hex()})
    i.noise_protocol.cipher_state_encrypt.rekey(); r.noise_protocol.cipher_state_decrypt.rekey()
    c = i.encrypt(b"after rekey"); assert r.decrypt(c) == b"after rekey"
    msgs.append({"dir": "i2r", "gen": 1, "plain": "after rekey", "cipher": c.hex()})
    c = r.encrypt(b"reply"); assert i.decrypt(c) == b"reply"
    msgs.append({"dir": "r2i", "gen": 0, "plain": "reply", "cipher": c.hex()})
    return {"protocol": PROTOCOL.decode(), "prologue": "", **KEYS,
            "init_static_pub": pub_from_priv(bytes.fromhex(KEYS["init_static"])).hex(),
            "resp_static_pub": pub_from_priv(bytes.fromhex(KEYS["resp_static"])).hex(),
            "init_fingerprint": fingerprint(pub_from_priv(bytes.fromhex(KEYS["init_static"]))),
            "resp_fingerprint": fingerprint(pub_from_priv(bytes.fromhex(KEYS["resp_static"]))),
            "handshake": [m1.hex(), m2.hex(), m3.hex()], "handshake_hash": hs_hash, "transport": msgs,
            "framing": "SecureChannel frame = 4-byte big-endian rekey generation || Noise transport ciphertext"}


if __name__ == "__main__":
    out = ROOT / "tests" / "vectors" / "noise_xx.json"
    out.write_text(json.dumps(generate(), indent=1) + "\n", encoding="utf-8")
    print(out)
