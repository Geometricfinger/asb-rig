# ADR-0049: Face handling — enrolled-only templates (supersedes D-17)

- Status: Accepted (owner sign-off)
- Date: 2026-10-29
- Supersedes: [ADR-0017](0017-d-17-face-handling.md)
- Source: [docs/FACE_MATCHING_MODULE_SPEC.md](../FACE_MATCHING_MODULE_SPEC.md)

## Context
D-17 allowed only transient eye-ROI detection and stored no face templates. The owner approved an optional face-matching add-on (M-16 `face_match`) whose personal mode needs a stored template for each person the user enrolls.

## Decision
Eye handling is unchanged: operator-aimed; transient eye-ROI detection in RAM; no stored face crops. Face templates may be stored **only** for people the user explicitly enrolled in M-16 personal mode, encrypted on device with a dedicated subkey, never uploaded or exported. Templates of unenrolled people are never stored, in any mode. Disabling or removing M-16 crypto-erases all face data and verifies the wipe.

## Where it is enforced
`oiris/guard/privacy.py`: `check_persist("face_template", ..., source="M-16", m16_enabled=True)` is the only accepted form; every other source and any stranger face data is refused. Storage, keys and wipe live in `oiris/modules/face_match/core.py` (per-person data keys sealed by a face key in `<data_dir>/face_match.key`, itself sealed by `keys.subkey("face-template")`). Tests: `tests/test_face_match.py` (wipe verification, person-delete undecryptability, research mode stores no face data, privacy guard).

## Changing it
Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
