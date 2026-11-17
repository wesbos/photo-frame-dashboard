"""dm-verity hashtree (as avbtool lays it out) and AOSP-style FEC (Reed-Solomon).

Standard library only.

Usage: hashtree.py IMAGE IMAGE_SIZE SALT_HEX     print root digest and tree size
"""
import hashlib
import sys

BLOCK = 4096


def build_hashtree(data, salt, alg="sha256", block=BLOCK):
    """Return (root_digest, tree_bytes) for `data` (length multiple of block).

    dm-verity version 1: each hash is H(salt || block). Levels are stored
    root-most first, leaf level last, each level zero-padded to a block.
    """
    assert len(data) % block == 0
    dlen = hashlib.new(alg).digest_size
    # avbtool pads each digest to the next power of two (32 for sha256, 64 for sha512)
    pad = 1
    while pad < dlen:
        pad *= 2
    levels = []
    cur = data
    while True:
        out = bytearray()
        mv = memoryview(cur)
        for off in range(0, len(cur), block):
            h = hashlib.new(alg, salt)
            h.update(mv[off : off + block])
            out += h.digest() + b"\0" * (pad - dlen)
        if len(cur) == block:
            root = bytes(out[:dlen])
            break
        out += b"\0" * (-len(out) % block)
        levels.append(bytes(out))
        cur = bytes(out)
    return root, b"".join(reversed(levels))


# ---- Reed-Solomon, as in AOSP libfec: GF(2^8) poly 0x11d, fcr 0, prim 1 ----

def _gf_tables():
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


_EXP, _LOG = _gf_tables()


def _mul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _generator(roots):
    g = [1]
    for i in range(roots):
        ng = [0] * (len(g) + 1)
        for k, c in enumerate(g):       # multiply by (x + alpha^i); g[0] is highest degree
            ng[k] ^= c
            ng[k + 1] ^= _mul(c, _EXP[i])
        g = ng
    return g


def _parity_coeffs(roots):
    """coeffs[j][k]: contribution of data byte j (0 = first) to parity byte k."""
    rsn = 255 - roots
    g = _generator(roots)
    coeffs = []
    for j in range(rsn):
        # remainder of x^(rsn-1-j) * x^roots mod g
        rem = [0] * roots
        msg = [0] * rsn
        msg[j] = 1
        for byte in msg:
            fb = byte ^ rem[0]
            rem = rem[1:] + [0]
            if fb:
                for k in range(roots):
                    rem[k] ^= _mul(fb, g[k + 1])
        coeffs.append(rem)
    return coeffs


def build_fec(data, roots=2, block=BLOCK):
    """FEC parity for `data`, laid out as AOSP `fec --encode` does (header stripped,
    as avbtool stores it). Codeword i takes byte i + j*rounds*block for j in 0..rsn-1
    (zero beyond the end of data); its `roots` parity bytes go to fec[i*roots:].
    """
    assert len(data) % block == 0
    rsn = 255 - roots
    blocks = len(data) // block
    rounds = -(-blocks // rsn)
    n = rounds * block                      # number of codewords
    coeffs = _parity_coeffs(roots)
    acc = [0] * roots
    for j in range(rsn):
        col = data[j * n : (j + 1) * n]
        if not col:
            break
        col = col + b"\0" * (n - len(col))
        for k in range(roots):
            c = coeffs[j][k]
            table = bytes(_mul(c, v) for v in range(256))
            acc[k] ^= int.from_bytes(col.translate(table), "big")
    cols = [a.to_bytes(n, "big") for a in acc]
    out = bytearray(n * roots)
    for k in range(roots):
        out[k::roots] = cols[k]
    return bytes(out)


def main():
    path, size, salt = sys.argv[1], int(sys.argv[2]), bytes.fromhex(sys.argv[3])
    with open(path, "rb") as f:
        data = f.read(size)
    root, tree = build_hashtree(data, salt)
    print("root_digest", root.hex())
    print("tree_size", len(tree), "tree_sha256", hashlib.sha256(tree).hexdigest())


if __name__ == "__main__":
    main()
