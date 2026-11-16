#!/usr/bin/env python3
"""Make a signed first-boot 'logo' image for the Lexar from the dashboard's start-up splash. Offline only.

    python3 -I tools/logo-from-splash.py <picture> <out.img> [--stock logo.img] [--lk lk.img] [--preloader boot0.img]

<picture> is one of (told apart by content, not by name):
  - a PNG, exactly 2000x1200, 8 bits per channel, RGB or RGBA with no transparency
  - a start-up animation zip (desc.txt says 2000 1200): its first frame, part0/000.png, is the picture
  - raw B,G,R,A bytes, exactly 2000x1200x4 = 9,600,000 bytes, every alpha byte 255

What it does, in this order:
  1. reads the picture into 2000x1200 B,G,R,A (alpha 255, as the factory pictures have)
  2. takes the FACTORY logo image as the template (its SHA-256 is pinned below; anything else is refused)
  3. replaces pictures 0 and 38 (the bootloader's logo and Android's repeat of it) and keeps every other
     picture's compressed bytes exactly as they are in the factory image
  4. signs with logosign.py (imported, not changed): cert1 by the MediaTek root key, cert2 by our image key
  5. checks its own work: 8 MiB, pictures 0 and 38 decode to the picture, all the others byte-identical
  6. runs logoverify.py on the result as a separate program (it shares no code with the signer)
  7. only if that says PASS does the file appear under the name asked for

Nothing here talks to the frame. No PNG library and no `sips` are needed: the PNG reader below uses only zlib,
so the same file can later run in the frame's Linux folder.
"""
import hashlib, io, os, re, struct, subprocess, sys, zipfile, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logosign  # noqa: E402
import logocodec  # noqa: E402
import px110conf  # noqa: E402  (where the backup is)

STOCK = os.path.join(px110conf.path('BACKUP_DIR') or 'BACKUP_DIR-not-set', 'logo.img')
STOCK_SHA256 = 'b2e2fc50b1243f0716a94b51fc9bc37e1489d2f3c1c1dcab91df5b4df328ab93'   # the factory logo partition
VERIFY = os.path.join(HERE, 'logoverify.py')

W, H = logosign.W, logosign.H
PICTURES = logosign.PICTURES            # (0, 38)
RAW_SIZE = W * H * 4
PART_SIZE = logosign.PART_SIZE
MAX_INPUT = 64 * 1024 * 1024            # nothing we read is anywhere near this
PNG_SIG = b'\x89PNG\r\n\x1a\n'


class SplashError(Exception):
    pass


# ---------------------------------------------------------------- the picture
def png_to_bgra(data):
    """PNG bytes -> (width, height, top-down B,G,R,A bytes with alpha 255). 8-bit RGB or RGBA, not interlaced."""
    if data[:8] != PNG_SIG:
        raise SplashError('not a PNG')
    pos, ihdr, idat, ended = 8, None, [], False
    while pos < len(data):
        if pos + 12 > len(data):
            raise SplashError('PNG is cut short')
        n, kind = struct.unpack_from('>I4s', data, pos)
        body = data[pos + 8:pos + 8 + n]
        if len(body) != n or pos + 12 + n > len(data):
            raise SplashError('PNG is cut short')
        if struct.unpack_from('>I', data, pos + 8 + n)[0] != (zlib.crc32(kind + body) & 0xFFFFFFFF):
            raise SplashError('PNG chunk %s fails its checksum' % kind.decode('latin-1'))
        pos += 12 + n
        if kind == b'IHDR':
            ihdr = body
        elif kind == b'IDAT':
            idat.append(body)
        elif kind == b'IEND':
            ended = True
            break
    if ihdr is None or len(ihdr) != 13 or not idat or not ended:
        raise SplashError('PNG has no header, no picture data or no end')
    w, h, depth, colour, comp, filt, lace = struct.unpack('>IIBBBBB', ihdr)
    if depth != 8 or colour not in (2, 6) or comp or filt or lace:
        raise SplashError('PNG must be 8 bits per channel, RGB or RGBA, not interlaced '
                          '(this one: depth %d, colour type %d, interlace %d)' % (depth, colour, lace))
    if not (0 < w <= 4096 and 0 < h <= 4096):
        raise SplashError('PNG is %dx%d' % (w, h))
    bpp = 3 if colour == 2 else 4
    stride = w * bpp
    try:
        z = zlib.decompressobj()
        flat = z.decompress(b''.join(idat), h * (stride + 1) + 1)
    except zlib.error as e:
        raise SplashError('PNG picture data does not decompress (%s)' % e)
    if len(flat) != h * (stride + 1) or z.unconsumed_tail:
        raise SplashError('PNG picture data is the wrong length')

    px = bytearray(h * stride)
    prev = bytes(stride)
    at = 0
    for y in range(h):
        ft = flat[at]
        row = bytearray(flat[at + 1:at + 1 + stride])
        at += 1 + stride
        if ft == 1:                                         # Sub
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif ft == 2:                                       # Up
            row = bytearray((a + b) & 255 for a, b in zip(row, prev))
        elif ft == 3:                                       # Average
            for i in range(bpp):
                row[i] = (row[i] + (prev[i] >> 1)) & 255
            for i in range(bpp, stride):
                row[i] = (row[i] + ((row[i - bpp] + prev[i]) >> 1)) & 255
        elif ft == 4:                                       # Paeth
            for i in range(bpp):
                row[i] = (row[i] + prev[i]) & 255
            for i in range(bpp, stride):
                a = row[i - bpp]; b = prev[i]; c = prev[i - bpp]
                p = a + b - c
                pa = abs(p - a); pb = abs(p - b); pc = abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif ft != 0:
            raise SplashError('PNG row %d has an unknown filter (%d)' % (y, ft))
        px[y * stride:(y + 1) * stride] = row
        prev = row

    if bpp == 4 and px[3::4].count(255) != w * h:
        raise SplashError('PNG has transparent pixels; the logo needs a fully opaque picture')
    out = bytearray(b'\xff' * (w * h * 4))
    out[0::4] = px[2::bpp]
    out[1::4] = px[1::bpp]
    out[2::4] = px[0::bpp]
    return w, h, bytes(out)


