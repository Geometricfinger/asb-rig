# ADR-0012: Storage (D-12)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

LUKS2 (Pi), SQLCipher (phone), 30-day retention, hashed IDs, no cloud.

## Where it is enforced

oiris/store/, oiris/guard/retention.py, oiris/guard/privacy.hash_identifier

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
