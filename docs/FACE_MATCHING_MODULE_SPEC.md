# O Iris — Face-Matching Module Spec (future add-on)

- **Status:** Built (v0.2.0-dev, 2026-10-29) in `oiris/modules/face_match/`; see §18 for what is real and what is not. Headless-tested only; never run on real hardware or real faces.
- **Proposed module ID:** M-16 `face_match` (optional, outside the M-01…M-15 core set)
- **Date:** 2026-10-29
- **Fits:** ports & adapters (`docs/ARCHITECTURE.md`), plugin registration (`docs/EXTENDING.md`), `ETHICS.md`, ADR-0013, ADR-0017, ADR-0021/0022, ADR-0024, ADR-0033, ADR-0039
- *Legal notes in this document are general pointers, not legal advice.*

---

## 1. Purpose and principle

**The module is neutral; the user decides.** It is a tool that can recognise people the user has chosen to enroll, and count (not identify) faces it doesn't know. It never decides anything about a person, never acts on a match, and never leaves the device unless the user explicitly sends something off it.

It ships **off**, isn't even loaded unless switched on, and can be turned off or removed at any time — and turning it off destroys every stored face template.

## 2. Project records (amended 2026-10-29, owner sign-off)

These records conflicted with this add-on and have been updated:

| Old rule | Now |
|---|---|
| ADR-0017 (D-17): no face templates | Superseded by **ADR-0049**: templates only for enrolled people, encrypted on device; disabling verifiably wipes all face data; no stranger templates. |
| ETHICS.md: face recognition out of scope | Now in scope only as opt-in M-16 under the rules in this spec. |
| ADR-0013 (D-13): no public or stranger use in Phase 0–1 | Superseded by **ADR-0050**: personal mode allowed now; research mode unlocks on the user's own explicit opt-in alone, with no legal review or external gate. |

Done with the M-16 build: `oiris/guard/privacy.py` now allows `face_template` only from source `M-16` while it is enabled and opted in; every other source, and any stranger face data (`face_embedding`, `face_id`, `face_hash`, `face_crop`), is refused. The build spec v2 non-goals now carve out M-16 as an optional add-on (amendment note in `docs/spec/ASB-Build-Spec-v2.md`).

## 3. Key design decision — what research mode can and cannot do

**The request:** a review log that says "we saw this person at Trader Joe's, ten times".

**The honest problem:** to know that the face seen today is *the same* unknown face seen last Tuesday, the system has to keep something that represents that face between sightings — a template or embedding. That *is* biometric data, by definition in BIPA, GDPR Art. 9 and the others. "Per-person frequency for strangers without biometric templates" is impossible; any scheme that links encounters (hashes of embeddings, clustered IDs, "fuzzy" fingerprints) is still a biometric identifier under these laws and is still a tracking tool.

**Decision:**
1. **Research mode = anonymous, unlinked counts only.** It records "unrecognized faces seen: N at place P on date D (time bucket T)". Each face is processed in RAM, counted, and its embedding discarded within the same frame cycle. There is **no cross-encounter linking** — the system cannot tell whether 10 counts were one person or ten.
2. **"Seen at Trader Joe's, ten times" exists only for enrolled people in personal mode**, because only they have a stored template, and only they (ideally) agreed.
3. No setting, plugin or flag can enable stranger linking. The schema has no column that could hold it (§8), and a test proves it (§12).

## 4. Guardrails kept from the project (cannot be switched off)

- **Never label a person a robot** (or android, fake, "not human"). All M-16 output passes `check_text()` / `Vocabulary.check()`. Matches are reported as a name the user chose or "unrecognized", nothing else.
- **Biometric data stays on device.** Templates never leave the device; no sync, no backup to cloud, no export (§9).
- **No full frames, no stored crops** (64×64 crop rule stays; M-16 stores zero images).
- **Phase 0–1: private, consenting use only**, except M-16 research mode on the user's own opt-in (ADR-0050).
- **Never act on a detection** (§6).
- **Retention defaults** follow ADR-0039.

## 5. Turning it on — opt-in and warning

### 5.1 Off by default
- Config flag `"M-16": false` by default and listed in `DEFAULT_OFF`. When false, the plugin is **not imported** and its port is not registered (zero code loaded, zero camera frames routed to it).
- Not in `LOCKED_ON`; it can always be switched off.

