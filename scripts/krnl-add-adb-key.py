#!/usr/bin/env python3
"""Add an ADB public key as /adb_keys to a Rockchip KRNL-wrapped boot image.

A KRNL image is: b"KRNL" + uint32 LE payload length + payload (gzip'd newc
cpio ramdisk) + uint32 LE Rockchip CRC32 of the payload. Everything after
that is padding up to the partition size.

The script checks the input's magic and CRC, refuses an image that already
has /adb_keys, appends one cpio entry (root:root 0644) before the trailer and
keeps every other entry byte for byte. The output is the same size as the
input, so it can be written back over the whole partition.

  krnl-add-adb-key.py boot.img ~/.android/adbkey.pub boot-patched.img
"""
import gzip
import struct
import sys

TRAILER = b"TRAILER!!!"


def rk_crc_table():
    table = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C10DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
        table.append(c)
    return table


TABLE = rk_crc_table()


def rk_crc(data):
    c = 0
    for b in data:
        c = ((c << 8) & 0xFFFFFFFF) ^ TABLE[(c >> 24) ^ b]
    return c


def align4(n):
    return (n + 3) & ~3


def parse_cpio(raw):
    """Return [(name, entry_bytes)] up to and including the trailer, and the rest."""
    entries, off = [], 0
    while True:
        hdr = raw[off:off + 110]
        if hdr[:6] != b"070701":
            sys.exit(f"not a newc cpio entry at offset {off}")
        fields = [int(hdr[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        filesize, namesize = fields[6], fields[11]
        name = raw[off + 110:off + 110 + namesize - 1]
        end = align4(align4(off + 110 + namesize) + filesize)
        entries.append((name, raw[off:end]))
        off = end
        if name == TRAILER:
            return entries, raw[off:]


def cpio_entry(name, data, ino, mtime):
    name_z = name + b"\0"
    values = [ino, 0o100644, 0, 0, 1, mtime, len(data), 0, 0, 0, 0, len(name_z), 0]
    out = b"070701" + b"".join(b"%08X" % v for v in values) + name_z
    out += b"\0" * (align4(len(out)) - len(out))
    out += data
    out += b"\0" * (align4(len(out)) - len(out))
    return out


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    src, key_path, dst = sys.argv[1:]
    image = open(src, "rb").read()
    if image[:4] != b"KRNL":
        sys.exit("input is not a KRNL image (an ANDROID! boot image needs a different tool)")
    length = struct.unpack("<I", image[4:8])[0]
    payload = image[8:8 + length]
    stored_crc = struct.unpack("<I", image[8 + length:12 + length])[0]
    if rk_crc(payload) != stored_crc:
        sys.exit("CRC mismatch: input is not a clean KRNL image, stopping")

    raw = gzip.decompress(payload)
    entries, tail = parse_cpio(raw)
    if any(name == b"adb_keys" for name, _ in entries):
        sys.exit("ramdisk already has /adb_keys; edit it by hand instead")

    key = open(key_path, "rb").read()
    if not key.startswith(b"QAAAA"):
        sys.exit(f"{key_path} does not look like an ADB public key (adbkey.pub)")
    if not key.endswith(b"\n"):
        key += b"\n"

    ino = max(int(e[6:14], 16) for _, e in entries) + 1
    mtime = int(entries[0][1][46:54], 16)
    new_raw = b"".join(e for _, e in entries[:-1]) + cpio_entry(b"adb_keys", key, ino, mtime) + entries[-1][1] + tail

    new_payload = gzip.compress(new_raw, compresslevel=9, mtime=0)
    blob = b"KRNL" + struct.pack("<I", len(new_payload)) + new_payload + struct.pack("<I", rk_crc(new_payload))
    if len(blob) > len(image):
        sys.exit("patched image is larger than the partition image")
    open(dst, "wb").write(blob + image[len(blob):])
    print(f"wrote {dst}: payload {length} -> {len(new_payload)} bytes, {len(entries) + 1} cpio entries")


if __name__ == "__main__":
    main()
