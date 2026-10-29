# ADR-0020: Fingerprints (D-20)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Behavioral BLE/AP + AP clock skew on fixed owned emitters; no IQ-level RFFI; drift = changed ≥2 features for ≥3 windows.

## Where it is enforced

oiris/features/rf.py, oiris/modules/fingerprint.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
