"""Build a `boot` image for the frame that arms our recovery note first (offline; never talks to the frame).

Takes the stock boot.img (Android boot image v2 with an AVB hash footer), keeps the kernel, the dtb,
the command line and every other header field byte for byte, and changes the ramdisk in one way:
the stock first-stage `init` becomes `init.real`, and our small wrapper (src/bootwrap/bootwrap.c)
takes its place as `init`. The result is signed with MediaTek's published default boot key, the key
the frame's vbmeta already names for `boot`, so vbmeta needs no change.

The ramdisk is handled as a cpio "newc" archive in memory; nothing from it is written out or run.

Usage:
    python3 -I tools/bootbuild.py          build all three images into BUILD_DIR/out-boot/
    python3 -I tools/bootbuild.py --help
Settings (unit.conf or the environment, see px110conf.py): BACKUP_DIR, KEY_DIR, BUILD_DIR, CLANG, ARM_LD, ARM_STRIP.

Outputs (BUILD_DIR/out-boot/):
    boot-stock-resigned.img   stock, taken apart, put together again and re-signed. Must be byte-identical
                              to stock: it proves the packer, the key and the signer.
    boot-wrap.img             wrapper as /init, stock init untouched as /init.real.
    boot-wrap-recovery.img    the same, and in init.real the word a failed first stage restarts with is
                              changed from "bootloader" to "recovery" (see TARGET PATCH below).
    bootwrap.elf              the wrapper program exactly as it sits in the two images.
    SHA256SUMS
"""
import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avblib  # noqa: E402
import px110conf  # noqa: E402

PARTITION_SIZE = 33554432          # the frame's `boot` partition, 32 MiB
AVB_BLOCK = 4096
BOOT_MAGIC = b"ANDROID!"
HEADER_V2_SIZE = 1660

HERE = os.path.dirname(os.path.abspath(__file__))
_BACKUP = px110conf.path("BACKUP_DIR")
DEF_STOCK = os.path.join(_BACKUP, "boot.img") if _BACKUP else None
DEF_KEY = px110conf.key("boot_prvk.pem")
DEF_SRC = os.path.join(px110conf.SRC, "bootwrap", "bootwrap.c")
DEF_OUT = px110conf.build_dir("out-boot")

# ---------------------------------------------------------------- pinned inputs
STOCK_SHA256 = "d232adc9af4f5dfe12c6c8bc6548519ef2dc113693e1cc7ad9665b7041718172"      # stock boot.img of PF1106_V2.06_20250527
assert STOCK_SHA256 == px110conf.STOCK_SHA256["boot.img"]
KEY_SHA256 = "4db337d4ce0368f6223491ee19c89fc3e1a240693c8bb1d5d9920fdb7fdb0b05"        # boot_prvk.pem (fetch-keys.sh)
STOCK_INIT_SHA256 = "77c1a8025106ce9c95e56ba07dae4f4abd1f67683a42026de4e5e43ee20c00b2"   # the first-stage init inside it

# ---------------------------------------------------------------- RAMDISK CHANGES
INIT = "init"
REAL = "init.real"
CHANGED_FILES = sorted([INIT, REAL])

# ---------------------------------------------------------------- TARGET PATCH
# Stock first-stage init restarts with reboot(RESTART2, "bootloader") when it hits a fatal error
# (android::init::InitFatalReboot). The word comes from one string in .rodata, read by exactly one
# place (the static initialiser of init_fatal_reboot_target); src/bootwrap/initscan.py proves
# that from the program's code. The variant "recovery" replaces those 10 bytes and nothing else.
TARGET_OFFSET = 0x7740             # file offset inside the stock init
TARGET_OLD = b"\0bootloader\0"     # with the zero bytes on both sides, at TARGET_OFFSET - 1
TARGET_NEW = b"\0recovery\0\0\0"

VARIANTS = {
    # name: (output file, wrapper?, patch the restart target?)
    "resigned": ("boot-stock-resigned.img", False, False),
    "wrap": ("boot-wrap.img", True, False),
    "wrap-recovery": ("boot-wrap-recovery.img", True, True),
}

