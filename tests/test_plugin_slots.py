"""Swap contract (ADR-0055): every model slot can be filled by a third-party plugin via config
alone, emptied without breaking anything, and plugin licences are declared and surfaced."""
from __future__ import annotations
import subprocess, sys, textwrap
from pathlib import Path

import numpy as np
import pytest

from oiris.config import Config, ConfigError
from oiris.fusion.stack import FusionModel
from oiris.modules.liveness import DigitChallenge, digit_score, indicators
from oiris.registry import PluginMeta, Registry, RegistryError, default_registry
from oiris.slots import SLOTS, SlotManager, Transcript

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples/plugins/oiris_dtmf_digits"))
import oiris_dtmf_digits as dtmf  # noqa: E402

CUSTOM = textwrap.dedent('''
    import numpy as np
    from oiris.registry import PluginMeta
    from oiris.slots import Transcript
    from oiris.fusion.stack import FusionModel
    META = PluginMeta("LicenseRef-Acme-Proprietary", "own_recorded", commercial_ok=True, source="acme")
    class Asr:
        name = "acme_asr"
        def __init__(self, text="1 2 3 4", delay=0.5): self.text, self.delay = text, delay
        def transcribe(self, audio, sr, t0): return Transcript(self.text, t0 + self.delay, 0.9)
    class Spoof:
        name = "acme_spoof"
        def spoof_score(self, audio, sr): return 0.25
    class Spk:
        name, dim = "acme_spk", 4
        def embed(self, audio, sr): return np.ones(4)
    class Eye:
        name = "acme_eye"
        def predict(self, f): return 0.75
    class Fw:
        name = "acme_fw"
        def load(self): return FusionModel(version="acme-1")
    def register(r):
        r.register("speech_recognizer", "acme_asr", Asr, port_version="1.0", meta=META)
        r.register("voice_antispoof", "acme_spoof", Spoof, port_version="1.0", meta=META)
        r.register("speaker_embed", "acme_spk", Spk, port_version="1.0", meta=META)
        r.register("eye_model", "acme_eye", Eye, port_version="1.0", meta=META)
        r.register("fusion_weights", "acme_fw", Fw, port_version="1.0", meta=META)
''')
SLOTSCFG = {"speech_recognizer": "acme_asr", "voice_antispoof": "acme_spoof", "speaker_embed": "acme_spk",
            "eye_model": "acme_eye", "fusion_weights": "acme_fw"}


@pytest.fixture
def plugin_file(tmp_path):
    p = tmp_path / "acme_plugin.py"
    p.write_text(CUSTOM, encoding="utf-8")
    return f"{p}:register"


def manager(plugin_file, slots=None):
    cfg = Config(plugins={"paths": [plugin_file], "entry_points": False, "slots": slots or dict(SLOTSCFG)}).validate()
    return SlotManager.from_config(cfg)


def test_custom_plugin_fills_every_slot_from_config_only(plugin_file):
    sm = manager(plugin_file)
    a = np.zeros(800, np.float32)
    assert sm.transcribe(a, 8000, 10.0) == Transcript("1 2 3 4", 10.5, 0.9)
    assert sm.spoof_score(a, 8000) == 0.25
    assert sm.speaker_embedding(a, 8000).tolist() == [1, 1, 1, 1]
    assert sm.eye_score({}) == 0.75
    assert sm.fusion_model().version == "acme-1"
    assert all(sm.status[s] == "active" for s in SLOTSCFG)
    # proprietary but commercial_ok: loads, flagged because licence is outside the bundled allow-list
    assert any("acme_asr" in w and "LicenseRef-Acme-Proprietary" in w for w in sm.registry.warnings)


def test_removing_each_slot_degrades_gracefully(plugin_file):
    sm = manager(plugin_file)
    for s in SLOTSCFG:
        sm.remove(s)
    a = np.zeros(10)
    assert sm.transcribe(a, 8000, 0) is None and sm.spoof_score(a, 8000) is None
    assert sm.speaker_embedding(a, 8000) is None and sm.eye_score({}) is None
    assert sm.fusion_model().version == FusionModel().version   # back to the documented prior
    ch = DigitChallenge(clock=lambda: 0.0)
    res = ch.verify_audio(ch.issue().nonce, a, 8000, sm)
    assert res.state == "unavailable"
    ind = indicators([digit_score(res)])
    assert ind["liveness_indicators"] == [] and ind["a11"] is False   # no indicator, never a verdict


def test_unknown_or_broken_plugin_empties_only_its_slot(tmp_path, plugin_file):
    bad = tmp_path / "bad.py"
    bad.write_text(textwrap.dedent('''
        from oiris.registry import PluginMeta
        M = PluginMeta("MIT", "synthetic", True)
        class Crash:
            name = "crash"
            def spoof_score(self, a, sr): raise RuntimeError("boom")
        class Nan:
            name = "nan"
            def predict(self, f): return float("nan")
        class NotAsr:
            name = "notasr"
        def register(r):
            r.register("voice_antispoof", "crash", Crash, port_version="1.0", meta=M)
            r.register("eye_model", "nan", Nan, port_version="1.0", meta=M)
            r.register("speech_recognizer", "notasr", NotAsr, port_version="1.0", meta=M)
    '''), encoding="utf-8")
    cfg = Config(plugins={"paths": [f"{bad}:register", plugin_file, "/nope/missing.py:register"], "entry_points": False,
                          "slots": {"voice_antispoof": "crash", "eye_model": "nan", "speech_recognizer": "notasr",
                                    "speaker_embed": "not_installed", "fusion_weights": "acme_fw"}}).validate()
    sm = SlotManager.from_config(cfg)
    assert any("missing.py" in w for w in sm.registry.warnings)
    a = np.zeros(10)
    assert sm.spoof_score(a, 8000) is None and sm.status["voice_antispoof"].startswith("failed")
    assert sm.eye_score({}) is None
    assert sm.transcribe(a, 8000, 0) is None and "does not implement" in sm.status["speech_recognizer"]
    assert sm.speaker_embedding(a, 8000) is None
    assert sm.fusion_model().version == "acme-1"   # healthy neighbour unaffected


