"""M-06 voice output with tiered barge-in. Tiers describe signatures, never people.
FYI: haptic only. ATTENTION: whitelisted phrase, queued, <=1 per 10 s.
CONFIRMED: needs an operator confirmation token; barges in and repeats until ack.
TTS backends sit behind the `tts` port; GPL engines (Piper, eSpeak NG) are excluded."""
from __future__ import annotations
import collections, time
from typing import Any, Callable, Protocol

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
    """Flite (CMU, BSD-style licence; Debian package `flite`) as a subprocess on the Pi/host.
    `out_dir` set -> every utterance is synthesised to a WAV there instead of the speaker
    (used by tests and headless runs, where there is no audio device)."""
    offline = True

    def __init__(self, voice: str | None = None, out_dir: str | None = None, binary: str = "flite"):
        import shutil
        self.bin = shutil.which(binary)
        if not self.bin:
            raise RuntimeError("flite not installed")
        self.voice, self.out_dir = voice, out_dir
        self._p: Any = None
        self.files: list[str] = []

    def _cmd(self, text: str, out: str | None) -> list[str]:
        cmd = [str(self.bin)] + (["-voice", self.voice] if self.voice else []) + ["-t", text]
        return cmd + (["-o", out] if out else [])

    def synthesize(self, text: str, path: str, timeout_s: float = 30.0) -> str:
        """Blocking synthesis to a 16-bit PCM WAV file; returns the path."""
        import subprocess
        subprocess.run(self._cmd(text, path), check=True, timeout=timeout_s, capture_output=True)
        return path

    def speak(self, text: str) -> None:
        import os, subprocess
        self.stop()
        out = None
        if self.out_dir:
            out = os.path.join(self.out_dir, f"utt{len(self.files):04d}.wav")
            self.files.append(out)
        self._p = subprocess.Popen(self._cmd(text, out), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait(self, timeout_s: float = 30.0) -> None:
        if self._p:
            self._p.wait(timeout=timeout_s)

    def stop(self) -> None:
        if self._p and self._p.poll() is None:
            self._p.terminate()
            self._p.wait(timeout=5)


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
