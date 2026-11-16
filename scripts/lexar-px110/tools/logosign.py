#!/usr/bin/env python3
"""Sign a MediaTek 'logo' partition image with the published MediaTek default keys. Offline only.

    python3 -I tools/logosign.py resign <in logo.img> <out>
    python3 -I tools/logosign.py make   <stock logo.img> <picture.png> <out>

Nothing here talks to the frame. The output is a file on this computer. Keys: KEY_DIR (see px110conf.py).

Image layout (parsed, then asserted against the stock values when the input is the stock image):
  0x000   512-byte header (magic 0x58881688, u32 payload size, name "logo")
  0x200   payload: the pictures (see logocodec.py)
  align16 'cert1': own 512-byte header + X.509-like DER, signed by the ROOT key; carries the IMAGE key
  align16 'cert2': own 512-byte header + DER, signed by the IMAGE key; carries two SHA-256 hashes
  zeros to exactly 8,388,608 bytes

The certificates are patched in place (same lengths, same layout). Only these bytes change:
  cert1: the image key (SubjectPublicKeyInfo after OID 2.16.886.2454.1.2) and the signature
  cert2: its own public key (the image key), the two hashes, and the signature
Signatures are RSA-PSS, SHA-256, MGF1-SHA-256, salt 32, made by the `openssl` command.
"""
import hashlib, os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logocodec  # noqa: E402  (pictures: decode / re-encode)
import px110conf  # noqa: E402  (where the key files are)

KEYDIR = os.path.dirname(px110conf.key('x'))
ROOT_KEY = os.path.join(KEYDIR, 'root_prvk.pem')
IMG_KEY = os.path.join(KEYDIR, 'img_prvk.pem')
# SHA-256 of `openssl rsa -noout -modulus` output (the line "Modulus=<HEX>\n")
ROOT_MODULUS_SHA256 = 'a2c5f4f92680d60dd400bc40245d4c3c0e52a16824b677b98aa4260ffebfbce3'
IMG_MODULUS_SHA256 = 'c107191b9c4bb4d13ece82c673d2cbeb9e59092a2f20b699f2c10cadee124f54'

PART_SIZE = 8 * 1024 * 1024
HDR = 0x200
MAGIC = 0x58881688
EXT_MAGIC = 0x58891689
ALIGN = 16
W, H = 2000, 1200
PICTURES = (0, 38)          # LK's first logo and Android's repeat of it

OID_MTK = bytes([0x60, 0x86, 0x76, 0x93, 0x16])     # 2.16.886.2454
OID_IMG_KEY = OID_MTK + b'\x01\x02'
OID_DATA_HASH = OID_MTK + b'\x02\x01'
OID_HDR_HASH = OID_MTK + b'\x02\x04'

# What the stock image must parse to (plan, "already proven"). Checked only for the stock input.
STOCK = dict(cert1_off=0x1A0D00, cert2_off=0x1A15B0, cert1_len=1709, cert2_len=957,
             c1_imgkey=(496, 790), c2_spki=(181, 475), spki_len=294)


class SignError(Exception):
    pass


# ---------------------------------------------------------------- DER (just enough)
def der_tlv(buf, off):
    """-> (tag, header_len, content_len) of the element starting at off."""
    tag = buf[off]
    n = buf[off + 1]
    if n < 0x80:
        return tag, 2, n
    k = n & 0x7F
    if not 1 <= k <= 4:
        raise SignError('unsupported DER length at %d' % off)
    return tag, 2 + k, int.from_bytes(buf[off + 2:off + 2 + k], 'big')


def der_children(buf, off):
    """Offsets (start, end) of the elements directly inside the constructed element at off."""
    _, hl, ln = der_tlv(buf, off)
    pos, end, out = off + hl, off + hl + ln, []
    while pos < end:
        _, h, l = der_tlv(buf, pos)
        out.append((pos, pos + h + l))
        pos += h + l
    if pos != end:
        raise SignError('DER children overrun at %d' % off)
    return out


