#!/usr/bin/env python3
"""Offline tests for logosign.py / logoverify.py (tests 1-10).

    python3 -I tools/test_logosign.py            run the tests against the files in BUILD_DIR/out-logo/
    python3 -I tools/test_logosign.py --build    (re)make BUILD_DIR/out-logo/ first, then run the tests

Needs your own backup (BACKUP_DIR) and the fetched keys (KEY_DIR); without them it prints SKIP and exits 0.
Never touches the frame. Scratch files go to a temporary folder that is removed afterwards.
Signatures are randomised (RSA-PSS salt), so --build gives new image hashes every time; SHA256SUMS is
rewritten to match.
"""
import hashlib, os, struct, subprocess, sys, tempfile, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logocodec, logosign, px110conf  # noqa: E402

BACKUP = px110conf.path('BACKUP_DIR')
STOCK = os.path.join(BACKUP, 'logo.img')
OUT = px110conf.build_dir('out-logo')
WHY_SKIP = px110conf.missing(backup_files=('logo.img', 'lk.img', 'mmcblk0boot0.img'), key_files=('root_prvk.pem', 'img_prvk.pem'))
if WHY_SKIP and __name__ == '__main__':
    print('SKIP test_logosign.py: ' + WHY_SKIP); sys.exit(0)
RESIGNED = os.path.join(OUT, 'logo-stock-resigned.img')
TESTIMG = os.path.join(OUT, 'logo-test.img')
TESTPNG = os.path.join(OUT, 'logo-test.png')
SIGN = [sys.executable, '-I', os.path.join(HERE, 'logosign.py')]
VERIFY = [sys.executable, '-I', os.path.join(HERE, 'logoverify.py')]
W, H = 2000, 1200

# Stock offsets from the plan (what was proven by hand before this tool existed)
C1, C2 = 0x1A0D00 + 0x200, 0x1A15B0 + 0x200          # start of each certificate's DER in the image
C1_LEN, C2_LEN = 1709, 957
C1_IMGKEY = (C1 + 496, C1 + 790)
C1_SIG = (C1 + C1_LEN - 256, C1 + C1_LEN)
C2_KEY = (C2 + 181, C2 + 475)
C2_TBS = (C2 + 4, C2 + 4 + 4 + 616)
C2_DATA_HASH = (C2 + 496 + 3, C2 + 496 + 35)
C2_HDR_HASH = (C2 + 552 + 3, C2 + 552 + 35)
C2_SIG = (C2 + C2_LEN - 256, C2 + C2_LEN)

results = []


def check(name, cond, detail=''):
    results.append(bool(cond))
    for folder in (BACKUP, OUT, px110conf.BASE):      # keep the log free of this computer's folder names
        detail = detail.replace(folder + os.sep, '')
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name, (' -- ' + detail) if detail else ''))


def verifier(path):
    """-> (exit status, last line of output)"""
    p = subprocess.run(VERIFY + [path, '--quiet'], capture_output=True, text=True)
    return p.returncode, (p.stdout.strip().splitlines() or [''])[-1]


