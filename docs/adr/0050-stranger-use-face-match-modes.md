# ADR-0050: Public or stranger use — face-match modes (supersedes D-13)

- Status: Accepted (owner sign-off)
- Date: 2026-10-29
- Supersedes: [ADR-0013](0013-d-13-public-or-stranger-use.md)
- Source: [docs/FACE_MATCHING_MODULE_SPEC.md](../FACE_MATCHING_MODULE_SPEC.md)

## Context
D-13 ruled out public or stranger use in Phase 0–1. M-16 has two modes with different exposure to people who never agreed.

## Decision
Never in Phase 0–1, with one exception: M-16 **personal mode** (matching only enrolled, consenting people) is allowed now. M-16 **research mode** (anonymous, unlinked counts of unrecognized faces) unlocks on the user's own explicit opt-in alone: no legal review, no phase gate, no external gate. Its technical limits are unchanged: anonymous, unlinked counts only; no templates; no acting on detections; local only. The opt-in shows the plain-language warning, which notes that biometric and recording laws vary by place and that compliance is the user's responsibility. All other public or stranger use is unchanged: never in Phase 0–1.

**Principle:** every feature with questionable legality is an on/off switch. The user makes the determination, the risk is the user's own, and the feature is an option the user may use as they choose.

## Where it is enforced
Hardware/process decision; documented only today. When M-16 is built, `research` mode is accepted once the user has completed the M-16 opt-in; jurisdiction information is shown as a warning only and never blocks it.

## Changing it
Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
