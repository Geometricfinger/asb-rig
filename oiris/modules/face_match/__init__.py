"""M-16 face matching (optional, off by default; ADR-0049/0050, docs/FACE_MATCHING_MODULE_SPEC.md).

Nothing in core imports this package. It is loaded only by `load_if_enabled()` in
`oiris.modules.face_match_loader` once the `M-16` flag is on and the typed opt-in is
recorded. Adapters (backends) only compute; the module core here owns storage, modes,
retention and wipe. Never alerts, blocks or follows anyone; results are review-log only."""
PORT = "face_match"
PORT_VERSION = "1.0"
