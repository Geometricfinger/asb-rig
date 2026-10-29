# oiris.dashboard
Stdlib HTTP server on 127.0.0.1 with zones D1–D6 from the C6 map and `/api/latest` JSON. Strict CSP, no external assets. Replace freely; it only reads C3/C4 data.

`/face` (face.py): M-16 review page. Present only when M-16 is on and opted in; otherwise shows the off notice and the enrollment guide. All changes are token-protected POSTs; disable requires typing WIPE and reports the verified wipe.
