"""M-15 app gate (host side). The phone uses BiometricPrompt BIOMETRIC_STRONG bound to a
Keystore key (see android/). On the Pi/Mac tool the gate is passphrase -> KeyStore.unlock,
with the 10-failure crypto-erase from PanicController. UI-only checks are not trusted:
data is unreadable without the key."""
from __future__ import annotations
import time

from ..security.keys import KeyStore, KeyStoreError
from ..security.panic import PanicController


class AppGate:
    def __init__(self, ks: KeyStore, panic: PanicController, auto_lock_s: float = 60, clock=time.monotonic):
        self.ks, self.panic, self.auto_lock_s, self.clock = ks, panic, auto_lock_s, clock
        self._last = None

    def unlock(self, passphrase: str) -> bool:
        try:
            self.ks.unlock(passphrase)
        except KeyStoreError:
            self.panic.unlock_result(False)
            return False
        self.panic.unlock_result(True)
        self._last = self.clock()
        return True

    def touch(self) -> None:
        self._last = self.clock()

    def background_tick(self) -> None:
        if self._last is not None and self.clock() - self._last >= self.auto_lock_s:
            self.lock()

    def lock(self) -> None:
        self.ks.lock()
        self._last = None

    @property
    def unlocked(self) -> bool:
        try:
            _ = self.ks.master
            return True
        except KeyStoreError:
            return False
