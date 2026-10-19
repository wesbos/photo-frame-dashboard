#!/usr/bin/env bash
# Back up the PF1506's firmware partitions over USB ADB, on stock Android 10 (shipped `su 0`).
#
# FIRMWARE PARTITIONS ONLY. This does NOT back up UDISK (photos, apps, settings) or frp.
# Later steps erase UDISK: copy any photos you want off the frame first.
#
# A bash version of the method used on the documented unit, which was run from Windows
# PowerShell; this script itself has not been run against a frame. It stops at the first
# mismatch. Each partition is streamed with root dd, cut to the partition's exact size
# (dd's status message can trail the data), and compared with a hash taken on the frame.
# super is read in 64 x 32 MiB pieces: on the documented unit, a full read made the frame
# restart partway through.
#
#   usage: backup.sh <empty output folder>
set -euo pipefail
OUT=${1:?usage: backup.sh <empty output folder>}
mkdir -p "$OUT"; cd "$OUT"
[ -z "$(ls -A .)" ] || { echo "$OUT is not empty" >&2; exit 1; }
B=/dev/block/by-name
dev_sha() { adb shell "su 0 dd if=$1 bs=$2 ${3:-} 2>/dev/null | sha256sum" | cut -d' ' -f1; }
check() {  # file, device hash, manifest (retained files by default)
    local host; host=$(sha256sum "$1" | cut -d' ' -f1)
    [ -n "$2" ] && [ "$2" = "$host" ] || { echo "MISMATCH on $1: stopping. Read it again before going on." >&2; exit 1; }
    echo "$host  $1" >> "${3:-MANIFEST.sha256.txt}"
}

adb get-state >/dev/null
[ "$(adb shell su 0 id -u | tr -d '\r')" = "0" ] || { echo "su 0 doesn't give root" >&2; exit 1; }

for p in boot bootloader dtbo env metadata misc private recovery vbmeta vbmeta_system vbmeta_vendor; do
    size=$(adb shell "su 0 blockdev --getsize64 $B/$p" | tr -d '\r')
    [[ "$size" =~ ^[0-9]+$ ]] || { echo "no size for $p" >&2; exit 1; }
    adb exec-out "su 0 dd if=$B/$p bs=1048576" > "$p.img"
    [ "$(stat -c %s "$p.img" 2>/dev/null || stat -f %z "$p.img")" -ge "$size" ] || { echo "$p: short read" >&2; exit 1; }
    truncate -s "$size" "$p.img"
    check "$p.img" "$(dev_sha "$B/$p" 1048576)"
done

size=$(adb shell "su 0 blockdev --getsize64 $B/super" | tr -d '\r')
[ "$size" = 2147483648 ] || { echo "super is $size bytes, expected 2147483648: not this board?" >&2; exit 1; }
for i in $(seq 0 63); do
    adb exec-out "su 0 dd if=$B/super bs=33554432 skip=$i count=1" > "super.$i"
    [ "$(stat -c %s "super.$i" 2>/dev/null || stat -f %z "super.$i")" -ge 33554432 ] || { echo "super piece $i: short read" >&2; exit 1; }
    truncate -s 33554432 "super.$i"
    check "super.$i" "$(dev_sha "$B/super" 33554432 "skip=$i count=1")" TRANSFER-CHUNKS.sha256.txt
done
cat $(seq -f 'super.%g' 0 63) > super.img
rm super.[0-9]*
sha256sum super.img >> MANIFEST.sha256.txt
sha256sum -c MANIFEST.sha256.txt
echo "Done. Copy this folder to a second machine. Not included: UDISK (your photos and apps) and frp."
