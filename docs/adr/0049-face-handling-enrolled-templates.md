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
Today: oiris/guard/privacy.py still rejects every `face_template` (M-16 is not built). When M-16 is built, the guard allows `face_template` only from M-16 for an enrolled `person_id`; wipe-verification and no-stranger-template tests are required (spec §15).

## Changing it
Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
