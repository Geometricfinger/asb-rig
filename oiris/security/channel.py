"""Pod<->phone encrypted channel: Noise_XX_25519_ChaChaPoly_BLAKE2s with rekey every
1,000 messages or 10 minutes (whichever first). Transport-agnostic (BLE GATT on device;
in-memory pipes in tests). Static keys are verified against the QR-paired fingerprint."""
from __future__ import annotations
import hashlib, time
from noise.connection import NoiseConnection, Keypair
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization

from .ct import equal

PROTOCOL = b"Noise_XX_25519_ChaChaPoly_BLAKE2s"


class ChannelError(RuntimeError):
    pass


def new_static() -> bytes:
    return X25519PrivateKey.generate().private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                                     serialization.NoEncryption())


def fingerprint(static_pub: bytes) -> str:
    return hashlib.blake2s(static_pub, digest_size=16).hexdigest()


class SecureChannel:
    def __init__(self, initiator: bool, static_priv: bytes, expected_peer_fp: str,
                 rekey_messages: int = 1000, rekey_seconds: float = 600, clock=time.monotonic):
        self.n = NoiseConnection.from_name(PROTOCOL)
        self.n.set_as_initiator() if initiator else self.n.set_as_responder()
        self.n.set_keypair_from_private_bytes(Keypair.STATIC, static_priv)
        self.expected = expected_peer_fp
        self.rekey_messages, self.rekey_seconds, self.clock = rekey_messages, rekey_seconds, clock
        self.n.start_handshake()
        proto = self.n.noise_protocol
        orig_done = proto.handshake_done

        def _capture_then_done():  # capture peer static before the library discards state
            pub = getattr(proto.handshake_state.rs, "public_bytes", None)
            if pub is not None:
                self._peer_pub = pub
            orig_done()
        proto.handshake_done = _capture_then_done
        self.initiator = initiator
        self._sent = self._recv = 0
        self._tx_epoch = self._rx_epoch = clock()
        self.rekeys = 0

    # handshake helpers
    def write_handshake(self) -> bytes:
        m = self.n.write_message()
        if self.n.handshake_finished:
            self._check_peer()
        return m

    def read_handshake(self, m: bytes) -> None:
        self.n.read_message(m)
        hs = getattr(self.n.noise_protocol, "handshake_state", None)
        pub = getattr(getattr(hs, "rs", None), "public_bytes", None)
        if pub is not None:
            self._peer_pub = pub
        if getattr(self, "_peer_pub", None) is not None:
            self._check_peer()   # fail as early as the peer's static key is known

    def _check_peer(self) -> None:
        pub = getattr(self, "_peer_pub", None)
        if pub is None:
            raise ChannelError("no peer static key")
        if not equal(fingerprint(pub).encode(), self.expected.encode()):
            raise ChannelError("peer static key does not match paired fingerprint")

    @property
    def ready(self) -> bool:
        return self.n.handshake_finished

    def _maybe_rekey(self, sending: bool) -> None:
        now = self.clock()
        if sending:
            if self._sent >= self.rekey_messages or now - self._tx_epoch >= self.rekey_seconds:
                self.n.noise_protocol.cipher_state_encrypt.rekey()
                self._sent, self._tx_epoch, self.rekeys = 0, now, self.rekeys + 1

    def encrypt(self, data: bytes) -> bytes:
        if not self.ready:
            raise ChannelError("handshake not finished")
        self._maybe_rekey(True)
        self._sent += 1
        # 1-byte header carries the rekey generation so the receiver follows deterministically
        return self.rekeys.to_bytes(4, "big") + self.n.encrypt(data)

    def decrypt(self, msg: bytes) -> bytes:
        gen = int.from_bytes(msg[:4], "big")
        while getattr(self, "_rx_gen", 0) < gen:
            self.n.noise_protocol.cipher_state_decrypt.rekey()
            self._rx_gen = getattr(self, "_rx_gen", 0) + 1
        if gen < getattr(self, "_rx_gen", 0):
            raise ChannelError("stale key generation (replay?)")
        try:
            return self.n.decrypt(msg[4:])
        except Exception as e:
            raise ChannelError(f"decrypt failed: {type(e).__name__}") from None


def pub_from_priv(priv: bytes) -> bytes:
    return X25519PrivateKey.from_private_bytes(priv).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
