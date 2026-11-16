#!/bin/bash
# Frame doctor: one command on the computer that says what state the Lexar PX-110 is in and can repair it.
# Firmware PF1106_V2.06_20250527 only: the partition sizes and the place of product inside super are fixed below.
#
#   frame-doctor.sh [status]              what the frame is doing and whether everything matches (reads only)
#   frame-doctor.sh check                 the same hashes read through the loader port (works when Android is dead)
#   frame-doctor.sh restore <part> <stock|ours>   write one partition back through the loader port
#   frame-doctor.sh restore-set <stock|ours>      product + vbmeta_system + vbmeta together (they must match)
#   frame-doctor.sh factory-logo          = restore logo stock
#   frame-doctor.sh safe on|off           set or remove the safe-start flag in /cache/rescue
#   frame-doctor.sh store                 store the known-good set (what the frame runs now) in /cache/rescue
#   frame-doctor.sh clear-note            clear our own note in para
#   frame-doctor.sh restart               free a frame that is stuck in loader mode (watchdog restart)
#   add --dry-run to see what a fix would do without doing it
#
# Every fix asks first; only the word "yes" goes ahead. <part> is one of: logo recovery boot vbmeta
# vbmeta_system product. Nothing else can be written: never the preloader, lk, lk2, seccfg, tee, frp, md_udc,
# nvdata, nvram, proinfo, persist or rpmb. Every loader-port job ends with the watchdog restart.
#
# Settings come from unit.conf beside the tools folder (copy unit.conf.example), or from the environment, where
# PX110_<NAME> wins: SERIAL (or ANDROID_SERIAL), BACKUP_DIR, BUILD_DIR, MTK_DIR, ADB, LIBUSB_DIR, GOOD_DIGEST.
#   BACKUP_DIR  your own backup: <partition>.img files, frame.sha256 ("<sha256>  <name>.img" lines) and
#               partition-table.txt
#   BUILD_DIR   where build.py, recbuild.py, bootbuild.py and logo-from-splash.py wrote (out/, out-recovery/,
#               out-boot/, out-logo/, each with its SHA256SUMS)
#   MTK_DIR     a folder holding repo/ (mtkclient with mtkclient-px110.patch applied) and venv/ (its Python).
#               The doctor stages files in MTK_DIR/reads/doctor.
# Stand-ins for tests (see test_frame_doctor.sh): FRAME_DOCTOR_ADB, FRAME_DOCTOR_MTK, FRAME_DOCTOR_USBPROBE,
# FRAME_DOCTOR_FAST.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
BASE=$(cd "$HERE/.." && pwd)
CONF=${PX110_CONF:-$BASE/unit.conf}
conf() {   # conf NAME [default]: environment PX110_NAME, else the line NAME=value in unit.conf, else the default
  local n="PX110_$1" v
  v=${!n:-}
  if [ -z "$v" ] && [ -f "$CONF" ]; then
    v=$(sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$CONF" | tail -1 | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/")
  fi
  printf '%s' "${v:-${2:-}}"
}
conf_path() {   # the same for a folder or file: ~ is expanded, a relative path is taken from BASE
  local v; v=$(conf "$1" "${2:-}")
  case "$v" in "") ;; "~/"*) v=$HOME/${v#\~/} ;; /*) ;; *) v=$BASE/$v ;; esac
  printf '%s' "$v"
}
ADB_BIN=${FRAME_DOCTOR_ADB:-$(conf ADB adb)}
SERIAL=${ANDROID_SERIAL:-$(conf SERIAL)}      # this frame's adb serial: no default, it is yours alone
BUILD=$(conf_path BUILD_DIR build)
MTKDIR=$(conf_path MTK_DIR)
STAGE=$MTKDIR/reads/doctor              # no spaces below repo/: mtkclient splits its commands on spaces
BACKUP=$(conf_path BACKUP_DIR)
LIBUSB=$(conf_path LIBUSB_DIR)
FAST=${FRAME_DOCTOR_FAST:-}
DRY=
GOOD_DIGEST=$(conf GOOD_DIGEST)          # optional: start of ro.boot.vbmeta.digest of the set you flashed (run_tests.sh prints it)

ALLOWED="logo recovery boot vbmeta vbmeta_system product"
NEVER="preloader lk lk2 seccfg tee1 tee2 tee frp md_udc nvdata nvram proinfo persist rpmb"
PRODUCT_SKIP=32512                       # product inside super: 4096-byte blocks 32512..59321
PRODUCT_COUNT=26810
SUPER_START=520704                       # super's first 512-byte sector (partition-table.txt in the backup)
PRODUCT_ABS=399769600                    # = 520704*512 + 32512*4096, byte offset on the eMMC
STOCK_PRODUCT=c5384ae1b53f444af60ef53735086c5e6c284df42912bbcedb314a2fb560d788   # that region in the super backup
NOTE_CMD=626f6f742d7265636f76657279      # "boot-recovery"
NOTE_ARG_PLAIN=7265636f766572790a        # "recovery\n"
NOTE_ARG_EXIT=7265636f766572790a2d2d6a7573745f657869740a   # "recovery\n--just_exit\n"