def first_frame(zip_bytes):
    """A start-up animation zip -> the bytes of its first frame (lowest-numbered part0/NNN.png)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = {i.filename: i for i in z.infolist()}
        if 'desc.txt' not in names or names['desc.txt'].file_size > 4096:
            raise SplashError('the zip has no desc.txt: not a start-up animation')
        first = z.read('desc.txt').decode('ascii', 'replace').split('\n')[0].split()
        if first[:2] != [str(W), str(H)]:
            raise SplashError('the animation is %s, not %d x %d' % (' x '.join(first[:2]) or '?', W, H))
        frames = sorted(n for n in names if re.fullmatch(r'part0/[0-9]+\.png', n))
        if not frames:
            raise SplashError('the animation has no part0 frames')
        if names[frames[0]].file_size > MAX_INPUT:
            raise SplashError('the first frame is implausibly large')
        return z.read(frames[0])
    except (zipfile.BadZipFile, KeyError, RuntimeError, zlib.error) as e:
        raise SplashError('cannot read the animation zip (%s)' % e)


def picture_bgra(path):
    """The picture file -> exactly 2000x1200 B,G,R,A bytes, alpha 255. Says what kind of input it was."""
    if os.path.getsize(path) > MAX_INPUT:
        raise SplashError('the picture file is implausibly large')
    data = open(path, 'rb').read()
    if data[:4] == b'PK\x03\x04':
        kind = 'first frame of the animation'
        w, h, raw = png_to_bgra(first_frame(data))
    elif data[:8] == PNG_SIG:
        kind = 'PNG'
        w, h, raw = png_to_bgra(data)
    elif len(data) == RAW_SIZE:
        kind = 'raw B,G,R,A'
        if data[3::4].count(255) != W * H:
            raise SplashError('raw picture has alpha bytes that are not 255')
        w, h, raw = W, H, data
    else:
        raise SplashError('the picture is not a PNG, an animation zip or %d raw bytes' % RAW_SIZE)
    if (w, h) != (W, H):
        raise SplashError('the picture is %dx%d; it must be exactly %dx%d' % (w, h, W, H))
    return raw, kind


# ---------------------------------------------------------------- the image
def build(raw, stock):
    """2000x1200 B,G,R,A + the factory logo image -> the signed 8 MiB image (not yet verified)."""
    if len(raw) != RAW_SIZE:
        raise SplashError('picture is %d bytes, expected %d' % (len(raw), RAW_SIZE))
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA256:
        raise SplashError('the template is not the factory logo image (SHA-256 differs); refusing')
    img = logosign.parse_image(stock)
    blobs = list(logocodec.parse(stock)['blobs'])           # the factory's compressed pictures, kept as they are
    if len(blobs) <= max(PICTURES):
        raise SplashError('the template has only %d pictures' % len(blobs))
    for i in PICTURES:
        if len(zlib.decompress(blobs[i])) != RAW_SIZE:
            raise SplashError('picture %d in the template is not %dx%d' % (i, W, H))
    new = zlib.compress(raw, 9)
    for i in PICTURES:
        blobs[i] = new
    n = len(blobs)
    offs, off = [], 8 + 4 * n
    for b in blobs:
        offs.append(off); off += len(b)
    payload = struct.pack('<II', n, off) + struct.pack('<%dI' % n, *offs) + b''.join(blobs)
    header = bytearray(img['header'])
    struct.pack_into('<I', header, 4, len(payload))
    return logosign.sign_parts(bytes(header), payload, img)


def self_check(out, raw, stock):
    """Our own look at the result before the independent checker sees it. Raises on anything unexpected."""
    if len(out) != PART_SIZE:
        raise SplashError('result is %d bytes, not %d' % (len(out), PART_SIZE))
    got, want = logocodec.parse(out), logocodec.parse(stock)
    if got['n'] != want['n']:
        raise SplashError('result has %d pictures, the factory image %d' % (got['n'], want['n']))
    for i in range(want['n']):
        if i in PICTURES:
            if zlib.decompress(got['blobs'][i]) != raw:
                raise SplashError('picture %d in the result is not the picture given' % i)
        elif got['blobs'][i] != want['blobs'][i]:
            raise SplashError('picture %d changed; it must stay the factory one' % i)
    if out[:4] != stock[:4] or out[8:logosign.HDR] != stock[8:logosign.HDR]:
        raise SplashError('the header changed outside its size field')


def verify(path, lk=None, preloader=None):
    """Run logoverify.py as its own program. -> (passed, its last line)."""
    cmd = [sys.executable, '-I', VERIFY, path, '--quiet']
    if lk:
        cmd += ['--lk', lk]
    if preloader:
        cmd += ['--preloader', preloader]
    p = subprocess.run(cmd, capture_output=True, text=True)
    last = (p.stdout.strip().splitlines() or [p.stderr.strip() or 'no output'])[-1]
    return p.returncode == 0 and last.startswith('PASS'), last


def make(picture, dst, stock_path=STOCK, lk=None, preloader=None, say=print):
    """The whole chain. The file `dst` exists afterwards only if every step passed. -> SHA-256 of the image."""
    raw, kind = picture_bgra(picture)
    stock = open(stock_path, 'rb').read()
    try:
        out = build(raw, stock)
    except (logosign.SignError, AssertionError) as e:
        raise SplashError('signing: %s' % e)
    self_check(out, raw, stock)
    tmp = dst + '.unverified'
    try:
        with open(tmp, 'wb') as f:
            f.write(out); f.flush(); os.fsync(f.fileno())
        ok, last = verify(tmp, lk, preloader)
        if not ok:
            raise SplashError('the independent check refused the image: %s' % last)
        if open(tmp, 'rb').read() != out:
            raise SplashError('the file on disk is not what was built')
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    digest = hashlib.sha256(out).hexdigest()
    packed = len(logocodec.parse(out)['blobs'][PICTURES[0]])
    say('picture         %s, %dx%d, %d bytes compressed (in twice: pictures %s)'
        % (kind, W, H, packed, ' and '.join(map(str, PICTURES))))
    say('room            payload %d bytes of the %d-byte partition'
        % (struct.unpack_from('<I', out, 4)[0], PART_SIZE))
    say('verified        logoverify.py: PASS')
    say('%s  %s  (%d bytes)' % (digest, dst, len(out)))
    return digest


def main(argv):
    args = argv[1:]
    opt = {'--stock': STOCK, '--lk': None, '--preloader': None}
    for k in list(opt):
        if k in args:
            i = args.index(k)
            if i + 1 >= len(args):
                print(__doc__); return 2
            opt[k] = args[i + 1]; del args[i:i + 2]
    if len(args) != 2:
        print(__doc__); return 2
    try:
        make(args[0], args[1], opt['--stock'], opt['--lk'], opt['--preloader'])
    except (SplashError, OSError) as e:
        print('logo-from-splash: ERROR: %s' % e, file=sys.stderr); return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
