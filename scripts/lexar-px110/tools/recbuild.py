"""Build a recovery image of our own for the frame (offline; nothing here talks to the frame).

Takes the stock recovery.img (Android boot image v2 with an AVB hash footer), keeps the kernel, the
dtb and the recovery dtbo byte for byte, changes a few files in the ramdisk, and signs the result
with MediaTek's published default recovery key, the key the frame's bootloader already trusts.

The ramdisk is handled as a cpio "newc" archive in memory. Nothing from it is written to disk and
nothing from it is run.

Usage:
    python3 -I tools/recbuild.py            build both images into BUILD_DIR/out-recovery/
    python3 -I tools/recbuild.py --help
Settings (unit.conf or the environment, see px110conf.py): BACKUP_DIR, KEY_DIR, BUILD_DIR.

Refuses to build unless the stock recovery.img has the hash recorded for firmware
PF1106_V2.06_20250527, and unless `product` sits in the backed-up `super` exactly where rescue.sh
has it fixed (4096-byte blocks 32512 onward, 109,813,760 bytes): the script that goes into the
image writes to that place.

Outputs:
    recovery-stock-resigned.img   stock, taken apart and put together again and re-signed. Must be
                                  byte-identical to stock; it proves the packer, the key and the signer.
    recovery-rescue.img           stock kernel + changed ramdisk (see RAMDISK CHANGES below).
"""
import argparse
import hashlib
import os
import re
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avblib  # noqa: E402
import px110conf  # noqa: E402

PARTITION_SIZE = 33554432          # the frame's `recovery` partition, 32 MiB
AVB_BLOCK = 4096                   # avbtool rounds the image up to this before the vbmeta blob
BOOT_MAGIC = b"ANDROID!"
HEADER_V2_SIZE = 1660

HERE = os.path.dirname(os.path.abspath(__file__))
_BACKUP = px110conf.path("BACKUP_DIR")
DEF_STOCK = os.path.join(_BACKUP, "recovery.img") if _BACKUP else None
DEF_SUPER = os.path.join(_BACKUP, "super.img") if _BACKUP else None
DEF_KEY = px110conf.key("recovery_prvk.pem")
DEF_SRC = os.path.join(px110conf.SRC, "recovery")
DEF_OUT = px110conf.build_dir("out-recovery")

# ---------------------------------------------------------------- pinned inputs
STOCK_SHA256 = px110conf.STOCK_SHA256["recovery.img"]

# rescue.sh writes `product` to a fixed place inside `super`. The numbers must be the ones in the
# script that is packed, and the user's own `super` must have `product` there (check_layout below).
RESCUE_LAYOUT_RE = r"^\s*product\)\s+DEV=\$BYNAME/super;\s+SKIP=(\d+);\s+COUNT=(\d+) ;;$"   # 4096-byte blocks

# ---------------------------------------------------------------- RAMDISK CHANGES
# Every change to the ramdisk is listed here; recverify.py reports the files that differ and
# test 6 checks that list against CHANGED_FILES.
INIT_RC = "system/etc/init/hw/init.rc"
PROP_FILE = "prop.default"
RESCUE_PATH = "system/bin/rescue.sh"
CHANGED_FILES = sorted([INIT_RC, PROP_FILE, RESCUE_PATH])

# The stock `recovery` program and its service are left exactly as they are: it runs beside
# rescue.sh, and started with --just_exit it clears the note and restarts the frame by itself.
# Exact-text replacements in init.rc. Each "old" text must occur exactly once or the build stops.
RC_EDITS = [
    # adbd: run in the `recovery` domain (the recovery policy has no `su` domain), no --root_seclabel.
    (
        "service adbd /system/bin/adbd --root_seclabel=u:r:su:s0 --device_banner=recovery\n"
        "    disabled\n"
        "    socket adbd stream 660 system system\n"
        "    seclabel u:r:adbd:s0\n",
        "service adbd /system/bin/adbd --device_banner=recovery\n"
        "    disabled\n"
        "    socket adbd stream 660 system system\n"
        "    seclabel u:r:recovery:s0\n",
    ),
]
RC_APPEND = "init.rescue.rc"       # in the source folder; appended to init.rc
PROP_OVERRIDES = "prop.overrides"  # in the source folder; key=value lines replacing existing keys
RESCUE_SRC = "rescue.sh"           # in the source folder; added as /system/bin/rescue.sh
RESCUE_MODE = 0o100755


