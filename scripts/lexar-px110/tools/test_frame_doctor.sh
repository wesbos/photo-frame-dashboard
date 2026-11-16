#!/bin/bash
# Tests for frame-doctor.sh. Run on the computer; no frame needed and none is touched:
#     bash tools/test_frame_doctor.sh
# adb, mtkclient and the USB listing are replaced by stand-ins; the "frame" is a folder of partition files in a
# temporary directory. Your real images (BACKUP_DIR, BUILD_DIR/out*) are read, never written.
# Needs BACKUP_DIR (your backup) and the built images in BUILD_DIR; without them the whole file is skipped.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
DOC=$HERE/frame-doctor.sh
B=$(python3 -I "$HERE/px110conf.py" get BACKUP_DIR)
REALBUILD=$(python3 -I "$HERE/px110conf.py" get BUILD_DIR)
if [ -z "$B" ] || [ ! -f "$B/frame.sha256" ] || [ ! -f "$B/super.img" ]; then
  echo "SKIP test_frame_doctor.sh: no backup (set BACKUP_DIR in unit.conf; it must hold the .img files and frame.sha256)"; exit 0
fi
for f in out/SHA256SUMS out/product.img out-recovery/recovery-rescue.img out-logo/logo-splash.img out-logo/SHA256SUMS; do
  [ -f "$REALBUILD/$f" ] || { echo "SKIP test_frame_doctor.sh: $f is not built yet in BUILD_DIR"; exit 0; }
done
T=$(mktemp -d "${TMPDIR:-/tmp}/fdtest.XXXXXX") || exit 2
trap 'rm -rf "$T"' EXIT
FAKE=$T/frame; ROOT=$T/root
pass=0; fail=0
ok()  { pass=$((pass+1)); echo "ok   $1"; }
bad() { fail=$((fail+1)); echo "FAIL $1"; [ -n "${2:-}" ] && echo "$2" | sed 's/^/       /' | head -30; }
has() { echo "$OUT" | grep -q -- "$1"; }
check() { if "${@:2}"; then ok "$1"; else bad "$1" "$OUT"; fi; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

# ---- a stand-in build folder: real images by link, its own mtkclient folder and its own out-logo copy
#      (out-boot is left out on purpose: the stand-in frame runs the factory boot)
mkdir -p "$ROOT/mtk/repo" "$ROOT/build/out-logo" "$FAKE/dev" "$FAKE/cache" "$FAKE/sys/mmcblk0p26" "$FAKE/bin" "$FAKE/props"
for d in out out-recovery; do ln -s "$REALBUILD/$d" "$ROOT/build/$d"; done
cp -c "$REALBUILD/out-logo/"* "$ROOT/build/out-logo/" 2>/dev/null || cp "$REALBUILD/out-logo/"* "$ROOT/build/out-logo/"
STAGE=$ROOT/mtk/reads/doctor
TESTSERIAL=TESTFRAME0001

# ---- the stand-in frame: our second image, our logo, our recovery, factory boot
clone() { cp -c "$1" "$2" 2>/dev/null || cp "$1" "$2"; }
reset_frame() {
  clone "$REALBUILD/out-logo/logo-splash.img" "$FAKE/dev/logo"
  clone "$REALBUILD/out-recovery/recovery-rescue.img" "$FAKE/dev/recovery"
  clone "$B/boot.img" "$FAKE/dev/boot"; clone "$B/vbmeta_vendor.img" "$FAKE/dev/vbmeta_vendor"
  clone "$REALBUILD/out/vbmeta.img" "$FAKE/dev/vbmeta"; clone "$REALBUILD/out/vbmeta_system.img" "$FAKE/dev/vbmeta_system"
  clone "$B/para.img" "$FAKE/dev/para"
  rm -f "$FAKE/dev/mmcblk0p26" "$FAKE/dev/super"; clone "$B/super.img" "$FAKE/dev/mmcblk0p26"
  dd if="$REALBUILD/out/product.img" of="$FAKE/dev/mmcblk0p26" bs=4096 seek=32512 conv=notrunc 2>/dev/null
  ln -s mmcblk0p26 "$FAKE/dev/super"
  for n in lk lk2 seccfg tee1 tee2 frp md_udc nvdata nvram proinfo persist preloader; do echo "untouched $n" > "$FAKE/dev/$n"; done
  echo 520704 > "$FAKE/sys/mmcblk0p26/start"
  rm -rf "$FAKE/cache"; mkdir -p "$FAKE/cache"
  echo green > "$FAKE/props/ro.boot.verifiedbootstate"; echo locked > "$FAKE/props/ro.boot.vbmeta.device_state"
  echo bf13b2cc00000000 > "$FAKE/props/ro.boot.vbmeta.digest"; echo 1 > "$FAKE/props/sys.boot_completed"
  echo device > "$FAKE/state"; echo ok > "$FAKE/mtk_mode"; : > "$FAKE/usb"; : > "$FAKE/adb.log"; : > "$FAKE/mtk.log"
  rm -f "$FAKE/after_reboot"
}
protected_sum() { cat "$FAKE"/dev/{lk,lk2,seccfg,tee1,tee2,frp,md_udc,nvdata,nvram,proinfo,persist,preloader} | shasum | cut -d' ' -f1; }

cat > "$FAKE/bin/sha256sum" <<'EOF'
#!/bin/bash
exec shasum -a 256 "$@"
EOF
cat > "$FAKE/bin/getprop" <<'EOF'
#!/bin/bash
cat "$FAKE/props/$1" 2>/dev/null
EOF
cat > "$T/adb" <<'EOF'
#!/bin/bash
# stand-in adb: device scripts run on the computer with the frame's paths pointed at the stand-in folder
echo "adb $*" >> "$FAKE/adb.log"
[ "$1" = "-s" ] && shift 2
st=$(cat "$FAKE/state")
case "$1" in
  devices) echo "List of devices attached"; [ "$st" = absent ] || printf '%s\t%s\n' "$TESTSERIAL" "$st" ;;
  connect) ;;
  reboot) [ -f "$FAKE/after_reboot" ] && cp "$FAKE/after_reboot" "$FAKE/state"; exit 0 ;;
  shell|exec-out)
    case "$st" in device|recovery) ;; *) exit 1 ;; esac
    shift
    s=$(printf '%s' "$*" | sed -e "s#/dev/block/by-name#$FAKE/dev#g" -e "s#/tmp/rescue_[c]ache#$FAKE/absent#g" \
        -e "s#/cache#$FAKE/cache#g" -e "s#/sys/class/block#$FAKE/sys#g")
    PATH="$FAKE/bin:$PATH" bash -c "$s" ;;
  push) cp "$2" "$(printf '%s' "$3" | sed "s#^/cache#$FAKE/cache#")" ;;
