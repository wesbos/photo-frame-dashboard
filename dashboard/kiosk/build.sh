#!/usr/bin/env bash
# Builds kiosk/build/homehq.apk without Gradle. Needs JDK 17 + Android build-tools 34 + platform 34:
#   brew install --cask android-commandlinetools
#   sdkmanager --sdk_root=$ANDROID_HOME "build-tools;34.0.0" "platforms;android-34"
# Ubuntu 24.04 (multiverse), with ANDROID_HOME=/usr/lib/android-sdk:
#   sudo apt install openjdk-17-jdk-headless zip google-android-build-tools-34.0.0-installer \
#     google-android-platform-34-installer
# Install on the tablet: adb install -r kiosk/build/homehq.apk
# Optional: KIOSK_SITE=<dir> bundles a static site, served at http://127.0.0.1:8765/ (README).
set -euo pipefail
cd "$(dirname "$0")"

ANDROID_HOME="${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}"
# d8 from build-tools 34 crashes (NullPointerException) on classes from some newer JDKs; then
# point BUILD_TOOLS at a newer version, e.g. BUILD_TOOLS=$ANDROID_HOME/build-tools/36.1.0
BT="${BUILD_TOOLS:-$ANDROID_HOME/build-tools/34.0.0}"
JAR="$ANDROID_HOME/platforms/android-34/android.jar"
KS="$HOME/.android/debug.keystore"

rm -rf build && mkdir -p build/gen build/classes

ASSETS=()
if [ -n "${KIOSK_SITE:-}" ]; then
  [ -f "$KIOSK_SITE/index.html" ] || { echo "KIOSK_SITE has no index.html: $KIOSK_SITE" >&2; exit 1; }
  mkdir -p build/assets/site
  cp -R "$KIOSK_SITE"/. build/assets/site/
  ASSETS=(-A build/assets)
  echo "Bundling $KIOSK_SITE as http://127.0.0.1:8765/"
fi

"$BT/aapt2" compile --dir res -o build/res.zip
# Target 28: Android 15 refuses to install below 24, and Android 14+ warns below 28 on the first
# launch. Targets of 30 and up need manifest changes (package visibility, exported), so stay at 28.
"$BT/aapt2" link -o build/base.apk -I "$JAR" --manifest AndroidManifest.xml ${ASSETS[@]+"${ASSETS[@]}"} build/res.zip \
  --java build/gen --min-sdk-version 23 --target-sdk-version 28 --version-code 3 --version-name 1.2

javac -nowarn -source 8 -target 8 -classpath "$JAR" -d build/classes \
  src/com/wesbos/homehq/*.java build/gen/com/wesbos/homehq/R.java

"$BT/d8" --min-api 23 --lib "$JAR" --output build $(find build/classes -name '*.class')
(cd build && zip -qj base.apk classes.dex)
"$BT/zipalign" -f 4 build/base.apk build/aligned.apk

if [ ! -f "$KS" ]; then
  mkdir -p "$(dirname "$KS")"
  keytool -genkeypair -keystore "$KS" -storepass android -keypass android -alias androiddebugkey \
    -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US" >/dev/null 2>&1
fi
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android --out build/homehq.apk build/aligned.apk
echo "Built kiosk/build/homehq.apk"