# Runs on the frame before every device script: where the partitions and the rescue store are.
PRE='B=/dev/block/by-name; [ -e $B/boot ] || B=/dev/block/platform/soc/11120000.mmc/by-name; C=/cache; [ -d /tmp/rescue_cache/rescue ] && C=/tmp/rescue_cache; '

say() { printf '%s\n' "$*"; }
die() { say "STOP: $*"; exit 1; }
nap() { [ -n "$FAST" ] || sleep "$1"; }
adb() { "$ADB_BIN" -s "$SERIAL" "$@" < /dev/null; }   # never let adb read the answer meant for confirm
dsh() { adb shell "$PRE$1" 2>/dev/null | tr -d '\r'; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
size_of() {
  case "$1" in
    logo) echo 8388608 ;; recovery|boot) echo 33554432 ;; vbmeta|vbmeta_system|vbmeta_vendor) echo 4194304 ;;
    product) echo 109813760 ;; para) echo 524288 ;; *) echo 0 ;;
  esac
}
need_backup() { [ -n "$BACKUP" ] && [ -d "$BACKUP" ] || die "BACKUP_DIR is not set or is not a folder (unit.conf or PX110_BACKUP_DIR): the doctor compares against your own backup"; }
need_serial() {   # every path that writes, or that judges the frame over adb, must know which frame it is talking to
  [ -n "$SERIAL" ] || die "SERIAL is not set (unit.conf, PX110_SERIAL or ANDROID_SERIAL). Without it the doctor cannot see the frame over adb, so it could not check where product sits or read a write back. Nothing was done."
}
need_mtk() {
  [ -n "${FRAME_DOCTOR_MTK:-}" ] && [ -n "$MTKDIR" ] && return 0
  [ -n "$MTKDIR" ] && [ -f "$MTKDIR/repo/mtk.py" ] && [ -x "$MTKDIR/venv/bin/python" ] ||
    die "MTK_DIR is not set up (unit.conf or PX110_MTK_DIR): it must hold repo/mtk.py (patched mtkclient) and venv/bin/python"
}
in_list() { local x; for x in $2; do [ "$x" = "$1" ] && return 0; done; return 1; }

confirm() {   # confirm <what will happen>; only "yes" goes ahead
  say ""; say "ABOUT TO: $1"
  if [ -n "$DRY" ]; then say "(dry run: not done)"; return 1; fi
  printf 'Type yes to go ahead: '
  local a=""; read -r a || true
  [ "$a" = "yes" ] && return 0
  say "Not done."; return 1
}

# ---------------------------------------------------------------- what is on USB
usb_ids() {   # prints vendor:product (hex) of every USB device on this computer (macOS ioreg)
  if [ -n "${FRAME_DOCTOR_USBPROBE:-}" ]; then "$FRAME_DOCTOR_USBPROBE"; return; fi
  ioreg -p IOUSB -l -w0 2>/dev/null | awk '
    function flush() { if (v != "" && p != "") printf "%04x:%04x\n", v, p; v = ""; p = "" }
    /\+-o / { flush() }
    /"idVendor" = /  { v = $NF }
    /"idProduct" = / { p = $NF }
    END { flush() }'
}

detect_state() {   # sets STATE: android | recovery | unauthorized | loader | brom | nothing
  local line st
  case "$SERIAL" in *:*) "$ADB_BIN" connect "$SERIAL" >/dev/null 2>&1 ;; esac
  line=$("$ADB_BIN" devices 2>/dev/null | tr -d '\r' | awk -v s="$SERIAL" '$1 == s { print $2 }')
  st=nothing
  case "$line" in
    device) st=android ;; recovery) st=recovery ;; unauthorized|offline) st=unauthorized ;;
  esac
  if [ "$st" = nothing ]; then
    local ids; ids=$(usb_ids)
    if echo "$ids" | grep -qi '^0e8d:2000$'; then st=loader
    elif echo "$ids" | grep -qi '^0e8d:0003$'; then st=brom; fi
  fi
  STATE=$st
}

