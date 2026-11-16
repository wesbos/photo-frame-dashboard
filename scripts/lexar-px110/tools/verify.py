#!/usr/bin/env python3
"""Independent offline checker for the Lexar PX-110 verified-boot chain.

It shares no code with the build tools (standard library only, own parsers).

  verify.py --lk lk.img --vbmeta vbmeta.img --vbmeta-system vbmeta_system.img
            (--product product.img | --super super.img)
            [--vbmeta-vendor vbmeta_vendor.img --boot boot.img [--expect-digest HEX]]
            [--extract /path/in/product OUTFILE] [--no-list]

Checks, in the order the frame trusts things:
  1. the public key inside vbmeta is the key embedded in lk.img
  2. vbmeta's SHA-256 and RSA signature verify with that key
  3. vbmeta's chain descriptor for vbmeta_system names the key that signed
     vbmeta_system, and vbmeta_system's hash and signature verify
     (same for vbmeta_vendor and boot when given; with all four, the combined
     digest that the bootloader reports as ro.boot.vbmeta.digest is printed)
  4. the product hashtree descriptor in vbmeta_system matches the product
     image: root digest recomputed from the filesystem bytes, stored tree
     bytes, FEC parity (Reed-Solomon syndromes), AVB footer copy
  5. the product ext4 filesystem is listed (mode, owner, SELinux label, sha256)
Exit status 0 only if every check passes.
"""
import argparse
import hashlib
import struct
import sys

FAILS = []


def ok(msg):
    print("PASS  " + msg)


def fail(msg):
    print("FAIL  " + msg)
    FAILS.append(msg)


def check(cond, msg):
    (ok if cond else fail)(msg)
    return cond


# ---------------------------------------------------------------- AVB

def u32(b, o): return int.from_bytes(b[o:o + 4], "big")
def u64(b, o): return int.from_bytes(b[o:o + 8], "big")


SHA256_DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")


class VB:
    def __init__(self, blob, label):
        self.label = label
        if blob[:4] != b"AVB0":
            raise ValueError("%s: no AVB0 magic" % label)
        self.auth_size, self.aux_size, self.alg = u64(blob, 12), u64(blob, 20), u32(blob, 28)
        self.size = 256 + self.auth_size + self.aux_size
        self.blob = blob[:self.size]
        self.header = self.blob[:256]
        auth = self.blob[256:256 + self.auth_size]
        self.aux = self.blob[256 + self.auth_size:]
        ho, hs, so, ss, po, ps = (u64(blob, 32 + 8 * i) for i in range(6))
        do, ds = u64(blob, 96), u64(blob, 104)
        self.hash, self.sig = auth[ho:ho + hs], auth[so:so + ss]
        self.pubkey = self.aux[po:po + ps]
        self.rollback_index, self.flags = u64(blob, 112), u32(blob, 120)
        self.release = blob[128:176].rstrip(b"\0").decode()
        self.descs = []
        d = self.aux[do:do + ds]
        o = 0
        while o < len(d):
            tag, n = u64(d, o), u64(d, o + 8)
            self.descs.append((tag, d[o + 16:o + 16 + n], d[o:o + 16 + n]))
            o += 16 + n

    def verify(self, expected_pubkey=None):
        """Return None if good, else a reason string."""
        if self.alg != 1:
            return "algorithm type %d is not SHA256_RSA2048" % self.alg
        digest = hashlib.sha256(self.header + self.aux).digest()
        if digest != self.hash:
            return "stored SHA-256 does not match header+aux"
        if expected_pubkey is not None and self.pubkey != expected_pubkey:
            return "signed by a different key than the one expected"
        if len(self.pubkey) != 8 + 512 or u32(self.pubkey, 0) != 2048 or len(self.sig) != 256:
            return "unexpected key or signature size"
        n = int.from_bytes(self.pubkey[8:264], "big")
        em = pow(int.from_bytes(self.sig, "big"), 65537, n).to_bytes(256, "big")
        want = b"\x00\x01" + b"\xff" * (256 - 3 - 19 - 32) + b"\x00" + SHA256_DIGESTINFO + digest
        if em != want:
            return "RSA signature does not verify"
        return None

    def chains(self):
        out = {}
        for tag, body, _ in self.descs:
            if tag == 4:
                loc, nl, kl = u32(body, 0), u32(body, 4), u32(body, 8)
                name = body[76:76 + nl].decode()
                out[name] = (loc, body[76 + nl:76 + nl + kl])
        return out

    def hashtrees(self):
        out = {}
        for tag, body, raw in self.descs:
            if tag == 1:
                f = dict(zip(
                    "ver image_size tree_offset tree_size dblk hblk fec_roots fec_offset fec_size".split(),
                    struct.unpack(">LQQQLLLQQ", body[:56])))
                f["alg"] = body[56:88].rstrip(b"\0").decode()
                nl, sl, dl, f["flags"] = struct.unpack(">LLLL", body[88:104])
                p = 164
                f["name"] = body[p:p + nl].decode()
                f["salt"] = body[p + nl:p + nl + sl]
                f["root"] = body[p + nl + sl:p + nl + sl + dl]
                f["raw"] = raw
                out[f["name"]] = f
        return out


