# ADR-0037: App gate (D-37)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

BIOMETRIC_STRONG + device credential; crypto-bound; 60 s lock; FLAG_SECURE.

## Where it is enforced

android Gate.kt, KeyVault.kt; oiris/modules/appgate.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
