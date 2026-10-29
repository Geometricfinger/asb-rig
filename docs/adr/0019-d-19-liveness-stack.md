# ADR-0019: Liveness stack (D-19)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

≥2 families; outputs "indicators not observed"; voice never alone; module ships disabled if its gate fails.

## Where it is enforced

asb/modules/liveness.py; Config.DEFAULT_OFF

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
