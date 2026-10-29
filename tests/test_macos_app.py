"""macOS .app bundle structure (built on any OS; no deps download in tests)."""
import plistlib, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_app_bundle_layout(tmp_path):
    whl = tmp_path / "o_iris-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(whl, "w") as z:
        z.writestr("oiris/__init__.py", "")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_macos_app.py"), "--wheel", str(whl), "--out", str(tmp_path),
                        "--commit", "abc123def4567890"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    app = tmp_path / "O Iris.app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "o-iris" and info["CFBundlePackageType"] == "APPL" and info["OIrisCommit"].startswith("abc123")
    launcher = app / "Contents" / "MacOS" / "o-iris"
    assert launcher.stat().st_mode & 0o111
    txt = launcher.read_text()
    assert "--no-index" in txt and "127.0.0.1" in txt and "0.1.0+abc123def456" in txt
    assert (app / "Contents" / "Resources" / "wheels" / whl.name).exists()
    assert (app / "Contents" / "Resources" / "LICENSE").exists()
    assert subprocess.run(["bash", "-n", str(launcher)]).returncode == 0
