"""Key store. On the Pi the data volume is LUKS2 (set up by scripts, not here); this
file keeps a master key wrapped by a passphrase-derived key (scrypt). Crypto-erase =
destroy the wrapped key file (+ LUKS header erase on the Pi), making data unreadable."""
from __future__ import annotations
import json, os, time
from dataclasses import dataclass
from pathlib import Path
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .aead import Sealer


class KeyStoreError(RuntimeError):
    pass


class KeyStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._master: bytes | None = None

    @staticmethod
    def _kdf(passphrase: str, salt: bytes) -> bytes:
        return Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1).derive(passphrase.encode())

    def exists(self) -> bool:
        return self.path.exists()

    def create(self, passphrase: str) -> bytes:
        salt, master = os.urandom(16), Sealer.new_key()
        blob = Sealer(self._kdf(passphrase, salt)).seal(master, b"asb-master")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"v": 1, "salt": salt.hex(), "wrapped": blob.hex()}))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        self._master = master
        return master

    def unlock(self, passphrase: str) -> bytes:
        if not self.exists():
            raise KeyStoreError("no key (erased or never created)")
        d = json.loads(self.path.read_text())
        try:
            self._master = Sealer(self._kdf(passphrase, bytes.fromhex(d["salt"]))).open(bytes.fromhex(d["wrapped"]), b"asb-master")
        except Exception:
            raise KeyStoreError("unlock failed") from None
        return self._master

    # ---- extra key slots (e.g. the Mac Keychain biometric gate), LUKS-keyslot style ----------
    def add_slot(self, name: str, secret: str) -> None:
        """Wrap the (unlocked) master key under another secret. Each slot has its own salt."""
        master = self.master
        d = json.loads(self.path.read_text())
        salt = os.urandom(16)
        blob = Sealer(self._kdf(secret, salt)).seal(master, b"asb-master:" + name.encode())
        d.setdefault("slots", {})[name] = {"salt": salt.hex(), "wrapped": blob.hex()}
        self._write(d)

    def remove_slot(self, name: str) -> None:
        d = json.loads(self.path.read_text())
        if d.get("slots", {}).pop(name, None) is not None:
            self._write(d)

    def slots(self) -> list[str]:
        return sorted(json.loads(self.path.read_text()).get("slots", {})) if self.exists() else []

    def unlock_slot(self, name: str, secret: str) -> bytes:
        if not self.exists():
            raise KeyStoreError("no key (erased or never created)")
        sl = json.loads(self.path.read_text()).get("slots", {}).get(name)
        if sl is None:
            raise KeyStoreError("no such key slot")
        try:
            self._master = Sealer(self._kdf(secret, bytes.fromhex(sl["salt"]))).open(bytes.fromhex(sl["wrapped"]), b"asb-master:" + name.encode())
        except Exception:
            raise KeyStoreError("unlock failed") from None
        return self._master

    def _write(self, d: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    @property
    def master(self) -> bytes:
        if self._master is None:
            raise KeyStoreError("locked")
        return self._master

    def lock(self) -> None:
        self._master = None

    def subkey(self, purpose: str) -> bytes:
        import hashlib, hmac
        return hmac.new(self.master, b"asb-subkey:" + purpose.encode(), hashlib.sha256).digest()

    def crypto_erase(self) -> None:
        """Overwrite then delete the wrapped key. Flash wear-levelling means overwrite is
        best-effort; security comes from the key never existing unwrapped on disk."""
        self._master = None
        if self.path.exists():
            n = self.path.stat().st_size
            with open(self.path, "r+b") as f:
                f.write(os.urandom(n)); f.flush(); os.fsync(f.fileno())
            self.path.unlink()


# ---- Pod<->phone static-key rotation (D-22): 90 days, then re-pair --------------------------
STATIC_MAX_AGE_S = 90 * 86400
STATIC_WARN_S = 7 * 86400           # "re-pair soon" shown during the last week


def static_key_status(created_epoch: float, now: float | None = None, max_age_s: float = STATIC_MAX_AGE_S) -> str:
    """ok | rotate_soon | expired. Expired keys are refused by SecureChannel (re-pair needed)."""
    age = (time.time() if now is None else now) - created_epoch
    if age >= max_age_s:
        return "expired"
    if age >= max_age_s - STATIC_WARN_S:
        return "rotate_soon"
    return "ok"


@dataclass
class PairingRecord:
    static_priv: bytes
    created: float                  # epoch seconds when this static key was generated
    peer_fp: str | None = None      # QR-paired peer fingerprint (None until re-paired)
    paired_at: float | None = None
    previous_peer_fp: str | None = None


class StaticKeyManager:
    """Keeps this device's Noise static key sealed under the KeyStore subkey "noise-static".
    `rotate()` makes a new static key and clears the pairing: the old peer fingerprint is kept
    only as `previous_peer_fp` for the UI, and the channel refuses to run until `complete_repair`
    records the peer fingerprint scanned from the new QR code."""

    def __init__(self, ks: KeyStore, path: str | Path, clock=time.time):
        self.ks, self.path, self.clock = ks, Path(path), clock

    def _sealer(self) -> Sealer:
        return Sealer(self.ks.subkey("noise-static"))

    def _save(self, r: PairingRecord) -> None:
        blob = self._sealer().seal(r.static_priv, b"noise-static")
        d = {"v": 1, "sealed": blob.hex(), "created": r.created, "peer_fp": r.peer_fp,
             "paired_at": r.paired_at, "previous_peer_fp": r.previous_peer_fp}
        tmp = self.path.with_suffix(".tmp")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(d)); os.chmod(tmp, 0o600); tmp.replace(self.path)

    def load(self) -> PairingRecord:
        if not self.path.exists():
            raise KeyStoreError("no static key")
        d = json.loads(self.path.read_text())
        try:
            priv = self._sealer().open(bytes.fromhex(d["sealed"]), b"noise-static")
        except Exception:
            raise KeyStoreError("static key unreadable") from None
        return PairingRecord(priv, d["created"], d["peer_fp"], d["paired_at"], d.get("previous_peer_fp"))

    def create(self) -> PairingRecord:
        from .channel import new_static
        r = PairingRecord(new_static(), self.clock())
        self._save(r)
        return r

    def complete_repair(self, peer_fp: str) -> PairingRecord:
        r = self.load()
        r.peer_fp, r.paired_at = peer_fp, self.clock()
        self._save(r)
        return r

    def status(self) -> str:
        r = self.load()
        if r.peer_fp is None:
            return "unpaired"
        return static_key_status(r.created, self.clock())

    def rotate(self) -> PairingRecord:
        from .channel import new_static
        old = self.load()
        r = PairingRecord(new_static(), self.clock(), None, None, old.peer_fp)
        self._save(r)
        return r

    def rotate_if_due(self) -> bool:
        if self.status() == "expired":
            self.rotate()
            return True
        return False
