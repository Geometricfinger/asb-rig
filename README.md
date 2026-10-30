# O Iris — Anomaly Signature Bench

An open-source **research** rig and Android operator app that combines passive sensors (thermal, near-IR camera, eye camera, BLE/Wi-Fi, mmWave radar, microphone, GPS) and reports **anomaly signatures** such as "lens-glint candidate" or "known emitter changed vs its baseline", each with its common benign causes.

It is built for one question: *can a cheap, passive, consent-based sensor stack flag unusual devices, emitters and liveness inconsistencies (for example a hidden camera, a photo or screen replay, or a mannequin) in a room or at close range?*

> **Honest limits — read first**
> - **No study shows this detects a disguised humanoid machine.** Nothing here has been validated against one. Every threshold in the test plan is a proposal, not a benchmark result.
> - The **eye-behaviour (M-01)** and **liveness (M-02)** modules are **hypotheses**. They ship **disabled by default** until their experiments (E-11/E-14, E-15/E-16) pass on real data. Micro-saccades cannot be resolved with this hardware at a distance and are report-only.
> - A **silicone mask on a live person** keeps real eyes, pulse and voice; this stack does not catch it.
> - A heated mannequin is expected to defeat thermal checks.
> - The output **never labels a person**. There is no "robot" or "human" verdict anywhere in the code, by design (see `oiris/guard/vocabulary.py`).
> - No accuracy claims are made. Results are research signals.

## What's in the repo

| Path | What it is |
|---|---|
| `oiris/` | Python 3.11+ runtime: one process, one thread per sensor, scores in [0,1], one fusion layer |
| `oiris/adapters/` | Sensor port (C2): real drivers (MLX90640, Lepton/PureThermal, Pi NoIR, BLE via bleak, Wi-Fi beacons via `iw`, GPS/NMEA, MR60BHA2 radar, RTL-SDR probe, Android node) + replay + simulated backends |
| `oiris/scores/`, `oiris/features/` | Score port (C1) and signal processing for the 11 scores |
| `oiris/fusion/` | Six signal families, logistic-regression stack, missing-family mask, ≥2-family evidence rule |
| `oiris/guard/` | **Required** guards: vocabulary, consent, privacy, retention, phrase whitelist, passive-only radio |
| `oiris/security/` | AES-256-GCM at rest, Noise_XX rotating-key link, HMAC hash chain + Ed25519 anchors, constant-time compare, crypto-erase, panic gesture, 10-fail wipe |
| `oiris/store/` | Encrypted SQLite with versioned migrations; sighting log (GPS, map pins) and sweep timeline |
| `oiris/slots.py`, `examples/plugins/` | Replaceable model slots: swap or remove voice recognition, face match, eye and fusion models with one config line ([docs/PLUGINS.md](docs/PLUGINS.md)); no weights bundled |
| `oiris/modules/` | Voice tiers, golden dataset + feedback loop, fingerprints, liveness stack, app gate |
| `oiris/headless/` | Headless mode: replay, virtual clock, no network, LED stub |
| `oiris/dashboard/` | Minimal local dashboard (127.0.0.1 only) |
| `android/` | Kotlin companion app: BiometricPrompt Class 3 gate bound to a Keystore key, SQLCipher, offline TTS tiers, fallback camera/BLE node, no INTERNET permission |
| `schema/` | Shared JSON contracts (Python and Kotlin read the same files) |
| `golden/` | Golden expectations for the headless suite (data stays out of git) |
| `docs/` | Architecture, extending, upgrading, ADRs, ethics, and the v2 build spec and module map PDFs |

## Quick start (no hardware needed)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                                   # full headless suite
oiris --headless --scenario camera_lens    # simulated rig run, JSON out
oiris --headless --scenario replay_screen --steps 3 --expect golden/expected/replay_screen.json
oiris check-phrases                        # every voice/display phrase passes the guard
oiris dashboard                            # http://127.0.0.1:8765
```

Scenarios: `quiet`, `camera_lens`, `warm_prop`, `fixed_emitter_drift`, `replay_screen` (lab proxies, never people).

Hardware drivers: `pip install -e ".[hw]"` on a Raspberry Pi 5. Parts list, wiring and IR eye-safety rules are in `docs/spec/ASB-Build-Spec-v2.pdf`.

## Status: what is real vs stub

See [docs/STATUS.md](docs/STATUS.md).

## Use it responsibly

Read [ETHICS.md](ETHICS.md). Short version: consent first, private premises, passive radio only, biometric laws apply (Illinois BIPA, Texas, Washington, California, GDPR), and never use it to accuse anyone of anything.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) · [docs/EXTENDING.md](docs/EXTENDING.md) · [SECURITY.md](SECURITY.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

Licensed under Apache-2.0.

## Say hi 👋

Thanks for stopping by! It's totally okay to just say hi. If you've tried this project or just read through it, we'd love to hear what you think, so feel free to open an issue and share. Got an idea to make it better? Suggestions and pull requests are very welcome, big or small.
