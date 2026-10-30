"""Plugin registry (ports & adapters). Core never imports concrete drivers/models;
it resolves them by (port, name) here. Third-party plugins register through the
`oiris.plugins` entry-point group: each entry point is a callable `register(registry)`."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

PORT_VERSIONS = {"sensor": "1.0", "score": "1.0", "model": "1.0", "tts": "1.0", "store": "1.0", "face_match": "1.0",
                 # replaceable model slots (ADR-0055, docs/PLUGINS.md); interfaces in oiris/slots.py
                 "speech_recognizer": "1.0", "voice_antispoof": "1.0", "speaker_embed": "1.0",
                 "eye_model": "1.0", "fusion_weights": "1.0"}
SLOT_PORTS = {"speech_recognizer", "voice_antispoof", "speaker_embed", "eye_model", "fusion_weights"}
DATA_TIERS = {"own_recorded", "synthetic", "restricted_licensed", "public_permissive", "public_noncommercial",
              "unknown", "none"}
ALLOWED_LICENSES = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0", "MPL-2.0"}


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class PluginMeta:
    """Licence facts an EXTERNAL plugin declares about itself (code, weights, training data).
    Bundled plugins (no meta) must be on ALLOWED_LICENSES. External plugins load with their
    declared licence (custom, proprietary, non-commercial...); anything outside the allow-list
    or with commercial_ok=False is recorded in Registry.warnings and logged at startup."""
    license: str
    data_tier: str
    commercial_ok: bool
    source: str = ""           # where the user fetched it / its licence text
    weights_license: str = ""  # if different from the code licence

    def check(self) -> None:
        if not self.license or self.data_tier not in DATA_TIERS:
            raise RegistryError(f"bad plugin metadata {self!r}")
        nc = any(t in (self.license + " " + self.weights_license).upper() for t in ("-NC", "NONCOMMERCIAL", "NON-COMMERCIAL"))
        if self.commercial_ok and (nc or self.data_tier == "public_noncommercial"):
            raise RegistryError(f"commercial_ok=True contradicts {self.license}/{self.weights_license}/{self.data_tier}")


@dataclass(frozen=True)
class Plugin:
    port: str
    name: str
    factory: Callable[..., Any]
    port_version: str
    license: str
    module_flag: str | None = None   # feature flag that gates it (e.g. "M-01")
    meta: PluginMeta | None = None


class Registry:
    def __init__(self) -> None:
        self._p: dict[tuple[str, str], Plugin] = {}
        self.warnings: list[str] = []

    def register(self, port: str, name: str, factory: Callable[..., Any], *, port_version: str,
                 license: str = "Apache-2.0", module_flag: str | None = None,
                 meta: PluginMeta | None = None) -> None:
        if port not in PORT_VERSIONS:
            raise RegistryError(f"unknown port {port}")
        if port_version.split(".")[0] != PORT_VERSIONS[port].split(".")[0]:
            raise RegistryError(f"{name}: port {port} v{port_version} incompatible with v{PORT_VERSIONS[port]}")
        if port in SLOT_PORTS and meta is None:
            raise RegistryError(f"{name}: model-slot plugins must declare PluginMeta (license, data_tier, commercial_ok)")
        if meta is not None:
            meta.check()
            license = meta.license
        if meta is not None:
            if not meta.commercial_ok or license not in ALLOWED_LICENSES or meta.data_tier == "unknown":
                msg = (f"WARNING: external plugin {port}:{name} licence={meta.license}"
                       f"{'/' + meta.weights_license if meta.weights_license else ''} data={meta.data_tier} "
                       f"commercial_ok={meta.commercial_ok} source={meta.source or '?'}. "
                       "Its licence is the installer's responsibility; it is not part of O Iris.")
                if not meta.commercial_ok:
                    msg += " NOT FOR COMMERCIAL USE."
                log.warning(msg)
                self.warnings.append(msg)
        elif license not in ALLOWED_LICENSES:
            raise RegistryError(f"{name}: license {license!r} not allowed (see docs/LICENSE_POLICY)")
        self._p[(port, name)] = Plugin(port, name, factory, port_version, license, module_flag, meta)

    def unregister(self, port: str, name: str) -> None:
        self._p.pop((port, name), None)

    def get(self, port: str, name: str) -> Plugin:
        try:
            return self._p[(port, name)]
        except KeyError:
            raise RegistryError(f"no plugin {port}:{name}") from None

    def create(self, port: str, name: str, *a: Any, **kw: Any) -> Any:
        return self.get(port, name).factory(*a, **kw)

    def names(self, port: str) -> list[str]:
        return sorted(n for (p, n) in self._p if p == port)

    def load_entry_points(self, group: str = "oiris.plugins") -> list[str]:
        loaded, eps = [], metadata.entry_points().select(group=group)
        for ep in eps:
            try:
                ep.load()(self)
                loaded.append(ep.name)
            except Exception as e:  # a broken plugin must not stop startup
                log.error("plugin %s failed to load: %s", ep.name, e)
                self.warnings.append(f"plugin {ep.name} failed to load: {e}")
        return loaded


    def load_paths(self, specs: list[str]) -> list[str]:
        """Config-listed plugins: "pkg.module:register" or "/path/to/file.py:register"."""
        import importlib, importlib.util
        loaded = []
        for spec in specs:
            try:
                target, _, fn = spec.rpartition(":")
                if not target:
                    raise RegistryError(f"plugin spec {spec!r} must be 'module:function'")
                if target.endswith(".py"):
                    sp = importlib.util.spec_from_file_location("oiris_userplugin_" + Path(target).stem, target)
                    if sp is None or sp.loader is None:
                        raise RegistryError(f"cannot load {target}")
                    mod = importlib.util.module_from_spec(sp)
                    sp.loader.exec_module(mod)
                else:
                    mod = importlib.import_module(target)
                getattr(mod, fn)(self)
                loaded.append(spec)
            except Exception as e:  # noqa: BLE001 - a broken plugin must not stop startup
                log.error("plugin %s failed to load: %s", spec, e)
                self.warnings.append(f"plugin {spec} failed to load: {e}")
        return loaded


def default_registry(plugins: dict | None = None) -> Registry:
    """`plugins` is Config.plugins: {"paths": [...], "entry_points": bool}."""
    from .adapters import builtin
    from .scores import builtin as score_builtin
    plugins = plugins or {}
    r = Registry()
    from .modules import face_match_gate
    builtin.register(r)
    score_builtin.register(r)
    face_match_gate.register(r)
    if plugins.get("entry_points", True):
        r.load_entry_points()
    r.load_paths(list(plugins.get("paths", [])))
    return r
