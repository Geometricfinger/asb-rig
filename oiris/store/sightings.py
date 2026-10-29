"""M-05 sighting log (encrypted, hash-chained, auto-GPS, export rounding) and
M-14 sweep history timeline."""
from __future__ import annotations
import json, time, uuid
from dataclasses import dataclass

from ..guard.privacy import round_gps
from ..security.hashchain import HashChain
from .db import DB

VERDICTS = {"confirmed", "benign", "unresolved"}
OSM_ATTRIBUTION = "© OpenStreetMap contributors"


@dataclass
class GpsFix:
    lat: float | None
    lon: float | None
    quality: str = "no_fix"     # "no_fix" | "2d" | "3d"


class SightingLog:
    def __init__(self, db: DB, chain: HashChain):
        self.db, self.chain = db, chain

    def add(self, event: dict, gps: GpsFix, crop_path: str | None = None, verdict: str = "unresolved") -> str:
        if verdict not in VERDICTS:
            raise ValueError("bad verdict")
        sid = uuid.uuid4().hex
        if gps.quality == "no_fix":
            lat = lon = None   # never guessed
        else:
            lat, lon = gps.lat, gps.lon
        body = {"event": event, "lat": lat, "lon": lon, "fix_quality": gps.quality, "crop_path": crop_path}
        rec = {"sighting_id": sid, "t_wall": time.time(), "codes": [event.get("signature")], "verdict": verdict}
        prev = self.chain.entries[-1][1] if self.chain.entries else b"\x00" * 32
        h = self.chain.append({**rec, "body_digest": json.dumps(body, sort_keys=True)})
        self.db.execute("INSERT INTO sighting VALUES(?,?,?,?,?,?,?,?,0)",
                        (sid, rec["t_wall"], json.dumps(rec["codes"]), self.db.seal_json(body, sid.encode()),
                         verdict, len(self.chain.entries), prev, h))
        return sid

    def set_verdict(self, sid: str, verdict: str) -> None:
        if verdict not in VERDICTS:
            raise ValueError("bad verdict")
        self.db.execute("UPDATE sighting SET verdict=? WHERE sighting_id=?", (verdict, sid))
        self.chain.append({"sighting_id": sid, "verdict_change": verdict, "t_wall": time.time()})

    def get(self, sid: str) -> dict:
        r = self.db.execute("SELECT sighting_id,t_wall,codes,body,verdict FROM sighting WHERE sighting_id=?", (sid,)).fetchone()
        if not r:
            raise KeyError(sid)
        return {"sighting_id": r[0], "t_wall": r[1], "codes": json.loads(r[2]), "verdict": r[4],
                **self.db.open_json(r[3], r[0].encode())}

    def all(self) -> list[dict]:
        return [self.get(r[0]) for r in self.db.execute("SELECT sighting_id FROM sighting ORDER BY t_wall")]

    def export(self, decimals: int = 2) -> list[dict]:
        out = []
        for s in self.all():
            s = dict(s)
            s["lat"], s["lon"] = round_gps(s["lat"], s["lon"], decimals)
            s.pop("crop_path", None)
            out.append(s)
        return out

    def map_pins(self) -> dict:
        """Pins for the offline map layer (our own layer; never merged into OSM data)."""
        pins = [{"id": s["sighting_id"], "lat": s["lat"], "lon": s["lon"], "codes": s["codes"], "verdict": s["verdict"]}
                for s in self.all() if s["lat"] is not None]
        return {"attribution": OSM_ATTRIBUTION, "pins": pins}


class SweepTimeline:
    def __init__(self, db: DB):
        self.db = db

    def start(self, site_code: str) -> str:
        sid = uuid.uuid4().hex
        self.db.execute("INSERT INTO sweep(sweep_id,site_code,t_wall,body,outcome) VALUES(?,?,?,?,?)",
                        (sid, site_code, time.time(), self.db.seal_json({"counts": {}}, sid.encode()), "open"))
        return sid

    def finish(self, sweep_id: str, counts: dict, new_since_last: list, outcome: str = "done") -> None:
        body = {"counts": counts, "new_since_last": new_since_last}
        self.db.execute("UPDATE sweep SET t_end=?, body=?, outcome=? WHERE sweep_id=?",
                        (time.time(), self.db.seal_json(body, sweep_id.encode()), outcome, sweep_id))

    def history(self, site_code: str | None = None) -> list[dict]:
        q = "SELECT sweep_id,site_code,t_wall,t_end,body,outcome FROM sweep"
        args: tuple = ()
        if site_code:
            q += " WHERE site_code=?"; args = (site_code,)
        rows = self.db.execute(q + " ORDER BY t_wall", args).fetchall()
        return [{"sweep_id": r[0], "site_code": r[1], "start": r[2], "end": r[3], "outcome": r[5],
                 **self.db.open_json(r[4], r[0].encode())} for r in rows]
