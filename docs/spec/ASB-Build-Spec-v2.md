<div class="cover" markdown="1">
<div class="kicker">Build specification v2 · Phase 0–1 bench prototype + operator app · public edition · October 28, 2026</div>

# Anomaly Signature Bench (ASB) v2
## Head-mounted multi-sensor rig and Android operator app: v1 audit, 15 new modules, settled defaults

<p class="sub">Supersedes <i>Glasses-Detection-Build-Spec-v1</i>. Specification only: nothing has been bought, built, sent, installed or published, and nothing touches other projects. Prices and facts were checked on <b>2026-10-28</b> (search listings unless noted). Unverified items are tagged <b>[UNVERIFIED]</b>; autonomous choices are tagged <b>[DEFAULT]</b> and listed in Section 15. Per the owner's instruction, every decision is settled as a recorded default; only a purchase approval and a few facts about the owner's own hardware remain open.</p>
</div>

### Summary: what v2 decides

<table class="t">
<tr><th style="width:23%">Question</th><th>Answer in this spec</th></tr>
<tr><td><b>What changed?</b></td><td>The v1 audit was repeated and found <b>32 more gaps</b> (Section 1; all 30 v1 rows kept). Fifteen modules were added (Section 5): eye behavior, liveness stacking, signal fingerprints, security, sighting log, voice output, location baselines, thermal grayscale, headless test + golden dataset, macOS build, sensor adapter layer, feedback loop, Android fallback node, sweep timeline, app gate. Architecture is unchanged: <b>one process, a thread per sensor, scores in 0..1, a fusion layer</b>.</td></tr>
<tr><td><b>Most important honest findings</b></td><td>(1) <b>Micro-saccades cannot be measured with this rig at any useful distance</b>: they need ≥250 Hz sampling and about 0.1 mm of pupil shift, which is under one pixel at 0.5 m. Pupil size, blink and corneal-glint behavior at ≤1 m are feasible; they are research signals, not detectors. (2) <b>A silicone mask worn by a live person keeps the wearer's real eyes</b>, so eye signals cannot catch it; thermal and skin-surface cues may. (3) The RTL-SDR V4 tunes only <b>500 kHz–1.766 GHz</b> and cannot see 2.4 GHz BLE/Wi-Fi at all, so IQ-level radio fingerprinting is out; v2 uses behavioral BLE/AP fingerprints and AP clock skew. (4) Voice anti-spoofing is weak in the wild (ASVspoof 5 best closed EER &lt;15%, baselines &gt;29%); voice is a low-weight stack member, never a verdict. (5) Offline operation and remote wipe conflict; the documented default is crypto-erase triggered locally or by a paired phone, with no cloud relay.</td></tr>
<tr><td><b>Cost (estimates, before tax/shipping)</b></td><td>Tier A v2 <b>≈ $461</b> (v1: $344; +$117 for eye camera, mic, GPS, haptics, lens, LEDs, buttons). Tier B v2 increment <b>≈ $401</b>, total <b>≈ $862</b> (v1: $722). The Android phone and a Mac/Linux build machine are assumed already owned.</td></tr>
<tr><td><b>Ethics and legal guard (unchanged, extended)</b></td><td>The system <b>never labels a real person "robot"</b>, "fake" or "not alive"; it reports signatures and indicators that were observed or not observed, with benign causes. Eye, voice and liveness data are treated as <b>sensitive biometrics</b>: consenting adults only, on-device only, derived traces only, 30-day retention, written release (Section 14). Anti-tamper features protect the owner's own data on the owner's own device.</td></tr>
<tr><td><b>How do we know it worked?</b></td><td>Frozen pass/fail thresholds for 29 experiments (E-01…E-29), including headless replay, a golden dataset protocol, security tests, and per-module gates. A module that misses its gate ships <b>disabled by default</b>; it never blocks the G1 decision unless listed there.</td></tr>
<tr><td><b>What still needs the owner?</b></td><td>Only: purchase approval (D-01), and five hardware or policy facts (R-1…R-5, Section 15). Everything else is settled.</td></tr>
</table>

### Changelog v1 → v2

| Area | v1 | v2 |
|---|---|---|
| Gap audit | 30 rows | same 30 rows (status updated where v2 changed them) + **32 new rows** N-01…N-32 |
| Modules | none | **15 modules** M-01…M-15 with feasibility, design, defaults, licenses, tests |
| Fusion | 6 scores, logistic regression | **11 scores in 6 families**, stacked logistic regression with missing-family mask, ≥2-family evidence rule, signatures A1–A11 |
| Parts / BOM | Tier A $344 / B $722 | adds eye camera + lens, mic, GPS, haptics, buttons, optional secure element, speaker; **$461 / $862**; all live prices dated |
| Wiring / power | GPIO18 LED gate; ~8 W / 11 W | **GPIO map redone** (I2S needs GPIO18–21; GPS moved to I2C); ~9.9 W / 12.4 W typical, 15 / 19 W peak |
| Platform | rig first | unchanged; **Android operator app** (new) and fallback node; Kotlin + Python share JSON score schema |
| Data and privacy | no audio, no GPS, no biometrics | mic, GPS and eye data added with push-to-talk, hardware mute, coarse exports, derived-only storage |
| Tests | E-01…E-10 | **E-11…E-29** added; gates G0, G1 kept; per-module gates M-gates added |
| Decisions | 7 defaults, 8 open | **settled defaults D-02…D-45**; residual R-1…R-5 |
| CI / build | none | local `build_all.sh`; **no paid Actions** (macOS runners $0.062/min on private repos); macOS job is spec-only |


## 1. Gap audit: before and after (all 30 v1 rows kept, 32 new rows)

Legend: "Closed" = researched and cited; "Decision" = closed by a recorded default; "Open" = needs hardware testing. v1 rows are unchanged except for a bold **v2:** note where v2 changed their status. <b>Section numbers inside v1 rows refer to the v1 PDF;</b> v2 equivalents: BOM 6, wiring/safety 7, software 8, data 9, build 10, tests 11, false positives 12, risks 13, legal 14, decisions 15.

**A. v1 rows (before, with v2 updates)**

| ID | Gap, weak claim or missing item in v1 | Sev. | How it is closed in this spec | Status |
|---|---|---|---|---|
| G-01 | **Brilliant Frame listed as an option; it is delisted.** Product page 404s; no end-of-life notice (Talaya, Extentos, oculos.io). | High | Removed from options. Halo is the only Brilliant product ("Shipping now" per store). | Closed |
| G-02 | **Halo maturity and US availability unclear.** Store says "Shipping now" but gives no date. Maker posts (reported on Reddit) show batch shipping, production pause until Oct 12, early pre-orders still waiting; return costs $49 restocking + shipping. | High | Halo moved to Phase 2 only. No Phase 0–1 dependency on it. Order-risk noted in Section 4. | Closed |
| G-03 | **Halo "open" claim too broad.** The firmware repo is public, but the Alif SDK portion is under a vendor license (restricts use to Alif silicon; no copyleft relicensing); Brilliant docs still say repo "coming soon" while GitHub shows it. | High | Treated as "mostly open, not fully OSI-open." Decision D-06 asks the owner whether that is acceptable. **v2:** D-06 settled: Halo stays out of the default build. | Decision |
| G-04 | **Halo camera/NPU capability uncertain.** v1 implied on-device ML. Docs show a Lua API returning 640-px JPEGs over BLE (16–80 KB each) and a raw-read call; a July review said Lua exposes no NPU/inference API. | High | Spec assumes **phone/laptop-side** processing, about 1 frame per second or less over BLE **[UNVERIFIED rate]**. On-device ML is not planned. | Closed (assumption) |
| G-05 | **Mentra Live ordering and limits unverified.** | Med | Verified: US-address web orders only; $449; Apache-2.0 OS, SDK and Bluetooth starter kit; camera photo upload to own webhook; streaming to own RTMP/SRT/WebRTC endpoint. Stock status **[UNVERIFIED]**. | Closed |
| G-06 | **Meta glasses treated as an option without license check.** | Med | Verified not open source: limited, revocable license; one third-party app at a time in developer mode. Excluded by the open-source-only rule. | Closed |
| G-07 | **Thermal parts mis-ranked.** v1 called the MLX90640 "cruder" without noting accuracy. | Med | Datasheet: ±1 °C typical vs Lepton 3.5 typical ±5 °C (±10 °C low gain). Tier A uses MLX90640 for absolute temperature; Tier B adds Lepton/UVC for spatial detail. Both tested in E-03. | Closed |
| G-08 | **No exact SKUs, links or live prices.** | High | Section 5 BOM with links and dated prices; stock caveats (Adafruit MLX90640 out of stock; RTL-SDR V4 end-of-line). **v2:** BOM re-priced and extended (Section 6). | Closed |
| G-09 | **IR LED eye-safety not addressed.** | High | IEC 62471 design rules and calculation (Section 6.3); exempt-group parts only; hardware current limit; no optics; consenting subjects. Independent lab verification **not** done. | Closed + caveat |
| G-10 | **Battery safety near the head.** | Med | Battery on belt, certified pack with protection; inspection rules (Section 6.4). | Closed |
| G-11 | **Interfaces and power budget missing.** | High | Pinout, buses, cable lengths, budget and runtime estimate (Section 6). Needs measurement (B-10). **v2:** GPIO18 conflict with I2S found and fixed; new budget (N-28, N-29). | Closed (estimate) |
| G-12 | **No software stack, license policy or repo layout.** | High | Section 7: open-source allow-list, deny-list (AGPL, non-commercial), automated license audit, repo tree. | Closed |
| G-13 | **No data schema or privacy design.** | High | Section 8: SQLite schema, hashing of radio identifiers, no face storage by default, 30-day retention. **v2:** schema extended for audio, GPS, eye data (Section 9). | Closed |
| G-14 | **Success metrics not defined before testing.** | High | Section 10: frozen thresholds, gates G0/G1, rule against moving goalposts. | Closed |
| G-15 | **No controls plan.** | High | Mannequin (cold/heated), powered toy robot, humans, phones, silicone prop, hot objects, silent devices (Section 10). | Closed |
| G-16 | **False-positive handling vague.** | High | Operating point set at ≤5% false-positive rate on human controls; contributing signatures shown; sensor-health suppression (Section 11). | Closed |
| G-17 | **Ethics rule only stated, not enforced.** | High | Vocabulary guard in code + automated test; output schema has no "robot" class field (Sections 2, 8, 11). **v2:** guard now also covers voice phrases and signatures A7–A11. | Closed |
| G-18 | **Legal section was generic; FCC claim came from a search summary.** | High | Checked FCC jammer page (jamming illegal; no personal exemptions), 18 U.S.C. §2511(2)(g), 47 CFR §15.121 via search results; checklist in Section 13. The FCC "interception" consumer guide fetch timed out, so wording is **[UNVERIFIED at source]**. **v2:** legal analysis extended to biometrics, voice, GPS (Section 14). | Closed + caveat |
| G-19 | **Thermal claims could drift into health claims.** | Med | FDA's thermography guidance expects ≤±0.5 °C and a blackbody reference for fever triage; our rig is not a medical device and never reports body temperature as health data. | Closed |
| G-20 | **"Phones carry cameras" false-positive for lens glint** and human eyes also retroreflect. | Med | Test E-01 includes phones, glasses, eyes; glint score uses IR-on minus IR-off differencing. | Closed (to be measured) |
| G-21 | **Wi-Fi scanning scope ambiguous.** Monitor mode and probe-request capture raise legal and privacy questions. | Med | Phase 0–1 = BLE advertisements and AP beacons in managed mode only; no monitor mode, no data frames, no cellular. Decision D-05. **v2:** AP clock skew read from managed-mode scan TSF; still no monitor mode. | Decision |
| G-22 | **mmWave module integration unproven.** MR60BHA2 ships with ESPHome for Home Assistant; direct Pi use not verified. | Med | Treated as integration risk RK-07; fallback: read via ESPHome native API or USB serial; drop to Tier B-lite if blocked. | Open |
| G-23 | **Memory-EM (ESauron-style) idea untested with cheap SDR.** Paper used USRP B210. | Low | Optional exploratory experiment E-10, not a gate. **v2:** RTL-SDR V4 range now verified (500 kHz–1.766 GHz); E-10 stays exploratory. | Open |
| G-24 | **Mounting, weight, enclosure absent.** | Med | Pod target <120 g, compute on belt, cable lengths, strain relief (Section 6.2). | Closed |
| G-25 | **No calibration or timing design.** | Med | Thermal two-point calibration, NoIR/thermal alignment, clock sync, drift limits (Section 9). | Closed |
| G-26 | **No logging/reproducibility.** | Med | Session manifest, config hash, git commit, sensor serials in every run (Section 8). | Closed |
| G-27 | **Human-subject policy absent.** | High | Adult household volunteers, written consent form, right to delete, no strangers (Sections 10, 13). Decision D-04. **v2:** D-04 settled (the owner first, then household adults). | Decision |
| G-28 | **other projects coupling.** | Low | Separate repo and data; no shared code or models. | Closed |
| G-29 | **Robot-specific detection performance has no published evidence.** | High | Stated as hypothesis; Phase 1 can only show separability of lab proxies, not real humanoids. Real-robot test is Decision D-08. | Open |
| G-30 | **Cost bands were guesses.** | Med | Two tiers ($344 / $722 estimated, excluding tax/shipping); alternatives listed. **v2:** re-priced: $461 / $862. | Closed |

**B. New rows found in the v2 re-audit and by the 15 modules**

