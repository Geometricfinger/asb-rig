# ADR-0024: Tamper-evident log (D-24)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

HMAC hash chain + Ed25519 anchors on the phone every 60 s or 100 records.

## Where it is enforced

asb/security/hashchain.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