# ---------------------------------------------------------------- boot image
def _pages(n, page):
    return (n + page - 1) // page * page


def unpack_boot(img):
    """Split an Android boot image v2 into its parts. Refuses anything it does not fully understand."""
    if img[:8] != BOOT_MAGIC:
        raise ValueError("not an Android boot image")
    (ksz, _kaddr, rsz, _raddr, ssz, _saddr, _tags, page, hver, _osv) = struct.unpack_from("<10I", img, 8)
    if hver != 2:
        raise ValueError("boot header version %d, expected 2" % hver)
    dbo_sz, dbo_off, hsize = struct.unpack_from("<IQI", img, 1632)
    dtb_sz, _dtb_addr = struct.unpack_from("<IQ", img, 1648)
    if hsize != HEADER_V2_SIZE or page not in (2048, 4096):
        raise ValueError("unexpected header size %d or page size %d" % (hsize, page))
    if any(img[HEADER_V2_SIZE:page]):
        raise ValueError("header page has data after the header")
    off = page
    parts = {}
    for name, size in (("kernel", ksz), ("ramdisk", rsz), ("second", ssz), ("recovery_dtbo", dbo_sz), ("dtb", dtb_sz)):
        parts[name] = img[off:off + size]
        if name == "recovery_dtbo" and dbo_off != off:
            raise ValueError("recovery dtbo offset field %d does not match layout %d" % (dbo_off, off))
        if any(img[off + size:off + _pages(size, page)]):
            raise ValueError("%s padding is not zero" % name)
        off += _pages(size, page)
    if boot_id(parts) != img[576:608]:
        raise ValueError("boot image id does not match its contents")
    return {"header": img[:HEADER_V2_SIZE], "page": page, "parts": parts, "size": off}


def boot_id(parts):
    """The header's id field: SHA-1 over each part followed by its length (as mkbootimg does), zero padded."""
    h = hashlib.sha1()
    for name in ("kernel", "ramdisk", "second", "recovery_dtbo", "dtb"):
        h.update(parts[name])
        h.update(struct.pack("<I", len(parts[name])))
    return h.digest() + b"\0" * 12


def pack_boot(boot, ramdisk):
    """Rebuild the boot image with a new ramdisk. Every other part and header field is kept."""
    page = boot["page"]
    parts = dict(boot["parts"], ramdisk=ramdisk)
    header = bytearray(boot["header"])
    struct.pack_into("<I", header, 16, len(ramdisk))
    dbo_off = page + _pages(len(parts["kernel"]), page) + _pages(len(ramdisk), page) + _pages(len(parts["second"]), page)
    struct.pack_into("<Q", header, 1636, dbo_off)
    header[576:608] = boot_id(parts)
    out = bytearray(bytes(header) + b"\0" * (page - len(header)))
    for name in ("kernel", "ramdisk", "second", "recovery_dtbo", "dtb"):
        out += parts[name]
        out += b"\0" * (-len(out) % page)
    return bytes(out)


# ---------------------------------------------------------------- gzip (same settings as stock)
GZ_HEADER = bytes.fromhex("1f8b0800000000000003")   # deflate, no flags, mtime 0, xfl 0, OS 3 (Unix)


def gunzip(blob):
    if blob[:10] != GZ_HEADER:
        raise ValueError("ramdisk gzip header is not the expected plain one")
    d = zlib.decompressobj(-15)
    raw = d.decompress(blob[10:])
    if not d.eof or len(d.unused_data) != 8:
        raise ValueError("ramdisk gzip stream is not a single clean member")
    crc, size = struct.unpack("<II", d.unused_data)
    if crc != zlib.crc32(raw) or size != len(raw) & 0xFFFFFFFF:
        raise ValueError("ramdisk gzip checksum mismatch")
    return raw


