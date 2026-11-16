#!/usr/bin/env python3
"""Offline tests for logocodec.py against the stock logo backup. Run: python3 -I tools/test_logocodec.py"""
import hashlib, os, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logocodec as L
import px110conf
_why = px110conf.missing(backup_files=('logo.img',))
if _why:
    print('SKIP test_logocodec.py: ' + _why); sys.exit(0)
STOCK = px110conf.backup('logo.img')
d = open(STOCK, 'rb').read()
ok = True
def check(name, cond):
    global ok; ok &= bool(cond); print(('PASS ' if cond else 'FAIL ') + name)

raws, p = L.decode(d)
check('42 pictures', len(raws) == 42)
check('every stock zlib stream is reproduced by zlib level 9', all(zlib.compress(r, 9) == b for r, b in zip(raws, p['blobs'])))
e = L.encode(raws, d)
check('decode -> encode is byte-identical to the 8 MiB partition image', e == d)
check('payload header size field equals real payload length', p['psize'] == len(L.build_payload(raws)))
check('pictures 0 and 38 (boot logo, kernel logo) are identical', raws[0] == raws[38])
# certificate: cert2 carries sha256(payload padded to 16 bytes)
pay = d[0x200:0x200 + p['psize']]; padded = pay + b'\0' * (-len(pay) % 16)
check('cert2 contains sha256 of the 16-byte-padded payload', hashlib.sha256(padded).digest() in d)
# edit one picture: result decodes back, differs only in that picture, partition size unchanged
r2 = list(raws); b = bytearray(r2[0]); b[0:4] = b'\x00\x00\xff\xff'; r2[0] = bytes(b)
e2 = L.encode(r2, d)
rr, pp = L.decode(e2)
check('edited image decodes; only picture 0 changed', rr[0] == r2[0] and all(rr[i] == raws[i] for i in range(1, 42)))
check('edited image keeps the 8 MiB size', len(e2) == len(d))
check('edited payload no longer matches cert2 hash (needs signing key: expected)', hashlib.sha256((lambda x: x + b'\0' * (-len(x) % 16))(e2[0x200:0x200 + pp['psize']])).digest() not in e2[pp['psize'] + 0x200:])
print('ALL PASS' if ok else 'FAILED'); sys.exit(0 if ok else 1)
