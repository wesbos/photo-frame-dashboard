#!/bin/bash
# Tries the root-shell blocks of docs/lexar-pexar-px-110.md, section 16, exactly as the page prints them.
#     bash tools/test_howto_blocks.sh
# The blocks are cut out of the page, their device paths are pointed at stand-in partition files in a temporary
# folder (real stock contents, cloned from your backup), and each is run in the good case and in the bad cases
# it must refuse. `stop`, `blockdev` and `sha256sum` are small stand-ins. No frame is needed and none is touched.
# This shows the checks hold in a shell on the computer. It does not show the frame's own shell behaves the same.
# Needs BACKUP_DIR and the built images in BUILD_DIR; without them the whole file is skipped.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PAGE=$HERE/../../../docs/lexar-pexar-px-110.md
REALB=$(python3 -I "$HERE/px110conf.py" get BACKUP_DIR)
BUILD=$(python3 -I "$HERE/px110conf.py" get BUILD_DIR)
[ -f "$PAGE" ] || { echo "SKIP test_howto_blocks.sh: the page is not where it is expected ($PAGE)"; exit 0; }
if [ -z "$REALB" ] || [ ! -f "$REALB/super.img" ] || [ ! -f "$REALB/para.img" ]; then
  echo "SKIP test_howto_blocks.sh: no backup (set BACKUP_DIR in unit.conf)"; exit 0
fi
for f in out/product.img out/vbmeta.img out/vbmeta_system.img work/patched-super.img work/stock/product.img out-boot/boot-wrap-recovery.img; do
  [ -f "$BUILD/$f" ] || { echo "SKIP test_howto_blocks.sh: $f is not built yet in BUILD_DIR"; exit 0; }
done
F=$(mktemp -d "${TMPDIR:-/tmp}/blocks.XXXXXX") || exit 2
trap 'rm -rf "${F:?}"' EXIT
B=$F/blocks; mkdir -p "$B"
# Cut the eight blocks out of the page. Each is found by the word it prints; each word must be in exactly one block.
python3 -I - "$PAGE" "$B" <<'PYEOF' || { echo "FAIL: could not cut the blocks out of the page"; exit 1; }
import re, sys
page = open(sys.argv[1]).read()
sec = page[page.index("## 16. Reproduce it"):]
blocks = re.findall(r"```sh\n(.*?)```", sec, re.S)
want = {"s5-write.sh": r"echo WRITES-DONE\b", "s5-readback.sh": r"echo READBACK-OK\b", "s5-stock.sh": r"echo STOCK-BACK-OK\b",
        "s7-note.sh": r"echo NOTE-SET\b", "s8-arm.sh": r'echo "note armed"', "s8-clear.sh": r'echo "note cleared"',
        "s9-boot.sh": r"echo BOOT-READBACK-OK\b", "s9-stock.sh": r"echo STOCK-BOOT-BACK-OK\b"}
for name, pat in want.items():
    hits = [b for b in blocks if re.search(pat, b)]
    if len(hits) != 1:
        sys.exit("%s: %d blocks print its word, expected exactly 1" % (name, len(hits)))
    open(sys.argv[2] + "/" + name, "w").write(hits[0])
