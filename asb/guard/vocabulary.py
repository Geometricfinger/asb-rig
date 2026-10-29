"""Vocabulary guard: no live string may label a person as a machine or as human.
ASB reports anomaly signatures only."""
from __future__ import annotations
import re
from typing import Any

BANNED = [r"robots?", r"androids?", r"fake", r"not\s+human", r"non-?human", r"impostors?",
          r"synthetic\s+person", r"not\s+alive", r"dead", r"replicas?", r"humanoids?",
          r"cyborgs?", r"is\s+human", r"real\s+person", r"machine\s+person", r"bots?"]
_RX = re.compile(r"\b(" + "|".join(BANNED) + r")\b", re.IGNORECASE)
FORBIDDEN_FIELDS = {"class", "label", "is_human", "is_robot", "identity", "species", "person_type", "verdict_class"}


class VocabularyViolation(ValueError):
    pass


def violations(text: str) -> list[str]:
    return [m.group(0) for m in _RX.finditer(text or "")]


def check_text(text: str) -> str:
    v = violations(text)
    if v:
        raise VocabularyViolation(f"banned wording {v!r} in output")
    return text


def check_output(obj: Any, path: str = "$") -> Any:
    """Recursively check a dict/list payload: no forbidden field names, no banned words."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN_FIELDS:
                raise VocabularyViolation(f"forbidden class-like field {path}.{k}")
            check_output(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            check_output(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        check_text(obj)
    return obj
