# oiris.features — signal processing
Pure functions (NumPy only): `optical` (A1/A2), `thermal` (A3 + M-08 rendering), `eye` (M-01, hypothesis), `vital` (rPPG POS, band SNR), `rf` (M-03), `baseline` (M-07). **Inputs**: arrays. **Outputs**: numbers/dicts. **Depends on**: numpy. No I/O, no state except the drift detector. Add new functions with a synthetic-signal test.

`eye_roi.py`: live eye ROI finding (dark pupil + LED-following glint, or face landmarks) and `EyeTracker`, which produces the `eye` sample from LED-coded NIR frame pairs (ADR-0051).
