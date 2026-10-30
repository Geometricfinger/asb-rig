"""Tamper-evident log: h_i = HMAC-SHA256(k_log, h_{i-1} || canonical(record_i)).
Head (index, hash) signed with Ed25519 and anchored every 100 records AND at least every
60 seconds while records are arriving (`tick()` is the timer hook for idle periods). Verification
detects edits, deletions, reordering and truncation past the last anchor."""
from __future__ import annotations
import hashlib, hmac, json, time
from typing import Callable
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
    anchor_seconds: float = 60.0
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        self._last_anchor_t = self.clock()

    def append(self, rec: dict) -> bytes:
        prev = self.entries[-1][1] if self.entries else GENESIS
        h = hmac.new(self.key, prev + canonical(rec), hashlib.sha256).digest()
        self.entries.append((rec, h))
        if len(self.entries) % self.anchor_every == 0:
            self.anchor()
        else:
            self.tick()
        return h

    def tick(self) -> Anchor | None:
        """60-second anchor timer. Call from the engine loop; anchors only if records were
        added since the last anchor, so an idle log does not grow."""
        if self.clock() - self._last_anchor_t < self.anchor_seconds:
            return None
        last_idx = self.anchors[-1].idx if self.anchors else 0
        if len(self.entries) == last_idx:
            self._last_anchor_t = self.clock()
            return None
        return self.anchor()

    def anchor(self) -> Anchor:
        idx = len(self.entries)
        head = self.entries[-1][1] if self.entries else GENESIS
        a = Anchor(idx, head, self.signer.sign(idx.to_bytes(8, "big") + head).signature)
        self.anchors.append(a)
        self._last_anchor_t = self.clock()
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