esac
EOF
cat > "$T/mtk" <<'EOF'
#!/bin/bash
# stand-in mtkclient: gets the multi string; acts on the stand-in partitions
echo "$1" >> "$FAKE/mtk.log"
mode=$(cat "$FAKE/mtk_mode")
[ "$mode" = miss ] && { sleep 600; exit 1; }
echo "Port - Device detected :)"
IFS=';' read -ra CMDS <<< "$1"
for c in "${CMDS[@]}"; do
  set -- $c
  case "$1" in
    w) cp "$3" "$FAKE/dev/$2" && echo "Wrote $3 to sector x" ;;
    wo) dd if="$4" of="$FAKE/dev/mmcblk0p26" bs=4096 seek=$(( ($2 - 266600448) / 4096 )) conv=notrunc 2>/dev/null && echo "Wrote $4 to offset $2 with length $3." ;;
    r) cp "$FAKE/dev/$2" "$3" && echo "Dumped $2" ;;
    ro) dd if="$FAKE/dev/mmcblk0p26" of="$4" bs=4096 skip=$(( ($2 - 266600448) / 4096 )) count=$(( $3 / 4096 )) 2>/dev/null && echo "Dumped offset" ;;
    reset) [ "$mode" = noreset ] && exit 0
           [ -f "$FAKE/after_reboot" ] && cp "$FAKE/after_reboot" "$FAKE/state"
           echo "Watchdog restart sent. The device should boot by itself." ;;
  esac
