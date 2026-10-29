# ADR-0004: RF scope (D-05)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

BLE adverts + AP beacons (incl. TSF) in managed mode; no monitor mode, cellular, data frames, or jamming.

## Where it is enforced

asb/guard/radio.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
