# ADR-0031: Headless/golden (D-31)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Replay adapters, virtual clock, subject-disjoint splits, frozen test hash at G0.

## Where it is enforced

asb/headless/, asb/modules/golden.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