# ---------------------------------------------------------------- known hashes on this computer
known_table() {   # prints "<sha256> <label>" for every image this computer has a record of
  local f
  [ -f "$BACKUP/frame.sha256" ] && awk '{ sub(/\.img$/, "", $2); print $1, "factory (backup) " $2 }' "$BACKUP/frame.sha256"
  echo "$STOCK_PRODUCT factory (backup) product"
  for f in out:"ours, second image" out-logo:"ours, logo" out-recovery:"ours, recovery" out-boot:"ours, boot"; do
    [ -f "$BUILD/${f%%:*}/SHA256SUMS" ] && awk -v l="${f#*:}" '{ print $1, l " (" $2 ")" }' "$BUILD/${f%%:*}/SHA256SUMS"
  done
}
label_of() {   # label_of <sha256> [<partition name>] -> label, or "NOT RECOGNISED"
  local l
  l=$(known_table | awk -v h="$1" -v p="${2:-}" '$1 == h { $1 = ""; sub(/^ /, ""); if (p == "" || index($0, p)) { print; exit } }')
  [ -n "$l" ] || l=$(known_table | awk -v h="$1" '$1 == h { $1 = ""; sub(/^ /, ""); print; exit }')
  echo "${l:-NOT RECOGNISED}"
}

# source_for <part> <stock|ours>: sets SRC (file) and SRC_SHA (hash it must have); stock product is cut from super
source_for() {
  local part=$1 fam=$2 dir name
  SRC=""; SRC_SHA=""
  if [ "$fam" = stock ]; then
    if [ "$part" = product ]; then
      SRC=$STAGE/stock-product.img; SRC_SHA=$STOCK_PRODUCT
      mkdir -p "$STAGE"
      [ -f "$SRC" ] && [ "$(sha "$SRC")" = "$SRC_SHA" ] ||
        dd if="$BACKUP/super.img" of="$SRC" bs=4096 skip=$PRODUCT_SKIP count=$PRODUCT_COUNT 2>/dev/null
    else
      SRC=$BACKUP/$part.img
      SRC_SHA=$(awk -v n="$part.img" '$2 == n { print $1 }' "$BACKUP/frame.sha256" 2>/dev/null)
    fi
  elif [ "$fam" = ours ]; then
    case "$part" in
      logo) dir=out-logo; name=logo-splash.img ;;  # our logo is the splash picture (logo-from-splash.py)
      recovery) dir=out-recovery; name=recovery-rescue.img ;;
      vbmeta|vbmeta_system|product) dir=out; name=$part.img ;;
      boot) dir=out-boot; name=boot-wrap-recovery.img ;;  # the note-arming wrapper (factory boot = restore boot stock)
    esac
    SRC=$BUILD/$dir/$name
    SRC_SHA=$(awk -v n="$name" '$2 == n { print $1 }' "$BUILD/$dir/SHA256SUMS" 2>/dev/null)
  else
    die "say which copy: stock (your factory backup) or ours (the images you built)"
  fi
  [ -f "$SRC" ] || die "the file for $part ($fam) is missing: $SRC"
  [ -n "$SRC_SHA" ] || die "no recorded hash for $part ($fam); refusing to write a file nothing vouches for"
  [ "$(wc -c < "$SRC" | tr -d ' ')" = "$(size_of "$part")" ] || die "$SRC is not $(size_of "$part") bytes"
  [ "$(sha "$SRC")" = "$SRC_SHA" ] || die "$SRC does not have its recorded hash $SRC_SHA"
}

# ---------------------------------------------------------------- reading the frame over adb
read_live() {   # fills LIVE with "name hash" lines read from the running frame
  LIVE=$(dsh 'for p in logo recovery boot vbmeta vbmeta_system vbmeta_vendor; do echo "$p $(sha256sum < $B/$p | cut -d" " -f1)"; done; echo "product $(dd if=$B/super bs=4096 skip='$PRODUCT_SKIP' count='$PRODUCT_COUNT' 2>/dev/null | sha256sum | cut -d" " -f1)"')
}
live_hash() { echo "$LIVE" | awk -v n="$1" '$1 == n { print $2 }'; }

