"""AES-256-GCM at rest with random 96-bit nonces and a per-key message cap so a nonce
is never reused (NIST SP 800-38D limit 2^32 random nonces per key; we cap far lower)."""
from __future__ import annotations
import os, threading
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_MESSAGES_PER_KEY = 2 ** 24
VERSION = b"\x01"


class KeyExhausted(RuntimeError):
    pass


class Sealer:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("AES-256 key must be 32 bytes")
        self._aes = AESGCM(key)
        self._n = 0
        self._seen: set[bytes] = set()
        self._lock = threading.Lock()

    def seal(self, plaintext: bytes, aad: bytes = b"") -> bytes:
        with self._lock:
            if self._n >= MAX_MESSAGES_PER_KEY:
                raise KeyExhausted("rotate key")
            while True:
                nonce = os.urandom(12)
                if nonce not in self._seen:
                    break
            self._seen.add(nonce)
            self._n += 1
        return VERSION + nonce + self._aes.encrypt(nonce, plaintext, aad)

    def open(self, blob: bytes, aad: bytes = b"") -> bytes:
        if blob[:1] != VERSION:
            raise ValueError("unknown ciphertext version")
        return self._aes.decrypt(blob[1:13], blob[13:], aad)

    @staticmethod
    def new_key() -> bytes:
        return AESGCM.generate_key(bit_length=256)