| ID | New gap found in the v2 re-audit or by a module | Sev. | How it is closed in this spec | Status |
|---|---|---|---|---|
| N-01 | **No eye-behavior physics in v1.** Micro-saccade, pupil and corneal signals were never assessed for distance, frame rate or light needs. | High | Section 5 M-01: ≥250 Hz needed for micro-saccades (sources) vs ≤120–143 fps cameras; pupil shift ≈0.09 mm ≈0.5 px at 0.5 m (my calculation). Micro-saccades: report-only. Pupil size, blink, glint geometry at 0.3–1 m: feasible. E-11…E-14. | Closed (analysis); tests open |
| N-02 | **v1 forbade face detection, but eye analysis needs an eye region.** | High | Operator-aimed narrow eye camera; transient eye-region detection in RAM only; no face templates, no stored face crops (D-17). | Decision |
| N-03 | **v1 non-goal 'no biometric' no longer true:** eye dynamics, voiceprint and liveness are biometric-adjacent. | High | Legal analysis (Section 14): BIPA lists retina/iris scans and voiceprints; WA RCW 19.375 and TX CUBI cover voiceprints; GDPR Art. 9. On-device only, derived traces, written release, 30-day retention, deletion rebuilds the golden set. | Closed + caveat |
| N-04 | **v1 safe harbor 'no microphones' lost** once voice is added; all-party-consent states. | High | Push-to-talk lab prompts only, hardware mute switch, no ambient recording, enrolled consenting speaker only (D-18). CA, FL, IL, WA are all-party states (recordinglaw.com). | Decision |
| N-05 | **Pupillary light reflex needs controlled light** and smartphone pupillometry fails often (30% vs 4% for infrared devices). | Med | Passive pupil/hippus by default; active light step only in lab, with photometer and consent (D-15). E-13 is report-grade. | Decision |
| N-06 | **Silicone mask on a live wearer keeps real eyes, pulse and voice.** | High | Stated limit: eye, pulse and voice signals cannot catch it; only thermal/NIR skin cues might (E-15 reports it, no pass criterion). | Closed (limit) |
| N-07 | **Liveness signals are spoofable:** rPPG, blink, voiceprint can be replayed or cloned. | High | Stack of independent families, challenge-response IR glint code, no standalone verdict, ROC reported with attack set. | Closed (design); tests open |
| N-08 | **Voiceprint purpose creep:** liveness consistency vs identifying people. | High | Purpose limitation: lab liveness checks on enrolled volunteers only; never used to identify strangers; embeddings ephemeral unless written enrollment (D-18). | Decision |
| N-09 | **v1 implied SDR fingerprinting; RTL-SDR V4 tunes only 500 kHz–1.766 GHz.** | High | IQ-level BLE/Wi-Fi RFFI out of Phase 0–1. Behavioral BLE fingerprints + AP clock skew from beacon TSF (Jana and Kasera, MobiCom 2008) instead. A 2.4 GHz SDR is a residual item (R-3). | Closed (correction) |
| N-10 | **BLE fingerprint limits:** random addresses rotate; clocks allow ±50 ppm active / ±500 ppm sleep; IQ fingerprints degrade at low SNR and in motion. | Med | Baselines only for fixed emitters on own premises; 'unknown' is a valid class; no claim of tracking phones. | Closed |
| N-11 | **'Tampering' is an over-claim:** drift can be firmware, temperature, battery. | Med | Output 'emitter changed vs baseline' (A9), needs ≥2 changed features persisting ≥3 windows; no attribution of cause. | Decision |
| N-12 | **Security was LUKS only:** no key hierarchy, channel, or log integrity. | High | M-04: AES-256-GCM/XTS at rest, Keystore keys, Noise_XX BLE channel, hash-chained HMAC log, anchors. | Closed (design) |
| N-13 | **Offline operation conflicts with remote wipe.** | High | Resolved default D-23: crypto-erase triggered locally (panic, failed unlocks) or by a paired phone in BLE range; optional user-owned relay OFF by default; dead-man timer OFF. | Decision |
| N-14 | **Overwrite wipe is unreliable on SD/flash (wear levelling).** | Med | Wipe = destroy keys (LUKS header erase, Keystore entry delete), not overwrite. | Closed |
| N-15 | **GPS privacy and v1 'No GPS' field.** | Med | Encrypted at rest, rounded to 0.01° on export, indoor 'no fix' recorded not guessed (D-25). | Decision |
| N-16 | **OSM tile policy:** bulk or pre-seeded downloads from tile.openstreetmap.org are forbidden; ODbL attribution needed. | Med | Offline maps from Mapsforge map files built from OSM extracts; attribution on screen; no tile-server fetches (D-26). | Closed |
| N-17 | **TTS licensing:** Piper (piper1-gpl) and eSpeak NG are GPL-3. | Med | Excluded from the default build. Platform TextToSpeech with offline voice on the phone; Flite (BSD) on the Pi; sherpa-onnx (Apache-2.0) optional once a voice's license is read (D-27). | Closed |
| N-18 | **'Threat-tiered' wording conflicts with the ethics rule.** | Med | Tiers are named FYI / Attention / Confirmed and refer to <i>observed signatures</i>, not people; Confirmed requires operator confirmation; phrases come from a whitelist (D-28). | Decision |
| N-19 | **Per-location baselines are hard for a moving head-mount.** | Med | RF-first baseline; thermal/NIR comparison only at marked anchors (ArUco, OpenCV); report-only thresholds for the optical path (M-07, E-21). | Closed (limit) |
| N-20 | **Color thermal palettes mislead and imply medical readings.** | Low | Grayscale default, fixed scale with legend, overlay on request (M-08, E-22). | Closed |
| N-21 | **No headless mode or regression data:** tests needed hardware and people. | High | Replay/sim adapters, virtual clock, golden dataset with hash manifest and frozen test split (M-09, E-23). | Closed (design) |
| N-22 | **macOS CI would cost money:** standard macOS runners $0.062/min on private repos (GitHub docs, 2026-10-28). | High | No paid Actions. Local `scripts/build_all.sh`; optional free self-hosted runner; CI job is spec-only (D-32). | Decision |
| N-23 | **macOS signing and notarization need a paid Apple program** [UNVERIFIED fee]. | Low | macOS artifact is an unsigned local build; documented Gatekeeper step; no notarization. | Decision |
| N-24 | **Sensors were wired into feature code:** no abstraction for replay, simulation or the phone. | High | M-11 adapter contract; real, replay and sim adapters; Kotlin adapter for the phone. | Closed (design) |
| N-25 | **Feedback loop could contaminate the pre-registered test set.** | High | Quarantine → review → growth set; frozen test split is immutable and hash-checked (M-12, E-26). | Closed |
| N-26 | **Android fallback could depend on proprietary Google services** (ML Kit, Play Services location). | Med | AOSP APIs only (LocationManager, CameraX, BiometricPrompt); no ML Kit, no Firebase; minSdk 29 (M-13). | Closed |
| N-27 | **App gate can be a UI-only check that is bypassable.** | High | Biometric unlock bound to a Keystore key (CryptoObject); BIOMETRIC_STRONG only; FLAG_SECURE (M-15, E-29). | Closed |
| N-28 | **Pin conflict:** v1 LED gate on GPIO18 (an I2S clock pin); v2 needs I2S, GPS, haptics. | High | GPIO map redone (Figure 3); GPS on I2C instead of UART. | Closed |
| N-29 | **Power budget omitted new loads.** | Med | New budget: ~9.9 W / 12.4 W typical, peak 15 / 19 W; 25 W PD profile required. | Closed (estimate) |
| N-30 | **License status of new libraries unchecked.** | High | Verified: Tink Apache-2.0; SQLCipher BSD-3; noise-java and Python noiseprotocol MIT; AASIST MIT; ECAPA model Apache-2.0; sherpa-onnx Apache-2.0; MapLibre Native BSD-2; Mapsforge LGPL-3 with shipping exception. Excluded: Piper, eSpeak NG, CryptoAuthLib (non-OSI). Model <i>training-data</i> licenses are <b>[UNVERIFIED]</b>. | Closed + caveat |
| N-31 | **Tiny samples:** ~150 runs cannot support many fusion inputs. | Med | ≤6 stacking inputs (one per family), L2 penalty, bootstrap CIs clustered by subject, report-only for sub-groups. | Closed |
| N-32 | **Anti-tamper and wipe features can be misread as evidence destruction.** | Med | Scope: protects the owner's own data on the owner's own device; nothing in Phase 0–1 involves third-party records; preservation duty noted (Section 14). | Decision |


## 2. Scope, requirements and non-goals

**Purpose.** Learn, with honest measurements, how much separable signal exists between living people and powered or heated stand-ins using low-cost passive sensing; and provide a **hidden-camera sweep** tool for the owner's own premises, with an encrypted sighting log. Phase 0–1 only: private premises, consenting adults, no strangers, no public places.

**Requirements.** R-01…R-10 from v1 stand (R-03 now covers two LED banks; R-07 now covers audio, GPS and eye traces). New:

| ID | Requirement | Verified by |
|---|---|---|
| R-11 | Eye module outputs pupil, blink and glint-geometry features at ≤1 m; micro-saccade output is offline report-only. | E-11…E-14 |
| R-12 | Liveness stack needs ≥2 independent families to raise an indicator-absent signature; never a verdict. | E-15, E-16 |
| R-13 | Fingerprint module baselines fixed emitters, flags drift (A9) after ≥2 features change for ≥3 windows. | E-17 |
| R-14 | Data at rest AES-256 (GCM or XTS); keys never in plaintext on disk; constant-time comparisons; channel encrypted and rekeyed; log hash-chained. | E-18 |
| R-15 | Works fully offline; remote wipe resolved by D-23; panic gesture locks in ≤1 s. | E-18 |
| R-16 | Sighting log is encrypted, auto-stamps GPS when a fix exists, shows pins on an offline map with OSM attribution, no network access in the offline build. | E-19 |
| R-17 | Voice output has three tiers; Confirmed barges in within ≤300 ms; only whitelisted phrases. | E-20 |
| R-18 | Per-site baselines; new fixed emitter or object at a known anchor raises A10. | E-21 |
| R-19 | Thermal display is grayscale by default; color overlay is a toggle. | E-22 |
| R-20 | Whole pipeline runs headless from recorded data with a virtual clock and a frozen golden dataset; identical outputs on repeat. | E-23, E-25 |
| R-21 | One commit builds an Android APK and a macOS artifact via a local script; no paid CI. | E-24 |
| R-22 | Confirmed sightings become quarantined candidate clips; the frozen test split never changes. | E-26 |
| R-23 | Any Android device with a camera can run as a reduced detection node. | E-27 |
| R-24 | Sweep timeline shows what is new since the previous sweep; records are tamper-evident. | E-28 |
| R-25 | App opens only after strong biometric or device-credential unlock; keys are bound to that unlock. | E-29 |

**Non-goals.** No face recognition or face templates; no identification of any person; no stored face crops; no strangers; no public spaces; no cloud services; no cellular, no monitor mode, no jamming, no transmit except IR LEDs and the Pi/phone's normal client radios; no medical readings; no claim that output identifies a robot; no use of the security features to hide wrongdoing or evade lawful requests.

**Standing rules.** Open-source only (no AGPL, no non-commercial licenses), clean temp files, never touch other projects, nothing purchased or sent without the owner's approval, **no paid GitHub Actions**.

## 3. System architecture and fusion design

<img src="spec_assets/arch2.svg" style="width:100%"/>

**Process model (unchanged in spirit).** The Pi runs <b>one process</b> with a thread per sensor adapter, a sync layer, a 1 Hz feature/score loop, one fusion layer, and a guard. The phone app has the same shape in Kotlin (coroutines per adapter). Why a pod and belt pack: heat, weight and battery risk stay off the head; the pod holds only the sensors that need the wearer's viewpoint.

**Signatures reported (vocabulary).** Observations, never identities. A1–A6 are as in v1; A7–A11 are new.

| Code | Signature | Source | Typical benign causes (always shown with the alert) |
|---|---|---|---|
| A1 | Lens-glint candidate | NoIR + IR LED code | Phones, webcams, glasses, watches, jewelry, human eyes |
| A2 | Active near-IR emitter | NoIR (LED off) | Security cameras, remotes, face-unlock, night-vision rings |
| A3 | Thermal pattern atypical vs baseline | Thermal | Cold hands, coats, hot drinks, fever, heaters, sun-warmed objects |
| A4 | Radio emitter near | BLE/Wi-Fi | Phones, watches, earbuds, medical devices, beacons |
| A5 | Expected vital motion absent at ≤1 m (B) | mmWave | Subject moving, wet clothing, radar blocked |
| A6 | Motion pattern irregular | Frames + IMU | Ordinary movement, children |
| A7 | Eye-dynamics atypical (pupil, blink, glint geometry) | Eye camera | Sunglasses, contact lenses, drops, fatigue, medication, glare, glass eye (prosthesis) |
| A8 | Voice-liveness indicators not observed | Mic | Poor mic placement, noise, a speaker phone, a cold, a recording device in use |
| A9 | Known emitter changed vs its baseline | BLE/AP | Firmware update, battery, temperature, relocated device |
| A10 | New fixed emitter or object at a known anchor | Baseline diff | Guests' devices, moved furniture, new appliance |
| A11 | Expected liveness indicators absent across ≥2 families | Stack | Photo or video on a screen, mask on a stand, mannequin, wearer outside the sensor's range |

**Fusion v2 (stacked, deliberately small).**

1. Each module emits a score in [0, 1], a confidence in [0, 1] and a health flag (unchanged contract). Eleven scores: S_glint, S_nir_emit, S_thermal, S_rf, S_radar, S_motion, S_eye, S_live (rPPG + blink), S_voice, S_rf_drift, S_newobj; adapter health is a flag, not a score.
2. Scores fold into <b>six families</b> (optical, thermal, RF, vital, eye/liveness, voice): the family value is the confidence-weighted maximum of its member scores. Level 2 is one L2-regularized logistic regression (scikit-learn, BSD-3) over ≤6 family values with a <b>missing-family mask</b>; scores are cross-fitted so the level-2 model never sees scores it trained on.
3. Evaluation is leave-one-subject-out, with bootstrap confidence intervals clustered by subject (N-31). Threshold is set at human false-positive rate ≤5%; the true-positive rate is reported even if low.
4. Evidence rule: an alert needs ≥2 independent families; one family alone is an "FYI". If ≥2 families are unhealthy the index is suppressed.
5. **Outputs:** `anomaly_index`, `signatures[]`, and `liveness_indicators[]` (each "observed" or "not observed", with the benign-cause list). No output field names a class.

<img src="spec_assets/flow2.svg" style="width:100%"/>

## 4. Platform decision: rig first, glasses later (facts verified 2026-10-28; unchanged from v1)

