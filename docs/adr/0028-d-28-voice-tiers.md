# ADR-0028: Voice tiers (D-28)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

FYI = haptic; Attention = whitelisted phrase, 1 per 10 s; Confirmed = barge-in, operator confirmation needed.

## Where it is enforced

asb/modules/voice.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
