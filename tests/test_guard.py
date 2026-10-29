import pytest
from asb.guard import vocabulary as v, phrases, consent, privacy, radio
from asb.schema import Event, SIGNATURES
import numpy as np


@pytest.mark.parametrize("bad", ["That is a robot", "ANDROID detected", "fake person", "not human", "Humanoid",
                                 "replica", "impostor", "synthetic person", "bot"])
def test_banned_words(bad):
    with pytest.raises(v.VocabularyViolation):
        v.check_text(bad)


def test_benign_words_pass():
    v.check_text("Candidate camera lens at left, one metre")
    v.check_text("Expected signals not observed: pulse, blink")


@pytest.mark.parametrize("field", ["class", "label", "is_human", "is_robot", "identity"])
def test_forbidden_fields(field):
    with pytest.raises(v.VocabularyViolation):
        v.check_output({"x": [{field: 1}]})


def test_all_signature_texts_and_events_clean():
    for code in SIGNATURES:
        v.check_output(Event(code, "fyi", 0.5, [], []).to_dict())


def test_phrase_whitelist():
    phrases.audit_all()
    assert phrases.render("glint", direction="at left", distance="one metre")
    with pytest.raises(phrases.PhraseError):
        phrases.render("glint", direction="robot", distance="one metre")
    with pytest.raises(phrases.PhraseError):
        phrases.render("free text")


def test_consent_required():
    r = consent.ConsentRegistry()
    with pytest.raises(consent.ConsentError):
        r.require(None)
    r.add(consent.ConsentRecord("c1", "S01", {"session"}, expires_utc=2e9))
    assert r.require("c1", now=1e9)
    with pytest.raises(consent.ConsentError):
        r.require("c1", "voice_enroll", now=1e9)
    with pytest.raises(consent.ConsentError):
        r.require("c1", now=3e9)
    seen = []
    r.withdraw_hooks.append(seen.append)
    r.withdraw("c1")
    assert seen == ["c1"]
    with pytest.raises(consent.ConsentError):
        r.require("c1", now=1e9)


def test_privacy_rules():
    with pytest.raises(privacy.PrivacyError):
        privacy.check_persist("audio", False)
    with pytest.raises(privacy.PrivacyError):
        privacy.check_persist("nir_frame", True, np.zeros((480, 640)))
    privacy.check_persist("nir_frame", True, np.zeros((64, 64)))
    privacy.check_persist("nir_frame", False, np.zeros((480, 640)))
    h = privacy.hash_identifier("AA:BB:CC:DD:EE:FF", b"k" * 32)
    assert "AA" not in h and len(h) == 32
    assert privacy.round_gps(38.25671, -85.75943) == (38.26, -85.76)
    assert privacy.round_gps(None, 1.0) == (None, None)


def test_retention(db):
    from asb.guard.retention import purge
    db.execute("INSERT INTO sighting(sighting_id,t_wall,codes,body,verdict) VALUES('old',0,'[]',x'00','benign')")
    db.execute("INSERT INTO sighting(sighting_id,t_wall,codes,body,verdict,keep) VALUES('kept',0,'[]',x'00','benign',1)")
    db.execute("INSERT INTO sighting(sighting_id,t_wall,codes,body,verdict) VALUES('new',?,'[]',x'00','benign')", (1e9,))
    assert purge(db, 30, now=1e9) == 1
    left = {r[0] for r in db.execute("SELECT sighting_id FROM sighting")}
    assert left == {"kept", "new"}


@pytest.mark.parametrize("argv", [["aireplay-ng", "-0"], ["iw", "dev", "wlan0", "set", "type", "monitor"],
                                  ["hackrf_transfer", "-t", "x"], ["rtl_power", "--tx"], ["airmon-ng", "start"], []])
def test_radio_denies(argv):
    with pytest.raises(radio.RadioPolicyError):
        radio.check_command(argv)


def test_radio_allows_passive():
    radio.check_command(["iw", "dev", "wlan0", "scan"])
    radio.check_command(["rtl_power", "-f", "800M:850M:100k", "-1"])


def test_monitor_mode_refusal():
    out = "phy#0\n\tInterface wlan0\n\t\ttype managed\n\tInterface mon0\n\t\ttype monitor\n"
    with pytest.raises(radio.RadioPolicyError):
        radio.assert_passive(out)
    radio.assert_passive("phy#0\n\tInterface wlan0\n\t\ttype managed\n")