read_note() {   # sets NOTE: empty | ours | just_exit | foreign | unreadable ; NOTE_TEXT for a foreign one
  local hex cmd args
  hex=$(adb exec-out "$PRE"'dd if=$B/para bs=2048 count=1 2>/dev/null' 2>/dev/null | xxd -p | tr -d '\n')
  NOTE_TEXT=""
  if [ ${#hex} -ne 4096 ]; then NOTE=unreadable; return; fi
  if [ -z "$(echo "$hex" | tr -d '0')" ]; then NOTE=empty; return; fi
  cmd=$(echo "${hex:0:64}" | sed 's/\(00\)*$//'); args=$(echo "${hex:128:1536}" | sed 's/\(00\)*$//')
  if [ "$cmd" = "$NOTE_CMD" ] && { [ -z "$args" ] || [ "$args" = "$NOTE_ARG_PLAIN" ]; }; then NOTE=ours
  elif [ "$cmd" = "$NOTE_CMD" ] && [ "$args" = "$NOTE_ARG_EXIT" ]; then NOTE=just_exit
  else NOTE=foreign; NOTE_TEXT=$(echo "${hex:0:1664}" | xxd -r -p | tr -c '[:print:]' ' ' | tr -s ' '); fi
}

layout_ok() {   # is super still where the product offset assumes? (only checkable over adb)
  local s
  s=$(dsh 'S=$(readlink $B/super); cat /sys/class/block/${S##*/}/start')
  [ "$s" = "$SUPER_START" ]
}

# ---------------------------------------------------------------- status
cmd_status() {
  need_backup
  [ -n "$SERIAL" ] || say "note: SERIAL is not set (unit.conf or ANDROID_SERIAL), so adb cannot be asked about this frame."
  detect_state
  local problems=0
  say "Frame doctor, $(date '+%d %b %Y %H:%M')"
  case "$STATE" in
    nothing) say "State: NOTHING on USB (no adb device $SERIAL, no MediaTek loader)."
             say "  Check the cable and power. If the screen is dark and stays dark, start 'frame-doctor.sh check':"
             say "  it waits for the loader, which shows for 2-3 seconds at every power-on."
             return 2 ;;
    loader)  say "State: LOADER mode (MediaTek preloader 0e8d:2000 on USB)."
             say "  This shows for 2-3 seconds at every restart. If it stays, the frame is stuck there:"
             say "  'frame-doctor.sh restart' frees it; 'frame-doctor.sh check' reads its partitions first."
             return 2 ;;
    brom)    say "State: BOOT ROM download mode (0e8d:0003). The preloader did not start."
             say "  This is the deepest fallback and it is untested on this frame (docs/lexar-pexar-px-110.md, Not tested). Nothing is done here."
             return 2 ;;
    unauthorized) say "State: adb sees the frame but is not allowed in (unauthorized or offline). Replug the cable."
             return 2 ;;
    android) say "State: ANDROID is running (adb)." ;;
    recovery) say "State: RECOVERY is running (adb in recovery). Android did not start, or recovery was asked for." ;;
  esac

  local vb dg lock boot
  vb=$(dsh 'getprop ro.boot.verifiedbootstate'); dg=$(dsh 'getprop ro.boot.vbmeta.digest')
  lock=$(dsh 'getprop ro.boot.vbmeta.device_state'); boot=$(dsh 'getprop sys.boot_completed')
  say ""
  say "Verified boot: ${vb:-?}, bootloader ${lock:-?}, digest ${dg:-?}"
  [ "$vb" = green ] || { say "  ATTENTION: not green."; problems=$((problems+1)); }
  [ "$lock" = locked ] || { say "  ATTENTION: bootloader not reported as locked."; problems=$((problems+1)); }
  if [ -n "$GOOD_DIGEST" ]; then
    case "$dg" in $GOOD_DIGEST*) say "  digest is the one recorded for our second image with the boot wrapper." ;;
      *) say "  note: digest differs from the recorded $GOOD_DIGEST... (expected after any vbmeta change)." ;; esac
  fi
  [ "$STATE" = android ] && say "Android start-up finished: $([ "$boot" = 1 ] && echo yes || echo 'NOT YET')"

  say ""; say "Partitions (hash on the frame = which known image):"
  read_live
  local p h l
  for p in logo recovery boot vbmeta vbmeta_system vbmeta_vendor product; do
    h=$(live_hash $p)
    if [ -z "$h" ]; then l="COULD NOT READ"; else l=$(label_of "$h" "$p"); fi
    printf '  %-14s %.12s  %s\n' "$p" "${h:-------------}" "$l"
    case "$l" in "NOT RECOGNISED"|"COULD NOT READ") problems=$((problems+1)) ;; esac
  done

  read_note; say ""
  case "$NOTE" in
    empty) say "Note in para: none." ;;
    ours) say "Note in para: OURS (plain boot-recovery). Normal while a start is still being judged; if it stays,"
          say "  the next restart goes to our recovery (the ladder)." ;;
    just_exit) say "Note in para: ours with --just_exit (recovery will start once and come straight back)." ;;
    foreign) say "Note in para: SOMEBODY ELSE'S: $NOTE_TEXT"; say "  (a factory reset or update is pending; the doctor leaves it alone)"; problems=$((problems+1)) ;;
    *) say "Note in para: could not be read."; problems=$((problems+1)) ;;
  esac

  say ""; say "Rescue store (/cache/rescue):"
  local store
  store=$(dsh 'R=$C/rescue; if [ ! -d $R ]; then echo "none"; else
      echo "rung $(cat $R/rung 2>/dev/null)"; [ -e $R/safe ] && echo "safe yes" || echo "safe no"
      echo "attempts $(cat $R/attempts 2>/dev/null)"; [ -e $R/stay ] && echo "stay $(cat $R/stay)"
      [ -f $R/list ] && sed "s/^/list /" $R/list; ls $R | sed "s/^/file /"; fi
      [ -f $C/rescue.marker ] && sed "s/^/marker /" $C/rescue.marker')
  if [ "$store" = none ] || [ -z "$store" ]; then
    say "  NONE. A restore from recovery has nothing to work with ('frame-doctor.sh store' makes one)."
    problems=$((problems+1))
  else
    local rung safe att
    rung=$(echo "$store" | awk '$1 == "rung" { print $2 }'); att=$(echo "$store" | awk '$1 == "attempts" { print $2 }')
    safe=$(echo "$store" | awk '$1 == "safe" { print $2 }')
    say "  ladder rung: ${rung:-0 (no failed starts counted)}    safe-start flag: $safe    restore tries: ${att:-0}"
    [ "$safe" = yes ] && say "  ATTENTION: the safe flag is set: Android starts in safe mode until it is removed ('safe off')."
    echo "$store" | grep -q '^stay ' && say "  a 'stay' file is present: recovery will wait before going home."
    echo "$store" | grep -q '^list guarded$' && say "  the list is marked 'guarded': a flash is being checked."
    if ! echo "$store" | grep -q '^list end$'; then
      say "  ATTENTION: no complete list."; problems=$((problems+1))
    else
      echo "$store" | awk '$1 == "list" && NF == 6 { print $2, $3, $4, $6 }' | while read -r p want file good; do
        h=$(live_hash "$p")
        if [ "$h" = "$want" ]; then l="matches the frame"
        else l="DIFFERS from the frame; a restore would write: $(label_of "$good" "$p")"; fi
        printf '  list %-14s expects %.12s  copy %-18s %s\n' "$p" "$want" "$file" "$l"
      done
    fi
    echo "$store" | grep -q '^marker ' && { say "  last recovery run:"; echo "$store" | sed -n 's/^marker /    /p'; }
  fi

  say ""
  if [ $problems -eq 0 ] && [ "$STATE" = android ]; then say "RESULT: healthy. Nothing needs doing."; return 0; fi
  say "RESULT: $problems point(s) need a look (marked above)."
  return 1
}

