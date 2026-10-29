"""Startup config: validated, safe defaults, feature flags per module (M-01..M-15)."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

MODULES = {
    "M-01": "eye_behavior", "M-02": "liveness", "M-03": "signal_fingerprint", "M-04": "security",
    "M-05": "sighting_log", "M-06": "voice_output", "M-07": "location_baselines", "M-08": "thermal_view",
    "M-09": "headless", "M-10": "build", "M-11": "sensor_bus", "M-12": "feedback_loop",
    "M-13": "android_fallback", "M-14": "sweep_timeline", "M-15": "app_gate",
}
# Modules that cannot be disabled: security and the bus are load-bearing; guards are not modules.
LOCKED_ON = {"M-04", "M-11"}
# Gate-dependent modules ship disabled until their experiment passes (spec section 11, M-gates).
DEFAULT_OFF = {"M-01", "M-02"}


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    flags: dict = field(default_factory=lambda: {m: m not in DEFAULT_OFF for m in MODULES})
    data_dir: str = "~/.asb"
    retention_days: int = 30
    gps_export_decimals: int = 2
    thermal_palette: str = "grayscale"
    thermal_range_c: tuple = (10.0, 45.0)
    queue_size: int = 64
    adapter_timeout_s: float = 2.0
    restart_backoff_max_s: float = 10.0
    breaker_threshold: int = 5
    breaker_cooldown_s: float = 30.0
    rekey_messages: int = 1000
    rekey_seconds: int = 600
    failed_unlock_wipe: int = 10
    voice_attention_min_interval_s: float = 10.0
    min_families_for_alert: int = 2
    max_unhealthy_families: int = 1
    allow_network: bool = False
    pled_duty_cap: float = 0.25

    def enabled(self, module: str) -> bool:
        return module in LOCKED_ON or bool(self.flags.get(module, False))

    def validate(self) -> "Config":
        errs = []
        unknown = set(self.flags) - set(MODULES)
        if unknown:
            errs.append(f"unknown module flags {sorted(unknown)}")
        for m in LOCKED_ON:
            self.flags[m] = True
        if not 1 <= self.retention_days <= 365: errs.append("retention_days must be 1..365")
        if self.gps_export_decimals not in (0, 1, 2, 3): errs.append("gps_export_decimals must be 0..3")
        if self.thermal_palette not in ("grayscale", "inferno", "viridis"): errs.append("bad thermal_palette")
        lo, hi = self.thermal_range_c
        if not lo < hi: errs.append("thermal_range_c low must be < high")
        if self.min_families_for_alert < 2: errs.append("min_families_for_alert cannot go below 2 (evidence rule)")
        if not 1 <= self.rekey_messages <= 1000: errs.append("rekey_messages must be 1..1000")
        if not 1 <= self.rekey_seconds <= 600: errs.append("rekey_seconds must be 1..600")
        if not 0 < self.pled_duty_cap <= 0.25: errs.append("LED duty cap must be in (0, 0.25]")
        if self.queue_size < 1 or self.adapter_timeout_s <= 0: errs.append("queue/timeout must be positive")
        if errs:
            raise ConfigError("; ".join(errs))
        return self

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        if path is None or not Path(path).exists():
            return cls().validate()
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        if "flags" in known:
            base = cls().flags
            base.update(known["flags"])
            known["flags"] = base
        if "thermal_range_c" in known:
            known["thermal_range_c"] = tuple(known["thermal_range_c"])
        return cls(**known).validate()

    def to_dict(self) -> dict:
        return asdict(self)
