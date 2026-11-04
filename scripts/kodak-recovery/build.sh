#!/usr/bin/env bash
# Build diagnostics/kodak-recovery.apk.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
if [ -z "${JAVA_HOME:-}" ] && command -v brew >/dev/null 2>&1; then
  JDK="$(brew --prefix)/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
  [ ! -d "$JDK" ] || export JAVA_HOME="$JDK"
fi
if [ -n "${JAVA_HOME:-}" ]; then export PATH="$JAVA_HOME/bin:$PATH"; fi
SDK="${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}"
BT="${BUILD_TOOLS:-$SDK/build-tools/34.0.0}"
JAR="$SDK/platforms/android-34/android.jar"
OUT="${KODAK_APK_OUT:-$ROOT/diagnostics/kodak-recovery.apk}"
KEYSTORE="${KODAK_KEYSTORE:-$HOME/.android/debug.keystore}"
[ -f "$JAR" ] && [ -x "$BT/aapt2" ] || {
  echo 'Install Android platform 34/build-tools 34.0.0; set ANDROID_HOME. See README.md.' >&2
  exit 1
}
WORK="$(mktemp -d "${TMPDIR:-/tmp}/kodak-recovery.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/classes" "$(dirname "$OUT")"
"$BT/aapt2" link -o "$WORK/base.apk" -I "$JAR" --manifest "$HERE/AndroidManifest.xml" \
  --version-code 5 --version-name 2.0
javac -source 8 -target 8 -classpath "$JAR" -d "$WORK/classes" \
  "$HERE/src/local/kodak/adbcheck/MainActivity.java"
CLASSES=()
while IFS= read -r file; do CLASSES+=("$file"); done < <(find "$WORK/classes" -name '*.class')
"$BT/d8" --min-api 23 --lib "$JAR" --output "$WORK" "${CLASSES[@]}"
zip -qj "$WORK/base.apk" "$WORK/classes.dex"
"$BT/zipalign" -f 4 "$WORK/base.apk" "$WORK/aligned.apk"
if [ ! -f "$KEYSTORE" ]; then
  mkdir -p "$(dirname "$KEYSTORE")"
  keytool -genkeypair -keystore "$KEYSTORE" -storepass android -keypass android \
    -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 \
    -dname 'CN=Android Debug,O=Android,C=US' >/dev/null 2>&1
fi
"$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --v4-signing-enabled false --out "$OUT" "$WORK/aligned.apk"
"$BT/apksigner" verify "$OUT"
echo "Built and signature-verified: $OUT"