# ---------------------------------------------------------------- loader-port jobs
# mtk_job <commands separated by ;>   Always ends with the watchdog restart. Returns 0 if the restart was sent.
mtk_job() {
  need_mtk
  local cmds="${1:+$1;}reset" log=$STAGE/last-job.log pid waited=0 limit=90
  mkdir -p "$STAGE"; : > "$log"
  say "Loader-port job: $cmds"
  detect_state
  (
    cd "$MTKDIR/repo" || exit 9
    if [ -n "${FRAME_DOCTOR_MTK:-}" ]; then exec "$FRAME_DOCTOR_MTK" "$cmds"
    else [ -n "$LIBUSB" ] && export DYLD_FALLBACK_LIBRARY_PATH="$LIBUSB"
      exec ../venv/bin/python mtk.py --serialport DETECT multi "$cmds"; fi
  ) > "$log" 2>&1 &
  pid=$!
  case "$STATE" in
    android|recovery) nap 3
      # Our own restarts must not count as failed starts. Before the start guard's all clear (5 min), the
      # note is armed and rung counts, so two doctor restarts put the frame in safe mode. Clear rung/attempts and our
      # own plain note first (never `safe`, never anybody else's note).
      dsh 'rm -f $C/rescue/rung $C/rescue/attempts; sync; P=$B/para; T=$C/rescue; mkdir -p $T
{ printf boot-recovery; dd if=/dev/zero bs=2035 count=1 2>/dev/null; } > $T/.n; dd if=$P of=$T/.c bs=2048 count=1 2>/dev/null
cmp -s $T/.c $T/.n && dd if=/dev/zero of=$P bs=2048 count=1 conv=notrunc 2>/dev/null; sync; rm -f $T/.n $T/.c' >/dev/null
      say "Restarting the frame so the loader shows..."; adb reboot >/dev/null 2>&1 ;;
    loader) say "The frame is already in loader mode." ;;
    *) say "Waiting for the loader: plug the frame in, or switch its power off and on, now." ; limit=300 ;;
  esac
  while kill -0 $pid 2>/dev/null; do
    if ! grep -q "Device detected" "$log" && [ $waited -ge $limit ]; then
      kill $pid 2>/dev/null; wait $pid 2>/dev/null
      say "The loader was not caught within $limit s (its window is 2-3 s; this happens). Nothing was written."
      say "The frame has simply started normally. Run the same command again."
      return 1
    fi
    [ -n "$FAST" ] && sleep 0.05 || sleep 1
    waited=$((waited+1))
    [ $((waited % 30)) -eq 0 ] && say "  ...still working ($waited s)"
  done
  wait $pid 2>/dev/null
  grep -E "^(Wrote|Failed|Dumped|Watchdog)" "$log" | sed 's/^/  mtkclient: /'
  if grep -q "^Failed" "$log"; then say "ATTENTION: mtkclient reported a failed step (log: $log)."; fi
  if grep -q "Watchdog restart sent" "$log"; then return 0; fi
  say "ATTENTION: no watchdog restart was confirmed. The frame may be sitting in loader mode:"
  say "  run 'frame-doctor.sh restart', or unplug and replug it. Log: $log"
  return 1
}