def gzip_like_stock(raw):
    c = zlib.compressobj(6, zlib.DEFLATED, -15)
    return GZ_HEADER + c.compress(raw) + c.flush() + struct.pack("<II", zlib.crc32(raw), len(raw) & 0xFFFFFFFF)


# ---------------------------------------------------------------- cpio newc, in memory only
CPIO_FIELDS = "ino mode uid gid nlink mtime filesize devmajor devminor rdevmajor rdevminor namesize check".split()
TRAILER = "TRAILER!!!"


def cpio_parse(raw):
    """Return (entries, total_length). Each entry is a dict of the header fields plus name and data."""
    entries, off = [], 0
    while True:
        if raw[off:off + 6] != b"070701":
            raise ValueError("cpio: bad magic at %d" % off)
        vals = [int(raw[off + 6 + i * 8:off + 14 + i * 8], 16) for i in range(13)]
        e = dict(zip(CPIO_FIELDS, vals))
        name_end = off + 110 + e["namesize"]
        if raw[name_end - 1] != 0:
            raise ValueError("cpio: name not terminated at %d" % off)
        e["name"] = raw[off + 110:name_end - 1].decode()
        data_off = (name_end + 3) & ~3
        e["data"] = raw[data_off:data_off + e["filesize"]]
        off = (data_off + e["filesize"] + 3) & ~3
        entries.append(e)
        if e["name"] == TRAILER:
            break
    if any(raw[off:]):
        raise ValueError("cpio: data after the trailer")
    return entries, len(raw)


def cpio_build(entries, block=512):
    out = bytearray()
    for e in entries:
        name = e["name"].encode() + b"\0"
        vals = dict(e, namesize=len(name), filesize=len(e["data"]))
        out += b"070701" + b"".join(b"%08x" % vals[f] for f in CPIO_FIELDS)
        out += name
        out += b"\0" * (-len(out) % 4)
        out += e["data"]
        out += b"\0" * (-len(out) % 4)
    out += b"\0" * (-len(out) % block)
    return bytes(out)


def _find(entries, name):
    hits = [e for e in entries if e["name"] == name]
    if len(hits) != 1:
        raise ValueError("ramdisk: expected exactly one %r, found %d" % (name, len(hits)))
    return hits[0]


def apply_changes(entries, src_dir):
    """Apply the ramdisk changes to the parsed entries (in place). Returns notes for the build log."""
    notes = []

    # 1. init.rc: exact replacements, then the rescue section appended.
    rc = _find(entries, INIT_RC)
    text = rc["data"].decode()
    for old, new in RC_EDITS:
        if text.count(old) != 1:
            raise ValueError("init.rc: expected text not found exactly once:\n" + old)
        text = text.replace(old, new)
    extra = open(os.path.join(src_dir, RC_APPEND)).read()
    if not text.endswith("\n"):
        text += "\n"
    rc["data"] = (text + "\n" + extra).encode()
    notes.append("%s: %d exact edits, %d lines appended from %s" % (INIT_RC, len(RC_EDITS), extra.count("\n"), RC_APPEND))

    # 2. prop.default: replace the value of existing keys only.
    prop = _find(entries, PROP_FILE)
    lines = prop["data"].decode().split("\n")
    for raw_line in open(os.path.join(src_dir, PROP_OVERRIDES)):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, _value = line.partition("=")
        idx = [i for i, l in enumerate(lines) if l.startswith(key + "=")]
        if not idx:
            raise ValueError("prop.default has no %s to override" % key)
        for i in idx:
            notes.append("%s: %s -> %s" % (PROP_FILE, lines[i], line))
            lines[i] = line
    prop["data"] = "\n".join(lines).encode()

    # 3. rescue.sh: a new regular file next to the other programs.
    if any(e["name"] == RESCUE_PATH for e in entries):
        raise ValueError("ramdisk already has " + RESCUE_PATH)
    script = open(os.path.join(src_dir, RESCUE_SRC), "rb").read()
    if b"\r" in script:
        raise ValueError("rescue.sh has carriage returns")
    model = _find(entries, "system/bin/reboot")           # a regular root-owned program
    new = dict(model, name=RESCUE_PATH, data=script, mode=RESCUE_MODE,
               ino=max(e["ino"] for e in entries) + 1)
    names = [e["name"] for e in entries]
    after = max(i for i, n in enumerate(names) if n.startswith("system/bin/") and n < RESCUE_PATH)
    entries.insert(after + 1, new)
    notes.append("%s: added, %d bytes, mode %o, after %s" % (RESCUE_PATH, len(script), RESCUE_MODE, names[after]))
    return notes