class Cert:
    """Offsets inside one certificate's DER."""

    def __init__(self, der):
        self.der = der
        tag, hl, ln = der_tlv(der, 0)
        if tag != 0x30 or hl + ln != len(der):
            raise SignError('certificate is not one DER SEQUENCE of the stated length')
        top = der_children(der, 0)
        if len(top) != 3:
            raise SignError('certificate should have 3 parts (TBS, algorithm, signature)')
        self.tbs = top[0]
        self.fields = der_children(der, self.tbs[0])
        s0, s1 = top[2]
        tag, hl, ln = der_tlv(der, s0)
        if tag != 0x03 or ln != 257 or der[s0 + hl] != 0:
            raise SignError('signature is not a 2048-bit BIT STRING')
        self.sig = (s0 + hl + 1, s1)
        # standard X.509 order: [0]version, serial, sigalg, issuer, validity, subject, SPKI, then MTK fields
        self.spki = self.fields[6]
        if der[self.spki[0]] != 0x30:
            raise SignError('field 7 of the TBS is not a SubjectPublicKeyInfo')

    def after_oid(self, oid):
        """(start, end) of the element that follows the given OID in the TBS."""
        want = b'\x06' + bytes([len(oid)]) + oid
        hits = [i for i, (a, b) in enumerate(self.fields) if self.der[a:b] == want]
        if len(hits) != 1:
            raise SignError('OID %s found %d times' % (oid.hex(), len(hits)))
        return self.fields[hits[0] + 1]

    def bitstring_body(self, span, length):
        """(start, end) of the bytes of a BIT STRING with 0 unused bits and the given length."""
        tag, hl, ln = der_tlv(self.der, span[0])
        if tag != 0x03 or ln != length + 1 or self.der[span[0] + hl] != 0:
            raise SignError('expected a BIT STRING of %d bytes at %d' % (length, span[0]))
        return span[0] + hl + 1, span[1]


# ---------------------------------------------------------------- image layout
def align(n, a=ALIGN):
    return (n + a - 1) // a * a


def parse_image(d):
    if len(d) != PART_SIZE:
        raise SignError('input is %d bytes, not %d' % (len(d), PART_SIZE))
    magic, psize = struct.unpack_from('<II', d, 0)
    if magic != MAGIC or d[8:40].rstrip(b'\0') != b'logo':
        raise SignError('not a logo image (magic/name)')
    out = dict(header=d[:HDR], payload=d[HDR:HDR + psize])
    pos = align(HDR + psize)
    for name in (b'cert1', b'cert2'):
        magic, clen = struct.unpack_from('<II', d, pos)
        if magic != MAGIC or d[pos + 8:pos + 40].rstrip(b'\0') != name:
            raise SignError('%s header not found at 0x%X' % (name.decode(), pos))
        if struct.unpack_from('<I', d, pos + 0x30)[0] != EXT_MAGIC:
            raise SignError('%s extended header magic missing' % name.decode())
        key = name.decode()
        out[key + '_off'] = pos
        out[key + '_hdr'] = d[pos:pos + HDR]
        out[key] = d[pos + HDR:pos + HDR + clen]
        pos = align(pos + HDR + clen)
    if any(d[out['cert2_off'] + HDR + len(out['cert2']):]):
        raise SignError('input has non-zero bytes after cert2')
    return out


def is_stock_layout(img):
    return img['cert1_off'] == STOCK['cert1_off'] and img['cert2_off'] == STOCK['cert2_off']


# ---------------------------------------------------------------- keys and openssl
def run(args, data=None):
    p = subprocess.run(args, input=data, capture_output=True)
    if p.returncode != 0:
        raise SignError('%s failed: %s' % (' '.join(args[:3]), p.stderr.decode(errors='replace').strip()))
    return p.stdout


