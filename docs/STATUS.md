# Status: what is real, what is a stub

Version 0.1.0. "Real" = implemented and unit-tested headless. "Untested on hardware" = code exists but has never touched the device. Nothing has been validated on real subjects.

| Area | State |
|---|---|
| Sensor bus, registry, config, flags, fault isolation | **Real**, tested (incl. fault injection) |
| Fusion (families, LR stack, mask, evidence rule, suppression, training, AUC) | **Real**; default weights are a hand-set prior (no trained weights yet) |
| Guards (vocabulary, consent, privacy, retention, phrases, passive radio) | **Real**, tested |
| Security (AES-GCM, keystore + scrypt, Noise_XX + rekey, hash chain + anchors, panic, wipe) | **Real** in Python, tested. LUKS2 setup on the Pi is an operator step (not scripted yet) |
| Sighting log, sweep timeline, migrations | **Real**, tested |
| Golden manifest, freeze, withdrawal, feedback loop, format migration | **Real**, tested. **No golden data exists yet**; expectations come from simulated scenarios |
| Headless mode, CLI, replay/record | **Real**, tested |
| Feature extractors (glint, NIR, thermal, pupil, blink, saccade, micro-saccade report, glint code, PLR, rPPG/POS, band SNR, AP clock skew, BLE drift, device type, site baselines) | **Real** algorithms, tested on synthetic signals only |
| Voice tiers (Python) | **Real**, tested with a null TTS; Flite backend untested on hardware |
| Hardware drivers (MLX90640, PureThermal, picamera2 + IR LED, bleak, iw, NMEA GPS, MR60BHA2, rtl_power) | **Untested on hardware**; parsers (NMEA, MR60 frames, iw scan) and LED duty cap are unit-tested. The MR60BHA2 frame type IDs follow the vendor's published protocol but were not checked against a device |
| Eye ROI detection (Haar cascade) | **Stub**: the eye score consumes pre-extracted features; ROI finding on live frames is not wired yet |
| Speaker embedding (ECAPA) and anti-spoof (AASIST) models | **Not included** (data terms unverified). `S_voice` takes a spoof score from the model port |
| Android app: gate, Keystore wrap, SQLCipher store, panic, offline TTS, fallback node logic, zones | **Real source; builds in CI only** (no device testing yet) |
| Android Noise channel | **Stub**: not yet implemented in Kotlin (noise-java is not on Maven Central; needs vendoring or a Kotlin port) |
| Android map screen (Mapsforge) | Dependency wired, attribution shown; **map view not yet implemented** |
| Android CameraX glint capture | Scoring logic present; **camera pipeline not yet wired** |
| Dashboard | Zones D1–D6 (headless data, 127.0.0.1 only) plus **real, tested** M-16 review page `/face` (browse, delete entry/person, disable+wipe, enrollment guide). D3/D4 remain text panels |
| Glasses display (G zones) | **Not started** (Phase 2 after gate G1) |
| Design tokens (C7) | **Not started** (Design workstream) |
| M-16 face matching (optional, off by default) | **Real** core, tested headless with a test-only synthetic backend: opt-in, enrollment (unlimited people), matching, research counts, review log, verified wipe, fault isolation. Real OpenCV Zoo backend: weights downloaded on request, **never run on a real face in tests**. Guided capture UI: CLI only (Android/glasses screens not built) |
| macOS artifact | Wheel + self-test tarball, unsigned; no `.app` bundle yet |