### 5.2 Opt-in steps
1. User sets the flag or taps "Enable face matching" in the app.
2. The device shows the warning below, on the phone (P-zone), full text, no skip.
3. User must type a confirmation phrase (e.g. `I UNDERSTAND`) — not just tap.
4. User picks the mode(s). Research mode is available as soon as the user opts in. Jurisdiction information (§10) is shown as a warning only and never blocks it.
5. An **opt-in record** is appended to the tamper-evident log (ADR-0024): time, mode, warning text version, device ID. Every later enable/disable/mode change is logged the same way.

### 5.3 Warning text (plain language, v1)
> **Face matching is about to be turned on.**
> - In **personal mode**, this device will store a mathematical map of each face you enroll (a "face template"). That is biometric data. It stays on this device, encrypted.
> - The camera will look at **every face it sees**, including people who **never agreed** to be scanned and don't know this device exists. Personal mode only matches people you enrolled; everyone else is ignored or, in research mode, counted anonymously.
> - In **research mode**, it keeps a count of unknown faces by time and place. It does not store their faces and cannot tell if it saw the same stranger twice.
> - Laws in some places (for example Illinois, Texas, Washington, the EU/UK, California) restrict collecting face data, sometimes with heavy penalties. Biometric and recording laws vary by place, and compliance is your responsibility. Whether to use this, and how, is your decision and your risk.
> - It will never alert you, block anyone, or follow anyone. It only keeps a log you can review and delete.
> - You can turn it off any time. Turning it off permanently deletes all stored face templates.

## 6. What it does — and never does

**Does:** detects faces in frames already on the sensor bus; compares to enrolled templates (personal mode); counts unknowns (research mode); writes log entries; shows them in a review screen on request.

**Never does:**
- No alerts, sounds, voice announcements, glasses overlays or vibration on a match. (No M-06 phrases exist for M-16; the phrase whitelist gets none.)
- No blocking, no automation hooks, no triggers to other modules, no event (C3) emission.
- No following, tracking routes, or linking with GPS trails of a person beyond the single place field of a log entry.
- No live "who's that" lookup during an encounter; results are viewable only in the review log afterwards. *(Open question Q1: whether a delayed review is the only access, or a "last 5 minutes" view is acceptable.)*

## 7. Modes in detail

### 7.1 Personal mode
- Matches only people in the user's enrollment list (contacts, friends, family).
- **Enrollment:** guided multi-angle capture, see §7.3. Images are discarded immediately; only the template is stored.
- **Enrollment consent (recommended, on by default):** a consent record via `oiris/guard/consent.py` with scope `face_enrollment` — who agreed, when, how (signed / verbal noted by user), and an optional end date. For a minor, a parent or guardian enrolls them and the guardian's agreement is recorded. The user can override with "no consent recorded", which is logged and shown with a warning badge on that person. *(Q2: should consent be mandatory rather than recommended in BIPA-type jurisdictions? Recommended: yes, mandatory there.)*
- **Withdrawal:** removing a person deletes their template and, by default, their encounter history.
- Match threshold conservative (prefer missing a match over a false match); below-threshold faces are treated as unrecognized.

### 7.2 Research mode
- Each unrecognized face → increment a counter keyed by (place bucket, date, time bucket). Nothing else.
- Embedding exists only in RAM for the current frame and is zeroed after comparison.
- No per-face IDs, no hashes, no cluster labels, no thumbnails.
- If personal mode is also on, enrolled people are matched first and are **not** counted as unrecognized.

### 7.3 Enrollment flow (memorization port)

**No cap.** There is no limit on how many people can be enrolled, or on how many people can be enrolled in one session. The user enrolls as many people as they want, for example a family's kids, a friend group or a whole team. No number in this spec, its schema, its config or its tests acts as a maximum. In practice each template is small (a few kilobytes), so device storage is very unlikely to matter. If storage did ever run low, that would be an ordinary disk-full error, not an enrollment rule.

**Before enrolling.** Enrollment needs the same opt-in as the module (§5): M-16 must be on, with the warning acknowledged and the opt-in record logged. If it isn't, the enrollment screen is locked and links to the opt-in.

