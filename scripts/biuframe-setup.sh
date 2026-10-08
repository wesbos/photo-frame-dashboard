#!/usr/bin/env bash
# Set up a BIUFRAME 10.1" frame (USB "Synergy 10X1", RK3126, Android 6.0.1) as a browser device.
# Guide: docs/biuframe-setup-guide.md
#
# Usage: scripts/biuframe-setup.sh <command>
#   check     Confirm the frame matches the known unit. Changes nothing.
#   backup    Save the eMMC up to the start of userdata to backups/<serial>/ and verify it.
#   verify-backup <file>  Compare boot, recovery and part of system on the frame with a backup.
#   apply     Run every setup step (each checks and skips work already done), then reboot.
#   verify    Check the end state after apply.
#
# Every step stops the script on the first failed check.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="${BIUFRAME_CACHE:-$ROOT/diagnostics/biuframe-downloads}"
DEV_TMP=/data/local/tmp/biuframe

EXPECT_FINGERPRINT="rockchip/rk312x/rk312x:6.0.1/MXC89K/user.thzy.20240919.143320:user/release-keys"
EXPECT_MODEL="10X1"
EXPECT_MANUFACTURER="Synergy"

# Loader sector 0 is eMMC sector 8192; userdata starts at loader sector 0x3B4000.
BACKUP_SECTORS=$((8192 + 0x3B4000))

FIREFOX_URL="https://archive.mozilla.org/pub/fenix/releases/143.0.4/android/fenix-143.0.4-android-armeabi-v7a/fenix-143.0.4.multi.android-armeabi-v7a.apk"
FIREFOX_SHA256="af560738627d4efc9ace75e708fc48aad6a24c78ef43a89daca27e16ff3829f8"
LAUNCHER_URL="https://f-droid.org/repo/amirz.rootless.nexuslauncher_30911.apk"
LAUNCHER_SHA256="7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a"
LIGHTNING_URL="https://f-droid.org/repo/acr.browser.lightning_101.apk"
LIGHTNING_SHA256="820f4f9977a20b060b4091db2b35cff8cd360e060f94aa742255c845747a2d7f"
WEBVIEW_URL="https://raw.githubusercontent.com/LineageOS/android_external_chromium-webview_prebuilt_arm/4b0ae494a7dd/webview.apk"
WEBVIEW_SHA256="e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580"
WEBVIEW_VERSION="106.0.5249.126"
ISRG_X1_URL="https://letsencrypt.org/certs/isrgrootx1.pem"
ISRG_X1_FP="96:BC:EC:06:26:49:76:F3:74:60:77:9A:CF:28:C5:A7:CF:E8:A3:C0:AA:E1:1A:8F:FC:EE:05:C0:BD:DF:08:C6"
ISRG_X2_URL="https://letsencrypt.org/certs/isrg-root-x2.pem"
ISRG_X2_FP="69:72:9B:8E:15:A8:6E:FC:17:7A:57:AF:B7:17:1D:FC:64:AD:D2:8C:2F:CA:8C:F1:50:7E:34:45:3C:CB:14:70"

VENDOR_DISABLE=(com.shenju.biuframe com.adups.fota android.rockchip.update.service
  com.cghs.stresstest com.DeviceTest com.android.rk com.android.rk.mediafloat)
# Persistent apps that Android 6 still starts at boot when only disabled.
VENDOR_HIDE=(com.adups.fota com.cghs.stresstest)

say() { printf '\n==> %s\n' "$*"; }
ok() { printf '    ok: %s\n' "$*"; }
die() { printf '    FAIL: %s\n' "$*" >&2; exit 1; }

sh_dev() { adb shell "$@" | tr -d '\r'; }

# dev_has <grep -E pattern> <command...>: capture output first so grep -q cannot break the pipe.
dev_has() { local pat=$1 out; shift; out="$(sh_dev "$@")"; grep -qE -- "$pat" <<<"$out"; }
has_pkg() { dev_has "^package:$1\$" pm list packages; }

# Run a script on the frame as root. The script is pushed as a file to avoid quoting problems.
root_script() {
  local file
  file="$(mktemp)"
  cat > "$file"
  adb push "$file" "$DEV_TMP/step.sh" >/dev/null
  rm -f "$file"
  adb shell "su -c 'sh $DEV_TMP/step.sh'" | tr -d '\r'
}

fetch() {  # fetch <url> <sha256> <name>
  local url=$1 sha=$2 out="$CACHE/$3"
  mkdir -p "$CACHE"
  if [ ! -f "$out" ] || [ "$(shasum -a 256 "$out" | cut -d' ' -f1)" != "$sha" ]; then
    curl -sfL -o "$out.partial" "$url" || die "download failed: $url"
    mv "$out.partial" "$out"
  fi
  [ "$(shasum -a 256 "$out" | cut -d' ' -f1)" = "$sha" ] || die "SHA-256 mismatch for $3"
  echo "$out"
}

