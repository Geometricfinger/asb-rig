# ADR-0054: Audit gap build (Oct 29 2026)

Status: Accepted

## Context
A code audit against the build spec (M-01..M-16) found partial modules. All gaps are code; some can only be *validated* on hardware or real people.

## Decisions
- **M-02** spoken digits: random 4-digit prompt, single-use nonce, 10 s TTL, human latency window (0.25–4 s), constant-time match; result feeds `S_voice`. The recogniser stays behind an input interface; no ASR model is shipped until one with commercial-OK training data is found.
- **M-04** static keys rotate every 90 days (warning in the last 7); rotation clears the pairing and the channel refuses to run until re-paired. The hash chain anchors every 100 records and at least every 60 s while records arrive (idle logs do not grow). A test lints `oiris/` for `==`/`!=` on secret-like names.
- **M-07** anchors are printed ArUco DICT_4X4_50 markers, detected in numpy (no OpenCV runtime dependency); IDs key the per-site baselines; pose from the planar homography when intrinsics are known.
- **M-03** tables are regenerated from the public Bluetooth SIG and IEEE registries; types are our curation; camera OUIs are hints only.
- **M-01** real-signal evidence comes from consented, CC BY 4.0 / MIT eye-tracker recordings fetched at test time (not redistributed). Thresholds record measured agreement; they validate the blink logic on real signals, not our camera pipeline.
- **M-15** macOS gate: Swift helper, biometrics only, KeyStore key slot. Unsigned builds use an LA-checked login-keychain item (`la-check`, weaker, reported); signed builds with an entitlement use `.biometryCurrentSet` access control (`keychain-acl`).
- **BLE link**: one GATT service, RX write-without-response + TX notify; segments carry seq/flags/length; everything on air is Noise ciphertext. Pod server uses `bless` (MIT, optional).
- **Android**: GPS through the platform LocationManager only; front-camera eye features are report-only (never fused, so the fallback node still cannot alert alone); the microphone is off by default and yields a level only.

## Consequences
Everything above is unit/JVM tested; radio, GPS, camera, microphone, Touch ID and glasses paths still need devices (docs/STATUS.md).
