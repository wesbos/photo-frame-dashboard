#!/usr/bin/env python3
"""Build a patched PF1007 boot image OFFLINE from the verified eMMC dump.

Nothing here touches the frame. It reads backups/pf1007-emmc/, checks the chunks
against SHA256SUMS, cuts out the boot partition (p6), and changes the ramdisk only:

  1. default.prop: ro.adb.secure=1 (adbd demands key auth), service.adb.tcp.port=5555
  2. /adb_keys: exactly one key, the PC's adbkey.pub
  3. init.rc: `on boot` starts adbd, so Wi-Fi ADB comes up whatever sys.usb.config is

Everything else (kernel, header fields, other cpio entries) stays byte-identical, and
the output is padded to the original image size. Run with `python -I`.

  python -I scripts/a33-sdboot/patch-boot.py --pubkey ~/.android/adbkey.pub --out DIR

Other boards with p6 at the same sector (the SOMY/Pastigio ZC002 family, M10R7): first print
that board's boot image length and SHA-256, then pass both. build-write.sh only builds a write
for images in TESTED:

  python -I scripts/a33-sdboot/patch-boot.py --inspect
  python -I scripts/a33-sdboot/patch-boot.py --pubkey ... --out DIR --boot-len N --expect-sha256 H
"""
import argparse
import gzip
import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECTOR = 512
BOOT_START_SECTOR = 172032  # p6, from docs/allwinner-a33-sdcard-adb-wifi.md
BOOT_LEN = 15_886_336  # kernel 10,221,784 + ramdisk 5,660,297 padded to 2048
CHUNK = 64 * 1024 * 1024
TCP_PORT = "5555"
# Tested original boot images at p6: SHA-256 -> bytes. Keep in step with TESTED in build-write.sh.
TESTED = {
    "d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4": 15_886_336,  # PF1007L 20260113
    "529ef1ee32e546e847f532c640922800d05edff986bb819f6dd9fa38c3c650be": 14_911_488,  # SOMY M10R7_20260313
    "4eb4a3bdf6a14b8239c6870f23bd29715ab1e46fbb4ae996bd5d593377c47b3b": 14_962_688,  # ALONG B-102K-Z_20240110
}


def die(msg):
    sys.exit(f"STOP: {msg}")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def read_boot(dump, boot_len):
    sums = {}
    for line in (dump / "SHA256SUMS").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            sums[parts[1].lstrip("*")] = parts[0]
    start = BOOT_START_SECTOR * SECTOR
    first, last = start // CHUNK, (start + boot_len - 1) // CHUNK
    buf = b""
    for i in range(first, last + 1):
        name = f"emmc-{i:02x}.bin"
        data = (dump / name).read_bytes()
        if len(data) != CHUNK:
            die(f"{name} is {len(data)} bytes, expected {CHUNK}")
        if sums.get(name) != sha256(data):
            die(f"{name} does not match SHA256SUMS")
        buf += data
    off = start - first * CHUNK
    return buf[off:off + boot_len]


def parse_header(img):
    if img[:8] != b"ANDROID!":
        die("no ANDROID! magic at the start of p6")
    (ksz, kaddr, rsz, raddr, ssz, saddr, taddr, page, dtsz) = struct.unpack_from("<9I", img, 8)
    return dict(ksz=ksz, rsz=rsz, ssz=ssz, page=page, dtsz=dtsz)


def layout(h):
    pg = h["page"]
    up = lambda n: (n + pg - 1) // pg * pg
    koff = pg
    roff = koff + up(h["ksz"])
    soff = roff + up(h["rsz"])
    doff = soff + up(h["ssz"])
    return koff, roff, soff, doff, up


def boot_id(img, h, rd):
    koff, roff, soff, doff, _ = layout(h)
    s = hashlib.sha1()
    s.update(img[koff:koff + h["ksz"]]); s.update(struct.pack("<I", h["ksz"]))
    s.update(rd); s.update(struct.pack("<I", len(rd)))
    s.update(img[soff:soff + h["ssz"]]); s.update(struct.pack("<I", h["ssz"]))
    if h["dtsz"]:
        s.update(img[doff:doff + h["dtsz"]]); s.update(struct.pack("<I", h["dtsz"]))
    return s.digest().ljust(32, b"\0")


