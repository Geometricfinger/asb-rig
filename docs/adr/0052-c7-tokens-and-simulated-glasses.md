# ADR-0052: C7 design tokens v0.1 and a simulated glasses renderer

- Status: Accepted (DEFAULT values; Design review may refine within Module Map 6.1)
- Date: 2026-10-29

## Context
C7 tokens and the G-zone glasses display were "not started": Phase 2 hardware waits on gate G1, and no Design output existed.

## Decision
Ship C7 v0.1 (`oiris/ui/design_tokens.json`) as the [DEFAULT] values allowed by Module Map 6.1, with a validator that rejects any token set breaking those rules, and a hardware-free SVG renderer for G1–G6 on the C7 canvas. Alert colours use the Okabe-Ito colour-vision-safe hues; colour is redundant to shape + word. No font, icon set or other third-party asset is bundled.

## Consequences
The renderer is a simulation; real-display limits (brightness, words per line, refresh budget) are validated in Phase 2 on hardware. Any token change must still pass `tokens.validate`.
