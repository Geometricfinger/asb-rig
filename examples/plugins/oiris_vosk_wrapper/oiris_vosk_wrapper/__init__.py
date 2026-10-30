"""Wrapper `speech_recognizer` plugin for a Vosk-style local engine. Ships NO engine and NO
weights. You install the engine (`pip install vosk`, Apache-2.0) and download a model yourself,
then declare that model's licence in config options; O Iris records and warns on it.

config.json:
  "plugins": {"slots": {"speech_recognizer": "vosk"},
              "options": {"vosk": {"model_dir": "~/models/vosk-en", "model_license": "Apache-2.0",
                                   "data_tier": "unknown", "commercial_ok": false}}}
"""
from __future__ import annotations
import json
import numpy as np
from oiris.registry import PluginMeta
from oiris.slots import Transcript

GRAMMAR = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "oh", "[unk]"]


class VoskRecognizer:
    name = "vosk"

    def __init__(self, model_dir: str, model_license: str = "unknown", data_tier: str = "unknown",
                 commercial_ok: bool = False):
        import os
        import vosk  # imported only when the user selects this slot
        self.meta = PluginMeta(model_license, data_tier, commercial_ok, source=model_dir)
        self._model = vosk.Model(os.path.expanduser(model_dir))
        self._vosk = vosk

    def transcribe(self, audio, sample_rate: int, t0: float) -> Transcript:
        rec = self._vosk.KaldiRecognizer(self._model, sample_rate, json.dumps(GRAMMAR))
        rec.SetWords(True)
        pcm = (np.clip(np.asarray(audio, np.float32), -1, 1) * 32767).astype("<i2").tobytes()
        rec.AcceptWaveform(pcm)
        res = json.loads(rec.FinalResult())
        words = res.get("result", [])
        start = t0 + float(words[0]["start"]) if words else t0 + len(audio) / sample_rate
        conf = float(np.mean([w.get("conf", 0.0) for w in words])) if words else 0.0
        return Transcript(res.get("text", ""), start, conf)


def register(r) -> None:
    # Code licence here is Apache-2.0; the MODEL you point it at carries its own terms, declared
    # in options and surfaced as a startup warning by `oiris plugins`.
    r.register("speech_recognizer", "vosk", VoskRecognizer, port_version="1.0",
               meta=PluginMeta("Apache-2.0", "unknown", commercial_ok=False,
                               source="user-supplied Vosk model; check its licence"))