# ---------------------------------------------------------------- the wrapper program
CLANG_FLAGS = [
    "--target=armv7a-none-linux-gnueabi", "-march=armv7-a", "-marm", "-mfloat-abi=soft", "-mfpu=none",
    "-O1", "-ffreestanding", "-fno-builtin", "-nostdlib", "-fno-stack-protector", "-fno-pic",
    "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-fno-ident", "-Wall", "-Wextra", "-Werror",
]
LD_FLAGS = ["-static", "-nostdlib", "-e", "_start", "-Ttext-segment=0x10000", "-z", "max-page-size=4096",
            "-z", "noexecstack", "--build-id=none"]
STRIP_FLAGS = ["-s", "-R", ".comment", "-R", ".ARM.attributes", "-R", ".note.GNU-stack"]


def compile_wrapper(src=DEF_SRC):
    """Compile bootwrap.c to a static ARM program and return its bytes. Needs clang and
    arm-none-eabi binutils (ld, strip): on the PATH, or named by CLANG, ARM_LD and ARM_STRIP in
    unit.conf. No C library is involved. The bytes depend on the compiler and binutils versions."""
    clang = px110conf.tool("CLANG", "clang")
    ld = px110conf.tool("ARM_LD", "arm-none-eabi-ld")
    strip = px110conf.tool("ARM_STRIP", "arm-none-eabi-strip")
    for tool in (clang, ld, strip):
        if not shutil.which(tool):
            raise RuntimeError("%s not found (PATH, or CLANG / ARM_LD / ARM_STRIP in unit.conf)" % tool)
    with tempfile.TemporaryDirectory() as tmp:
        obj, elf = os.path.join(tmp, "bootwrap.o"), os.path.join(tmp, "bootwrap.elf")
        env = dict(os.environ, ZERO_AR_DATE="1", SOURCE_DATE_EPOCH="0")
        subprocess.run([clang] + CLANG_FLAGS + ["-c", src, "-o", obj], check=True, env=env)
        subprocess.run([ld] + LD_FLAGS + ["-o", elf, obj], check=True, env=env)
        subprocess.run([strip] + STRIP_FLAGS + [elf], check=True, env=env)
        with open(elf, "rb") as f:
            return f.read()


# ---------------------------------------------------------------- boot image v2
def _pages(n, page):
    return (n + page - 1) // page * page


PARTS = ("kernel", "ramdisk", "second", "recovery_dtbo", "dtb")


def unpack_boot(img):
    """Split an Android boot image v2 into its parts. Refuses anything it does not fully understand."""
    if img[:8] != BOOT_MAGIC:
        raise ValueError("not an Android boot image")
    (ksz, _kaddr, rsz, _raddr, ssz, _saddr, _tags, page, hver, _osv) = struct.unpack_from("<10I", img, 8)
    if hver != 2:
        raise ValueError("boot header version %d, expected 2" % hver)
    dbo_sz, dbo_off, hsize = struct.unpack_from("<IQI", img, 1632)
    dtb_sz, _dtb_addr = struct.unpack_from("<IQ", img, 1648)
    if hsize != HEADER_V2_SIZE or page != 2048:
        raise ValueError("unexpected header size %d or page size %d" % (hsize, page))
    if dbo_sz != 0 or dbo_off != 0 or ssz != 0:
        raise ValueError("this boot image has a second stage or a recovery dtbo; the stock one has neither")
    if any(img[HEADER_V2_SIZE:page]):
        raise ValueError("header page has data after the header")
    off = page
    parts = {}
    for name, size in zip(PARTS, (ksz, rsz, ssz, dbo_sz, dtb_sz)):
        parts[name] = img[off:off + size]
        if len(parts[name]) != size or any(img[off + size:off + _pages(size, page)]):
            raise ValueError("%s is cut short or its padding is not zero" % name)
        off += _pages(size, page)
    if boot_id(parts) != img[576:608]:
        raise ValueError("boot image id does not match its contents")
    return {"header": img[:HEADER_V2_SIZE], "page": page, "parts": parts, "size": off}


