# ADR-0051: Live eye ROI by dark-pupil + glint (numpy), landmarks when available

- Status: Accepted
- Date: 2026-10-29

## Context
STATUS listed eye ROI finding on live frames as a stub (the plan named Haar cascades). The
`opencv-python-headless` 5.x wheels no longer bundle the Haar cascade XML files, and pulling them
from another source adds a third-party data file to track. Under 850 nm illumination the pupil is
the darkest compact round blob and the cornea returns a small glint only on LED-on frames, which is
exactly the signal M-01 already scores.

## Decision
`oiris/features/eye_roi.py` finds eye ROIs with a dependency-free dark-pupil + glint detector, or
from face landmarks (YuNet points 0/1, MIT) when a detector already ran. `EyeTracker` turns the
LED-coded on/off pairs into the existing `eye` sample; `NirEyeAdapter` (`camera_noir_eye`) wires it
to the Pi NoIR camera with a fresh random LED code from `secrets`. No new third-party code or data.
ROIs are transient: never stored, never matched, never an identity.

## Consequences
Tested on synthetic NIR frames only; thresholds need tuning on the real camera (hardware-required).