done
EOF
cat > "$T/usb" <<'EOF'
#!/bin/bash
cat "$FAKE/usb"
EOF
chmod +x "$T/adb" "$T/mtk" "$T/usb" "$FAKE/bin/"*
export FAKE FRAME_DOCTOR_ADB="$T/adb" FRAME_DOCTOR_MTK="$T/mtk" FRAME_DOCTOR_USBPROBE="$T/usb" FRAME_DOCTOR_FAST=1
export PX110_CONF=/dev/null PX110_BACKUP_DIR="$B" PX110_BUILD_DIR="$ROOT/build" PX110_MTK_DIR="$ROOT/mtk" TESTSERIAL
export ANDROID_SERIAL=$TESTSERIAL   # a made-up serial: the stand-in adb answers to it
unset PX110_SERIAL PX110_GOOD_DIGEST PX110_ADB PX110_LIBUSB_DIR
run() { OUT=$(printf '%s\n' "$ANSWER" | bash "$DOC" "$@" 2>&1); RC=$?; }
ANSWER=yes
no_frame_writes() { ! grep -Eq 'of=|rm -f|mv |: >|push|reboot|mkdir' "$FAKE/adb.log" && [ ! -s "$FAKE/mtk.log" ]; }
product_hash() { dd if="$FAKE/dev/mmcblk0p26" bs=4096 skip=32512 count=26810 2>/dev/null | shasum -a 256 | cut -d' ' -f1; }
STOCK_LOGO=$(awk '$2=="logo.img"{print $1}' "$B/frame.sha256")
OUR_PRODUCT=$(awk '$2=="product.img"{print $1}' "$REALBUILD/out/SHA256SUMS")
STOCK_PRODUCT=c5384ae1b53f444af60ef53735086c5e6c284df42912bbcedb314a2fb560d788

echo "== constants"
OUT=$(awk '$NF=="super"{print $2}' "$B/partition-table.txt")
check "super starts at sector 520704 in the backed-up partition table" [ "$OUT" = 520704 ]
check "product byte offset = 520704*512 + 32512*4096" [ $((520704*512 + 32512*4096)) = "$(sed -n 's/^PRODUCT_ABS=\([0-9]*\).*/\1/p' "$DOC")" ]
check "product length = 26810 blocks" [ $((26810*4096)) = 109813760 ]
OUT=$(dd if="$B/super.img" bs=4096 skip=32512 count=26810 2>/dev/null | shasum -a 256 | cut -d' ' -f1)
check "the stock product hash in the script is the region in the super backup" [ "$OUT" = "$STOCK_PRODUCT" ]

echo "== status"
reset_frame; run status
check "frame with no rescue store: one point to look at, exit 1" [ $RC = 1 -a -n "$(echo "$OUT" | grep 'RESULT: 1 point')" ]
check "healthy frame: state Android, green, locked" has "ANDROID is running"
check "logo recognised as ours" has "logo .*ours, logo (logo-splash.img)"
check "boot recognised as factory" has "boot .*factory (backup) boot"
check "product recognised as our second image" has "product .*ours, second image (product.img)"
check "no store is reported as a point" has "NONE. A restore from recovery"
OUT2=$OUT; run status; OUT=$OUT2
check "status wrote nothing to the frame and never called mtkclient" no_frame_writes
printf 'XXXX' | dd of="$FAKE/dev/logo" bs=1 seek=100 conv=notrunc 2>/dev/null; run status
check "tampered logo: not recognised, exit 1" [ $RC = 1 -a -n "$(echo "$OUT" | grep 'logo .*NOT RECOGNISED')" ]
reset_frame; echo orange > "$FAKE/props/ro.boot.verifiedbootstate"; run status
check "not green is flagged" has "ATTENTION: not green"
reset_frame; echo recovery > "$FAKE/state"; run status
check "recovery state detected" has "RECOVERY is running"
reset_frame; echo absent > "$FAKE/state"; echo "0e8d:2000" > "$FAKE/usb"; run status
check "loader state detected (0e8d:2000)" [ $RC = 2 -a -n "$(echo "$OUT" | grep 'LOADER mode')" ]
echo "0e8d:0003" > "$FAKE/usb"; run status
check "boot ROM state detected (0e8d:0003)" has "BOOT ROM download mode"
echo "05ac:8104" > "$FAKE/usb"; run status
check "nothing on USB detected" [ $RC = 2 -a -n "$(echo "$OUT" | grep 'NOTHING on USB')" ]
reset_frame; echo unauthorized > "$FAKE/state"; run status
check "unauthorized adb reported" has "not allowed in"

