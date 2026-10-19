"""Write a new bootlogo.bmp into a copy of the PF1506 'bootloader' partition (FAT16)
in place: same size, same header, same clusters. Only the pixel bytes change; the FAT
tables and directory entries are not touched. The new BMP must match the stock format
exactly (checked), and the result is read back and compared before it is written.

usage: patch_logo.py <orig.img> <new-logo.bmp> <out.img>
"""
import os
import struct
import sys

orig_img, new_bmp, out_img = sys.argv[1:4]
if os.path.exists(out_img):
    sys.exit(f"{out_img} exists; not overwriting")
img = bytearray(open(orig_img, "rb").read())

# FAT16 boot sector (BPB)
bps, spc, reserved, nfats, root_entries = struct.unpack_from("<HBHBH", img, 11)
sectors_per_fat = struct.unpack_from("<H", img, 22)[0]
fat_off = reserved * bps
root_off = fat_off + nfats * sectors_per_fat * bps
data_off = root_off + root_entries * 32
cluster_bytes = spc * bps

# Root directory entry for BOOTLOGO.BMP
for i in range(root_entries):
    e = root_off + i * 32
    if img[e:e + 11] == b"BOOTLOGOBMP":
        first_cluster = struct.unpack_from("<H", img, e + 26)[0]
        size = struct.unpack_from("<I", img, e + 28)[0]
        break
else:
    sys.exit("BOOTLOGO.BMP not found")

# Cluster chain from the first FAT copy
chain, c = [], first_cluster
while 2 <= c < 0xFFF8:
    chain.append(c)
    c = struct.unpack_from("<H", img, fat_off + c * 2)[0]
assert len(chain) * cluster_bytes >= size, "chain shorter than file"

def read_file(image):
    return b"".join(image[data_off + (c - 2) * cluster_bytes:][:cluster_bytes] for c in chain)[:size]


def check_bmp(b, what):
    """Exactly the stock format: BM, 54-byte header (40-byte BITMAPINFOHEADER), 1920x1080
    bottom-up (positive height), 1 plane, 24 bits, no compression, and all pixel bytes present."""
    if b[:2] != b"BM":
        sys.exit(f"{what}: not a BMP")
    off, hdr = struct.unpack_from("<II", b, 10)
    w, h, planes, bpp, comp = struct.unpack_from("<iiHHI", b, 18)
    want = (54, 40, 1920, 1080, 1, 24, 0)
    if (off, hdr, w, h, planes, bpp, comp) != want:
        sys.exit(f"{what}: offset/header/width/height/planes/bits/compression = "
                 f"{(off, hdr, w, h, planes, bpp, comp)}, need {want}")
    if len(b) < 54 + PIXELS:
        sys.exit(f"{what}: {len(b)} bytes, too short for 1920x1080x3 pixels")


PIXELS = 1920 * 1080 * 3          # rows of 5760 bytes: already 4-byte aligned, no padding
old = read_file(img)
new = open(new_bmp, "rb").read()
check_bmp(old, "stock BOOTLOGO.BMP")
check_bmp(new, new_bmp)
data = old[:54] + new[54:54 + PIXELS] + old[54 + PIXELS:]    # original header + trailing bytes
assert len(data) == size

for n, c in enumerate(chain):
    chunk = data[n * cluster_bytes:(n + 1) * cluster_bytes]
    if not chunk:
        break
    start = data_off + (c - 2) * cluster_bytes
    img[start:start + len(chunk)] = chunk

orig = open(orig_img, "rb").read()
assert len(img) == len(orig), "image size changed"
assert read_file(img) == data, "read-back of BOOTLOGO.BMP does not match"
# Every changed byte must be inside the logo's own clusters: blank those clusters in
# both copies and the rest must be identical.
a, b = bytearray(img), bytearray(orig)
for c in chain:
    start = data_off + (c - 2) * cluster_bytes
    a[start:start + cluster_bytes] = b[start:start + cluster_bytes] = bytes(cluster_bytes)
if a != b:
    sys.exit("bytes outside BOOTLOGO.BMP would change; nothing written")
open(out_img, "wb").write(img)
print(f"patched {size} bytes across {len(chain)} clusters (first {first_cluster}); read back OK")
