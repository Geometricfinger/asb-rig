import json
import socket
import pytest

from asb.config import Config, ConfigError
from asb.modules.voice import VoiceOutput, NullTts
from asb.modules.appgate import AppGate
from asb.security.keys import KeyStore
from asb.security.panic import PanicController
from asb import headless, cli
from asb.adapters import drivers


def test_config_defaults_and_validation(tmp_path):
    c = Config.load(None)
    assert c.thermal_palette == "grayscale" and c.retention_days == 30
    assert not c.enabled("M-01") and c.enabled("M-03")
    for bad in [{"retention_days": 0}, {"min_families_for_alert": 1}, {"thermal_palette": "rainbow"},
                {"flags": {"M-99": True}}, {"rekey_messages": 5000}, {"pled_duty_cap": 0.5}]:
        p = tmp_path / "c.json"; p.write_text(json.dumps(bad))
        with pytest.raises(ConfigError):
            Config.load(p)
    p = tmp_path / "ok.json"; p.write_text(json.dumps({"flags": {"M-04": False, "M-01": True}, "unknown_key": 1}))
    c = Config.load(p)
    assert c.enabled("M-04") and c.enabled("M-01")     # security cannot be disabled


def test_feature_flags_disable_modules():
    from asb.engine import Engine
    c = Config(); c.flags["M-03"] = False; c.flags["M-07"] = False
    names = {m.name for m in Engine(c).score_modules}
    assert "S_rf_drift" not in names and "S_newobj" not in names and "S_eye" not in names
    c.flags["M-01"] = True
    assert "S_eye" in {m.name for m in Engine(c).score_modules}


def test_voice_tiers(clock):
    t = NullTts(); hap = []
    v = VoiceOutput(t, lambda: hap.append(1), clock=clock)
    assert v.announce("fyi", "rf_near") == "haptic" and hap and not t.spoken
    assert v.announce("attention", "glint", direction="ahead", distance="one metre") == "spoken"
    assert v.announce("attention", "rf_near") == "queued"
    with pytest.raises(PermissionError):
        v.announce("confirmed", "confirm", what="camera lens")
    assert v.announce("confirmed", "confirm", confirm_token=True, what="camera lens") == "barged_in"
    assert t.stopped == 1
    v.tick(); assert t.spoken[-1].startswith("Confirmed")
    v.acknowledge(); clock.advance(11); v.tick()
    assert t.spoken[-1] == "Radio device nearby"


def test_voice_rejects_online_tts():
    class Online(NullTts):
        offline = False
    with pytest.raises(ValueError):
        VoiceOutput(Online())


def test_app_gate(tmp_path, clock):
    ks = KeyStore(tmp_path / "k.json"); ks.create("pw"); ks.lock()
    erased = []
    gate = AppGate(ks, PanicController(lambda: None, lambda: (erased.append(1), ks.crypto_erase()), clock=clock), clock=clock)
    assert gate.unlock("pw") and gate.unlocked
    clock.advance(61); gate.background_tick()
    assert not gate.unlocked
    for _ in range(10):
        assert not gate.unlock("nope")
    assert erased and not ks.exists()


def test_headless_deterministic_and_offline():
    a = headless.run_scenario("camera_lens", 3)
    b = headless.run_scenario("camera_lens", 3)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    with headless.no_network():
        with pytest.raises(headless.NetworkBlocked):
            socket.create_connection(("127.0.0.1", 9), timeout=0.1)


def test_led_stub():
    with pytest.raises(AssertionError):
        headless.LedStub().on()


def test_cli(tmp_path, capsys):
    out = tmp_path / "o.json"
    assert cli.main(["--headless", "--scenario", "warm_prop", "--steps", "2", "--out", str(out)]) == 0
    assert cli.main(["--headless", "--scenario", "warm_prop", "--steps", "2", "--expect", str(out)]) == 0
    assert cli.main(["--headless", "--scenario", "quiet", "--steps", "2", "--expect", str(out)]) == 1
    assert cli.main(["check-phrases"]) == 0
    bad = tmp_path / "bad.json"; bad.write_text('{"retention_days": -1}')
    assert cli.main(["--config", str(bad), "version"]) == 2


