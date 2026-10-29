"""M-03 passive RF features: BLE advertising behaviour, AP clock skew (TSF), drift and
coarse device type. Fixed emitters on the owner's premises only; rotating random
addresses are counted, never followed. Identifiers are stored only as HMACs."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

# Bluetooth SIG company identifiers (public assigned numbers; small excerpt)
COMPANY_TYPES = {0x004C: "phone_or_wearable", 0x0006: "pc_or_peripheral", 0x0075: "phone_or_wearable",
                 0x00E0: "phone_or_wearable", 0x02E5: "iot_module", 0x0059: "iot_module",
                 0x0157: "fitness_wearable", 0x038F: "smart_home"}
UUID_TYPES = {"180d": "fitness_wearable", "fe9f": "beacon", "feaa": "beacon", "1812": "pc_or_peripheral",
              "180f": "battery_device", "fd6f": "phone_or_wearable"}
TYPES = {"phone_or_wearable", "pc_or_peripheral", "iot_module", "fitness_wearable", "beacon", "smart_home",
         "access_point", "camera_like", "battery_device", "unknown"}
CAMERA_OUI_HINTS: set[str] = set()   # populated by site config; empty by default (no vendor lists shipped)


def adv_features(times_s: list[float], tx_power: list[int | None], rssi: list[int], payload_len: list[int]) -> dict:
    t = np.asarray(times_s, float)
    d = np.diff(t) if len(t) > 1 else np.array([0.0])
    tx = [x for x in tx_power if x is not None]
    return {"interval_mean": float(d.mean()), "interval_jitter": float(d.std()),
            "tx_power": float(np.mean(tx)) if tx else 0.0, "rssi_mean": float(np.mean(rssi)) if rssi else 0.0,
            "payload_len": float(np.median(payload_len)) if payload_len else 0.0}


def clock_skew_ppm(tsf_us: list[int], local_s: list[float]) -> float:
    """Jana & Kasera 2008: slope of (TSF - local) vs local time, in ppm."""
    x = np.asarray(local_s, float)
    y = np.asarray(tsf_us, float) / 1e6 - x
    if len(x) < 3:
        return 0.0
    slope = np.polyfit(x - x[0], y - y[0], 1)[0]
    return float(slope * 1e6)


@dataclass
class EmitterBaseline:
    mean: dict
    std: dict
    n_windows: int


def build_baseline(windows: list[dict]) -> EmitterBaseline:
    keys = windows[0].keys()
    return EmitterBaseline({k: float(np.mean([w[k] for w in windows])) for k in keys},
                           {k: float(np.std([w[k] for w in windows])) for k in keys}, len(windows))


@dataclass
class DriftDetector:
    """A9: >=2 features outside k-sigma for >=3 consecutive windows."""
    baseline: EmitterBaseline
    k: float = 3.0
    min_features: int = 2
    min_windows: int = 3
    floor: dict = field(default_factory=lambda: {"interval_mean": 0.005, "interval_jitter": 0.005, "tx_power": 1.0,
                                                  "rssi_mean": 3.0, "payload_len": 0.5, "skew_ppm": 0.5})
    _run: int = 0

    def update(self, w: dict) -> tuple[bool, list[str]]:
        changed = [f for f, v in w.items() if f in self.baseline.mean and
                   abs(v - self.baseline.mean[f]) > self.k * max(self.baseline.std[f], self.floor.get(f, 1e-6))]
        self._run = self._run + 1 if len(changed) >= self.min_features else 0
        return self._run >= self.min_windows, changed


def device_type(company_id: int | None = None, service_uuids: list[str] | None = None, is_ap: bool = False,
                oui: str | None = None) -> str:
    if is_ap:
        return "camera_like" if oui and oui.lower() in CAMERA_OUI_HINTS else "access_point"
    for u in service_uuids or []:
        u = u.lower(); t = UUID_TYPES.get(u[4:8] if len(u) > 8 else u[-4:])
        if t:
            return t
    if company_id is not None and company_id in COMPANY_TYPES:
        return COMPANY_TYPES[company_id]
    return "unknown"
