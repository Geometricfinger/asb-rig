"""M-15 macOS Keychain biometric gate (host side of macos/keychain_gate/main.swift).

The Swift helper does the platform work: LocalAuthentication (Touch ID, biometrics only, no
password fallback) and a Keychain generic-password item holding a random 32-byte slot secret.
Signed builds with a keychain-access-group entitlement bind the item to the current biometric
set with SecAccessControl (.biometryCurrentSet) in the data-protection keychain ("keychain-acl").
Unsigned builds cannot use that keychain (errSecMissingEntitlement), so the helper falls back to
a login-keychain item released only after a successful LocalAuthentication check ("la-check",
weaker: another process running as the same user could read the item). The binding is reported,
never hidden. The secret never touches disk outside the Keychain and is passed over pipes only."""
from __future__ import annotations
import json, subprocess
from pathlib import Path

EXIT = {0: "ok", 2: "cancelled", 3: "unavailable", 4: "not_found", 5: "auth_failed"}


class GateError(RuntimeError):
    pass


class GateCancelled(GateError):
    pass


class GateUnavailable(GateError):
    pass


class KeychainBiometricGate:
    def __init__(self, helper: str | Path, service: str = "org.oiris.appgate", account: str = "master-slot",
                 timeout_s: float = 120.0):
        self.helper, self.service, self.account, self.timeout_s = str(helper), service, account, timeout_s

    def _run(self, *args: str, stdin: bytes | None = None) -> dict:
        p = subprocess.run([self.helper, *args, "--service", self.service, "--account", self.account],
                           input=stdin, capture_output=True, timeout=self.timeout_s)
        kind = EXIT.get(p.returncode, "error")
        if kind == "cancelled":
            raise GateCancelled("cancelled by user")
        if kind == "unavailable":
            raise GateUnavailable(p.stderr.decode(errors="replace").strip() or "biometrics unavailable")
        if kind != "ok":
            raise GateError(f"helper {kind} ({p.returncode})")
        try:
            return json.loads(p.stdout.decode() or "{}")
        except ValueError:
            raise GateError("helper returned malformed output") from None

    def status(self) -> dict:
        return self._run("status")

    def store(self, secret: bytes) -> str:
        if len(secret) != 32:
            raise ValueError("slot secret must be 32 bytes")
        return str(self._run("store", stdin=secret.hex().encode()).get("binding", "unknown"))

    def load(self, reason: str = "Unlock O Iris") -> bytes:
        d = self._run("load", "--reason", reason)
        try:
            s = bytes.fromhex(d["secret"])
        except (KeyError, ValueError):
            raise GateError("helper returned no secret") from None
        if len(s) != 32:
            raise GateError("bad secret length")
        return s

    def delete(self) -> None:
        try:
            self._run("delete")
        except GateError:
            pass
