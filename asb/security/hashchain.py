"""Tamper-evident log: h_i = HMAC-SHA256(k_log, h_{i-1} || canonical(record_i)).
Head (index, hash) signed with Ed25519 and anchored periodically. Verification
detects edits, deletions, reordering and truncation past the last anchor."""
from __future__ import annotations
import hashlib, hmac, json
from dataclasses import dataclass, field
from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

from .ct import equal

GENESIS = b"\x00" * 32


def canonical(rec: dict) -> bytes:
    return json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass
class Anchor:
    idx: int
    head: bytes
    sig: bytes


@dataclass
class HashChain:
    key: bytes
    signer: SigningKey
    entries: list = field(default_factory=list)   # (record, h_this)
    anchors: list = field(default_factory=list)
    anchor_every: int = 100

    def append(self, rec: dict) -> bytes:
        prev = self.entries[-1][1] if self.entries else GENESIS
        h = hmac.new(self.key, prev + canonical(rec), hashlib.sha256).digest()
        self.entries.append((rec, h))
        if len(self.entries) % self.anchor_every == 0:
            self.anchor()
        return h

    def anchor(self) -> Anchor:
        idx = len(self.entries)
        head = self.entries[-1][1] if self.entries else GENESIS
        a = Anchor(idx, head, self.signer.sign(idx.to_bytes(8, "big") + head).signature)
        self.anchors.append(a)
        return a


class ChainInvalid(ValueError):
    pass


def verify(entries: list, key: bytes, anchors: list, verify_key: VerifyKey) -> int:
    prev = GENESIS
    heads = {}
    for i, (rec, h) in enumerate(entries, 1):
        exp = hmac.new(key, prev + canonical(rec), hashlib.sha256).digest()
        if not equal(exp, h):
            raise ChainInvalid(f"entry {i} does not chain")
        heads[i] = h
        prev = h
    for a in anchors:
        try:
            verify_key.verify(a.idx.to_bytes(8, "big") + a.head, a.sig)
        except BadSignatureError:
            raise ChainInvalid("anchor signature bad") from None
        if a.idx > len(entries):
            raise ChainInvalid(f"truncated past anchor {a.idx}")
        if a.idx and not equal(heads[a.idx], a.head):
            raise ChainInvalid(f"anchor {a.idx} head mismatch")
    return len(entries)
