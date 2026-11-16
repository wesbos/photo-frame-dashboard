"""Small self-contained AVB (Android Verified Boot 2.0) library.

Parses and rebuilds vbmeta blobs, descriptors and footers, converts RSA keys
to the AVB public-key format, and signs the way avbtool does (RSA PKCS#1 v1.5
over SHA-256/512 of header||aux). Standard library only; RSA private-key
parameters are read through `openssl rsa -text`.
"""
import hashlib
import struct
import subprocess

HDR_FMT = ">4sLLQQLQQQQQQQQQQQLL48s80s"
HDR_SIZE = struct.calcsize(HDR_FMT)
assert HDR_SIZE == 256
HDR_FIELDS = (
    "magic ver_major ver_minor auth_size aux_size algorithm hash_offset hash_size "
    "sig_offset sig_size pk_offset pk_size pkmd_offset pkmd_size desc_offset desc_size "
    "rollback_index flags rollback_index_location release reserved"
).split()

# algorithm_type -> (name, hash name, hash bytes, signature bytes)
ALGS = {
    0: ("NONE", None, 0, 0),
    1: ("SHA256_RSA2048", "sha256", 32, 256),
    2: ("SHA256_RSA4096", "sha256", 32, 512),
    3: ("SHA256_RSA8192", "sha256", 32, 1024),
    4: ("SHA512_RSA2048", "sha512", 64, 256),
    5: ("SHA512_RSA4096", "sha512", 64, 512),
    6: ("SHA512_RSA8192", "sha512", 64, 1024),
}
DIGESTINFO = {
    "sha256": bytes.fromhex("3031300d060960864801650304020105000420"),
    "sha512": bytes.fromhex("3051300d060960864801650304020305000440"),
}

TAG_PROPERTY, TAG_HASHTREE, TAG_HASH, TAG_CMDLINE, TAG_CHAIN = 0, 1, 2, 3, 4
TAG_NAMES = {0: "property", 1: "hashtree", 2: "hash", 3: "kernel_cmdline", 4: "chain_partition"}

HT_FMT = ">LQQQLLLQQ32sLLLL60s"   # after the 16-byte tag/len header
HT_SIZE = struct.calcsize(HT_FMT)
assert HT_SIZE == 164
HT_FIELDS = (
    "dm_verity_version image_size tree_offset tree_size data_block_size hash_block_size "
    "fec_num_roots fec_offset fec_size hash_algorithm name_len salt_len digest_len flags reserved"
).split()
HASH_FMT = ">Q32sLLLL60s"
CHAIN_FMT = ">LLL64s"
FOOTER_FMT = ">4sLLQQQ28s"
FOOTER_SIZE = 64


class Vbmeta:
    """A parsed vbmeta blob (header + auth block + aux block)."""

    def __init__(self, blob):
        vals = struct.unpack(HDR_FMT, blob[:HDR_SIZE])
        self.h = dict(zip(HDR_FIELDS, vals))
        if self.h["magic"] != b"AVB0":
            raise ValueError("not a vbmeta blob (magic %r)" % self.h["magic"])
        self.size = HDR_SIZE + self.h["auth_size"] + self.h["aux_size"]
        self.blob = bytes(blob[: self.size])
        self.header = self.blob[:HDR_SIZE]
        self.auth = self.blob[HDR_SIZE : HDR_SIZE + self.h["auth_size"]]
        self.aux = self.blob[HDR_SIZE + self.h["auth_size"] :]
        h = self.h
        self.hash = self.auth[h["hash_offset"] : h["hash_offset"] + h["hash_size"]]
        self.signature = self.auth[h["sig_offset"] : h["sig_offset"] + h["sig_size"]]
        self.public_key = self.aux[h["pk_offset"] : h["pk_offset"] + h["pk_size"]]
        self.pkmd = self.aux[h["pkmd_offset"] : h["pkmd_offset"] + h["pkmd_size"]]
        self.desc_bytes = self.aux[h["desc_offset"] : h["desc_offset"] + h["desc_size"]]
        self.descriptors = parse_descriptors(self.desc_bytes)

    @property
    def release(self):
        return self.h["release"].rstrip(b"\0").decode()

    def alg(self):
        return ALGS[self.h["algorithm"]]

    def verify(self, expected_key=None):
        """Check hash and RSA signature. Returns the embedded AVB public key.

        If expected_key is given, the embedded key must equal it exactly.
        Raises ValueError on any mismatch.
        """
        name, hname, hlen, slen = self.alg()
        if hname is None:
            raise ValueError("vbmeta is unsigned (algorithm NONE)")
        digest = hashlib.new(hname, self.header + self.aux).digest()
        if digest != self.hash:
            raise ValueError("vbmeta hash mismatch")
        if expected_key is not None and self.public_key != expected_key:
            raise ValueError("vbmeta is signed by a different key than expected")
        bits, n, _ = decode_avb_pubkey(self.public_key)
        if bits // 8 != slen or len(self.signature) != slen:
            raise ValueError("key/signature size does not match algorithm")
        em = pow(int.from_bytes(self.signature, "big"), 65537, n).to_bytes(slen, "big")
        if em != pkcs1_pad(hname, digest, slen):
            raise ValueError("vbmeta RSA signature mismatch")
        return self.public_key


