"""M-06 voice output with tiered barge-in. Tiers describe signatures, never people.
FYI: haptic only. ATTENTION: whitelisted phrase, queued, <=1 per 10 s.
CONFIRMED: needs an operator confirmation token; barges in and repeats until ack.
TTS backends sit behind the `tts` port; GPL engines (Piper, eSpeak NG) are excluded."""
from __future__ import annotations
import collections, time
from typing import Callable, Protocol

from ..guard.phrases import render
from ..schema import Level


class Tts(Protocol):
    def speak(self, text: str) -> None: ...
    def stop(self) -> None: ...
    offline: bool


class NullTts:
    offline = True

    def __init__(self):
        self.spoken: list[str] = []
        self.stopped = 0

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        self.stopped += 1


class FliteTts:
    """Flite (BSD-style) as a subprocess on the Pi."""
    offline = True

    def __init__(self):
        import shutil
        if not shutil.which("flite"):
            raise RuntimeError("flite not installed")
        self._p = None

    def speak(self, text: str) -> None:
        import subprocess
        self.stop()
        self._p = subprocess.Popen(["flite", "-t", text])

    def stop(self) -> None:
        if self._p and self._p.poll() is None:
            self._p.terminate()


class VoiceOutput:
    def __init__(self, tts: Tts, haptic: Callable[[], None] = lambda: None, min_interval_s: float = 10.0,
                 clock=time.monotonic):
        if not getattr(tts, "offline", False):
            raise ValueError("only offline TTS voices are allowed")
        self.tts, self.haptic, self.min_interval_s, self.clock = tts, haptic, min_interval_s, clock
        self._last_attention = -1e9
        self.queue: collections.deque = collections.deque(maxlen=5)
        self.pending_confirmed: str | None = None
        self.log: list[tuple[str, str]] = []

    def announce(self, level: Level | str, key: str, confirm_token: bool = False, **slots: str) -> str:
        level = Level(level)
        if level == Level.FYI:
            self.haptic(); self.log.append(("fyi", key)); return "haptic"
        text = render(key, **slots)
        if level == Level.ATTENTION:
            now = self.clock()
            if now - self._last_attention < self.min_interval_s:
                self.queue.append(text); return "queued"
            self._last_attention = now
            self.tts.speak(text); self.log.append(("attention", text)); return "spoken"
        if not confirm_token:
            raise PermissionError("confirmed tier requires operator confirmation")
        self.tts.stop()          # barge-in
        self.tts.speak(text)
        self.pending_confirmed = text
        self.log.append(("confirmed", text))
        return "barged_in"

    def tick(self) -> None:
        """Called by the engine loop: repeat unacknowledged confirmed, drain attention queue."""
        if self.pending_confirmed:
            self.tts.speak(self.pending_confirmed); return
        if self.queue and self.clock() - self._last_attention >= self.min_interval_s:
            self._last_attention = self.clock()
            self.tts.speak(self.queue.popleft())

    def acknowledge(self) -> None:
        self.pending_confirmed = None
        self.tts.stop()