# ---- newc cpio -------------------------------------------------------------
def cpio_parse(raw):
    ents, p = [], 0
    while True:
        if raw[p:p + 6] != b"070701":
            die(f"bad cpio magic at {p}")
        f = [int(raw[p + 6 + 8 * i:p + 14 + 8 * i], 16) for i in range(13)]
        ino, mode, uid, gid, nlink, mtime, fsz, dmaj, dmin, rmaj, rmin, nsz, chk = f
        name = raw[p + 110:p + 110 + nsz - 1].decode()
        p = (p + 110 + nsz + 3) & ~3
        data = raw[p:p + fsz]
        p = (p + fsz + 3) & ~3
        ents.append(dict(f=f, name=name, data=data))
        if name == "TRAILER!!!":
            return ents, p


def cpio_pack(ents):
    out = bytearray()
    for e in ents:
        f = list(e["f"])
        nb = e["name"].encode() + b"\0"
        f[6], f[11] = len(e["data"]), len(nb)
        out += b"070701" + b"".join(b"%08x" % v for v in f) + nb
        out += b"\0" * (-len(out) % 4)
        out += e["data"]
        out += b"\0" * (-len(out) % 4)
    return bytes(out)


def new_entry(like, name, data, mode, ino):
    f = list(like["f"])
    f[0], f[1], f[2], f[3], f[4] = ino, mode, 0, 0, 1
    return dict(f=f, name=name, data=data)

def patch_ramdisk(raw, key_line):
    ents, end = cpio_parse(raw)
    tail = raw[end:]
    if cpio_pack(ents) + tail != raw:
        die("cpio writer does not reproduce the original ramdisk byte for byte")
    by = {e["name"]: e for e in ents}
    if "adb_keys" in by:
        die("ramdisk already has /adb_keys; refusing to guess")
    for need in ("default.prop", "init.rc"):
        if need not in by:
            die(f"{need} missing from ramdisk")

    dp = by["default.prop"]["data"].decode()
    if "ro.adb.secure" in dp or "service.adb.tcp.port" in dp:
        die("default.prop already sets adb props")
    dp = dp.replace("persist.sys.usb.config=none","persist.sys.usb.config=adb")
    if not dp.endswith("\n"):
        dp += "\n"
    dp += f"ro.adb.secure=1\nservice.adb.tcp.port={TCP_PORT}\n"
    by["default.prop"]["data"] = dp.encode()

    rc = by["init.rc"]["data"].decode()
    rc = rc.replace("service adbd /sbin/adbd --root_seclabel=u:r:su:s0", "service adbd /sbin/adbd")
    if not rc.endswith("\n"):
        rc += "\n"
    rc += (
        "\n# a33: Wi-Fi ADB (key auth, /adb_keys) regardless of sys.usb.config\n"
        "on boot\n"
        "    start adbd\n"
    )
    by["init.rc"]["data"] = rc.encode()

    trailer = ents.pop()
    inos = [e["f"][0] for e in ents]
    dpmode = by["default.prop"]["f"][1]
    ents.append(new_entry(by["default.prop"], "adb_keys", key_line.encode(), dpmode, max(inos) + 1))
    ents.append(trailer)
    out = cpio_pack(ents)
    if len(raw) % 512 == 0:
        out += b"\0" * (-len(out) % 512)
    return out, dpmode