echo "== the note in para"
reset_frame; printf 'boot-recovery' | dd of="$FAKE/dev/para" bs=1 conv=notrunc 2>/dev/null; run status
check "our plain note recognised" has "Note in para: OURS"
printf 'recovery\n--wipe_data\n' | dd of="$FAKE/dev/para" bs=1 seek=64 conv=notrunc 2>/dev/null; run status
check "a wipe note is somebody else's" has "SOMEBODY ELSE'S: boot-recovery recovery --wipe_data"
before=$(sha "$FAKE/dev/para"); run clear-note
check "clear-note refuses a foreign note and leaves para alone" [ $RC != 0 -a "$(sha "$FAKE/dev/para")" = "$before" ]
reset_frame; printf 'boot-recovery' | dd of="$FAKE/dev/para" bs=1 conv=notrunc 2>/dev/null
ANSWER=no; run clear-note; ANSWER=yes
check "clear-note without yes changes nothing" [ "$(sha "$FAKE/dev/para")" != "$(sha "$B/para.img")" ]
run clear-note
check "clear-note with yes: para equals the factory copy again (only the note went)" [ $RC = 0 -a "$(sha "$FAKE/dev/para")" = "$(sha "$B/para.img")" ]
run clear-note
check "clear-note with no note: nothing to do" has "Nothing to do"
reset_frame; echo absent > "$FAKE/state"; echo "0e8d:2000" > "$FAKE/usb"; echo device > "$FAKE/after_reboot"
printf 'boot-recovery' | dd of="$FAKE/dev/para" bs=1 conv=notrunc 2>/dev/null; run clear-note
check "clear-note in loader mode writes factory para through mtkclient, with restart" [ "$(cat "$FAKE/mtk.log")" = "w para ../reads/doctor/para.img;reset" -a "$(sha "$FAKE/dev/para")" = "$(sha "$B/para.img")" ]

echo "== never-write list"
reset_frame; psum=$(protected_sum)
for p in preloader lk lk2 seccfg tee1 tee2 tee frp md_udc nvdata nvram proinfo persist rpmb; do
  run restore $p stock
  check "restore $p is refused, mtkclient not called" [ $RC != 0 -a ! -s "$FAKE/mtk.log" -a -n "$(echo "$OUT" | grep 'never-write list')" ]
done
for p in para super userdata vbmeta_vendor dtbo cache "logo;w lk x"; do
  run restore "$p" stock
  check "restore '$p' (not on the allow-list) is refused" [ $RC != 0 -a ! -s "$FAKE/mtk.log" ]
done
run restore logo; check "restore without stock|ours is refused" [ $RC != 0 -a ! -s "$FAKE/mtk.log" ]
run restore logo theirs; check "restore with an unknown family is refused" [ $RC != 0 -a ! -s "$FAKE/mtk.log" ]
run restore boot ours; check "restore boot ours is refused (there is none)" [ $RC != 0 -a ! -s "$FAKE/mtk.log" ]

