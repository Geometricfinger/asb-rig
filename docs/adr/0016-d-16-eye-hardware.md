# ADR-0016: Eye hardware (D-16)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

OV9281 mono CSI, 25° M12 lens, two 850 nm LEDs pulsed in sync (Section 6).

## Where it is enforced

Hardware/process decision; documented only (no code path).

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