wait_boot() {
  adb wait-for-device
  for _ in $(seq 1 90); do
    [ "$(sh_dev getprop sys.boot_completed 2>/dev/null)" = 1 ] && { sleep 10; return; }
    sleep 2
  done
  die "frame did not finish booting"
}

cmd_check() {
  say "Checking the frame matches the known unit"
  command -v adb >/dev/null || die "adb not found (brew install android-platform-tools)"
  local state
  state="$(adb get-state 2>/dev/null || true)"
  [ "$state" = device ] || die "no authorized ADB device (state: ${state:-none}). Accept the prompt on the frame."
  [ "$(sh_dev getprop ro.build.fingerprint)" = "$EXPECT_FINGERPRINT" ] || die "build fingerprint differs: $(sh_dev getprop ro.build.fingerprint)"
  ok "fingerprint $EXPECT_FINGERPRINT"
  [ "$(sh_dev getprop ro.product.model)" = "$EXPECT_MODEL" ] || die "model is not $EXPECT_MODEL"
  [ "$(sh_dev getprop ro.product.manufacturer)" = "$EXPECT_MANUFACTURER" ] || die "manufacturer is not $EXPECT_MANUFACTURER"
  ok "model $EXPECT_MANUFACTURER $EXPECT_MODEL"
  dev_has 'Rockchip RK3126' cat /proc/cpuinfo || die "CPU is not Rockchip RK3126"
  ok "RK3126"
  dev_has '^ssv6x5x' lsmod || die "Wi-Fi driver ssv6x5x not loaded"
  ok "Wi-Fi driver ssv6x5x"
  [ "$(sh_dev "su -c id" | cut -d' ' -f1)" = "uid=0(root)" ] || die "su did not give root"
  ok "su gives root"
  [ "$(sh_dev "su -c 'cat /sys/block/mmcblk0/mmcblk0p5/start'")" = 90112 ] || die "boot partition is not at eMMC sector 90112"
  ok "partition layout (boot at eMMC sector 90112)"
}

cmd_backup() {
  cmd_check
  local serial dir out
  serial="$(sh_dev getprop ro.serialno)"
  dir="$ROOT/backups/$serial"
  out="$dir/emmc-0-$BACKUP_SECTORS.img.gz"
  mkdir -p "$dir"
  [ -e "$out" ] && die "$out already exists"
  say "Reading $BACKUP_SECTORS sectors ($((BACKUP_SECTORS / 2048)) MiB) over ADB"
  adb exec-out "su -c 'dd if=/dev/block/mmcblk0 bs=512 count=$BACKUP_SECTORS 2>/dev/null'" \
    | tee >(shasum -a 256 | cut -d' ' -f1 > "$out.sha256.raw") | gzip -1 > "$out.partial"
  mv "$out.partial" "$out"
  local size raw
  size="$(gunzip -c "$out" | wc -c | tr -d ' ')"
  [ "$size" = $((BACKUP_SECTORS * 512)) ] || die "backup is $size bytes, expected $((BACKUP_SECTORS * 512))"
  raw="$(cat "$out.sha256.raw")"
  [ "$(gunzip -c "$out" | shasum -a 256 | cut -d' ' -f1)" = "$raw" ] || die "gzip readback does not match stream hash"
  ok "$size bytes, SHA-256 $raw"
  echo "$raw" > "$out.sha256"
  rm -f "$out.sha256.raw"
  cmd_verify_backup "$out"
  ok "backup saved to $out"
}

# Re-read boot, recovery and the start of system from the frame and compare with a backup image.
cmd_verify_backup() {
  local out=${1:?usage: verify-backup <backup.img.gz>} name start count a b
  [ -f "$out" ] || die "$out not found"
  say "Re-reading boot, recovery and 16 MiB of system data to compare with $(basename "$out")"
  # system data at loader 0xC0000; the start of system holds the ext4 superblock and journal, which
  # change while mounted (SuperSU remounts /system several times a minute).
  for region in "boot 90112 24576" "recovery 114688 65536" "system 794624 32768"; do
    read -r name start count <<<"$region"
    a="$(adb exec-out "su -c 'dd if=/dev/block/mmcblk0 bs=512 skip=$start count=$count 2>/dev/null'" | shasum -a 256 | cut -d' ' -f1)"
    # dd stops reading early; ignore gunzip's broken pipe.
    b="$({ gunzip -c "$out" 2>/dev/null || true; } | dd bs=512 skip="$start" count="$count" 2>/dev/null | shasum -a 256 | cut -d' ' -f1)"
    [ "$a" = "$b" ] || die "$name differs between backup and re-read"
    ok "$name matches"
  done
}