echo "== restore through the loader port"
reset_frame; ANSWER=no; run factory-logo; ANSWER=yes
check "factory-logo without yes: nothing happens" [ ! -s "$FAKE/mtk.log" -a "$(sha "$FAKE/dev/logo")" != "$STOCK_LOGO" ]
run factory-logo --dry-run
check "factory-logo --dry-run: nothing happens, plan shown" [ ! -s "$FAKE/mtk.log" -a -n "$(echo "$OUT" | grep 'dry run')" -a -n "$(echo "$OUT" | grep 'logo <- factory')" ]
run factory-logo
check "factory-logo: mtkclient gets exactly 'w logo ...;reset'" [ "$(cat "$FAKE/mtk.log")" = "w logo ../reads/doctor/logo.img;reset" ]
check "factory-logo: frame now holds the factory logo, read back, DONE" [ $RC = 0 -a "$(sha "$FAKE/dev/logo")" = "$STOCK_LOGO" -a -n "$(echo "$OUT" | grep '^DONE')" ]
check "factory-logo: the frame was restarted first so the loader shows" grep -q "reboot" "$FAKE/adb.log"
run restore logo ours
check "restore logo ours puts our logo back" [ $RC = 0 -a "$(sha "$FAKE/dev/logo")" = "$(sha "$REALBUILD/out-logo/logo-splash.img")" ]
run restore recovery stock
check "restore recovery stock" [ $RC = 0 -a "$(sha "$FAKE/dev/recovery")" = "$(sha "$B/recovery.img")" ]
run restore vbmeta stock
check "single vbmeta restore carries the family warning" has "only start together as one family"
: > "$FAKE/mtk.log"; run restore-set stock
check "restore-set stock: one job, product by offset, ends in reset" [ "$(cat "$FAKE/mtk.log")" = "wo 399769600 109813760 ../reads/doctor/product.img;w vbmeta_system ../reads/doctor/vbmeta_system.img;w vbmeta ../reads/doctor/vbmeta.img;reset" ]
check "restore-set stock: product region is the factory one" [ $RC = 0 -a "$(product_hash)" = "$STOCK_PRODUCT" ]
check "restore-set stock: the rest of super is untouched" [ "$(sha "$FAKE/dev/mmcblk0p26")" = "$(awk '$2=="super.img"{print $1}' "$B/frame.sha256")" ]
run restore-set ours
check "restore-set ours: product region is ours again" [ $RC = 0 -a "$(product_hash)" = "$OUR_PRODUCT" ]
check "the protected partitions were never changed" [ "$(protected_sum)" = "$psum" ]
check "every mtkclient job ended with the watchdog restart" [ -z "$(grep -v ';reset$' "$FAKE/mtk.log" | grep -v '^reset$')" ]

reset_frame; echo 999 > "$FAKE/sys/mmcblk0p26/start"; run restore product ours
check "product restore refused when super is not where expected" [ $RC != 0 -a ! -s "$FAKE/mtk.log" ]
reset_frame; echo miss > "$FAKE/mtk_mode"; run factory-logo
check "missed loader window: says so, nothing written, non-zero" [ $RC != 0 -a -n "$(echo "$OUT" | grep 'was not caught')" -a "$(sha "$FAKE/dev/logo")" != "$STOCK_LOGO" ]
reset_frame; echo noreset > "$FAKE/mtk_mode"; run factory-logo
check "no restart confirmed: warns about loader mode" has "no watchdog restart was confirmed"
reset_frame; printf 'X' | dd of="$ROOT/build/out-logo/logo-splash.img" bs=1 seek=5000 conv=notrunc 2>/dev/null; run restore logo ours
check "a damaged image on the computer is refused" [ $RC != 0 -a ! -s "$FAKE/mtk.log" -a -n "$(echo "$OUT" | grep 'recorded hash')" ]
clone "$REALBUILD/out-logo/logo-splash.img" "$ROOT/build/out-logo/logo-splash.img" 2>/dev/null
rm -f "$ROOT/build/out-logo/logo-splash.img"; clone "$REALBUILD/out-logo/logo-splash.img" "$ROOT/build/out-logo/logo-splash.img"
reset_frame; echo absent > "$FAKE/state"; echo "0e8d:2000" > "$FAKE/usb"; echo device > "$FAKE/after_reboot"; run factory-logo
check "restore from loader mode (Android dead): works without adb reboot" [ $RC = 0 -a "$(sha "$FAKE/dev/logo")" = "$STOCK_LOGO" ]
check "  ...and adb reboot was not used" [ -z "$(grep ' reboot' "$FAKE/adb.log")" ]

echo "== check and restart through the loader port"
reset_frame; run check
check "check: reads only, ends in reset" [ -z "$(grep -E '(^|;)(w|wo|e|es|wf|wl) ' "$FAKE/mtk.log")" -a -n "$(grep ';reset$' "$FAKE/mtk.log")" ]
check "check: labels what it read" [ -n "$(echo "$OUT" | grep 'product .*ours, second image')" -a -n "$(echo "$OUT" | grep 'recovery .*ours, recovery')" -a -n "$(echo "$OUT" | grep 'note in para: none')" ]
reset_frame; echo absent > "$FAKE/state"; echo "0e8d:2000" > "$FAKE/usb"; echo device > "$FAKE/after_reboot"; run restart
check "restart: job is just 'reset', frame comes back" [ "$(cat "$FAKE/mtk.log")" = "reset" -a -n "$(echo "$OUT" | grep 'DONE: the frame is back')" ]

