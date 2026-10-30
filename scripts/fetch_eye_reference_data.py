#!/usr/bin/env python3
"""Fetch the pinned real eye-tracker recordings used by tests/test_eye_real.py (M-01).

Source: LaborTrack (Latifzadeh et al., "Assessing Medical Training Skills via Eye and Head
Movements", 2025). Preprocessed CSVs: github.com/kayhan-latifzadeh/LaborTrack (MIT); raw data
Zenodo record 15163456 (CC BY 4.0). Participants signed a consent form (paper, Sec. 3).
Recorded with Tobii Pro Glasses 2 (100 Hz). Files are pinned to a commit and SHA-256 checked;
they are downloaded into training-library/external/ (git-ignored) and never committed here."""
from __future__ import annotations
import hashlib, sys, urllib.request
from pathlib import Path

COMMIT = "5f95f84d5b815e1ce891d1095252ceffaf772293"
BASE = f"https://raw.githubusercontent.com/kayhan-latifzadeh/LaborTrack/{COMMIT}/data"
FILES = {
    "pupil/session_1/3ShqB.csv": "1b572743388c9737dcbb84d0f740124206c12fd89a0bd264f8eec354f8327fe4",
    "blinks/session_1/3ShqB.csv": "585f0ac660f608162d1e28824b5d6a6112c239caf1d109d648b3faa55dfa70bb",
    "pupil/session_1/VVCFR.csv": "3ef1fc626b160abc3738c5005c14a7e7074405ed9b99f096939ac69ef2e6614f",
    "blinks/session_1/VVCFR.csv": "e9060b16caace692b0d0379299c7a6745c02647dd2e6f141a3e4d0e5c89cd9bd",
}
DEST = Path(__file__).resolve().parents[1] / "training-library/external/labortrack"


def main() -> int:
    for rel, sha in FILES.items():
        out = DEST / rel
        if out.exists() and hashlib.sha256(out.read_bytes()).hexdigest() == sha:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        data = urllib.request.urlopen(f"{BASE}/{rel}", timeout=60).read()
        got = hashlib.sha256(data).hexdigest()
        if got != sha:
            print(f"sha256 mismatch for {rel}: {got}", file=sys.stderr)
            return 1
        out.write_bytes(data)
    (DEST / "ATTRIBUTION.txt").write_text(
        "LaborTrack eye-tracking data, (c) 2025 Kayhan Latifzadeh et al. Preprocessed CSVs under the MIT License "
        "(github.com/kayhan-latifzadeh/LaborTrack); raw data CC BY 4.0 (doi:10.5281/zenodo.15163456). "
        "Paper: doi:10.1145/3699682.3728330.\n")
    print(f"ok: {len(FILES)} files in {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