step_debloat() {
  say "Disabling vendor apps"
  local p
  for p in "${VENDOR_DISABLE[@]}"; do
    sh_dev "su -c 'pm disable $p'" >/dev/null
  done
  for p in "${VENDOR_HIDE[@]}"; do
    sh_dev "su -c 'pm hide $p'" >/dev/null
  done
  for p in "${VENDOR_DISABLE[@]}"; do
    dev_has 'enabled=[23]' dumpsys package "$p" || die "$p is not disabled"
  done
  for p in "${VENDOR_HIDE[@]}"; do
    dev_has 'hidden=true' dumpsys package "$p" || die "$p is not hidden"
  done
  ok "${#VENDOR_DISABLE[@]} disabled, ${#VENDOR_HIDE[@]} hidden"
}

step_zram() {
  say "Swap: zram 128 MB -> 512 MB at every boot"
  adb push "$ROOT/scripts/biuframe-su.d-50zram" "$DEV_TMP/50zram" >/dev/null
  root_script <<EOF
set -e
mount -o remount,rw /system
mkdir -p /system/su.d
cp $DEV_TMP/50zram /system/su.d/50zram
[ -f /system/bin/install-recovery.sh.bak ] || cp /system/bin/install-recovery.sh /system/bin/install-recovery.sh.bak
grep -q 50zram /system/bin/install-recovery.sh || echo '[ -x /system/su.d/50zram ] && /system/su.d/50zram' >> /system/bin/install-recovery.sh
mount -o remount,rw /system
chmod 0700 /system/su.d /system/su.d/50zram
chown 0:0 /system/su.d /system/su.d/50zram
sync
mount -o remount,ro /system
/system/su.d/50zram
EOF
  dev_has 50zram "su -c 'tail -1 /system/bin/install-recovery.sh'" || die "boot hook missing"
  dev_has 524280 cat /proc/swaps || die "swap is not 512 MB"
  ok "swap 512 MB, boot hook in install-recovery.sh"
}

step_apps() {
  say "Installing Firefox 143.0.4 and Rootless Pixel Launcher 3.9.1"
  local ff la li
  ff="$(fetch "$FIREFOX_URL" "$FIREFOX_SHA256" firefox-143.0.4-armeabi-v7a.apk)"
  la="$(fetch "$LAUNCHER_URL" "$LAUNCHER_SHA256" rootless-pixel-launcher-3.9.1.apk)"
  has_pkg org.mozilla.firefox || adb install "$ff" >/dev/null
  has_pkg amirz.rootless.nexuslauncher || adb install "$la" >/dev/null
  if [ "${BIUFRAME_LIGHTNING:-0}" = 1 ]; then
    li="$(fetch "$LIGHTNING_URL" "$LIGHTNING_SHA256" lightning-5.1.0.apk)"
    has_pkg acr.browser.lightning || adb install "$li" >/dev/null
  fi
  has_pkg org.mozilla.firefox || die "Firefox not installed"
  has_pkg amirz.rootless.nexuslauncher || die "launcher not installed"
  ok "installed"
}

