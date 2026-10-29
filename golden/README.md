# Golden dataset
`expected/*.json` are the headless expectations for simulated scenarios (E-23). Real clips (derived features and non-person arrays only) live in an **encrypted archive outside git** with a `manifest.json` (format v2, see `oiris/modules/golden.py`). The frozen test split hash is recorded at gate G0.

## Synthetic seed set (`synthetic/`)
**SYNTHETIC ONLY.** 5 simulator-generated clips (quiet, camera_lens, warm_prop, replay_screen, fixed_emitter_drift), source tier `synthetic`, no person, no recording, no third-party data. `manifest.json` (C5 v2, frozen test hash) and `expected.json` are built by `python scripts/make_synthetic_golden.py` and checked in CI with `--check`. It proves the tooling, not detection performance.

## Procedure for real data (hardware and people required)
1. Record with the rig only (`oiris record` equivalents on hardware); keep derived features and non-person arrays only.
2. Every clip with a person needs a signed consent ID (`ConsentRegistry`); withdrawal removes clips (`Manifest.withdraw`).
3. Tier `own_recorded` (or `restricted_licensed` with a licence that allows commercial use, recorded in THIRD_PARTY.md).
4. Store clips in an encrypted archive outside git (`golden/data/`, ignored); commit only `manifest.json`.
5. Assign splits, have a second person review labels, then `Manifest.freeze()` at gate G0 and record the hash in the ADR log. The frozen test split never receives clips.
6. Confirmed field sightings go through the feedback loop (quarantine → growth), never into test.
