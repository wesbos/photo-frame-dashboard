#!/usr/bin/env bash
# PF1007L boot fixes: one Wi-Fi MAC at all times, a correct clock after power cuts, no brownout or
# freeze when Wi-Fi starts, and fast DHCP and DNS.
# Guide: docs/pf1007l-boot-fixes.md
#
# Usage: scripts/pf1007l-boot/install.sh <command>
#   check      Confirm the frame is a PF1007L with root ADB, and show what is installed. Changes nothing.
#   backup     Copy the files that apply changes to backups/pf1007l-boot/<time>/.
#   apply      Install the fixes with the settings in scripts/pf1007l-boot/frame-boot.conf. Runs backup first.
#   verify     After a reboot, show what each fix did on this boot.
#   uninstall  Put back install-recovery.sh and wpa_supplicant and remove the fixes.
#
# Uses the only ADB device, or the one in ANDROID_SERIAL. Stops at the first failed check.

set -euo pipefail

# Git Bash rewrites arguments that look like POSIX paths before calling adb.exe (#185).
# Exclude frame-side paths; local paths are still converted for adb push.
case "$(uname -s)" in
  MINGW*|MSYS*) export MSYS2_ARG_CONV_EXCL="${MSYS2_ARG_CONV_EXCL:+$MSYS2_ARG_CONV_EXCL;}/sbin/;/system/;/data/;/sys/;/proc/" ;;
esac

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CONF="$HERE/frame-boot.conf"
DEV_TMP=/data/local/tmp/frame-boot
DEV_CONF=/data/local/frame-boot.conf
HOOK_LINE='exec /system/bin/sh /system/bin/frame-boot-hook.sh'
OLD_HOOK_LINE='exec /system/bin/sh /system/bin/frame-fixmac.sh'   # from PR #6
SCRIPTS=(frame-boot-hook.sh frame-fixmac.sh frame-powerfix.sh frame-timesync.sh frame-wifidefer.sh frame-firewall.sh)

EXPECT_DEVICE=astar-m86_8723cs
EXPECT_RELEASE=6.0.1

say() { printf '\n==> %s\n' "$*"; }
ok() { printf '    ok: %s\n' "$*"; }
warn() { printf '    note: %s\n' "$*"; }
die() { printf '    FAIL: %s\n' "$*" >&2; exit 1; }

sh_dev() { adb shell "$@" | tr -d '\r'; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
dev_sha() { sh_dev "/sbin/busybox sha256sum $1" | cut -d' ' -f1; }
# A CRLF script passes the SHA-256 checks (both copies have the CRs) but cannot run on the frame
# and breaks Wi-Fi (#185). Git Bash's grep hides CRs, so count them with tr.
no_cr() { [ -z "$(tr -cd '\r' < "$1")" ] ||
  die "$1 has CRLF line endings. Re-check out with LF: git rm -r -q --cached . && git reset --hard"; }

# Run a script on the frame. It is pushed as a file to avoid quoting problems.
root_script() {
  local file
  file="$(mktemp)"
  cat > "$file"
  adb push "$file" "$DEV_TMP/step.sh" >/dev/null
  rm -f "$file"
  adb shell "sh $DEV_TMP/step.sh" | tr -d '\r'
}

cmd_check() {
  say "Checking the frame"
  command -v adb >/dev/null || die "adb not found"
  local state
  state="$(adb get-state 2>/dev/null || true)"
  [ "$state" = device ] || die "no ADB device (state: ${state:-none})"
  [ "$(sh_dev getprop ro.product.device)" = "$EXPECT_DEVICE" ] ||
    die "device is $(sh_dev getprop ro.product.device), not $EXPECT_DEVICE (PF1007L)"
  [ "$(sh_dev getprop ro.build.version.release)" = "$EXPECT_RELEASE" ] || die "Android is not $EXPECT_RELEASE"
  ok "PF1007L ($EXPECT_DEVICE), Android $EXPECT_RELEASE, firmware $(sh_dev getprop ro.build.display.id)"
  [ "$(sh_dev id | cut -d' ' -f1)" = "uid=0(root)" ] || die "adb shell is not root (see T7 in docs/pf1007l-start-here.md)"
  ok "root ADB"
  ok "SELinux: $(sh_dev getenforce)"
  case "$(adb get-serialno 2>/dev/null)" in
    *:*) warn "ADB is over the network. These fixes replace wpa_supplicant and change Wi-Fi start-up; if
    that goes wrong you lose network ADB, and on Route S that is your only ADB. Prefer installing over USB." ;;
  esac
  sh_dev 'test -f /system/bin/install-recovery.sh && echo yes' | grep -q yes || die "/system/bin/install-recovery.sh not found"
  ok "install-recovery.sh present"
  sh_dev 'test -f /system/bin/wpa_supplicant && echo yes' | grep -q yes || die "/system/bin/wpa_supplicant not found"
  if sh_dev 'test -e /system/vendor/modules/aic8800_fdrv.ko && echo yes' | grep -q yes; then
    ok "AIC8800 Wi-Fi driver"
  else
    warn "aic8800_fdrv.ko not found: set WIFI_DRIVER in frame-boot.conf or WIFI_DEFER=0"
  fi
  if sh_dev 'test -w /sys/devices/platform/axp22_board/axp22_reg && echo yes' | grep -q yes; then
    ok "AXP22x power chip"
  else
    warn "AXP22x control file not found: POWER_FIX does nothing on this unit"
  fi
  sh_dev 'test -x /sbin/busybox && echo yes' | grep -q yes || die "/sbin/busybox not found (used for SHA-256 checks and the saved time)"
  say "Installed now"
  if sh_dev 'grep -q frame-boot-hook /system/bin/install-recovery.sh && echo yes' | grep -q yes; then
    ok "boot fixes installed"
  else
    ok "boot fixes not installed"
  fi
  if sh_dev 'test -e /system/bin/wpa_supplicant.real && echo yes' | grep -q yes; then
    ok "wpa_supplicant is wrapped (wpa_supplicant.real exists)"
  fi
}

