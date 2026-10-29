"""M-02 liveness stacking (HYPOTHESIS module; ships disabled until E-15/E-16 pass).
Reports per-family liveness indicators as observed / not observed; A11 needs >=2
families agreeing that expected indicators are absent. Never a verdict about a person."""
from __future__ import annotations

from ..schema import BENIGN_CAUSES, Health, Score

INDICATOR_OF = {"S_live": ("vital", "pulse"), "S_radar": ("vital", "breathing"), "S_eye": ("eye", "blink"),
                "S_voice": ("voice", "voice liveness"), "S_thermal": ("thermal", "skin-band heat")}


def indicators(scores: list[Score], absent_at: float = 0.5) -> dict:
    out, fams_absent = [], set()
    for s in scores:
        if s.module not in INDICATOR_OF or s.health == Health.FAILED or s.confidence <= 0.1:
            continue
        fam, name = INDICATOR_OF[s.module]
        state = "not observed" if s.value >= absent_at else "observed"
        if state == "not observed":
            fams_absent.add(fam)
        out.append({"indicator": name, "family": fam, "state": state, "score": round(s.value, 4)})
    return {"liveness_indicators": out, "families_absent": sorted(fams_absent),
            "a11": len(fams_absent) >= 2, "benign_causes": BENIGN_CAUSES["A11"],
            "limit": "A silicone mask on a live wearer keeps real eyes, pulse and voice; this stack does not catch it."}
