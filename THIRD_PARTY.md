# Third-party components

Policy (R-05): allowed MIT, BSD-2/3, Apache-2.0, ISC, PSF, MPL-2.0; LGPL only with dynamic linking or an app exception. GPL tools only as **separate executables**, never imported. Denied: AGPL, non-commercial, "research only", SSPL/BUSL, proprietary. `scripts/license_check.py` enforces this in CI.

## Python runtime (required)
| Package | License | Use |
|---|---|---|
| numpy | BSD-3-Clause | arrays, signal processing |
| cryptography | Apache-2.0 OR BSD-3-Clause | AES-256-GCM, scrypt, X25519 |
| PyNaCl (libsodium) | Apache-2.0 (libsodium ISC) | Ed25519 anchors |
| noiseprotocol | MIT | Noise_XX channel |

## Python optional (`pip install .[hw]`)
| Package | License | Use |
|---|---|---|
| bleak | MIT | passive BLE scanning |
| pyserial | BSD-3-Clause | GPS, mmWave UART |
| opencv-python-headless | Apache-2.0 (OpenCV); wheel bundles FFmpeg under LGPL as a shared library | UVC thermal; Haar cascade file license **unverified** |
| adafruit-circuitpython-mlx90640 | MIT | MLX90640 thermal |
| gpiozero | BSD-3-Clause | IR LED gate |
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
| cryptsetup (LUKS2) | GPL-2.0 | Pi data volume (set up by the operator) |
| flite | BSD-style | Pi TTS |

## Android (see android/dependencies.txt)
AndroidX core/fragment/biometric/camera/sqlite (Apache-2.0); SQLCipher for Android (BSD-3-Clause); Mapsforge (LGPL-3.0 with exception). Android SDK/Gradle are build-time tools only. No Google Play Services, ML Kit or Firebase.

## Algorithms and data
- rPPG: own implementation of the published POS method (Wang et al., 2017). Patent status **unverified**.
- AP clock skew: Jana & Kasera, MobiCom 2008 (method, own implementation).
- Bluetooth SIG company identifiers / UUIDs: public assigned numbers (small excerpt).
- Colormap stops approximate matplotlib's inferno/viridis (CC0).
- **Not included**: speaker-embedding or anti-spoof model weights. ECAPA-TDNN (Apache-2.0 card, VoxCeleb data terms unverified) and AASIST (MIT code, ASVspoof data ODC-By) can be added as model packages through the model port after their data terms are verified. Piper and eSpeak NG are GPL-3.0 and excluded.
