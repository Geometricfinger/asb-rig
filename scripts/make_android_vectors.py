#!/usr/bin/env python3
"""Generate shared vectors the Kotlin core (android/core, JVM-checked) must reproduce:
  tests/vectors/ble_framing.json   - BLE GATT segmenting of Noise frames (oiris/link/ble.py)
  tests/vectors/thermal_render.json - thermal grid -> grayscale / colour pixels (oiris/ui/glasses.thermal_image)
  tests/vectors/eye_android.json   - blinks + dark-pupil diameter (oiris/features/eye.py)
usage: make_android_vectors.py [--check]"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from oiris.features.eye import blinks, pupil_diameter_px  # noqa: E402
from oiris.link.ble import segment  # noqa: E402
from oiris.ui.glasses import thermal_image  # noqa: E402


def ble() -> dict:
    cases = []
    for n, mtu, seq0 in [(1, 23, 0), (17, 23, 250), (300, 23, 7), (1000, 247, 0), (4000, 185, 255)]:
        frame = bytes((i * 31 + 7) % 256 for i in range(n))
        cases.append({"frame": frame.hex(), "mtu": mtu, "seq0": seq0, "segments": [s.hex() for s in segment(frame, mtu, seq0)]})
    return {"cases": cases}


def thermal() -> dict:
    rng = np.random.default_rng(42)
    cases = []
    for h, w in [(4, 4), (6, 8), (24, 32)]:
        f = np.round(rng.normal(25, 6, (h, w)), 2)
        g = thermal_image(f, False)
        c = thermal_image(f, True)
        cases.append({"h": h, "w": w, "celsius": f.ravel().tolist(), "gray": g.ravel().tolist(), "rgb": c.reshape(-1, 3).ravel().tolist()})
    flat = np.full((3, 3), 30.0)
    cases.append({"h": 3, "w": 3, "celsius": flat.ravel().tolist(), "gray": thermal_image(flat, False).ravel().tolist(),
                  "rgb": thermal_image(flat, True).reshape(-1, 3).ravel().tolist()})
    return {"cases": cases}


def eye() -> dict:
    rng = np.random.default_rng(7)
    bl = []
    for fps in (30.0, 60.0):
        o = np.ones(int(fps * 6))
        for start, dur in [(int(fps), 0.12), (int(2.5 * fps), 0.03), (int(4 * fps), 0.8), (int(5 * fps), 0.3)]:
            o[start:start + max(1, int(dur * fps))] = 0.05
        o = np.clip(o + rng.normal(0, 0.02, o.size), 0, 1).round(3)
        bl.append({"fps": fps, "openness": o.tolist(), "blinks": [list(map(int, b)) for b in blinks(o, fps)]})
    pu = []
    for r in (3, 6, 9):
        y, x = np.mgrid[:32, :40]
        roi = np.full((32, 40), 170.0) + rng.normal(0, 4, (32, 40))
        roi[(y - 16) ** 2 + (x - 20) ** 2 <= r * r] = 30
        roi = np.clip(roi, 0, 255).astype(int)
        d, q = pupil_diameter_px(roi.astype(float))
        pu.append({"h": 32, "w": 40, "roi": roi.ravel().tolist(), "diameter": d, "quality": q})
    return {"blinks": bl, "pupil": pu}


def main() -> int:
    out = {"ble_framing.json": ble(), "thermal_render.json": thermal(), "eye_android.json": eye()}
    check = "--check" in sys.argv
    bad = 0
    for name, d in out.items():
        p = ROOT / "tests/vectors" / name
        txt = json.dumps(d, separators=(",", ":")) + "\n"
        if check:
            if not p.exists() or p.read_text() != txt:
                print(f"stale: {p}"); bad += 1
        else:
            p.write_text(txt)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