# ---------------------------------------------------------------- AVB footer
def stock_vbmeta(img):
    ft = avblib.parse_footer(img[-avblib.FOOTER_SIZE:])
    if ft is None:
        raise ValueError("stock image has no AVB footer")
    vb = avblib.Vbmeta(img[ft["vbmeta_offset"]:ft["vbmeta_offset"] + ft["vbmeta_size"]])
    hashes = [d for d in vb.descriptors if d["type"] == "hash"]
    if len(hashes) != 1 or vb.descriptors[0] is not hashes[0] or hashes[0]["name"] != "recovery":
        raise ValueError("stock vbmeta does not start with exactly one hash descriptor for `recovery`")
    if vb.alg()[0] != "SHA256_RSA2048" or hashes[0]["hash_algorithm"] != "sha256":
        raise ValueError("stock vbmeta is not SHA256_RSA2048 / sha256")
    return ft, vb


def hash_descriptor(stock_desc, image):
    """The stock hash descriptor with image size and digest replaced (same length, same salt)."""
    raw = bytearray(stock_desc["raw"])
    digest = hashlib.sha256(stock_desc["salt"] + image).digest()
    struct.pack_into(">Q", raw, 16, len(image))
    end = 16 + struct.calcsize(avblib.HASH_FMT) + len(stock_desc["name"].encode()) + len(stock_desc["salt"])
    if bytes(raw[end:end + 32]) != stock_desc["digest"]:
        raise ValueError("hash descriptor layout is not what was expected")
    raw[end:end + 32] = digest
    return bytes(raw)


def add_footer(image, stock_vb, key, allow_other_key=False):
    """Return the full partition image: boot image, zero fill, signed vbmeta, zero fill, footer."""
    pub = avblib.encode_avb_pubkey(key[0], key[2])
    if pub != stock_vb.public_key and not allow_other_key:
        raise ValueError("the signing key is not the key the stock recovery is signed with; refusing")
    desc = hash_descriptor(stock_vb.descriptors[0], image)
    blob = avblib.rebuild_vbmeta(stock_vb, descriptors={0: desc},
                                 public_key=None if pub == stock_vb.public_key else pub, key=key)
    vb_off = (len(image) + AVB_BLOCK - 1) // AVB_BLOCK * AVB_BLOCK
    if vb_off + len(blob) > PARTITION_SIZE - avblib.FOOTER_SIZE:
        raise ValueError("image too large for the recovery partition")
    footer = struct.pack(avblib.FOOTER_FMT, b"AVBf", 1, 0, len(image), vb_off, len(blob), b"\0" * 28)
    out = bytearray(PARTITION_SIZE)
    out[:len(image)] = image
    out[vb_off:vb_off + len(blob)] = blob
    out[-avblib.FOOTER_SIZE:] = footer
    return bytes(out)


