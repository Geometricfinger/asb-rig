# ADR-0046: Purchase approval. Tier A v2 ≈ $461; Tier B v2 +$401; props +$50–150; Phase 2 glasses +$399–449 (D-01)

- Status: Open (owner decision)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Nothing is bought. Recommend Tier A v2 first, Tier B only after G0.

## Where it is enforced

Hardware/process decision; documented only (no code path).

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
