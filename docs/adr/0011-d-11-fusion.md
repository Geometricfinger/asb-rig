# ADR-0011: Fusion (D-11)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

Stacked logistic regression over ≤6 family values; LOSO; human FPR ≤5%.

## Where it is enforced

asb/fusion/stack.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
