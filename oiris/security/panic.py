"""Kill switch, panic gesture and failed-unlock wipe (D-23). Crypto-erase only."""
from __future__ import annotations
import hmac, time
from typing import Callable

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


class PanicController:
    """Pod button: hold >=1 s -> soft panic; then 3 presses within 5 s -> hard panic (erase).
    Phone: 5x volume-down -> soft panic only. 10 failed unlocks -> erase. A signed wipe
    command from the paired phone -> erase."""

    def __init__(self, soft: Callable[[], None], erase: Callable[[], None], fail_limit: int = 10,
                 clock=time.monotonic):
        self.soft, self.erase, self.fail_limit, self.clock = soft, erase, fail_limit, clock
        self.soft_active_since: float | None = None
        self._presses: list[float] = []
        self._vol: list[float] = []
        self.failed_unlocks = 0
        self.erased = False

    def button_hold(self, seconds: float) -> str:
        if seconds >= 1.0:
            self.soft()
            self.soft_active_since = self.clock()
            self._presses.clear()
            return "soft"
        return "none"

    def button_press(self) -> str:
        now = self.clock()
        if self.soft_active_since is None:
            return "none"           # hard panic requires soft panic first (double step)
        self._presses = [t for t in self._presses if now - t <= 5.0] + [now]
        if len(self._presses) >= 3 and now - self._presses[0] <= 5.0:
            self._do_erase()
            return "hard"
        return "pending"

    def volume_down(self) -> str:
        now = self.clock()
        self._vol = [t for t in self._vol if now - t <= 3.0] + [now]
        if len(self._vol) >= 5:
            self._vol.clear()
            self.soft()
            return "soft"
        return "none"

    def unlock_result(self, ok: bool) -> str:
        if ok:
            self.failed_unlocks = 0
            self.soft_active_since = None
            return "ok"
        self.failed_unlocks += 1
        if self.failed_unlocks >= self.fail_limit:
            self._do_erase()
            return "erased"
        return f"failed {self.failed_unlocks}/{self.fail_limit}"

    def remote_wipe(self, command: bytes, signature: bytes, phone_key: VerifyKey, expect_nonce: bytes) -> bool:
        if not command.startswith(b"ASB-WIPE:") or not hmac.compare_digest(command[9:], expect_nonce):
            return False
        try:
            phone_key.verify(command, signature)
        except BadSignatureError:
            return False
        self._do_erase()
        return True

    def _do_erase(self) -> None:
        if not self.erased:
            self.erase()
            self.erased = True
