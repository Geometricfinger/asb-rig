#!/usr/bin/env python3
"""Build an UNSIGNED macOS `O Iris.app` bundle around the project wheel (M-10 artifact).

Layout: Contents/Info.plist, Contents/MacOS/o-iris (launcher), Contents/Resources/wheels/*.whl.
First launch creates a private venv in ~/Library/Application Support/O Iris using the system
python3 (>= 3.11), installs the bundled wheels with --no-index (offline), then starts the
local dashboard (127.0.0.1) and opens it. No network, no signing, no paid service.
Signing/notarization steps for someone with an Apple Developer account: docs/MACOS.md.

  python scripts/make_macos_app.py --wheel dist/X/o_iris-*.whl --out dist/X [--bundle-deps] [--commit SHA]
"""
from __future__ import annotations
import argparse, os, plistlib, shutil, stat, subprocess, sys
from pathlib import Path

LAUNCHER = r"""#!/bin/bash
# O Iris launcher (unsigned). Offline: installs only the wheels inside this bundle.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SUPPORT="$HOME/Library/Application Support/O Iris"
VENV="$SUPPORT/venv"
PY="${OIRIS_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$PY" ]] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
  osascript -e 'display alert "O Iris needs Python 3.11 or newer" message "Install it from python.org, then open O Iris again."' || true
  exit 1
fi
STAMP="$VENV/.oiris-version"
if [[ ! -f "$STAMP" || "$(cat "$STAMP")" != "@VERSION@" ]]; then
  mkdir -p "$SUPPORT"; "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install --no-index --find-links "$HERE/Resources/wheels" o-iris
  echo "@VERSION@" > "$STAMP"
fi
PORT="${OIRIS_PORT:-8765}"
( sleep 1; open "http://127.0.0.1:$PORT/" ) &
exec "$VENV/bin/oiris" dashboard --port "$PORT"
"""


def build(wheel: Path, out: Path, version: str, commit: str, bundle_deps: bool) -> Path:
    app = out / "O Iris.app"
    if app.exists():
        shutil.rmtree(app)
    macos, res = app / "Contents" / "MacOS", app / "Contents" / "Resources" / "wheels"
    macos.mkdir(parents=True); res.mkdir(parents=True)
    shutil.copy2(wheel, res / wheel.name)
    if bundle_deps:
        for pv in ("3.11", "3.12", "3.13"):   # the user's python3 may be any supported version
            subprocess.run([sys.executable, "-m", "pip", "download", "--only-binary=:all:", "--python-version", pv,
                            "-d", str(res), str(wheel)], check=True)
    info = {"CFBundleName": "O Iris", "CFBundleDisplayName": "O Iris", "CFBundleIdentifier": "io.github.geometricfinger.oiris",
            "CFBundleVersion": version, "CFBundleShortVersionString": version, "CFBundlePackageType": "APPL",
            "CFBundleExecutable": "o-iris", "LSMinimumSystemVersion": "11.0", "NSHighResolutionCapable": True,
            "OIrisCommit": commit, "LSApplicationCategoryType": "public.app-category.developer-tools"}
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(info, f)
    lp = macos / "o-iris"
    lp.write_text(LAUNCHER.replace("@VERSION@", f"{version}+{commit[:12]}"), encoding="utf-8")
    lp.chmod(lp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY.md"):
        src = Path(__file__).resolve().parents[1] / name
        if src.exists():
            shutil.copy2(src, app / "Contents" / "Resources" / name)
    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--commit", default=os.environ.get("ASB_COMMIT", "unknown"))
    ap.add_argument("--version", default="0.1.0")
    ap.add_argument("--bundle-deps", action="store_true")
    a = ap.parse_args()
    print(build(a.wheel, a.out, a.version, a.commit, a.bundle_deps))