def parse_descriptors(data):
    out = []
    off = 0
    while off < len(data):
        tag, nbf = struct.unpack(">QQ", data[off : off + 16])
        raw = data[off : off + 16 + nbf]
        body = raw[16:]
        d = {"tag": tag, "type": TAG_NAMES.get(tag, "unknown"), "raw": raw}
        if tag == TAG_HASHTREE:
            f = dict(zip(HT_FIELDS, struct.unpack(HT_FMT, body[:HT_SIZE])))
            p = HT_SIZE
            f["name"] = body[p : p + f["name_len"]].decode(); p += f["name_len"]
            f["salt"] = body[p : p + f["salt_len"]]; p += f["salt_len"]
            f["root_digest"] = body[p : p + f["digest_len"]]
            f["hash_algorithm"] = f["hash_algorithm"].rstrip(b"\0").decode()
            d.update(f)
        elif tag == TAG_HASH:
            n = struct.calcsize(HASH_FMT)
            isz, alg, nl, sl, dl, fl, _ = struct.unpack(HASH_FMT, body[:n])
            p = n
            d.update(image_size=isz, hash_algorithm=alg.rstrip(b"\0").decode(), flags=fl)
            d["name"] = body[p : p + nl].decode(); p += nl
            d["salt"] = body[p : p + sl]; p += sl
            d["digest"] = body[p : p + dl]
        elif tag == TAG_CHAIN:
            n = struct.calcsize(CHAIN_FMT)
            loc, nl, kl, _ = struct.unpack(CHAIN_FMT, body[:n])
            p = n
            d["rollback_index_location"] = loc
            d["name"] = body[p : p + nl].decode(); p += nl
            d["public_key"] = body[p : p + kl]
        elif tag == TAG_CMDLINE:
            fl, ln = struct.unpack(">LL", body[:8])
            d.update(flags=fl, cmdline=body[8 : 8 + ln].decode())
        elif tag == TAG_PROPERTY:
            kl, vl = struct.unpack(">QQ", body[:16])
            d["key"] = body[16 : 16 + kl].decode()
            d["value"] = body[16 + kl + 1 : 16 + kl + 1 + vl]
        out.append(d)
        off += 16 + nbf
    return out


def build_hashtree_descriptor(d):
    """Serialise a hashtree descriptor dict (as produced by parse_descriptors)."""
    name = d["name"].encode()
    body = struct.pack(
        HT_FMT, d["dm_verity_version"], d["image_size"], d["tree_offset"], d["tree_size"],
        d["data_block_size"], d["hash_block_size"], d["fec_num_roots"], d["fec_offset"],
        d["fec_size"], d["hash_algorithm"].encode(), len(name), len(d["salt"]),
        len(d["root_digest"]), d["flags"], d["reserved"],
    ) + name + d["salt"] + d["root_digest"]
    body += b"\0" * (-len(body) % 8)
    return struct.pack(">QQ", TAG_HASHTREE, len(body)) + body


def parse_footer(image_tail64):
    magic, vmaj, vmin, orig, off, size, _ = struct.unpack(FOOTER_FMT, image_tail64)
    if magic != b"AVBf":
        return None
    return {"ver": (vmaj, vmin), "original_image_size": orig, "vbmeta_offset": off, "vbmeta_size": size}


def decode_avb_pubkey(blob):
    bits, n0inv = struct.unpack(">LL", blob[:8])
    nb = bits // 8
    n = int.from_bytes(blob[8 : 8 + nb], "big")
    return bits, n, n0inv


def encode_avb_pubkey(n, bits):
    nb = bits // 8
    n0inv = (1 << 32) - pow(n, -1, 1 << 32)
    rr = pow(2, 2 * bits, n)
    return struct.pack(">LL", bits, n0inv) + n.to_bytes(nb, "big") + rr.to_bytes(nb, "big")


def pkcs1_pad(hname, digest, klen):
    t = DIGESTINFO[hname] + digest
    return b"\x00\x01" + b"\xff" * (klen - len(t) - 3) + b"\x00" + t


def load_private_key(pem_path):
    """Return (n, d, bits) from an RSA PEM using `openssl rsa -text`."""
    txt = subprocess.run(
        ["openssl", "rsa", "-in", pem_path, "-noout", "-text"],
        check=True, capture_output=True, text=True,
    ).stdout
    vals, cur = {}, None
    for line in txt.splitlines():
        if line and not line.startswith(" "):
            cur = line.split(":")[0].strip()
            vals[cur] = ""
        elif cur:
            vals[cur] += line.strip().replace(":", "")
    n = int(vals["modulus"], 16)
    d = int(vals["privateExponent"], 16)
    bits = n.bit_length()
    assert pow(pow(0x1234567, 65537, n), d, n) == 0x1234567, "key self-test failed"
    return n, d, bits


