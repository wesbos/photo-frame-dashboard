#!/usr/bin/env bash
# Builds frame-kiosk.apk without Gradle: aapt2 -> javac -> d8 -> zipalign -> apksigner.
# build-tools 35+: d8 34.0.0 crashes (NPE) on JDK 21 class files.
# The signing key (kiosk.keystore) must be kept: updates need the same key.
set -euo pipefail
export PATH=$HOME/android-sdk/jdk/bin:$PATH  # javac/keytool from the bundled JDK
cd "$(dirname "$0")"
SDK=${ANDROID_SDK:-$HOME/android-sdk}
BT=$SDK/build-tools/35.0.0
JAR=$SDK/platforms/android-33/android.jar
rm -rf build && mkdir -p build/res build/gen build/classes build/dex build/ical

# ical.js (MPL-2.0) parses calendars in standalone mode. Downloaded from the npm registry
# and checked against the registry's own sha512 before use; nothing else is downloaded.
ICAL_VER=2.2.1
ICAL_SHA512=yK/UlPbEs316igb/tjRgbFA8ZV75rCsBJp/hWOatpyaPNlgw0dGDmU+FoicOcwX4xXkeXOkYiOmCqNPFpNPkQg==
if [[ ! -f assets/web/ical.min.js ]]; then
  curl -fsSL -o build/ical/ical.tgz "https://registry.npmjs.org/ical.js/-/ical.js-$ICAL_VER.tgz"
  got=$(openssl dgst -sha512 -binary build/ical/ical.tgz | base64 | tr -d '\n')
  [[ "$got" == "$ICAL_SHA512" ]] || { echo "ical.js download does not match its sha512" >&2; exit 1; }
  tar -xzf build/ical/ical.tgz -C build/ical package/dist/ical.es5.min.cjs package/LICENSE
  cp build/ical/package/dist/ical.es5.min.cjs assets/web/ical.min.js
fi

"$BT/aapt2" compile --dir res -o build/res/res.zip
"$BT/aapt2" link -I "$JAR" --manifest AndroidManifest.xml --java build/gen -A assets \
  -o build/unsigned.apk build/res/res.zip

javac -source 8 -target 8 -bootclasspath "$JAR" -Xlint:-options -encoding UTF-8 \
  -d build/classes $(find src build/gen -name '*.java')
"$BT/d8" --lib "$JAR" --min-api 29 --release --output build/dex $(find build/classes -name '*.class')

cp build/unsigned.apk build/with-dex.apk
(cd build/dex && zip -q -j ../with-dex.apk classes.dex)
"$BT/zipalign" -f -p 4 build/with-dex.apk build/aligned.apk

if [[ ! -f kiosk.keystore ]]; then
  keytool -genkeypair -keystore kiosk.keystore -storepass framekiosk -keypass framekiosk \
    -alias kiosk -keyalg RSA -keysize 2048 -validity 36500 -dname "CN=Frame Kiosk" >/dev/null
fi
"$BT/apksigner" sign --ks kiosk.keystore --ks-pass pass:framekiosk --ks-key-alias kiosk \
  --out frame-kiosk.apk build/aligned.apk
"$BT/apksigner" verify frame-kiosk.apk && ls -la frame-kiosk.apk
