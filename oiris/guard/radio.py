"""Passive-only RF guard. ASB never transmits, jams, deauths or uses monitor mode.
Refuses to run if a wireless interface is in monitor mode or a banned tool is requested."""
from __future__ import annotations
import re, shutil, subprocess

BANNED_COMMANDS = {"aireplay-ng", "mdk3", "mdk4", "hackrf_transfer", "rpitx", "airmon-ng", "tx", "sendiq",
                   "bettercap", "wifijammer"}
BANNED_ARGS = re.compile(r"(monitor|deauth|inject|--tx|transmit|set\s+type\s+monitor|jam)", re.I)
ALLOWED_COMMANDS = {"iw", "rtl_power", "rtl_test"}


class RadioPolicyError(PermissionError):
    pass


def check_command(argv: list[str]) -> list[str]:
    if not argv:
        raise RadioPolicyError("empty command")
    exe = argv[0].rsplit("/", 1)[-1]
    if exe in BANNED_COMMANDS or exe not in ALLOWED_COMMANDS:
        raise RadioPolicyError(f"radio tool {exe!r} not allowed (passive-only policy)")
    joined = " ".join(argv[1:])
    if BANNED_ARGS.search(joined):
        raise RadioPolicyError(f"argument not allowed: {joined}")
    if exe == "iw" and not (argv[1:] == ["dev"] or (len(argv) >= 4 and argv[1] == "dev" and argv[3] in ("scan", "info", "link"))):
        raise RadioPolicyError("iw only allowed for 'dev <if> scan|info|link'")
    return argv


def interfaces_in_monitor_mode(iw_dev_output: str | None = None) -> list[str]:
    if iw_dev_output is None:
        if not shutil.which("iw"):
            return []
        iw_dev_output = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5).stdout
    out, cur = [], None
    for line in iw_dev_output.splitlines():
        line = line.strip()
        if line.startswith("Interface "):
            cur = line.split()[1]
        elif line.startswith("type ") and line.split()[1] == "monitor" and cur:
            out.append(cur)
    return out


def assert_passive(iw_dev_output: str | None = None) -> None:
    mon = interfaces_in_monitor_mode(iw_dev_output)
    if mon:
        raise RadioPolicyError(f"refusing to run: monitor mode on {mon}")


def run_passive(argv: list[str], timeout: float = 30) -> str:
    check_command(argv)
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout).stdout
