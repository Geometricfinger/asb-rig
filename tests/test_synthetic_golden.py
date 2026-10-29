"""Seed synthetic golden set: hashes, frozen test split, synthetic-only, replay == expectations."""
import subprocess, sys
from pathlib import Path

from oiris.modules.golden import Manifest

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "golden" / "synthetic"


def test_manifest_is_synthetic_frozen_and_verifies():
    m = Manifest.load(G / "manifest.json")
    assert m.clips and all(c.source_tier == "synthetic" and not c.contains_person for c in m.clips)
    assert m.frozen_test_hash == m.test_hash()
    assert m.verify(G) == []


def test_check_tool_passes():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_synthetic_golden.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
