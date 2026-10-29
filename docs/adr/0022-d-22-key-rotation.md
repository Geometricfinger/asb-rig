# ADR-0022: Key rotation (D-22)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

New Noise handshake every session; Rekey ≤1,000 messages or 10 min; static keys 90 days; no double ratchet.

## Where it is enforced

oiris/security/channel.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