PYEOF
mkdir -p "$F/bin" "$F/dev" "$F/lx" "$F/sys/mmcblk0p26" "$F/cache/rescue"
printf '#!/bin/sh\nexec shasum -a 256 "$@"\n' > "$F/bin/sha256sum"
printf '#!/bin/sh\n[ "$1" = --getro ] && echo ${GETRO:-0}\nexit 0\n' > "$F/bin/blockdev"
printf '#!/bin/sh\necho stop >> %s/calls\n' "$F" > "$F/bin/stop"
chmod +x "$F"/bin/*
cl() { cp -c "$1" "$2" 2>/dev/null || cp "$1" "$2"; chmod u+w "$2"; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
reset() {
  rm -f "${F:?}"/dev/* "${F:?}"/lx/* "${F:?}"/cache/rescue/* "${F:?}"/calls
  cl "$REALB/super.img" "$F/dev/mmcblk0p26"; ln -s mmcblk0p26 "$F/dev/super"; echo 520704 > "$F/sys/mmcblk0p26/start"
  for p in vbmeta vbmeta_system boot para; do cl "$REALB/$p.img" "$F/dev/$p"; done
  for n in product vbmeta vbmeta_system; do cl "$BUILD/out/$n.img" "$F/lx/$n.img"; cl "$BUILD/work/stock/$n.img" "$F/lx/stock-$n.img"; done
  cl "$BUILD/out-boot/boot-wrap-recovery.img" "$F/lx/boot-new.img"; cl "$REALB/boot.img" "$F/lx/boot-stock.img"
}
blk() {   # blk "<assignments>" file...: run blocks in one shell, as a root shell on the frame would, paths pointed at the stand-in
  local pre=$1; shift
  { echo "$pre"; for f in "$@"; do sed -e "s#/dev/block/by-name#$F/dev#g" -e "s#/data/local/tmp/lx#$F/lx#g" -e "s#/sys/class/block#$F/sys#g" -e "s#/cache/rescue#$F/cache/rescue#g" "$B/$f"; done; } > "$F/run.sh"
  OUT=$(PATH="$F/bin:$PATH" sh "$F/run.sh" 2>&1)
}
pass=0; fail=0
ck() { if eval "$2"; then pass=$((pass+1)); echo "ok   $1"; else fail=$((fail+1)); echo "FAIL $1"; echo "$OUT" | tail -5 | sed 's/^/       /'; fi; }
has() { echo "$OUT" | grep -q -- "$1"; }
SUPER0=47a75dd03635c7a1d40e757a034ade0bce057f8429c15f2e732116cd3c231d01
P=$(sha "$BUILD/out/product.img"); VS=$(sha "$BUILD/out/vbmeta_system.img"); VB=$(sha "$BUILD/out/vbmeta.img"); SA=$(sha "$BUILD/work/patched-super.img")
NEW=$(sha "$BUILD/out-boot/boot-wrap-recovery.img"); STOCKBOOT=$(sha "$REALB/boot.img"); VB0=$(sha "$REALB/vbmeta.img"); VS0=$(sha "$REALB/vbmeta_system.img"); PARA0=$(sha "$REALB/para.img")
V="P=$P; VS=$VS; VB=$VB; SUPER_AFTER=$SA"
stock3() { [ "$(sha "$F/dev/mmcblk0p26")" = $SUPER0 ] && [ "$(sha "$F/dev/vbmeta")" = "$VB0" ] && [ "$(sha "$F/dev/vbmeta_system")" = "$VS0" ]; }
poke() { printf X | dd of="$1" bs=1 seek="$2" conv=notrunc 2>/dev/null; }
wipe_note() { printf 'boot-recovery' | dd of="$F/dev/para" bs=1 conv=notrunc 2>/dev/null; printf 'recovery\n--wipe_data\n' | dd of="$F/dev/para" bs=1 seek=64 conv=notrunc 2>/dev/null; }

echo "== step 5"
reset; blk "$V" s5-write.sh s5-readback.sh
ck "all checks right: three writes, WRITES-DONE, READBACK-OK, super is the expected whole" 'has WRITES-DONE && has READBACK-OK && [ "$(sha "$F/dev/mmcblk0p26")" = "$SA" ] && [ "$(sha "$F/dev/vbmeta")" = "$VB" ] && [ "$(sha "$F/dev/vbmeta_system")" = "$VS" ] && [ -s "$F/calls" ]'
blk "" s5-stock.sh
ck "put stock back: STOCK-BACK-OK and the three partitions are stock again" 'has STOCK-BACK-OK && stock3'
reset; blk "" s5-write.sh
ck "variables not set: STOP, nothing written, Android not stopped" 'has "STOP: a check failed" && ! has WRITES-DONE && stock3 && [ ! -e "$F/calls" ]'
reset; blk "P=$VS; VS=$VS; VB=$VB" s5-write.sh
ck "wrong product hash given: STOP, nothing written" 'has "STOP: a check failed" && stock3'
reset; poke "$F/lx/vbmeta_system.img" 1440; blk "$V" s5-write.sh
ck "a pushed image damaged on the frame: STOP, nothing written" 'has "STOP: a check failed" && stock3'
reset; poke "$F/lx/stock-product.img" 99; blk "$V" s5-write.sh
ck "a stock copy (the way back) damaged: STOP, nothing written" 'has "STOP: a check failed" && stock3'
reset; poke "$F/dev/vbmeta" 700; h0=$(sha "$F/dev/vbmeta"); blk "$V" s5-write.sh
ck "the frame is not stock to begin with: STOP, nothing written" 'has "STOP: a check failed" && [ "$(sha "$F/dev/vbmeta")" = "$h0" ] && [ "$(sha "$F/dev/mmcblk0p26")" = $SUPER0 ]'
reset; echo 999 > "$F/sys/mmcblk0p26/start"; blk "$V" s5-write.sh
ck "super starts somewhere else: STOP, nothing written" 'has "STOP: a check failed" && stock3'
reset; export GETRO=1; blk "$V" s5-write.sh; unset GETRO
ck "a partition is read-only: STOP, nothing written" 'has "STOP: a check failed" && stock3'
reset; blk "$V" s5-write.sh; poke "$F/dev/vbmeta" 700; blk "$V; h() { sha256sum \"\$1\" | cut -d' ' -f1; }; D=$F/dev" s5-readback.sh
ck "a write that did not land: READBACK-WRONG" 'has READBACK-WRONG && ! has READBACK-OK'
reset; poke "$F/lx/stock-vbmeta.img" 5; blk "" s5-stock.sh
ck "stock-back with a damaged stock copy: STOP, nothing written" 'has "STOP: the stock copies" && stock3 && [ ! -e "$F/calls" ]'

echo "== step 7 note (--just_exit)"
reset; blk "" s7-note.sh
ck "empty para: NOTE-SET, command at 0, arguments at 64, rest of para untouched" 'has NOTE-SET && [ "$(head -c 13 "$F/dev/para")" = boot-recovery ] && [ "$(dd if="$F/dev/para" bs=1 skip=64 count=20 2>/dev/null | tr "\n" "_")" = "recovery_--just_exit" ] && cmp -s <(tail -c +2049 "$F/dev/para") <(tail -c +2049 "$REALB/para.img")'
reset; wipe_note; h0=$(sha "$F/dev/para"); blk "" s7-note.sh
ck "a pending wipe note: STOP, para untouched" 'has "STOP: para is not empty" && [ "$(sha "$F/dev/para")" = "$h0" ]'
reset; rm -f "${F:?}/dev/para"; blk "" s7-note.sh
ck "para cannot be read: STOP" 'has "STOP: para is not empty" && ! has NOTE-SET'

echo "== step 8 arm and all clear"
reset; blk "" s8-arm.sh
ck "arm on an empty para: armed, exactly our plain note" 'has "note armed" && [ "$(head -c 13 "$F/dev/para")" = boot-recovery ]'
h0=$(sha "$F/dev/para"); blk "" s8-arm.sh; ck "arm again: already armed, unchanged" 'has "already armed" && [ "$(sha "$F/dev/para")" = "$h0" ]'
echo 2 > "$F/cache/rescue/rung"; blk "" s8-clear.sh
ck "all clear: note cleared, para is the factory para again, rung gone" 'has "note cleared" && [ "$(sha "$F/dev/para")" = "$PARA0" ] && [ ! -e "$F/cache/rescue/rung" ]'
reset; wipe_note; h0=$(sha "$F/dev/para")
blk "" s8-arm.sh; ck "arm over a foreign note: left alone" 'has "left alone" && [ "$(sha "$F/dev/para")" = "$h0" ]'
blk "" s8-clear.sh; ck "all clear over a foreign note: left alone" 'has "left alone" && [ "$(sha "$F/dev/para")" = "$h0" ]'

echo "== step 9 guarded boot"
mklist() { printf 'rescue-list 1\nproduct aa product.gz bb aa\nvbmeta_system cc vbmeta_system.gz dd cc\nvbmeta ee vbmeta.gz ff ee\nlogo 11 logo.gz 22 11\nboot %s boot.gz 33 %s\nend\n' "$STOCKBOOT" "$STOCKBOOT" > "$F/list.now"
  awk -v n="$1" 'NR == 1 { print; print "guarded"; next } $1 == "boot" { $2 = n } { print }' "$F/list.now" > "$F/lx/list.guarded"; cp "$F/list.now" "$F/cache/rescue/list"; }
untouched() { [ "$(sha "$F/dev/boot")" = "$STOCKBOOT" ] && cmp -s "$F/list.now" "$F/cache/rescue/list" && [ "$(sha "$F/dev/para")" = "$1" ] && [ ! -e "$F/calls" ]; }
reset; mklist "$NEW"; echo 1 > "$F/cache/rescue/rung"; blk "NEW=$NEW" s9-boot.sh
ck "all right: list in, rung gone, note armed, boot written, BOOT-READBACK-OK" 'has BOOT-READBACK-OK && [ "$(sha "$F/dev/boot")" = "$NEW" ] && cmp -s "$F/lx/list.guarded" "$F/cache/rescue/list" && [ ! -e "$F/cache/rescue/rung" ] && [ "$(head -c 13 "$F/dev/para")" = boot-recovery ]'
blk "" s9-stock.sh; ck "stock boot back: STOCK-BOOT-BACK-OK" 'has STOCK-BOOT-BACK-OK && [ "$(sha "$F/dev/boot")" = "$STOCKBOOT" ]'
reset; mklist "$NEW"; blk "" s9-boot.sh
ck "NEW not set: STOP; list, note and boot untouched" 'has "STOP: a check failed" && untouched $PARA0'
reset; mklist "$NEW"; poke "$F/lx/boot-new.img" 4000000; blk "NEW=$NEW" s9-boot.sh
ck "boot-new.img damaged on the frame: STOP; nothing written" 'has "STOP: a check failed" && untouched $PARA0'
reset; mklist "$NEW"; blk "NEW=$STOCKBOOT" s9-boot.sh
ck "NEW set to the stock hash by mistake: STOP" 'has "STOP: a check failed" && untouched $PARA0'
reset; mklist "$STOCKBOOT"; blk "NEW=$NEW" s9-boot.sh
ck "list does not expect the new image: STOP; nothing written" 'has "STOP: a check failed" && [ "$(sha "$F/dev/boot")" = "$STOCKBOOT" ] && [ "$(sha "$F/dev/para")" = "$PARA0" ] && [ ! -e "$F/calls" ]'
reset; mklist "$NEW"; grep -v '^end$' "$F/lx/list.guarded" > "$F/lx/l2"; mv "$F/lx/l2" "$F/lx/list.guarded"; blk "NEW=$NEW" s9-boot.sh
ck "guarded list cut short (no end): STOP; nothing written" 'has "STOP: a check failed" && untouched $PARA0'
reset; mklist "$NEW"; wipe_note; h1=$(sha "$F/dev/para"); blk "NEW=$NEW" s9-boot.sh
ck "a foreign note in para: STOP; list, note and boot untouched" 'has "STOP: a check failed" && untouched $h1'
reset; mklist "$NEW"; poke "$F/dev/boot" 100; hb=$(sha "$F/dev/boot"); blk "NEW=$NEW" s9-boot.sh
ck "live boot is not stock: STOP; boot untouched" 'has "STOP: a check failed" && [ "$(sha "$F/dev/boot")" = "$hb" ] && [ "$(sha "$F/dev/para")" = "$PARA0" ]'
reset; mklist "$NEW"; chmod 555 "$F/cache/rescue"; blk "NEW=$NEW" s9-boot.sh; chmod 755 "$F/cache/rescue"
ck "the list cannot be put in: STOP; note and boot not written" 'has "guarded list did not go in" && [ "$(sha "$F/dev/boot")" = "$STOCKBOOT" ] && [ "$(sha "$F/dev/para")" = "$PARA0" ]'
reset; mklist "$NEW"; poke "$F/lx/boot-stock.img" 7; blk "" s9-stock.sh
ck "stock-boot-back with a damaged stock file: STOP" 'has "STOP: boot-stock.img" && [ ! -e "$F/calls" ]'
echo; echo "passed $pass, failed $fail"; [ $fail = 0 ]
