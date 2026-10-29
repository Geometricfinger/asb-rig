# ADR-0039: Biometric retention (D-39)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Raw eye/voice never stored; derived traces 30 days; enrollments until withdrawal or set end.

## Where it is enforced

oiris/guard/retention.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