def sign_vbmeta(header, aux, key):
    """Return a complete vbmeta blob for the given 256-byte header and aux block.

    The header's algorithm and auth-block layout are kept; only the hash and
    signature bytes in the auth block are produced. RSA PKCS#1 v1.5 is
    deterministic, so identical inputs give an identical blob.
    """
    n, d, bits = key
    h = dict(zip(HDR_FIELDS, struct.unpack(HDR_FMT, header)))
    name, hname, hlen, slen = ALGS[h["algorithm"]]
    assert hname and bits // 8 == slen and h["hash_size"] == hlen and h["sig_size"] == slen
    assert h["aux_size"] == len(aux)
    digest = hashlib.new(hname, header + aux).digest()
    sig = pow(int.from_bytes(pkcs1_pad(hname, digest, slen), "big"), d, n).to_bytes(slen, "big")
    auth = bytearray(h["auth_size"])
    auth[h["hash_offset"] : h["hash_offset"] + hlen] = digest
    auth[h["sig_offset"] : h["sig_offset"] + slen] = sig
    return header + bytes(auth) + aux


def rebuild_vbmeta(vb, descriptors=None, public_key=None, key=None):
    """Return a new vbmeta blob from `vb` with replaced descriptors and/or public key.

    descriptors: {index: new_raw_bytes}. Every replacement must be the same
    length as what it replaces, so no offset or size field in the header moves
    and the header is reused byte for byte. Signed with `key` unless the blob
    is unsigned (algorithm NONE).
    """
    raws = [d["raw"] for d in vb.descriptors]
    for i, raw in (descriptors or {}).items():
        if len(raw) != len(raws[i]):
            raise ValueError("descriptor %d length changed; refusing" % i)
        raws[i] = raw
    desc = b"".join(raws)
    aux = bytearray(vb.aux)
    o = vb.h["desc_offset"]
    aux[o : o + len(desc)] = desc
    if public_key is not None:
        if len(public_key) != vb.h["pk_size"]:
            raise ValueError("public key length changed; refusing")
        o = vb.h["pk_offset"]
        aux[o : o + len(public_key)] = public_key
    aux = bytes(aux)
    assert len(aux) == len(vb.aux)
    if vb.h["algorithm"] == 0:
        return vb.header + vb.auth + aux
    return sign_vbmeta(vb.header, aux, key)


def describe(vb):
    h = vb.h
    lines = [
        "  vbmeta size %d (hdr 256 + auth %d + aux %d), algorithm %s, flags %d, rollback_index %d, "
        "rollback_location %d, release %r" % (vb.size, h["auth_size"], h["aux_size"], vb.alg()[0],
                                              h["flags"], h["rollback_index"],
                                              h["rollback_index_location"], vb.release)
    ]
    if vb.public_key:
        lines.append("  public key: %d bytes, sha256 %s, modulus %s..." % (
            len(vb.public_key), hashlib.sha256(vb.public_key).hexdigest(),
            vb.public_key[8:16].hex().upper()))
    for i, d in enumerate(vb.descriptors):
        t = d["type"]
        if t == "hashtree":
            lines.append(
                "  [%d] hashtree %s: image_size %d, tree_offset %d, tree_size %d, blocks %d/%d, "
                "alg %s, fec_roots %d fec_offset %d fec_size %d, flags %d\n        salt %s\n        root %s"
                % (i, d["name"], d["image_size"], d["tree_offset"], d["tree_size"], d["data_block_size"],
                   d["hash_block_size"], d["hash_algorithm"], d["fec_num_roots"], d["fec_offset"],
                   d["fec_size"], d["flags"], d["salt"].hex(), d["root_digest"].hex()))
        elif t == "hash":
            lines.append("  [%d] hash %s: image_size %d, alg %s, flags %d\n        salt %s\n        digest %s" % (
                i, d["name"], d["image_size"], d["hash_algorithm"], d["flags"], d["salt"].hex(), d["digest"].hex()))
        elif t == "chain_partition":
            lines.append("  [%d] chain %s: rollback_location %d, key sha256 %s, modulus %s..." % (
                i, d["name"], d["rollback_index_location"], hashlib.sha256(d["public_key"]).hexdigest(),
                d["public_key"][8:16].hex().upper()))
        elif t == "kernel_cmdline":
            lines.append("  [%d] cmdline flags %d: %s" % (i, d["flags"], d["cmdline"]))
        elif t == "property":
            lines.append("  [%d] property %s = %r" % (i, d["key"], d["value"][:80]))
        else:
            lines.append("  [%d] unknown tag %d (%d bytes)" % (i, d["tag"], len(d["raw"])))
    return "\n".join(lines)