# ---------------------------------------------------------------- top level
def check_layout(super_path, src_dir):
    """Refuse unless the user's own `super` has `product` where the rescue.sh being packed writes it."""
    if not super_path:
        raise ValueError("no super.img given (BACKUP_DIR or --super): the product layout cannot be checked; refusing")
    px110conf.check_product_layout(super_path)
    script = open(os.path.join(src_dir, RESCUE_SRC)).read()
    found = re.findall(RESCUE_LAYOUT_RE, script, re.M)
    want = (str(px110conf.PRODUCT_FIRST_BLOCK), str(px110conf.PRODUCT_BYTES // 4096))
    if found != [want] or px110conf.PRODUCT_BYTES % 4096:
        raise ValueError("rescue.sh does not carry exactly the product position that was checked in super "
                         "(found %r, want %r); refusing" % (found, want))


def build(stock_path, key_path, src_dir=None, allow_other_key=False, log=print, super_path=None,
          allow_other_stock=False):
    """Return the partition image. src_dir=None means no ramdisk change (the re-sign of stock)."""
    if not stock_path:
        raise ValueError("no stock recovery.img given (BACKUP_DIR or --stock)")
    stock = open(stock_path, "rb").read()
    if len(stock) != PARTITION_SIZE:
        raise ValueError("stock recovery is %d bytes, expected %d" % (len(stock), PARTITION_SIZE))
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA256 and not allow_other_stock:
        raise ValueError("stock recovery image does not have the hash recorded for %s; refusing" % px110conf.FIRMWARE)
    if src_dir is not None:
        check_layout(super_path, src_dir)
    ft, vb = stock_vbmeta(stock)
    boot = unpack_boot(stock[:ft["original_image_size"]])
    if boot["size"] != ft["original_image_size"]:
        raise ValueError("boot image size does not match the footer's original image size")
    cpio = gunzip(boot["parts"]["ramdisk"])
    entries, _ = cpio_parse(cpio)
    if cpio_build(entries) != cpio:
        raise ValueError("cpio round trip is not byte-identical; refusing to go on")
    if gzip_like_stock(cpio) != boot["parts"]["ramdisk"]:
        raise ValueError("gzip round trip is not byte-identical with this Python's zlib; refusing to go on")
    if src_dir is not None:
        for note in apply_changes(entries, src_dir):
            log("  " + note)
        cpio = cpio_build(entries)
    image = pack_boot(boot, gzip_like_stock(cpio))
    key = avblib.load_private_key(key_path)
    return add_footer(image, vb, key, allow_other_key)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stock", default=DEF_STOCK)
    ap.add_argument("--key", default=DEF_KEY)
    ap.add_argument("--super", default=DEF_SUPER, dest="super_img",
                    help="your backed-up super.img; its product layout must be the one rescue.sh is fixed to")
    ap.add_argument("--src", default=DEF_SRC)
    ap.add_argument("--out-dir", default=DEF_OUT)
    ap.add_argument("--only", choices=("resigned", "rescue"), help="build just one of the two images")
    ap.add_argument("--out", help="with --only: write to this path instead of the default name")
    ap.add_argument("--allow-other-key", action="store_true",
                    help="TESTS ONLY: sign with a key that is not the stock one (the frame will reject the result)")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    jobs = [("resigned", "recovery-stock-resigned.img", None), ("rescue", "recovery-rescue.img", a.src)]
    sums = []
    for kind, name, src in jobs:
        if a.only and a.only != kind:
            continue
        print("building %s" % name)
        try:
            img = build(a.stock, a.key, src, a.allow_other_key, super_path=a.super_img)
        except (ValueError, OSError) as e:
            sys.exit("STOP: %s" % e)
        path = a.out if (a.only and a.out) else os.path.join(a.out_dir, name)
        with open(path, "wb") as f:
            f.write(img)
        digest = hashlib.sha256(img).hexdigest()
        sums.append((digest, name))
        print("  wrote %s (%d bytes) sha256 %s" % (path, len(img), digest))
    if not a.only:
        with open(os.path.join(a.out_dir, "SHA256SUMS"), "w") as f:
            for digest, name in sums:
                f.write("%s  %s\n" % (digest, name))


if __name__ == "__main__":
    main()