def boot_id(parts):
    """The header's id field: SHA-1 over each part followed by its length (as mkbootimg does), zero padded."""
    h = hashlib.sha1()
    for name in PARTS:
        h.update(parts[name])
        h.update(struct.pack("<I", len(parts[name])))
    return h.digest() + b"\0" * 12


def pack_boot(boot, ramdisk):
    """Rebuild the boot image with a new ramdisk. Only the ramdisk size and the id change in the header."""
    page = boot["page"]
    parts = dict(boot["parts"], ramdisk=ramdisk)
    header = bytearray(boot["header"])
    struct.pack_into("<I", header, 16, len(ramdisk))
    header[576:608] = boot_id(parts)
    out = bytearray(bytes(header) + b"\0" * (page - len(header)))
    for name in PARTS:
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
    return entries


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


def patch_target(init):
    """Stock init with the fatal-restart word changed from "bootloader" to "recovery". 10 bytes."""
    if hashlib.sha256(init).hexdigest() != STOCK_INIT_SHA256:
        raise ValueError("init is not the stock first-stage init this patch was proven on; refusing")
    at = TARGET_OFFSET - 1
    if init[at:at + len(TARGET_OLD)] != TARGET_OLD or init.count(b"bootloader") != 1:
        raise ValueError("the restart word is not where it was proven to be; refusing")
    out = init[:at] + TARGET_NEW + init[at + len(TARGET_OLD):]
    assert len(out) == len(init)
    return out


def apply_changes(entries, wrapper, patch):
    """init -> init.real (optionally with the restart word patched); the wrapper becomes init."""
    names = [e["name"] for e in entries]
    if names.count(INIT) != 1 or REAL in names:
        raise ValueError("ramdisk: expected exactly one init and no init.real")
    i = names.index(INIT)
    stock = entries[i]
    if stock["mode"] != 0o100750 or stock["uid"] or stock["gid"] or stock["nlink"] != 1:
        raise ValueError("ramdisk: stock init does not look as expected")
    if hashlib.sha256(stock["data"]).hexdigest() != STOCK_INIT_SHA256:
        raise ValueError("ramdisk: init is not the stock first-stage init; refusing")
    if wrapper[:4] != b"\x7fELF" or not 1024 <= len(wrapper) <= 65536:
        raise ValueError("the wrapper does not look like a small ELF program")
    real = dict(stock, name=REAL, data=patch_target(stock["data"]) if patch else stock["data"])
    new = dict(stock, name=INIT, data=wrapper)
    entries[i:i + 1] = [new, real]
    # mkbootfs numbers the entries in order, trailer included; keep that.
    base = min(e["ino"] for e in entries)
    for n, e in enumerate(entries):
        e["ino"] = base + n
    return ["%s: stock init (%d bytes), %s" % (REAL, len(real["data"]),
                                              "restart word bootloader -> recovery" if patch else "unchanged"),
            "%s: wrapper, %d bytes, mode %o" % (INIT, len(wrapper), new["mode"])]


# ---------------------------------------------------------------- AVB footer
def stock_vbmeta(img):
    ft = avblib.parse_footer(img[-avblib.FOOTER_SIZE:])
    if ft is None:
        raise ValueError("stock image has no AVB footer")
    vb = avblib.Vbmeta(img[ft["vbmeta_offset"]:ft["vbmeta_offset"] + ft["vbmeta_size"]])
    hashes = [d for d in vb.descriptors if d["type"] == "hash"]
    if len(hashes) != 1 or vb.descriptors[0] is not hashes[0] or hashes[0]["name"] != "boot":
        raise ValueError("stock vbmeta does not start with exactly one hash descriptor for `boot`")
    if vb.alg()[0] != "SHA256_RSA2048" or hashes[0]["hash_algorithm"] != "sha256":
        raise ValueError("stock vbmeta is not SHA256_RSA2048 / sha256")
    vb.verify()
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
        raise ValueError("the signing key is not the key the stock boot image is signed with; refusing")
    desc = hash_descriptor(stock_vb.descriptors[0], image)
    blob = avblib.rebuild_vbmeta(stock_vb, descriptors={0: desc},
                                 public_key=None if pub == stock_vb.public_key else pub, key=key)
    vb_off = (len(image) + AVB_BLOCK - 1) // AVB_BLOCK * AVB_BLOCK
    if vb_off + len(blob) > PARTITION_SIZE - avblib.FOOTER_SIZE:
        raise ValueError("image too large for the boot partition")
    footer = struct.pack(avblib.FOOTER_FMT, b"AVBf", 1, 0, len(image), vb_off, len(blob), b"\0" * 28)
    out = bytearray(PARTITION_SIZE)
    out[:len(image)] = image
    out[vb_off:vb_off + len(blob)] = blob
    out[-avblib.FOOTER_SIZE:] = footer
    return bytes(out)


