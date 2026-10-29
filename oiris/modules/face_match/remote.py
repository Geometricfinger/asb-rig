"""EnrollmentPort over the pod<->phone SecureChannel (spec 7.3: "used by the phone app").

The phone only guides and captures; this pod-side handler runs every check (opt-in, consent,
quality, angle), builds and seals templates. Requests/responses are canonical JSON
(`sort_keys`, compact) inside Noise transport frames; frames are raw 8-bit pixels, `fmt` "bgr" (w*h*3) or "gray" (w*h), base64.
Messages over 60 kB travel as several Noise frames (`security.channel.fragment` / `Reassembler`).
Errors come back as {"ok": false, "error": ...}; nothing here raises to the transport.
There is no count limit anywhere (spec 7.3)."""
from __future__ import annotations
import base64, json
from typing import Any, Callable

import numpy as np

from . import optin
from .port import Angle

MAX_SIDE = 1280   # refuse absurd frames (memory), not people


def dumps(d: dict) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


class EnrollmentServer:
    def __init__(self, db, chain, device_id: str, factory: Callable[[], Any], module: Any = None):
        self.db, self.chain, self.device_id, self.factory, self.m = db, chain, device_id, factory, module

    def handle(self, raw: bytes | str) -> str:
        try:
            req = json.loads(raw)
            return dumps({"ok": True, **self._op(req)})
        except Exception as e:  # noqa: BLE001  (fault isolation: report, never crash the link)
            return dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:200]})

    def _mod(self):
        if self.m is None:
            raise PermissionError("face matching is off; opt in first")
        return self.m

    def _op(self, r: dict) -> dict:
        op = r.get("op")
        if op == "status":
            rec = optin.opt_in_record(self.db)
            return {"opted_in": rec is not None and self.m is not None, "modes": rec["modes"] if rec else []}
        if op == "warning":
            return {"text": optin.warning_for(r.get("jurisdiction", "strictest"))}
        if op == "opt_in":
            rec = optin.record_opt_in(self.db, self.chain, r["typed"], list(r["modes"]), self.device_id,
                                      r.get("jurisdiction", "strictest"), warning_shown=r.get("warning_shown"))
            self.m = self.factory()
            return {"modes": rec["modes"]}
        m = self._mod()
        if op == "start_session":
            return {"session": m.start_session()}
        if op == "add_person":
            return {"person": m.add_person(r["session"], r["label"], r.get("consent_id"), bool(r.get("guardian", False)))}
        if op == "shot":
            w, h = int(r["w"]), int(r["h"])
            if not (0 < w <= MAX_SIDE and 0 < h <= MAX_SIDE):
                raise ValueError("frame size out of range")
            ch = {"bgr": 3, "gray": 1}[r.get("fmt", "bgr")]
            buf = bytearray(base64.b64decode(r["pixels_b64"], validate=True))
            if len(buf) != w * h * ch:
                raise ValueError("frame bytes do not match w*h*channels")
            frame = np.frombuffer(bytes(buf), np.uint8).reshape((h, w, 3) if ch == 3 else (h, w)).copy()
            buf[:] = b"\0" * len(buf)
            try:
                res = m.submit_shot(r["person"], frame, Angle(r["angle"]))
            finally:
                frame.fill(0)
            needed = sorted(getattr(a, "value", a) for a in res.needed_angles)
            return {"accepted": res.ok, "code": res.code, "reason": res.reason, "needed": needed}
        if op == "finish":
            st = m.finish_person(r["person"])
            return {"complete": st.complete, "message": st.message, "missing": sorted(getattr(a, "value", a) for a in st.missing_angles)}
        if op == "end_session":
            m.end_session(r["session"]); return {}
        raise ValueError(f"unknown op {op!r}")
