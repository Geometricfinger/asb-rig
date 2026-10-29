# Ethics and legal-use notice

*General information, not legal advice.*

ASB is a research bench for **anomaly signatures**. It is not a lie detector, an identity system, or a way to decide what someone "is".

## Rules built into the code (cannot be switched off)
- **No person labels.** The vocabulary guard blocks words like "robot", "android", "fake", "not human" in any output, and output schemas have no class field.
- **Consent.** Any session with a human subject needs a recorded consent ID with the right scope (session, biometric release, voice/eye enrollment, golden dataset). Withdrawal deletes their clips.
- **Privacy.** No audio is ever written to disk. No full camera frames of people (64×64 crops only). Radio identifiers are stored only as per-site HMACs. GPS is rounded to 0.01° on export.
- **Retention.** 30 days by default; a nightly purge deletes expired rows.
- **Passive radio only.** No transmitting, jamming, deauthentication, packet injection or monitor mode. The software refuses to run if a wireless interface is in monitor mode.
- **Fixed phrases only.** Voice and glasses output come from a whitelist.

## Your responsibilities
- Use it on **your own premises**, with **adults who gave written consent**. No strangers, no children, no public use without legal review, except M-16 research mode on the user's own opt-in (ADR-0050).
- **Biometric laws** may apply to eye and voice features, including Illinois BIPA (written release, retention schedule, private right of action), Texas CUBI, Washington RCW 19.375, California CCPA/CPRA, and the EU/UK GDPR (biometric data is special-category). Where unsure, follow the strictest.
- **Recording and wiretap laws** vary; the mic is push-to-talk and stores no audio for this reason.
- **IR eye safety**: follow the IEC 62471-based worksheet in the build spec (≤100 mA, duty cap, distance minimums). The code caps LED duty at 25%.
- **Never act on an alert against a person.** A signature is an observation with benign causes, shown alongside it.

## Out of scope by design
Tracking people or phones, de-anonymising rotating Bluetooth addresses, covert recording, and any offensive radio use.

## Optional face matching (M-16, opt-in)
Face recognition is in scope only as the optional add-on in [docs/FACE_MATCHING_MODULE_SPEC.md](docs/FACE_MATCHING_MODULE_SPEC.md) (ADR-0049, ADR-0050). Built in `oiris/modules/face_match/` (headless-tested, not yet run on real hardware). The rules:
- **Off by default.** Turned on only after a plain-language warning: what it stores, and that the camera sees people who never agreed.
- **Personal mode:** matches only people you enrolled. Their templates stay on the device, encrypted. Recording their consent is recommended (required where the law demands it).
- **Research mode:** anonymous, unlinked counts of unrecognized faces only — no templates, no way to tell if the same stranger was seen twice. Unlocks on your own explicit opt-in; no legal review or external gate.
- **Your call, your risk.** Every feature with questionable legality is an on/off switch. You make the determination, the risk is your own, and the feature is an option you may use as you choose. Biometric and recording laws vary by place; compliance is your responsibility.
- **No acting on detections.** No alerts, no blocking, no following. It logs; you review and can delete any entry.
- **No cloud upload by default.** Templates are never exported.
- **Off means gone.** Disabling or removing it wipes all face templates, verified.

All rules above still apply to it, including no person labels.
