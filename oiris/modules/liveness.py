"""M-02 liveness stacking (HYPOTHESIS module; ships disabled until E-15/E-16 pass).
Reports per-family liveness indicators as observed / not observed; A11 needs >=2
families agreeing that expected indicators are absent. Never a verdict about a person."""
from __future__ import annotations

import hmac as _hmac
import secrets as _secrets
import time as _time
from dataclasses import dataclass as _dc

from ..schema import BENIGN_CAUSES, Health, Score

INDICATOR_OF = {"S_live": ("vital", "pulse"), "S_radar": ("vital", "breathing"), "S_eye": ("eye", "blink"),
                "S_voice": ("voice", "voice liveness"), "S_thermal": ("thermal", "skin-band heat")}


def indicators(scores: list[Score], absent_at: float = 0.5) -> dict:
    out, fams_absent = [], set()
    for s in scores:
        if s.module not in INDICATOR_OF or s.health == Health.FAILED or s.confidence <= 0.1:
            continue
        fam, name = INDICATOR_OF[s.module]
        state = "not observed" if s.value >= absent_at else "observed"
        if state == "not observed":
            fams_absent.add(fam)
        out.append({"indicator": name, "family": fam, "state": state, "score": round(s.value, 4)})
    return {"liveness_indicators": out, "families_absent": sorted(fams_absent),
            "a11": len(fams_absent) >= 2, "benign_causes": BENIGN_CAUSES["A11"],
            "limit": "A silicone mask on a live wearer keeps real eyes, pulse and voice; this stack does not catch it."}


# ---- Spoken-digit challenge (M-02 voice family) ---------------------------------------------
# A fresh random digit string is prompted; the wearer-side speech recogniser (an offline ASR
# behind the `transcript` input, never a cloud call) returns what was heard plus the time the
# speech started. A replayed recording cannot know the digits; a live speaker answers within a
# human latency window. Each nonce is single-use. This is an indicator, never a verdict.

_WORDS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "for": "4",
          "five": "5", "six": "6", "seven": "7", "eight": "8", "ate": "8", "nine": "9"}


def normalise_digits(transcript: str) -> str:
    """'four 7 nine' -> '479'. Non-digit words are ignored."""
    out = []
    for tok in transcript.lower().replace(",", " ").replace("-", " ").split():
        if tok.isdigit():
            out.append(tok)
        elif tok in _WORDS:
            out.append(_WORDS[tok])
    return "".join(out)


@_dc(frozen=True)
class DigitPrompt:
    nonce: str
    digits: str
    issued_at: float
    expires_at: float

    @property
    def text(self) -> str:
        return "Please say: " + " ".join(self.digits)


@_dc(frozen=True)
class DigitResult:
    state: str           # "observed" | "not observed" | "rejected"
    reason: str
    latency_s: float | None = None

    def as_score_value(self) -> float:
        """Liveness-indicator convention: higher = expected indicator less observed."""
        return 0.0 if self.state == "observed" else 1.0


class DigitChallenge:
    """Issues and verifies spoken-digit challenges. `min_latency_s` rejects answers that start
    before a human could have heard the prompt (pre-recorded audio started early);
    `max_latency_s` and `ttl_s` bound the window. Nonces are single-use (replay rejected)."""

    def __init__(self, n_digits: int = 4, ttl_s: float = 10.0, min_latency_s: float = 0.25,
                 max_latency_s: float = 4.0, clock=_time.monotonic, rng=None):
        if not 3 <= n_digits <= 8:
            raise ValueError("n_digits must be 3..8")
        self.n_digits, self.ttl_s = n_digits, ttl_s
        self.min_latency_s, self.max_latency_s = min_latency_s, max_latency_s
        self.clock = clock
        self._rng = rng or _secrets.SystemRandom()
        self._open: dict[str, DigitPrompt] = {}
        self._used: set[str] = set()

    def issue(self) -> DigitPrompt:
        digits = "".join(str(self._rng.randrange(10)) for _ in range(self.n_digits))
        now = self.clock()
        p = DigitPrompt(_secrets.token_hex(16), digits, now, now + self.ttl_s)
        self._open[p.nonce] = p
        return p

    def verify(self, nonce: str, transcript: str, speech_start: float) -> DigitResult:
        if nonce in self._used:
            return DigitResult("rejected", "replay: challenge already answered")
        p = self._open.pop(nonce, None)
        if p is None:
            return DigitResult("rejected", "unknown challenge")
        self._used.add(nonce)
        now = self.clock()
        if now > p.expires_at:
            return DigitResult("not observed", "timeout")
        lat = speech_start - p.issued_at
        if lat < self.min_latency_s:
            return DigitResult("not observed", "answer began before the prompt could be heard", lat)
        if lat > self.max_latency_s:
            return DigitResult("not observed", "answer too slow", lat)
        heard = normalise_digits(transcript).encode()
        if not _hmac.compare_digest(heard, p.digits.encode()):
            return DigitResult("not observed", "digits did not match", lat)
        return DigitResult("observed", "digits matched in time", lat)

    def expire(self) -> int:
        now = self.clock()
        dead = [n for n, p in self._open.items() if now > p.expires_at]
        for n in dead:
            self._open.pop(n); self._used.add(n)
        return len(dead)


def digit_score(res: DigitResult, confidence: float = 0.6) -> Score:
    """Feed a challenge result into the S_voice indicator family (stack above)."""
    return Score(module="S_voice", value=res.as_score_value(), confidence=confidence, health=Health.OK,
                 evidence={"challenge": res.state, "reason": res.reason})
