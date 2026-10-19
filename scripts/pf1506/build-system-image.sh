#!/usr/bin/env bash
# Build the PF1506 system image: LineageOS 20 a64_bvN GSI + touch fix + boot-time fix +
# f2fs wear fix, and optionally the Wi-Fi ADB script. Runs on a Linux host (e2fsprogs:
# e2fsck, resize2fs, debugfs). It creates the output image and a temporary work folder
# (removed on exit) and changes nothing else; flashing is a separate, manual step.
#
#   usage: build-system-image.sh <lineage-...-a64_bvN.img.gz> <out.img> [--wifi-adb]
#
# --wifi-adb adds frame-adb-wifi.sh. Read it first: this build's adbd has no
# authentication, so network ADB is root for anything allowed to reach it.
set -euo pipefail
[ $# -ge 2 ] || { sed -n 2,11p "$0"; exit 2; }
GZ=$(realpath "$1")
OUT=$(realpath -m "$2")
WIFI=${3:-}
HERE=$(cd "$(dirname "$0")" && pwd)
GSI_SHA=62551575a4134813274ed2b255bc695523e8b5dd991b53269c7019227cb65e4e
IMG_SHA=d4ed044bcbfbb8352fb1dd8d2ec583f3bccf7181a06b99479723f8517325c733
MAX_BYTES=$((1900 * 1024 * 1024))   # super group cap 2,040 MiB minus vendor and product
LABEL=u:object_r:system_file:s0
LABEL_NUL="${LABEL}X"                # the stored label ends in a NUL: length + 1

# e2fsck: 0 = clean, 1 = errors corrected; anything else stops the build.
fsck() {
    local rc=0
    e2fsck "$@" || rc=$?
    [ "$rc" -le 1 ] || { echo "e2fsck $* failed with status $rc" >&2; exit 1; }
}

[ -e "$OUT" ] && { echo "refusing to overwrite $OUT" >&2; exit 1; }
[ -x "$HERE/entropy_seed" ] || { echo "build entropy_seed first (see the doc)" >&2; exit 1; }
echo "$GSI_SHA  $GZ" | sha256sum -c -

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cp "$HERE"/{gslX680.idc,idc.cmds,entropy_seed,entropy_seed.rc,seed.cmds,frame-tuning.sh,frame-tuning.rc,tuning.cmds} "$WORK"/
FILES=(/system/usr/idc/gslX680.idc /system/bin/entropy_seed /system/etc/init/entropy_seed.rc
       /system/etc/frame-tuning.sh /system/etc/init/frame-tuning.rc)
CMDS=(idc.cmds seed.cmds tuning.cmds)
if [ "$WIFI" = "--wifi-adb" ]; then
    cp "$HERE"/{frame-adb-wifi.sh,frame-adb-wifi.rc,adb.cmds} "$WORK"/
    CMDS+=(adb.cmds)
    FILES+=(/system/etc/frame-adb-wifi.sh /system/etc/init/frame-adb-wifi.rc)
elif [ -n "$WIFI" ]; then
    echo "unknown option $WIFI" >&2; exit 2
fi

gunzip -c "$GZ" > "$OUT"
echo "$IMG_SHA  $OUT" | sha256sum -c -
fsck -fy "$OUT"
resize2fs "$OUT" 1880M
fsck -fy -E unshare_blocks "$OUT"
for c in "${CMDS[@]}"; do
    (cd "$WORK" && debugfs -w -f "$c" "$OUT")   # idc.cmds writes label.bin into $WORK first
done
fsck -fy "$OUT"
resize2fs -M "$OUT"
fsck -fn "$OUT"

size=$(stat -c %s "$OUT")
[ "$size" -lt "$MAX_BYTES" ] || { echo "image is $size bytes, over the 1,900 MiB limit" >&2; exit 1; }
for f in "${FILES[@]}"; do
    # debugfs prints: security.selinux (26) = "u:object_r:system_file:s0\000"
    got=$(debugfs -R "ea_get $f security.selinux" "$OUT" 2>/dev/null || true)
    [ "$got" = "security.selinux (${#LABEL_NUL}) = \"$LABEL\\000\"" ] \
        || { echo "missing or wrong label on $f: $got" >&2; exit 1; }
    cmp -s <(debugfs -R "cat $f" "$OUT" 2>/dev/null) "$WORK/$(basename "$f")" \
        || { echo "content of $f differs from the source file" >&2; exit 1; }
done
echo "built $OUT ($size bytes)"
sha256sum "$OUT"
