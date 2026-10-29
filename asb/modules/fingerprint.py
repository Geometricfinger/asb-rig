"""M-03 signal fingerprint: per-emitter RF baselines for fixed emitters, drift flagged as
possible tampering (A9, observation only), coarse device type. Passive data only."""
from __future__ import annotations
from dataclasses import dataclass, field

from ..features.rf import DriftDetector, build_baseline, device_type


@dataclass
class FingerprintTracker:
    baseline_windows: int = 10
    windows: dict = field(default_factory=dict)      # key -> list[feature dict]
    detectors: dict = field(default_factory=dict)    # key -> DriftDetector
    types: dict = field(default_factory=dict)
    drift_log: list = field(default_factory=list)

    def observe(self, key: str, feats: dict, company_id=None, uuids=None, is_ap=False) -> dict:
        self.types[key] = device_type(company_id, uuids, is_ap)
        if key not in self.detectors:
            w = self.windows.setdefault(key, [])
            w.append(feats)
            if len(w) >= self.baseline_windows:
                self.detectors[key] = DriftDetector(build_baseline(w))
            return {"key": key, "state": "baselining", "type": self.types[key]}
        drift, changed = self.detectors[key].update(feats)
        if drift:
            self.drift_log.append({"key": key, "changed": changed})
        return {"key": key, "state": "drift" if drift else "ok", "changed": changed, "type": self.types[key],
                "note": "possible tampering or benign change (firmware, battery, temperature, relocation)" if drift else ""}

    def drifted(self) -> list[str]:
        return sorted({d["key"] for d in self.drift_log})
