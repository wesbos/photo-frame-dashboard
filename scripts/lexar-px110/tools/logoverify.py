#!/usr/bin/env python3
"""Independent checker for a signed MediaTek 'logo' partition image. Offline only; reads files, writes none.

    python3 -I tools/logoverify.py <logo image> [--lk lk.img] [--preloader mmcblk0boot0.img] [--quiet]

Shares no code with logosign.py (it imports nothing from this project). The RSA-PSS check is done twice:
in plain Python (integer maths + hashlib), and again by the `openssl` command; both must agree.

Checks, in this order; prints PASS, or FAIL with the first check that fails (exit status 0 / 1):
  size            file is exactly 8,388,608 bytes
  layout          logo header, payload table, cert1 and cert2 headers where the 16-byte alignment puts them
  padding         the alignment gaps and everything after cert2 are zeros
  shape           both certificates are well-formed and carry the expected fields
  root key        cert1's own public key is the key built into the backed-up lk.img and preloader
  cert1 signature cert1 is signed by that root key (RSA-PSS, SHA-256, MGF1-SHA-256, salt 32)
  key match       cert2's public key is the image key that cert1 carries
  cert2 signature cert2 is signed by that image key
  data hash       cert2's data hash = SHA-256 of the payload zero-padded to 16 bytes
  header hash     cert2's header hash = SHA-256 of the image's first 512 bytes
  pictures        every picture in the payload decompresses
"""
import hashlib, os, struct, subprocess, sys, tempfile, zlib

SIZE = 8388608