cmd_backup() {
  cmd_check
  local dir f
  dir="$ROOT/backups/pf1007l-boot/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$dir"
  say "Copying files to $dir"
  for f in /system/bin/install-recovery.sh /system/bin/wpa_supplicant /system/bin/wpa_supplicant.real \
    /system/bin/install-recovery.sh.bak "$DEV_CONF"; do
    sh_dev "test -f $f && echo yes" | grep -q yes || continue
    adb exec-out "cat $f" > "$dir/$(basename "$f")"
    [ "$(sha "$dir/$(basename "$f")")" = "$(dev_sha "$f")" ] || die "copy of $f does not match the frame"
    ok "$f"
  done
}

# A stable, locally administered MAC from the serial number, so reinstalling gives the same address.
mac_from_serial() {
  local h
  h="$(printf '%s' "$(sh_dev getprop ro.serialno)" | shasum -a 256 | cut -c1-10)"
  printf '02:%s:%s:%s:%s:%s\n' "${h:0:2}" "${h:2:2}" "${h:4:2}" "${h:6:2}" "${h:8:2}"
}

cmd_apply() {
  [ -f "$CONF" ] || die "$CONF not found. Copy frame-boot.conf.example to frame-boot.conf and edit it."
  local f
  for f in "${SCRIPTS[@]}" wpa_supplicant-wrapper.sh; do no_cr "$HERE/device/$f"; done
  no_cr "$CONF"
  # Validate the optional firewall before writing anything; mistakes can remove network ADB.
  if ( . "$CONF"; [ "${FIREWALL:-0}" = 1 ] ); then
    ( . "$CONF"; . "$HERE/device/frame-firewall.sh"; fw_config ) ||
      die "invalid firewall settings: use literal IPv4 DNS addresses and IPv4:port destinations"
    case "$(adb get-serialno 2>/dev/null)" in
      *:*) die "install FIREWALL=1 over working USB ADB, not network ADB; verify USB recovery first" ;;
      unknown|'') die "no selected USB ADB device for firewall installation" ;;
    esac
  fi
  cmd_backup
  local tmp mac s
  tmp="$(mktemp -d)"
  trap "rm -rf '$tmp'" EXIT
  cp "$CONF" "$tmp/frame-boot.conf"
  # shellcheck disable=SC1090
  mac="$(. "$CONF"; printf '%s' "${MAC:-}")"
  if [ -z "$mac" ]; then
    mac="$(mac_from_serial)"
    sed -i.orig "s/^MAC=.*/MAC=$mac/" "$tmp/frame-boot.conf"
    ok "MAC not set; using $mac (from the serial number). Reserve it in DHCP."
  fi
  printf '%s\n' "$mac" | grep -qiE '^[0-9a-f][26ae](:[0-9a-f]{2}){5}$' ||
    die "MAC $mac is not a locally administered address (second hex digit 2, 6, A or E)"

  say "Pushing files"
  sh_dev "mkdir -p $DEV_TMP"
  for s in "${SCRIPTS[@]}" wpa_supplicant-wrapper.sh; do
    adb push "$HERE/device/$s" "$DEV_TMP/$s" >/dev/null
    [ "$(dev_sha "$DEV_TMP/$s")" = "$(sha "$HERE/device/$s")" ] || die "$s did not arrive intact"
  done
  adb push "$tmp/frame-boot.conf" "$DEV_TMP/frame-boot.conf" >/dev/null
  ok "files pushed"

  say "Installing"
  root_script <<EOF
set -e
T=$DEV_TMP
B=/system/bin
grep -v -x '$OLD_HOOK_LINE' \$B/install-recovery.sh | grep -v -x '$HOOK_LINE' > \$T/install-recovery.new
if grep -q 'frame-' \$T/install-recovery.new; then
    echo "    FAIL: install-recovery.sh has other frame- changes. Put back the stock file first."
    exit 1
