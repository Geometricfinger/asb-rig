"""M-01 real-signal ingestion: load eye-tracker recordings and run the M-01 eye features on
them, scoring against the recording's own reference events.

Supported now: the Tobii Pro Glasses 2 export format used by the LaborTrack dataset
(Latifzadeh et al., 2025; raw data CC BY 4.0 on Zenodo 15163456, preprocessed CSVs MIT on
GitHub kayhan-latifzadeh/LaborTrack; participants gave written consent per the paper), and a
generic CSV (`t_ms,openness[,pupil,gaze_x,gaze_y]`) for the project's own recordings once the
eye camera exists. Nothing here is a person-level verdict; outputs are signal statistics."""
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .eye import blinks


@dataclass
class EyeRecording:
    t_ms: np.ndarray           # sample times (ms, monotonic)
    openness: np.ndarray       # 0 closed / no eye .. 1 open
    pupil: np.ndarray | None   # diameter (unit per source) or None
    fps: float
    source: str


def _fps(t_ms: np.ndarray) -> float:
    d = np.diff(t_ms)
    return float(1000.0 / np.median(d[d > 0])) if d.size else 0.0


def load_tobii_labortrack(pupil_csv: str | Path) -> EyeRecording:
    """validity 0 = valid; anything else = eye not tracked (closed lid or lost)."""
    t, op, pu = [], [], []
    with open(pupil_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t.append(float(r["timestamp"]))
            valid = r["validity_left"] == "0" or r["validity_right"] == "0"
            op.append(1.0 if valid else 0.0)
            pl, pr = float(r["pupil_left"]), float(r["pupil_right"])
            pu.append(np.nan if not valid else np.nanmean([x if x > 0 else np.nan for x in (pl, pr)] or [np.nan]))
    ta = np.asarray(t)
    return EyeRecording(ta - ta[0], np.asarray(op), np.asarray(pu), _fps(ta), f"tobii:{Path(pupil_csv).name}")


def load_generic(path: str | Path) -> EyeRecording:
    a = np.genfromtxt(path, delimiter=",", names=True)
    t = np.asarray(a["t_ms"], float)
    pupil = np.asarray(a["pupil"], float) if "pupil" in (a.dtype.names or ()) else None
    return EyeRecording(t - t[0], np.clip(np.asarray(a["openness"], float), 0, 1), pupil, _fps(t), f"generic:{Path(path).name}")


def load_reference_blinks(blinks_csv: str | Path, t0_ms: float) -> list[tuple[float, float]]:
    with open(blinks_csv, newline="", encoding="utf-8") as f:
        return [(float(r["start"]) - t0_ms, float(r["end"]) - t0_ms) for r in csv.DictReader(f)]


def detected_blinks_ms(rec: EyeRecording, **kw) -> list[tuple[float, float]]:
    """Run eye.blinks() on the recording; returns (start_ms, end_ms) events."""
    return [(float(rec.t_ms[s]), float(rec.t_ms[min(e, len(rec.t_ms) - 1)])) for s, e in blinks(rec.openness, rec.fps, **kw)]


def agreement(det: list[tuple[float, float]], ref: list[tuple[float, float]], tol_ms: float = 20.0) -> dict:
    """Event-level precision/recall: a detection matches a reference blink if they overlap
    (with `tol_ms` slack). Each reference matches at most one detection."""
    used: set[int] = set()
    tp = 0
    for ds, de in det:
        for i, (rs, re_) in enumerate(ref):
            if i not in used and ds <= re_ + tol_ms and rs <= de + tol_ms:
                used.add(i); tp += 1; break
    p = tp / len(det) if det else 0.0
    r = tp / len(ref) if ref else 0.0
    return {"detected": len(det), "reference": len(ref), "matched": tp, "precision": p, "recall": r}


def summary(rec: EyeRecording, det: list[tuple[float, float]]) -> dict:
    mins = (rec.t_ms[-1] - rec.t_ms[0]) / 60000 if len(rec.t_ms) > 1 else 0.0
    pu = rec.pupil[np.isfinite(rec.pupil)] if rec.pupil is not None else np.array([])
    return {"source": rec.source, "fps": round(rec.fps, 2), "minutes": round(float(mins), 2),
            "blink_rate_per_min": round(float(len(det) / mins), 2) if mins else None,
            "pupil_median": float(np.median(pu)) if pu.size else None,
            "valid_fraction": round(float(rec.openness.mean()), 4)}