def check_key(path, want):
    if not os.path.exists(path):
        raise SignError('key file missing: %s (fetch-keys.sh gets it)' % path)
    got = hashlib.sha256(run(['openssl', 'rsa', '-in', path, '-noout', '-modulus'])).hexdigest()
    if got != want:
        raise SignError('%s is not the pinned key (modulus hash %s)' % (os.path.basename(path), got))


def public_spki(path):
    return run(['openssl', 'rsa', '-in', path, '-pubout', '-outform', 'DER'])


def pss_sign(key_path, message):
    with tempfile.NamedTemporaryFile() as f:
        f.write(message); f.flush()
        sig = run(['openssl', 'dgst', '-sha256', '-sign', key_path,
                   '-sigopt', 'rsa_padding_mode:pss', '-sigopt', 'rsa_pss_saltlen:32', f.name])
    if len(sig) != 256:
        raise SignError('signature is %d bytes, expected 256' % len(sig))
    return sig


# ---------------------------------------------------------------- signing
def data_hash(payload):
    return hashlib.sha256(payload + b'\0' * (-len(payload) % ALIGN)).digest()


def sign_parts(header, payload, img):
    """Build the full 8 MiB image from a header, a payload and the parsed stock/previous image."""
    check_key(ROOT_KEY, ROOT_MODULUS_SHA256)
    check_key(IMG_KEY, IMG_MODULUS_SHA256)
    img_spki = public_spki(IMG_KEY)
    root_spki = public_spki(ROOT_KEY)

    c1 = Cert(img['cert1']); c2 = Cert(img['cert2'])
    k1 = c1.after_oid(OID_IMG_KEY)          # image key carried by cert1
    k2 = c2.spki                            # cert2's own key = the image key
    h_data = c2.bitstring_body(c2.after_oid(OID_DATA_HASH), 32)
    h_hdr = c2.bitstring_body(c2.after_oid(OID_HDR_HASH), 32)

    if is_stock_layout(img):                # the parse must agree with the plan's offsets
        assert (len(c1.der), len(c2.der)) == (STOCK['cert1_len'], STOCK['cert2_len']), 'certificate lengths'
        assert k1 == STOCK['c1_imgkey'], 'cert1 image-key offsets %r' % (k1,)
        assert k2 == STOCK['c2_spki'], 'cert2 key offsets %r' % (k2,)
    if c1.der[c1.spki[0]:c1.spki[1]] != root_spki:
        raise SignError("cert1's own public key is not the published root key; refusing")
    for span, what in ((k1, 'cert1 image key'), (k2, 'cert2 key')):
        if span[1] - span[0] != len(img_spki):
            raise SignError('%s is %d bytes; the new key is %d: cannot patch in place'
                            % (what, span[1] - span[0], len(img_spki)))

    n1 = bytearray(c1.der)
    n1[k1[0]:k1[1]] = img_spki
    n1[c1.sig[0]:c1.sig[1]] = pss_sign(ROOT_KEY, bytes(n1[c1.tbs[0]:c1.tbs[1]]))

    n2 = bytearray(c2.der)
    n2[k2[0]:k2[1]] = img_spki
    n2[h_data[0]:h_data[1]] = data_hash(payload)
    n2[h_hdr[0]:h_hdr[1]] = hashlib.sha256(header).digest()
    n2[c2.sig[0]:c2.sig[1]] = pss_sign(IMG_KEY, bytes(n2[c2.tbs[0]:c2.tbs[1]]))

    assert len(n1) == len(c1.der) and len(n2) == len(c2.der)
    out = bytearray(header) + payload
    out += b'\0' * (align(len(out)) - len(out))
    out += img['cert1_hdr'] + n1
    out += b'\0' * (align(len(out)) - len(out))
    out += img['cert2_hdr'] + n2
    if len(out) > PART_SIZE:
        raise SignError('image would be %d bytes: does not fit the 8 MiB partition' % len(out))
    return bytes(out) + b'\0' * (PART_SIZE - len(out))


