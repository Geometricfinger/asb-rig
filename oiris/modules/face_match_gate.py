"""The only door to M-16. Importing this file does NOT import `oiris.modules.face_match`;
the package is imported only by `load()` when the M-16 flag is on and the opt-in is
recorded. Backends are registered lazily by import path."""
from __future__ import annotations
import importlib
from typing import Any

BACKENDS = {  # name -> (module path, class, licence of code + weights)
    "opencv_zoo": ("oiris.modules.face_match.backends.opencv_zoo", "OpenCvZooBackend", "Apache-2.0"),
}


def _lazy(path: str, cls: str):
    def make(*a: Any, **kw: Any) -> Any:
        return getattr(importlib.import_module(path), cls)(*a, **kw)
    return make


def register(r) -> None:
    for name, (path, cls, lic) in BACKENDS.items():
        r.register("face_match", name, _lazy(path, cls), port_version="1.0", license=lic, module_flag="M-16")


def load(cfg, db, keys, registry, chain=None, consents=None, backend: Any = None):
    """Build the M-16 module, or return None while it is off. Refuses without the opt-in."""
    if not cfg.enabled("M-16"):
        return None
    core = importlib.import_module("oiris.modules.face_match.core")
    fcfg = core.FaceMatchConfig.from_dict(cfg.face_match)
    if backend is None:
        # one config setting swaps the backend: plugins.slots.face_match (else face_match.adapter)
        name = (getattr(cfg, "plugins", {}) or {}).get("slots", {}).get("face_match") or fcfg.adapter
        backend = registry.create("face_match", name)
    return core.FaceMatchModule(db, keys, cfg.data_dir, backend, chain=chain, cfg=fcfg, consents=consents,
                                timeout_s=cfg.adapter_timeout_s, breaker_threshold=cfg.breaker_threshold,
                                breaker_cooldown_s=cfg.breaker_cooldown_s)
