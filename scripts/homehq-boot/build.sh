#!/usr/bin/env bash
# Build only. Never installs an APK or changes a connected frame.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/scripts/homehq-boot"
SDK="${FRAME_BOOT_SDK:-$ROOT/diagnostics/android-sdk}"
OUT="${FRAME_BOOT_OUTPUT:-$ROOT/diagnostics/homehq-boot}"
# Kept outside OUT so a rebuild does not regenerate the key: a new key means
# INSTALL_FAILED_UPDATE_INCOMPATIBLE on an already-installed frame.
KEYSTORE="${FRAME_BOOT_KEYSTORE:-$ROOT/diagnostics/homehq-boot-signing.p12}"
JAVA="${JAVA_HOME:?Set JAVA_HOME to a JDK}"
BT="$SDK/build-tools/34.0.0"
JAR="$SDK/platforms/android-34/android.jar"

rm -rf "$OUT"; mkdir -p "$OUT"
CLASSES="$OUT/classes"; mkdir -p "$CLASSES"

# The frame is API 23, so compile and dex against that floor.
"$BT/aapt2" link -o "$OUT/base.apk" -I "$JAR" \
  --manifest "$SRC/AndroidManifest.xml" \
  --version-code 1 --version-name 1.0 \
  --min-sdk-version 23 --target-sdk-version 23

"$JAVA/bin/javac" --release 8 -nowarn -classpath "$JAR" -d "$CLASSES" \
  "$SRC"/src/com/homehq/boot/*.java

"$JAVA/bin/java" -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 \
  --min-api 23 --lib "$JAR" --output "$OUT" \
  "$CLASSES"/com/homehq/boot/*.class

(cd "$OUT" && zip -qj base.apk classes.dex)
"$BT/zipalign" -f 4 "$OUT/base.apk" "$OUT/aligned.apk"

if [[ ! -f "$KEYSTORE" ]]; then
  "$JAVA/bin/keytool" -genkeypair -keystore "$KEYSTORE" \
    -storepass android -keypass android -alias homehqboot -keyalg RSA -keysize 2048 \
    -validity 10000 -dname 'CN=Photo Frame Development' >/dev/null 2>&1
fi

"$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android \
  --v3-signing-enabled false --v4-signing-enabled false \
  --key-pass pass:android --out "$OUT/homehq-boot.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify --min-sdk-version 23 --max-sdk-version 23 "$OUT/homehq-boot.apk"
shasum -a 256 "$OUT/homehq-boot.apk"
