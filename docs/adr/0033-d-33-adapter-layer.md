# ADR-0033: Adapter layer (D-33)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Python Protocol + Kotlin interface from one JSON schema.

## Where it is enforced

asb/adapters/base.py, schema/*.json, android Fusion.kt

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
