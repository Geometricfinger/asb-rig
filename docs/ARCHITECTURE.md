# Architecture

## Shape
One process. One thread per sensor adapter (the **sensor bus**). An asyncio loop at 1 Hz drains the bus, runs every enabled **score module** (each returns a score in [0,1], a confidence and a health flag), and hands the scores to **one fusion layer**. A **guard** checks every output. The phone app and dashboard talk to the runtime only through the contracts below.

```
 sensors ─► adapters (C2) ─► SensorBus ──► score modules (C1) ──► fusion ──► guard ──► events (C3)
   real │ replay │ sim      thread/adapter   safe_update()         families       vocabulary      │
                            watchdog, breaker                       ≥2-family rule                  ├─► voice tiers (M-06)
                                                                                                   ├─► sighting log (C4, M-05)
                                                                                                   └─► Noise link ─► Android app
```

## Ports (ports & adapters)
| Port | Interface | Version | Registry key |
|---|---|---|---|
| sensor | `oiris.adapters.base.SensorAdapter` (open/start/read/stop/close/health, `caps`, `license`) | 1.0 | `("sensor", id)` |
| score | `oiris.scores.base.ScoreModule` (`name`, `inputs`, `module_flag`, `update(window)->Score`) | 1.0 | `("score", name)` |
| model | `oiris.models.ModelPort` + C9 manifest; loaded into a `ModelSlot` | 1.0 | `("model", name)` |
| tts | `oiris.modules.voice.Tts` (`speak`, `stop`, `offline`) | 1.0 | `("tts", name)` |
| store | `oiris.store.db.DB` (migrations, sealed JSON) | 1.0 | `("store", name)` |

`oiris/registry.py` holds the ports; built-ins register in `oiris/adapters/builtin.py` and `oiris/scores/builtin.py`; third parties register through the `oiris.plugins` entry-point group. A plugin with a different **major** port version or a disallowed license is rejected at registration. A plugin that throws while loading is logged and skipped.

## Fault isolation
| Failure | Containment | Test |
|---|---|---|
| Adapter `read()` raises (even `SystemExit`) | caught in the adapter thread → DEGRADED, restart with exponential back-off | `test_fault_injection.py` |
| Adapter hangs | read runs in a helper thread with a timeout; timeout counts as a failure | same |
| N consecutive failures | circuit breaker opens → FAILED, no restarts until cooldown | same |
| Garbage samples | validator rejects; counter incremented | same |
| Score module raises / NaN / wrong type | `safe_update` → FAILED score; family masked | same |
| ≥2 families unhealthy | fusion suppresses the index | same |
| Model or fusion-weights load fails | last-good or disabled; never raises | `test_model_slot`, `test_model_load_failure_falls_back` |
| Event handler raises | logged; loop continues | `test_event_handler_crash_does_not_stop_loop` |
| Bad config | rejected at startup with a clear message; unknown keys ignored; safe defaults | `test_config_defaults_and_validation` |
| DB newer than code | refuses to open (no silent downgrade) | `test_refuses_newer_schema` |

## Contracts
| ID | Contract | Where | Owner |
|---|---|---|---|
| C1 | Score: module, value [0,1], confidence [0,1], health, timestamps, version; no class field | `oiris/schema.py`, `schema/score.json` | Core |
| C2 | Sensor adapter + Sample | `oiris/adapters/base.py`, `schema/sample.json` | Core |
| C3 | Event: signature A1–A11, level fyi/attention/confirmed, benign causes; no class field | `oiris/schema.py`, `schema/event.json` | Core |
| C4 | Sighting log: encrypted body, GPS policy, hash-chain fields, verdict, retention | `oiris/store/sightings.py`, migrations | Core |
| C5 | Golden dataset manifest (format v2) | `oiris/modules/golden.py` | Training |
| C6 | Layout-zone map (glasses G*, phone P1–P5, dashboard D1–D6) | `docs/spec/ASB-Module-Map-v1.1.pdf`, used by `android/` and `oiris/dashboard/` | Design |
| C7 | Design tokens | to be produced by the Design workstream (see STATUS) | Design |
| C8 | Versioning and change policy | `docs/UPGRADING.md` | Docs |
| C9 | Model package manifest | `oiris/models.py` (`REQUIRED` fields) | Training |

## Signal families and signatures
Families: optical, thermal, rf, vital, eye_liveness, voice. Signatures A1–A11 are defined in `oiris/schema.py` with their benign causes. An alert (ATTENTION) needs ≥2 families; one family is FYI; CONFIRMED is set only by an operator.

## Module map (spec M-01…M-15 → code)
| Module | Code |
|---|---|
| M-01 Eye behaviour | `features/eye.py`, `scores/builtin.EyeScore` (default off) |
| M-02 Liveness stacking | `modules/liveness.py`, `features/vital.py`, `LiveScore`, `VoiceScore` (default off) |
| M-03 Signal fingerprint | `features/rf.py`, `modules/fingerprint.py`, `RfDriftScore` |
| M-04 Security | `security/*`, `android/.../KeyVault.kt` |
| M-05 Sighting log | `store/sightings.SightingLog`, `android/.../SightingStore.kt` |
| M-06 Voice output | `modules/voice.py`, `guard/phrases.py`, `android/.../VoiceOut.kt` |
| M-07 Baselines / new object | `features/baseline.py`, `NewObjScore` |
| M-08 Thermal view | `features/thermal.render/overlay` |
| M-09 Headless + golden | `headless/`, `modules/golden.py`, `golden/expected/` |
| M-10 One-commit build | `scripts/build_all.sh`, `.github/workflows/ci.yml` |
| M-11 Sensor bus / adapters | `bus.py`, `adapters/*`, `registry.py` |
| M-12 Feedback loop | `modules/golden.FeedbackLoop` |
| M-13 Android fallback node | `android/.../FallbackNode.kt`, `adapters/drivers.AndroidBridgeAdapter` |
| M-14 Sweep timeline | `store/sightings.SweepTimeline` |
| M-15 App gate | `android/.../Gate.kt`, `modules/appgate.py` |
