# ADR-0013: Public or stranger use (D-13)

- Status: Superseded by ADR-0050
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Never in Phase 0–1.

## Where it is enforced

superseded by [ADR-0050](0050-stranger-use-face-match-modes.md). Outside M-16 this stays a process decision; M-16 modes are enforced in `oiris/modules/face_match/` (built 2026-10-29).

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
