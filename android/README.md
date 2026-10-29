# Android companion app (Kotlin, minSdk 29)
**Purpose**: operator app and fallback detection node. **Inputs**: C1/C3 records over the (planned) Noise link, local camera/BLE in fallback mode. **Outputs**: zone UI (P1–P5), voice tiers, encrypted sighting log. **Depends on**: AndroidX, SQLCipher, Mapsforge (see `dependencies.txt`), and the shared `schema/` JSON (packaged as assets).
Build: `cd android && gradle assembleDebug` (JDK 17, Android SDK 34). No INTERNET permission, `FLAG_SECURE`, no backups. Unsigned. See docs/STATUS.md for stubs.
