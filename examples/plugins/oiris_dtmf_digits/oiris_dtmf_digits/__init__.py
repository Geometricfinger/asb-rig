"""Reference `speech_recognizer` plugin (Apache-2.0, no model, no training data).

Recognises keypad (DTMF) tones with the Goertzel algorithm. It is NOT speech recognition: it
exists to prove the slot contract end to end with real audio, and as the smallest template
for your own recogniser. Copy this package, replace `transcribe`, keep `register`.
"""
from __future__ import annotations
import numpy as np
from oiris.registry import PluginMeta
from oiris.slots import Transcript

LOW, HIGH = (697, 770, 852, 941), (1209, 1336, 1477)
KEYS = {(697, 1209): "1", (697, 1336): "2", (697, 1477): "3", (770, 1209): "4", (770, 1336): "5",
        (770, 1477): "6", (852, 1209): "7", (852, 1336): "8", (852, 1477): "9", (941, 1336): "0"}


def _power(x: np.ndarray, sr: int, f: float) -> float:
    k = 2 * np.cos(2 * np.pi * f / sr)
    s1 = s2 = 0.0
    for v in x:
        s1, s2 = float(v) + k * s1 - s2, s1
    return s1 * s1 + s2 * s2 - k * s1 * s2


def tone(digits: str, sr: int = 8000, on: float = 0.08, off: float = 0.06, lead: float = 0.0) -> np.ndarray:
    inv = {v: k for k, v in KEYS.items()}
    t = np.arange(int(on * sr)) / sr
    parts = [np.zeros(int(lead * sr))]
    for d in digits:
        lo, hi = inv[d]
        parts += [0.4 * (np.sin(2 * np.pi * lo * t) + np.sin(2 * np.pi * hi * t)), np.zeros(int(off * sr))]
    return np.concatenate(parts).astype(np.float32)


class DtmfRecognizer:
    name = "dtmf_digits"

    def __init__(self, frame_s: float = 0.04, min_energy: float = 1e-3):
        self.frame_s, self.min_energy = frame_s, min_energy

    def transcribe(self, audio, sample_rate: int, t0: float) -> Transcript:
        x = np.asarray(audio, np.float64)
        n = max(1, int(self.frame_s * sample_rate))
        out, prev, start = [], None, None
        for i in range(0, len(x) - n + 1, n):
            fr = x[i:i + n]
            key = None
            if float(np.mean(fr * fr)) > self.min_energy:
                lo = max(LOW, key=lambda f: _power(fr, sample_rate, f))
                hi = max(HIGH, key=lambda f: _power(fr, sample_rate, f))
                key = KEYS.get((lo, hi))
            if key and key != prev:
                out.append(key)
                if start is None:
                    start = t0 + i / sample_rate
            prev = key
        return Transcript(" ".join(out), start if start is not None else t0 + len(x) / sample_rate, 1.0 if out else 0.0)


META = PluginMeta(license="Apache-2.0", data_tier="none", commercial_ok=True,
                  source="examples/plugins/oiris_dtmf_digits (this repo)")


def register(r) -> None:
    r.register("speech_recognizer", "dtmf_digits", DtmfRecognizer, port_version="1.0", meta=META)