| Platform | Verified facts | Fit |
|---|---|---|
| **Head-mounted rig (Pi 5 + sensors) + Android operator app** | Only route to thermal, IR LED, radio and eye sensing; every part has a datasheet or store page. | **Chosen** |
| **Mentra Live + MentraOS** | $449; US-address web orders only; 43 g, 12 MP camera; MentraOS, Bluetooth SDK and starter kit Apache-2.0; no display. IR sensitivity, raw IMU **[UNVERIFIED]**. | Phase 2 carrier; spike S-01 optional |
| **Brilliant Labs Halo** | $399, batch shipping; Lua API returns 640-px JPEGs over BLE; firmware public with mixed licenses (Alif SDK vendor license). | Phase 2 only; D-06 settled: not in the default build |
| **Brilliant Labs Frame** | No longer sold; no end-of-life notice. | Excluded |
| **Meta Ray-Ban/Oakley** | Not open source; limited revocable license; one third-party app at a time. | Excluded |
| **Even G2, Vuzix Z100, Snap SPECS, XREAL, Android XR** | No camera, closed, or not shipping. | Excluded / watch |

Glasses compatibility spike S-01 (does a glasses camera even pass 850 nm?) stays optional and skipped until G1 (D-07 settled: skip).


## 5. Module specifications M-01…M-15

Each module follows one template: <b>Feasibility</b> (what the physics and literature allow), <b>Design</b> (what we build, with settled defaults), <b>Libs</b> (license checked), <b>Gate</b> (the experiment that decides whether it stays enabled). Calculations marked "(calc)" are mine, from the stated assumptions, not measurements.

### M-01 Eye-behavior analysis (signals S_eye; signature A7)

**Feasibility.** Micro-saccades last a few ms and studies use ≥250 Hz trackers; 30–60 Hz webcams miss them, 120 Hz still under-samples (Tobii/PMC, RemoteEye). Our best eye camera (OV9281, 120 fps USB / up to 143 fps CSI per the vendor listing) is below 250 Hz. A 0.5° eye rotation moves the pupil ≈0.09 mm (calc, assuming a ≈10 mm lever arm). With a 25° lens on 1280 px the pixel footprint is 0.17 mm at 0.5 m and 0.35 mm at 1 m (calc), so the shift is ≈0.5 px and ≈0.25 px. <b>Micro-saccade detection at a distance is not feasible; it is report-only.</b> Pupil diameter is feasible: a 4 mm pupil spans ≈23 px at 0.5 m, ≈12 px at 1 m, ≈6 px at 2 m (calc). The pupillary light reflex (latency ≈0.17–0.23 s) needs controlled light, and smartphone pupillometers failed 30% of attempts vs 4% for infrared devices. Hippus (0.3–0.7 Hz) is too small to rely on. Corneal reflections work as liveness cues against photos, screens and some masks (Y-EYES/AIME report ≈200 ms detection), but their reliability against contact lenses and hand-made prosthetic eyes is unclear and ocularist-made eyes can look live even in near-IR; only central specular reflections hint at an odd cornea. <b>A wearer under a silicone mask keeps real eyes.</b>

**Design.** (1) Operator-aimed OV9281 with a 25° M12 lens at 0.3–1 m; two 850 nm LEDs pulsed in sync with exposure; 400×300 eye ROI found transiently in RAM (OpenCV Haar eye cascade, Apache-2.0 [cascade-file license UNVERIFIED]); no face template, no stored crops (D-17). (2) Features at 60–120 fps: blink rate and duration, pupil diameter trace (ellipse fit), glint count/size/offset from pupil centre, bright-pupil response (on-axis LED) and a <b>glint challenge-response</b>: the two LEDs run a random on/off code; a live cornea's glints must follow the code within one frame, a replayed screen cannot. (3) Camera-lens glints (A1) look different from corneal ones: sharp, tiny, no pupil structure, retroreflective; the eye module can down-weight them. (4) Active light-step PLR: lab only, consenting volunteer, visible LED ≤1 s with a photometer reading logged, start dim; default OFF (D-15). (5) Micro-saccade estimator runs offline on saved 120 fps pupil traces for the report only.
**Libs.** OpenCV (Apache-2.0), NumPy/SciPy (BSD-3). <b>Gate.</b> E-11…E-14; if E-11 or E-14 fail, S_eye ships disabled.

### M-02 Liveness detection with multi-signal stacking (S_live, S_voice; signature A11)

