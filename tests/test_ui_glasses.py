"""C7 tokens rules and the simulated glasses display (G1-G6)."""
import copy
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from oiris.guard.vocabulary import VocabularyViolation
from oiris.ui import tokens as T
from oiris.ui.glasses import GlassesState, LayoutError, check_layout, render, thermal_image, zones


def test_tokens_pass_rules_and_contrast():
    t = T.load()
    assert T.contrast(t["color"]["text"], t["color"]["bg"]) >= 4.5
    assert abs(T.contrast("#FFFFFF", "#000000") - 21) < 0.01


@pytest.mark.parametrize("mut", [
    lambda t: t["color"].__setitem__("text", "#333333"),
    lambda t: t["alert_levels"]["low"].__setitem__("shape", "triangle"),
    lambda t: t["alert_levels"]["medium"].__setitem__("word", "Medium robot"),
    lambda t: t["color"].__setitem__("surface", t["color"]["alert"]["low"]),
    lambda t: t["type"].__setitem__("glasses_body", 14),
    lambda t: t["motion"].__setitem__("max_flashes_per_s", 5),
])
def test_token_rule_violations_rejected(mut):
    t = copy.deepcopy(T.load()); mut(t)
    with pytest.raises(T.TokenError):
        T.validate(t)


def test_layout_keeps_centre_clear_and_zones_disjoint():
    t = T.load(); check_layout(t)
    bad = copy.deepcopy(t); bad["glasses"]["centre_clear_fraction"] = 0.99
    with pytest.raises(LayoutError):
        check_layout(bad)
    assert set(zones(t)) == {"G1", "G2", "G3", "G4", "G5", "G6"}


def test_render_all_zones_valid_svg():
    st = GlassesState(level="medium", alert_text="Cold object near door", new_sighting=True,
                      thermal=np.random.default_rng(0).normal(30, 2, (24, 32)), health={"thermal": "ok", "ble": "degraded"},
                      locked=True, panic_armed=True)
    svg = render(st)
    root = ET.fromstring(svg)
    ids = {e.get("id") for e in root.iter() if e.get("id")}
    assert {"G1", "G2", "G3", "G5", "G6"} <= ids
    assert "Medium signal" in svg and "<polygon" in svg and 'data-mode="grayscale"' in svg


def test_alert_line_word_limit_vocabulary_and_movement():
    with pytest.raises(LayoutError):
        render(GlassesState(level="low", alert_text="one two three four five six seven"))
    with pytest.raises(VocabularyViolation):
        render(GlassesState(level="low", alert_text="robot detected"))
    svg = render(GlassesState(level="low", alert_text="Cold object", moving=True))
    assert 'id="G2"' not in svg and 'id="G1"' in svg


def test_thermal_grayscale_default_and_colour_never_uses_alert_colours():
    f = np.linspace(20, 40, 24 * 32).reshape(24, 32)
    assert thermal_image(f, False).ndim == 2
    col = thermal_image(f, True)
    alerts = {tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in T.load()["color"]["alert"].values()}
    assert not ({tuple(p) for p in col.reshape(-1, 3)} & alerts)


def test_cli_glasses_sim_from_headless_scenario(tmp_path):
    from oiris.cli import main
    out = tmp_path / "g.svg"
    assert main(["glasses-sim", "--scenario", "camera_lens", "--steps", "3", "--out", str(out)]) == 0
    svg = out.read_text()
    ET.fromstring(svg)
    assert "Medium signal" in svg and "robot" not in svg.lower()