# ---------------------------------------------------------------- top level
def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _sha(path):
    return hashlib.sha256(_read(path)).hexdigest()


def build(stock_path, key_path, wrapper=None, patch=False, allow_other_key=False, allow_other_stock=False, log=print):
    """Return the partition image. wrapper=None means no ramdisk change (the re-sign of stock)."""
    if not stock_path:
        raise ValueError("no stock boot.img given (BACKUP_DIR or --stock)")
    stock = _read(stock_path)
    if len(stock) != PARTITION_SIZE:
        raise ValueError("stock boot is %d bytes, expected %d" % (len(stock), PARTITION_SIZE))
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA256 and not allow_other_stock:
        raise ValueError("stock boot image does not have its recorded hash; refusing")
    if _sha(key_path) != KEY_SHA256 and not allow_other_key:
        raise ValueError("the key file does not have its pinned hash (see fetch-keys.sh); refusing")
    ft, vb = stock_vbmeta(stock)
    boot = unpack_boot(stock[:ft["original_image_size"]])
    if boot["size"] != ft["original_image_size"]:
        raise ValueError("boot image size does not match the footer's original image size")
    cpio = gunzip(boot["parts"]["ramdisk"])
    entries = cpio_parse(cpio)
    if cpio_build(entries) != cpio:
        raise ValueError("cpio round trip is not byte-identical; refusing to go on")
    if gzip_like_stock(cpio) != boot["parts"]["ramdisk"]:
        raise ValueError("gzip round trip is not byte-identical with this Python's zlib; refusing to go on")
    if wrapper is not None:
        for note in apply_changes(entries, wrapper, patch):
            log("  " + note)
        cpio = cpio_build(entries)
    elif patch:
        raise ValueError("the restart-word patch is only built together with the wrapper")
    image = pack_boot(boot, gzip_like_stock(cpio))
    key = avblib.load_private_key(key_path)
    return add_footer(image, vb, key, allow_other_key)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stock", default=DEF_STOCK)
    ap.add_argument("--key", default=DEF_KEY)
    ap.add_argument("--src", default=DEF_SRC)
    ap.add_argument("--out-dir", default=DEF_OUT)
    ap.add_argument("--only", choices=sorted(VARIANTS), help="build just one of the images")
    ap.add_argument("--out", help="with --only: write to this path instead of the default name")
    ap.add_argument("--wrapper", help="use this already-built wrapper instead of compiling (tests)")
    ap.add_argument("--allow-other-key", action="store_true",
                    help="TESTS ONLY: sign with a key that is not the stock one (the frame will reject the result)")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    wrapper = _read(a.wrapper) if a.wrapper else compile_wrapper(a.src)
    sums = []
    if not a.only:
        with open(os.path.join(a.out_dir, "bootwrap.elf"), "wb") as f:
            f.write(wrapper)
        sums.append((hashlib.sha256(wrapper).hexdigest(), "bootwrap.elf"))
        print("wrapper: %d bytes, sha256 %s" % (len(wrapper), sums[0][0]))
    for kind in ("resigned", "wrap", "wrap-recovery"):
        name, wrapped, patch = VARIANTS[kind]
        if a.only and a.only != kind:
            continue
        print("building %s" % name)
        img = build(a.stock, a.key, wrapper if wrapped else None, patch, a.allow_other_key)
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
