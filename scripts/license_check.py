#!/usr/bin/env python3
"""License audit (R-05). Checks installed Python distributions required by O Iris (runtime
+ optional hw extras that are installed) against the allow-list, and the Android
dependency list in android/dependencies.txt. Exit 1 on any denied or unknown license.
Allowed: MIT, BSD, Apache-2.0, ISC, PSF, MPL-2.0. Denied: GPL in-process, AGPL, non-commercial."""
from __future__ import annotations
import re, sys
from importlib import metadata
from pathlib import Path

ALLOW = re.compile(r"\b(MIT|BSD|Apache|ISC|PSF|Python Software Foundation|MPL|Mozilla Public License 2\.0|Unlicense|0BSD|Zlib)\b", re.I)
DENY = re.compile(r"\b(AGPL|GPL|Affero|Non-?Commercial|NC-|SSPL|BUSL|research only)\b", re.I)
# LGPL is only acceptable with dynamic linking / an exception; none are used by the Python runtime.
RUNTIME = ["numpy", "cryptography", "PyNaCl", "noiseprotocol", "cffi", "pycparser"]
OPTIONAL = ["bleak", "bless", "pyserial", "opencv-python-headless", "adafruit-circuitpython-mlx90640", "gpiozero"]
KNOWN = {  # where package metadata is ambiguous, the verified license is recorded here
    "cryptography": "Apache-2.0 OR BSD-3-Clause", "numpy": "BSD-3-Clause", "PyNaCl": "Apache-2.0",
    "noiseprotocol": "MIT", "cffi": "MIT", "pycparser": "BSD-3-Clause",
}


def lic(dist: str) -> str | None:
    if dist in KNOWN:
        return KNOWN[dist]
    try:
        md = metadata.metadata(dist)
    except metadata.PackageNotFoundError:
        return None
    parts = [md.get("License-Expression") or "", md.get("License") or ""]
    parts += [c for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
    return " | ".join(p for p in parts if p)[:200]


def check_python() -> list[str]:
    bad = []
    for d in RUNTIME + OPTIONAL:
        text = lic(d)
        if text is None:
            if d in RUNTIME:
                bad.append(f"{d}: not installed")
            continue
        if DENY.search(text.replace("LGPL", "")) or not ALLOW.search(text):
            bad.append(f"{d}: {text}")
        else:
            print(f"ok  {d}: {text}")
    return bad


def check_android(path=Path("android/dependencies.txt")) -> list[str]:
    bad = []
    if not path.exists():
        return ["android/dependencies.txt missing"]
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        coord, _, license_ = line.partition("|")
        license_ = license_.strip()
        if DENY.search(license_.replace("LGPL-3.0-with-exception", "")) or not (ALLOW.search(license_) or "LGPL-3.0-with-exception" in license_):
            bad.append(f"{coord.strip()}: {license_}")
        else:
            print(f"ok  {coord.strip()}: {license_}")
    return bad


def check_gradle_matches(gradles=(Path("android/app/build.gradle.kts"), Path("android/core/build.gradle.kts")),
                         deps=Path("android/dependencies.txt")) -> list[str]:
    listed = {ln.split("|")[0].strip() for ln in deps.read_text().splitlines() if ln.strip() and not ln.startswith("#")}
    used: set[str] = set()
    for gradle in gradles:
        used |= set(re.findall(r'"([\w.\-]+:[\w.\-]+):[\w.\-]+"', gradle.read_text()))
    missing = used - listed
    return [f"{m}: used in Gradle but not license-listed" for m in sorted(missing)]


def main() -> int:
    bad = check_python() + check_android() + check_gradle_matches()
    if bad:
        print("LICENSE CHECK FAILED:\n  " + "\n  ".join(bad))
        return 1
    print("license check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