wait_for_adb() {   # waits until adb sees the frame again; sets STATE
  local n=0 max=90; [ -n "$FAST" ] && max=3
  say "Waiting for the frame to come back..."
  while [ $n -lt $max ]; do
    detect_state
    case "$STATE" in android|recovery) return 0 ;; esac
    nap 2; n=$((n+1))
  done
  return 1
}

stage() {   # stage <src> <name>: copy into the staging folder (no spaces in its mtkclient-relative path), re-check
  mkdir -p "$STAGE"
  [ "$1" = "$STAGE/$2" ] || cp -c "$1" "$STAGE/$2" 2>/dev/null || cp "$1" "$STAGE/$2" || die "could not stage $1"
  [ "$(sha "$STAGE/$2")" = "$SRC_SHA" ] || die "the staged copy of $2 is damaged"
}
write_cmd() {   # write_cmd <part> <staged name>: the mtkclient command that writes it
  if [ "$1" = product ]; then echo "wo $PRODUCT_ABS $(size_of product) ../reads/doctor/$2"
  else echo "w $1 ../reads/doctor/$2"; fi
}

do_restore() {   # do_restore <family> <part>...
  local fam=$1; shift
  local p cmds="" plan="" names="" before=""
  for p in "$@"; do
    in_list "$p" "$NEVER" && die "'$p' is on the never-write list. The doctor will not touch it."
    in_list "$p" "$ALLOWED" || die "'$p' is not a partition the doctor may write. Allowed: $ALLOWED"
  done
  need_serial; need_backup; need_mtk
  detect_state
  case "$STATE" in unauthorized|brom) die "the frame is in a state the doctor cannot work from ($STATE); run status" ;; esac
  if [ "$STATE" = android ] || [ "$STATE" = recovery ]; then
    read_live
    if in_list product "$*" && ! layout_ok; then die "super is not where the product offset assumes; refusing to write product"; fi
  fi
  for p in "$@"; do
    source_for "$p" "$fam"
    stage "$SRC" "$p.img"
    cmds="${cmds:+$cmds;}$(write_cmd "$p" "$p.img")"
    [ "$STATE" = android ] || [ "$STATE" = recovery ] && before=" (frame now has $(label_of "$(live_hash "$p")" "$p"))"
    plan="$plan
   - $p <- $(label_of "$SRC_SHA" "$p"), ${SRC_SHA:0:12}...$before"
    names="$names $p:$SRC_SHA"
  done
  local warn=""
  if [ $# -eq 1 ] && in_list "$1" "vbmeta vbmeta_system product"; then
    warn="
   WARNING: vbmeta, vbmeta_system and product only start together as one family (all stock or all ours).
   Writing one alone is right only if the other two are already that family. 'restore-set' writes all three."
  fi
  if in_list product "$*" && [ "$STATE" != android ] && [ "$STATE" != recovery ]; then
    warn="$warn
   NOTE: with Android down the doctor cannot re-check where product sits; it uses the recorded offset."
  fi
  confirm "write through the loader port and restart the frame:$plan$warn" || return 1
  mtk_job "$cmds" || return 1
  if ! wait_for_adb; then
    say "The frame has not come back on adb. Run 'frame-doctor.sh status' in a minute; if it shows loader mode, 'restart'."
    return 1
  fi
  read_live
  local bad=0 n want
  for n in $names; do
    p=${n%%:*}; want=${n#*:}
    if [ "$(live_hash "$p")" = "$want" ]; then say "  $p: read back from the frame, correct."
    else say "  $p: READ-BACK DIFFERS (frame has $(live_hash "$p"))."; bad=1; fi
  done
  say "Verified boot now: $(dsh 'getprop ro.boot.verifiedbootstate')"
  [ $bad -eq 0 ] && say "DONE." || say "NOT RIGHT: run status and try again."
  return $bad
}

cmd_check() {   # deep check through the loader port: works whatever Android is doing
  local p cmds="" h l
  need_backup; need_mtk
  confirm "read logo, recovery, boot, vbmeta, vbmeta_system, vbmeta_vendor, para and product through the loader port
   (nothing is written; the frame restarts once)" || return 1
  mkdir -p "$STAGE"
  for p in logo recovery boot vbmeta vbmeta_system vbmeta_vendor para; do
    rm -f "$STAGE/read-$p.bin"; cmds="${cmds:+$cmds;}r $p ../reads/doctor/read-$p.bin"
  done
  rm -f "$STAGE/read-product.bin"
  cmds="$cmds;ro $PRODUCT_ABS $(size_of product) ../reads/doctor/read-product.bin"
  mtk_job "$cmds"
  say ""; say "Read through the loader port:"
  for p in logo recovery boot vbmeta vbmeta_system vbmeta_vendor product para; do
    if [ -s "$STAGE/read-$p.bin" ]; then h=$(sha "$STAGE/read-$p.bin"); l=$(label_of "$h" "$p"); else h=""; l="NOT READ"; fi
    printf '  %-14s %.12s  %s\n' "$p" "${h:-------------}" "$l"
  done
  if [ -s "$STAGE/read-para.bin" ]; then
    if [ -z "$(head -c 2048 "$STAGE/read-para.bin" | xxd -p | tr -d '0\n')" ]; then say "  note in para: none"
    else say "  note in para: $(head -c 832 "$STAGE/read-para.bin" | tr -c '[:print:]' ' ' | tr -s ' ')"; fi
  fi
}

cmd_restart() {
  need_mtk
  confirm "send the watchdog restart through the loader port (nothing is written)" || return 1
  mtk_job "" && wait_for_adb && say "DONE: the frame is back ($STATE)."   # mtk_job adds the restart itself
}

# ---------------------------------------------------------------- fixes over adb
need_adb() { detect_state; case "$STATE" in android|recovery) ;; *) die "this needs the frame on adb (Android or our recovery); it is: $STATE" ;; esac; }

