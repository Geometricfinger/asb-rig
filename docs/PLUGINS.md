# Plugins: removing and replacing models (voice recognition, face match, eye, fusion)

O Iris is modular. Every model it uses sits in a **slot** with a fixed, versioned interface.
Which model fills a slot is **one config setting**. No core file needs editing, and no model
weights are bundled in this repo.

| Slot (port v1.0) | Interface | Used by | When empty |
|---|---|---|---|
| `speech_recognizer` | `oiris.slots.SpeechRecognizer.transcribe(audio, sample_rate, t0) -> Transcript` | M-02 spoken-digit challenge (`DigitChallenge.verify_audio`) | result `unavailable`, zero confidence, no liveness indicator |
| `voice_antispoof` | `VoiceAntiSpoof.spoof_score(audio, sr) -> [0,1]` | `S_voice` | no score |
| `speaker_embed` | `SpeakerEmbed.embed(audio, sr) -> vector[dim]` | voice enrolment similarity | no similarity |
| `eye_model` | `EyeModel.predict(features) -> [0,1]` | `S_eye` learned variant | built-in rule-based eye features only |
| `fusion_weights` | `FusionWeights.load() -> FusionModel` | fusion layer | documented hand-set prior (ADR-0004) |
| `face_match` | `oiris.modules.face_match.port.FaceMatchPort` | M-16 (opt-in, off by default) | M-16 cannot start; nothing else changes |

Every call into a slot is isolated (`oiris.slots.SlotManager`): exceptions, wrong types,
NaN or out-of-range outputs empty that one slot and are logged. The rest keeps running
(tested in `tests/test_plugin_slots.py`).

## Plug one in
1. Write a class that implements the interface, and a `register(r)` function:
   ```python
   from oiris.registry import PluginMeta
   META = PluginMeta(license="Apache-2.0", data_tier="own_recorded", commercial_ok=True,
                     source="https://example.com/my-model", weights_license="Apache-2.0")
   def register(r):
       r.register("speech_recognizer", "my_asr", MyAsr, port_version="1.0", meta=META)
   ```
2. Make it findable, either way:
   - an installed package with an entry point: `[project.entry-points."oiris.plugins"] my_asr = "my_pkg:register"`
   - or a path in config: `"plugins": {"paths": ["/home/me/my_asr.py:register"]}` (or `"my_pkg.mod:register"`)
3. Select it: `"plugins": {"slots": {"speech_recognizer": "my_asr"}, "options": {"my_asr": {"model_dir": "..."}}}`.
   `options.<name>` is passed to your class as keyword arguments.
4. Check: `oiris plugins --config config.json` lists every slot, what fills it, and licence warnings.

## Remove one
Delete its line from `plugins.slots` (or uninstall the package). The slot is empty; the
feature degrades as in the table above. Nothing else needs changing.

## Replace voice recognition
Point `plugins.slots.speech_recognizer` at another plugin. Shipped examples (not installed by default):
- `examples/plugins/oiris_dtmf_digits`: Apache-2.0, no model; recognises keypad tones. It is not speech
  recognition. It's a working template that proves the contract with real audio.
- `examples/plugins/oiris_vosk_wrapper`: wraps a Vosk-style local engine. Ships no engine and no model.
  You `pip install vosk` and download a model yourself.
Same for `voice_antispoof` and `speaker_embed`.

## Replace face match (e.g. SFace)
Implement `FaceMatchPort`, register it on port `face_match` with `PluginMeta`, and set
`plugins.slots.face_match` (this overrides `face_match.adapter`). Backends compute only; they
never store, log or export. All M-16 guardrails (opt-in, consent, deletion, export block) stay in core
and apply to every backend.

## Licences: who is responsible
- **In this repo:** only permissive code (MIT/BSD/Apache-2.0/ISC/PSF/MPL-2.0). No weights. No
  non-commercial or unclear-licence code, models or training data, ever. Bundled plugins
  are checked against the allow-list and refused otherwise.
- **External plugins** must declare `PluginMeta`: `license`, `weights_license`, `data_tier`
  (`own_recorded`, `synthetic`, `public_permissive`, `public_noncommercial`, `restricted_licensed`,
  `unknown`, `none`) and `commercial_ok`. They load with their declared licence (custom,
  proprietary or non-commercial). If the licence is outside the allow-list, the data tier is unknown, or
  `commercial_ok=False`, a **startup warning** is logged and shown by `oiris plugins`
  (`NOT FOR COMMERCIAL USE` when applicable). Declaring `commercial_ok=True` for NC terms is refused.
- Whoever installs a plugin is responsible for following its licence. If you sell a product
  built on O Iris, use only plugins whose code, weights **and training data** allow it.
