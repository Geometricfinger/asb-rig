# ADR-0021: Crypto primitives (D-21)

- Status: Accepted (settled default, spec v2)
- Date: 2026-10-28
- Source: docs/spec/ASB-Build-Spec-v2.pdf, section 15

## Decision

AES-256-GCM (Keystore, files) / AES-256-XTS (LUKS2); ChaCha20-Poly1305 and X25519 in Noise; Ed25519 anchors; SHA-256, BLAKE2s; no custom crypto.

## Where it is enforced

oiris/security/aead.py, channel.py, hashchain.py

## Changing it

Write a new ADR that supersedes this one, update CHANGELOG.md, and (if it touches a guardrail) get owner sign-off. A change to a frozen test threshold cannot be used to declare a pass retroactively.
