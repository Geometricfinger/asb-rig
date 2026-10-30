# Extending ASB without touching core

## Add a sensor
1. Subclass `oiris.adapters.base.AdapterBase`; set `id`, `bus`, `caps` (capabilities it produces), `units`, `license`.
2. Import vendor libraries **inside `open()`** and raise `DriverUnavailable` if missing, so the package imports anywhere.
3. `read(timeout_s)` returns `self._sample(data)` where `data` is the dict shape documented on the score module that consumes your capability (e.g. `{"frame_c": 2D °C}` for `thermal_frame`). Return `None` when nothing is ready.
4. Register it — in your own package:
   ```python
   # my_pkg/oiris_plugin.py
   def register(r):
       r.register("sensor", "my_thermal", MyThermal, port_version="1.0", license="MIT")
   ```
   ```toml
   [project.entry-points."oiris.plugins"]
   my_thermal = "my_pkg.oiris_plugin:register"
   ```
5. Run the contract suite: add your class to a parametrised list in your plugin's tests or locally to `tests/test_contracts.py`.

You do not need to handle crashes, hangs or restarts: the bus does that.

## Add a score
Implement `name` (`S_*`), `inputs` (capabilities), `module_flag` (spec module or `None`) and `update(window) -> Score`. Map it to a family in `fusion/stack.SCORE_FAMILY` (that is the one core edit; a PR must justify the family). Exceptions/NaN are contained by `safe_update`.

## Replace or remove a model slot
See [PLUGINS.md](PLUGINS.md): speech recogniser, voice anti-spoof, speaker embedding, eye model, fusion weights and face match are all selected by `plugins.slots` in config.

## Add a model
Ship a directory with `manifest.json` (C9: name, version, license, file, sha256, hypothesis, output_range `[0,1]`, data_tier) and the weights file. Load with `oiris.models.load_into(slot, path, loader)`. A bad hash, license or output range leaves the slot on its last-good model or disabled.

## Add a face backend (M-16)
Implement `FaceMatchPort` (`oiris/modules/face_match/port.py`: `detect`, `embed`, `compare`, `open`/`close`/`health`, plus `license`, `model_id`, `model_version`, `test_only`) and register it on port `face_match` v1.0 from an `oiris.plugins` entry point with `module_flag="M-16"`. Backends only compute: no storage, logging or export methods (a contract test checks). Weights and their training-data terms must be permissive and recorded in THIRD_PARTY.md; never commit weights.

## Add a TTS engine
Implement `speak`, `stop` and `offline = True`. Network voices are rejected. GPL engines are not accepted.

## Add a UI piece
UI reads C3 events and C4 logs only. Place it in a zone from the C6 map (`docs/spec/ASB-Module-Map-v1.1.pdf`: glasses G*, phone P1–P5, dashboard D1–D6). Show level by **shape + word**, colour only as backup; every string passes `Vocabulary.check()` (Kotlin) / `check_text()` (Python).

## Add a database column / table
Append a new `(version, sql)` to `oiris/store/migrations.py`. Never edit a shipped migration.

## Disable a module
Set `"flags": {"M-07": false}` in the config JSON. M-04 (security) and M-11 (bus) cannot be disabled. M-16 is off by default; turn it on only with `oiris face-match enable` (typed opt-in) and off with `oiris face-match disable` (verified wipe).
