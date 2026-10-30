"""Startup config: validated, safe defaults, feature flags per module (M-01..M-16)."""
from __future__ import annotations
import math
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

MODULES = {
    "M-01": "eye_behavior", "M-02": "liveness", "M-03": "signal_fingerprint", "M-04": "security",
    "M-05": "sighting_log", "M-06": "voice_output", "M-07": "location_baselines", "M-08": "thermal_view",
    "M-09": "headless", "M-10": "build", "M-11": "sensor_bus", "M-12": "feedback_loop",
    "M-13": "android_fallback", "M-14": "sweep_timeline", "M-15": "app_gate",
    "M-16": "face_match",   # optional add-on (ADR-0049/0050): off by default, not imported until enabled
}
# Modules that cannot be disabled: security and the bus are load-bearing; guards are not modules.
LOCKED_ON = {"M-04", "M-11"}
# Gate-dependent modules ship disabled until their experiment passes (spec section 11, M-gates).
DEFAULT_OFF = {"M-01", "M-02", "M-16"}


class ConfigError(ValueError):
    pass


def validate_face_match(d: dict) -> list[str]:
    """Validate M-16 settings without importing the module (it stays unloaded while off).
    Mirrors oiris.modules.face_match.core.FaceMatchConfig; a test keeps the two in sync."""
    if not isinstance(d, dict):
        return ["face_match must be an object"]
    errs = []
    unknown = set(d) - FACE_MATCH_KEYS
    if unknown:
        errs.append(f"face_match: unknown keys {sorted(unknown)}")
    if any(m not in ("personal", "research") for m in d.get("modes", [])): errs.append("face_match.modes: personal/research only")
    if not 0.5 <= float(d.get("match_threshold", 0.8)) < 1.0: errs.append("face_match.match_threshold must be in [0.5, 1)")
    if not 1 <= int(d.get("encounter_retention_days", 30)) <= 365: errs.append("face_match.encounter_retention_days must be 1..365")
    if d.get("place_source", "named") not in ("named", "gps_0.01"): errs.append("face_match.place_source must be named|gps_0.01")
    if not 5 <= int(d.get("enroll_min_shots", 5)) <= int(d.get("enroll_max_shots", 10)):
        errs.append("face_match.enroll_min_shots must be >= 5 and <= enroll_max_shots")
    if d.get("allow_test_backend"): errs.append("face_match.allow_test_backend is for tests only")
    return errs


PLUGIN_KEYS = {"paths", "entry_points", "slots", "options"}
SLOT_NAMES = {"speech_recognizer", "voice_antispoof", "speaker_embed", "eye_model", "fusion_weights", "face_match"}


def validate_plugins(d: dict) -> list[str]:
    if not isinstance(d, dict):
        return ["plugins must be an object"]
    errs = []
    if set(d) - PLUGIN_KEYS: errs.append(f"plugins: unknown keys {sorted(set(d) - PLUGIN_KEYS)}")
    if not all(isinstance(p, str) and ":" in p for p in d.get("paths", [])): errs.append("plugins.paths: 'module:function' strings")
    slots = d.get("slots", {})
    if not isinstance(slots, dict) or set(slots) - SLOT_NAMES: errs.append(f"plugins.slots: keys must be in {sorted(SLOT_NAMES)}")
    return errs


FACE_MATCH_KEYS = {"modes", "jurisdiction", "require_enrollment_consent", "match_threshold", "encounter_retention_days", "place_source",
                   "time_bucket_minutes", "allow_log_export", "enroll_min_shots", "enroll_max_shots", "enroll_required_angles",
                   "reenroll_confidence_drop", "reenroll_window_matches", "adapter", "model_dir", "allow_test_backend"}


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
    sensor_max_age_s: float = 5.0      # cached readings older than this are stale: not scored, health degraded
    adapter_hung_disable_s: float = 30.0  # a read hung this long disables the adapter until it returns
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
    face_match: dict = field(default_factory=dict)   # M-16 settings, validated by FACE_MATCH_KEYS below
    # Replaceable model slots (docs/PLUGINS.md): {"paths": ["pkg.mod:register"], "entry_points": true,
    #  "slots": {"speech_recognizer": "name", ...}, "options": {name: {...}}}
    plugins: dict = field(default_factory=dict)

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
        if not (isinstance(self.sensor_max_age_s, (int, float)) and math.isfinite(self.sensor_max_age_s) and self.sensor_max_age_s > 0):
            errs.append("sensor_max_age_s must be a positive number")
        if not (isinstance(self.adapter_hung_disable_s, (int, float)) and math.isfinite(self.adapter_hung_disable_s)
                and self.adapter_hung_disable_s > 0):
            errs.append("adapter_hung_disable_s must be a positive number")
        errs += validate_face_match(self.face_match)
        errs += validate_plugins(self.plugins)
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
