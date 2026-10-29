# macOS app

CI (`build` job, macOS runner) produces `o-iris-<commit>-macos-app-unsigned.zip` containing `O Iris.app`
(built by `scripts/make_macos_app.py`). It is **unsigned**: there is no paid Apple Developer account.

## Running the unsigned app
1. Install Python 3.11+ from python.org (the app uses the system `python3`; set `OIRIS_PYTHON` to pick one).
2. Unzip, move `O Iris.app` to Applications, then right-click → Open (or `xattr -dr com.apple.quarantine "/Applications/O Iris.app"`).
3. First launch creates `~/Library/Application Support/O Iris/venv` and installs the bundled wheels offline; the dashboard opens at http://127.0.0.1:8765/.

## Signing and notarizing (needs an Apple Developer ID, paid; not done here)
```
codesign --force --deep --options runtime --timestamp --sign "Developer ID Application: NAME (TEAMID)" "O Iris.app"
ditto -c -k --keepParent "O Iris.app" o-iris.zip
xcrun notarytool submit o-iris.zip --apple-id YOU --team-id TEAMID --password APP_SPECIFIC_PW --wait
xcrun stapler staple "O Iris.app"
spctl --assess --type execute -vv "O Iris.app"
```
Never put signing identities or passwords in this public repository's CI.
