# Security policy

## Reporting
Please report vulnerabilities privately via GitHub's **"Report a vulnerability"** (Security → Advisories) on this repository. Do not open a public issue. We aim to acknowledge within 7 days.

## Scope
The security module (M-04) protects **the owner's own data on the owner's own devices**: AES-256-GCM at rest (LUKS2 on the Pi, SQLCipher on the phone), a Noise_XX_25519_ChaChaPoly_BLAKE2s link with rekey every 1,000 messages or 10 minutes, an HMAC-SHA256 hash-chained log with Ed25519 anchors, crypto-erase on panic / 10 failed unlocks / signed wipe from the paired phone.

## Known limits
- Python cannot guarantee constant-time behaviour of surrounding code; secret comparisons use `hmac.compare_digest` and a lint test bans `==` on secret-named variables.
- Overwriting flash is unreliable; erasure relies on destroying keys (crypto-erase).
- The Android Noise channel is not yet implemented in Kotlin (see docs/STATUS.md); the Python side is complete and tested.
- Builds are unsigned. Verify artifacts against the SHA-256 list in `BUILD_INFO.json` from CI.
- No secrets are stored in this repository or in CI.