cmd_safe() {
  need_serial
  need_adb
  case "${1:-}" in
    on) confirm "set the safe-start flag (/cache/rescue/safe): from the next restart Android starts in safe mode
   (firewall and adb only, no kiosk) until the flag is removed" || return 1
        dsh 'mkdir -p $C/rescue && echo manual > $C/rescue/safe && sync; [ -e $C/rescue/safe ] && echo SET' | grep -q SET && say "DONE: flag set (manual: stays until 'safe off')." || die "could not set the flag" ;;
    off) confirm "full reset: remove the safe-start flag and the ladder counters (rung, attempts), and clear our recovery note in para (never anybody else's): the next restart is a normal start" || return 1
        # Removing only the flag left rung 2 and the armed note, so the next restart went to recovery and stayed.
        local out
        out=$(dsh 'rm -f $C/rescue/safe $C/rescue/rung $C/rescue/attempts; sync; P=$B/para; T=$C/rescue
dd if=/dev/zero of=$T/.z bs=2048 count=1 2>/dev/null; { printf boot-recovery; dd if=/dev/zero bs=2035 count=1 2>/dev/null; } > $T/.n
dd if=$P of=$T/.c bs=2048 count=1 2>/dev/null
if cmp -s $T/.c $T/.n; then dd if=$T/.z of=$P bs=2048 count=1 conv=notrunc 2>/dev/null; sync; dd if=$P of=$T/.c bs=2048 count=1 2>/dev/null; cmp -s $T/.c $T/.z && echo NOTE-CLEARED || echo NOTE-STUCK
elif cmp -s $T/.c $T/.z; then echo NOTE-NONE; else echo NOTE-FOREIGN; fi; rm -f $T/.z $T/.n $T/.c
[ -e $C/rescue/safe ] || echo GONE')
        echo "$out" | grep -q GONE || die "could not remove the flag"
        case $out in
          *NOTE-CLEARED*|*NOTE-NONE*) say "DONE: safe mode off, counters removed, no recovery note left." ;;
          *NOTE-FOREIGN*) say "DONE: safe mode off and counters removed; para holds somebody else's note (a pending factory reset?), left alone." ;;
          *) die "flag removed, but our note in para did not clear: the next restart may go to recovery" ;;
        esac ;;
    *) die "say: safe on   or   safe off" ;;
  esac
}

cmd_clear_note() {
  need_serial
  detect_state
  if [ "$STATE" = loader ] || [ "$STATE" = nothing ]; then
    need_backup; need_mtk
    SRC=$BACKUP/para.img; SRC_SHA=$(awk '$2 == "para.img" { print $1 }' "$BACKUP/frame.sha256")
    [ -f "$SRC" ] && [ "$(sha "$SRC")" = "$SRC_SHA" ] || die "the para backup is missing or damaged"
    stage "$SRC" para.img
    confirm "write the factory copy of para (which holds no note) through the loader port and restart the frame" || return 1
    mtk_job "w para ../reads/doctor/para.img"; return
  fi
  need_adb; read_note
  case "$NOTE" in
    empty) say "There is no note in para. Nothing to do."; return 0 ;;
    foreign) die "the note is not ours ($NOTE_TEXT). A reset or update is pending; the doctor will not remove it." ;;
    unreadable) die "para could not be read" ;;
  esac
  confirm "zero the first 2048 bytes of para (our note: $NOTE). Nothing else in para is written" || return 1
  dsh 'dd if=/dev/zero of=$B/para bs=2048 count=1 conv=notrunc,fsync 2>/dev/null; sync'
  read_note
  [ "$NOTE" = empty ] && say "DONE: the note is cleared (read back)." || die "the note is still there ($NOTE)"
}