def _backup_dir():
    """BACKUP_DIR: environment PX110_BACKUP_DIR, else unit.conf. Read here, in a few lines of its own, so that
    this checker still imports nothing from the project."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    value = os.environ.get('PX110_BACKUP_DIR', '')
    conf = os.environ.get('PX110_CONF') or os.path.join(base, 'unit.conf')
    if not value and os.path.isfile(conf):
        for line in open(conf):
            key, eq, v = line.strip().partition('=')
            if eq and key.strip() == 'BACKUP_DIR':
                value = v.strip().strip('"\'')
    if not value:
        return 'BACKUP_DIR-not-set'
    value = os.path.expanduser(value)
    return value if os.path.isabs(value) else os.path.normpath(os.path.join(base, value))


BACKUP = _backup_dir()
MTK = bytes.fromhex('6086769316')                    # OID 2.16.886.2454
RSA_ENCRYPTION = bytes.fromhex('2a864886f70d010101')
RSASSA_PSS = bytes.fromhex('2a864886f70d01010a')


class Fail(Exception):
    def __init__(self, check, why):
        Exception.__init__(self, '%s: %s' % (check, why)); self.check = check; self.why = why


def need(cond, check, why):
    if not cond:
        raise Fail(check, why)


# ---- DER
def tlv(b, o):
    t = b[o]; n = b[o + 1]
    if n < 128:
        return t, o + 2, o + 2 + n
    k = n & 127
    return t, o + 2 + k, o + 2 + k + int.from_bytes(b[o + 2:o + 2 + k], 'big')


def kids(b, o):
    t, s, e = tlv(b, o); out = []
    while s < e:
        _, _, n = tlv(b, s); out.append((s, n)); s = n
    if s != e:
        raise ValueError('bad DER nesting')
    return out


def rsa_public(spki):
    """SubjectPublicKeyInfo bytes -> (n, e)."""
    alg, bits = kids(spki, 0)
    oid = kids(spki, alg[0])[0]
    _, s, e = tlv(spki, oid[0])
    if spki[s:e] != RSA_ENCRYPTION:
        raise ValueError('not an RSA key')
    t, s, e = tlv(spki, bits[0])
    if t != 3 or spki[s] != 0:
        raise ValueError('bad key BIT STRING')
    n_, e_ = kids(spki, s + 1)
    val = lambda span: int.from_bytes(spki[tlv(spki, span[0])[1]:span[1]], 'big')
    return val(n_), val(e_)


def split_cert(der, check):
    """-> dict(tbs bytes, fields [(start,end)], alg bytes, sig bytes, spki bytes)."""
    try:
        t, s, e = tlv(der, 0)
        need(t == 0x30 and e == len(der), check, 'not a single DER SEQUENCE filling the certificate')
        top = kids(der, 0)
        need(len(top) == 3, check, 'expected TBS, algorithm, signature')
        f = kids(der, top[0][0])
        t, s, e = tlv(der, top[2][0])
        need(t == 3 and der[s] == 0 and e - s - 1 == 256, check, 'signature is not 256 bytes')
        need(RSASSA_PSS in der[top[1][0]:top[1][1]], check, 'signature algorithm is not RSASSA-PSS')
        need(len(f) > 7 and der[f[6][0]] == 0x30, check, 'no public key in the usual place')
        return dict(der=der, tbs=der[top[0][0]:top[0][1]], fields=f, sig=der[s + 1:e], spki=der[f[6][0]:f[6][1]])
    except (IndexError, ValueError) as x:
        raise Fail(check, 'malformed DER (%s)' % x)


def value_after(c, oid_tail, check):
    want = b'\x06\x07' + MTK + oid_tail
    f = c['fields']; der = c['der']
    hits = [i for i, (a, b) in enumerate(f) if der[a:b] == want]
    need(len(hits) == 1 and hits[0] + 1 < len(f), check, 'field 2.16.886.2454.%d.%d missing' % tuple(oid_tail))
    a, b = f[hits[0] + 1]
    return der[a:b]


def hash_value(c, oid_tail, check):
    v = value_after(c, oid_tail, check)
    need(len(v) == 35 and v[:3] == b'\x03\x21\x00', check, 'hash field is not a 32-byte BIT STRING')
    return v[3:]


# ---- RSA-PSS (RFC 8017, 9.1.2), SHA-256, MGF1-SHA-256, salt 32
def mgf1(seed, n):
    out = b''; i = 0
    while len(out) < n:
        out += hashlib.sha256(seed + struct.pack('>I', i)).digest(); i += 1
    return out[:n]


def pss_ok_python(n, e, message, sig):
    k = (n.bit_length() + 7) // 8
    s = int.from_bytes(sig, 'big')
    if len(sig) != k or s >= n:
        return False
    embits = n.bit_length() - 1
    emlen = (embits + 7) // 8
    em = pow(s, e, n).to_bytes(k, 'big')[k - emlen:]
    if em[-1] != 0xBC:
        return False
    h = em[-33:-1]; masked = em[:-33]
    topbits = 8 * emlen - embits
    if masked[0] >> (8 - topbits):
        return False
    db = bytearray(x ^ y for x, y in zip(masked, mgf1(h, len(masked))))
    db[0] &= 0xFF >> topbits
    pad = len(db) - 32 - 1
    if any(db[:pad]) or db[pad] != 1:
        return False
    salt = bytes(db[pad + 1:])
    return hashlib.sha256(b'\0' * 8 + hashlib.sha256(message).digest() + salt).digest() == h


def pss_ok_openssl(spki, message, sig):
    with tempfile.TemporaryDirectory() as t:
        p = lambda name, data: (open(os.path.join(t, name), 'wb').write(data), os.path.join(t, name))[1]
        r = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', p('k.der', spki), '-keyform', 'DER',
                            '-sigopt', 'rsa_padding_mode:pss', '-sigopt', 'rsa_pss_saltlen:32',
                            '-signature', p('s.bin', sig), p('m.bin', message)], capture_output=True)
    return r.returncode == 0 and b'Verified OK' in r.stdout


def check_signature(check, spki, message, sig):
    n, e = rsa_public(spki)
    need(n.bit_length() == 2048 and e == 65537, check, 'key is not RSA-2048 with exponent 65537')
    py = pss_ok_python(n, e, message, sig); ossl = pss_ok_openssl(spki, message, sig)
    need(py == ossl, check, 'the Python check (%s) and openssl (%s) disagree' % (py, ossl))
    need(py, check, 'signature does not verify')


# ---- the image
def verify(path, lk_path, pl_path, say):
    d = open(path, 'rb').read()
    need(len(d) == SIZE, 'size', '%d bytes, expected %d' % (len(d), SIZE))
    say('size            %d bytes' % len(d))

    L = 'layout'
    magic, psize = struct.unpack_from('<II', d, 0)
    need(magic == 0x58881688 and d[8:40].rstrip(b'\0') == b'logo', L, 'logo header magic/name')
    need(struct.unpack_from('<II', d, 0x30) == (0x58891689, 0x200), L, 'logo extended header')
    need(0x200 + psize <= SIZE - 0x400, L, 'payload size field too large')
    pay = d[0x200:0x200 + psize]
    count, total = struct.unpack_from('<II', pay, 0)
    need(total == psize and 0 < count < 1000 and 8 + 4 * count <= psize, L, 'payload table header')
    offs = list(struct.unpack_from('<%dI' % count, pay, 8)) + [total]
    need(offs[0] == 8 + 4 * count and all(a < b for a, b in zip(offs, offs[1:])), L, 'picture offsets not ascending')
    up16 = lambda x: (x + 15) & ~15
    certs = []; pos = up16(0x200 + psize); gaps = [(0x200 + psize, pos)]
    for name in (b'cert1', b'cert2'):
        need(pos + 0x200 <= SIZE, L, '%s header beyond the image' % name.decode())
        magic, clen = struct.unpack_from('<II', d, pos)
        need(magic == 0x58881688 and d[pos + 8:pos + 40].rstrip(b'\0') == name, L,
             '%s header not at 0x%X' % (name.decode(), pos))
        need(struct.unpack_from('<II', d, pos + 0x30) == (0x58891689, 0x200), L, '%s extended header' % name.decode())
        need(pos + 0x200 + clen <= SIZE, L, '%s runs past the image' % name.decode())
        certs.append((pos, d[pos + 0x200:pos + 0x200 + clen]))
        end = pos + 0x200 + clen; pos = up16(end); gaps.append((end, pos))
    end_cert2 = gaps.pop()[0]
    say('layout          payload %d bytes, %d pictures; cert1 at 0x%X (%d bytes), cert2 at 0x%X (%d bytes)'
        % (psize, count, certs[0][0], len(certs[0][1]), certs[1][0], len(certs[1][1])))

    need(not any(any(d[a:b]) for a, b in gaps), 'padding', 'alignment gap is not zeros')
    need(not any(d[end_cert2:]), 'padding', 'non-zero bytes after cert2 (from 0x%X)' % end_cert2)
    say('padding         zeros from 0x%X to the end' % end_cert2)

    c1 = split_cert(certs[0][1], 'shape'); c2 = split_cert(certs[1][1], 'shape')
    image_key = value_after(c1, b'\x01\x02', 'shape')
    stored_data = hash_value(c2, b'\x02\x01', 'shape'); stored_hdr = hash_value(c2, b'\x02\x04', 'shape')
    try:
        root_n, root_e = rsa_public(c1['spki']); rsa_public(image_key); rsa_public(c2['spki'])
    except (IndexError, ValueError) as x:
        raise Fail('shape', 'a public key does not parse (%s)' % x)
    say('shape           cert1 and cert2 parse; image key, data hash and header hash fields present')

    raw_n = root_n.to_bytes(256, 'big')
    for label, p in (('lk.img', lk_path), ('preloader', pl_path)):
        at = open(p, 'rb').read().find(raw_n)
        need(at >= 0, 'root key', "cert1's own key is not inside the backed-up %s" % label)
        say('root key        modulus %s... found in %s at byte %d' % (raw_n[:6].hex(), label, at))

    check_signature('cert1 signature', c1['spki'], c1['tbs'], c1['sig'])
    say('cert1 signature verifies with the root key (Python and openssl)')

    need(c2['spki'] == image_key, 'key match', "cert2's key is not the image key in cert1")
    say('key match       cert2 key = cert1 image key (modulus %s...)' % ('%x' % rsa_public(image_key)[0])[:12])

    check_signature('cert2 signature', image_key, c2['tbs'], c2['sig'])
    say('cert2 signature verifies with the image key (Python and openssl)')

    got = hashlib.sha256(pay + b'\0' * (-len(pay) % 16)).digest()
    need(got == stored_data, 'data hash', 'payload hashes to %s, cert2 says %s' % (got.hex(), stored_data.hex()))
    say('data hash       %s' % got.hex())
    got = hashlib.sha256(d[:0x200]).digest()
    need(got == stored_hdr, 'header hash', 'header hashes to %s, cert2 says %s' % (got.hex(), stored_hdr.hex()))
    say('header hash     %s' % got.hex())

    for i in range(count):
        try:
            zlib.decompress(pay[offs[i]:offs[i + 1]])
        except zlib.error as x:
            raise Fail('pictures', 'picture %d does not decompress (%s)' % (i, x))
    say('pictures        all %d decompress' % count)


def main(argv):
    args = argv[1:]; opt = {'--lk': os.path.join(BACKUP, 'lk.img'), '--preloader': os.path.join(BACKUP, 'mmcblk0boot0.img')}
    quiet = '--quiet' in args
    if quiet:
        args.remove('--quiet')
    for k in list(opt):
        if k in args:
            i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
    if len(args) != 1:
        print(__doc__); return 2
    try:
        verify(args[0], opt['--lk'], opt['--preloader'], (lambda s: None) if quiet else print)
    except Fail as f:
        print('FAIL [%s] %s' % (f.check, f.why)); return 1
    except OSError as x:
        print('FAIL [files] %s' % x); return 1
    print('PASS  %s' % args[0]); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
