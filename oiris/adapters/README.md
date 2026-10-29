# oiris.adapters — sensor port (C2, M-11)
**Purpose**: turn hardware, recordings or generators into `Sample`s. **Inputs**: device / file / seed. **Outputs**: `Sample{adapter_id, t_mono_ns, t_wall, seq, units, quality, data}`. **Depends on**: `oiris.schema`, `oiris.guard.radio` (radio drivers). **Variants**: `drivers.py` (real, lazy imports), `base.ReplayAdapter`, `sim.make()`.
**Extend**: see docs/EXTENDING.md "Add a sensor". The bus provides threading, timeouts, restarts and breakers; adapters stay simple.