cmd_store() {   # store what the frame runs now as the known-good set, from this computer's own copies
  need_serial; need_backup; need_mtk    # need_mtk: a stock product copy is cut from the backup into MTK_DIR/reads/doctor
  need_adb
  [ "$STATE" = android ] || die "store the set from a running Android, so that what is stored is known to start"
  [ "$(dsh 'getprop ro.boot.verifiedbootstate')" = green ] || die "the frame is not green; not storing this as known-good"
  [ "$(dsh 'getprop sys.boot_completed')" = 1 ] || die "Android has not finished starting; try again in a minute"
  local old; old=$(dsh 'cat $C/rescue/list 2>/dev/null')
  echo "$old" | grep -q '^guarded$' && die "the list on the frame is marked 'guarded': a flash is being checked. Not touching it."
  read_live
  local tmp p h f fam src plan="" lines="" push=""
  tmp=$(mktemp -d) || die "no temp folder"
  for p in product vbmeta_system vbmeta logo boot; do
    h=$(live_hash $p); src=""
    for fam in ours stock; do
      # (boot: both families; ours = the wrapper image in out-boot)
      ( source_for $p $fam ) >/dev/null 2>&1 || continue
      source_for $p $fam
      [ "$SRC_SHA" = "$h" ] && { src=$SRC; break; }
    done
    [ -n "$src" ] || { rm -rf "$tmp"; die "$p on the frame (${h:0:12}...) is not an image this computer has; cannot store a known-good copy"; }
    # keep a copy that is already on the frame and still right
    local oldline oldgz
    oldline=$(echo "$old" | awk -v n="$p" -v g="$h" '$1 == n && $5 == g { print }')
    if [ -n "$oldline" ]; then
      f=$(echo "$oldline" | awk '{ print $3 }'); oldgz=$(echo "$oldline" | awk '{ print $4 }')
      if [ "$(dsh "sha256sum < \$C/rescue/$f | cut -d' ' -f1")" = "$oldgz" ]; then
        lines="$lines$p $h $f $oldgz $h
"; plan="$plan
   - $p: $(label_of "$h" "$p") (copy already there, kept)"; continue
      fi
    fi
    gzip -6 -n -c "$src" > "$tmp/$p.gz" || die "gzip failed"
    lines="$lines$p $h $p.gz $(sha "$tmp/$p.gz") $h
"; push="$push $p"; plan="$plan
   - $p: $(label_of "$h" "$p") (new copy, $(( $(wc -c < "$tmp/$p.gz") / 1048576 )) MB)"
  done
  printf 'rescue-list 1\n%send\n' "$lines" > "$tmp/list"
  confirm "store the known-good set in /cache/rescue (what the frame runs now):$plan
   While copies are being replaced there is briefly no list, so a restore in that minute would do nothing" || { rm -rf "$tmp"; return 1; }
  dsh 'mkdir -p $C/rescue; rm -f $C/rescue/list $C/rescue/attempts; sync'
  for p in $push; do
    dsh "rm -f \$C/rescue/$p.gz; sync"
    adb push "$tmp/$p.gz" "/cache/rescue/$p.gz" >/dev/null 2>&1 || { rm -rf "$tmp"; die "copying $p.gz failed (cache full?). There is no list now; fix and run store again."; }
    [ "$(dsh "sha256sum < \$C/rescue/$p.gz | cut -d' ' -f1")" = "$(sha "$tmp/$p.gz")" ] || { rm -rf "$tmp"; die "$p.gz arrived damaged. There is no list now; run store again."; }
  done
  adb push "$tmp/list" /cache/rescue/list.new >/dev/null 2>&1 && dsh 'mv $C/rescue/list.new $C/rescue/list; sync'
  [ "$(dsh 'sha256sum < $C/rescue/list | cut -d" " -f1')" = "$(sha "$tmp/list")" ] || { rm -rf "$tmp"; die "the list did not arrive whole; run store again"; }
  rm -rf "$tmp"
  say "DONE: known-good set stored and read back."
}

# ---------------------------------------------------------------- main
args=""
for a in "$@"; do [ "$a" = "--dry-run" ] && DRY=1 || args="$args $a"; done
set -- $args
case "${1:-status}" in
  status) cmd_status ;;
  check) cmd_check ;;
  restore) [ $# -eq 3 ] || die "say: restore <part> <stock|ours>   (parts: $ALLOWED)"; do_restore "$3" "$2" ;;
  restore-set) [ $# -eq 2 ] || die "say: restore-set <stock|ours>"; do_restore "$2" product vbmeta_system vbmeta ;;
  factory-logo) do_restore stock logo ;;
  safe) cmd_safe "${2:-}" ;;
  store) cmd_store ;;
  clear-note) cmd_clear_note ;;
  restart) cmd_restart ;;
  -h|--help|help) sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//' ;;
  *) die "unknown command '$1'. Try: frame-doctor.sh help" ;;
esac
