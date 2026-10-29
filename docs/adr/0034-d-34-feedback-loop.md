# ADR-0034: Feedback loop (D-34)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Quarantine → review → growth set; frozen test never changes.

## Where it is enforced

asb/modules/golden.FeedbackLoop

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
