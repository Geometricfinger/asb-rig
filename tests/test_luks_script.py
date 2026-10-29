"""Pi LUKS2 script: dry-run plan, idempotency, refusals. Tool binaries are faked on PATH; nothing touches a disk."""
import os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pi_luks2_setup.sh"


def fake_env(tmp_path, is_luks=False):
    b = tmp_path / "bin"; b.mkdir()
    log = tmp_path / "calls.log"
    for tool in ("cryptsetup", "blkid", "mkfs.ext4", "mount", "mountpoint"):
        code = "1"
        if tool == "cryptsetup":
            code = '$( [ "$1" = isLuks ] && echo %d || echo 0 )' % (0 if is_luks else 1)
        if tool == "mount":
            code = "0"
        (b / tool).write_text(f'#!/bin/sh\necho "{tool} $*" >> {log}\nexit {code}\n'); (b / tool).chmod(0o755)
    env = dict(os.environ, PATH=f"{b}:{os.environ['PATH']}", OIRIS_CRYPTTAB=str(tmp_path / "crypttab"), OIRIS_FSTAB=str(tmp_path / "fstab"))
    return env, log


def run(env, *args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env)


def test_dry_run_prints_plan_and_changes_nothing(tmp_path):
    env, log = fake_env(tmp_path)
    r = run(env, "--device", "/dev/fake1", "--mount", str(tmp_path / "mnt"), "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "DRY-RUN: cryptsetup luksFormat --type luks2 --pbkdf argon2id" in r.stdout
    assert "DRY-RUN: append to" in r.stdout and "noauto" in r.stdout
    calls = log.read_text() if log.exists() else ""
    assert "luksFormat" not in calls and "mkfs" not in calls and "open" not in calls
    assert not (tmp_path / "crypttab").exists() and not (tmp_path / "mnt").exists()


def test_dry_run_idempotent_when_already_luks_and_entries_present(tmp_path):
    env, _ = fake_env(tmp_path, is_luks=True)
    (tmp_path / "crypttab").write_text("oiris_data UUID=<luks-uuid> none luks,noauto\n")
    r = run(env, "--device", "/dev/fake1", "--mount", "/m", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "already LUKS" in r.stdout and "luksFormat" not in r.stdout
    assert f"ok: {tmp_path / 'crypttab'} already has entry" in r.stdout


def test_refuses_bad_args(tmp_path):
    env, _ = fake_env(tmp_path)
    assert run(env, "--dry-run").returncode == 2
    assert run(env, "--device", "/dev/x", "--name", "bad name", "--dry-run").returncode == 2
