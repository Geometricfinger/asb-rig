"""Registers built-in adapters with the registry. Core resolves adapters by name only."""
from __future__ import annotations

from . import drivers, sim
from .base import ReplayAdapter


def register(r) -> None:
    for cls in drivers.REAL:
        r.register("sensor", cls.id, cls, port_version="1.0")
    r.register("sensor", "replay", ReplayAdapter, port_version="1.0")
    r.register("sensor", "sim", sim.make, port_version="1.0")
