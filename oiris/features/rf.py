"""M-03 passive RF features: BLE advertising behaviour, AP clock skew (TSF), drift and
coarse device type. Fixed emitters on the owner's premises only; rotating random
addresses are counted, never followed. Identifiers are stored only as HMACs."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

def _load_tables() -> dict:
    import json
    from importlib import resources
    return json.loads(resources.files("oiris.features").joinpath("rf_tables.json").read_text(encoding="utf-8"))


_T = _load_tables()
RF_TABLE_SOURCES: dict = _T["sources"]
# Bluetooth SIG company identifiers -> coarse type (IDs from the SIG Assigned Numbers registry;
# types are our curation). Regenerate with scripts/make_rf_tables.py.
COMPANY_TYPES: dict[int, str] = {int(k, 16): v["type"] for k, v in _T["company_types"].items()}
UUID_TYPES = {"180d": "fitness_wearable", "fe9f": "beacon", "feaa": "beacon", "1812": "pc_or_peripheral",
              "180f": "battery_device", "fd6f": "phone_or_wearable", "1808": "medical_device", "1810": "medical_device",
              "181f": "medical_device", "1816": "fitness_wearable", "1818": "fitness_wearable", "1826": "fitness_wearable",
              "1822": "medical_device", "110b": "audio_device", "184e": "audio_device", "1850": "audio_device"}
TYPES = {"phone_or_wearable", "pc_or_peripheral", "iot_module", "fitness_wearable", "beacon", "smart_home",
         "access_point", "camera_like", "battery_device", "audio_device", "medical_device", "vehicle", "unknown"}
# IEEE MA-L OUIs of organisations whose main line is IP/home security cameras (hint only).
# Site config may add more with add_camera_ouis().
CAMERA_OUI_HINTS: set[str] = set(_T["camera_ouis"])


def normalise_oui(mac_or_oui: str) -> str:
    h = "".join(c for c in mac_or_oui.lower() if c in "0123456789abcdef")[:6]
    return ":".join(h[i:i + 2] for i in (0, 2, 4)) if len(h) == 6 else ""


def add_camera_ouis(ouis) -> None:
    CAMERA_OUI_HINTS.update(o for o in (normalise_oui(x) for x in ouis) if o)


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
        return "camera_like" if oui and normalise_oui(oui) in CAMERA_OUI_HINTS else "access_point"
    for u in service_uuids or []:
        u = u.lower(); t = UUID_TYPES.get(u[4:8] if len(u) > 8 else u[-4:])
        if t:
            return t
    if company_id is not None and company_id in COMPANY_TYPES:
        return COMPANY_TYPES[company_id]
    return "unknown"