def test_headless_engine_runs_with_slots_misconfigured(tmp_path):
    from oiris.headless import run_scenario
    cfg = Config(plugins={"slots": {s: "does_not_exist" for s in SLOTS if s != "face_match"}}).validate()
    assert run_scenario("quiet", 2, config=cfg)


def test_reference_dtmf_plugin_drives_the_digit_challenge():
    r = Registry()
    dtmf.register(r)
    sm = SlotManager(r, {"speech_recognizer": "dtmf_digits"})
    clock = [100.0]
    ch = DigitChallenge(clock=lambda: clock[0])
    p = ch.issue()
    audio = dtmf.tone(p.digits, lead=0.6)
    clock[0] += 2.0
    res = ch.verify_audio(p.nonce, audio, 8000, sm)
    assert res.state == "observed", res
    p2 = ch.issue()
    wrong = "".join(str((int(c) + 1) % 10) for c in p2.digits)
    assert ch.verify_audio(p2.nonce, dtmf.tone(wrong, lead=0.6), 8000, sm).state == "not observed"
    assert ch.verify_audio(p.nonce, audio, 8000, sm).state == "rejected"   # replay


def test_entry_point_plugin_registers_without_editing_core(monkeypatch):
    class EP:
        name = "dtmf_digits"
        def load(self):
            return dtmf.register

    class EPS:
        def select(self, group):
            assert group == "oiris.plugins"
            return [EP()]
    import oiris.registry as reg
    monkeypatch.setattr(reg.metadata, "entry_points", lambda: EPS())
    r = default_registry({"slots": {"speech_recognizer": "dtmf_digits"}})
    assert "dtmf_digits" in r.names("speech_recognizer") and r.warnings == []   # clean licence: no warning


def test_noncommercial_external_plugin_loads_with_warning():
    r = Registry()
    r.register("speaker_embed", "nc", object, port_version="1.0",
               meta=PluginMeta("CC-BY-NC-4.0", "public_noncommercial", commercial_ok=False, source="https://example"))
    assert r.get("speaker_embed", "nc").meta.commercial_ok is False
    assert len(r.warnings) == 1 and "commercial_ok=False" in r.warnings[0] and "NOT FOR COMMERCIAL USE" in r.warnings[0]


def test_licence_rules_still_strict_for_bundled_and_dishonest_metadata():
    r = Registry()
    with pytest.raises(RegistryError):   # bundled path (no meta) keeps the allow-list
        r.register("face_match", "nc", object, port_version="1.0", license="CC-BY-NC-4.0")
    with pytest.raises(RegistryError):   # slot plugins must declare metadata
        r.register("speech_recognizer", "x", object, port_version="1.0")
    with pytest.raises(RegistryError):   # cannot claim commercial_ok for NC terms
        r.register("eye_model", "x", object, port_version="1.0", meta=PluginMeta("CC-BY-NC-4.0", "synthetic", True))
    with pytest.raises(RegistryError):
        r.register("eye_model", "x", object, port_version="1.0", meta=PluginMeta("MIT", "public_noncommercial", True))
    with pytest.raises(RegistryError):
        r.register("eye_model", "x", object, port_version="1.0", meta=PluginMeta("MIT", "bogus-tier", True))
    with pytest.raises(RegistryError):
        r.register("speaker_embed", "x", object, port_version="2.0", meta=PluginMeta("MIT", "none", True))


def test_face_match_backend_swapped_by_one_setting():
    from oiris.modules import face_match_gate
    seen = []

    class Reg:
        def create(self, port, name):
            seen.append((port, name)); raise LookupError("stop here")
    cfg = Config(plugins={"slots": {"face_match": "my_face"}}).validate()
    cfg.flags["M-16"] = True
    with pytest.raises(LookupError):
        face_match_gate.load(cfg, None, None, Reg())
    assert seen == [("face_match", "my_face")]


def test_config_rejects_bad_plugin_settings():
    with pytest.raises(ConfigError):
        Config(plugins={"slots": {"not_a_slot": "x"}}).validate()
    with pytest.raises(ConfigError):
        Config(plugins={"paths": ["no_colon"]}).validate()
    with pytest.raises(ConfigError):
        Config(plugins={"bogus": 1}).validate()


def test_no_model_weights_are_committed():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    exts = (".onnx", ".pt", ".pth", ".tflite", ".pb", ".safetensors", ".ckpt", ".gguf", ".h5", ".mdl")
    assert [f for f in files if f.lower().endswith(exts)] == []


def test_cli_lists_slots(plugin_file, tmp_path, capsys):
    import json
    from oiris.cli import main
    c = tmp_path / "c.json"
    c.write_text(json.dumps({"plugins": {"paths": [plugin_file], "entry_points": False, "slots": SLOTSCFG}}))
    assert main(["plugins", "--config", str(c)]) == 0
    out = capsys.readouterr()
    assert "speech_recognizer  -> acme_asr" in out.out and "[active]" in out.out
    assert "LicenseRef-Acme-Proprietary" in out.err