**Feasibility.** rPPG pulse works at short range with still subjects and is spoofable by lighting and motion; mmWave breathing helps to 1.5 m (v1 evidence). Voiceprint (speaker embedding) can verify an <i>enrolled</i> volunteer but a cloned voice passes it; liveness needs a separate anti-spoof model, and ASVspoof 5 shows top closed-set EER &lt;15% while baselines exceed 29%: weak in the wild. A live TTS speaker cannot be told from a person by voice alone. Therefore no single family decides anything.
**Design.** Families: Optical/thermal (skin-region thermal texture + NIR response), Vital (rPPG from NoIR/eye cam, mmWave breathing), Eye (blink, pupil, glint code), Voice (replay/TTS indicators), RF (a person's carried devices; absent devices prove nothing). Stack per Section 3: ≥2 families must agree that expected indicators are <i>not observed</i> to emit A11, wording "Expected liveness indicators not observed: pulse, blink. Benign causes: …". Challenge-response parts: glint code (eye), a spoken digit prompt (voice, lab only).
**Libs.** Own implementation of published rPPG methods (CHROM/POS patent status <b>[UNVERIFIED]</b>); scikit-learn. <b>Gate.</b> E-15.

### M-03 Signal fingerprint module (S_rf, S_rf_drift; signature A9)

**Feasibility.** Physical-layer BLE fingerprints exceed 99% in lab studies but degrade with low SNR, motion, power level and temperature (Oakland 2022: viable but sometimes unreliable in a field study of hundreds of devices; WCNC 2025: a noise-robust model still keeps only ≈75% at 10 dB SNR), and they need raw IQ, which the Pi's BLE chip and an RTL-SDR (500 kHz–1.766 GHz) cannot provide. BLE clocks allow ±50 ppm active and ±500 ppm sleep, so timing is not a unique ID. AP clock skew from beacon TSF timestamps is a proven fingerprint (Jana and Kasera, MobiCom 2008: stable per AP, estimable from ≈50–100 frames) and is available in managed-mode scans.
**Design.** For <b>fixed emitters on the owner's own premises</b> only: baseline = advertising-interval mean/jitter, TX-power field, payload template and length, service UUID set, company ID, per-channel (37/38/39) ratio where a sniffer is present, RSSI distribution at anchor, and AP TSF skew. Drift (A9) = ≥2 features outside 3σ of baseline for ≥3 consecutive 60 s windows. Device-type identification = lookup on company ID, OUI of APs (not of rotating BLE addresses), service UUIDs, and payload pattern into ≥5 coarse types plus "unknown". No attempt to track phones or people; random-address devices are counted, not followed.
**Libs.** bleak (MIT), `iw` as a subprocess (ISC/GPL tools only as executables), NumPy. <b>Gate.</b> E-17.

### M-04 Security module (cross-cutting)

Scope: <b>protects the owner's own data on the owner's own device</b> (D-45).

| Control | Default design | Library (license) |
|---|---|---|
| Data at rest | Pi: LUKS2 (AES-256-XTS) data volume; phone: SQLCipher DB, 256-bit key wrapped by an Android Keystore AES-256-GCM key (StrongBox when present, attestation checked, `setUserAuthenticationRequired`). | cryptsetup (GPL tool, subprocess), SQLCipher (BSD-3), Android Keystore (AOSP), Tink (Apache-2.0) |
| Constant-time crypto | No custom primitives. Compare secrets only with `hmac.compare_digest` / libsodium `sodium_memcmp` / Tink. A lint test bans `==` on key, tag or MAC variables. Python cannot guarantee timing of high-level code; stated as a limit. | libsodium via PyNaCl (ISC / Apache-2.0), BoringSSL inside Tink |
| Pod ↔ phone channel | Pair once by QR code (static key fingerprints out of band). Per session: <b>Noise_XX_25519_ChaChaPoly_BLAKE2s</b> handshake over BLE GATT; payloads are scores, events, thermal frames (≈6 KB/s); <b>Rekey every 1,000 messages or 10 min</b>, whichever first; re-handshake every session; static keys rotated every 90 days or on re-pair. A double ratchet is not used: it targets asynchronous messaging and adds complexity (D-22). | noise-java (MIT) on Android; Python `noiseprotocol` (MIT) on the Pi |
| Offline operation | No cloud, no INTERNET permission in the offline APK build; time from RTC/GPS. | — |
| Tamper-evident log | Append-only; `h_i = HMAC-SHA256(k_log, h_{i-1} ‖ canonical(record_i))`; the head hash and count are signed (Ed25519) and anchored on the phone every 60 s or 100 records; verification detects edits, deletions, reordering, and truncation past the last anchor. | hashlib (PSF), PyNaCl |
| Kill switch / remote wipe | <b>Conflict resolved (D-23):</b> an offline device cannot receive a remote command, so wipe is <b>crypto-erase</b> (LUKS header erase + Keystore key delete; overwriting flash is unreliable). Triggers: panic gesture, 10 failed unlocks, or a signed wipe command from the paired phone over the Noise link. An optional user-owned HTTPS relay is OFF by default; dead-man timer OFF. The phone's own loss case is covered by the OS vendor's find-my-device service, which is not part of ASB. | — |
| Panic gesture | Pod button: hold 1 s = <b>soft panic</b> (clear screens, drop session keys, require unlock); then press 3× within 5 s with haptic confirmation = <b>hard panic</b> (crypto-erase). Phone: 5× volume-down in the app, soft panic only. Accidental hard erase is guarded by the double step. | — |

**Gate.** E-18.

### M-05 Sighting log (S: events; map screen)

**Design.** Each sighting = signature codes, scores, thermal/NIR crop (non-person only), operator verdict (confirmed / benign / unresolved), GPS fix, timestamps, hash-chain link. Stored in SQLCipher on the phone; the Pi keeps a mirror on the LUKS volume. GPS: Android `LocationManager` GPS provider (AOSP, no Play Services); pod GPS (PA1010D) as backup. Indoors there is usually no fix: recorded as "no fix", never guessed. Exports round coordinates to 0.01° (≈1.1 km) unless the owner overrides (D-25). <b>Offline map:</b> Mapsforge (LGPL-3.0 with its shipping exception) renders Mapsforge map files built from OSM extracts (ODbL data); "© OpenStreetMap contributors" stays visible; the OSM Foundation tile policy forbids bulk or pre-seeded downloads from tile.openstreetmap.org, so we never fetch those; MBTiles + MapLibre Native (BSD-2) is the alternative. Sighting pins live in our own DB layer, not merged into OSM-derived data. <b>Gate.</b> E-19.

### M-06 Voice output with tiered barge-in

**Design.** Tiers describe <i>observed signatures</i>, not people. <b>FYI</b>: haptic tick, no speech. <b>Attention</b>: ≤8-word whitelisted phrase, queued, rate-limited to one per 10 s. <b>Confirmed</b>: spoken immediately, <b>barges in</b> (cuts current speech) and repeats until acknowledged; requires an operator confirm button, or ≥3 families plus operator ack; for sweep mode it means "operator physically found it". Phrases are templates ("Candidate camera lens at left, one metre"); no free text; the vocabulary guard checks every template at build time. TTS: Android platform TextToSpeech with an <b>offline voice</b> (reject voices that need network); Flite (BSD) on the Pi; Piper and eSpeak NG are GPL-3 and excluded; sherpa-onnx (Apache-2.0) is allowed only with a voice whose model card license is read first. Phone earpiece/wired earphones; Bluetooth earbuds would appear as RF emitters (own devices go on a self-allowlist). <b>Gate.</b> E-20.

### M-07 Per-location baselines and new-object alert (S_newobj; A10)

**Design.** A site is a named place with 1–6 <b>anchors</b> (ArUco markers, OpenCV, Apache-2.0). Baseline pass ×3: RF set (fixed emitters), NoIR glint candidate list, thermal background (median 32×24 frames) at each anchor. Later passes compare: <b>new fixed emitter</b> (most reliable), new thermal blob ≥5 °C above ambient and ≥4 px, new glint candidate. <b>Limits (honest):</b> a hand-held head view does not register exactly; lighting, moved furniture and warm sunlit surfaces cause misses and false alarms; optical A10 thresholds are report-only, RF A10 is gated. <b>Gate.</b> E-21.

### M-08 Thermal grayscale default with color overlay toggle

Default view: linear 8-bit grayscale on a fixed 10–45 °C scale (legend always shown), so ranking is by brightness and no palette implies a threshold; toggle = inferno/viridis-style overlay (matplotlib palettes are permissive-licensed) alpha-blended on the NoIR frame; auto-range toggle separate. The toggle never changes stored data (raw arrays are always saved) and a "not a medical measurement" tag remains. <b>Gate.</b> E-22.

### M-09 Headless test mode and golden dataset

**Design.** `asb --headless --replay <clip-set>` runs the full pipeline with <b>replay adapters</b> (recorded timestamps), a <b>virtual clock</b>, GPIO/LED stubs that assert the LED is never driven, no network and no hardware. Golden dataset = versioned clips (derived features and non-person NoIR/thermal arrays; volunteers' raw eye/voice never included) with `manifest.json` (SHA-256 per file, label, source, consent ID, license, split). Splits are subject-disjoint: <b>train</b>, <b>dev</b>, and a <b>frozen test</b> split whose manifest hash is recorded in the decision log at G0; the frozen split never changes (re-freeze needs a new decision and resets claims). Stored as an encrypted archive on local disk; git holds only manifests and code. Runs on Linux (box or laptop), Pi and Mac. <b>Gate.</b> E-23, E-25.

### M-10 macOS CI job producing the Android APK and macOS artifacts from one commit (spec-only)

**Decision (D-32).** GitHub-hosted macOS runners are free on public repos but cost <b>$0.062 per minute on private repos</b> (GitHub docs, 2026-10-28); the owner's rule forbids paid Actions. Therefore the "CI job" is a <b>local script</b>: `scripts/build_all.sh` (run on the owner's Mac) refuses a dirty git tree, records `git rev-parse HEAD`, builds the APK (Gradle, JDK 17, Android command-line tools; the Android SDK license is Google's and is a build-time tool only) and the macOS app (py2app, MIT, or a zipped CLI), writes `BUILD_INFO.json` (commit, tool versions, SHA-256 of both artifacts) into both, and verifies the two commit hashes match. Linux alternative: the same Gradle APK build on the box (free). Railway Linux builders are possible but not priced here <b>[UNVERIFIED]</b>. An optional free self-hosted runner (GitHub states self-hosted usage is currently free; a planned $0.002/min fee was postponed, so recheck) may call the same script; hosted macOS only if the repo is public and the owner approves. macOS artifact is <b>unsigned</b>; notarization needs a paid Apple program (fee <b>[UNVERIFIED]</b>). <b>Gate.</b> E-24.

### M-11 Sensor bus / driver adapter layer

**Contract (Python `Protocol`; Kotlin `interface` mirrors it from one JSON schema).**

```
class SensorAdapter(Protocol):
    id: str; bus: Literal["i2c","csi","usb","uart","i2s","gpio","ble","wifi","android"]
    caps: set[str]                    # e.g. {"thermal_frame","nir_frame","rf_adv","audio_ptt"}
    def open(self, cfg: dict) -> None; def start(self) -> None; def stop(self) -> None
    def read(self, timeout_s: float) -> Sample | None    # Sample{t_mono_ns,t_wall,seq,units,quality,data}
    def health(self) -> Health                           # OK | DEGRADED | FAILED + reason
class ScoreModule(Protocol):
    def update(self, window: Window) -> Score            # Score{value 0..1, confidence 0..1, health, evidence}
```

Rules: one thread per adapter; bounded queue with drop-oldest and a drop counter; timestamps stamped at read time with monotonic ns; a crash sets FAILED and never stops the session; USB devices re-open with back-off (≤10 s); capability registry lets fusion mask missing families (this is how the phone fallback works). Variants per interface: <b>real</b>, <b>replay</b> (clip files), <b>sim</b> (synthetic generators for unit tests). Adapter and score plug-ins declare a license field; the audit rejects non-allowed licenses. <b>Gate.</b> E-25.

### M-12 Feedback loop: confirmed sightings → labeled golden clips

**Design.** Operator marks a sighting <i>confirmed</i> (e.g. camera physically found) or <i>benign</i> (false positive). The app packages ±10 s of derived features and non-person arrays into a <b>quarantine</b> candidate with label, site, consent flag, and hash-chain link. A reviewer (the owner) promotes it to the <b>growth set</b> (used for train/dev only). Rules: frozen test split never receives clips; any clip with a person but no consent ID is rejected automatically; withdrawn consent deletes the clip and triggers a manifest version bump; models are retrained only offline with logged seeds. <b>Gate.</b> E-26.

### M-13 Fallback mode: any Android device with a camera as a detection node

**Design.** The Kotlin adapters (CameraX, BLE scanner, optional mic) run with the same score modules via the capability registry. Available: A1 glint by white-flash on/off differencing (phones lack an IR illuminator and most front cameras have an IR-cut filter), A4 BLE scan, optional blink/pupil coarse features from the front camera (30–60 fps, no micro-saccades). Not available: thermal, radar, IR eye illumination. Constraints from Android: BLE scan start/stop limited to 5 per 30 s; Wi-Fi scans 4 per 2 min in the foreground, 1 per 30 min in the background; Android 12+ needs BLUETOOTH_SCAN (use `neverForLocation` only if we do not derive location from scans, which filters some beacons). <b>A fallback node can never alert alone</b> (only 2 families: optical + RF); output is advisory. AOSP/Apache libraries only: CameraX, OpenCV Android, TFLite (Apache-2.0); no ML Kit, no Play Services, minSdk 29 (D-35). <b>Gate.</b> E-27.

### M-14 Sweep history timeline

**Design.** A <b>sweep</b> = one hidden-camera session at a site. Table `sweep` (site, start/end, operator, duration, counts per signature, outcomes, GPS, anchor hash). Timeline screen lists sweeps and shows "new since last sweep" using M-07 baselines; records are hash-chained and exports are encrypted. <b>Gate.</b> E-28.

### M-15 App gate

**Design.** Phone: `BiometricPrompt` with <b>BIOMETRIC_STRONG</b> (fingerprint, or face only if the device rates it Class 3) with device-credential fallback; the unlock is bound to a Keystore key through a `CryptoObject`, so the database cannot be decrypted by bypassing the UI check (OWASP warns UI-only checks are bypassable); auto-lock after 60 s in background; `FLAG_SECURE` blocks screenshots and recents thumbnails; OS-enforced lockout after repeated failures; 10 failed credential attempts trigger D-23 crypto-erase. The app never sees biometric data (the OS keeps it), so the gate itself is not a collection of biometrics by ASB (not legal advice). Mac tool: Keychain item with biometric access control. Pi: no screen gate; physical button + LUKS passphrase at boot (typed, or delivered by the paired phone). AndroidX Biometric is Apache-2.0. <b>Gate.</b> E-29.


## 6. Bill of materials v2 (two budget tiers)

Prices are list prices from store pages or search listings seen <b>2026-10-28</b>, USD, <b>before tax and shipping</b>. "Est." = my estimate, <b>[UNVERIFIED]</b>. Stock not confirmed unless stated. <b>Not included:</b> the Android phone (the owner's own, must support Keystore; StrongBox and Class 3 biometrics preferred), the Mac/Linux build machine, and any mannequin or props. Nothing here has been ordered.

**Tier A v2: bench rig + eye, voice, GPS, haptics** (v1 rows A1–A12 unchanged; A13–A20 new).

| # | Item | SKU / link | Qty | Price | Notes and alternatives |
|---|---|---|---|---|---|
| A1 | Raspberry Pi 5, 4 GB | raspberrypi.com/products/raspberry-pi-5/ | 1 | $110 | Price rose $25 in April 2026 (memory costs). 8 GB $175. Alt: Pi 4 4GB $100 (slower). Pi Zero 2 W ($15) is widely sold out. |
| A2 | Official 27 W USB-C supply (bench) | raspberrypi.com/products/27w-power-supply/ | 1 | $12 est. | Price not seen; needed for 5 V/5 A and USB current. |
| A3 | Active cooler | Raspberry Pi | 1 | $5 est. | Pi 5 can reach ~12 W. |
| A4 | Camera Module 3 **NoIR** (75°) | adafruit.com/product/5659 | 1 | $25.00 | In stock (27) at Adafruit when checked; Pimoroni NoIR "coming soon". Alt: Pi GS camera (global shutter, price not checked). |
| A5 | Pi 5 camera cable (22→15 pin), 300 mm | Raspberry Pi / resellers | 1 | $5 est. | Pi 5 needs the mini CSI cable. |
| A6 | **MLX90640 55° thermal breakout** | waveshare.com/product/mlx90640-d55-thermal-camera.htm | 1 | $54.99 | Alts: Adafruit 4407 $74.95 (out of stock; Newark $73.45, ~3 week lead); The Pi Hut £60 (7 left). 110° "BAA" version has wider view, lower detail. |
| A7 | 850 nm IR LEDs, Vishay VSLY5850 | vishay.com/docs/83160/vsly5850.pdf | 2 (+2 spare) | $2 est. | Datasheet: ±3° half angle, 600 mW/sr at 100 mA. Listed exempt in Vishay's IEC 62471 table. Alt: OSRAM SFH 4725S (940 nm, invisible, less camera sensitivity). |
| A8 | N-ch logic MOSFET, resistors, JST connectors, perfboard | Any | 1 kit | $15 est. | |
| A9 | USB-C PD power bank, ≥20,000 mAh, 5 V/5 A PD profile | any certified (UN 38.3) | 1 | $50 est. | **Must output 5 V/5 A** and not auto-off at low current; check before relying on it (RK-04). |
| A10 | Head strap / helmet mount + belt pouch | Generic | 1 | $20 est. | Pod 3D-printed (PETG) or off-the-shelf box. |
| A11 | Calibration kit: TMP117 breakout, matte black tape, aluminum block, kettle/ice | Adafruit / hardware store | 1 | $25 est. | TMP117 ~±0.1 °C class **[UNVERIFIED part/price]**. |
| A12 | Cables, heat-shrink, strain relief, zip ties, spare microSD (64 GB) | Any | 1 | $20 est. | |
| A13 | **Eye camera**: Arducam OV9281 1 MP mono global-shutter NoIR, CSI, 130° M12 module | arducam.com (OV9281 NoIR MIPI) | 1 | $41.99 | Listed in stock (search listing 2026-10-28); up to 143 fps at 1280×800 RAW8. USB version B0332 $49.99 (120 fps MJPG). Cheaper Pi alternatives $25.90–29.19 not checked for NIR. |
| A14 | M12 lens, ≈25° horizontal FOV (swap for the 130° lens) | any M12 lens vendor | 1 | $10 est. | Gives ≈0.17 mm/px at 0.5 m. **[UNVERIFIED]** part and price. |
| A15 | Eye IR LED bank: 2× VSLY5850, logic N-FET, resistors | as A7/A8 | 1 | $6 est. | Second bank on GPIO27, own series switch and current limit. |
| A16 | Second Pi 5 camera/display adapter cable (22→15 pin) | pimoroni.com (Pi 5 cables) | 1 | $5 est. | Price not seen; Pimoroni lists the cables. |
| A17 | I2S MEMS microphone breakout SPH0645LM4H | adafruit.com/product/3421 | 1 | $6.95 | Alt: INMP441 modules ($4–7). Pi 5 wiring: GPIO18 BCLK, GPIO19 WS, GPIO20 DIN; I2S driver quirks **[UNVERIFIED]**. Slide switch on 3V3 = hardware mute. |
| A18 | GPS: Adafruit Mini GPS PA1010D (UART + I2C, STEMMA QT) | adafruit.com/product/4415 | 1 | $29.95 | In stock when listed. Alt: Ultimate GPS PA1616S $29.95; u-blox NEO-M8N module $17.45 (backordered). Indoors expect no fix. |
| A19 | Haptic: DRV2605L controller + LRA motor | adafruit.com/product/2305 | 1 | $7.95 + $3 est. | Silent alert path (FYI tier). |
| A20 | Buttons (ack, panic), 3V3 slide switch (mic mute), series switch for LED supply | any | 1 kit | $6 est. | Panic and ack on GPIO22; mute state read on GPIO23. |
| | **Tier A v2 total** | | | **≈ $461** | v1 $343.99 + $116.84 of new parts = $460.83 |

**Tier B v2: adds second thermal, radar, SDR, audio out, optional secure element** (v1 rows B1–B6 unchanged; B7–B10 new).

| # | Item | SKU / link | Price | Notes and alternatives |
|---|---|---|---|---|
| B1 | FLIR Lepton 3.5 (160×120) | groupgets.com/products/flir-lepton-3-5 | $172 | 86 in stock when checked. Datasheet accuracy ±5 °C typical; glass blocks LWIR. |
| B2 | PureThermal Mini USB (UVC carrier) | groupgets.com/products/purethermal-mini-usb | $114.99 | 640 in stock when checked. **Confirm whether the Lepton is included before ordering [UNVERIFIED].** Alt: TOPDON TC001 256×192 at $289 (topdon.us); open OpenCV parsers exist. |
| B3 | Seeed MR60BHA2 60 GHz breathing/heartbeat kit | seeedstudio.com (p-5945) | $26.99 | Breathing/heartbeat to 1.5 m, presence to 6 m; ESPHome pre-flashed; Pi integration unproven (RK-07). |
| B4 | RTL-SDR Blog **V4L** dongle + antenna | rtl-sdr.com shop | $37.95 | V4 is end-of-line ($44.95 / $54.95 with antenna); beware counterfeit marketplace V4s. |
| B5 | Nordic nRF52840 Dongle (BLE sniffer, optional) | Nordic via distributors | $14 est. ($11–16) | Optional second BLE view. |
| B6 | Powered USB 3 hub, short cables | Any | $12 est. | Pi 5 USB budget with PureThermal + SDR. |
| B7 | Adafruit ATECC608 breakout (optional secure element) | adafruit.com/product/4314 | $4.95 | **Optional, off by default (D-41):** Microchip's CryptoAuthLib license restricts use to Microchip parts (not OSI-open). Key storage without it: LUKS passphrase + phone-held key. |
| B8 | Adafruit MAX98357A I2S amplifier | adafruit.com/product/3006 | $5.95 | Pi-side speaker for headless mode. |
| B9 | Small 4–8 Ω speaker, 3 W | any | $4 est. | Not worn; belt pack only. |
| B10 | USB-C data cable for phone tether (clip export, no RF) | any | $8 est. | |
| | **Tier B v2 increment** | | **≈ $401** | with Tier A v2 ≈ $862 (v1 incr. $377.93) |

**Corrections to v1 parts notes.** (1) RTL-SDR Blog V4 tuning range is now verified: 500 kHz–1.766 GHz (vendor datasheet), so it <b>cannot receive 2.4 GHz BLE/Wi-Fi</b>; it remains useful only for the optional E-10 memory-emission probe and for sub-GHz sweeps. (2) If the owner later wants IQ-level BLE/Wi-Fi fingerprints (R-3), a 2.4 GHz-capable receive-capable SDR is needed; none is in the BOM and no price was checked. (3) The Pi 5 has two 4-lane MIPI camera ports (confirmed), so the NoIR and eye cameras do not share a port.

**Software cost:** $0 (all open-source). Apple Developer Program for notarization is not used.


## 7. Wiring, power, enclosure and safety

<img src="spec_assets/wiring2.svg" style="width:100%"/>

### 7.1 Interfaces and constraints (v2)

| Interface | Detail | Constraint / check |
|---|---|---|
| I²C1 (GPIO2/3) | MLX90640 0x33, TMP117 0x48 (calibration), PA1010D GPS 0x10, DRV2605L 0x5A, ATECC608B 0x60 (optional) | 400 kHz; no address clash; cable ≤30 cm; a second I²C bus on other pins if GPS traffic disturbs thermal frames **[bench-test]**. |
| CSI-0 / CSI-1 | NoIR Camera Module 3 / OV9281 eye camera (two 4-lane MIPI ports on Pi 5) | Two adapter cables; keep ribbons away from LED wiring. |
| I²S (GPIO18/19/20 in, GPIO21 out) | MEMS mic (Tier A), MAX98357A (Tier B) | Pi 5 I²S pin map per Raspberry Pi white paper; only one I²S block at a time. **v1's GPIO18 LED gate moved.** |
| GPIO17 / GPIO27 | Glint LED gate / eye LED gate, each N-FET with 100 kΩ pull-down, 100 Ω gate resistor | Hardware series resistor limits each bank to ≤100 mA; LEDs off at boot. |
| GPIO22 / GPIO23 | Ack-panic button / mic-mute sense | Pull-ups, 30 ms debounce; mute switch cuts mic 3V3 in hardware. |
| UART GPIO14/15 or USB | MR60BHA2 radar (Tier B) | Protocol to confirm (RK-07). |
| USB 3.0 | PureThermal, RTL-SDR, phone tether | Powered hub if undervoltage (`vcgencmd get_throttled`). |
| BLE / Wi-Fi | Pi 5 onboard; phone BLE | BLE scan with bleak; AP beacons (incl. TSF) from managed-mode `iw scan`; scans windowed so the phone link stays up. |

### 7.2 Power and mounting

Budget and runtime are in Figure 3 (Tier A v2 ≈9.9 W typical/15 W peak; Tier B ≈12.4 W/19 W; ≈6.4 h / 5.1 h theoretical on a 74 Wh bank). A 5 V/3 A supply is not enough: use a certified 25 W (5 V/5 A) PD bank. <b>Head pod target ≤140 g</b> (v1: ≤120 g; the eye camera, LEDs, GPS and haptic add weight; recheck in B-11): two cameras, thermal board, four LEDs, haptic, mic, button, GPS on a short lead if it is better on the belt. Cable bundle ≤50 cm with a breakaway connector. Two-part PETG case; LED windows open (no lens, no concentrating diffuser); no cover plate over the thermal sensor; a front label "IR emitter".

### 7.3 IR LED eye-safety design rules (IEC 62471; standard cited, product not certified)

IEC 62471 classifies lamps and LEDs; for 780–1400 nm IR, the key limits at the standard 200 mm distance are: cornea/lens irradiance ≤100 W/m² for 1000 s (**Exempt**), ≤570 W/m² for 100 s (RG1), ≤3200 W/m² for 10 s (RG2). The retinal weak-visual-stimulus limit is L_IR ≤ 6000/α W·m⁻²·sr⁻¹ for 1000 s (Exempt). The standard is not itself law but is the basis of regional rules (OSRAM application note); the classification of the final product is the builder's responsibility.

**Back-of-envelope for this design (assumption: datasheet values; not independently measured).** One VSLY5850 at 100 mA gives 600 mW/sr (900 mW/sr absolute max). At 0.2 m: 0.9 / 0.2² = 22.5 W/m² per LED at the absolute-maximum rating; two LEDs ≈ 45 W/m² ≪ 100 W/m² exempt limit. With a 25% duty cycle the time-average is lower still. Vishay lists the part in its exempt table at 850 nm.

**Rules we adopt (D-03 default):**

1. Only parts that the maker lists as IEC 62471 exempt; **no lasers**; **no lenses, collimators, magnifiers or reflectors** in front of the LEDs.
2. Max 2 LEDs, fixed series resistor for ≤100 mA, software duty ≤25%, a pulse ≤10 ms, and a hardware current check in B-10.
3. Fault rule: if the software watchdog stops, the MOSFET gate pull-down turns the LEDs off; a **physical switch in series with the LED supply** lets the wearer cut them instantly.
4. Aimed at objects by default. Aiming at a consenting person's face is allowed in E-01 only at ≥0.5 m, ≤1 s at a time, with explicit consent, and never at children or pets.
5. If this ever becomes a product or is used on strangers, an accredited IEC 62471 test is required first.

**v2 addition: eye illuminator (M-01).** A second bank of two VSLY5850 at ≤100 mA, pulsed in sync with 120 fps exposures (≤50% duty, pulse ≤4 ms). Worst case at the closest allowed subject distance of 0.3 m: (0.9 W/sr at the absolute-maximum rating) / 0.3² = 10 W/m² per LED; four LEDs on at once ≈ 40 W/m², still below the 100 W/m² exempt limit (calc, datasheet values, not measured). Rules: both banks sit behind the same series switch; subject distance ≥0.3 m for eye work (≥0.5 m for glint work as in v1); LED code is random but bounded by the duty caps; the PLR visible stimulus (lab only) is a separate white LED, ≤1 s, dim start, photometer reading logged, and the visible-light (blue-light) limit of IEC 62471 must be checked against that LED's datasheet <b>[UNVERIFIED, not done]</b>. Children and pets are excluded.

### 7.4 Battery and thermal safety

- Use a commercially certified power bank (UN 38.3 listed), never a bare LiPo cell wired by hand. Inspect for swelling or damage before each session; stop use if it is hot, swollen or smells. OSHA guidance on small and wearable lithium devices applies: a failed cell near the head causes burns or fire.
- Keep the battery on the belt, away from the head and neck; no charging unattended or in the bag; a metal tin or LiPo bag for storage.
- Surface-temperature limit: rig parts at ≤45 °C measured by the thermal camera (E-09). Pi 5 gets an active cooler.


## 8. Software architecture, licenses and repo layout

**Stack.** Pi: Raspberry Pi OS 64-bit, Python 3.11+, one asyncio process, a thread per adapter, SQLite, NumPy `.npy`. Phone: Kotlin, minSdk 29, CameraX, SQLCipher, BiometricPrompt, Mapsforge, platform TTS. Shared: one JSON schema for samples, scores, events and the guard vocabulary; the golden dataset checks that Python and Kotlin scores agree within 0.02 on shared features (E-27).

**License policy (R-05, unchanged).** Allowed: MIT, BSD-2/3, Apache-2.0, ISC, PSF, MPL-2.0, LGPL (dynamic or with exception). GPL/LGPL <i>tools</i> only as separate executables. Denied: AGPL, CC-BY-NC, "research only", SSPL/BUSL, any proprietary or non-commercial library, model or dataset.

| Component (module) | Purpose | License (checked 2026-10-28 unless noted) | Verdict |
|---|---|---|---|
| bleak (M-03) | BLE scan | MIT | Allowed |
| OpenCV + Haar eye cascade (M-01, M-07) | pupil, markers | Apache-2.0 (cascade file **[UNVERIFIED]**) | Allowed |
| scikit-learn, NumPy, SciPy | fusion | BSD-3 | Allowed |
| Tink; BoringSSL inside it (M-04) | Android crypto | Apache-2.0 (BoringSSL: Apache-2.0 with OpenSSL-era BSD parts) | Allowed |
| libsodium / PyNaCl (M-04) | Pi crypto, Ed25519, constant-time compare | ISC / Apache-2.0 **[PyNaCl license from general knowledge]** | Allowed |
| noise-java (Android), `noiseprotocol` (Pi) | Noise_XX channel | MIT, MIT | Allowed |
| SQLCipher Community / sqlcipher-android | encrypted DB | BSD-3 (notice must ship in the app) | Allowed |
| AndroidX Biometric, CameraX, TFLite | gate, camera, ML | Apache-2.0 | Allowed |
| Mapsforge (M-05) | offline vector map | LGPL-3.0 with §4(d)–(e) waived for apps | Allowed |
| MapLibre Native Android | alt. map renderer | BSD-2-Clause | Allowed (alt.) |
| SpeechBrain ECAPA-TDNN weights (M-02) | speaker embedding | Apache-2.0 model card; trained on VoxCeleb (data license **[UNVERIFIED]**) | Lab use; verify data terms |
| AASIST (M-02) | replay/TTS detection | MIT code; trained on ASVspoof 2019 LA (ODC-By) | Allowed with attribution |
| Flite (M-06) | Pi TTS | BSD-style | Allowed |
| sherpa-onnx (M-06) | optional TTS | Apache-2.0; each Piper-VITS voice has its own license | Allowed only per voice |
| Piper (piper1-gpl), eSpeak NG | TTS | GPL-3.0 | <b>Denied</b> (default build) |
| Microchip CryptoAuthLib (ATECC608B) | secure element | proprietary-style, Microchip parts only | <b>Denied</b> by default (D-41) |
| Google ML Kit, Play Services, Firebase | — | proprietary | <b>Denied</b> |
| cryptsetup/LUKS, `iw`, `rtl_power` | tools | GPL | Separate executables only |

```
# asb-rig: standalone repo, Apache-2.0, standalone
LICENSE NOTICE README SECURITY.md
docs/       spec  consent_form  biometric_release  legal_checklist  eye_safety_worksheet
hardware/   pod_cad/  wiring.md  bom.csv
schema/     sample.json score.json event.json vocabulary.json   (shared by Python and Kotlin)
asb/adapters/  thermal_mlx90640 thermal_uvc camera_noir camera_eye ir_led ble_scan wifi_beacons
               mmwave_mr60 imu mic_ptt gps_i2c button_haptic sdr_probe   (+ replay_* and sim_*)
asb/features/  glint thermal_roi pupil blink glint_code rppg voice_embed rf_stats rf_skew baseline
asb/scores/    one module per score (value 0..1, confidence, health, evidence)
asb/fusion/    stack calibrate report          asb/guard/     vocabulary privacy consent retention phrases
asb/security/  keys noise_channel hashchain panic wipe          asb/store/  schema.sql db export sightings sweeps
asb/           cli ui headless/ (replay, virtual clock, stubs)
android/app/   Kotlin: adapters gate sighting map tts sweep fallback
golden/        manifest.json README   (data lives in an encrypted archive, git-ignored)
scripts/       build_all.sh verify_build.sh license_audit.sh run_experiment.py cal_thermal.py cal_align.py
tests/         guard consent hash led_dutycap schema license adapter_contract hashchain crypto headless golden
```

**Guard rules (enforced + unit-tested), extended.** (1) Regex blocklist for "robot", "android", "fake", "not human", "impostor", "synthetic person", "not alive", "dead", "replica" in any live string about a subject. (2) The output schema has no class field. (3) A human-subject session requires a consent ID. (4) Full-frame NoIR images saved only for non-person objects; humans: 64×64 glint crops, thermal arrays and derived traces only. (5) <b>No audio is saved</b>: the mic adapter yields embeddings and spoof scores in RAM; raw audio exists only for the length of one prompt and is never written. (6) <b>Voice output uses only whitelisted phrase templates.</b> (7) Refuse to run if monitor mode or a banned radio is found.

## 9. Data schema (v1 tables kept; additions below)

SQLite (phone: SQLCipher), UTC ISO-8601 plus monotonic ns. v1 tables `session`, `consent`, `device`, `calibration`, `run`, `thermal_frame`, `nir_frame`, `rf_observation`, `radar_sample`, `feature`, `signature_event`, `fusion_result`, `lab_label`, `audit_log` are unchanged (`signature_event.code` now A1–A11; `consent` gains `biometric_release`, `voice_enroll`, `eye_enroll`; `session` gains `site_code`, `gps_policy`).

| New table | Key columns | Purpose / privacy note |
|---|---|---|
| `eye_trace` | run_id, t_mono_ns, pupil_mm, blink, glint_n, glint_offset_px, glint_code_ok, quality | Derived numbers only; no eye images for humans (non-person props may keep frames). |
| `voice_event` | run_id, t_mono_ns, prompt_id, spoof_score, embed_sim (nullable), enrolled (bool) | No audio. `embed_sim` only if the speaker enrolled; embeddings are never stored for non-enrolled speakers. |
| `enrollment` | subject_code, kind (voice/eye), embedding_enc, created_utc, delete_after_utc | AES-GCM encrypted; written release required; deleted on withdrawal. |
| `emitter_baseline` | site_code, emitter_key, features_json, n_windows, built_utc | Fixed emitters only; `emitter_key` = HMAC of address or BSSID with a per-site key. |
| `emitter_drift` | emitter_key, t_utc, changed_features, windows | Source of A9; observation only. |
| `site` / `anchor` | site_code, name, anchors (marker id, pose), baseline_ids | Per-location baselines. |
| `sighting` | sighting_id, t_utc, codes, scores, verdict, lat, lon, fix_quality, crop_path, chain_idx | Phone-encrypted; verdict ∈ confirmed/benign/unresolved. |
| `sweep` | sweep_id, site_code, start/end, counts_json, new_since_last_json, outcome | Timeline source. |
| `golden_clip` | clip_id, split (train/dev/test/growth/quarantine), label, sha256, source_sighting, consent_ok, manifest_version | The frozen test split hash is recorded in the decision log. |
| `chain` | idx, h_prev, h_this, anchor_sig | Tamper-evident log; see M-04. |

**Retention (R-07 extended).** 30 days default for sessions, traces, sightings and sweeps unless the owner marks a sighting "keep"; enrollments are deleted on withdrawal or at the session-set end; golden clips from volunteers contain derived features only and are deleted (manifest version bump) on withdrawal; nightly job deletes expired rows and blobs and logs an `audit_log` entry; encryption keys destroyed by the wipe in M-04 make all copies unreadable.


## 10. Build and calibration procedure (for a later, approved build)

Effort estimate: three weekends for Tier A v2, one more for Tier B, one for the Android app and security. Record every result in `docs/build_log.md`.

### 10.0 Build steps (nothing done yet; stop at any failed check)

| Step | Action | Check (pass condition) |
|---|---|---|
| B-00 | **Approvals.** the owner approves budget (D-01), repo (D-02), human-subject policy (D-04). | Written OK in the decision log |
| B-01 | Order parts only from Section 5; confirm stock and total at checkout; keep receipts. | Order total ≤ approved budget |
| B-02 | Inspect parts on arrival; photograph serials; note firmware versions. | No damage; serials logged in `device` table |
| B-03 | Flash Raspberry Pi OS 64-bit to microSD; enable I²C, I²S, both cameras, SSH keys only; create the LUKS2 data volume with a typed passphrase; install `git`, Python. | Boots; `i2cdetect -y 1` runs |
| B-04 | Bench-wire the MLX90640 and TMP117 on I²C1 (≤30 cm cable). | `i2cdetect` shows 0x33 and the TMP117 address; frames read at ≥2 Hz |
| B-05 | Connect NoIR camera; capture test frames. | `rpicam-hello` or picamera2 preview works; image not frozen |
| B-06 | Build both IR LED drivers (glint GPIO17, eye GPIO27) on perfboard **with the LEDs disconnected**: verify gate pull-down and current with a resistor load. | Multimeter: 0 mA with GPIO low; ≤100 mA with GPIO high; no current at boot |
| B-07 | Connect LEDs; verify duty cap in software (`test_led_dutycap.py`) and by scope or logged timestamps. | Duty ≤25%, pulse ≤10 ms |
| B-08 | Thermal calibration (see 9.1). | Residual RMS ≤1.0 °C (MLX) at 25–45 °C |
| B-09 | NoIR ↔ thermal alignment (see 9.2). | Reprojection error ≤2 thermal pixels |
| B-10 | Power test: run a 30-min soak with all Tier A sensors; log `vcgencmd get_throttled`, battery voltage if available, surface temps. | No undervoltage flag; surface ≤45 °C; projected runtime ≥2 h |
| B-11 | Build the head pod; weigh it; strain-relieve; test breakaway connector. | Pod ≤120 g; connector releases at light tug |
| B-12 | Run the license audit: `scripts/license_audit.sh`. | No AGPL / non-commercial packages; GPL only as separate executables |
| B-13 | Run the unit tests (guard, consent, hashing, LED cap, schema, adapter contract, hash chain, crypto lint, golden replay). | All pass |
| B-14 | Tier B only: add PureThermal + Lepton, MR60BHA2, RTL-SDR; repeat B-04, B-10 for each. | Each device detected; USB power OK |
| B-15 | Dry run in an empty room (no people), 10 min, all sensors. | Zero crashes; clock skew ≤100 ms; files closed cleanly |
| B-16 | Mount the OV9281 eye camera on CSI-1 with the 25° M12 lens; focus at 0.5 m; print an artificial-pupil target (3, 4, 6 mm discs). | 120 fps capture; 4 mm disc ≥20 px at 0.5 m; pupil fit error ≤0.5 mm |
| B-17 | Wire the eye LED bank (LEDs off), then connect; log LED current for both banks, 4 LEDs on together. | Each bank ≤100 mA; combined duty caps hold; series switch cuts both |
| B-18 | Wire mic + hardware mute switch; implement push-to-talk gating. | With the switch off, 0 non-zero samples; with it on, audio only while PTT held; no file written |
| B-19 | Wire GPS (I²C 0x10) and haptic (0x5A); parse NMEA; trigger the three haptic patterns. | Addresses detected; fix or explicit "no fix"; patterns distinguishable |
| B-20 | Pair pod and phone by QR; run the Noise_XX session; force a rekey; replay and bit-flip packets. | Handshake OK; rekey ≤1,000 msgs/10 min; replays and flips rejected |
| B-21 | Create keys: LUKS2 passphrase, Keystore AES-256-GCM key (StrongBox if present), HMAC log key; rehearse crypto-erase on a <b>scratch</b> volume only. | Volume unreadable after erase; no plaintext key on disk |
| B-22 | Run `scripts/build_all.sh` on the Mac (or the Linux box for the APK). | Clean tree; APK + macOS artifact carry the same commit hash and SHA-256 list |
| B-23 | Build an offline Mapsforge map for the site region from an OSM extract; test in airplane mode. | Map renders offline; attribution visible; zero network calls |
| B-24 | Record the Phase 0 clips into golden dataset v0; write the manifest; at G0 record the frozen test-split hash. | `verify_golden` passes; hash logged |
| B-25 | Run adapter contract tests for every real, replay and sim adapter. | 100% pass; crash isolation shown |

### 10.1 Thermal calibration

1. Warm up the sensor for 10 min (thermal sensors drift while warming up).
2. Target: a flat aluminum block with matte black tape (emissivity ≈0.95 **assumption**), held at a known temperature measured by the TMP117 taped to its surface. Use three reference points: ice-water-cooled block (≈5–10 °C), room (≈22 °C), warm-water-heated block (≈37–45 °C). Never exceed 45 °C.
3. Distance 0.5 m, normal incidence. Fit a two-point linear correction per sensor; store in `calibration`.
4. Verify at one held-out temperature. Record the residual; if >1.0 °C (MLX) the rig does **not** go on to human tests.
5. Reminder: this is not fever screening. FDA guidance for thermography as a medical triage device expects ≤±0.5 °C with a blackbody reference; this rig makes no such claim and never reports body temperature as health data.

### 10.2 Alignment and timing

- Heat a printed checkerboard pattern backed with a warm pad (cutouts show as thermal contrast) and photograph it with both cameras; compute a homography with OpenCV; log the error.
- Clock: all records use `time.monotonic_ns()`; wall time from the Pi RTC with NTP when online. Max inter-sensor skew target ≤100 ms; BLE and Wi-Fi scans are windowed at 1 s and 10 s and are not expected to be aligned tighter.


## 11. Test plan, pass/fail criteria and go/no-go gates

**Pre-registration rule.** The thresholds below are frozen when the owner approves this spec. Any change after data collection starts must be logged in the decision log with the reason and **cannot be used to declare a pass retroactively**. Every experiment is run and logged even when it fails.

**Subjects and controls (v1 list plus v2 additions).** v1: (a) volunteers with written consent, **the owner first** (D-38); (b) mannequin unheated; (c) mannequin warmed to ≈33–35 °C; (d) powered toy or hobby robot; (e) silicone prop mask or glove on a stand; (f) phones, earbuds, watch; (g) hot drink, laptop, heater; (h) fan or spinning chair; (i) silent object. <b>v2 adds:</b> (j) printed face photo and a tablet playing a close-up video of a face (replay attacks); (k) a glass or acrylic craft eye / mannequin with glass eyes (prosthesis-style eye prop); (l) a loudspeaker playing a recorded and a TTS voice (voice replay attacks); (m) a volunteer wearing the silicone prop mask or half-mask with eye holes (report-only: real eyes, pulse, voice remain); (n) 6 owned fixed emitters (ESP32/nRF beacons, own AP, smart plug) for fingerprints; (o) planted objects for baselines (hand warmer, powered USB camera, powered beacon, phone in airplane mode, cardboard, mirror). Props are owned, borrowed or bought only after approval (D-01).

| ID | Experiment | Design | **Pass criterion (frozen)** |
|---|---|---|---|
| E-01 | Lens glint | 6 camera devices (2 phones, webcam, action cam, laptop cam, a pen/USB spy-style camera if available) and 6 non-camera glints (eyeglasses, watch, jewelry, pen clip, glass bottle, metal faucet); distances 0.5/1/2/3 m; angles 0/10/20/30° off axis; IR-on vs IR-off frame pairs; 3 consenting volunteers' eyes at ≥0.5 m | Camera detection ≥90% at ≤1 m and ≤10° (n ≥ 60 trials); at ≥2 m **report only**. Non-camera false candidates: report; on/off differencing must remove ≥50% of them vs a single-frame threshold. |
| E-02 | Active IR emitters | Known emitters (TV remote 940 nm, phone face-unlock, security-camera IR ring if available) vs negatives, LED off, 1 m lit and 2 m dark | Detect ≥90% of positives; false alarm ≤5% of frames on negatives |
| E-03 | Thermal accuracy | Reference block at 25/33/37/45 °C, 0.5 m; both thermal sensors | Median absolute error after calibration: MLX ≤2.0 °C (target 1.0); Lepton ≤3.0 °C; drift ≤1.0 °C over 30 min after 10 min warm-up |
| E-04 | Thermal separability | Face/hand ROI of 5 humans vs the 4 non-human controls and distractors, at 0.5/1/2 m, rooms at 20–24 °C, plus one cold-hands trial | Report ROC. **Gate G1 input:** thermal-only AUC ≥0.75 for human vs *unheated* mannequin + toy robot + object controls. Human vs *heated* mannequin is **report-only** (expected to be low). |
| E-05 | BLE / Wi-Fi scanning | Known advertisers (phone, watch, earbuds, ESP32 beacon at 0.1/1/10 s intervals) at 1/3/5/10 m; airplane-mode phone and silent object as negatives; observe MAC rotation for 30 min | Detect ≥95% of ≤1 s advertisers within 10 s at ≤5 m; **0 detections** from silent negatives; confirm identifiers rotate (expected) and report what can/can't be linked; nearest-of-3 by RSSI correct ≥70% |
| E-06 | mmWave breathing (Tier B) | Seated still humans at 0.5/1.0/1.5 m; negatives: mannequin, toy robot, oscillating fan | Breathing detected ≥80% within 15 s at ≤1 m; fan false-positive ≤20%. Heart rate is **not** a gate (literature shows weak accuracy). |
| E-07 | End-to-end fusion | ≥30 runs per class (human_volunteer, mannequin_unheated, mannequin_heated, toy_robot_powered, object_control); leave-one-subject-out CV; threshold set at human FPR ≤5% | **G1: fused AUC ≥0.80** (human vs unheated mannequin + toy robot + object); report TPR at 5% FPR; heated mannequin result reported separately; every ≥1 sensor failure logged |
| E-08 | Guard and privacy tests | Unit/integration tests | 100% pass: no banned strings in any output; no session without consent; no raw MAC stored; retention job deletes test data; full frames not saved when `contains_person=1`; no audio on disk; guard also checks voice phrases |
| E-09 | Safety and endurance | 2-h run, 25% LED duty; measure LED current; surface temps with the thermal sensor; pod weight | LED ≤100 mA; surfaces ≤45 °C; runtime ≥2 h; pod ≤140 g; no undervoltage |
| E-10 | Memory-EM probe (optional, exploratory) | RTL-SDR V4L near a known camera while lights toggle, looking for activity in the 24–1766 MHz tuning range (DDR clocks near 800–850 MHz appear in the paper) | **No gate.** Success = reproducible burst correlated with the light toggle at ≥0.5 m. Paper used a USRP B210; a cheap dongle may not work. |
| E-11 | Pupil measurement | Artificial pupil targets (3, 4, 6, 8 mm) on a mannequin face and 5 volunteers at 0.3/0.5/0.75/1.0 m; 120 fps; reference = ruler/target | **Median absolute error ≤0.5 mm at ≤0.5 m; eye-visible frames with a valid pupil ≥90%; 1 m **report-only**** |
| E-12 | Blink and saccade detection | 10 min of video per volunteer at 60 and 120 fps; stimuli at ±5° and ±10°; blinks and saccades hand-annotated; micro-saccade (&lt;1°) estimator run offline | **Blink F1 ≥0.85 at 60 fps; saccades ≥5° recall ≥0.80 at 120 fps; **micro-saccades report-only (expected: not detectable beyond noise)**** |
| E-13 | Pupil light step (lab only) | Written consent, photometer reading logged, dim start, ≤1 s step, 0.5 m; targets: volunteers, artificial pupils, glass-eye prop | **Volunteers: constriction ≥10% in ≥90% of valid trials; artificial/glass pupils ≤3%; failure rate reported (literature: up to 30%). **Not a G1 input**** |
| E-14 | Corneal glint geometry and code | random on/off code across the two eye LEDs; volunteers' eyes, glass-eye prop, camera lenses (phones, webcam), printed photo, tablet video; 0.3–1 m | **AUC ≥0.85 volunteer eyes vs {photo, tablet, camera lens, mannequin eye}; code-follow ≥95% on volunteers; glass-eye prop and masked volunteer **report-only**** |
| E-15 | Liveness stack | Volunteers (live) vs attack set {photo, tablet video, mannequin + speaker voice, TTS speaker, toy robot, heated mannequin}; families: optical/thermal, vital, eye, voice; LOSO; ≥20 runs per attack class | **Stack AUC ≥0.90 on the attack set; ≥2-family rule never alerts on a single family; masked-volunteer result **report-only**; per-family ROC reported** |
| E-16 | Voice liveness and enrollment | ≥5 volunteers × 5 sessions; enrolled ECAPA embedding vs impostor volunteers; AASIST on replay (phone, Bluetooth speaker) and TTS; fixed digit prompts; push-to-talk | **Verification EER ≤5% on volunteers (small n: report CI); spoof detection ≥80% at human false-reject ≤10%; **no audio file ever written** (disk scan); voice never alone raises an alert** |
| E-17 | RF baseline, drift, device type | 6 fixed emitters + 3 APs for 24 h baseline; then change one emitter's interval, TX power, payload or firmware; AP skew over 3 days; 12 owned devices for type labels | **Drift detected ≤5 min in ≥90% of 20 injected changes; false drift ≤1 per 24 h static; same-AP skew repeatable within 3σ and distinct APs separable; type accuracy ≥90% with 'unknown' allowed; <b>no IQ fingerprints</b> (hardware cannot)** |
| E-18 | Security tests | Automated + manual per M-04 | **100% of: AES-GCM nonce never reused (property test); canary strings absent from disk images; hash-chain verify fails on 1,000 random edits/deletes/reorders and on truncation past the anchor; Noise replay/bit-flip rejected; rekey ≤1,000 msgs/10 min; soft panic ≤1 s; hard panic leaves volume unmountable; 10 failed unlocks trigger erase; constant-time lint clean (no `==` on secrets)** |
| E-19 | Sighting log and offline map | 20 sightings outdoors and indoors; airplane mode; manifest/traffic check; DB opened without key | **GPS stamped ≥95% with a fix; indoor no-fix recorded, never guessed; DB unreadable without key; map renders offline; **0 network requests** and no INTERNET permission in the offline build; OSM attribution visible; exports rounded to 0.01°** |
| E-20 | Voice output tiers | 50 events per tier; speech start latency; barge-in over a running Attention phrase; airplane mode | **Attention start ≤1.5 s p95; Confirmed barge-in cuts speech ≤300 ms p95; ≤1 Attention per 10 s; 100% of phrases from whitelist; 0 banned words; offline voice only (no network voice)** |
| E-21 | Baselines and new-object alert | 3 rooms × 3 baseline passes; 12 planted objects and 12 unplanted control passes; anchors | **New powered emitter at an anchor flagged ≥90% within 2 min; false A10 ≤1 per room-pass on unchanged rooms; thermal blob (≥+5 °C, ≥4 px, ≤1.5 m) ≥80%; passive objects (cardboard, mirror) **report-only**** |
| E-22 | Thermal grayscale and overlay | Fresh-install and UI tests; readout vs data | **Default is grayscale in 100% of fresh installs; toggle persists; legend and 'not a medical measurement' tag always shown; displayed value equals stored value within 0.1 °C** |
| E-23 | Headless run and golden suite | `asb --headless --replay` on the golden dataset, Linux, no hardware, no network; 3 repeats | **0 failures; guard output byte-identical across repeats; float scores within 1e-6; LED stub asserts never driven; suite ≤2 min laptop, ≤10 min Pi 5; manifest verification 100%** |
| E-24 | One-commit build | `build_all.sh` on a clean Mac; again on dirty tree; Linux APK build | **Refuses dirty tree; APK and macOS artifact carry identical commit hash, SHA-256 list recorded; APK installs and passes app-gate smoke test; macOS self-test runs headless; Linux APK reported (content-equivalence, not bitwise)** |
| E-25 | Adapter contract | Contract suite for every real/replay/sim adapter; kill one adapter thread; unplug a USB device | **100% pass; others continue and the failed one is flagged; re-open ≤10 s; replay timestamps within 1 ms; queue drop counter reported** |
| E-26 | Feedback loop | 20 simulated confirmed and 20 benign sightings; attempt to inject into frozen test | **All become quarantined candidates; promotion needs review; clips with people but no consent ID rejected 100%; frozen test manifest hash unchanged 100%; withdrawal bumps manifest and removes clip** |
| E-27 | Android fallback node | ≥2 phones of different make; known cameras at ≤1 m; beacons at ≤5 m; Python-Kotlin replay parity | **Glint candidates ≥70% at ≤1 m (reported separately, lower than rig); BLE beacons ≥90% within 10 s at ≤5 m; node never alerts alone; 0 network; score parity within 0.02; ≥2 h runtime at the chosen scan duty** |
| E-28 | Sweep timeline | 5 sweeps of one room, 2 with a planted object | **'New since last sweep' shows the planted object in 100% of those sweeps and nothing in the 3 unchanged ones (≤1 spurious entry overall); chain verifies** |
| E-29 | App gate | Class 3 check on test phones; forced UI-callback bypass; lock timing; screenshot | **Auto-lock ≤60 s in background; DB stays undecryptable when the UI callback is bypassed (crypto-bound key); face unlock offered only if Class 3; FLAG_SECURE blocks screenshot; OS lockout observed after repeated failures** |

**Run protocol (identical for every trial; `scripts/run_experiment.py` enforces the order).**

1. Check consent ID (if a person is in the trial), room temperature/lux, and that calibration is valid (≤7 days old). Log battery and sensor health.
2. Warm-up: rig on for ≥10 min; empty-room baseline for 60 s (no subject).
3. Place the subject or object at the marked distance and angle (tape marks at 0.5/1/2/3 m); subject stays still for 15 s, then moves naturally for 15 s where relevant.
4. Capture: thermal 4 Hz, NoIR with LED off/on pairs (LED duty ≤25%), BLE/Wi-Fi windows, radar (Tier B). Operator does not look at the live anomaly index until the run ends (blinding).
5. Operator then enters the ground-truth class in `lab_label` (never before the run).
6. Re-run the empty-room baseline for 30 s; flag drift >1 °C.
7. Repeat in randomized order (a pre-generated schedule, not operator choice); ≥3 repeats per condition.
8. Same day: export a checksum manifest; run E-08 tests; write a one-paragraph run note, including failures.
9. <b>v2 modalities:</b> eye camera at 120 fps with the LED code only for runs with a signed biometric release; mic live only during a spoken prompt (push-to-talk); GPS logged only when a fix exists; the headless replay of the finished run must reproduce the live outputs (E-23).


**Golden dataset protocol (M-09, M-12; freezes at G0).**

1. <b>Composition at freeze:</b> ≥100 clips; ≥15 per class (human_volunteer derived traces, mannequin_unheated, mannequin_heated, toy_robot_powered, object_control, replay_attack, planted_object, benign_false_positive); every clip has `manifest.json` entry: SHA-256, label, source run, site, consent ID or "non-person", license, split.
2. <b>Splits are subject-disjoint:</b> train 50%, dev 20%, <b>frozen test 30%</b>. The frozen-test manifest hash is written to the decision log at G0 and checked at every build; changing it needs a new decision and voids earlier claims.
3. <b>Growth set:</b> new confirmed sightings (M-12) go to quarantine → review → growth (train/dev only). Test never grows silently.
4. <b>Headless regression:</b> every code change must reproduce expected outputs (E-23); a tolerance change is a logged decision.
5. <b>Privacy:</b> human clips contain derived features only; withdrawal removes the clip and bumps `manifest_version`; the archive is encrypted and kept outside git.

**Gate G0 (unchanged).** Phase 0: a plain phone camera + hand-held 850 nm LED shows a glint from ≥4 of 6 camera devices at ≤1 m; a borrowed thermal camera separates a human from an unheated mannequin at 0.5 m (else moved to B-08); the owner approves the legal checklist. <b>New at G0:</b> golden dataset v0 frozen (B-24).

**Gate G1 (v2).** Phase 2 (glasses or custom firmware) only if E-01 camera detection, E-03, E-05, E-08, <b>E-18 (security)</b> and <b>E-23 (headless)</b> pass <b>and</b> E-07 reaches AUC ≥0.80. If E-07 fails: publish the negative result and stop. If E-07 passes only against unheated proxies (expected): "we can flag unusual devices and cold objects; a determined imitation such as a heated mannequin defeats it."

**Module gates (M-gates).** Eye (M-01): E-11 and E-14. Liveness (M-02): E-15 and E-16. Fingerprint (M-03): E-17. Baseline (M-07): E-21 (RF part). Fallback (M-13): E-27. Each module whose gate fails <b>ships disabled by default</b>; its score is excluded from fusion (missing-family mask) and the failure is written up. Module gates do not block G1, except security and headless as listed.


## 12. False-positive handling and operator conduct

1. **Alert wording.** "Anomaly signature(s) observed: A3, A4. Not an identification. Common benign causes: cold hands, coat, phone." Never "robot", "fake", "not human".
2. **Threshold policy.** Operating point is chosen from human controls (FPR ≤5%). Alerts below the threshold are logged but not shown.
3. **Evidence threshold.** A single signature (e.g. A4 alone) is displayed as "FYI" only; the anomaly index needs ≥2 independent sensor families to alert.
4. **Human-first review.** The operator must see the contributing sensors; the UI does not hide uncertainty.
5. **No confrontation, no photos, no posting.** Alerts are for the operator's learning during lab tests; Phase 0–1 has no real-world targets.
6. **Hidden-camera sweep mode.** The only mode meant for real use (the owner's own premises). A1/A2 hits are "candidate camera locations", to be confirmed by physical inspection; nothing is called a camera until seen.
7. **Quality flags.** Cold start (<10 min), direct sun, reflective surfaces, subject moving >0.5 m/s, and low battery reduce confidence automatically.
8. **v2 additions.** Eye and voice signatures (A7, A8, A11) are shown only as "indicator not observed" with the benign list, never as a conclusion; prosthetic eyes, contact lenses, sunglasses, eye drops, medication, a cold and a bad mic all trigger them. Spoken alerts use whitelisted phrases; Confirmed tier needs the operator. The operator may press <b>benign</b> on any alert; those clips feed the feedback loop (M-12) as false-positive examples. A fallback phone node is advisory only.


## 13. Risk register

| ID | Risk | L | I | Mitigation | Owner |
|---|---|---|---|---|---|
| RK-01 | Misuse: tool used to label or confront real people | M | H | Guard + schema without class label; phase limits; the owner decision on any public use | the owner |
| RK-02 | IR LED eye injury | L | H | Exempt parts, no optics, hardware current limit, duty cap, consent rules (7.3) | Builder |
| RK-03 | Li-ion pack failure near head | L | H | Certified pack on belt, inspection, no unattended charge (7.4) | Builder |
| RK-04 | Power bank cannot supply 5 V/5 A or auto-shuts off | M | M | Check PD profile first; fall back to 15 W with powered hub, or bench PSU only | Builder |
| RK-05 | Part stock-outs / price jumps (Pi, MLX90640, SDR V4) | H | M | Alternatives listed; verify stock at checkout; budget +15% buffer | the owner |
| RK-06 | Thermal sensors not accurate enough for the question | H | M | Calibration, report-only thresholds for heated mannequin, honest negative result | Builder |
| RK-07 | MR60BHA2 cannot be read directly by the Pi | M | M | Try UART/ESPHome native API/USB serial; drop to Tier B-lite without radar | Builder |
| RK-08 | Legal exposure from recording people or radio use | M | H | Private test environment, written consent, passive-only RF, no jamming, no monitor mode, legal checklist | the owner |
| RK-09 | Biometric-law exposure (BIPA etc.) | L | H | No face images/templates stored; thermal arrays only; no identification | Builder |
| RK-10 | Data leak (laptop/Pi lost) | M | M | LUKS volume, hashed radio IDs, 30-day deletion, no cloud | Builder |
| RK-11 | Project drifts into surveillance product | L | H | Scope statement, decision gate G1, separate repo, explicit non-goals | the owner |
| RK-12 | Confirmation bias (tuning until it "works") | M | M | Frozen thresholds, leave-one-subject-out, negative results published in the report | Builder |
| RK-13 | License contamination (AGPL/non-commercial) | L | M | Allow/deny lists, automated audit B-12 | Builder |
| RK-14 | Halo/Mentra delivery delays or restrictions (Phase 2) | H | L | Not on critical path; spike optional | the owner |
| RK-15 | Wi-Fi/BLE scanning disrupts own connectivity | M | L | Scan windows; separate USB adapter if needed | Builder |
| RK-16 | Subject distress or false accusation during tests | L | M | Consent briefing; "we are testing sensors, not people"; right to withdraw | Operator |
| RK-17 | Eye module fails (micro-saccades not detectable; glint code fooled by glass eyes) | H | L | Documented limits; module ships disabled if E-11/E-14 fail; no G1 dependency | Builder |
| RK-18 | Biometric-law exposure for eye/voice data (BIPA, WA, TX, GDPR) | M | H | the owner-first policy, written release, derived-only data, 30-day retention, no strangers, lawyer review before widening | the owner |
| RK-19 | Voice spoofing or false rejection undermines liveness stack | H | L | Voice is low-weight, never alone; report ROC; disable if E-16 fails | Builder |
| RK-20 | Accidental hard erase or data loss | M | M | Two-step hard panic; wipe rehearsed on scratch volume only; golden archive backed up encrypted before any erase test | Builder |
| RK-21 | Lost Pi with unlocked volume or leaked phone | L | M | LUKS2 + Keystore keys, auto-lock 60 s, crypto-erase, no cloud copy | Builder |
| RK-22 | GPS log reveals the owner's home or routines | M | M | Encrypted store, 0.01° export rounding, sightings only on premises, no continuous track | the owner |
| RK-23 | Map data license mistakes (OSM tile policy, ODbL) | L | M | No tile-server downloads, attribution visible, separate layers | Builder |
| RK-24 | Dependency drift: GPL TTS or proprietary SDK creeps in | M | M | License audit in `build_all.sh`; deny-list includes Piper, eSpeak NG, ML Kit | Builder |
| RK-25 | Golden test split leaks into training | M | H | Frozen hash checked every build; growth set separate | Builder |
| RK-26 | Pin map or power budget wrong at bench time | M | L | B-10 soak, I²S/GPS bench checks (B-18, B-19), keep v1 fallback pins documented | Builder |
| RK-27 | Phone model lacks StrongBox or Class 3 biometrics | M | L | Software Keystore with credential fallback; recorded on the device sheet; face unlock disabled if not Class 3 | the owner |
| RK-28 | Free CI assumptions change (GitHub pricing, postponed self-hosted fee) | M | L | Local script is the only required path; recheck pricing before using any runner | the owner |

## 14. Legal and ethics checklist (general information, not legal advice; review before B-01)

**Radio**

- ☐ **No jamming or blocking of any signal, ever.** The FCC states it is generally illegal to operate, market, sell or import RF jammers; there are no exemptions for personal, business, school or vehicle use. The rig has no transmitter except the Pi's normal client Wi-Fi/Bluetooth and the IR LEDs.
- ☐ **Passive receive only.** Receiving public advertisements (BLE adverts, AP beacons) only. Do **not** decode or retain contents of other people's communications: the federal Wiretap Act (18 U.S.C. §2511) restricts interception; the §2511(2)(g) exception for radio communications "readily accessible to the general public" does not cover cellular or other common-carrier traffic.
- ☐ **No cellular reception.** 47 U.S.C. §302a(d) and 47 CFR §15.121 bar scanners that can receive cellular bands or be easily modified to; the RTL-SDR must not be used to listen to cellular channels, and the software will refuse such center frequencies.
- ☐ No Wi-Fi monitor mode and no data-frame capture in Phase 0–1 (D-05).

**People and privacy**

- ☐ Written, informed consent from every human subject; the form lists sensors, what is stored, retention, right to withdraw, and that the rig does **not** identify people.
- ☐ Adult volunteers only; no children, no strangers, no public places in Phase 0–1.
- ☐ No face recognition, no face templates, no stored face images. Thermal arrays at 32×24 or 160×120 are not used to identify anyone.
- ☐ <b>Audio (v2 changed):</b> the rig now has a mic. It is push-to-talk with a hardware mute switch, records <b>no ambient audio</b>, writes no audio files, and listens only to a consenting speaker reading a prompt. California, Florida, Illinois and Washington are all-party consent states for recording (recordinglaw.com, 2026); Texas is one-party. Federal law (18 U.S.C. §2511) still applies to oral communications.
- ☐ Private property: tests happen in the owner's home/office or with the owner's permission. Malls, stores and public venues are out of scope until a legal review.
- ☐ Hidden-camera sweeps limited to premises the owner controls or has permission to inspect.

**Ethics**

- ☐ Output never labels a person as a robot; only "anomaly signatures".
- ☐ People with prostheses, implants (pacemakers, insulin pumps), hearing aids, wearables and silicone facial prostheses are expected to trigger signatures; we do not test on them without voluntary, informed consent and never publish identifying details.
- ☐ No medical claims: thermal readings are not health data.
- ☐ Negative results are published in the final report.
- ☐ Any change of scope (public use, strangers, selling, or sharing the tool) needs the owner's written decision and a legal review first.

**v2: eye, voice and liveness data as sensitive biometrics (not legal advice; no lawyer consulted)**

- ☐ <b>Illinois BIPA</b> defines biometric identifiers as retina or iris scan, fingerprint, voiceprint, or scan of hand or face geometry (740 ILCS 14/10); requires notice, written release (electronic signature counts after Public Act 103-0769, effective 2024-08-02), a retention and destruction policy, and bars selling them; damages $1,000 negligent / $5,000 intentional or reckless, now one recovery per person for repeated collection by the same method (and a 7th Circuit ruling in 2026 applied that amendment retroactively). Our pupil/blink/glint traces are not iris templates and we store no iris images, but a voice <i>enrollment</i> is a voiceprint; so every enrolled volunteer signs a written biometric release regardless of state. Applies if the owner or a volunteer is in Illinois.
- ☐ <b>Texas CUBI</b> (informed consent before capturing a biometric identifier for a commercial purpose) and <b>Washington RCW 19.375</b> (voiceprints and other identifiers; notice, consent or opt-out for commercial enrollment) treat voiceprints similarly; <b>California</b> separately requires prior express written consent for voiceprint or voice-stress testing. Our use is non-commercial research on volunteers, which may fall outside some statutes; <b>[UNVERIFIED]</b> and not relied on.
- ☐ <b>GDPR Art. 9</b> (if any EU person is involved): biometric data for unique identification is special-category; a DPIA-style note is kept even for household research. We do not identify anyone, which weakens but does not remove the exposure.
- ☐ <b>Purpose limitation:</b> eye/voice data is used only for the lab liveness experiments; never for identifying strangers, never sold or shared, deleted on withdrawal.
- ☐ <b>GPS and sighting data:</b> location of the owner's premises is personal data; encrypted, rounded on export, no tracking of other people.
- ☐ <b>Anti-tamper and wipe:</b> protects the owner's own data on the owner's own device. Do not use crypto-erase or the panic gesture to destroy records that are subject to a legal hold or an investigation; if a dispute, subpoena or complaint is pending, stop wiping and ask counsel.
- ☐ <b>Hidden-camera findings:</b> a "confirmed" sighting means the operator physically found a device on premises the owner controls. Do not remove, tamper with, or publish about a device found elsewhere; contact the property owner or police as appropriate.
- ☐ <b>Open-source licenses:</b> keep SQLCipher's BSD notice and the ODC-By attribution for ASVspoof-derived models in the app's licenses screen; show "© OpenStreetMap contributors".



## 15. Decision log: settled defaults and residual items

the owner's instruction was to ask nothing and settle everything; every row below is a <b>recorded default</b> that the owner may overturn later (changes after data collection must be logged and cannot rescue a failed criterion). Only the residual table needs a human.

| ID | Topic | Settled default and reason |
|---|---|---|
| D-02 | Repo and license | New repo `asb-rig`, Apache-2.0, standalone. |
| D-03 | IR policy | Exempt-group parts, ≤2 LEDs per bank (two banks), ≤100 mA, duty caps, no optics, series switch; subject ≥0.3 m (eye) / ≥0.5 m (glint). |
| D-04 | Subjects | Household adults with a written release; no strangers, no children, private premises only. |
| D-05 | RF scope | BLE adverts + AP beacons (incl. TSF) in managed mode; no monitor mode, cellular, data frames, or jamming. |
| D-05b | Prosthesis control | Silicone prop and glass-eye prop only; no volunteer with a prosthesis for now. |
| D-06 | Halo | Not in the default build (vendor-licensed SDK portion). |
| D-07 | Glasses spike | Skip until G1. |
| D-08 | Real humanoid test | Skip; optionally watch a public demo without recording anyone. |
| D-09 | Platform | Rig + Android operator app; glasses Phase 2 only after G1. |
| D-10 | Thermal | MLX90640 primary, Lepton/UVC Tier B. |
| D-11 | Fusion | Stacked logistic regression over ≤6 family values; LOSO; human FPR ≤5%. |
| D-12 | Storage | LUKS2 (Pi), SQLCipher (phone), 30-day retention, hashed IDs, no cloud. |
| D-13 | Public or stranger use | Never in Phase 0–1. |
| D-14 | Legal review | Self-review now; a lawyer's review before any subject beyond household adults, any public use, or any sale/sharing. |
| D-15 | Eye scope | Near-range (0.3–1 m) pupil, blink, glint-code; micro-saccades report-only; light-step PLR lab-only and off by default. |
| D-16 | Eye hardware | OV9281 mono CSI, 25° M12 lens, two 850 nm LEDs pulsed in sync (Section 6). |
| D-17 | Face handling | Operator-aimed; transient eye-ROI detection in RAM; no templates; no stored face crops. |
| D-18 | Voice | Push-to-talk, hardware mute, no ambient audio, no audio files; embeddings ephemeral unless written enrollment; liveness-consistency purpose only. |
| D-19 | Liveness stack | ≥2 families; outputs "indicators not observed"; voice never alone; module ships disabled if its gate fails. |
| D-20 | Fingerprints | Behavioral BLE/AP + AP clock skew on fixed owned emitters; no IQ-level RFFI; drift = changed ≥2 features for ≥3 windows. |
| D-21 | Crypto primitives | AES-256-GCM (Keystore, files) / AES-256-XTS (LUKS2); ChaCha20-Poly1305 and X25519 in Noise; Ed25519 anchors; SHA-256, BLAKE2s; no custom crypto. |
| D-22 | Key rotation | New Noise handshake every session; Rekey ≤1,000 messages or 10 min; static keys 90 days; no double ratchet. |
| D-23 | Offline vs remote wipe | Crypto-erase; triggers: panic, 10 failed unlocks, signed wipe from the paired phone in BLE range; cloud relay OFF; dead-man OFF. |
| D-24 | Tamper-evident log | HMAC hash chain + Ed25519 anchors on the phone every 60 s or 100 records. |
| D-25 | GPS | Stored encrypted at full resolution; exports rounded to 0.01°; no continuous tracking; no fix = "no fix". |
| D-26 | Maps | Mapsforge + OSM extracts; no tile.openstreetmap.org downloads; attribution on screen. |
| D-27 | TTS | Platform TTS with an offline voice (phone), Flite (Pi); Piper and eSpeak NG excluded. |
| D-28 | Voice tiers | FYI = haptic; Attention = whitelisted phrase, 1 per 10 s; Confirmed = barge-in, operator confirmation needed. |
| D-29 | Baselines | RF-first; optical comparison only at ArUco anchors; optical A10 report-only. |
| D-30 | Thermal display | Grayscale 10–45 °C fixed scale default; color overlay is a toggle. |
| D-31 | Headless/golden | Replay adapters, virtual clock, subject-disjoint splits, frozen test hash at G0. |
| D-32 | macOS CI | Spec-only: local `build_all.sh`; no paid Actions; self-hosted free runner optional; unsigned macOS artifact. |
| D-33 | Adapter layer | Python Protocol + Kotlin interface from one JSON schema. |
| D-34 | Feedback loop | Quarantine → review → growth set; frozen test never changes. |
| D-35 | Fallback node | AOSP/Apache only; minSdk 29; advisory only; never alerts alone. |
| D-36 | Sweep timeline | SQLite/SQLCipher, hash-chained, "new since last sweep". |
| D-37 | App gate | BIOMETRIC_STRONG + device credential; crypto-bound; 60 s lock; FLAG_SECURE. |
| D-38 | Rollout order | the owner alone first, then household adults. |
| D-39 | Biometric retention | Raw eye/voice never stored; derived traces 30 days; enrollments until withdrawal or set end. |
| D-40 | GPIO map | Figure 3 (GPIO17/27 LED gates, I2S on 18–21, GPS on I²C). |
| D-41 | Secure element | Not in default build (CryptoAuthLib is not OSI-open); optional ATECC608B listed in Tier B. |
| D-42 | Phone | the owner's existing Android phone (assumed owned; not bought). |
| D-43 | Pod weight | ≤140 g. |
| D-44 | Golden composition | ≥100 clips, ≥15 per class, 50/20/30 splits. |
| D-45 | Anti-tamper scope | Protects the owner's data on the owner's device only. |

**Residual items (need the owner or a fact only the owner has)**

| ID | Item | Default until answered |
|---|---|---|
| D-01 | <b>Purchase approval.</b> Tier A v2 ≈ $461; Tier B v2 +$401; props +$50–150; Phase 2 glasses +$399–449. | Nothing is bought. Recommend Tier A v2 first, Tier B only after G0. |
| R-1 | the owner's phone model: StrongBox and Class 3 biometric support are unknown. | Software Keystore + device-credential fallback; record at B-22. |
| R-2 | Will `asb-rig` be public or private? Public repos get free hosted macOS minutes; private ones cost $0.062/min. | Private; local build only. |
| R-3 | IQ-level BLE/Wi-Fi fingerprinting would need a 2.4 GHz receive SDR (not budgeted, price unchecked). | Not planned. |
| R-4 | Where the owner and volunteers live (which biometric/recording statutes apply). | Strictest rules everywhere: written release, all-party recording consent. |
| R-5 | Optional user-owned wipe relay endpoint. | OFF. |

<div class="pb"></div>

## Appendix A. Sources (all accessed 2026-10-28)

<b>v1 sources 1–25 remain valid</b> (Halo, Mentra, Meta, Raspberry Pi, part vendors, Melexis, FLIR, Seeed, RTL-SDR, Nordic, Vishay/OSRAM/IEC 62471, FDA/AAMI, FCC, 18 U.S.C. §2511, BIPA, Eye of Sauron, bleak, OSHA, mmWave reviews); see the v1 PDF's Appendix A. New in v2 (items marked <b>(secondary)</b> are blogs, vendor pages or aggregators):

- <b>S26.</b> Eye tracking: Tobii, "Eye tracker sampling frequency" (connect.tobii.com); PMC7880983 (Tobii Pro Spectrum and microsaccades); RemoteEye, Behav. Res. Methods (doi 10.3758/s13428-019-01305-2); PMC7141092 (60 vs 120 Hz mobile saccade detection); JOV 2800208 (limits of iPad eye tracking).
- <b>S27.</b> Pupillometry: PupilScreen 2nd generation (Neurosurgery abstract, doi 10.1227/neu.0000000000001880_477); PMC10686294 (at-home smartphone pupillometry); Evaluation of two portable pupillometers (doi 10.2217/cnc-2020-0016, 30% vs 4% failures); Int J Appl Basic Med Res 14(1):23 (2024).
- <b>S28.</b> Corneal glint and eye liveness: Y-EYES (ACM, doi 10.1145/3469261.3469408); AIME (doi 10.1145/3458864.3466911); Morales et al., Introduction to Iris PAD (biometrics.eps.uam.es); PAD for iris recognition review, arXiv 1804.00194 (prosthetic eyes); Attack of mechanical replicas, IEEE TIFS (doi 10.1109/tifs.2015.2405345).
- <b>S29.</b> RF fingerprints: Evaluating Physical-Layer BLE Location Tracking (IEEE S&P 2022, UCSD); Identifying BLE devices (ACM SenSys 2021, doi 10.1145/3485730.3492880); Robust RFFI for BLE (IEEE WCNC 2025, doi 10.1109/wcnc61545.2025.10978258); TI BLE5-Stack clock accuracy guide (±50/±500 ppm); Jana and Kasera, MobiCom 2008 (doi 10.1145/1409944.1409958).
- <b>S30.</b> Voice: ASVspoof 5 (arXiv 2408.08739; Comput. Speech Lang. 2025, doi 10.1016/j.csl.2025.101825); Vulnerability issues in ASV, EURASIP J. Audio Speech Music (2024); SpeechBrain spkrec-ecapa-voxceleb (Hugging Face model card); clovaai/aasist LICENSE (MIT).
- <b>S31.</b> Android security: developer.android.com/privacy-and-security/keystore, KeyGenParameterSpec.Builder, security-key-attestation; developer.android.com/identity/sign-in/biometric-auth; source.android.com biometric and attestation pages; OWASP MASTG-KNOW-0001; Android Bluetooth permissions and Wi-Fi scanning docs; Android BLE scan limits (Silicon Labs docs and Stack Overflow **(secondary)**).
- <b>S32.</b> Crypto libraries and protocols: google/tink LICENSE (Apache-2.0); BoringSSL LICENSE; noiseprotocol.org (Noise spec); signal.org Double Ratchet specification; rweather/noise-java (MIT); sqlcipher/sqlcipher-android LICENSE (BSD-3).
- <b>S33.</b> Maps: OSM Foundation Tile Usage Policy (operations.osmfoundation.org/policies/tiles/); OSMF Licence/Attribution Guidelines and Legal FAQ; mapsforge/mapsforge COPYING (LGPL-3.0 with exceptions); maplibre-native Android LICENSE (BSD-2); OpenAndroMaps license page; organicmaps (Apache-2.0).
- <b>S34.</b> TTS: OHF-Voice/piper1-gpl (GPL-3.0); espeak-ng (GPL-3.0); k2-fsa/sherpa-onnx (Apache-2.0) and TTS APK docs; Piper voice licensing discussion (rhasspy/piper #271) **(secondary)**; Flite (BSD) **(secondary listing)**.
- <b>S35.</b> CI: GitHub Docs, "Billing and usage" and "Actions runner pricing" ($0.062/min standard macOS private repos; Linux $0.006/min; self-hosted free for now); GitHub "Pricing changes for GitHub Actions" (2026).
- <b>S36.</b> Parts: Arducam OV9281 listings (arducam.com, Amazon, RobotShop) **(secondary)**; Adafruit products 4415 (PA1010D), 746, 4279, 3421 (SPH0645), 3006 (MAX98357A), 2305 (DRV2605L), 4314 (ATECC608); Addicore NEO-M8N; Pimoroni Pi 5 camera cables; RTL-SDR Blog V4 datasheet (500 kHz–1.766 GHz); Raspberry Pi 5 product brief and I2S white paper (RP-009699); Microchip CryptoAuthLib license.txt.
- <b>S37.</b> Law: Illinois PA 103-0769 (ilga.gov); ABA Business Law Today and Sidley (7th Cir. 2026 retroactivity) **(secondary)**; recordinglaw.com state recording and biometric pages **(secondary)**; Justia 50-state survey **(secondary)**; Chapter 19.375 RCW (app.leg.wa.gov).

## Appendix B. Still unverified or deliberately not done

- <b>Everything v1 listed</b> (stock, "est." prices, PureThermal contents, MR60BHA2 on a Pi, Mentra stock/IR, Halo details, FCC interception guide text, state hidden-camera laws, IR-LED measurements) still applies.
- <b>New:</b> price and part of the M12 25° lens, second Pi 5 camera cable, LRA motor, LED/driver parts, speaker, USB tether, buttons; OV9281 stock (listing only); I²S mic driver quirks on Pi 5; GPS on I²C alongside thermal at 400 kHz.
- Licenses read from search summaries, not from the repos' files: Haar eye cascade, PyNaCl, `noiseprotocol` (Python), SpeechBrain/AASIST <i>training-data</i> terms (VoxCeleb), Mapsforge map-file terms, Flite voices, CHROM/POS rPPG patent status.
- Photobiological (blue-light) limit for the visible PLR stimulus LED: not calculated.
- All pass thresholds in E-11…E-29 are my proposals, not published benchmarks. Eye, voice and liveness performance against a real humanoid is <b>unknown</b>; no study covers it.
- Railway as a Linux build host: not priced or tested. Apple Developer Program fee: not checked.
- State biometric statutes beyond IL, TX, WA, CA were not surveyed; nothing here is legal advice.


