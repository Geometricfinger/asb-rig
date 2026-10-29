# Changelog

All notable changes. Format: Keep a Changelog; versioning: SemVer. Contracts C1–C9 are versioned separately (see docs/UPGRADING.md).

## [Unreleased]
### Docs
- Face-matching add-on spec (M-16, not built): `docs/FACE_MATCHING_MODULE_SPEC.md`.
- ADR-0049 supersedes ADR-0017 (enrolled-only encrypted face templates; verified wipe on disable).
- ADR-0050 supersedes ADR-0013 (personal mode allowed in Phase 0–1; research mode unlocks on the user's own opt-in, no legal review or external gate).
- ETHICS.md: face recognition in scope only as the opt-in M-16 module.

## [0.1.0] - 2026-10-28
### Added
- Python runtime: sensor bus (thread per adapter, watchdog, restart/back-off, circuit breaker), plugin registry with `oiris.plugins` entry points, validated config with module feature flags.
- Score modules S_glint, S_nir_emit, S_thermal, S_rf, S_rf_drift, S_radar, S_motion, S_eye, S_live, S_voice, S_newobj; fusion v2 (six families, missing mask, ≥2-family rule, suppression).
- Modules M-01…M-15 per build spec v2 (see docs/STATUS.md for real vs stub).
- Guards: vocabulary, consent, privacy, retention, phrases, passive-only radio.
- Security: AES-256-GCM, Noise_XX channel with rekey, hash chain + Ed25519 anchors, panic/kill switch, crypto-erase.
- Storage: SQLite schema v3 with migrations; golden manifest format v2 with migration from v1.
- Drivers with lazy imports: MLX90640, PureThermal/Lepton, Pi NoIR + IR LED (duty cap), BLE (bleak), Wi-Fi beacons (iw), GPS (NMEA), MR60BHA2, RTL-SDR probe, Android node bridge.
- Headless mode, golden expectations, CLI, local dashboard.
- Android companion app (Kotlin): biometric gate bound to Keystore, SQLCipher sighting store, offline TTS tiers, panic, fallback node.
- CI: Linux tests (3.11–3.13), ruff, mypy, license audit, golden suite; macOS job building APK + macOS artifact from one commit.
- Docs: architecture, extending, upgrading, status, 48 ADRs, ethics, spec v2 and module map PDFs.
