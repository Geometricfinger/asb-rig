# ADR-0023: Offline vs remote wipe (D-23)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Crypto-erase; triggers: panic, 10 failed unlocks, signed wipe from the paired phone in BLE range; cloud relay OFF; dead-man OFF.

## Where it is enforced

asb/security/panic.py, keys.crypto_erase

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
