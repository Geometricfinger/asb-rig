"""Plugin registry (ports & adapters). Core never imports concrete drivers/models;
it resolves them by (port, name) here. Third-party plugins register through the
`asb.plugins` entry-point group: each entry point is a callable `register(registry)`."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from importlib import metadata
from typing import Any, Callable

log = logging.getLogger(__name__)

PORT_VERSIONS = {"sensor": "1.0", "score": "1.0", "model": "1.0", "tts": "1.0", "store": "1.0"}
ALLOWED_LICENSES = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0", "MPL-2.0"}


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class Plugin:
    port: str
    name: str
    factory: Callable[..., Any]
    port_version: str
    license: str
    module_flag: str | None = None   # feature flag that gates it (e.g. "M-01")


class Registry:
    def __init__(self) -> None:
        self._p: dict[tuple[str, str], Plugin] = {}

    def register(self, port: str, name: str, factory: Callable[..., Any], *, port_version: str,
                 license: str = "Apache-2.0", module_flag: str | None = None) -> None:
        if port not in PORT_VERSIONS:
            raise RegistryError(f"unknown port {port}")
        if port_version.split(".")[0] != PORT_VERSIONS[port].split(".")[0]:
            raise RegistryError(f"{name}: port {port} v{port_version} incompatible with v{PORT_VERSIONS[port]}")
        if license not in ALLOWED_LICENSES:
            raise RegistryError(f"{name}: license {license!r} not allowed (see docs/LICENSE_POLICY)")
        self._p[(port, name)] = Plugin(port, name, factory, port_version, license, module_flag)

    def get(self, port: str, name: str) -> Plugin:
        try:
            return self._p[(port, name)]
        except KeyError:
            raise RegistryError(f"no plugin {port}:{name}") from None

    def create(self, port: str, name: str, *a: Any, **kw: Any) -> Any:
        return self.get(port, name).factory(*a, **kw)

    def names(self, port: str) -> list[str]:
        return sorted(n for (p, n) in self._p if p == port)

    def load_entry_points(self, group: str = "asb.plugins") -> list[str]:
        loaded, eps = [], metadata.entry_points().select(group=group)
        for ep in eps:
            try:
                ep.load()(self)
                loaded.append(ep.name)
            except Exception as e:  # a broken plugin must not stop startup
                log.error("plugin %s failed to load: %s", ep.name, e)
        return loaded


def default_registry() -> Registry:
    from .adapters import builtin
    from .scores import builtin as score_builtin
    r = Registry()
    builtin.register(r)
    score_builtin.register(r)
    r.load_entry_points()
    return r
