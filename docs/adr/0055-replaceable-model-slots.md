# ADR-0055: Replaceable model slots and external-plugin licensing (Oct 29 2026)

Status: Accepted

## Context
O Iris must let anyone remove the voice recognition or face-match model and plug in a different one,
including their own custom or commercial model, without editing core. An audit at `fb306df`
found that sensor/score/face_match/tts ports and `oiris.plugins` entry points existed. But there was
no port for speech recognition, voice anti-spoof, speaker embedding, eye models or fusion weights. The
digit challenge took a raw transcript, and the registry refused any licence outside the allow-list, so a
user's proprietary or non-commercial plugin could not load at all.

## Decision
- New ports v1.0 `speech_recognizer`, `voice_antispoof`, `speaker_embed`, `eye_model`, `fusion_weights`.
  Their Protocols are in `oiris/slots.py`. `SlotManager` resolves each slot from one config setting
  (`plugins.slots`) and isolates every call.
- Plugins come from `oiris.plugins` entry points or `plugins.paths` (`module:function` / `file.py:function`).
- Model-slot plugins must declare `PluginMeta` (license, weights_license, data_tier, commercial_ok).
  Bundled registrations (no meta) keep the strict allow-list. External plugins load under their
  declared licence, with a startup warning when it is non-permissive, unknown or `commercial_ok=False`.
  False `commercial_ok=True` claims for NC terms are refused.
- `face_match` backend selectable by `plugins.slots.face_match`.
- Reference plugins in `examples/plugins/` (DTMF digits, Vosk wrapper), with no weights. A test fails if model
  weight files are ever committed.

## Consequences
The repo itself stays permissive. Users can run non-commercial models for their own use, and they are told
clearly at startup. Guardrails (consent, privacy, M-16 opt-in, no identity output) stay in core and apply to any plugin.
