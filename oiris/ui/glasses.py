"""Glasses display renderer (G1-G6, Module Map 7.1), simulated as SVG on the C7 canvas.

Additive display: black is transparent, so everything is sparse light-on-dark at low default
brightness. G1 level strip, G2 alert line (<=6 words, vocabulary-guarded), G3 thermal window
(grayscale default, colour overlay toggle, never the alert colours), G4 health dots, G5 voice
tier, G6 lock / panic-armed state. The centre of view stays clear except the thermal window."""
from __future__ import annotations
import base64, html, io, zlib, struct
from dataclasses import dataclass, field

import numpy as np

from ..guard.vocabulary import check_text
from . import tokens as T


@dataclass
class GlassesState:
    level: str | None = None                 # low | medium | confirmed | None
    alert_text: str = ""
    new_sighting: bool = False
    thermal: np.ndarray | None = None         # degC frame
    thermal_colour: bool = False
    health: dict = field(default_factory=dict)   # sensor -> ok|degraded|down
    voice_tier: str = "low"
    locked: bool = False
    panic_armed: bool = False
    moving: bool = False


class LayoutError(ValueError):
    pass


def zones(tok: dict) -> dict:
    W, H = tok["glasses"]["canvas"]
    return {"G1": (0, 0, W, 28), "G2": (0, 32, W, 36), "G3": tuple(tok["glasses"]["thermal_window"]),
            "G4": (8, H - 28, 200, 20), "G5": (W - 160, H - 28, 152, 20), "G6": (8, 72, 160, 24)}


def _centre(tok: dict) -> tuple:
    W, H = tok["glasses"]["canvas"]
    f = tok["glasses"]["centre_clear_fraction"]
    return (W * (1 - f) / 2, H * (1 - f) / 2, W * f, H * f)


