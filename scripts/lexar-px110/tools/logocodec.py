#!/usr/bin/env python3
"""MediaTek logo.img (partition 'logo') decoder/encoder. Offline only.

Layout (verified on the Lexar PX-110 backup):
  0x000  512-byte MTK header: magic 0x58881688, u32 payload_size, char name[32]="logo", then
         ext header (magic 0x58891689, hdr_size 0x200, ...) padded with 0xFF.
  0x200  payload: u32 count, u32 total_size, u32 offset[count] (offsets relative to payload start),
         then count zlib streams (each decompresses to a raw 32-bit-per-pixel picture).
  after  16-byte-aligned? (here: 9 zero bytes then) MTK 'cert1' and 'cert2' blobs (each with its own
         512-byte header), then zeros to the end of the 8 MB partition.
cert2 holds sha256(payload padded to 16 bytes). Changing the payload therefore invalidates
the secure-boot signature (see report). This tool keeps cert blobs verbatim.
"""
import struct, zlib, sys, os, hashlib

MAGIC = 0x58881688

def parse(d):
    magic, psize = struct.unpack_from('<II', d, 0)
    assert magic == MAGIC, hex(magic)
    name = d[8:40].split(b'\0')[0]
    pay = d[0x200:0x200 + psize]
    n, total = struct.unpack_from('<II', pay, 0)
    assert total == psize
    offs = list(struct.unpack_from('<%dI' % n, pay, 8)) + [total]
    blobs = [pay[offs[i]:offs[i + 1]] for i in range(n)]
    tail = d[0x200 + psize:]
    return dict(hdr=d[:0x200], name=name, n=n, offs=offs[:-1], blobs=blobs, tail=tail, psize=psize)

def decode(d):
    p = parse(d)
    return [zlib.decompress(b) for b in p['blobs']], p

def build_payload(raws, level=9, template_blobs=None):
    """zlib-compress each raw picture. If template_blobs is given and decompresses to the same raw,
    reuse the original compressed bytes (keeps byte-exact round-trip)."""
    blobs = []
    for i, r in enumerate(raws):
        if template_blobs and i < len(template_blobs) and zlib.decompress(template_blobs[i]) == r:
            blobs.append(template_blobs[i])
        else:
            blobs.append(zlib.compress(r, level))
    n = len(blobs)
    off = 8 + 4 * n
    offs = []
    for b in blobs:
        offs.append(off); off += len(b)
    return struct.pack('<II', n, off) + struct.pack('<%dI' % n, *offs) + b''.join(blobs)

def encode(raws, template):
    """Rebuild a full logo.img image from raws using template (original file bytes) for header/tail/size."""
    t = parse(template)
    pay = build_payload(raws)  # pure re-compression: zlib level 9 reproduces the stock streams exactly
    hdr = bytearray(t['hdr']); struct.pack_into('<I', hdr, 4, len(pay))
    out = bytes(hdr) + pay
    # certs/tail: keep verbatim position-independent: tail begins right after the payload in the original
    # (original tail starts with 9 alignment bytes then cert1). Keep the tail but re-align to the same
    # absolute offset when the payload size is unchanged; otherwise caller must re-sign (not possible offline).
    if len(pay) == t['psize']:
        out += t['tail']
    else:
        out += t['tail']  # certificate no longer matches; flagged in the report
    total = len(template)
    out = out[:total] if len(out) >= total else out + b'\xff' * 0 + b'\0' * (total - len(out))
    return out

def png(path, w, h, rgba):
    def chunk(t, c):
        x = struct.pack('>I', len(c)) + t + c
        return x + struct.pack('>I', zlib.crc32(t + c) & 0xffffffff)
    raw = b''.join(b'\0' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
                           chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'list':
        d = open(sys.argv[2], 'rb').read(); raws, p = decode(d)
        print('name', p['name'], 'payload', p['psize'], 'pictures', p['n'])
        for i, r in enumerate(raws):
            print(i, 'compressed', len(p['blobs'][i]), 'raw', len(r), 'px', len(r) // 4)
    elif cmd == 'extract':
        d = open(sys.argv[2], 'rb').read(); out = sys.argv[3]; os.makedirs(out, exist_ok=True)
        raws, p = decode(d)
        for i, r in enumerate(raws): open('%s/%02d.raw' % (out, i), 'wb').write(r)
    elif cmd == 'roundtrip':
        d = open(sys.argv[2], 'rb').read(); raws, p = decode(d)
        e = encode(raws, d); print('byte-exact:', e == d, len(e), len(d))
