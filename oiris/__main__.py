"""Allow ``python -m oiris`` (same entry point as the ``oiris`` console script)."""
from oiris.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
