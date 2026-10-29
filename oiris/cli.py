"""`oiris` command line. Examples:
  oiris --headless --scenario camera_lens --steps 3
  oiris --headless --replay golden/clips/camera_lens
  oiris check-phrases | license-audit | selftest | dashboard
  oiris face-match status|enable|fetch-models|enroll|review|delete-entry|delete-person|disable  (M-16, opt-in)
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from . import __version__
from .config import Config, ConfigError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="oiris", description="Anomaly Signature Bench (research tool; no identity output)")
    p.add_argument("command", nargs="?", default="run",
                   choices=["run", "selftest", "check-phrases", "dashboard", "record", "version", "face-match"])
    p.add_argument("sub", nargs="?", help="face-match subcommand")
    p.add_argument("--mode", action="append", choices=["personal", "research"], help="face-match enable: mode(s)")
    p.add_argument("--jurisdiction", help="face-match enable: jurisdiction profile (unknown -> strictest)")
    p.add_argument("--camera", type=int, help="face-match enroll: capture from this camera index")
    p.add_argument("--id", help="face-match delete-entry/delete-person: entry or person ID")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--scenario", default="quiet")
    p.add_argument("--replay", type=Path)
    p.add_argument("--steps", type=int, default=3)
    p.add_argument("--config", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--expect", type=Path, help="compare output to an expected JSON file; exit 1 on mismatch")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args(argv)
    try:
        cfg = Config.load(a.config)
    except ConfigError as e:
        print(f"config invalid: {e}", file=sys.stderr)
        return 2
    if a.command == "face-match":
        from .face_match_cli import run
        return run(a, cfg, a.config or Path(cfg.data_dir).expanduser() / "config.json")
    if a.command == "version":
        print(__version__); return 0
    if a.command == "check-phrases":
        from .guard.phrases import audit_all
        audit_all(); print("all phrase templates pass the vocabulary guard"); return 0
    if a.command == "record":
        from .headless import record_clip
        record_clip(a.scenario, a.out or Path(f"clip_{a.scenario}"), a.steps); return 0
    if a.command == "dashboard":
        from .dashboard.server import serve
        face = None
        if cfg.enabled("M-16"):  # the face-match page is live only when M-16 is on AND opted in
            from .face_match_cli import _ctx
            from .modules import face_match_gate
            from .registry import default_registry
            _, ks, db, chain = _ctx(cfg)
            try:
                face = face_match_gate.load(cfg, db, ks, default_registry(), chain=chain)
            except PermissionError as e:
                print(f"face match page disabled: {e}")
        serve(cfg, port=a.port, face_module=face); return 0
    if a.command == "selftest" or a.headless:
        from .headless import run_replay, run_scenario
        res = run_replay(a.replay, None, cfg) if a.replay else run_scenario(a.scenario, a.steps, config=cfg)
        txt = json.dumps(res, indent=1, sort_keys=True)
        if a.out:
            a.out.write_text(txt, encoding="utf-8")
        else:
            print(txt)
        if a.expect:
            ok = json.loads(a.expect.read_text(encoding="utf-8")) == json.loads(txt)
            print("golden: PASS" if ok else "golden: FAIL", file=sys.stderr)
            return 0 if ok else 1
        return 0
    print("live mode needs hardware adapters configured; see docs/EXTENDING.md", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
