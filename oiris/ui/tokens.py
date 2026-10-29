"""C7 design tokens: load and enforce the Module Map 6.1 rules (contrast, reserved alert colours,
three levels with shape + word, <=6 type sizes, glasses one size up, no flashing)."""
from __future__ import annotations
import json
from pathlib import Path

PATH = Path(__file__).with_name("design_tokens.json")
LEVELS = ("low", "medium", "confirmed")


class TokenError(ValueError):
    pass


def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def validate(t: dict) -> dict:
    c = t["color"]
    if contrast(c["text"], c["bg"]) < 4.5 or contrast(c["text_muted"], c["bg"]) < 4.5:
        raise TokenError("body text below 4.5:1")
    if set(t["alert_levels"]) != set(LEVELS) or set(c["alert"]) != set(LEVELS):
        raise TokenError("exactly three alert levels: low, medium, confirmed")
    shapes = {v["shape"] for v in t["alert_levels"].values()}
    if len(shapes) != 3:
        raise TokenError("each level needs a distinct shape (colour is redundant only)")
    for lv, v in t["alert_levels"].items():
        if "robot" in v["word"].lower() or "signal" not in v["word"].lower():
            raise TokenError(f"{lv}: level words use 'signal', never 'robot'")
        if contrast(c["alert"][lv], c["bg"]) < 3.0:
            raise TokenError(f"{lv}: alert colour below 3:1")
    reserved = {v.upper() for v in c["alert"].values()}
    if any(isinstance(v, str) and v.upper() in reserved for k, v in c.items() if k != "alert"):
        raise TokenError("alert colours are reserved")
    ty = t["type"]
    if len(ty["scale_px"]) > 6 or ty["glasses_body"] <= ty["phone_body"]:
        raise TokenError("type scale <=6 sizes; glasses one size up from phone")
    if ty["glasses_body"] not in ty["scale_px"] or ty["phone_body"] not in ty["scale_px"]:
        raise TokenError("body sizes must come from the scale")
    if t["motion"]["max_flashes_per_s"] > 3 or t["touch_target_dp"] < 48:
        raise TokenError("motion/touch-target rule")
    return t


def load(path: str | Path = PATH) -> dict:
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))
