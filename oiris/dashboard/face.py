"""M-16 face-match review page for the local dashboard (spec sections 7.3, 9, 14).

Stdlib only. The page exists only when the caller hands in a live FaceMatchModule (M-16 on
and opted in); otherwise it shows the off-by-default notice and the enrollment guide.
Every state change is a POST carrying a per-process token (the server binds 127.0.0.1 and
the CSP forbids cross-origin form posts). Disable+wipe additionally requires typing WIPE.
Wording stays neutral: "possible match", never an alert, never a judgement about anyone."""
from __future__ import annotations
import html, secrets, time
from typing import Any
from urllib.parse import parse_qs

ANGLES = ("front", "left", "right", "up", "down")

GUIDE = """<h2>Enrollment guide</h2><ol>
<li>M-16 is <b>off by default</b>. Turn it on only with <code>oiris face-match enable</code> and type <code>I UNDERSTAND</code>
after reading the warning.</li>
<li>Enroll only people who agreed (record their consent). Strangers are never enrolled; research mode stores counts only.</li>
<li>Capture 5&ndash;10 shots per person, at least one at each angle: front, left, right, up, down.
Good light, one face in frame, face fills a fair part of the image, hold still (blurred shots are rejected).</li>
<li>Run <code>oiris face-match enroll --name NAME</code>; the checklist below ticks off each angle as accepted.</li>
<li>Review possible matches here. Delete any entry or person at any time. Disabling destroys every template and the key,
then verifies the wipe.</li></ol>"""

STYLE = ("body{font:14px system-ui;margin:16px;max-width:900px}table{border-collapse:collapse}"
         "td,th{border:1px solid #888;padding:4px 6px}form{display:inline}.badge{background:#eee;padding:1px 4px}")


class FaceReview:
    def __init__(self, module: Any = None, token: str | None = None):
        self.module = module
        self.token = token or secrets.token_urlsafe(24)

    def _form(self, action: str, label: str, extra: str = "") -> str:
        return (f'<form method=post action="{html.escape(action)}"><input type=hidden name=token value="{self.token}">'
                f'{extra}<button>{html.escape(label)}</button></form>')

    def render(self, msg: str = "") -> str:
        m = self.module
        out = [f"<!doctype html><meta charset=utf-8><title>Face match review</title><style>{STYLE}</style>",
               "<h1>M-16 face match (optional)</h1>"]
        if msg:
            out.append(f"<p><b>{html.escape(msg)}</b></p>")
        if m is None or not getattr(m, "modes", None):
            out.append("<p>Status: <b>off</b>. Nothing is captured, stored or matched.</p>")
            out.append(GUIDE + self._checklist(set()))
            return "".join(out)
        h, why = m.health()
        out.append(f"<p>Status: <b>on</b> · modes: {html.escape(', '.join(sorted(m.modes)))} · "
                   f"health: {html.escape(getattr(h, 'value', str(h)))} {html.escape(why or '')}</p>")
        log = m.review_log()
        out.append("<h2>Enrolled people</h2>")
        if not log["people"]:
            out.append("<p>No one enrolled.</p>")
        for p in log["people"]:
            pid = p["person_id"]
            badge = " <span class=badge>no consent recorded</span>" if p["no_consent_badge"] else ""
            out.append(f"<h3>{html.escape(p['name'])}{badge}</h3>")
            if p["hint"]:
                out.append(f"<p><small>{html.escape(p['hint'])}</small></p>")
            out.append("<ul>" + "".join(f"<li>{html.escape(s)}</li>" for s in p["summary"]) + "</ul>")
            if p["entries"]:
                out.append("<table><tr><th>When</th><th>Where</th><th>Confidence</th><th></th></tr>")
                for e in p["entries"]:
                    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(e["seen_at"]))
                    out.append(f"<tr><td>{when}</td><td>{html.escape(e['place'])}</td><td>{e['confidence']:.2f}</td>"
                               f"<td>{self._form('/face/entry/delete', 'Delete entry', self._hid('id', e['entry_id']))}</td></tr>")
                out.append("</table>")
            out.append(self._form("/face/person/delete", f"Delete {p['name']} and all their data", self._hid("id", pid)))
        if log["unrecognized_counts"]:
            out.append("<h2>Research counts (no face data)</h2><table><tr><th>Place</th><th>Date</th><th>Count</th></tr>")
            out += [f"<tr><td>{html.escape(c['place'])}</td><td>{html.escape(str(c['date']))}</td><td>{int(c['count'])}</td></tr>"
                    for c in log["unrecognized_counts"]]
            out.append("</table>")
        out.append("<h2>Disable and wipe</h2><p>Destroys every template, the key and (unless kept) the logs, then verifies.</p>")
        out.append(self._form("/face/disable", "Disable M-16 and wipe", '<input name=confirm placeholder="type WIPE"> '))
        out.append(GUIDE + self._checklist(set()))
        return "".join(out)

    @staticmethod
    def _hid(k: str, v: str) -> str:
        return f'<input type=hidden name={k} value="{html.escape(v)}">'

    @staticmethod
    def _checklist(done: set) -> str:
        return "<h3>Angle checklist</h3><ul>" + "".join(
            f"<li>{'&#9745;' if a in done else '&#9744;'} {a}</li>" for a in ANGLES) + "</ul>"

    def post(self, path: str, body: str) -> tuple[int, str]:
        """Handle a form POST. Returns (status, message). Never raises to the HTTP layer."""
        f = {k: v[0] for k, v in parse_qs(body).items()}
        if not secrets.compare_digest(f.get("token", ""), self.token):
            return 403, "bad or missing form token"
        m = self.module
        if m is None or not getattr(m, "modes", None):
            return 409, "M-16 is off"
        if path == "/face/entry/delete":
            return (200, "entry deleted") if m.delete_entry(f.get("id", "")) else (404, "no such entry")
        if path == "/face/person/delete":
            try:
                r = m.delete_person(f.get("id", ""))
            except KeyError:
                return 404, "no such person"
            return 200, getattr(r, "message", "person deleted")
        if path == "/face/disable":
            if f.get("confirm") != "WIPE":
                return 400, "type WIPE to confirm"
            r = m.disable()
            self.module = None
            return (200 if r.verified else 500), r.message
        return 404, "unknown action"
