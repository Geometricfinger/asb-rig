# Changelog

All notable changes. Format: Keep a Changelog; versioning: SemVer. Contracts C1–C9 are versioned separately (see docs/UPGRADING.md).

## [Unreleased]
### Fixed (Forge static review, each reproduced first by a failing test in `tests/test_forge_review.py` / `tests/test_face_match.py::test_f3_*`)
- F1 engine: cached sensor readings now expire after `sensor_max_age_s` (default 5 s, validated > 0); stale readings are not scored (so cannot drive alerts) and the adapter's reported health drops from OK to DEGRADED ("stale: ...").
- F2 bus: at most one in-flight `read()` thread per adapter; while a timed-out read is still running no new thread is spawned, the adapter is reported "hung" (counts toward the circuit breaker), and after `adapter_hung_disable_s` (default 30 s) it is FAILED/"disabled" until the driver returns, then restarted.
- F3 M-16: consent is rechecked on every template load/match and on `ConsentRegistry.withdraw`; templates under a withdrawn or expired consent are purged through the same verified crypto-erase as person deletion (`consent_withdrawn` change-log entry). Unknown consent IDs (registry not persisted) and recorded no-consent overrides are kept.
- F4 privacy guard: `check_persist` compared shape tuples lexicographically (32x1024 passed the 64x64 limit); now each dimension and the area are checked, and shapeless/1-D payloads are refused.
- F5 fusion: `FusionModel.from_json` rejects non-finite `w_mask` (it already rejected non-finite `w`/`b`); `load_weights` logs a warning when falling back to the default weights.
### Added
- Replaceable model slots (ADR-0055, docs/PLUGINS.md): ports `speech_recognizer`, `voice_antispoof`, `speaker_embed`, `eye_model`, `fusion_weights` (Protocols in `oiris/slots.py`, fault-isolated `SlotManager`); config `plugins` (`paths`, `entry_points`, `slots`, `options`); `PluginMeta` licence metadata with startup warnings for external non-permissive/non-commercial plugins; `DigitChallenge.verify_audio` runs the configured recogniser; `plugins.slots.face_match` selects the M-16 backend; `oiris plugins` command; reference plugins `examples/plugins/oiris_dtmf_digits` and `oiris_vosk_wrapper` (no weights). Tests: `tests/test_plugin_slots.py`.
- Audit gap build (ADR-0054): M-02 spoken-digit challenge; M-04 90-day static-key rotation + re-pair (`StaticKeyManager`, `channel.from_pairing`), 60-second anchor timer, secret-comparison lint test (fixed 3 real `!=` comparisons of hashes/nonces); M-07 numpy ArUco detector + marker-ID anchors; M-03 registry-derived company IDs and camera OUIs (`scripts/make_rf_tables.py`); M-06 Flite backend writes WAV and is run for real in CI; M-01 real-signal ingestion + test on consented CC BY 4.0 Tobii recordings; M-15 Swift Keychain/Touch ID helper + KeyStore key slots; M-16 glasses enrollment mini-guide; BLE GATT link for Noise frames (`oiris/link/`, Kotlin `BleFraming`, `BleGattTransport`) with pod service incl. thermal frames.
- Android: `LocationSource` (GPS → sightings), `ThermalView` + colour toggle, `TimelineActivity`, `FrontEyeCamera`, `MicMonitor` (off by default), `ScanRateLimiter`, pod pairing with rotation; core `ThermalRender`, `EyeFeatures`, `NodePolicy`; JVM checks 216 → 266. Shared vectors `tests/vectors/{ble_framing,thermal_render,eye_android}.json` (`scripts/make_android_vectors.py --check`).
- Tests: `tests/test_audit_gaps.py`, `tests/test_link_ble.py`, `tests/test_eye_real.py`, `tests/test_secret_compare_lint.py`.
### Fixed
- Android: missing `VIBRATE` permission (haptics), `ACCESS_COARSE_LOCATION` alongside fine, legacy BLE permissions for API 29–30, `KeyVault` call that needed API 30 on minSdk 29 (all found by Android lint).
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
