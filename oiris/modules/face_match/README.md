# oiris.modules.face_match — M-16 face matching (optional, off by default)

Spec: `docs/FACE_MATCHING_MODULE_SPEC.md` · ADR-0049, ADR-0050 · ETHICS.md.

- `port.py` — `FaceMatchPort` (backends only compute), `Embedding` (RAM only, `zero()`), `Angle`.
- `core.py` — `FaceMatchModule`: storage, keys, modes, enrollment (`start_session`, `add_person`, `needed_angles`, `submit_shot`, `finish_person`, `end_session`, `reenroll`, `delete_person`), `process_frame` (counts only), `review_log`, `delete_entry`, `export_log` (blocked by default, never templates), `disable` (verified wipe).
- `quality.py` — per-shot checks: one face, size, light, blur, angle.
- `optin.py` — warning text v1, typed `I UNDERSTAND`, jurisdiction notes, tamper-evident `DbChain`.
- `supervisor.py` — every backend call in a thread with timeout and a circuit breaker.
- `backends/opencv_zoo.py` — YuNet (MIT) + SFace (Apache-2.0); `oiris face-match fetch-models`.
- `backends/test_deterministic.py` — **TEST ONLY**, synthetic frames, refused outside tests.

Loaded only by `oiris/modules/face_match_gate.load()` when `"M-16": true` and the opt-in is recorded.
No alerts, no events, no live lookup, no limit on enrolled people. Never labels anyone as anything but a user-chosen name or "unrecognized".

CLI: `oiris face-match status | enable --mode personal [--mode research] | fetch-models | enroll [--camera 0] | review | delete-entry --id E | delete-person --id P | disable`.
