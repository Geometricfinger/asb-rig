"""Minimal local dashboard (stdlib only). Binds 127.0.0.1 only. Zones follow the design
bot's C6 map: D1 status strip, D2 sighting table, D3 map pins, D4 sweep timeline,
D5 sensor health, D6 review queue. Headless scenario data when no rig is attached."""
from __future__ import annotations
import html, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..config import Config
from ..headless import run_scenario
from ..store.sightings import OSM_ATTRIBUTION

PAGE = """<!doctype html><meta charset=utf-8><title>ASB dashboard</title>
<style>body{{font:14px system-ui;margin:0;display:grid;grid-template:auto 1fr 1fr/1fr 1fr 1fr;gap:8px;padding:8px}}
section{{border:1px solid #888;padding:8px}} #D1{{grid-column:1/4}} h2{{font-size:13px;margin:0 0 6px}}</style>
<section id=D1><h2>D1 Status</h2>{status}</section>
<section id=D2><h2>D2 Signatures (latest)</h2>{sigs}</section>
<section id=D3><h2>D3 Map pins</h2>Offline map layer. <small>{attr}</small></section>
<section id=D4><h2>D4 Sweep timeline</h2>No sweeps in demo mode.</section>
<section id=D5><h2>D5 Sensor health</h2>{health}</section>
<section id=D6><h2>D6 Review queue</h2>Confirmed/benign sightings awaiting review appear here.</section>
<p style="grid-column:1/4"><a href="/face">Face match (M-16, optional, off by default)</a></p>
<p style="grid-column:1/4"><small>Research tool. Signatures are observations with benign causes; never an identity.</small></p>"""


def render(res: dict) -> str:
    sigs = "".join(f"<li>{html.escape(s)}</li>" for s in res["signatures"]) or "none"
    health = "".join(f"<li>{html.escape(k)}: {html.escape(v['health'] if isinstance(v, dict) else str(v))}</li>"
                     for k, v in res.get("health", {}).items()) or "headless (no live adapters)"
    status = f"Level: <b>{html.escape(str(res['level'] or 'none'))}</b> · index {res['anomaly_index']:.2f}"
    return PAGE.format(status=status, sigs=f"<ul>{sigs}</ul>", attr=html.escape(OSM_ATTRIBUTION), health=f"<ul>{health}</ul>")


def serve(cfg: Config, port: int = 8765, scenario: str = "quiet", face_module=None) -> None:
    from .face import FaceReview
    face = FaceReview(face_module)

    class H(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
            self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            n = min(int(self.headers.get("Content-Length") or 0), 65536)
            code, msg = face.post(self.path, self.rfile.read(n).decode("utf-8", "replace"))
            self._send(code, face.render(msg).encode())

        def do_GET(self):
            if self.path == "/face":
                return self._send(200, face.render().encode())
            res = run_scenario(scenario, 1, config=cfg)[-1]
            body = json.dumps(res).encode() if self.path == "/api/latest" else render(res).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json" if self.path == "/api/latest" else "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.end_headers(); self.wfile.write(body)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
