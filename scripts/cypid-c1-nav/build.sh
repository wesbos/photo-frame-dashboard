#!/usr/bin/env bash
# Build and sign only. Never installs an APK or changes a connected device.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/scripts/cypid-c1-nav"
SDK="${ANDROID_HOME:?Set ANDROID_HOME to the Android SDK}"
JAVA="${JAVA_HOME:?Set JAVA_HOME to a JDK 17 installation}"
export PATH="$JAVA/bin:$PATH"
BUILD_TOOLS="${C1_NAV_BUILD_TOOLS:-36.0.0}"
PLATFORM="${C1_NAV_PLATFORM:-android-37.0}"
BT="$SDK/build-tools/$BUILD_TOOLS"
JAR="$SDK/platforms/$PLATFORM/android.jar"
OUT="${C1_NAV_OUTPUT:-$ROOT/diagnostics/cypid-c1/nav-helper}"
mkdir -p "$OUT"
work="$(mktemp -d "$OUT/build.XXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/classes" "$work/dex"
"$BT/aapt2" link -o "$work/base.apk" -I "$JAR" \
    --manifest "$SRC/AndroidManifest.xml" --version-code 3 --version-name 1.2
"$JAVA/bin/javac" --release 8 -classpath "$JAR" -d "$work/classes" \
    "$SRC"/src/com/photoframe/c1nav/*.java
"$JAVA/bin/java" -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 \
    --min-api 28 --lib "$JAR" --output "$work/dex" \
    "$work/classes"/com/photoframe/c1nav/*.class
"$JAVA/bin/jar" uf "$work/base.apk" -C "$work/dex" classes.dex
"$BT/zipalign" -f 4 "$work/base.apk" "$work/aligned.apk"
if [[ ! -f "$OUT/signing.p12" ]]; then
    "$JAVA/bin/keytool" -genkeypair -keystore "$OUT/signing.p12" \
        -storepass android -keypass android -alias c1nav -keyalg RSA -keysize 2048 \
        -validity 10000 -dname 'CN=C1 Navigation Development' >/dev/null 2>&1
fi
"$BT/apksigner" sign --ks "$OUT/signing.p12" --ks-pass pass:android \
    --key-pass pass:android --out "$OUT/c1nav.apk" "$work/aligned.apk"
"$BT/apksigner" verify --min-sdk-version 28 --max-sdk-version 35 "$OUT/c1nav.apk"
sha256sum "$OUT/c1nav.apk"
