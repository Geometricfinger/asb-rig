"""Synthetic sensor generators for headless runs and tests (M-09). Scenario names describe
lab proxies (objects and props), never people."""
from __future__ import annotations
import numpy as np

from .base import SimAdapter

SCENARIOS = {"quiet", "camera_lens", "warm_prop", "fixed_emitter_drift", "replay_screen"}


def _frames(rng, lens: bool):
    r = np.random.default_rng(rng.randrange(1 << 30))
    off = r.integers(0, 40, (48, 64)).astype(np.uint8)
    on = np.clip(off.astype(int) + r.integers(0, 15, off.shape), 0, 255).astype(np.uint8)
    if lens:
        on[20:22, 30:32] = 250
    return {"on": on, "off": off}


def make(scenario: str = "quiet", seed: int = 0, period_s: float = 0.0) -> list[SimAdapter]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario}")
    lens = scenario == "camera_lens"
    warm = scenario == "warm_prop"
    screen = scenario == "replay_screen"

    def nir(t, rng):
        return _frames(rng, lens)

    def therm(t, rng):
        r = np.random.default_rng(rng.randrange(1 << 30))
        f = 21 + r.normal(0, 0.3, (24, 32))
        if warm:
            f[8:16, 10:20] = 41 + r.normal(0, 0.3, (8, 10))   # too hot for a skin band, e.g. a heater
        return {"frame_c": f}

    def rf(t, rng):
        em = [{"key": "own-ap", "rssi": -70, "self": True}]
        if lens:
            em.append({"key": "k-" + str(rng.randrange(3)), "rssi": -50})
        return {"emitters": em}

    def drift(t, rng):
        return {"drift": ["k1"] if scenario == "fixed_emitter_drift" else []}

    def radar(t, rng):
        return {"breath_snr_db": 0.5 if (warm or screen) else 8.0, "range_m": 0.8}

    def eye_(t, rng):
        code = [rng.randrange(2) for _ in range(30)]
        present = [0] * 30 if screen else code
        return {"led_code": code, "glint_present": present, "blink_rate": 0 if screen else 15, "pupil_q": 0.8}

    def skin(t, rng):
        fps, n = 30.0, 300
        tt = np.arange(n) / fps
        pulse = 0 if (screen or warm) else 0.004 * np.sin(2 * np.pi * 1.2 * tt)
        r = np.random.default_rng(rng.randrange(1 << 30))
        base = np.array([150, 110, 90], float)
        rgb = base * (1 + np.outer(pulse, [0.33, 0.77, 0.53]) + r.normal(0, 0.0005, (n, 3)))
        return {"rgb_means": rgb, "fps": fps}

    def voice(t, rng):
        return {"spoof": 0.9 if screen else 0.1}

    def motion(t, rng):
        return {"jerk": 0.1}

    def site(t, rng):
        return {"new_emitters": 1 if lens else 0, "new_thermal": 1 if warm else 0, "new_glints": 0}

    specs = [("sim_nir", {"nir_pair"}, nir), ("sim_thermal", {"thermal_frame"}, therm), ("sim_ble", {"rf_adv"}, rf),
             ("sim_rf_drift", {"rf_drift"}, drift), ("sim_radar", {"radar"}, radar), ("sim_eye", {"eye"}, eye_),
             ("sim_skin", {"skin_rgb"}, skin), ("sim_voice", {"voice_feat"}, voice), ("sim_motion", {"motion"}, motion),
             ("sim_site", {"site_diff"}, site)]
    return [SimAdapter(i, c, f, period_s=period_s, seed=seed + k) for k, (i, c, f) in enumerate(specs)]
