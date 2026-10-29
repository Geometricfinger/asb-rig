# ADR-0035: Fallback node (D-35)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

AOSP/Apache only; minSdk 29; advisory only; never alerts alone.

## Where it is enforced

android FallbackNode.kt, minSdk 29

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