def resign(d):
    img = parse_image(d)
    return sign_parts(img['header'], img['payload'], img)


# ---------------------------------------------------------------- pictures
def read_bmp_bgra(path):
    """Read an uncompressed 24- or 32-bit BMP -> (width, height, top-down B,G,R,A bytes, alpha 255)."""
    b = open(path, 'rb').read()
    if b[:2] != b'BM':
        raise SignError('not a BMP')
    pix_off = struct.unpack_from('<I', b, 10)[0]
    hsize, w, h, planes, bpp, comp = struct.unpack_from('<IiiHHI', b, 14)
    if hsize < 40 or planes != 1:
        raise SignError('unsupported BMP header')
    if bpp == 24 and comp == 0:
        order = (0, 1, 2)                   # file bytes are B,G,R
    elif bpp == 32 and comp == 0:
        order = (0, 1, 2)
    elif bpp == 32 and comp == 3:           # BI_BITFIELDS: masks follow the 40-byte core (or sit in a V4/V5 header)
        masks = struct.unpack_from('<III', b, 14 + 40)
        pos = {0x000000FF: 0, 0x0000FF00: 1, 0x00FF0000: 2, 0xFF000000: 3}
        try:
            r, g, bl = (pos[m] for m in masks)
        except KeyError:
            raise SignError('unsupported BMP colour masks')
        order = (bl, g, r)
    else:
        raise SignError('unsupported BMP: %d bits, compression %d' % (bpp, comp))
    step = bpp // 8
    stride = (w * step + 3) & ~3
    top_down = h < 0
    h = abs(h)
    if len(b) < pix_off + stride * h:
        raise SignError('BMP is truncated')
    out = bytearray(b'\xff' * (w * h * 4))
    for y in range(h):
        src = pix_off + stride * (y if top_down else h - 1 - y)
        row = b[src:src + w * step]
        dst = y * w * 4
        for c in range(3):
            out[dst + c:dst + w * 4:4] = row[order[c]::step]
    return w, h, bytes(out)


def picture_to_bgra(png_path):
    """PNG -> raw 2000x1200 B,G,R,A (alpha 255, like the stock pictures), via macOS sips."""
    with tempfile.TemporaryDirectory() as t:
        bmp = os.path.join(t, 'p.bmp')
        run(['sips', '-s', 'format', 'bmp', png_path, '--out', bmp])
        w, h, raw = read_bmp_bgra(bmp)
    if (w, h) != (W, H):
        raise SignError('picture is %dx%d; it must be exactly %dx%d' % (w, h, W, H))
    return raw


def make(stock, png_path):
    raw = picture_to_bgra(png_path)
    img = parse_image(stock)
    raws, p = logocodec.decode(stock)
    for i in PICTURES:
        if len(raws[i]) != W * H * 4:
            raise SignError('picture %d in the input image is not %dx%d' % (i, W, H))
        raws[i] = raw
    payload = logocodec.build_payload(raws, template_blobs=p['blobs'])   # untouched pictures keep their bytes
    header = bytearray(img['header'])
    struct.pack_into('<I', header, 4, len(payload))
    return sign_parts(bytes(header), payload, img)


def main(argv):
    try:
        if len(argv) == 4 and argv[1] == 'resign':
            out = resign(open(argv[2], 'rb').read()); dst = argv[3]
        elif len(argv) == 5 and argv[1] == 'make':
            out = make(open(argv[2], 'rb').read(), argv[3]); dst = argv[4]
        else:
            print(__doc__); return 2
    except (SignError, AssertionError, OSError) as e:
        print('logosign: ERROR: %s' % e, file=sys.stderr); return 1
    with open(dst, 'wb') as f:
        f.write(out)
    print('%s  %s  (%d bytes)' % (hashlib.sha256(out).hexdigest(), dst, len(out)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
