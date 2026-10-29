"""Key store. On the Pi the data volume is LUKS2 (set up by scripts, not here); this
file keeps a master key wrapped by a passphrase-derived key (scrypt). Crypto-erase =
destroy the wrapped key file (+ LUKS header erase on the Pi), making data unreadable."""
from __future__ import annotations
import json, os
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
