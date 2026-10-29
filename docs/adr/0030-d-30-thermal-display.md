# ADR-0030: Thermal display (D-30)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Grayscale 10–45 °C fixed scale default; color overlay is a toggle.

## Where it is enforced

asb/features/thermal.py render()

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
