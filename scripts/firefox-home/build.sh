#!/usr/bin/env bash
# Build only. Never installs an APK or changes a connected frame.
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK_SRC="$TASK_ROOT/scripts/firefox-home"
TASK_SDK="${FIREFOX_HOME_SDK:-$TASK_ROOT/diagnostics/android-sdk}"
TASK_OUT="${FIREFOX_HOME_OUTPUT:-$TASK_ROOT/diagnostics/firefox-home}"
TASK_JAVA="${JAVA_HOME:?Set JAVA_HOME to a JDK 17 installation}"
TASK_BT="$TASK_SDK/build-tools/34.0.0"
TASK_JAR="$TASK_SDK/platforms/android-34/android.jar"
# Windows build-tools ship .exe and .bat wrappers.
tool() { if [[ -x "$TASK_BT/$1" ]]; then echo "$TASK_BT/$1"; elif [[ -f "$TASK_BT/$1.exe" ]]; then echo "$TASK_BT/$1.exe"; else echo "$TASK_BT/$1.bat"; fi; }
mkdir -p "$TASK_OUT"
rm -rf "$TASK_OUT/classes" "$TASK_OUT/dex"
mkdir -p "$TASK_OUT/classes" "$TASK_OUT/dex"
"$(tool aapt2)" link -o "$TASK_OUT/base.apk" -I "$TASK_JAR" \
  --manifest "$TASK_SRC/AndroidManifest.xml" --version-code 1 --version-name 1.0
"$TASK_JAVA/bin/javac" --release 8 -classpath "$TASK_JAR" -d "$TASK_OUT/classes" \
  "$TASK_SRC"/src/com/photoframe/firefoxhome/*.java
"$TASK_JAVA/bin/java" -cp "$TASK_BT/lib/d8.jar" com.android.tools.r8.D8 \
  --min-api 26 --lib "$TASK_JAR" --output "$TASK_OUT/dex" \
  "$TASK_OUT"/classes/com/photoframe/firefoxhome/*.class
"$TASK_JAVA/bin/jar" --update --no-manifest --file "$TASK_OUT/base.apk" -C "$TASK_OUT/dex" classes.dex
"$(tool zipalign)" -f 4 "$TASK_OUT/base.apk" "$TASK_OUT/aligned.apk"
if [[ ! -f "$TASK_OUT/signing.p12" ]]; then
  "$TASK_JAVA/bin/keytool" -genkeypair -keystore "$TASK_OUT/signing.p12" \
    -storepass android -keypass android -alias firefoxhome -keyalg RSA -keysize 2048 \
    -validity 10000 -dname 'CN=Photo Frame Development' >/dev/null 2>&1
fi
"$(tool apksigner)" sign --ks "$TASK_OUT/signing.p12" --ks-pass pass:android \
  --key-pass pass:android --out "$TASK_OUT/firefox-home.apk" "$TASK_OUT/aligned.apk"
"$(tool apksigner)" verify "$TASK_OUT/firefox-home.apk"
sha256sum "$TASK_OUT/firefox-home.apk" 2>/dev/null || shasum -a 256 "$TASK_OUT/firefox-home.apk"
