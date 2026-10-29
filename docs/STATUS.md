# Status: what is real, what is a stub

Version 0.1.0. "Real" = implemented and unit-tested headless. "Untested on hardware" = code exists but has never touched the device. Nothing has been validated on real subjects.

| Area | State |
|---|---|
| Sensor bus, registry, config, flags, fault isolation | **Real**, tested (incl. fault injection) |
| Fusion (families, LR stack, mask, evidence rule, suppression, training, AUC) | **Real**; default weights are a hand-set prior (no trained weights yet) |
| Guards (vocabulary, consent, privacy, retention, phrases, passive radio) | **Real**, tested |
| Security (AES-GCM, keystore + scrypt, Noise_XX + rekey, hash chain + anchors, panic, wipe) | **Real** in Python, tested. LUKS2 data-partition setup is scripted (`scripts/pi_luks2_setup.sh`: idempotent, `--dry-run`, typed confirmation; tested in dry-run with faked tools). **Never run on a real Pi yet** |
| Sighting log, sweep timeline, migrations | **Real**, tested |
| Golden manifest, freeze, withdrawal, feedback loop, format migration | **Real**, tested. **Synthetic seed set** in `golden/synthetic/` (clearly labelled synthetic; tooling `scripts/make_synthetic_golden.py`, checked in CI). **No real golden data** (needs hardware recordings and consenting volunteers; procedure in golden/README.md) |
| Headless mode, CLI, replay/record | **Real**, tested |
| Feature extractors (glint, NIR, thermal, pupil, blink, saccade, micro-saccade report, glint code, PLR, rPPG/POS, band SNR, AP clock skew, BLE drift, device type, site baselines) | **Real** algorithms, tested on synthetic signals only |
| Voice tiers (Python) | **Real**, tested with a null TTS; Flite backend untested on hardware |
| Hardware drivers (MLX90640, PureThermal, picamera2 + IR LED, bleak, iw, NMEA GPS, MR60BHA2, rtl_power) | **Untested on hardware**; parsers (NMEA, MR60 frames, iw scan) and LED duty cap are unit-tested. The MR60BHA2 frame type IDs follow the vendor's published protocol but were not checked against a device |
| Eye ROI detection (live frames) | **Real**, tested on synthetic NIR frames: dark-pupil + glint detector or landmark crop (`features/eye_roi.py`, ADR-0051), `EyeTracker` → `eye` sample, `camera_noir_eye` adapter. **Untested on hardware**; thresholds need tuning on the real camera |
| Speaker embedding (ECAPA) and anti-spoof (AASIST) models | **Not included** (data terms unverified). `S_voice` takes a spoof score from the model port |
| Android app: gate, Keystore wrap, SQLCipher store, panic, offline TTS, fallback node logic, zones | **Real source; builds in CI only** (no device testing yet) |
| Android Noise channel | **Stub**: not yet implemented in Kotlin (noise-java is not on Maven Central; needs vendoring or a Kotlin port) |
| Android map screen (Mapsforge) | Dependency wired, attribution shown; **map view not yet implemented** |
| Android CameraX glint capture | Scoring logic present; **camera pipeline not yet wired** |
| Dashboard | Zones D1–D6 (headless data, 127.0.0.1 only) plus **real, tested** M-16 review page `/face` (browse, delete entry/person, disable+wipe, enrollment guide). D3/D4 remain text panels |
| Glasses display (G zones) | **Real renderer in simulation** (`oiris/ui/glasses.py`, SVG, G1–G6, tested; `oiris glasses-sim`). No glasses hardware: real-display validation is Phase 2 after gate G1 |
| Design tokens (C7) | **v0.1 DEFAULT** (`oiris/ui/design_tokens.json`, rules enforced by `tokens.validate`, ADR-0052); Design review may refine |
| M-16 face matching (optional, off by default) | **Real** core, tested headless with a test-only synthetic backend: opt-in, enrollment (unlimited people), matching, research counts, review log, verified wipe, fault isolation. Real OpenCV Zoo backend: weights downloaded on request, **never run on a real face in tests**. Guided capture UI: CLI only (Android/glasses screens not built) |
| macOS artifact | Wheel + self-test tarball + **unsigned `O Iris.app`** zip (offline wheels, launches the local dashboard; `scripts/make_macos_app.py`, structure tested). Signing/notarization needs a paid Apple Developer ID: steps in docs/MACOS.md, **not done** |
