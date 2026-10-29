# ADR-0029: Baselines (D-29)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

RF-first; optical comparison only at ArUco anchors; optical A10 report-only.

## Where it is enforced

asb/features/baseline.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
