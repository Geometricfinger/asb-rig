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
- Use it on **your own premises**, with **adults who gave written consent**. No strangers, no children, no public use without legal review.
- **Biometric laws** may apply to eye and voice features, including Illinois BIPA (written release, retention schedule, private right of action), Texas CUBI, Washington RCW 19.375, California CCPA/CPRA, and the EU/UK GDPR (biometric data is special-category). Where unsure, follow the strictest.
- **Recording and wiretap laws** vary; the mic is push-to-talk and stores no audio for this reason.
- **IR eye safety**: follow the IEC 62471-based worksheet in the build spec (≤100 mA, duty cap, distance minimums). The code caps LED duty at 25%.
- **Never act on an alert against a person.** A signature is an observation with benign causes, shown alongside it.

## Out of scope by design
Tracking people or phones, de-anonymising rotating Bluetooth addresses, face recognition, covert recording, and any offensive radio use.