step_webview() {
  say "System WebView 44 -> $WEBVIEW_VERSION"
  local apk libs
  apk="$(fetch "$WEBVIEW_URL" "$WEBVIEW_SHA256" webview-$WEBVIEW_VERSION.apk)"
  libs="$CACHE/webview-libs"
  rm -rf "$libs"
  mkdir -p "$libs"
  unzip -q -j "$apk" 'lib/armeabi-v7a/*' -d "$libs"
  sh_dev "mkdir -p $DEV_TMP/wvlib"
  adb push "$apk" "$DEV_TMP/webview.apk" >/dev/null
  adb push "$libs"/. "$DEV_TMP/wvlib/" >/dev/null
  root_script <<EOF
set -e
W=/system/app/webview
mount -o remount,rw /system
[ -f \$W/webview.apk.bak ] || cp \$W/webview.apk \$W/webview.apk.bak
cp $DEV_TMP/webview.apk \$W/webview.apk
rm -rf \$W/oat
mkdir -p \$W/lib/arm
cp $DEV_TMP/wvlib/*.so \$W/lib/arm/
mount -o remount,rw /system
chmod 0644 \$W/webview.apk \$W/lib/arm/*.so
chmod 0755 \$W/lib \$W/lib/arm
chown -R 0:0 \$W/webview.apk \$W/lib
sync
mount -o remount,ro /system
EOF
  local want got f
  for f in "$apk" "$libs"/*.so; do
    want="$(md5 -q "$f")"
    case "$f" in
      *.apk) got="$(sh_dev "md5sum /system/app/webview/webview.apk" | cut -d' ' -f1)" ;;
      *) got="$(sh_dev "md5sum /system/app/webview/lib/arm/$(basename "$f")" | cut -d' ' -f1)" ;;
    esac
    [ "$want" = "$got" ] || die "$(basename "$f") on the frame does not match"
  done
  dev_has '^-rw-r--r--' "ls -l /system/app/webview/lib/arm/libwebviewchromium.so" || die "WebView library is not 0644"
  ok "APK and $(ls "$libs" | wc -l | tr -d ' ') native libraries in place (active after reboot)"
}

step_certs() {
  say "Adding Let's Encrypt roots (ISRG Root X1, X2) to the system CA store"
  local pem fp h tmp
  tmp="$(mktemp -d)"
  for pair in "$ISRG_X1_URL $ISRG_X1_FP" "$ISRG_X2_URL $ISRG_X2_FP"; do
    read -r url fp <<<"$pair"
    pem="$tmp/$(basename "$url")"
    curl -sfL -o "$pem" "$url" || die "download failed: $url"
    [ "$(openssl x509 -in "$pem" -noout -fingerprint -sha256 | cut -d= -f2)" = "$fp" ] || die "fingerprint mismatch for $url"
    h="$(openssl x509 -in "$pem" -noout -subject_hash_old)"
    { openssl x509 -in "$pem" -outform PEM; openssl x509 -in "$pem" -noout -text -fingerprint; } > "$tmp/$h.0"
    adb push "$tmp/$h.0" "$DEV_TMP/$h.0" >/dev/null
    root_script <<EOF
set -e
mount -o remount,rw /system
cp $DEV_TMP/$h.0 /system/etc/security/cacerts/$h.0
mount -o remount,rw /system
chmod 0644 /system/etc/security/cacerts/$h.0
chown 0:0 /system/etc/security/cacerts/$h.0
sync
mount -o remount,ro /system
EOF
    dev_has '^-rw-r--r--' "ls -l /system/etc/security/cacerts/$h.0" || die "$h.0 is not 0644"
    ok "$h.0 $(openssl x509 -in "$pem" -noout -subject | sed 's/.*CN *= *//')"
  done
  rm -rf "$tmp"
}

step_navbar() {
  say "Turning on the navigation bar (Back and volume only on this firmware)"
  root_script <<'EOF'
set -e
mount -o remount,rw /system
[ -f /system/build.prop.bak ] || cp /system/build.prop /system/build.prop.bak
grep -q '^qemu.hw.mainkeys=' /system/build.prop || echo 'qemu.hw.mainkeys=0' >> /system/build.prop
mount -o remount,rw /system
chmod 0644 /system/build.prop
sync
mount -o remount,ro /system
EOF
  dev_has '^qemu.hw.mainkeys=0$' cat /system/build.prop || die "build.prop not updated"
  ok "qemu.hw.mainkeys=0 (active after reboot)"
}

cmd_verify() {
  say "Verifying end state"
  [ "$(sh_dev "dumpsys package com.android.webview" | grep -m1 versionName | sed 's/.*=//')" = "$WEBVIEW_VERSION" ] || die "WebView is not $WEBVIEW_VERSION"
  ok "WebView $WEBVIEW_VERSION"
  dev_has 'webviewchromiumloader: Failed to load library' logcat -d && die "WebView native library failed to load"
  ok "WebView native library loaded"
  dev_has 524280 cat /proc/swaps || die "swap is not 512 MB after boot"
  ok "swap 512 MB after boot"
  dev_has 'Window\{.* NavigationBar\}' dumpsys window windows || die "no navigation bar window"
  ok "navigation bar present"
  local running
  running="$(sh_dev ps | grep -E 'adups|stresstest|biuframe|rockchip.update|DeviceTest|com.android.rk' || true)"
  [ -z "$running" ] || die "vendor processes still running: $running"
  ok "no vendor processes"
  sh_dev "ls /system/etc/security/cacerts/6187b673.0 /system/etc/security/cacerts/8794b4e3.0" >/dev/null || die "Let's Encrypt roots missing"
  ok "Let's Encrypt roots present"
}

cmd_apply() {
  cmd_check
  sh_dev "mkdir -p $DEV_TMP"
  step_debloat
  step_zram
  step_apps
  step_webview
  step_certs
  step_navbar
  say "Rebooting"
  adb reboot
  sleep 15
  wait_boot
  cmd_verify
  sh_dev "rm -rf $DEV_TMP"
  say "Done. On the frame: press Home, pick Rootless Pixel Launcher, tap Always."
}

case "${1:-}" in
  check) cmd_check ;;
  backup) cmd_backup ;;
  verify-backup) cmd_verify_backup "${2:-}" ;;
  apply) cmd_apply ;;
  verify) cmd_verify ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
