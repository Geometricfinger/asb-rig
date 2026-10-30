#!/usr/bin/env bash
# M-10: build the Android APK and the macOS artifact from ONE clean commit, record both
# hashes in BUILD_INFO.json, verify they carry the same commit. Unsigned (no secrets used).
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "$(git status --porcelain)" && "${ASB_ALLOW_DIRTY:-0}" != "1" ]]; then
  echo "refusing: working tree is dirty (commit first)"; exit 2
fi
COMMIT=$(git rev-parse HEAD)
export ASB_COMMIT=$COMMIT
OUT=dist/$COMMIT
mkdir -p "$OUT"

# 1) Android APK (unsigned release + debug for install testing)
( cd android && gradle --no-daemon :core:check assembleDebug assembleRelease )   # :core:check = JVM checks vs shared vectors
cp android/app/build/outputs/apk/debug/app-debug.apk "$OUT/o-iris-$COMMIT-debug.apk"
cp android/app/build/outputs/apk/release/app-release-unsigned.apk "$OUT/o-iris-$COMMIT-release-unsigned.apk"

# 2) Host artifact: wheel + self-test (on macOS this is the macOS artifact)
python3 -m pip wheel --no-deps -w "$OUT" . >/dev/null
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
python3 -m oiris.cli selftest --scenario camera_lens --steps 3 --expect golden/expected/camera_lens.json
if [[ "$OS" == "darwin" ]]; then
  # unsigned .app bundle (offline wheels inside); zipped with ditto to keep bundle metadata
  python3 scripts/make_macos_app.py --wheel "$(ls "$OUT"/o_iris-*.whl)" --out "$OUT" --commit "$COMMIT" --bundle-deps
  # M-15 Keychain biometric gate helper (Swift; LocalAuthentication + Security frameworks)
  swiftc -O macos/keychain_gate/main.swift -o "$OUT/O Iris.app/Contents/MacOS/keychain-gate"
  "$OUT/O Iris.app/Contents/MacOS/keychain-gate" status      # runs on CI; no biometrics there -> {"biometry": false}
  OIRIS_MAC_GATE_HELPER="$OUT/O Iris.app/Contents/MacOS/keychain-gate" python3 -m pytest -q tests/test_audit_gaps.py -k "real_swift_helper or keychain"
  ditto -c -k --keepParent "$OUT/O Iris.app" "$OUT/o-iris-$COMMIT-macos-app-unsigned.zip"
  rm -rf "$OUT/O Iris.app"
fi
tar -czf "$OUT/o-iris-$COMMIT-$OS.tar.gz" -C "$OUT" "$(cd "$OUT" && ls o_iris-*.whl)" -C "$PWD" README.md LICENSE NOTICE THIRD_PARTY.md

# 3) Manifest
python3 - "$OUT" "$COMMIT" <<'PY'
import hashlib, json, pathlib, platform, subprocess, sys
out, commit = pathlib.Path(sys.argv[1]), sys.argv[2]
arts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.suffix in (".apk", ".gz", ".whl", ".zip")}
info = {"commit": commit, "host": platform.platform(), "python": platform.python_version(), "artifacts": arts}
assert all(commit in n for n in arts if n.endswith((".apk", ".gz", ".zip"))), "artifact commit mismatch"
(out / "BUILD_INFO.json").write_text(json.dumps(info, indent=2))
print(json.dumps(info, indent=2))
PY
