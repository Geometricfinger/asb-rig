# oiris.ui
- `design_tokens.json` (C7 v0.1, DEFAULT proposal per Module Map 6.1) + `tokens.py`: loader that enforces the rules (WCAG contrast, three levels with distinct shape + "signal" word, reserved alert colours, <=6 type sizes, glasses one size up, no flashing, 48 dp targets).
- `glasses.py`: simulated glasses display (SVG on the C7 canvas): G1 level strip, G2 alert line (<=6 words, vocabulary guard, hidden while moving), G3 thermal window (grayscale default, colour toggle avoiding alert colours), G4 health dots, G5 voice tier, G6 lock/panic. Layout check keeps the centre clear. `oiris glasses-sim --scenario camera_lens --out g.svg`.
Real-display validation (brightness, legibility, refresh budget) is Phase 2 hardware work.

M-16 enrollment mini-guide: `glasses.guide_from_port(port, person_id, last_shot)` + `render_enroll_guide()` show only the next angle needed (arrow + ≤6 words), a tick when a shot is accepted, a plain reason when rejected, and five progress dots in G4. No names, no image, nothing on a match.
