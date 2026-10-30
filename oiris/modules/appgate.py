"""M-15 app gate (host side). The phone uses BiometricPrompt BIOMETRIC_STRONG bound to a
Keystore key (see android/). On the Pi/Mac tool the gate is passphrase -> KeyStore.unlock,
with the 10-failure crypto-erase from PanicController. On macOS the gate can also be Touch ID:
a random slot secret lives in the Keychain behind LocalAuthentication (modules/mac_gate.py and
the Swift helper in macos/keychain_gate), and opens a KeyStore key slot. UI-only checks are not trusted:
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

    # ---- macOS Keychain + Touch ID (M-15) --------------------------------------------------
    BIOMETRIC_SLOT = "mac-biometric"

    def enroll_biometric(self, gate) -> str:
        """While unlocked: create a random slot secret, store it in the Keychain behind
        biometrics, and add the matching key slot. Returns the binding strength."""
        import os
        secret = os.urandom(32)
        binding = gate.store(secret)
        self.ks.add_slot(self.BIOMETRIC_SLOT, secret.hex())
        return binding

    def unlock_biometric(self, gate, reason: str = "Unlock O Iris") -> bool:
        from .mac_gate import GateCancelled, GateUnavailable
        try:
            secret = gate.load(reason)
        except (GateCancelled, GateUnavailable):
            return False                       # not an authentication failure; passphrase still works
        except Exception:
            self.panic.unlock_result(False)
            return False
        try:
            self.ks.unlock_slot(self.BIOMETRIC_SLOT, secret.hex())
        except KeyStoreError:
            self.panic.unlock_result(False)
            return False
        self.panic.unlock_result(True)
        self._last = self.clock()
        return True

    def remove_biometric(self, gate) -> None:
        self.ks.remove_slot(self.BIOMETRIC_SLOT)
        gate.delete()