def read(path):
    with open(path, "rb") as f:
        return f.read()


def footer_vbmeta(img, label):
    """vbmeta blob referenced by the AVB footer at the end of a partition image."""
    ft = img[-64:]
    if ft[:4] != b"AVBf":
        return None, None
    orig, off, size = u64(ft, 12), u64(ft, 20), u64(ft, 28)
    return VB(img[off:off + size], label + " footer"), orig


# ---------------------------------------------------------------- LP (super)

def product_from_super(path, name="product"):
    with open(path, "rb") as f:
        f.seek(4096)
        g = f.read(4096)
        if struct.unpack("<L", g[:4])[0] != 0x616C4467:
            raise ValueError("super: no LP geometry")
        gsize = struct.unpack("<L", g[4:8])[0]
        if hashlib.sha256(g[:8] + bytes(32) + g[40:gsize]).digest() != g[8:40]:
            raise ValueError("super: geometry checksum")
        max_size = struct.unpack("<L", g[40:44])[0]
        f.seek(4096 * 3)
        m = f.read(max_size)
        magic, _, _, hsize = struct.unpack("<LHHL", m[:12])
        if magic != 0x414C5030:
            raise ValueError("super: no LP metadata header")
        tsize = struct.unpack("<L", m[44:48])[0]
        t = m[hsize:hsize + tsize]
        if hashlib.sha256(m[:12] + bytes(32) + m[44:hsize]).digest() != m[12:44] or \
                hashlib.sha256(t).digest() != m[48:80]:
            raise ValueError("super: metadata checksum")
        po, pn, ps, eo, en, es = struct.unpack("<6L", m[80:104])
        for i in range(pn):
            e = t[po + i * ps:po + (i + 1) * ps]
            if e[:36].rstrip(b"\0").decode() == name:
                first, count = struct.unpack("<LL", e[40:48])
                data, ranges = bytearray(), []
                for k in range(first, first + count):
                    ns, ttype, tdata, tsrc = struct.unpack("<QLQL", t[eo + k * es:eo + k * es + 24])
                    if ttype != 0 or tsrc != 0:
                        raise ValueError("super: unsupported extent")
                    f.seek(tdata * 512)
                    data += f.read(ns * 512)
                    ranges.append((tdata * 512, ns * 512))
                return bytes(data), ranges
    raise ValueError("super: no partition " + name)


# ---------------------------------------------------------------- dm-verity

def verity_root(data, salt, block=4096):
    levels = []
    cur = data
    while True:
        mv = memoryview(cur)
        nxt = b"".join(hashlib.sha256(salt + mv[o:o + block]).digest() for o in range(0, len(cur), block))
        if len(cur) == block:
            return nxt, b"".join(reversed(levels))
        nxt += bytes(-len(nxt) % block)
        levels.append(nxt)
        cur = nxt


