#!/usr/bin/env python3
"""Offline tests for logo-from-splash.py.

    python3 -I tools/test_logo_from_splash.py

Needs your own backup (BACKUP_DIR), the fetched keys (KEY_DIR) and BUILD_DIR/out-logo (test_logosign.py --build);
without the first two it prints SKIP and exits 0. Never touches the frame. Scratch files go to a temporary folder that is removed afterwards. Each built image
is checked by logoverify.py run as its own program (the signer and the checker share no code).
"""
import hashlib, importlib.util, io, os, random, struct, subprocess, sys, tempfile, zipfile, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import px110conf  # noqa: E402
WHY_SKIP = px110conf.missing(backup_files=('logo.img', 'lk.img', 'mmcblk0boot0.img'), key_files=('root_prvk.pem', 'img_prvk.pem'))
if WHY_SKIP:
    print('SKIP test_logo_from_splash.py: ' + WHY_SKIP); sys.exit(0)
spec = importlib.util.spec_from_file_location('logo_from_splash', os.path.join(HERE, 'logo-from-splash.py'))
lfs = importlib.util.module_from_spec(spec); spec.loader.exec_module(lfs)
import logocodec  # noqa: E402  (on the path once logosign has been imported by the tool)

STOCK = px110conf.backup('logo.img')
OTHER = px110conf.build_dir('out-logo', 'logo-stock-resigned.img')   # a valid image that is not the factory one
TOOL = [sys.executable, '-I', os.path.join(HERE, 'logo-from-splash.py')]
VERIFY = [sys.executable, '-I', os.path.join(HERE, 'logoverify.py')]
W, H = 2000, 1200

results = []


def check(name, cond, detail=''):
    results.append(bool(cond))
    detail = str(detail)
    for folder in (px110conf.path('BACKUP_DIR'), px110conf.build_dir(), px110conf.BASE):
        detail = detail.replace(folder + os.sep, '')
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name, (' -- ' + detail) if detail else ''))


def refused(name, fn, wanted):
    """fn must raise SplashError whose text contains `wanted`."""
    try:
        fn()
    except lfs.SplashError as e:
        check(name, wanted in str(e), str(e))
    else:
        check(name, False, 'was accepted')


def verifier(path, *more):
    p = subprocess.run(VERIFY + [path, '--quiet'] + list(more), capture_output=True, text=True)
    return p.returncode, (p.stdout.strip().splitlines() or [''])[-1]


# ---- a small PNG writer of our own, so the reader is tested against something it did not write
def chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xFFFFFFFF)


def paeth(a, b, c):
    p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def png(w, h, px, bpp, filters=(0,), depth=8, lace=0, colour=None, split=1):
    """px: w*h*bpp bytes, top row first. filters: the filter type of each row, cycled."""
    stride = w * bpp
    flat = bytearray()
    prev = bytes(stride)
    for y in range(h):
        row = px[y * stride:(y + 1) * stride]
        ft = filters[y % len(filters)]
        left = lambda i: row[i - bpp] if i >= bpp else 0
        upleft = lambda i: prev[i - bpp] if i >= bpp else 0
        if ft == 0:
            enc = row
        elif ft == 1:
            enc = bytes((row[i] - left(i)) & 255 for i in range(stride))
        elif ft == 2:
            enc = bytes((row[i] - prev[i]) & 255 for i in range(stride))
        elif ft == 3:
            enc = bytes((row[i] - ((left(i) + prev[i]) >> 1)) & 255 for i in range(stride))
        else:
            enc = bytes((row[i] - paeth(left(i), prev[i], upleft(i))) & 255 for i in range(stride))
        flat += bytes([ft]) + enc
        prev = row
    z = zlib.compress(bytes(flat), 6)
    cut = max(1, len(z) // split)
    idat = b''.join(chunk(b'IDAT', z[i:i + cut]) for i in range(0, len(z), cut))
    ihdr = struct.pack('>IIBBBBB', w, h, depth, colour if colour is not None else (2 if bpp == 3 else 6), 0, 0, lace)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'tEXt', b'note\0hello') + idat + chunk(b'IEND', b'')


