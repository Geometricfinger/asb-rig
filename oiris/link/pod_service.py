"""Pod-side request handler behind the Noise link (phone app = client). Adds the thermal live
view feed (P3) to the face-match EnrollmentServer ops. Requests/responses are canonical JSON
inside Noise frames (security/channel.fragment / Reassembler), carried over BLE by ble.py."""
from __future__ import annotations
import json
from typing import Any, Callable

import numpy as np

from ..security.channel import Reassembler, SecureChannel, fragment


def _dumps(d: dict) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class PodService:
    def __init__(self, thermal: Callable[[], np.ndarray | None] = lambda: None, enrollment: Any = None):
        self.thermal, self.enrollment = thermal, enrollment

    def handle(self, raw: bytes | str) -> str:
        try:
            req = json.loads(raw)
            op = req.get("op")
        except (ValueError, AttributeError):
            return _dumps({"ok": False, "error": "bad request"})
        if op == "thermal":
            f = self.thermal()
            if f is None:
                return _dumps({"ok": True, "w": None, "h": None, "celsius": []})
            a = np.asarray(f, float)
            if a.ndim != 2:
                return _dumps({"ok": False, "error": "bad thermal frame"})
            return _dumps({"ok": True, "h": int(a.shape[0]), "w": int(a.shape[1]),
                           "celsius": [round(float(x), 1) for x in a.ravel()]})
        if self.enrollment is not None:
            return str(self.enrollment.handle(raw))
        return _dumps({"ok": False, "error": f"unknown op {op!r}"})


def serve_once(ch: SecureChannel, rx: Reassembler, transport, svc: PodService, timeout_s: float = 5.0) -> bool:
    """Read one request from the transport, answer it. Returns False on timeout."""
    while True:
        f = transport.receive(timeout_s)
        if f is None:
            return False
        msg = rx.feed(f)
        if msg is not None:
            for out in fragment(ch, svc.handle(msg).encode()):
                transport.send(out)
            return True