def fec_syndromes_zero(data, fec, roots, block=4096):
    """True if every RS(255, 255-roots) codeword (AOSP libfec layout, GF(2^8)
    poly 0x11d, generator roots alpha^0..alpha^(roots-1)) has all-zero syndromes."""
    exp, x = [], 1
    for _ in range(255):
        exp.append(x)
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    log = {v: i for i, v in enumerate(exp)}
    rsn = 255 - roots
    rounds = -(-(len(data) // block) // rsn)
    n = rounds * block
    if len(fec) != n * roots:
        return False
    cols = [data[j * n:(j + 1) * n].ljust(n, b"\0") for j in range(rsn)]
    cols += [fec[k::roots] for k in range(roots)]          # codeword positions 0..254
    for r in range(roots):
        acc = 0
        for pos, col in enumerate(cols):
            power = (r * (254 - pos)) % 255                 # coefficient of x^(254-pos) at alpha^r
            if power:
                table = bytes(0 if v == 0 else exp[(log[v] + power) % 255] for v in range(256))
                col = col.translate(table)
            acc ^= int.from_bytes(col, "little")
        if acc:
            return False
    return True


# ---------------------------------------------------------------- ext4 (read-only)

class Ext4:
    def __init__(self, img):
        self.img = img
        sb = img[1024:2048]
        if struct.unpack("<H", sb[56:58])[0] != 0xEF53:
            raise ValueError("no ext4 superblock")
        self.inodes, self.blocks, _, self.free_blocks, self.free_inodes, first = struct.unpack("<6L", sb[0:24])
        self.bs = 1024 << struct.unpack("<L", sb[24:28])[0]
        self.ipg = struct.unpack("<L", sb[40:44])[0]
        self.bpg = struct.unpack("<L", sb[32:36])[0]
        self.isize = struct.unpack("<H", sb[88:90])[0]
        self.uuid = sb[104:120].hex()
        self.name = sb[120:136].rstrip(b"\0").decode()
        incompat = struct.unpack("<L", sb[96:100])[0]
        self.dsize = struct.unpack("<H", sb[254:256])[0] if incompat & 0x80 else 32
        self.gdt = (first + 1) * self.bs

    def inode(self, ino):
        g, idx = divmod(ino - 1, self.ipg)
        gd = self.img[self.gdt + g * self.dsize:self.gdt + (g + 1) * self.dsize]
        table = struct.unpack("<L", gd[8:12])[0]
        o = table * self.bs + idx * self.isize
        return self.img[o:o + self.isize]

    def extents(self, node):
        magic, entries, _, depth = struct.unpack("<HHHH", node[:8])
        if magic != 0xF30A:
            raise ValueError("inode does not use extents")
        for i in range(entries):
            e = node[12 + 12 * i:24 + 12 * i]
            if depth == 0:
                lblk, ln, hi, lo = struct.unpack("<LHHL", e)
                yield lblk, ln if ln <= 32768 else ln - 32768, (hi << 32) | lo
            else:
                _, lo, hi = struct.unpack("<LLH", e[:10])
                blk = (hi << 32) | lo
                yield from self.extents(self.img[blk * self.bs:(blk + 1) * self.bs])

    def data(self, raw):
        size = struct.unpack("<L", raw[4:8])[0] | (struct.unpack("<L", raw[108:112])[0] << 32)
        mode = struct.unpack("<H", raw[0:2])[0]
        if (mode & 0xF000) == 0xA000 and size < 60:
            return raw[40:40 + size]
        if not struct.unpack("<L", raw[32:36])[0] & 0x80000:
            raise ValueError("non-extent inode")
        out = bytearray(-(-size // self.bs) * self.bs)
        for lblk, ln, pblk in self.extents(raw[40:100]):
            out[lblk * self.bs:(lblk + ln) * self.bs] = self.img[pblk * self.bs:(pblk + ln) * self.bs]
        return bytes(out[:size])

    def xattrs(self, raw):
        if struct.unpack("<L", raw[104:108])[0]:
            return {"(external xattr block)": b"?"}
        extra = struct.unpack("<H", raw[128:130])[0]
        o = 128 + extra
        out = {}
        if raw[o:o + 4] != b"\x00\x00\x02\xea":
            return out
        base = o + 4
        p = base
        prefixes = {1: "user.", 4: "trusted.", 6: "security.", 7: "system."}
        while p + 16 <= len(raw) and raw[p:p + 4] != b"\0\0\0\0":
            nl, idx, voff = raw[p], raw[p + 1], struct.unpack("<H", raw[p + 2:p + 4])[0]
            vsize = struct.unpack("<L", raw[p + 8:p + 12])[0]
            name = prefixes.get(idx, "?%d." % idx) + raw[p + 16:p + 16 + nl].decode()
            out[name] = raw[base + voff:base + voff + vsize]
            p += (16 + nl + 3) & ~3
        return out

    def walk(self, ino=2, path=""):
        raw = self.inode(ino)
        mode, uid = struct.unpack("<HH", raw[0:4])
        gid = struct.unpack("<H", raw[24:26])[0]
        size = struct.unpack("<L", raw[4:8])[0]
        yield path or "/", ino, mode, uid, gid, size, raw
        if (mode & 0xF000) != 0x4000:
            return
        d = self.data(raw)
        entries = []
        for b in range(0, len(d), self.bs):
            o = b
            while o < b + self.bs:
                child, rec, nl = struct.unpack("<LHB", d[o:o + 7])
                if rec < 8:
                    break
                name = d[o + 8:o + 8 + nl].decode()
                if child and name not in (".", ".."):
                    entries.append((name, child))
                o += rec
        for name, child in sorted(entries):
            yield from self.walk(child, path + "/" + name)

    def lookup(self, path):
        for p, ino, mode, uid, gid, size, raw in self.walk():
            if p == path:
                return raw
        return None


def list_fs(fs):
    print("\nproduct filesystem: label %r, uuid %s, %d blocks of %d, free blocks %d (%d KB), free inodes %d of %d" % (
        fs.name, fs.uuid, fs.blocks, fs.bs, fs.free_blocks, fs.free_blocks * fs.bs // 1024, fs.free_inodes, fs.inodes))
    print("%-7s %4s %4s %9s  %-28s %-16s %s" % ("mode", "uid", "gid", "size", "selinux", "sha256[:16]", "path"))
    n = 0
    for path, ino, mode, uid, gid, size, raw in fs.walk():
        n += 1
        label = fs.xattrs(raw).get("security.selinux", b"(none)").rstrip(b"\0").decode()
        kind = {0x4000: "d", 0x8000: "-", 0xA000: "l"}.get(mode & 0xF000, "?")
        digest = hashlib.sha256(fs.data(raw)).hexdigest()[:16] if kind == "-" else ""
        print("%s%04o %5d %4d %9d  %-28s %-16s %s" % (kind, mode & 0o7777, uid, gid, size, label, digest, path))
    print("%d entries" % n)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lk", required=True)
    ap.add_argument("--vbmeta", required=True)
    ap.add_argument("--vbmeta-system", required=True)
    ap.add_argument("--vbmeta-vendor")
    ap.add_argument("--boot")
    ap.add_argument("--product")
    ap.add_argument("--super")
    ap.add_argument("--expect-digest")
    ap.add_argument("--extract", nargs=2, metavar=("PATH", "OUTFILE"))
    ap.add_argument("--no-list", action="store_true")
    a = ap.parse_args()
    if bool(a.product) == bool(a.super):
        ap.error("give exactly one of --product or --super")

    # 1 + 2: vbmeta against the key in lk
    lk = read(a.lk)
    vb = VB(read(a.vbmeta), "vbmeta")
    modulus = vb.pubkey[8:264]
    print("vbmeta: %d bytes, flags %d, rollback %d, release %r, key modulus %s..." % (
        vb.size, vb.flags, vb.rollback_index, vb.release, modulus[:8].hex().upper()))
    pos = lk.find(modulus)
    check(len(modulus) == 256 and pos >= 0,
          "vbmeta's public key modulus is embedded in lk.img" + (" (offset %d)" % pos if pos >= 0 else ""))
    why = vb.verify()
    check(why is None, "vbmeta hash and RSA signature verify with that key" + ("" if why is None else ": " + why))

    # 3: chain
    chains = vb.chains()
    chained = {}
    for name, path in (("vbmeta_system", a.vbmeta_system), ("vbmeta_vendor", a.vbmeta_vendor), ("boot", a.boot)):
        if not path:
            continue
        if not check(name in chains, "vbmeta has a chain descriptor for %s" % name):
            continue
        loc, key = chains[name]
        img = read(path)
        try:
            c = footer_vbmeta(img, name)[0] if name == "boot" else VB(img, name)
            if c is None:
                raise ValueError("no AVB footer")
        except ValueError as e:
            fail("%s: %s" % (name, e))
            continue
        why = c.verify(expected_pubkey=key)
        check(why is None, "%s verifies with the key named in vbmeta's chain descriptor (modulus %s..., rollback "
              "location %d)%s" % (name, key[8:16].hex().upper(), loc, "" if why is None else ": " + why))
        check(c.flags == 0, "%s has zero flags (required for a chained vbmeta)" % name)
        chained[name] = c
    if all(n in chained for n in ("vbmeta_system", "vbmeta_vendor", "boot")):
        order = [n for n in chains if n in chained]     # descriptor order, as libavb loads them
        h = hashlib.sha256(vb.blob)
        total = vb.size
        for n in order:
            h.update(chained[n].blob)
            total += chained[n].size
        print("combined vbmeta digest (ro.boot.vbmeta.digest): %s, size %d" % (h.hexdigest(), total))
        if a.expect_digest:
            check(h.hexdigest() == a.expect_digest.lower(), "combined digest equals the expected value")

    # 4: product
    if "vbmeta_system" not in chained:
        fail("cannot check product without a parsed vbmeta_system")
        return finish()
    hts = chained["vbmeta_system"].hashtrees()
    if not check("product" in hts, "vbmeta_system has a hashtree descriptor for product"):
        return finish()
    ht = hts["product"]
    if a.super:
        product, ranges = product_from_super(a.super)
        print("product read from super: " + ", ".join("offset %d length %d" % r for r in ranges))
    else:
        product = read(a.product)
    print("product: partition %d bytes; descriptor image_size %d, tree %d+%d, fec %d+%d roots %d, %s, blocks %d/%d" % (
        len(product), ht["image_size"], ht["tree_offset"], ht["tree_size"], ht["fec_offset"], ht["fec_size"],
        ht["fec_roots"], ht["alg"], ht["dblk"], ht["hblk"]))
    sane = (ht["alg"] == "sha256" and ht["dblk"] == ht["hblk"] == 4096 and ht["ver"] == 1
            and ht["image_size"] % 4096 == 0 and ht["tree_offset"] == ht["image_size"]
            and ht["fec_offset"] + ht["fec_size"] <= len(product))
    if not check(sane, "descriptor geometry is sane and fits inside the partition"):
        return finish()
    data = product[:ht["image_size"]]
    root, tree = verity_root(data, ht["salt"])
    check(root == ht["root"], "product root digest recomputed from the image equals the descriptor (%s)" % root.hex())
    stored_tree = product[ht["tree_offset"]:ht["tree_offset"] + ht["tree_size"]]
    check(tree == stored_tree, "hashtree stored in the partition equals the recomputed tree")
    if ht["fec_roots"]:
        fec = product[ht["fec_offset"]:ht["fec_offset"] + ht["fec_size"]]
        check(fec_syndromes_zero(product[:ht["fec_offset"]], fec, ht["fec_roots"]),
              "FEC parity is consistent with data+tree (all Reed-Solomon syndromes zero)")
    fvb, orig = footer_vbmeta(product, "product")
    if check(fvb is not None, "product partition ends with an AVB footer"):
        fht = fvb.hashtrees().get("product")
        check(fht is not None and fht["raw"] == ht["raw"] and orig == ht["image_size"],
              "footer's copy of the hashtree descriptor equals the one in vbmeta_system")

    # 5: filesystem
    try:
        fs = Ext4(data)
        check(fs.blocks * fs.bs == ht["image_size"], "ext4 filesystem size equals the verified image size")
        if not a.no_list:
            list_fs(fs)
        if a.extract:
            raw = fs.lookup(a.extract[0])
            if check(raw is not None, "found %s in product" % a.extract[0]):
                with open(a.extract[1], "wb") as f:
                    f.write(fs.data(raw))
    except (ValueError, struct.error, IndexError) as e:
        fail("product filesystem could not be read: %r" % e)
    return finish()


def finish():
    if FAILS:
        print("\nRESULT: FAIL (%d check%s failed)" % (len(FAILS), "" if len(FAILS) == 1 else "s"))
        return 1
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
