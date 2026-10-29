"""Dashboard: zones render; M-16 review page (browse, delete entry/person, disable+wipe, token, off state)."""
# ruff: noqa: F811
import threading, urllib.request
from urllib.parse import urlencode

from oiris.dashboard.face import FaceReview
from oiris.dashboard.server import render
from oiris.headless import run_scenario
from oiris.modules.face_match.backends.test_deterministic import synth_face_frame
from oiris.modules.face_match.port import REQUIRED_ANGLES
from tests.test_face_match import enroll, env, make  # noqa: F401,F811  (fixture reuse)


def test_main_page_zones_and_face_link():
    page = render(run_scenario("quiet", 1)[-1])
    for z in ("D1", "D2", "D3", "D4", "D5", "D6"):
        assert f"id={z}" in page
    assert 'href="/face"' in page


def test_face_page_off_shows_guide_and_refuses_posts():
    r = FaceReview(None, token="t")
    page = r.render()
    assert "off</b>" in page and "I UNDERSTAND" in page and all(a in page for a in ("front", "left", "right", "up", "down"))
    assert r.post("/face/disable", "token=t&confirm=WIPE")[0] == 409


def _module_with_match(env):
    m = make(env)
    sid = m.start_session()
    pid = enroll(m, sid, 7, name="Alex")
    m.end_session(sid)
    m.process_frame(synth_face_frame(7, REQUIRED_ANGLES[0], noise_seed=3), place="Home")
    return m, pid


def test_review_browse_delete_entry_and_person(env):
    m, pid = _module_with_match(env)
    r = FaceReview(m, token="t")
    page = r.render()
    assert "Alex" in page and "possible match" in page and "Delete entry" in page
    assert "robot" not in page.lower()
    eid = m.review_log()["people"][0]["entries"][0]["entry_id"]
    assert r.post("/face/entry/delete", urlencode({"token": "bad", "id": eid}))[0] == 403
    assert r.post("/face/entry/delete", urlencode({"token": "t", "id": eid})) == (200, "entry deleted")
    assert m.review_log()["people"][0]["entries"] == []
    code, msg = r.post("/face/person/delete", urlencode({"token": "t", "id": pid}))
    assert code == 200 and "verified" in msg
    assert m.review_log()["people"] == []
    assert r.post("/face/person/delete", urlencode({"token": "t", "id": pid}))[0] == 404


def test_disable_requires_typed_wipe_and_verifies(env):
    m, _ = _module_with_match(env)
    r = FaceReview(m, token="t")
    assert r.post("/face/disable", "token=t&confirm=yes")[0] == 400
    code, msg = r.post("/face/disable", "token=t&confirm=WIPE")
    assert code == 200 and "verified" in msg
    assert env["db"].execute("SELECT COUNT(*) FROM fm_enrolled").fetchone()[0] == 0
    assert "off</b>" in r.render()


def test_http_server_binds_localhost_and_serves_face_page():
    import socket
    from oiris.config import Config
    from oiris.dashboard import server
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    threading.Thread(target=server.serve, args=(Config(), port), daemon=True).start()
    import time
    for _ in range(50):
        try:
            body = urllib.request.urlopen(f"http://127.0.0.1:{port}/face", timeout=2).read().decode()
            break
        except OSError:
            time.sleep(0.1)
    assert "Status: <b>off</b>" in body
    req = urllib.request.Request(f"http://127.0.0.1:{port}/face/disable", data=b"token=x", method="POST")
    try:
        urllib.request.urlopen(req, timeout=2); raise AssertionError("expected 403")
    except urllib.error.HTTPError as e:
        assert e.code == 403
