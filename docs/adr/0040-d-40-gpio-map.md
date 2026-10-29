# ADR-0040: GPIO map (D-40)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Figure 3 (GPIO17/27 LED gates, I2S on 18–21, GPS on I²C).

## Where it is enforced

Hardware/process decision; documented only (no code path).

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