echo "== safe mode flag"
reset_frame; ANSWER=no; run safe on; ANSWER=yes
check "safe on without yes: no flag" [ ! -e "$FAKE/cache/rescue/safe" ]
run safe on; check "safe on: flag file exists" [ $RC = 0 -a -e "$FAKE/cache/rescue/safe" ]
run status; check "status flags safe mode" has "safe flag is set"
run safe off; check "safe off: flag gone" [ $RC = 0 -a ! -e "$FAKE/cache/rescue/safe" ]
run safe sideways; check "safe with a wrong word is refused" [ $RC != 0 ]
echo absent > "$FAKE/state"; run safe on; check "safe needs adb" [ $RC != 0 ]

echo "== known-good store"
reset_frame; run store
check "store: done" [ $RC = 0 -a -n "$(echo "$OUT" | grep 'DONE: known-good set stored')" ]
L=$FAKE/cache/rescue/list
check "store: list has the header, five entries and end" [ "$(head -1 "$L")" = "rescue-list 1" -a "$(tail -1 "$L")" = "end" -a "$(wc -l < "$L" | tr -d ' ')" = 7 ]
okc=1
while read -r n want f gz good; do
  case "$n" in rescue-list|end) continue ;; esac
  [ "$(sha "$FAKE/cache/rescue/$f")" = "$gz" ] || okc=0
  [ "$(gunzip -c "$FAKE/cache/rescue/$f" | shasum -a 256 | cut -d' ' -f1)" = "$good" ] || okc=0
  [ "$want" = "$good" ] || okc=0
  case "$n" in product) [ "$good" = "$OUR_PRODUCT" ] || okc=0 ;; logo) [ "$good" = "$(sha "$FAKE/dev/logo")" ] || okc=0 ;;
    boot) [ "$good" = "$(sha "$FAKE/dev/boot")" ] || okc=0 ;; vbmeta|vbmeta_system) [ "$good" = "$(sha "$FAKE/dev/$n")" ] || okc=0 ;; *) okc=0 ;; esac
done < "$L"
check "store: every copy has its listed hashes and unpacks to what the frame runs" [ $okc = 1 ]
run status
check "status after store: exit 0, says healthy, list matches the frame" [ $RC = 0 -a -n "$(echo "$OUT" | grep 'RESULT: healthy')" -a "$(echo "$OUT" | grep -c 'matches the frame')" = 5 ]
: > "$FAKE/adb.log"; run store
check "store again: copies kept, only the list is sent" [ $RC = 0 -a "$(grep -c ' push ' "$FAKE/adb.log")" = 1 ]
echo 3 > "$FAKE/cache/rescue/attempts"; run store
check "store removes a leftover attempts counter" [ ! -e "$FAKE/cache/rescue/attempts" ]
run factory-logo; run status
check "after a logo change the list is shown as differing" has "list logo .*DIFFERS from the frame; a restore would write: ours, logo"
printf 'rescue-list 1\nguarded\nend\n' > "$L"; before=$(sha "$L"); run store
check "store refuses while a guarded flash is being checked" [ $RC != 0 -a "$(sha "$L")" = "$before" ]
reset_frame; printf 'XXXX' | dd of="$FAKE/dev/boot" bs=1 seek=100 conv=notrunc 2>/dev/null; run store
check "store refuses when the frame runs something the computer has no copy of" [ $RC != 0 -a ! -e "$FAKE/cache/rescue/list" ]
reset_frame; echo red > "$FAKE/props/ro.boot.verifiedbootstate"; run store
check "store refuses when the frame is not green" [ $RC != 0 -a ! -e "$FAKE/cache/rescue/list" ]
reset_frame; ANSWER=no; run store; ANSWER=yes
check "store without yes: nothing stored" [ ! -e "$FAKE/cache/rescue/list" ]

echo "== misc"
run help; check "help prints the usage" has "frame-doctor.sh restore"
run frobnicate; check "unknown command refused" [ $RC != 0 ]

echo; echo "passed $pass, failed $fail"
[ $fail = 0 ]