def test_golden_suite(tmp_path):
    """E-23 in miniature: every committed golden expectation reproduces exactly."""
    from pathlib import Path
    root = Path("golden/expected")
    files = sorted(root.glob("*.json"))
    assert files, "golden expectations missing"
    for f in files:
        assert headless.run_scenario(f.stem, 3) == json.loads(f.read_text()), f.stem


def test_led_duty_cap(clock):
    class Pwm:
        def on(self): pass
        def off(self): pass
    led = drivers.IrLed(18, pwm=Pwm(), clock=clock)
    on_ok = 0
    for _ in range(100):
        if led.on():
            on_ok += 1
            clock.advance(0.05); led.off(); clock.advance(0.05)
        else:
            clock.advance(0.1)
    assert led.duty() <= 0.25 + 1e-9
    with pytest.raises(ValueError):
        drivers.IrLed(18, duty_cap=0.5, pwm=Pwm())


def test_nmea_parser():
    s = "GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,"
    cs = 0
    for ch in s:
        cs ^= ord(ch)
    fix = drivers.parse_nmea(f"${s}*{cs:02X}")
    assert abs(fix["lat"] - 48.1173) < 1e-3 and abs(fix["lon"] - 11.5167) < 1e-3
    assert drivers.parse_nmea(f"${s}*00") is None
    assert drivers.parse_nmea("garbage") is None
    nf = "GPGGA,123519,,,,,0,00,,,M,,M,,"
    c2 = 0
    for ch in nf:
        c2 ^= ord(ch)
    assert drivers.parse_nmea(f"${nf}*{c2:02X}")["quality"] == "no_fix"


def test_mr60_parser():
    import struct
    data = struct.pack("<f", 14.5)
    head = bytes([0x01, 0x00, 0x01]) + struct.pack(">HH", 4, 0x0A14)
    hck = (~(sum(head) & 0xFF)) & 0xFF
    dck = (~(sum(data) & 0xFF)) & 0xFF
    assert drivers.parse_mr60_frame(head + bytes([hck]) + data + bytes([dck]))["breath_rate"] == pytest.approx(14.5)
    assert drivers.parse_mr60_frame(head + bytes([0]) + data + bytes([dck])) is None
    assert drivers.parse_mr60_frame(b"\x02") is None


def test_iw_parser():
    txt = "BSS aa:bb:cc:dd:ee:ff(on wlan0)\n\tTSF: 123456789 usec (0d, 00:02:03)\n\tsignal: -48.00 dBm\nBSS 11:22:33:44:55:66(on wlan0)\n\tsignal: -80.00 dBm\n"
    r = drivers.parse_iw_scan(txt)
    assert r[0]["tsf_us"] == 123456789 and r[0]["rssi"] == -48 and r[1]["tsf_us"] is None


def test_model_slot(tmp_path):
    import hashlib
    from asb.models import ModelSlot, load_into
    w = tmp_path / "m.bin"; w.write_bytes(b"weights")
    man = {"name": "eye", "version": "1", "license": "Apache-2.0", "file": "m.bin",
           "sha256": hashlib.sha256(b"weights").hexdigest(), "hypothesis": "h", "output_range": [0, 1], "data_tier": "synthetic"}
    (tmp_path / "m.json").write_text(json.dumps(man))

    class M:
        def predict(self, x): return 0.4
    slot = load_into(ModelSlot("eye"), tmp_path / "m.json", lambda p, m: M())
    assert slot.status == "active" and slot.predict(None) == 0.4
    w.write_bytes(b"tampered")
    load_into(slot, tmp_path / "m.json", lambda p, m: M())
    assert slot.status == "last_good" and slot.predict(None) == 0.4
    man["license"] = "CC-BY-NC-4.0"; (tmp_path / "n.json").write_text(json.dumps(man))
    assert load_into(ModelSlot("x"), tmp_path / "n.json", lambda p, m: M()).status == "disabled"

    class Bad:
        def predict(self, x): return 7.0
    s2 = ModelSlot("b", Bad(), status="active")
    assert s2.predict(None) is None
