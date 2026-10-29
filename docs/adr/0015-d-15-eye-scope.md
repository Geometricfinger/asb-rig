# ADR-0015: Eye scope (D-15)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Near-range (0.3–1 m) pupil, blink, glint-code; micro-saccades report-only; light-step PLR lab-only and off by default.

## Where it is enforced

asb/features/eye.py (microsaccades_report, pupil_light_response)

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
