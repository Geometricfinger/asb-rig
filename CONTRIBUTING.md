# Contributing

Thanks for helping. Smarter people than the original authors will make this better; here is how to do it without breaking anything.

## Setup
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check oiris tests scripts && mypy oiris && python scripts/license_check.py
```

## Ground rules
1. **Add, don't edit core.** New sensors, scores, models and TTS engines plug in through ports (see [docs/EXTENDING.md](docs/EXTENDING.md)). Core (`engine.py`, `bus.py`, `fusion/`) must not import a concrete driver.
2. **Tests are mandatory**: a contract test for any new adapter/score (they are parametrised; usually you just register it) and a fault-injection case if your code can fail at runtime.
3. **Guards are not optional.** Do not weaken `oiris/guard/*`. PRs that add person-classification wording, transmit/monitor-mode radio, or audio persistence will be closed.
4. **Licenses**: only MIT/BSD/Apache/ISC/PSF/MPL dependencies. Update `THIRD_PARTY.md` (and `android/dependencies.txt` for Gradle deps).
5. **Thresholds are frozen** once data collection starts. Changing a pass/fail criterion needs an ADR and cannot be used to declare a pass retroactively.
6. **No personal data in issues or PRs**: no recordings of people, no audio, no location traces.
7. Update `CHANGELOG.md`; add an ADR in `docs/adr/` when you change a settled default.

## Versioning
Semver for the package and for each contract (C1–C9). See [docs/UPGRADING.md](docs/UPGRADING.md).