**Steps, per person:**
1. **Name.** The user gives the person a name or label ("Mom", "Alex", "Coach"). It is stored sealed and shown in the review log.
2. **Consent.** Record the person's agreement (recommended; required by jurisdiction profile where the law demands it). For a minor, a parent or guardian enrolls them and the guardian's agreement is recorded.
3. **Guided capture.** 5–10 varied shots: **front, left, right, up, down**, plus extras if the user wants. Varied angles let the template still match when the head is turned. The phone app shows a five-angle guide with each angle ticked off as it's captured. The glasses display shows a minimal version: the next angle needed and a tick.
4. **Per-shot quality checks**, run before a shot is accepted. A shot that fails is rejected with a plain reason ("too blurry, hold still", "too dark", "move closer", "only one face in frame, please"):
   - blur (sharpness above a per-model threshold)
   - light (exposure not too dark or blown out)
   - face size (face large enough in the frame)
   - exactly one face in frame (so no one else's face ends up in this person's template)
   - angle matches the one requested
5. **Template complete.** When every angle is covered and at least 5 shots pass, the app shows "Template complete for *name*". The embeddings are combined into that person's template, sealed and stored. All images and individual embeddings are wiped from RAM.

**Multi-person sessions.** One session can enroll any number of people one after another. Each person has their own `person_id`, their own template row and their own capture buffer, and the buffer is cleared when the next person starts. Templates are never mixed or averaged across people. A shot showing more than one face is always rejected.

**Review log.** Each enrolled person has a history in the review log, under the name the user gave them ("Alex — seen at Trader Joe's, 10 times in the last 30 days"). Any single entry can be deleted.

**Re-enrollment.** The module watches each person's match confidence. If the rolling median of their last 20 match confidences drops by 0.1 or more below their median for the first week after enrollment (configurable), or falls below the match threshold plus a small margin, the review log marks the person "recognition getting weaker — re-enroll?". The module never re-captures on its own. Re-enrolling runs the same guided capture and *replaces* the old template (the old one is crypto-erased). Encounter history is kept.

**Deleting a person** crypto-erases their template, deletes their row and (by default) their encounter history, then checks that the template can no longer be decrypted or found, and logs "1 template destroyed, verified" with no name.

**EnrollmentPort**, a companion to `FaceMatchPort`, implemented by the module core and used by the phone app and glasses UI. Adapters still only compute:
```python
class EnrollmentPort(Protocol):
    def start_session(self) -> SessionId: ...                  # requires M-16 opt-in
    def add_person(self, s: SessionId, label: str, consent_id: str | None,
                   guardian: bool = False) -> PersonId: ...
    def needed_angles(self, p: PersonId) -> set[Angle]: ...    # FRONT, LEFT, RIGHT, UP, DOWN
    def submit_shot(self, p: PersonId, frame, angle: Angle) -> ShotResult: ...
                                                               # ok | reason (blur/light/size/faces/angle)
    def finish_person(self, p: PersonId) -> TemplateStatus: ...# "complete" or what is missing
    def end_session(self, s: SessionId) -> None: ...           # clears every capture buffer
    def reenroll(self, p: PersonId) -> SessionId: ...
    def delete_person(self, p: PersonId) -> WipeReport: ...    # verified wipe
```
None of these methods take or return a count limit, and there is no "enrollment full" result.

## 8. Data schema (C4-style, new migrations only)

Added by appending to `oiris/store/migrations.py`; bodies sealed with the existing AEAD (`oiris/security/aead.py`) like the sighting log.

**`fm_enrolled`** — one row per enrolled person
| Field | Type | Notes |
|---|---|---|
| person_id | random UUID | not derived from the face |
| display_name | sealed text | user-chosen label |
| template | sealed blob | embedding; encrypted with subkey `face-template` |
| model_id / model_version | text | template only valid with this model |
| consent_id | text / null | link to consent record |
| guardian_enrolled | bool | true if a parent/guardian enrolled a minor |
| shot_count, angles_covered | int, text | capture summary only; no images |
| baseline_confidence | float | median confidence in the first week, used for re-enrollment |
| enrolled_at, expires_at | timestamps | expiry per ADR-0039 ("until withdrawal or set end") |

**`fm_encounter`** — personal-mode sightings of enrolled people
| Field | Notes |
|---|---|
| entry_id | random UUID |
| person_id | FK → fm_enrolled (cascade delete) |
| seen_at | timestamp, rounded to minute |
| place | user-named place ("Trader Joe's") or GPS rounded to 0.01° (existing policy) |
| confidence | [0,1] |
| expires_at | default seen_at + 30 days |

