"""Built-in score modules. Each consumes samples whose `data` is a dict with the keys
listed in its docstring. Real adapters, replay files and sim generators all produce
the same dict shapes (C2), so modules cannot tell them apart."""
from __future__ import annotations
import numpy as np
from typing import Any

from ..features import optical, thermal, eye, vital, baseline
from ..schema import Health, Sample, Score


def _no_data(name: str) -> Score:
    return Score(name, 0.0, 0.0, Health.DEGRADED, {"reason": "no samples"})


class GlintScore:
    """data: {"on": 2D uint8, "off": 2D uint8}"""
    name, inputs, module_flag = "S_glint", {"nir_pair"}, None

    def update(self, w: list[Sample]) -> Score:
        if not w:
            return _no_data(self.name)
        d = w[-1].data
        c = optical.glint_candidates(np.asarray(d["on"]), np.asarray(d["off"]))
        v, conf = optical.glint_score(c)
        return Score(self.name, v, conf, evidence={"candidates": len(c)})


class NirEmitScore:
    """data: {"off": 2D uint8}"""
    name, inputs, module_flag = "S_nir_emit", {"nir_pair"}, None

    def update(self, w):
        if not w:
            return _no_data(self.name)
        v, c = optical.nir_emitter_score(np.asarray(w[-1].data["off"]))
        return Score(self.name, v, c)


class ThermalScore:
    """data: {"frame_c": 2D float °C}"""
    name, inputs, module_flag = "S_thermal", {"thermal_frame"}, None

    def update(self, w):
        if not w:
            return _no_data(self.name)
        f = np.asarray(w[-1].data["frame_c"], float)
        st = thermal.roi_stats(f)
        hot = f[f > st["ambient"] + 3]
        v, c = thermal.skin_range_score(hot) if hot.size else (0.0, 0.3)
        return Score(self.name, v, c, evidence={"max_c": st["max"], "hot_px": st["hot_px"]})


class RfScore:
    """data: {"emitters": [{"key","rssi",...}]}: near, unknown emitters raise A4."""
    name, inputs, module_flag = "S_rf", {"rf_adv"}, None

    def update(self, w):
        if not w:
            return _no_data(self.name)
        em = w[-1].data.get("emitters", [])
        near = [e for e in em if e.get("rssi", -100) > -60 and not e.get("self", False)]
        return Score(self.name, min(1.0, 0.5 * len(near)), 0.6, evidence={"near": len(near)})


class RfDriftScore:
    """data: {"drift": [emitter_key, ...]} from the fingerprint module (M-03)."""
    name, inputs, module_flag = "S_rf_drift", {"rf_drift"}, "M-03"

    def update(self, w):
        if not w:
            return _no_data(self.name)
        n = len(w[-1].data.get("drift", []))
        return Score(self.name, 1.0 if n else 0.0, 0.8, evidence={"drifted": n})


class RadarScore:
    """data: {"breath_snr_db": float, "range_m": float}; A5 only within 1 m."""
    name, inputs, module_flag = "S_radar", {"radar"}, None

    def update(self, w):
        if not w:
            return _no_data(self.name)
        d = w[-1].data
        if d.get("range_m", 9) > 1.0:
            return Score(self.name, 0.0, 0.1, evidence={"note": "out of range"})
        return Score(self.name, vital.absence_score(d["breath_snr_db"]), 0.6)


class MotionScore:
    """data: {"jerk": float} normalised irregularity from frames+IMU."""
    name, inputs, module_flag = "S_motion", {"motion"}, None

    def update(self, w):
        if not w:
            return _no_data(self.name)
        return Score(self.name, float(w[-1].data.get("jerk", 0.0)), 0.3)


class EyeScore:
    """data: {"led_code": [0/1], "glint_present": [0/1], "blink_rate": float|None, "pupil_q": float}"""
    name, inputs, module_flag = "S_eye", {"eye"}, "M-01"

    def update(self, w):
        if not w:
            return _no_data(self.name)
        d = w[-1].data
        follow = eye.glint_code_follow(np.asarray(d["led_code"]), np.asarray(d["glint_present"]))
        v, c = eye.eye_score(follow, d.get("blink_rate"), d.get("pupil_q", 0.5))
        return Score(self.name, v, c, evidence={"glint_follow": follow})


class LiveScore:
    """data: {"rgb_means": (N,3), "fps": float} -> rPPG pulse absence (vital family)."""
    name, inputs, module_flag = "S_live", {"skin_rgb"}, "M-02"

    def update(self, w):
        if not w:
            return _no_data(self.name)
        d = w[-1].data
        rgb = np.asarray(d["rgb_means"], float)
        snr, hz = vital.band_snr(vital.pos_pulse(rgb, d["fps"]), d["fps"], 0.7, 3.0)
        return Score(self.name, vital.absence_score(snr), 0.5 if len(rgb) >= 3 * d["fps"] else 0.2,
                     evidence={"snr_db": round(snr, 2), "peak_hz": round(hz, 2)})


class VoiceScore:
    """data: {"spoof": float in [0,1]} from the anti-spoof model port. No audio is ever stored."""
    name, inputs, module_flag = "S_voice", {"voice_feat"}, "M-02"

    def update(self, w):
        if not w:
            return _no_data(self.name)
        return Score(self.name, float(w[-1].data["spoof"]), 0.4)


class NewObjScore:
    """data: {"new_emitters": int, "new_thermal": int, "new_glints": int} (M-07)."""
    name, inputs, module_flag = "S_newobj", {"site_diff"}, "M-07"

    def update(self, w):
        if not w:
            return _no_data(self.name)
        d = w[-1].data
        v, c = baseline.newobj_score(d.get("new_emitters", 0), d.get("new_thermal", 0), d.get("new_glints", 0))
        return Score(self.name, v, c)


ALL = [GlintScore, NirEmitScore, ThermalScore, RfScore, RfDriftScore, RadarScore, MotionScore,
       EyeScore, LiveScore, VoiceScore, NewObjScore]


def register(r) -> None:
    cls: Any
    for cls in ALL:
        r.register("score", cls.name, cls, port_version="1.0", module_flag=cls.module_flag)
