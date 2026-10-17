#!/usr/bin/env bash
# Offline checks on a finished PF1007L eMMC backup, before boot-patch.py. Read-only: it touches no
# device, and the image is mounted read-only into a Docker container that has no network.
#
# Usage, from the repository root (no sudo; chown the backup to yourself first, see the U-Boot
# guide section 4):
#   scripts/a33-uboot/inspect-emmc-backup.sh [backups/a33-emmc-full.img]
#
# Prints:
#   - the eMMC size and which known size it is;
#   - the MBR partition starts, and whether env/boot/system/recovery are where the guides expect;
#   - the T6 boot-image SHA-256 (sector 172032, 31,028 sectors) and the firmware-table row it matches;
#   - every `on property:sys.usb.config=...` trigger line in the boot ramdisk's .rc files;
#   - persist.sys.usb.config from /data/property and the USB/ADB lines of /system/build.prop.
# boot-patch.py hooks only the `sys.usb.config=mass_storage` action. If the saved setting is
# something else (ptp, mtp, accessory...), the patched image can boot without ADB (#81).
#
# Needs Python 3 and a running Docker daemon (for debugfs from e2fsprogs; macOS has no ext4 tools).
# The first run builds a small local image, pf1007l-inspect (Ubuntu 24.04 + e2fsprogs).
set -euo pipefail
cd "$(dirname "$0")/../.."

IMG="${1:-backups/a33-emmc-full.img}"
[ -f "$IMG" ] || { echo "STOP: no image at $IMG" >&2; exit 1; }
[ -r "$IMG" ] || { echo "STOP: $IMG is not readable by $(id -un); chown it to yourself" >&2; exit 1; }
IMG="$(cd "$(dirname "$IMG")" && pwd -P)/$(basename "$IMG")"

python3 -I - "$IMG" <<'PY'
import gzip, hashlib, struct, sys

SIZES = {
    30535680: "smaller eMMC (units B and C)",
    30777344: "larger eMMC (the common one)",
    30310400: "third size, one January unit so far (#164)",
}
# First 8 digits of the T6 hash, from the firmware table in docs/pf1007l-start-here.md.
BOOT = {
    "d71c313d": "January 20260113",
    "8ffc2a7d": "April 20260410",
    "bef19d67": "April 20260416",
    "3f0dc9d5": "OS-PF1009.0.20260417",
    "9a6e2456": "May 20260519 (different ramdisk slot)",
    "6c118dc1": "May 20260529",
    "1fb8937e": "July 20250716 (#120, not in the table yet)",
}
JANUARY = "d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4"

path = sys.argv[1]
f = open(path, "rb")
size = f.seek(0, 2)
sectors = size // 512
print(f"size: {size} bytes = {sectors} sectors -> {SIZES.get(sectors, 'UNKNOWN SIZE: stop and report it')}")

f.seek(0)
mbr = f.read(512)
if mbr[510:] != b"\x55\xaa":
    sys.exit("STOP: no MBR signature at sector 0")
parts, ext = [], None
for i in range(4):
    entry = 446 + i * 16
    kind = mbr[entry + 4]
    start, count = struct.unpack_from("<II", mbr, entry + 8)
    if kind in (0x05, 0x0F):
        ext = start
    elif kind:
        parts.append((start, count, kind))
ebr = ext
while ebr is not None:
    f.seek(ebr * 512)
    b = f.read(512)
    kind1 = b[446 + 4]
    start1, count1 = struct.unpack_from("<II", b, 446 + 8)
    kind2 = b[462 + 4]
    start2 = struct.unpack_from("<I", b, 462 + 8)[0]
    parts.append((ebr + start1, count1, kind1))
    ebr = ext + start2 if kind2 else None
print("partitions (start, sectors, type):")
for start, count, kind in parts:
    note = "  (past the end of the eMMC, as the PF1007L guide notes for UDISK)" if start + count > sectors else ""
    print(f"  {start:>9} {count:>9} {kind:#04x}{note}")
