"""Whitelisted voice/display phrase templates (M-06). No free text is ever spoken."""
from __future__ import annotations
import string

from .vocabulary import check_text

TEMPLATES = {
    "glint": "Candidate camera lens {direction}, {distance}",
    "ir_emitter": "Infrared emitter {direction}",
    "thermal": "Unusual heat pattern {direction}",
    "rf_near": "Radio device nearby",
    "rf_drift": "Known device changed",
    "new_object": "New object at {anchor}",
    "liveness": "Expected signals not observed: {signals}",
    "eye": "Eye signals unusual, check lighting",
    "voice": "Voice signals not observed",
    "health": "Sensor {sensor} offline",
    "confirm": "Confirmed by operator: {what}",
    "panic": "Locked",
}
SLOT_VALUES = {
    "direction": {"ahead", "at left", "at right", "behind", "above", "below"},
    "distance": {"half a metre", "one metre", "two metres", "three metres", "far"},
    "anchor": {f"anchor {i}" for i in range(1, 7)},
    "signals": {"pulse", "blink", "pulse, blink", "breathing", "pulse, breathing", "blink, breathing"},
    "sensor": {"thermal", "camera", "eye camera", "radio", "radar", "microphone", "GPS"},
    "what": {"camera lens", "infrared emitter", "radio device", "new object", "heat source"},
}
MAX_WORDS = 8


class PhraseError(ValueError):
    pass


def render(key: str, **slots: str) -> str:
    if key not in TEMPLATES:
        raise PhraseError(f"no template {key}")
    tpl = TEMPLATES[key]
    needed = {f for _, f, _, _ in string.Formatter().parse(tpl) if f}
    if set(slots) != needed:
        raise PhraseError(f"{key} needs slots {sorted(needed)}")
    for k, v in slots.items():
        if v not in SLOT_VALUES[k]:
            raise PhraseError(f"slot {k}={v!r} not whitelisted")
    out = tpl.format(**slots)
    if len(out.split()) > MAX_WORDS:
        raise PhraseError("phrase too long for glasses/voice budget")
    return check_text(out)


def audit_all() -> None:
    """Build-time check: every template with every slot value passes the guard."""
    import itertools
    for key, tpl in TEMPLATES.items():
        fields = [f for _, f, _, _ in string.Formatter().parse(tpl) if f]
        for combo in itertools.product(*(sorted(SLOT_VALUES[f]) for f in fields)):
            render(key, **dict(zip(fields, combo)))
