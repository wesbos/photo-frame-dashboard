#!/usr/bin/env python3
"""Checks every MediaTek cert1/cert2 signature pair inside a partition image (lk, lk2, tee1, tee2, logo...).
Offline only; reads files, writes none.

    python3 -I tools/certverify.py <image> [<image> ...] [--keys KEY_DIR]

For each signed piece (a payload followed by cert1 and cert2) it checks, with logoverify.py's own routines:
  root key        cert1's own public key is the key built into the backed-up lk.img and preloader
  cert1 signature cert1 is signed by that root key
  key match       cert2's public key is the image key that cert1 carries
  cert2 signature cert2 is signed by that image key
  data hash       cert2's data hash = SHA-256 of the payload zero-padded to 16 bytes
  header hash     cert2's header hash = SHA-256 of the payload's own 512-byte header
and says whether the root key and the image key are ones we hold (private keys in --keys).
Exit status 0 if every piece passes, 1 otherwise.
"""
import hashlib, os, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logoverify as lv  # noqa: E402
import px110conf  # noqa: E402  (where the key files are)

MAGIC = 0x58881688


def walk(d):
    """-> [(offset, name, payload bytes, header bytes)] for the chain of MediaTek sub-images at the start of d."""
    out = []; o = 0
    while o + 0x200 <= len(d) and struct.unpack_from('<I', d, o)[0] == MAGIC:
        size = struct.unpack_from('<I', d, o + 4)[0]
        name = d[o + 8:o + 40].split(b'\0')[0].decode('ascii', 'replace')
        magic2, hdr = struct.unpack_from('<II', d, o + 0x30)
        align = struct.unpack_from('<I', d, o + 0x44)[0] or 1
        if magic2 != 0x58891689 or hdr != 0x200 or o + hdr + size > len(d):
            break
        out.append((o, name, d[o + hdr:o + hdr + size], d[o:o + hdr]))
        o = (o + hdr + size + align - 1) // align * align
    return out


def held_keys(keydir):
    """-> {modulus int: file name} for every private key in keydir."""
    out = {}
    if not os.path.isdir(keydir):
        return out
    for f in sorted(os.listdir(keydir)):
        if f.endswith('.pem'):
            r = subprocess.run(['openssl', 'rsa', '-in', os.path.join(keydir, f), '-noout', '-modulus'],
                               capture_output=True, text=True)
            if r.returncode == 0 and 'Modulus=' in r.stdout:
                out[int(r.stdout.strip().split('=')[1], 16)] = f
    return out


def check_image(path, keys, lk_path, pl_path, say):
    d = open(path, 'rb').read()
    parts = walk(d)
    lv.need(parts, 'layout', 'no MediaTek image header at the start')
    lk = open(lk_path, 'rb').read(); pl = open(pl_path, 'rb').read()
    pieces = 0; i = 0
    while i < len(parts):
        off, name, pay, hdr = parts[i]
        lv.need(name not in ('cert1', 'cert2'), 'layout', 'certificate at 0x%X without a payload before it' % off)
        if not (i + 2 < len(parts) and parts[i + 1][1] == 'cert1' and parts[i + 2][1] == 'cert2'):
            say('  %-12s at 0x%X: %d bytes, NOT SIGNED (no cert1/cert2 after it)' % (name, off, len(pay)))
            i += 1; continue
        tag = '%s/%s' % (os.path.basename(path), name)
        c1 = lv.split_cert(parts[i + 1][2], tag + ' shape'); c2 = lv.split_cert(parts[i + 2][2], tag + ' shape')
        image_key = lv.value_after(c1, b'\x01\x02', tag + ' shape')
        root_n, _ = lv.rsa_public(c1['spki']); img_n, _ = lv.rsa_public(image_key)
        raw = root_n.to_bytes(256, 'big')
        lv.need(raw in lk, tag + ' root key', "cert1's key is not inside the backed-up lk.img")
        lv.need(raw in pl, tag + ' root key', "cert1's key is not inside the backed-up preloader")
        lv.check_signature(tag + ' cert1 signature', c1['spki'], c1['tbs'], c1['sig'])
        lv.need(c2['spki'] == image_key, tag + ' key match', "cert2's key is not the image key in cert1")
        lv.check_signature(tag + ' cert2 signature', image_key, c2['tbs'], c2['sig'])
        got = hashlib.sha256(pay + b'\0' * (-len(pay) % 16)).digest()
        lv.need(got == lv.hash_value(c2, b'\x02\x01', tag + ' shape'), tag + ' data hash', 'payload hash differs')
        lv.need(hashlib.sha256(hdr).digest() == lv.hash_value(c2, b'\x02\x04', tag + ' shape'),
                tag + ' header hash', 'header hash differs')
        say('  %-12s at 0x%X: %d bytes, cert1+cert2 verify; root key %s (%s), image key %s (%s)'
            % (name, off, len(pay), raw[:4].hex(), keys.get(root_n, 'NOT HELD'),
               img_n.to_bytes(256, 'big')[:4].hex(), keys.get(img_n, 'not held')))
        pieces += 1; i += 3
    end = parts[-1][0] + 0x200 + len(parts[-1][2])
    say('  %d signed piece(s); bytes after the chain (from 0x%X): %s'
        % (pieces, end, 'all zero' if not any(d[end:]) else 'NOT all zero'))
    return pieces


def main(argv):
    args = argv[1:]
    keydir = os.path.dirname(px110conf.key('x'))
    if '--keys' in args:
        i = args.index('--keys'); keydir = args[i + 1]; del args[i:i + 2]
    if not args:
        print(__doc__); return 2
    keys = held_keys(keydir); bad = 0
    for p in args:
        print(p)
        try:
            check_image(p, keys, os.path.join(lv.BACKUP, 'lk.img'), os.path.join(lv.BACKUP, 'mmcblk0boot0.img'), print)
            print('  PASS')
        except lv.Fail as f:
            print('  FAIL [%s] %s' % (f.check, f.why)); bad = 1
        except OSError as x:
            print('  FAIL [files] %s' % x); bad = 1
    return bad


if __name__ == '__main__':
    sys.exit(main(sys.argv))