def test_picture_rgba():
    """A plain 2000x1200 test card: colour bars, a grey ramp, a white border, a red corner block. No text."""
    bars = [(255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0), (255, 0, 255), (255, 0, 0), (0, 0, 255), (0, 0, 0)]
    top = b''.join(bytes(bars[x * 8 // W]) + b'\xff' for x in range(W))
    ramp = b''.join(bytes([x * 256 // W] * 3) + b'\xff' for x in range(W))
    white = b'\xff' * (4 * W)
    rows = []
    for y in range(H):
        if y < 4 or y >= H - 4:
            row = white
        else:
            row = bytearray(top if y < 800 else ramp)
            row[:16] = white[:16]; row[-16:] = white[:16]
            if y < 200:                                   # red block top-left: shows orientation and R/B order
                row[16:16 + 4 * 200] = b'\xff\x00\x00\xff' * 200
            row = bytes(row)
        rows.append(row)
    return b''.join(rows)


def rgba_to_bgra(rgba):
    b = bytearray(rgba); b[0::4] = rgba[2::4]; b[2::4] = rgba[0::4]
    return bytes(b)


def build():
    os.makedirs(OUT, exist_ok=True)
    logocodec.png(TESTPNG, W, H, test_picture_rgba())
    subprocess.run(SIGN + ['resign', STOCK, RESIGNED], check=True)
    subprocess.run(SIGN + ['make', STOCK, TESTPNG, TESTIMG], check=True)
    with open(os.path.join(OUT, 'SHA256SUMS'), 'w') as f:
        for name in ('logo-stock-resigned.img', 'logo-test.img', 'logo-test.png'):
            f.write('%s  %s\n' % (hashlib.sha256(open(os.path.join(OUT, name), 'rb').read()).hexdigest(), name))


def diff_ranges(a, b):
    """Byte ranges [(start, end)] where a and b differ (same length)."""
    out = []; i = 0; n = len(a); step = 4096
    while i < n:
        if a[i:i + step] == b[i:i + step]:
            i += step; continue
        for j in range(i, min(i + step, n)):
            if a[j] != b[j]:
                if out and out[-1][1] == j:
                    out[-1][1] = j + 1
                else:
                    out.append([j, j + 1])
        i += step
    return [tuple(x) for x in out]


def inside(ranges, allowed):
    return all(any(a <= s and e <= b for a, b in allowed) for s, e in ranges)


def asn1_outline(der, tmp):
    p = os.path.join(tmp, 'c.der'); open(p, 'wb').write(der)
    return subprocess.run(['openssl', 'asn1parse', '-inform', 'DER', '-in', p], capture_output=True, text=True).stdout.splitlines()


def modulus_hex(spki_or_pem, tmp=None, private=False):
    if private:
        args = ['openssl', 'rsa', '-in', spki_or_pem, '-noout', '-modulus']
    else:
        p = os.path.join(tmp, 'k.der'); open(p, 'wb').write(spki_or_pem)
        args = ['openssl', 'rsa', '-pubin', '-inform', 'DER', '-in', p, '-noout', '-modulus']
    return subprocess.run(args, capture_output=True, text=True).stdout.strip().split('=')[-1]


def main():
    if '--build' in sys.argv:
        build()
    stock = open(STOCK, 'rb').read()
    for p in (RESIGNED, TESTIMG, TESTPNG):
        if not os.path.exists(p):
            print('FAIL missing %s (run with --build)' % p); return 1
    resigned = open(RESIGNED, 'rb').read(); test = open(TESTIMG, 'rb').read()

    with tempfile.TemporaryDirectory() as tmp:
        def variant(name, edit):
            d = bytearray(stock); edit(d)
            p = os.path.join(tmp, name); open(p, 'wb').write(d); return p

        def flip(off):
            def f(d): d[off] ^= 0x01
            return f

        # 0. the plan's offsets are what the signer's parser finds in the stock image
        img = logosign.parse_image(stock)
        c1 = logosign.Cert(img['cert1']); c2 = logosign.Cert(img['cert2'])
        check('0. signer parses the stock image to the offsets in the plan',
              (img['cert1_off'] + 0x200, img['cert2_off'] + 0x200, len(c1.der), len(c2.der)) == (C1, C2, C1_LEN, C2_LEN)
              and c1.after_oid(logosign.OID_IMG_KEY) == (496, 790) and c2.spki == (181, 475)
              and c1.sig == (C1_LEN - 256, C1_LEN) and c2.sig == (C2_LEN - 256, C2_LEN)
              and c2.tbs == (4, 624) and c1.tbs == (4, 1376))

        # 1
        rc, line = verifier(STOCK)
        check('1. checker on the stock logo.img: PASS', rc == 0 and line.startswith('PASS'), line)
        # 2
        rc, line = verifier(variant('flip-payload.img', flip(0x200 + 800000)))
        check('2. one payload byte flipped: FAIL at the data hash', rc == 1 and line.startswith('FAIL [data hash]'), line)
        # 3
        rc, line = verifier(variant('flip-header.img', flip(0x100)))
        check('3. one header byte flipped: FAIL at the header hash', rc == 1 and line.startswith('FAIL [header hash]'), line)
        # 4
        rc, line = verifier(variant('flip-sig1.img', flip(C1_SIG[0] + 100)))
        check('4a. one cert1 signature byte flipped: FAIL at the cert1 signature', rc == 1 and line.startswith('FAIL [cert1 signature]'), line)
        rc, line = verifier(variant('flip-sig2.img', flip(C2_SIG[0] + 100)))
        check('4b. one cert2 signature byte flipped: FAIL at the cert2 signature', rc == 1 and line.startswith('FAIL [cert2 signature]'), line)
        # 5: cert2 carrying, and correctly signed by, a throwaway key that cert1 does not vouch for
        throw = os.path.join(tmp, 'throwaway.pem')
        subprocess.run(['openssl', 'genrsa', '-out', throw, '2048'], capture_output=True, check=True)
        spki = logosign.public_spki(throw)

        def forge(d):
            d[C2_KEY[0]:C2_KEY[1]] = spki
            d[C2_SIG[0]:C2_SIG[1]] = logosign.pss_sign(throw, bytes(d[C2_TBS[0]:C2_TBS[1]]))
        rc, line = verifier(variant('throwaway-cert2.img', forge))
        check('5. cert2 re-signed by a throwaway key not in cert1: FAIL (key mismatch)', len(spki) == 294 and rc == 1 and line.startswith('FAIL [key match]'), line)

        # 6
        rc, line = verifier(RESIGNED)
        check('6a. logo-stock-resigned.img: checker PASS', rc == 0, line)
        ranges = diff_ranges(stock, resigned)
        allowed = [C1_IMGKEY, C1_SIG, C2_KEY, C2_SIG]
        print('     changed byte ranges: ' + ', '.join('0x%X-0x%X (%d)' % (s, e - 1, e - s) for s, e in ranges))
        check('6b. differs from stock only inside the two image-key fields and the two signatures',
              ranges and inside(ranges, allowed) and all(any(a <= s < b for s, e in ranges) for a, b in allowed))
        check('6c. size, header, payload, both hashes and both certificate headers identical to stock',
              len(resigned) == len(stock) and resigned[:C1 - 0x200] == stock[:C1 - 0x200]
              and resigned[C2_DATA_HASH[0]:C2_DATA_HASH[1]] == stock[C2_DATA_HASH[0]:C2_DATA_HASH[1]]
              and resigned[C2_HDR_HASH[0]:C2_HDR_HASH[1]] == stock[C2_HDR_HASH[0]:C2_HDR_HASH[1]]
              and resigned[C1 - 0x200:C1] == stock[C1 - 0x200:C1] and resigned[C2 - 0x200:C2] == stock[C2 - 0x200:C2])
        img_mod = modulus_hex(logosign.IMG_KEY, private=True)
        check('6d. the image key now in cert1 and cert2 is the published one',
              modulus_hex(resigned[C1_IMGKEY[0]:C1_IMGKEY[1]], tmp) == img_mod == modulus_hex(resigned[C2_KEY[0]:C2_KEY[1]], tmp))

        # 7
        rc, line = verifier(TESTIMG)
        check('7a. logo-test.img: checker PASS', rc == 0, line)
        want = rgba_to_bgra(test_picture_rgba())
        check('7b. logo-test.png is the generated test card', open(TESTPNG, 'rb').read() == png_bytes(test_picture_rgba()))
        raws0, p0 = logocodec.decode(stock); raws, p = logocodec.decode(test)
        check('7c. pictures 0 and 38 decode to exactly the input picture (B,G,R,A, alpha 255)', raws[0] == want and raws[38] == want)
        check('7d. 42 pictures; the other 40 streams byte-identical to stock',
              p['n'] == 42 and all(p['blobs'][i] == p0['blobs'][i] for i in range(42) if i not in (0, 38))
              and p['blobs'][0] != p0['blobs'][0])
        end = 0x200 + p['psize']; end = (end + 15) & ~15; end += 0x200 + C1_LEN; end = (end + 15) & ~15; end += 0x200 + C2_LEN
        check('7e. 8 MiB; tail all zeros', len(test) == 8388608 and not any(test[end:]) and any(test[end - 256:end]))
        small = os.path.join(tmp, 'small.png'); logocodec.png(small, 1200, 2000, b'\x10\x20\x30\xff' * (1200 * 2000))
        r = subprocess.run(SIGN + ['make', STOCK, small, os.path.join(tmp, 'no.img')], capture_output=True, text=True)
        check('7f. a picture of another size (1200x2000) is refused and no file is written',
              r.returncode != 0 and not os.path.exists(os.path.join(tmp, 'no.img')), r.stderr.strip())

        # 8
        s1 = asn1_outline(stock[C1:C1 + C1_LEN], tmp); s2 = asn1_outline(stock[C2:C2 + C2_LEN], tmp)
        for label, d in (('logo-stock-resigned.img', resigned), ('logo-test.img', test)):
            i1 = logosign.parse_image(d)
            check('8. %s: asn1parse outline of cert1 (%d lines) and cert2 (%d lines) equals stock line for line'
                  % (label, len(s1), len(s2)),
                  len(s1) > 60 and len(s2) > 60 and asn1_outline(i1['cert1'], tmp) == s1 and asn1_outline(i1['cert2'], tmp) == s2)

        # 9
        ok = True
        for path, want_hash in ((logosign.ROOT_KEY, logosign.ROOT_MODULUS_SHA256), (logosign.IMG_KEY, logosign.IMG_MODULUS_SHA256)):
            out = subprocess.run(['openssl', 'rsa', '-in', path, '-noout', '-modulus'], capture_output=True).stdout
            ok &= hashlib.sha256(out).hexdigest() == want_hash
        check('9a. fetched root and image keys match the pinned modulus hashes', ok)
        root_n = bytes.fromhex(modulus_hex(logosign.ROOT_KEY, private=True))
        lk = open(os.path.join(BACKUP, 'lk.img'), 'rb').read(); pl = open(os.path.join(BACKUP, 'mmcblk0boot0.img'), 'rb').read()
        check('9b. root key equals the one inside lk.img (payload offset 379792) and the preloader (offset 2560)',
              lk[512 + 379792:512 + 379792 + 256] == root_n and pl[2560:2560 + 256] == root_n)

        # 10
        r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'test_logocodec.py')], capture_output=True, text=True)
        n = sum(1 for l in r.stdout.splitlines() if l.startswith('PASS '))
        check('10. test_logocodec.py still 9/9', r.returncode == 0 and n == 9, '%d PASS lines' % n)

    bad = results.count(False)
    print('ALL PASS (%d checks)' % len(results) if not bad else 'FAILED: %d of %d checks' % (bad, len(results)))
    return 1 if bad else 0


def png_bytes(rgba):
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, 'x.png'); logocodec.png(p, W, H, rgba)
        return open(p, 'rb').read()


if __name__ == '__main__':
    sys.exit(main())