**`fm_unrecognized_count`** — research mode
| Field | Notes |
|---|---|
| place, date, time_bucket (e.g. hour) | |
| count | integer |
| expires_at | default + 30 days |

There is deliberately **no** template, embedding, hash or face ID column in `fm_unrecognized_count`.

The review log ("Alex — seen at Trader Joe's, 10 times in the last 30 days") is a query over `fm_encounter`.

## 9. Storage, encryption and retention

- **Local only.** All tables live in the existing encrypted store in `data_dir`.
- **Encryption:** reuse the project scheme — master key from `oiris/security/keys.py`, a dedicated subkey `keys.subkey("face-template")` for templates and `keys.subkey("face-log")` for logs, sealed with the existing AEAD. Key rotation follows ADR-0022; secure element per ADR-0041 when present.
- **No cloud upload by default.** There is no upload code path for templates at all. Encounter logs/counts may be exported only by an explicit, per-export user action, with GPS rounding applied; templates are never exportable. No cross-device sync by default.
- **Retention:** encounter logs and counts auto-expire after **30 days** (configurable 1–365; existing nightly purge in `oiris/guard/retention.py`). Templates kept until withdrawal or the set end date. A jurisdiction profile may force shorter limits.

## 10. Legal pointers and jurisdiction warnings (not legal advice)

**Principle:** every feature with questionable legality is an on/off switch. The user makes the determination, the risk is the user's own, and the feature is an option the user may use as they choose. Research mode unlocks on the user's own opt-in alone; nothing below blocks it.

| Law | Why it matters | Default behaviour |
|---|---|---|
| **Illinois BIPA** | written release before collecting face geometry; public retention schedule; private right of action with statutory damages | consent mandatory for enrollment; research-mode warning |
| **Texas CUBI** (Bus. & Com. Code §503.001) | notice and consent before capturing identifiers for a commercial purpose; destruction deadline | consent mandatory; short retention |
| **Washington RCW 19.375** (and My Health My Data Act) | notice/consent for enrolling identifiers | consent mandatory |
| **EU/UK GDPR Art. 9** | biometric data for identification is special-category; household exemption is narrow and may not cover public-space scanning | research-mode warning; personal mode warns strongly |
| **California CCPA/CPRA** | biometric = sensitive personal info; mainly applies to businesses | warning shown |

