# Upgrading, versioning and deprecation

## Versions
- **Package**: SemVer (`asb.__version__`).
- **Ports** (`registry.PORT_VERSIONS`): a plugin's major must equal the port's major. Minor bumps are additive.
- **Contracts C1–C9**: semantic version each (`SCHEMA_VERSION` for C1–C3, SQLite `user_version` for C4, `FORMAT_VERSION` for C5, manifest fields for C9).
- **SQLite schema**: `PRAGMA user_version`; migrations in `asb/store/migrations.py` apply in a transaction at startup. A DB newer than the code is refused.
- **Golden manifest**: `format_version`; `asb.modules.golden.migrate()` upgrades old files on load; newer files are refused.

## Policy (C8)
1. Consumers support the current and the previous minor of every contract.
2. Breaking change = major bump, a migration where data is involved, an ADR, a CHANGELOG entry, and sign-off from each consuming workstream; guardrail changes also need owner sign-off.
3. **Deprecations** live for at least one minor release: the old path keeps working and logs a warning, the CHANGELOG lists it under *Deprecated*, and removal happens in the next major.
4. Frozen test thresholds and the frozen golden test split never change silently (see ADR-0031 / D-31).

## Upgrade steps
```bash
git pull && pip install -e ".[dev]"
pytest                      # includes migration tests
asb --headless --scenario quiet   # opens nothing on disk; real runs migrate the DB on first open
```
Back up the encrypted data directory first; migrations are forward-only.
