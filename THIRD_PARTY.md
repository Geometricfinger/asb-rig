# Third-party components

Policy (R-05): allowed MIT, BSD-2/3, Apache-2.0, ISC, PSF, MPL-2.0; LGPL only with dynamic linking or an app exception. GPL tools only as **separate executables**, never imported. Denied: AGPL, non-commercial, "research only", SSPL/BUSL, proprietary. `scripts/license_check.py` enforces this in CI.

## Python runtime (required)
| Package | License | Use |
|---|---|---|
| numpy | BSD-3-Clause | arrays, signal processing |
| cryptography | Apache-2.0 OR BSD-3-Clause | AES-256-GCM, scrypt, X25519 |
| PyNaCl (libsodium) | Apache-2.0 (libsodium ISC) | Ed25519 anchors |
| noiseprotocol | MIT | Noise_XX channel |

## macOS app bundle (redistributed wheels, CI artifact only)
`O Iris.app` (`scripts/make_macos_app.py`) bundles the binary wheels of the required runtime above plus their dependencies: cffi (MIT), pycparser (BSD-3-Clause). numpy wheels may bundle OpenBLAS (BSD-3-Clause) and libgfortran/libquadmath (GPL-3.0 **with GCC Runtime Library Exception**, permits redistribution in any program); cryptography wheels bundle OpenSSL (Apache-2.0); PyNaCl bundles libsodium (ISC). Licence files travel inside each wheel's `.dist-info`.

## Python optional (`pip install .[hw]`)
| Package | License | Use |
|---|---|---|
| bleak | MIT | passive BLE scanning |
| pyserial | BSD-3-Clause | GPS, mmWave UART |
| opencv-python-headless | Apache-2.0 (OpenCV); wheel bundles FFmpeg under LGPL as a shared library | UVC thermal. Haar cascade files are **not used** (eye ROI is numpy dark-pupil + glint, ADR-0051) |
| adafruit-circuitpython-mlx90640 | MIT | MLX90640 thermal |
| gpiozero | BSD-3-Clause | IR LED gate |
| bless | MIT | pod-side BLE GATT server for the phone/glasses link (`oiris/link/ble.py`; untested without a radio) |
| picamera2 | BSD-2-Clause | Pi NoIR camera (Raspberry Pi OS package) |

## M-16 face models (not in the repo; downloaded only by `oiris face-match fetch-models`)
| File | Licence (file checked 2026-10-29) | SHA-256 | Data tier |
|---|---|---|---|
| opencv_zoo `face_detection_yunet_2023mar.onnx` (YuNet) | MIT (Shiqi Yu) | `8f2383e4…52fa4` | detector trained on WIDER FACE; terms unverified |
| opencv_zoo `face_recognition_sface_2021dec.onnx` (SFace) | Apache-2.0 | `0ba9fbfa…c34e79` | **unverified**: paper trains on CASIA-WebFace / VGGFace2 / MS1M-family data with research-oriented terms; owner decision before commercial reliance |

The test backend `oiris/modules/face_match/backends/test_deterministic.py` (Apache-2.0, this repo) is TEST-ONLY and uses synthetic frames. InsightFace/ArcFace model packs and FaceNet weights trained on VGGFace2/MS-Celeb are **not** used (non-commercial terms).

## Dev only
pytest (MIT), hypothesis (MPL-2.0), ruff (MIT), mypy (MIT), pip-licenses (MIT).

## Separate executables (GPL/other; invoked as subprocesses, not linked)
| Tool | License | Use |
|---|---|---|
| iw | ISC | managed-mode Wi-Fi scan (passive policy enforced) |
| rtl_power (rtl-sdr) | GPL-2.0 | receive-only E-10 probe |
| cryptsetup (LUKS2) | GPL-2.0 | Pi data volume (`scripts/pi_luks2_setup.sh` runs it as a separate executable) |
| flite | BSD-style (CMU; core BSD-like, GPL only in build tooling, not runtime; checked in the upstream COPYING 2026-10-29) | Pi/host TTS; Debian/Ubuntu package `flite` 2.2; CI installs it and runs real synthesis (M-06) |

## Android (see android/dependencies.txt)
AndroidX core/fragment/biometric/camera (incl. camera-view)/sqlite (Apache-2.0); Bouncy Castle `bcprov-jdk18on` 1.78.1 (Bouncy Castle Licence, MIT-style: X25519, ChaCha20-Poly1305, BLAKE2s for the Kotlin Noise port); SQLCipher for Android (BSD-3-Clause); Mapsforge (LGPL-3.0 with exception). Android SDK/Gradle are build-time tools only. No Google Play Services, ML Kit or Firebase.

## Algorithms and data
- rPPG: own implementation of the published POS method (Wang et al., 2017). Patent status **unverified**.
- AP clock skew: Jana & Kasera, MobiCom 2008 (method, own implementation).
- Bluetooth SIG company identifiers / UUIDs: identifier->organisation facts from the public Bluetooth SIG Assigned Numbers (`company_identifiers.yaml`, bitbucket.org/bluetooth-SIG/public), retrieved 2026-10-29, 59 IDs curated into coarse types by `scripts/make_rf_tables.py` -> `oiris/features/rf_tables.json`. No licence file is published with the registry; only the factual ID/name pairs are used.
- Camera OUI hints: 164 MA-L assignments of IP/home-security camera makers from the IEEE Registration Authority public listing (`oui.csv`), retrieved 2026-10-29 (factual registry data; a hint, never proof).
- ArUco DICT_4X4_50 code words (50 x 16-bit integers) as in OpenCV's predefined dictionary (opencv/opencv, Apache-2.0); the detector itself is our numpy implementation (`oiris/features/aruco.py`).
- Real eye-tracker recordings for the M-01 real-signal test: LaborTrack (Latifzadeh et al. 2025), preprocessed CSVs MIT (github.com/kayhan-latifzadeh/LaborTrack @5f95f84), raw data CC BY 4.0 (doi:10.5281/zenodo.15163456); participants signed consent forms (paper). **Not shipped**: fetched at test time by `scripts/fetch_eye_reference_data.py` (sha256-pinned) into the git-ignored `training-library/`.
- Colormap stops approximate matplotlib's inferno/viridis (CC0).
- **Not included**: speaker-embedding or anti-spoof model weights. ECAPA-TDNN (Apache-2.0 card, VoxCeleb data terms unverified) and AASIST (MIT code, ASVspoof data ODC-By) can be added as model packages through the model port after their data terms are verified. Piper and eSpeak NG are GPL-3.0 and excluded.
