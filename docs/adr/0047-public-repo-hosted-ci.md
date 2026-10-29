# ADR-0047: Public repo, hosted CI (supersedes D-32)

- Status: Accepted
- Date: 2026-10-28

## Context
D-32 made macOS CI a local script because hosted macOS runners bill private repos. The owner then chose to publish asb-rig as a public repository so others can improve it. GitHub-hosted standard runners (Linux and macOS) are free for public repositories.

## Decision
`.github/workflows/ci.yml` runs Linux tests (Python 3.11-3.13, ruff, mypy, pytest, license audit, headless golden suite) and a macOS job that runs `scripts/build_all.sh` to build the Android APK and the macOS artifact from the same commit. Only standard runners; no larger runners; no secrets; fork PRs use `pull_request` (read-only token). Artifacts are unsigned. `build_all.sh` still works locally.

## Consequences
No cost on standard runners. Signing/notarization stays a separate, owner-run step.
