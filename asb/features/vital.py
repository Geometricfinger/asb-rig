"""Vital-sign features: rPPG (POS method, Wang et al. 2017; own implementation; patent
status UNVERIFIED, see THIRD_PARTY) and mmWave breathing band power."""
from __future__ import annotations
import numpy as np


def pos_pulse(rgb_means: np.ndarray, fps: float, win_s: float = 1.6) -> np.ndarray:
    """rgb_means: (N,3) skin-ROI mean colour per frame -> pulse signal."""
    n, win = len(rgb_means), max(2, int(win_s * fps))
    h = np.zeros(n)
    P = np.array([[0, 1, -1], [-2, 1, 1]], dtype=float)
    for t in range(0, n - win + 1):
        c = rgb_means[t:t + win].T
        cn = c / (c.mean(axis=1, keepdims=True) + 1e-9)
        s = P @ cn
        p = s[0] + (s[0].std() / (s[1].std() + 1e-9)) * s[1]
        h[t:t + win] += p - p.mean()
    return h


def band_snr(sig: np.ndarray, fps: float, lo: float, hi: float) -> tuple[float, float]:
    """Peak SNR within [lo,hi] Hz; returns (snr_db, peak_hz)."""
    if len(sig) < 8:
        return 0.0, 0.0
    sig = sig - sig.mean()
    spec = np.abs(np.fft.rfft(sig * np.hanning(len(sig)))) ** 2
    f = np.fft.rfftfreq(len(sig), 1 / fps)
    band = (f >= lo) & (f <= hi)
    if not band.any():
        return 0.0, 0.0
    k = np.argmax(np.where(band, spec, 0))
    near = (np.abs(f - f[k]) <= 0.1)
    sig_p = spec[near].sum()
    noise_p = spec[band & ~near].sum() + 1e-12
    return float(10 * np.log10(sig_p / noise_p + 1e-12)), float(f[k])


def absence_score(snr_db: float, present_db: float = 3.0) -> float:
    """0 when the vital rhythm is clearly present, 1 when absent."""
    return float(np.clip((present_db - snr_db) / present_db, 0, 1))
