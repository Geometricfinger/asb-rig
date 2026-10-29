# Changelog

All notable changes. Format: Keep a Changelog; versioning: SemVer. Contracts C1–C9 are versioned separately (see docs/UPGRADING.md).

## [Unreleased]
### Added
- Android: Kotlin Noise_XX port + SecureChannel + fragments in new pure-Kotlin module `android/core` (byte-identical to Python on shared vectors `tests/vectors/`), M-16 guided enrollment screen (`EnrollmentActivity`, typed opt-in, 5-angle checklist, no limit), offline Mapsforge map (`MapActivity`), CameraX glint capture (`GlintCamera`), C7 alert visuals + haptics (`AlertUi`); `:core:check` JVM checks run in CI. Pod side: EnrollmentPort over the link (`oiris/modules/face_match/remote.py`), `security.channel.fragment`/`Reassembler`; ADR-0053. Tests: `tests/test_phone_link.py`.
- Unsigned macOS `O Iris.app` bundle in the CI artifact (`scripts/make_macos_app.py`, offline bundled wheels for Python 3.11–3.13); signing steps in docs/MACOS.md. Tests: `tests/test_macos_app.py`.
- Synthetic seed golden set `golden/synthetic/` (5 simulator clips, frozen manifest, expectations) + `scripts/make_synthetic_golden.py` (`--check` in CI); real-data procedure in golden/README.md. Tests: `tests/test_synthetic_golden.py`.
- C7 design tokens v0.1 + validator (`oiris/ui/tokens.py`) and simulated glasses display G1–G6 (`oiris/ui/glasses.py`, `oiris glasses-sim`); ADR-0052. Tests: `tests/test_ui_glasses.py`.
- `scripts/pi_luks2_setup.sh`: LUKS2 (argon2id, aes-xts-512) data partition for the Pi, idempotent, `--dry-run`, noauto crypttab/fstab (passphrase never stored). Tests: `tests/test_luks_script.py`.
- Live eye ROI (M-01): `oiris/features/eye_roi.py` (dark-pupil + glint, or landmarks), `EyeTracker`, `NirEyeAdapter` (`camera_noir_eye`); ADR-0051. Tests: `tests/test_eye_roi.py`.
- Dashboard M-16 review page `/face` (`oiris/dashboard/face.py`): status, browse possible matches, delete entry, delete person (verified), disable+wipe (typed WIPE, verified), enrollment guide with angle checklist; per-process form token, `form-action 'self'` CSP; `oiris dashboard` wires M-16 only when on and opted in. Tests: `tests/test_dashboard.py`.
- M-16 face matching (optional, off by default; ADR-0049/0050, docs/FACE_MATCHING_MODULE_SPEC.md): `oiris/modules/face_match/` (FaceMatchPort, module core, EnrollmentPort with unlimited enrollment and 5-angle guided capture, quality checks, personal matching, research-mode anonymous counts, review log with per-entry delete, retention, export block, verified crypto-erase on disable and person delete, fault-isolation supervisor), `face_match_gate.py` (lazy load), `oiris face-match` CLI, schema migration v4 (`fm_*` tables), `face_match` port v1.0, `M-16` flag (DEFAULT_OFF).
- Backends: `opencv_zoo` (YuNet MIT + SFace Apache-2.0, weights fetched on request with pinned SHA-256) and a TEST-ONLY deterministic backend.
- Tests: `tests/test_face_match.py`, M-16 fault injection and FaceMatchPort contract tests.
### Changed
- Privacy guard allows `face_template` only from the enabled, opted-in M-16 module; refuses stranger face data kinds.
- Retention purge covers M-16 encounter logs and counts; engine routes `face_frame` samples to M-16 when loaded (no events, no scores).
- Build spec v2 non-goals amended for the M-16 add-on; ADR-0013/0017/0049/0050, ETHICS.md, STATUS.md, EXTENDING.md, THIRD_PARTY.md updated.
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