def to_bgra(px, bpp):
    n = len(px) // bpp
    out = bytearray(b'\xff' * (n * 4))
    out[0::4] = px[2::bpp]; out[1::4] = px[1::bpp]; out[2::4] = px[0::bpp]
    return bytes(out)


def card_rgb():
    """A 2000x1200 test picture, R,G,B: a red block top-left, a blue one bottom-right, colour stripes and a ramp."""
    rows = []
    for y in range(H):
        row = bytearray()
        for x in range(0, W, 8):
            row += bytes(((x * 255 // W), (y * 255 // H), (x + y) & 255)) * 8
        if y < 100:
            row[:300] = b'\xff\x00\x00' * 100
        if y >= H - 100:
            row[-300:] = b'\x00\x00\xff' * 100
        rows.append(bytes(row))
    return b''.join(rows)


def animation(frames, desc='%d %d 10\np 0 0 part0\n' % (W, H), method=zipfile.ZIP_STORED):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', method) as z:
        z.writestr('desc.txt', desc)
        for name, data in frames:
            z.writestr(name, data)
    return b.getvalue()


def main():
    stock = open(STOCK, 'rb').read()
    sp = logocodec.parse(stock)
    rnd = random.Random(7)
    with tempfile.TemporaryDirectory() as t:
        def put(name, data):
            p = os.path.join(t, name)
            open(p, 'wb').write(data)
            return p

        # ------------------------------------------------------------ 1. the PNG reader
        w, h = 13, 9
        rgb = bytes(rnd.randrange(256) for _ in range(w * h * 3))
        rgba = bytes(255 if i % 4 == 3 else rnd.randrange(256) for i in range(w * h * 4))
        for ft in range(5):
            check('1.%d reader: RGB, row filter %d' % (ft, ft), lfs.png_to_bgra(png(w, h, rgb, 3, (ft,))) == (w, h, to_bgra(rgb, 3)))
        check('1.5 reader: RGBA, every filter in one picture, data in 4 chunks',
              lfs.png_to_bgra(png(w, h, rgba, 4, (4, 3, 2, 1, 0), split=4)) == (w, h, to_bgra(rgba, 4)))
        check('1.6 reader: a red pixel comes out as bytes 00 00 FF FF (B,G,R,A)',
              lfs.png_to_bgra(png(1, 1, b'\xff\x00\x00', 3))[2] == b'\x00\x00\xff\xff')
        good = png(w, h, rgb, 3)
        refused('1.7 reader: transparent pixels refused',
                lambda: lfs.png_to_bgra(png(w, h, rgba[:-1] + b'\x80', 4)), 'transparent')
        refused('1.8 reader: interlaced refused', lambda: lfs.png_to_bgra(png(w, h, rgb, 3, lace=1)), 'interlaced')
        refused('1.9 reader: 16-bit refused', lambda: lfs.png_to_bgra(png(w, h, rgb, 3, depth=16)), '8 bits')
        refused('1.10 reader: palette picture refused', lambda: lfs.png_to_bgra(png(w, h, rgb, 3, colour=3)), 'RGB or RGBA')
        bad = bytearray(good); bad[len(bad) - 20] ^= 1
        refused('1.11 reader: a flipped bit in the data is caught by the checksum', lambda: lfs.png_to_bgra(bytes(bad)), 'checksum')
        refused('1.12 reader: a file cut short refused', lambda: lfs.png_to_bgra(good[:-30]), '')
        refused('1.13 reader: an unknown row filter refused', lambda: lfs.png_to_bgra(png(w, h, rgb, 3, (7,))), 'filter')
        refused('1.14 reader: not a PNG refused', lambda: lfs.png_to_bgra(b'GIF89a' + bytes(40)), 'not a PNG')

        # ------------------------------------------------------------ 2. what counts as a picture
        card = card_rgb()
        want = to_bgra(card, 3)
        card_png = put('card.png', png(W, H, card, 3, (1, 2, 4, 0, 3)))
        raw, kind = lfs.picture_bgra(card_png)
        check('2.1 a 2000x1200 PNG is read exactly, as B,G,R,A', raw == want and kind == 'PNG')
        check('2.2 top-left pixel is the red block, bottom-right the blue one',
              raw[:4] == b'\x00\x00\xff\xff' and raw[-4:] == b'\xff\x00\x00\xff')
        refused('2.3 a 1280x800 PNG refused', lambda: lfs.picture_bgra(put('small.png', png(1280, 800, bytes(1280 * 800 * 3), 3))), 'exactly 2000x1200')
        refused('2.4 a 1200x2000 (turned) PNG refused', lambda: lfs.picture_bgra(put('turned.png', png(H, W, bytes(W * H * 3), 3))), 'exactly 2000x1200')
        raw2, kind2 = lfs.picture_bgra(put('card.bgra', want))
        check('2.5 raw B,G,R,A of the right length is taken as it is', raw2 == want and kind2 == 'raw B,G,R,A')
        holed = bytearray(want); holed[3] = 0
        refused('2.6 raw bytes with an alpha that is not 255 refused', lambda: lfs.picture_bgra(put('holed.bgra', bytes(holed))), 'alpha')
        refused('2.7 raw bytes of the wrong length refused', lambda: lfs.picture_bgra(put('short.bgra', want[:-4])), 'not a PNG')
        other = png(W, H, bytes(W * H * 3), 3)
        zp = put('anim.zip', animation([('part0/001.png', other), ('part0/000.png', open(card_png, 'rb').read()), ('part0/002.png', other)]))
        raw3, kind3 = lfs.picture_bgra(zp)
        check("2.8 from an animation zip the picture is its first frame, part0/000.png", raw3 == want and 'first frame' in kind3)
        refused("2.9 another frame's animation (1280 800) refused",
                lambda: lfs.picture_bgra(put('other.zip', animation([('part0/000.png', other)], '1280 800 10\np 0 10 part0\n'))), 'not 2000 x 1200')
        nodesc = io.BytesIO()
        with zipfile.ZipFile(nodesc, 'w') as z:
            z.writestr('part0/000.png', other)
        refused('2.10 a zip with no desc.txt refused', lambda: lfs.picture_bgra(put('nodesc.zip', nodesc.getvalue())), 'desc.txt')
        refused('2.11 an animation with no frames refused', lambda: lfs.picture_bgra(put('empty.zip', animation([]))), 'no part0 frames')

        # ------------------------------------------------------------ 3. the image built from the picture
        out_path = os.path.join(t, 'logo-new.img')
        digest = lfs.make(card_png, out_path, say=lambda s: None)
        out = open(out_path, 'rb').read()
        op = logocodec.parse(out)
        check('3.1 the image is exactly 8,388,608 bytes and its SHA-256 is the one reported',
              len(out) == 8388608 and hashlib.sha256(out).hexdigest() == digest)
        rc, last = verifier(out_path)
        check('3.2 logoverify.py (its own program) says PASS', rc == 0 and last.startswith('PASS'), last)
        check('3.3 pictures 0 and 38 decode to exactly the picture given, 2000x1200x4 bytes',
              all(zlib.decompress(op['blobs'][i]) == want for i in (0, 38)) and len(want) == 9600000)
        same = [i for i in range(sp['n']) if i not in (0, 38) and op['blobs'][i] == sp['blobs'][i]]
        check('3.4 the image has 42 pictures and the other 40 are byte-identical to the factory ones',
              op['n'] == sp['n'] == 42 and len(same) == 40, '%d identical' % len(same))
        check('3.5 the header differs from the factory header only in its size field',
              out[:4] == stock[:4] and out[8:0x200] == stock[8:0x200] and struct.unpack_from('<I', out, 4)[0] == op['psize'])
        end = 0x200 + op['psize']
        c2 = out.rfind(b'cert2') - 8                              # start of the second certificate's own header
        check('3.6 everything after the second certificate is zeros to the end',
              c2 > end and not any(out[c2 + 0x200 + 957:]))
        check('3.7 no unverified file is left beside the result', os.listdir(t).count('logo-new.img.unverified') == 0)
        out_b = os.path.join(t, 'logo-from-zip.img')
        p = subprocess.run(TOOL + [zp, out_b], capture_output=True, text=True)
        ob = logocodec.parse(open(out_b, 'rb').read()) if p.returncode == 0 else None
        check('3.8 run as a command on the animation zip: exit 0, PASS printed, same pictures',
              p.returncode == 0 and 'logoverify.py: PASS' in p.stdout and ob['blobs'][0] == op['blobs'][0] and verifier(out_b)[0] == 0,
              p.stderr.strip())

        # ------------------------------------------------------------ 4. a damaged image fails the check
        def damaged(name, at, expect):
            d = bytearray(out); d[at] ^= 0x01
            rc, last = verifier(put('bad.img', bytes(d)))
            check(name, rc == 1 and last.startswith('FAIL [%s]' % expect), last)
        damaged('4.1 one bit changed inside picture 0: FAIL at the data hash', 0x200 + op['offs'][0] + 100, 'data hash')
        damaged('4.2 one bit changed inside a factory picture (5): FAIL at the data hash', 0x200 + op['offs'][5] + 10, 'data hash')
        damaged('4.3 one bit changed in the header: FAIL at the header hash', 0x100, 'header hash')
        damaged('4.4 one bit changed in the last signature: FAIL at the cert2 signature', c2 + 0x200 + 957 - 5, 'cert2 signature')
        damaged('4.5 one bit set in the empty tail: FAIL at the padding', 8388608 - 1, 'padding')
        rc, last = verifier(put('bad.img', out[:-4096]))
        check('4.6 an image cut short: FAIL at the size', rc == 1 and last.startswith('FAIL [size]'), last)

        # ------------------------------------------------------------ 5. nothing unverified is ever left behind
        nokey = put('not-lk.img', bytes(1024 * 1024))             # stands in for a bootloader that does not hold our root key
        dst = os.path.join(t, 'must-not-exist.img')
        p = subprocess.run(TOOL + [card_png, dst, '--lk', nokey], capture_output=True, text=True)
        check('5.1 when the check refuses (root key not in the bootloader given): exit 1, no image, no leftovers',
              p.returncode == 1 and 'root key' in p.stderr and not os.path.exists(dst) and not os.path.exists(dst + '.unverified'),
              p.stderr.strip())
        dst2 = os.path.join(t, 'kept.img')
        open(dst2, 'wb').write(b'earlier good image')
        p = subprocess.run(TOOL + [card_png, dst2, '--lk', nokey], capture_output=True, text=True)
        check('5.2 an earlier image under the same name is left untouched by a refused build',
              p.returncode == 1 and open(dst2, 'rb').read() == b'earlier good image')
        refused('5.3 a template that is not the factory image is refused (pictures 1..n must be the factory ones)',
                lambda: lfs.make(card_png, os.path.join(t, 'x.img'), stock_path=OTHER, say=lambda s: None), 'not the factory logo')
        check('5.4 ...and it left no file', not os.path.exists(os.path.join(t, 'x.img')))
        p = subprocess.run(TOOL + [put('small2.png', png(1280, 800, bytes(1280 * 800 * 3), 3)), os.path.join(t, 'y.img')], capture_output=True, text=True)
        check('5.5 a wrong-sized picture as a command: exit 1, a plain reason, no file',
              p.returncode == 1 and 'exactly 2000x1200' in p.stderr and not os.path.exists(os.path.join(t, 'y.img')), p.stderr.strip())
        src = open(os.path.join(HERE, 'logo-from-splash.py')).read()
        check('5.6 the tool has no adb, no partition path and no network in it',
              not any(s in src for s in ('adb', '/dev/block', 'by-name', 'urllib', 'socket', 'http')))
        check('5.7 logosign.py is imported, not copied: the tool signs only through logosign.sign_parts',
              'logosign.sign_parts(' in src and 'openssl' not in src)

    print('\n%d checks, %d failed' % (len(results), results.count(False)))
    print('ALL PASS' if all(results) else 'SOME FAILED')
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
