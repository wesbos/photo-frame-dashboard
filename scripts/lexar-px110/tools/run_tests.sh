#!/bin/zsh
# Runs every acceptance test of the product / vbmeta build and writes the full log to BUILD_DIR/out/test-output.txt,
# then BUILD_DIR/out/SHA256SUMS (frame-doctor.sh will not write an image that has no line there).
# Usage: zsh tools/run_tests.sh      (after python3 -I tools/build.py)
# Settings (unit.conf or PX110_<NAME>, see px110conf.py): BUILD_DIR, KEY_DIR, KIOSK_APK, E2FSPROGS_DIR, and for
# tests 8 and 11 ANDROID_BUILD_TOOLS, JAVA_HOME and KIOSK_PREVIOUS_APK.
set -u
TOOLS=${0:A:h}
conf() { python3 -I $TOOLS/px110conf.py get $1; }
BUILD=$(conf BUILD_DIR)
if [ ! -f $BUILD/out/product.img ] || [ ! -f $BUILD/out/kiosk-path.txt ] || [ ! -f $BUILD/work/stock/super.img ]; then
  echo "SKIP run_tests.sh: nothing built in BUILD_DIR/out yet (build.py needs your backup, the keys and a kiosk APK)"
  exit 0
fi
E2=$(conf E2FSPROGS_DIR); E2=${E2:+$E2/}                 # empty: debugfs, e2fsck and dumpe2fs come from the PATH
BT=$(conf ANDROID_BUILD_TOOLS)
J=$(conf JAVA_HOME); [ -n "$J" ] && export JAVA_HOME=$J
KEY=$(conf KEY_DIR)/testkey_rsa2048.pem
SRCAPK=$(conf KIOSK_APK)
PREVAPK=$(conf KIOSK_PREVIOUS_APK)
SRCRC=$TOOLS/../src/photoframe.rc
cd $BUILD || exit 1
KIOSK=$(cat out/kiosk-path.txt)                          # where build.py put the kiosk, e.g. /app/<name>/<name>.apk
export TOOLS E2 KEY SRCRC
S=work/stock
LOG=out/test-output.txt
FRAME_DIGEST=56adcc31739410d7cba798b73b24fd56114c38f9cb350edf5184eb9dda9dd754   # ro.boot.vbmeta.digest of the stock firmware
V=(python3 $TOOLS/verify.py --lk $S/lk.img --vbmeta-vendor $S/vbmeta_vendor.img --boot $S/boot.img)
PATCHED=(--vbmeta out/vbmeta.img --vbmeta-system out/vbmeta_system.img)
fails=0
expect() {  # expect <0|1> <title> <cmd...>
  local want=$1 title=$2; shift 2
  echo "\n================ $title"; echo "\$ $*"
  "$@"; local rc=$?
  echo "exit status: $rc (expected $([ $want = 0 ] && echo 0 || echo non-zero))"
  if { [ $want = 0 ] && [ $rc != 0 ]; } || { [ $want != 0 ] && [ $rc = 0 ]; }; then
    echo "!!!! TEST FAILED: $title"; fails=$((fails+1))
  fi
}
{
echo "Run: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

expect 0 "1. verify.py on the untouched stock images (straight from the super backup copy)" \
  $V --vbmeta $S/vbmeta.img --vbmeta-system $S/vbmeta_system.img --super $S/super.img --expect-digest $FRAME_DIGEST --no-list

expect 0 "2. verify.py on the patched set (with file listing)" \
  $V $PATCHED --product out/product.img --extract $KIOSK work/extracted-kiosk.apk

echo "\n================ 3. patched super assembled from stock super + product.img at the LP extents"
cp -c $S/super.img work/patched-super.img 2>/dev/null || cp $S/super.img work/patched-super.img
python3 - <<'EOF'
pos = 0
with open("out/product.img", "rb") as p, open("work/patched-super.img", "r+b") as s:
    for line in open("out/product.extents.txt"):
        if line.startswith("#"):
            continue
        img_off, sup_off, length = (int(x) for x in line.split()[:3])
        p.seek(img_off); s.seek(sup_off); s.write(p.read(length))
        print("wrote product.img[%d:+%d] at super byte offset %d" % (img_off, length, sup_off))
EOF
expect 0 "3a. verify.py on the patched set, product read out of the patched super" \
  $V $PATCHED --super work/patched-super.img --no-list
echo "\n================ 3b. stock super vs patched super: every changed byte must be inside product's extent"
python3 - <<'EOF'
import sys
ext = [tuple(int(x) for x in l.split()[1:3]) for l in open("out/product.extents.txt") if not l.startswith("#")]
a, b = open("work/stock/super.img", "rb"), open("work/patched-super.img", "rb")
lo = hi = None; off = 0
while True:
    x, y = a.read(1 << 20), b.read(1 << 20)
    if not x and not y: break
    if x != y:
        idx = [i for i in range(len(x)) if x[i] != y[i]]
        lo = off + idx[0] if lo is None else lo; hi = off + idx[-1]
    off += len(x)
print("extents (offset, length):", ext, " super size", off)
print("first changed byte %d, last changed byte %d" % (lo, hi))
inside = any(s <= lo and hi < s + n for s, n in ext)
print("all changes inside product's extent:", inside)
sys.exit(0 if inside else 1)
EOF
[ $? = 0 ] || { echo "!!!! TEST FAILED: 3b"; fails=$((fails+1)); }

echo "\n================ 4. negative tests: one flipped byte"
python3 - <<'EOF'
def flip(src, dst, off):
    d = bytearray(open(src, "rb").read()); d[off] ^= 0x01; open(dst, "wb").write(d)
    print("flipped bit 0 of byte %d: %s -> %s" % (off, src, dst))
flip("out/product.img", "work/flip-product.img", 37 * 4096 + 100)   # inside the first block the build wrote
flip("out/vbmeta_system.img", "work/flip-vbmeta_system.img", 1440)  # inside the product root digest
flip("out/vbmeta.img", "work/flip-vbmeta.img", 700)                 # inside the chain key
EOF
expect 1 "4a. patched set with one byte flipped in product.img" \
  $V $PATCHED --product work/flip-product.img --no-list
expect 1 "4b. patched set with one byte flipped in vbmeta_system.img" \
  $V --vbmeta out/vbmeta.img --vbmeta-system work/flip-vbmeta_system.img --product out/product.img --no-list
expect 1 "4c. (extra) patched set with one byte flipped in vbmeta.img" \
  $V --vbmeta work/flip-vbmeta.img --vbmeta-system out/vbmeta_system.img --product out/product.img --no-list
expect 1 "4d. (extra) mixed set: patched product with STOCK vbmeta images must not pass" \
  $V --vbmeta $S/vbmeta.img --vbmeta-system $S/vbmeta_system.img --product out/product.img --no-list

echo "\n================ 5. signer over stock vbmeta contents reproduces stock signatures"
python3 - <<'EOF'
import os, sys; sys.path.insert(0, os.environ["TOOLS"])
import avblib, hashtree
key = avblib.load_private_key(os.environ["KEY"])
pub = avblib.encode_avb_pubkey(key[0], key[2])
okall = True
for name in ("vbmeta", "vbmeta_system", "vbmeta_vendor"):
    img = open("work/stock/%s.img" % name, "rb").read()
    vb = avblib.Vbmeta(img)
    if vb.public_key == pub:
        same = avblib.sign_vbmeta(vb.header, vb.aux, key) == vb.blob
        okall &= same
        print("%-14s signed with the AOSP test key; re-signed stock header+aux identical to stock (%d bytes incl. 256-byte signature): %s" % (name, vb.size, same))
    else:
        print("%-14s signed with a different key (modulus %s...) whose private half we do not hold: cannot be reproduced, and is not needed" % (name, vb.public_key[8:16].hex().upper()))
p = open("work/stock/product.img", "rb").read()
h = [d for d in avblib.Vbmeta(open("work/stock/vbmeta_system.img", "rb").read()).descriptors if d.get("name") == "product"][0]
root, tree = hashtree.build_hashtree(p[:h["image_size"]], h["salt"])
t = root == h["root_digest"] and tree == p[h["tree_offset"]:h["tree_offset"] + h["tree_size"]]
f = hashtree.build_fec(p[:h["fec_offset"]], h["fec_num_roots"]) == p[h["fec_offset"]:h["fec_offset"] + h["fec_size"]]
print("hashtree generator reproduces stock root digest and %d tree bytes: %s" % (h["tree_size"], t))
print("FEC generator reproduces stock %d FEC bytes: %s" % (h["fec_size"], f))
sys.exit(0 if okall and t and f else 1)
EOF
[ $? = 0 ] || { echo "!!!! TEST FAILED: 5"; fails=$((fails+1)); }

echo "\n================ 6. byte-level diff, stock vs patched"
python3 $TOOLS/diffsum.py $S/product.img out/product.img --max 30 \
  --regions filesystem:0:107999232,hashtree:107999232:108855296,fec:108855296:109723648,footer_vbmeta:109723648:109813760
python3 $TOOLS/diffsum.py $S/vbmeta_system.img out/vbmeta_system.img --block 1
python3 $TOOLS/diffsum.py $S/vbmeta.img out/vbmeta.img --block 1
python3 - <<'EOF'
import os, sys; sys.path.insert(0, os.environ["TOOLS"])
import avblib
for n in ("vbmeta", "vbmeta_system"):
    a = avblib.Vbmeta(open("work/stock/%s.img" % n, "rb").read()); b = avblib.Vbmeta(open("out/%s.img" % n, "rb").read())
    print("%s: header identical %s; descriptors changed: %s; public key changed: %s; trailing padding all zero: %s" % (
        n, a.header == b.header,
        [(i, x["type"], x.get("name", x.get("key"))) for i, (x, y) in enumerate(zip(a.descriptors, b.descriptors)) if x["raw"] != y["raw"]],
        a.public_key != b.public_key, not any(open("out/%s.img" % n, "rb").read()[b.size:])))
EOF

expect 0 "7. e2fsck -fn on the filesystem inside out/product.img" \
  sh -c "head -c 107999232 out/product.img > work/check.ext4 && ${E2}e2fsck -fn work/check.ext4"
echo "\n---- stock vs patched superblock fields that differ"
head -c 107999232 $S/product.img > work/stock-check.ext4
diff <(${E2}dumpe2fs -h work/stock-check.ext4 2>/dev/null) <(${E2}dumpe2fs -h work/check.ext4 2>/dev/null)
echo "\n---- stock vs patched file listing (verify.py's own ext4 reader)"
diff <($V --vbmeta $S/vbmeta.img --vbmeta-system $S/vbmeta_system.img --product $S/product.img | sed -n '/^mode/,$p') \
     <($V $PATCHED --product out/product.img | sed -n '/^mode/,$p')

echo "\n================ 8. APK read back out of the patched image vs the source APK (KIOSK_APK)"
if [ -z "$SRCAPK" ] || [ ! -f "$SRCAPK" ]; then
  echo "KIOSK_APK is not set to the APK that was built in, so there is nothing to compare with"
  echo "!!!! TEST FAILED: 8"; fails=$((fails+1))
elif [ -z "$BT" ]; then
  shasum -a 256 "$SRCAPK" work/extracted-kiosk.apk
  if cmp -s "$SRCAPK" work/extracted-kiosk.apk; then echo "identical bytes (ANDROID_BUILD_TOOLS not set: the aapt2 and apksigner looks are left out)"
  else echo "!!!! TEST FAILED: 8"; fails=$((fails+1)); fi
else
  shasum -a 256 "$SRCAPK" work/extracted-kiosk.apk
  $BT/aapt2 dump badging "$SRCAPK" > work/badging-source.txt
  $BT/aapt2 dump badging work/extracted-kiosk.apk > work/badging-extracted.txt
  if cmp -s "$SRCAPK" work/extracted-kiosk.apk && diff work/badging-source.txt work/badging-extracted.txt; then
    echo "identical bytes; aapt2 dump badging output identical:"; head -4 work/badging-extracted.txt
  else echo "!!!! TEST FAILED: 8"; fails=$((fails+1)); fi
  $BT/apksigner verify --min-sdk-version 30 --max-sdk-version 30 -v work/extracted-kiosk.apk | head -4
fi

echo "\n================ 9. photoframe.rc in the patched image: the second image's two early hooks and the unchanged late one"
python3 - <<'EOF'
import os, re, sys
src = open(os.environ["SRCRC"]).read()
back = open("work/readback-photoframe.rc").read()
bad = []
if src != back: bad.append("the rc read back from the image differs from src/photoframe.rc")
sections, cur = [], None
for n, line in enumerate(src.splitlines(), 1):
    t = line.strip()
    if not t or t.startswith("#"):
        continue
    if re.match(r"^(on|service) \S", line):
        cur = [line, []]; sections.append(cur)
    elif cur is None or not line.startswith("    "):
        bad.append("line %d is neither a section header nor indented under one: %r" % (n, line))
    else:
        cur[1].append(t)
        if not re.match(r"^(user|group|seclabel|oneshot|disabled|class|exec_background|mount|start) ?", t):
            bad.append("line %d: command not in the set the first image uses or the draft adds: %r" % (n, t))
posts = [s for s in sections if s[0] == "on post-fs-data"]
cmds = [c for s in posts for c in s[1]]
want_exec = "exec_background u:r:su:s0 root root -- /system/bin/sh /data/local/photoframe/early.sh"
want_mount = "mount none /data/local/photoframe/bootanimation.zip /system/media/bootanimation.zip bind"
if want_exec not in cmds: bad.append("missing the early.sh hook at post-fs-data")
if want_mount not in cmds: bad.append("missing the bootanimation bind mount at post-fs-data")
svc = [s for s in sections if s[0] == "service photoframe /system/bin/sh /data/local/photoframe/boot.sh"]
if len(svc) != 1 or svc[0][1] != ["user root", "group root", "seclabel u:r:su:s0", "oneshot", "disabled"]:
    bad.append("the late photoframe service is not exactly the first image's")
late = [s for s in sections if s[0] == "on property:sys.boot_completed=1"]
if len(late) != 1 or late[0][1] != ["start photoframe"]:
    bad.append("the late trigger (sys.boot_completed=1 -> start photoframe) is not exactly the first image's")
if want_exec in cmds and want_mount in cmds and cmds.index(want_exec) > cmds.index(want_mount):
    bad.append("early.sh should be started before the mount")
print("sections:", [s[0] for s in sections])
print("post-fs-data commands:", cmds)
print("rc problems:", bad or "none")
sys.exit(1 if bad else 0)
EOF
[ $? = 0 ] || { echo "!!!! TEST FAILED: 9"; fails=$((fails+1)); }

echo "\n================ 10. product still fits: free space inside the patched filesystem (the first image had 9.4 MB free)"
python3 - <<'EOF'
import os, re, subprocess, sys
out = subprocess.run([os.environ["E2"] + "dumpe2fs", "-h", "work/check.ext4"], capture_output=True, text=True).stdout
free = int(re.search(r"Free blocks:\s+(\d+)", out).group(1)); bs = int(re.search(r"Block size:\s+(\d+)", out).group(1))
print("product free space: %d blocks x %d = %.2f MB" % (free, bs, free * bs / 1e6))
sys.exit(0 if free * bs >= 1_000_000 else 1)
EOF
[ $? = 0 ] || { echo "!!!! TEST FAILED: 10"; fails=$((fails+1)); }

echo "\n================ 11. the kiosk in the image is signed with the same key as the kiosk the frame ran before"
# Android refuses to update an app to one signed with another key. KIOSK_PREVIOUS_APK is the APK the frame has
# run until now; on a first install there is none, and then there is nothing to compare.
if [ -z "$PREVAPK" ]; then
  echo "not run: KIOSK_PREVIOUS_APK is not set (first install of the kiosk on this frame)"
elif [ -z "$BT" ]; then
  echo "KIOSK_PREVIOUS_APK is set but ANDROID_BUILD_TOOLS is not: apksigner is needed for this test"
  echo "!!!! TEST FAILED: 11"; fails=$((fails+1))
else
  dig() { PATH=${JAVA_HOME:+$JAVA_HOME/bin:}$PATH $BT/apksigner verify --print-certs "$1" 2>/dev/null | grep "SHA-256 digest" | head -1; }
  new=$(dig work/extracted-kiosk.apk); first=$(dig "$PREVAPK")
  echo "image: $new"; echo "first: $first"
  [ -n "$new" ] && [ "$new" = "$first" ] || { echo "!!!! TEST FAILED: 11"; fails=$((fails+1)); }
fi

echo "\n================ SUMMARY: $fails test(s) failed"
} > $LOG 2>&1
echo "\n---- sha256 of the whole super partition before and after (for an on-device read-back)" >> $LOG
shasum -a 256 $S/super.img work/patched-super.img >> $LOG
failed=$(grep -c "TEST FAILED" $LOG)
grep "SUMMARY" $LOG
echo "full log: $BUILD/$LOG"
if [ $failed = 0 ]; then
  ( cd out && shasum -a 256 product.img vbmeta.img vbmeta_system.img product.extents.txt > SHA256SUMS
    echo "$(shasum -a 256 $TOOLS/verify.py | cut -d' ' -f1)  verify.py" >> SHA256SUMS )
else
  rm -f out/SHA256SUMS      # a set that failed a test gets no hash list, so frame-doctor.sh will not write it
fi

# ---- Logo signing (separate job; nothing above depends on it). Log: BUILD_DIR/out-logo/test-output.txt
if [ -f out-logo/logo-test.img ]; then
  python3 -I $TOOLS/test_logosign.py > out-logo/test-output.txt 2>&1
  echo "logo signing tests: exit status $? : $(tail -1 out-logo/test-output.txt)"
fi

# ---- Recovery build (separate job; nothing above depends on it). Log: BUILD_DIR/out-recovery/test-output.txt
if [ -f out-recovery/recovery-rescue.img ]; then
  python3 -I $TOOLS/test_recovery.py > out-recovery/test-output.txt 2>&1
  echo "recovery tests: exit status $? : $(tail -1 out-recovery/test-output.txt)"
fi
[ $failed = 0 ]
