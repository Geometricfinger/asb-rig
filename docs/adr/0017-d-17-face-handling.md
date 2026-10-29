# ADR-0017: Face handling (D-17)

- Status: Superseded by ADR-0049
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Operator-aimed; transient eye-ROI detection in RAM; no templates; no stored face crops.

## Where it is enforced

superseded by [ADR-0049](0049-face-handling-enrolled-templates.md); oiris/guard/privacy.py (64x64 crops only; `face_template` refused except from the opted-in M-16 module, built 2026-10-29)

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