def inspect(dump):
    """Length and hash of the Android boot image at p6, read from its own header."""
    head = read_boot(dump, 4096)
    h = parse_header(head)
    if h["page"] != 2048:
        die(f"unexpected page size {h['page']}")
    koff, roff, soff, doff, up = layout(h)
    n = h["page"] + up(h["ksz"]) + up(h["rsz"]) + up(h["ssz"]) + up(h["dtsz"])
    img = read_boot(dump, n)
    ok = boot_id(img, h, img[roff:roff + h["rsz"]]) == img[0x240:0x260]
    print(f"boot image at sector {BOOT_START_SECTOR}: page {h['page']}, kernel {h['ksz']}, ramdisk {h['rsz']}")
    print(f"--boot-len {n} --expect-sha256 {sha256(img)}")
    print(f"header boot id matches: {ok}")
    if TESTED.get(sha256(img)) == n:
        print("this is a tested boot image")
    else:
        print("this boot image is not in TESTED: build-write.sh will refuse it. Open a PR with this output")
    if h["ssz"] or h["dtsz"]:
        print("this image has second/dt sections: this builder can't patch it")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(ROOT / "backups" / "pf1007-emmc"))
    ap.add_argument("--pubkey")
    ap.add_argument("--out")
    ap.add_argument("--inspect", action="store_true",
                    help="only print the boot image's length and SHA-256 from the dump, then exit")
    ap.add_argument("--boot-len", type=int, default=BOOT_LEN,
                    help="length of the original boot image in bytes (default: the PF1007L's)")
    ap.add_argument("--expect-sha256",
                    help="stop unless the original boot image has this SHA-256")
    a = ap.parse_args()
    if a.inspect:
        return inspect(Path(a.dump))
    if not (a.pubkey and a.out):
        ap.error("--pubkey and --out are required (or use --inspect)")
    if a.boot_len != BOOT_LEN and not a.expect_sha256:
        ap.error("--boot-len needs --expect-sha256")
    boot_len = a.boot_len

    key = Path(a.pubkey).expanduser().read_text().strip().replace("\r", "")
    if "\n" in key or len(key.split(" ")[0]) < 600:
        die("pubkey must be a single adbkey.pub line")
    key_line = key + "\n"

    img = read_boot(Path(a.dump), boot_len)
    if a.expect_sha256 and sha256(img) != a.expect_sha256.lower():
        die(f"p6 in the dump is {sha256(img)}, not the expected {a.expect_sha256}")
    h = parse_header(img)
    if h["page"] != 2048:
        die(f"unexpected page size {h['page']}")
    koff, roff, soff, doff, up = layout(h)
    if h["ssz"] or h["dtsz"]:
        die("image has second/dt sections; this builder assumes none")
    if up(h["ksz"]) + up(h["rsz"]) + h["page"] != boot_len:
        die("header sizes do not add up to the expected image length")
    rd_gz = img[roff:roff + h["rsz"]]
    if boot_id(img, h, rd_gz) != img[0x240:0x260]:
        die("computed boot id differs from the header's; parser is wrong")
    raw = gzip.decompress(rd_gz)

    new_raw, mode = patch_ramdisk(raw, key_line)
    new_gz = gzip.compress(new_raw, 9, mtime=0)
    if up(len(new_gz)) > up(h["rsz"]):
        die(f"new ramdisk {len(new_gz)} B needs more pages than the original {h['rsz']} B")

    new = bytearray(img)
    new[roff:roff + up(h["rsz"])] = new_gz.ljust(up(h["rsz"]), b"\0")
    struct.pack_into("<I", new, 16, len(new_gz))  # ramdisk_size
    new[0x240:0x260] = boot_id(bytes(new), dict(h, rsz=len(new_gz)), new_gz)
    new = bytes(new)
    if len(new) != boot_len:
        die("size changed")
    if img[koff:koff + h["ksz"]] != new[koff:koff + h["ksz"]]:
        die("kernel region changed")
    if img[:16] != new[:16] or img[20:0x240] != new[20:0x240] or img[0x260:koff] != new[0x260:koff]:
        die("header changed outside the ramdisk size and boot id")
    if img[roff + up(h["rsz"]):] != new[roff + up(h["rsz"]):]:
        die("bytes after the ramdisk slot changed")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "boot-original.img").write_bytes(img)
    (out / "boot-patched.img").write_bytes(new)
    diff = [i for i in range(len(img)) if img[i] != new[i]]
    rep = [
        f"original  {sha256(img)}  {len(img)} B",
        f"patched   {sha256(new)}  {len(new)} B",
        f"ramdisk   {h['rsz']} -> {len(new_gz)} B (gzip), raw {len(raw)} -> {len(new_raw)} B",
        f"differing bytes {len(diff)}, first {diff[0]}, last {diff[-1]}",
        f"kernel region identical: {img[koff:koff+h['ksz']] == new[koff:koff+h['ksz']]}",
        f"header identical except size/id: "
        f"{img[:16] == new[:16] and img[20:0x240] == new[20:0x240]}",
        f"/adb_keys mode {mode:o}, key sha256 {sha256(key_line.encode())}",
    ]
    (out / "REPORT.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