def _overlap(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def check_layout(tok: dict) -> None:
    z, c = zones(tok), _centre(tok)
    W, H = tok["glasses"]["canvas"]
    for k, r in z.items():
        if r[0] < 0 or r[1] < 0 or r[0] + r[2] > W or r[1] + r[3] > H:
            raise LayoutError(f"{k} outside canvas")
        if k != "G3" and _overlap(r, c):
            raise LayoutError(f"{k} intrudes on the clear centre")
    ks = list(z)
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            if _overlap(z[a], z[b]):
                raise LayoutError(f"{a} overlaps {b}")


def _png_gray(img: np.ndarray) -> bytes:
    h, w = img.shape[:2]
    ch = 3 if img.ndim == 3 else 1
    raw = b"".join(b"\x00" + img[y].astype(np.uint8).tobytes() for y in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2 if ch == 3 else 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def thermal_image(frame: np.ndarray, colour: bool) -> np.ndarray:
    f = np.asarray(frame, float)
    g = (255 * (f - f.min()) / (np.ptp(f) or 1)).astype(np.uint8)
    if not colour:
        return g
    # overlay ramp (black->purple->white); built from neither alert hue family
    r = np.clip(g * 1.0, 0, 255); gg = np.clip((g.astype(int) - 128) * 2, 0, 255); b = np.clip(255 - np.abs(g.astype(int) - 128) * 2, 0, 255)
    return np.stack([r, gg, b], axis=-1).astype(np.uint8)


def _shape(kind: str, x: float, y: float, s: float, col: str) -> str:
    if kind == "circle":
        return f'<circle cx="{x}" cy="{y}" r="{s / 2}" fill="{col}"/>'
    if kind == "triangle":
        return f'<polygon points="{x},{y - s / 2} {x + s / 2},{y + s / 2} {x - s / 2},{y + s / 2}" fill="{col}"/>'
    return f'<polygon points="{x},{y - s / 2} {x + s / 2},{y} {x},{y + s / 2} {x - s / 2},{y}" fill="{col}"/>'


def render(st: GlassesState, tok: dict | None = None) -> str:
    tok = tok or T.load()
    check_layout(tok)
    W, H = tok["glasses"]["canvas"]
    z, c, fs = zones(tok), tok["color"], tok["type"]["glasses_body"]
    br = tok["glasses"]["default_brightness"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="{tok["type"]["font_family"]}" font-size="{fs}" opacity="{br}">',
           f'<rect width="{W}" height="{H}" fill="{c["bg"]}"/>']
    if st.level:
        if st.level not in T.LEVELS:
            raise LayoutError("unknown level")
        lv = tok["alert_levels"][st.level]
        x, y, w, h = z["G1"]
        out.append(_shape(lv["shape"], 16, y + h / 2, 16, c["alert"][st.level]))
        out.append(f'<text id="G1" x="32" y="{y + h - 7}" fill="{c["alert"][st.level]}">{html.escape(lv["word"])}</text>')
    if st.alert_text and not st.moving:   # no pop-ups during movement; G1 strip still shows the level
        words = st.alert_text.split()
        if len(words) > tok["glasses"]["max_words_alert_line"]:
            raise LayoutError("alert line exceeds the word limit")
        check_text(st.alert_text)
        x, y, w, h = z["G2"]
        out.append(f'<text id="G2" x="8" y="{y + h - 10}" fill="{c["text"]}">{html.escape(st.alert_text)}</text>')
    if st.new_sighting:
        out.append(f'<text id="G2cue" x="{W - 150}" y="{z["G2"][1] + 26}" fill="{c["text_muted"]}">New sighting</text>')
    if st.thermal is not None:
        x, y, w, h = z["G3"]
        img = thermal_image(st.thermal, st.thermal_colour)
        b64 = base64.b64encode(_png_gray(img)).decode()
        out.append(f'<image id="G3" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="none" '
                   f'href="data:image/png;base64,{b64}" data-mode="{"colour" if st.thermal_colour else "grayscale"}"/>')
    x, y, w, h = z["G4"]
    for i, (name, hs) in enumerate(sorted(st.health.items())):
        col = {"ok": c["health_ok"], "degraded": c["health_degraded"]}.get(hs, c["health_down"])
        filled = "" if hs == "ok" else ' stroke-width="2"'
        out.append(f'<circle class="G4" cx="{x + 8 + i * 18}" cy="{y + h / 2}" r="5" fill="{col if hs == "ok" else "none"}" '
                   f'stroke="{col}"{filled}><title>{html.escape(name)}: {html.escape(hs)}</title></circle>')
    x, y, w, h = z["G5"]
    out.append(f'<text id="G5" x="{x}" y="{y + h - 4}" fill="{c["text_muted"]}">Voice: {html.escape(st.voice_tier)}</text>')
    x, y, w, h = z["G6"]
    g6 = ("Locked" if st.locked else "") + (" Panic armed" if st.panic_armed else "")
    if g6:
        out.append(f'<text id="G6" x="{x}" y="{y + h - 6}" fill="{c["text"]}">{g6.strip()}</text>')
    out.append("</svg>")
    return "".join(out)


def save(st: GlassesState, path: str) -> None:
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(render(st))


ENGINE_LEVEL = {"fyi": "low", "attention": "medium", "confirmed": "confirmed"}


def state_from_result(res: dict) -> GlassesState:
    """Map a C3 headless/engine result to the glasses state (signature IDs only; no identities)."""
    lvl = ENGINE_LEVEL.get(str(res.get("level") or ""), None)
    sigs = list(res.get("signatures") or [])
    text = ("Signatures " + " ".join(sigs[:4])) if sigs else ""
    health = {k: (v["health"] if isinstance(v, dict) else str(v)) for k, v in (res.get("health") or {}).items()}
    return GlassesState(level=lvl, alert_text=text, health=health)


# ---- M-16 enrollment mini-guide (FACE_MATCHING_MODULE_SPEC §7.3 step 3) ----------------------
# The glasses show only the next angle needed and a tick when a shot is accepted. No names, no
# face image, nothing in the clear centre, and never anything on a *match* (spec §6 "Never does").
GUIDE_ORDER = ("front", "left", "right", "up", "down")
GUIDE_WORDS = {"front": "Look straight ahead", "left": "Turn head left", "right": "Turn head right",
               "up": "Tilt head up", "down": "Tilt head down"}
GUIDE_ARROW = {"front": "", "left": "\u2190", "right": "\u2192", "up": "\u2191", "down": "\u2193"}


@dataclass
class EnrollGuide:
    needed: list[str]                 # angles still needed, in GUIDE_ORDER
    last_ok: bool | None = None        # result of the last submitted shot (None = no shot yet)
    last_reason: str = ""              # plain reason when the last shot was rejected
    complete: bool = False

    @property
    def next_angle(self) -> str | None:
        return self.needed[0] if self.needed else None


def guide_from_port(port, person_id: str, last=None) -> EnrollGuide:
    """Build the guide from an EnrollmentPort (local core or remote.py proxy) and the last
    ShotResult. Works with either Angle enums or plain strings."""
    have = {getattr(a, "value", a) for a in port.needed_angles(person_id)}
    needed = [a for a in GUIDE_ORDER if a in have]
    ok = None if last is None else bool(last.ok)
    reason = "" if last is None or last.ok else str(last.reason)
    return EnrollGuide(needed, ok, reason, complete=not needed)


def _short(reason: str, n: int) -> str:
    words = reason.replace(",", "").split()
    return " ".join(words[:n])


def render_enroll_guide(g: EnrollGuide, tok: dict | None = None) -> str:
    tok = tok or T.load()
    check_layout(tok)
    W, H = tok["glasses"]["canvas"]
    z, c, fs = zones(tok), tok["color"], tok["type"]["glasses_body"]
    br = tok["glasses"]["default_brightness"]
    maxw = tok["glasses"]["max_words_alert_line"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="{tok["type"]["font_family"]}" font-size="{fs}" opacity="{br}" data-mode="enroll-guide">',
           f'<rect width="{W}" height="{H}" fill="{c["bg"]}"/>']
    if g.complete:
        line = "Template complete"
    elif g.last_ok is False and g.last_reason:
        line = _short(g.last_reason, maxw)
    else:
        a = g.next_angle or "front"
        line = (GUIDE_ARROW[a] + " " + GUIDE_WORDS[a]).strip()
    if len(line.split()) > maxw:
        raise LayoutError("guide line exceeds the word limit")
    check_text(line)
    x, y, w, h = z["G2"]
    out.append(f'<text id="G2" x="8" y="{y + h - 10}" fill="{c["text"]}">{html.escape(line)}</text>')
    if g.last_ok:   # tick for the accepted shot, top-right of G2, outside the clear centre
        tx, ty = W - 40, y + 6
        out.append(f'<polyline id="tick" points="{tx},{ty + 12} {tx + 8},{ty + 20} {tx + 24},{ty + 2}" fill="none" '
                   f'stroke="{c["health_ok"]}" stroke-width="3"/>')
    x, y, w, h = z["G4"]       # five progress dots: filled = captured
    for i, a in enumerate(GUIDE_ORDER):
        done = a not in g.needed
        out.append(f'<circle class="guide" data-angle="{a}" cx="{x + 8 + i * 18}" cy="{y + h / 2}" r="5" '
                   f'fill="{c["text"] if done else "none"}" stroke="{c["text_muted"]}"/>')
    out.append("</svg>")
    return "".join(out)
