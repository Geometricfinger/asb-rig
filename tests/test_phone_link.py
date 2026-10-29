"""Phone link interop: Noise vectors shared with the Kotlin port, and the EnrollmentPort over a
real SecureChannel pair (test-only synthetic backend; no real faces)."""
import base64, json
from pathlib import Path

import numpy as np

from oiris.modules.face_match.backends.test_deterministic import TestDeterministicBackend, synth_face_frame
from oiris.modules.face_match.core import FaceMatchConfig, FaceMatchModule
from oiris.modules.face_match.port import REQUIRED_ANGLES
from oiris.modules.face_match.remote import EnrollmentServer, dumps
from oiris.security.channel import Reassembler, SecureChannel, fingerprint, fragment, new_static, pub_from_priv
from tests.test_face_match import env  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
VEC = json.loads((ROOT / "tests" / "vectors" / "noise_xx.json").read_text())


def test_noise_vectors_reproduce_from_python():
    import importlib.util
    spec = importlib.util.spec_from_file_location("mk", ROOT / "scripts" / "make_noise_vectors.py")
    mk = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert mk.generate() == VEC


def test_vector_fingerprints_match_channel():
    assert fingerprint(bytes.fromhex(VEC["resp_static_pub"])) == VEC["resp_fingerprint"]
    assert pub_from_priv(bytes.fromhex(VEC["init_static"])).hex() == VEC["init_static_pub"]


def _pair():
    pk, ph = new_static(), new_static()
    pod = SecureChannel(False, pk, fingerprint(pub_from_priv(ph)))
    phone = SecureChannel(True, ph, fingerprint(pub_from_priv(pk)))
    pod.read_handshake(phone.write_handshake())
    phone.read_handshake(pod.write_handshake())
    pod.read_handshake(phone.write_handshake())
    return pod, phone


def test_enrollment_over_secure_channel(env):  # noqa: F811
    def factory():
        return FaceMatchModule(env["db"], env["ks"], env["dir"], TestDeterministicBackend(), env["chain"],
                               FaceMatchConfig(modes=["personal"], allow_test_backend=True), env["consents"])
    srv = EnrollmentServer(env["db"], env["chain"], "phone1", factory)
    pod, phone = _pair()

    rx_pod, rx_phone = Reassembler(pod), Reassembler(phone)

    def call(req: dict) -> dict:
        got = None
        for f in fragment(phone, dumps(req).encode()):
            got = rx_pod.feed(f)
        assert got is not None
        out = None
        for f in fragment(pod, srv.handle(got).encode()):
            out = rx_phone.feed(f)
        return json.loads(out)

    assert call({"op": "status"}) == {"ok": True, "opted_in": False, "modes": []}
    assert call({"op": "start_session"})["ok"] is False                     # locked until opt-in
    warn = call({"op": "warning", "jurisdiction": "us-other"})["text"]
    assert call({"op": "opt_in", "typed": "i understand", "modes": ["personal"], "warning_shown": warn})["ok"] is False
    assert call({"op": "opt_in", "typed": "I UNDERSTAND", "modes": ["personal"], "warning_shown": warn, "jurisdiction": "us-other"})["ok"]
    sid = call({"op": "start_session"})["session"]
    pid = call({"op": "add_person", "session": sid, "label": "Alex", "consent_id": "c-ok", "guardian": False})["person"]

    def shot(a, **kw):
        g = np.clip(synth_face_frame(5, a, **kw), 0, 255).astype(np.uint8)
        return call({"op": "shot", "person": pid, "angle": a.value, "w": g.shape[1], "h": g.shape[0], "fmt": "gray",
                     "pixels_b64": base64.b64encode(g.tobytes()).decode()})
    r = shot(REQUIRED_ANGLES[0], blur=True)
    assert r["ok"] and r["accepted"] is False and "blurry" in r["reason"]
    for a in REQUIRED_ANGLES:
        assert shot(a)["accepted"], a
    fin = call({"op": "finish", "person": pid})
    assert fin["complete"] is True
    assert call({"op": "end_session", "session": sid})["ok"]
    assert call({"op": "shot", "person": pid, "angle": "front", "w": 2, "h": 2, "pixels_b64": "AAAA"})["ok"] is False
    assert call({"op": "status"})["opted_in"] is True


def test_vector_requests_are_accepted_shape(env):  # noqa: F811
    reqs = json.loads((ROOT / "tests" / "vectors" / "enrollment_protocol.json").read_text())["requests"]
    srv = EnrollmentServer(env["db"], env["chain"], "phone1", lambda: None)
    for name, raw in reqs.items():
        out = json.loads(srv.handle(raw))
        assert "ok" in out, name
    assert json.loads(srv.handle("not json"))["ok"] is False
