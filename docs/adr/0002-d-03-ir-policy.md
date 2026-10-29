# ADR-0002: IR policy (D-03)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Exempt-group parts, ≤2 LEDs per bank (two banks), ≤100 mA, duty caps, no optics, series switch; subject ≥0.3 m (eye) / ≥0.5 m (glint).

## Where it is enforced

oiris/adapters/drivers.py IrLed (duty cap <=25%), Config.pled_duty_cap

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