- **Jurisdiction profile (informational):** user sets a jurisdiction profile at opt-in (or it's inferred from coarse location with user confirmation). Restrictive profiles show stronger warnings and force consent records for enrollment; they never block research mode. Unknown jurisdiction → strictest profile ("where unsure, follow the strictest", per ETHICS.md).

## 11. Threat and misuse model

| Threat | Mitigations |
|---|---|
| **Stalking** — enrolling an ex or stranger and logging where they go | No alerts or live lookup (§6); enrollment requires capture in-app; consent badge; opt-in audit trail; per-person history visible and deletable; no route/trail views |
| **Covert stranger tracking via research mode** | No stranger templates or linking, enforced by schema and test |
| **Data theft / device seizure** | AEAD at rest; crypto-erase (`crypto_erase`) and existing panic/remote-wipe (ADR-0023); no plaintext templates on disk |
| **Exfiltration by a plugin or bad update** | Templates readable only via the port; no export API; plugin licence and port-version checks at registration |
| **Someone else enabling it on the user's device** | Opt-in needs unlock + typed phrase; every change in tamper-evident log, shown on next app open |
| **Misidentification harm** | Conservative threshold; no action on matches; results framed as "possible match", never a label about what a person is |
| **Scope creep** (alerts, cloud, sharing added later) | Any such change needs a new ADR with owner sign-off and contract tests that currently forbid it |

## 12. Interface — `FaceMatchPort`

New port in the registry, key `("face_match", name)`, port version `1.0`, defined once in `schema/face_match.json` → Python Protocol + Kotlin interface (ADR-0033).

```python
class FaceMatchPort(Protocol):
    name: str
    license: str            # must be on the permissive allow-list
    model_id: str
    model_version: str

    def open(self, cfg: dict) -> None: ...
    def close(self) -> None: ...
    def health(self) -> tuple[Health, str]: ...

    def detect(self, frame, timeout_s: float) -> list[FaceBox]: ...
    def embed(self, frame, box: FaceBox) -> Embedding: ...   # RAM only
    def compare(self, e: Embedding, templates: Sequence[Template]) -> MatchResult | None: ...
```

- The **adapter** only computes; it never stores, logs or exports. The M-16 **module core** owns storage, modes, retention and wipe, so a third-party adapter can't bypass the rules.
- `Embedding` objects are zeroed after use; research mode calls `detect` + `embed` + `compare` only against enrolled templates and then drops the embedding.
- Wrapped like every adapter: calls run in a helper thread with timeout, exceptions → DEGRADED, N failures → circuit breaker opens (existing `adapter_timeout_s`, `breaker_threshold`, `breaker_cooldown_s`). M-16 failing never affects other modules or fusion.
- Plugin registration via the `oiris.plugins` entry-point group; rejected on wrong major version or disallowed licence.

## 13. Configuration flags

```json
{
  "flags": {"M-16": false},
  "face_match": {
    "modes": [],                       // "personal", "research"
    "jurisdiction": "strictest",
    "require_enrollment_consent": true,
    "match_threshold": 0.8,            // conservative; per-model calibrated
    "encounter_retention_days": 30,    // 1..365
    "place_source": "named",           // "named" | "gps_0.01"
    "time_bucket_minutes": 60,
    "allow_log_export": false,
    "enroll_min_shots": 5,             // per person; 5..10 recommended
    "enroll_max_shots": 10,            // per person, not a limit on people
    "enroll_required_angles": ["front","left","right","up","down"],
    "reenroll_confidence_drop": 0.1,
    "reenroll_window_matches": 20,
    "adapter": "<name>"
  }
}
```
There is deliberately no setting for the number of enrolled people or people per session.

Validation follows existing config rules: bad values rejected at startup with a clear message; `research` in `modes` accepted once the M-16 opt-in is recorded; jurisdiction never blocks it.

## 14. Disable, remove and wipe procedure

Disabling (flag off, app toggle, or `oiris face-match disable`) runs:
1. Stop the module; unregister the port; stop routing frames.
2. **Crypto-erase templates:** destroy the `face-template` subkey material (rotate master/subkey so old ciphertext is unreadable), then delete all `fm_enrolled` rows and `VACUUM`. Overwrite is best-effort on flash; security comes from key destruction (same approach as `KeyStore.crypto_erase`).
3. Encounter logs and counts: user chooses keep (until normal expiry) or delete now. Default: **delete now**.
4. Append a "disabled + wiped" record to the tamper-evident log (record contains counts only, no names).
5. Verify (step 12 below) and show the user "N templates destroyed, verified".

Removing the plugin package runs the same wipe first. Re-enabling starts from zero: new opt-in, new enrollments.

## 15. Test plan

| Test | Proves |
|---|---|
| Contract tests (`tests/test_contracts.py` parametrised over FaceMatchPort adapters) | interface, licence field, health states, RAM-only embeddings |
| Default-off test | with default config, `oiris.modules.face_match` is not imported and no port registered |
| Opt-in test | can't enable without typed confirmation; opt-in record written to hash chain |
| Fault injection (`test_fault_injection.py`) | adapter raise / hang / garbage → DEGRADED/FAILED, breaker opens, other modules unaffected |
| **No-templates-in-research-mode test** | run research mode on synthetic faces; scan DB, files in `data_dir`, temp dirs and process-written bytes: no embedding-shaped data, no face IDs, schema has no such column; counts can't distinguish 1 face×10 from 10 faces×1 |
| No-action test | a match produces no C3 event, no TTS call, no glasses/phone notification |
| Vocabulary test | all M-16 strings pass `check_text()` |
| Retention test | entries past expiry purged by nightly job |
| Per-entry delete test | deleting one review entry removes exactly that row; deleting a person cascades |
| **Wipe-verification test** | after disable: no `fm_enrolled` rows, old ciphertext undecryptable with any available key, log record present |
| **No-enrollment-cap test** | enroll a large generated set of synthetic people (several hundred), in one session and across sessions; every one succeeds and matches its own template; code and config contain no max-people constant |
| Enrollment opt-in test | `start_session` refuses while M-16 is off or not opted in |
| Guided-capture test | missing angles reported; template "complete" only after every angle plus at least 5 good shots |
| Shot quality test | blurred, dark, too-small, two-face and wrong-angle shots each rejected with the right reason |
| Template isolation test | in a multi-person session, each template is built only from that person's shots; capture buffer is empty after each person and session |
| Re-enrollment test | simulated confidence drop raises the flag; re-enroll replaces and crypto-erases the old template |
| Person-delete wipe test | after `delete_person`, that template is undecryptable and absent; other people are untouched |
| Guardian test | minor enrollment records guardian consent |
| Export test | no API returns templates; log export blocked unless flag + explicit action |
| Jurisdiction test | strict profiles show stronger warnings and force enrollment consent, but research mode still unlocks on opt-in |

Test faces are synthetic or from consenting, permissively licensed datasets only.

## 16. Model licence requirement

- Detector and embedding weights **must be commercial-use OK under a permissive licence** (MIT, Apache-2.0, BSD). No non-commercial or research-only weights — this rules out many InsightFace model packs, whose weights are non-commercial even though the code is MIT. No GPL-family code in the adapter.
- Licence of **weights and training data terms** checked separately from code, recorded in the C9 manifest (`license`, `data_tier`, `sha256`).
- **Chosen backend (`opencv_zoo`):** OpenCV Zoo YuNet detector (`face_detection_yunet_2023mar.onnx`, LICENSE file: MIT) + SFace embedder (`face_recognition_sface_2021dec.onnx`, LICENSE file: Apache-2.0), run through OpenCV (Apache-2.0). Licence files checked 2026-10-29 at github.com/opencv/opencv_zoo. Weights are **not** in the repo; `oiris face-match fetch-models` downloads them on explicit request and pins SHA-256. **Open item:** the SFace paper trains on public face datasets (CASIA-WebFace / VGGFace2 / MS1M family) whose own terms are research-oriented; the weights' Apache-2.0 grant does not settle the training-data terms. Recorded as `data_tier: unverified` in THIRD_PARTY.md; the owner decides before relying on it commercially.
- **Test backend (`test_deterministic`):** dependency-free, works only on synthetic frames, labelled TEST-ONLY, never registered, refused unless `allow_test_backend` (tests only).

## 17. Open questions

1. Is a live or "last few minutes" view ever acceptable, or review-log only?
2. Should enrollment consent be mandatory everywhere, not just strict jurisdictions?
3. Place granularity: user-named places only, or rounded GPS too?
4. Research-mode time bucket: is hourly too fine in quiet places (one person per hour ≈ identifying)? Consider a minimum-count threshold before storing (e.g. store only if N ≥ 3).
5. Which licence-verified permissive models perform well enough on-device?
6. Does M-16 run on the glasses, the phone (ADR-0042), or both?
7. Who signs off the superseding ADRs for D-17, D-13 and ETHICS.md?
8. Should the opt-in expire and require re-confirmation (e.g. every 90 days)?

## 18. Build status (2026-10-29)

| Part | State |
|---|---|
| Opt-in (typed `I UNDERSTAND`, full warning v1, jurisdiction note, tamper-evident record), mode changes, disable | **Real**, tested (`optin.py`, `DbChain` / `HashChain`) |
| Default off, not imported, no port instance while off | **Real**, tested in a clean subprocess (`face_match_gate.py`) |
| EnrollmentPort: sessions, unlimited people, per-person buffers, 5 angles, 5–10 shots, quality checks (faces/size/light/blur/angle), consent + guardian, re-enroll, verified person delete | **Real**, tested (`core.py`, `quality.py`) |
| Personal matching, research counts (no face data, no linking), review log, per-entry delete, retention, export block | **Real**, tested |
| Encrypted storage (face key file + per-person DEKs + AEAD) and verified crypto-erase on disable | **Real**, tested |
| Fault isolation (thread + timeout + breaker) | **Real**, tested with raise / hang / garbage / SystemExit backends |
| Guided capture UI | **CLI** (`oiris face-match enroll`, ticks per angle, file or camera input). Android phone screen and glasses mini-guide: **not built** |
| Real backend (`opencv_zoo`) | Code real; CI test skips without weights; detection/pose geometry checked locally with the real weights; never run on a real face in tests |
| Dashboard review page | **Not built** (CLI `review` / `delete-entry` / `delete-person` only) |

Open questions in §17 are unchanged; the build takes the conservative side (review log only, no live view; consent required by default; hourly buckets).