starts = {s for s, _, _ in parts}
for start, name in [(139264, "env"), (172032, "boot"), (237568, "system"), (2400256, "recovery")]:
    print(f"  {name} at {start}: {'yes' if start in starts else 'NO - stop and report'}")

f.seek(172032 * 512)
boot = f.read(31028 * 512)
digest = hashlib.sha256(boot).hexdigest()
row = "January 20260113 (full hash)" if digest == JANUARY else BOOT.get(digest[:8])
print(f"T6 boot SHA-256 (172032, 31028 sectors): {digest}")
print(f"  firmware table: {row or 'NOT IN THE TABLE - untested, report it before any write'}")

magic, kernel_size, _, ramdisk_size, _, _, _, _, page = struct.unpack_from("<8s8I", boot, 0)
if magic != b"ANDROID!":
    sys.exit("STOP: no ANDROID! header at sector 172032")
pad = lambda n: (n + page - 1) // page * page
ramdisk = gzip.decompress(boot[page + pad(kernel_size): page + pad(kernel_size) + ramdisk_size])
off, found = 0, False
while off + 110 <= len(ramdisk):
    hdr = ramdisk[off:off + 110]
    if hdr[:6] != b"070701":
        sys.exit("STOP: the ramdisk is not a newc cpio archive")
    file_size, name_size = int(hdr[54:62], 16), int(hdr[94:102], 16)
    name = ramdisk[off + 110: off + 110 + name_size - 1]
    data_off = (off + 110 + name_size + 3) & ~3
    data = ramdisk[data_off:data_off + file_size]
    off = (data_off + file_size + 3) & ~3
    if name == b"TRAILER!!!":
        break
    if name.endswith(b".rc") and b"sys.usb.config=" in data:
        found = True
        print(f"--- {name.decode()}: sys.usb.config actions")
        for line in data.decode(errors="replace").splitlines():
            if line.startswith("on ") and "sys.usb.config=" in line:
                print("   ", line)
if not found:
    print("--- no sys.usb.config action in any ramdisk .rc file: stop and report it")
PY

DATA_START=$(python3 -I -c 'import struct,sys; print(struct.unpack_from("<I", open(sys.argv[1], "rb").read(512), 454)[0])' "$IMG")
SYSTEM_START=237568

docker build -q -t pf1007l-inspect - >/dev/null <<'EOF'
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends e2fsprogs \
    && rm -rf /var/lib/apt/lists/*
EOF

# debugfs reads the ext4 file systems at their sector offsets inside the read-only image.
docker run --rm -i --network none --mount "type=bind,src=$IMG,dst=/img,readonly" pf1007l-inspect \
  bash -s "$DATA_START" "$SYSTEM_START" <<'SH'
set -u
data="/img?offset=$(($1 * 512))"
system="/img?offset=$(($2 * 512))"
echo "--- /data (partition 1, sector $1)"
if debugfs -R 'stat /property' "$data" 2>/dev/null | grep -q 'Type: directory'; then
  value=$(debugfs -R 'cat /property/persist.sys.usb.config' "$data" 2>/dev/null)
  if [ -n "$value" ]; then echo "  /data/property/persist.sys.usb.config = $value"
  else echo "  /data/property/persist.sys.usb.config: absent (the build.prop value applies)"; fi
else
  echo "  STOP: could not read /property on partition 1, so the /data result is unknown, not absent"
fi
echo "--- /system (sector $2)"
if debugfs -R 'stat /build.prop' "$system" 2>/dev/null | grep -q 'Type: regular'; then
  debugfs -R 'cat /build.prop' "$system" 2>/dev/null | grep -E 'usb\.config|adb|debuggable|ro\.secure' \
    | sed 's/^/  build.prop: /' || echo "  build.prop: no usb.config/adb lines"
else
  echo "  STOP: could not read /build.prop from the system partition"
fi
SH

echo "boot-patch.py hooks only 'sys.usb.config=mass_storage'. If the saved value above is anything"
echo "else (ptp, mtp, accessory...), the patched image can boot without ADB (#81): stop and decide."