fi
echo '$HOOK_LINE' >> \$T/install-recovery.new
mount -o remount,rw /system
[ -e \$B/install-recovery.sh.bak ] || cp -p \$B/install-recovery.sh \$B/install-recovery.sh.bak
if [ ! -e \$B/wpa_supplicant.real ]; then
    # Only move the real binary: never move a wrapper script over it.
    [ "\$(dd if=\$B/wpa_supplicant bs=4 count=1 2>/dev/null | od -An -c | tr -d ' ')" = '177ELF' ]
    mv \$B/wpa_supplicant \$B/wpa_supplicant.real
fi
cp \$T/wpa_supplicant-wrapper.sh \$B/wpa_supplicant
chown root:shell \$B/wpa_supplicant
chmod 0755 \$B/wpa_supplicant
for s in ${SCRIPTS[*]}; do
    cp \$T/\$s \$B/\$s
    chown root:shell \$B/\$s
    chmod 0750 \$B/\$s
done
cat \$T/install-recovery.new > \$B/install-recovery.sh
sync
mount -o remount,ro /system || echo "    note: /system stays read-write until the next reboot"
cp \$T/frame-boot.conf $DEV_CONF
chown root:root $DEV_CONF
chmod 0600 $DEV_CONF
rm -rf \$T
echo "    ok: installed"
EOF
  say "Checking the installed files"
  for s in "${SCRIPTS[@]}"; do
    [ "$(dev_sha "/system/bin/$s")" = "$(sha "$HERE/device/$s")" ] || die "/system/bin/$s does not match"
  done
  [ "$(dev_sha /system/bin/wpa_supplicant)" = "$(sha "$HERE/device/wpa_supplicant-wrapper.sh")" ] ||
    die "/system/bin/wpa_supplicant does not match the wrapper"
  sh_dev "tail -n 1 /system/bin/install-recovery.sh" | grep -qx "$HOOK_LINE" || die "install-recovery.sh hook missing"
  ok "scripts, wrapper and hook match"
  printf '\nReboot the frame (power-cycle if adb reboot hangs), then run: %s verify\n' "$0"
}

cmd_verify() {
  cmd_check
  say "This boot"
  local mac conf_mac
  mac="$(sh_dev cat /sys/class/net/wlan0/address)"
  conf_mac="$(sh_dev "grep '^MAC=' $DEV_CONF" | cut -d= -f2)"
  [ "$mac" = "$conf_mac" ] && ok "wlan0 MAC is the configured one" || warn "wlan0 MAC $mac is not $conf_mac"
  ok "address: $(sh_dev 'ip -4 addr show wlan0' | grep -o 'inet [0-9./]*' || echo none)"
  ok "clock: $(sh_dev date)"
  ok "focus: $(sh_dev 'dumpsys window' | grep -o 'mCurrentFocus=[^ ]* [^ ]* [^}]*' | head -1)"
  sh_dev 'logcat -d -v time -s frame-powerfix frame-wifidefer frame-timesync frame-fixmac' |
    grep -v '^-' | sed 's/^/    /'
}

cmd_uninstall() {
  cmd_backup
  say "Removing the boot fixes"
  root_script <<EOF
set -e
B=/system/bin
[ -e \$B/install-recovery.sh.bak ] || { echo "    FAIL: no install-recovery.sh.bak"; exit 1; }
mount -o remount,rw /system
want=\$(/sbin/busybox sha256sum \$B/install-recovery.sh.bak | cut -d' ' -f1)
cp -p \$B/install-recovery.sh.bak \$B/install-recovery.sh
[ "\$(/sbin/busybox sha256sum \$B/install-recovery.sh | cut -d' ' -f1)" = "\$want" ] || { echo "    FAIL: restored install-recovery.sh does not match the backup"; exit 1; }
rm \$B/install-recovery.sh.bak
if [ -e \$B/wpa_supplicant.real ]; then
    [ "\$(dd if=\$B/wpa_supplicant.real bs=4 count=1 2>/dev/null | od -An -c | tr -d ' ')" = '177ELF' ] || { echo "    FAIL: wpa_supplicant.real is not the original binary"; exit 1; }
    mv \$B/wpa_supplicant.real \$B/wpa_supplicant
fi
for s in ${SCRIPTS[*]}; do rm -f \$B/\$s; done
sync
mount -o remount,ro /system || echo "    note: /system stays read-write until the next reboot"
rm -f $DEV_CONF /data/local/frame-lasttime /data/local/frame-nowifi /data/local/frame-empty.ko /data/local/frame-ntpreq /data/local/frame-ntpresp
echo "    ok: removed. Reboot the frame."
EOF
}

case "${1:-}" in
  check) cmd_check ;;
  backup) cmd_backup ;;
  apply) cmd_apply ;;
  verify) cmd_verify ;;
  uninstall) cmd_uninstall ;;
  *) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
