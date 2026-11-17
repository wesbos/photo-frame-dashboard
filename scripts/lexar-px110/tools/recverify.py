"""Independent checker for a recovery partition image (offline; never talks to the frame).

Shares no code with recbuild.py or avblib.py: it has its own boot-header, cpio, AVB footer, vbmeta,
hash and RSA handling, so a mistake in the builder is not repeated here.

Checks, each reported by name:
    size         the file is exactly the 32 MiB partition size
    boot-header  Android boot image v2, sizes consistent, zero padding
    boot-id      the header's id equals SHA-1 over the parts
    footer       AVB footer at the very end points at a vbmeta blob inside the image
    vbmeta       vbmeta header sane, algorithm SHA256_RSA2048, one hash descriptor named `recovery`
    image-hash   SHA-256(salt + image) equals the digest in the hash descriptor
    vbmeta-hash  SHA-256(vbmeta header + aux block) equals the hash in the auth block
    signature    RSA PKCS#1 v1.5 signature over that hash verifies with the key inside the vbmeta
    key-in-lk    that key's modulus is present inside the backed-up lk.img (the bootloader trusts it)
and, when --stock is given:
    same-kernel, same-dtb, same-recovery-dtbo, same-second, same-header, same-vbmeta-props
    ramdisk      lists every ramdisk entry that was added, removed or changed; with
                 --expect-changed a,b,c the list must be exactly those names

Usage:  python3 -I tools/recverify.py IMAGE [--stock STOCK] [--lk LK] [--expect-changed a,b,c]
Exit status 0 only if every check passes. Last line: "RESULT: PASS" or "RESULT: FAIL (names)".
"""
import argparse
import hashlib
import os
import struct
import sys
import zlib

PART_SIZE = 32 * 1024 * 1024
SHA256_DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import px110conf  # noqa: E402  (file locations only; no parsing, hashing or signing code is shared)

DEF_LK = os.path.join(px110conf.path("BACKUP_DIR") or "BACKUP_DIR-not-set", "lk.img")


class Report:
    def __init__(self):
        self.failed = []

    def check(self, name, ok, detail=""):
        print("%-18s %s%s" % (name, "ok  " if ok else "FAIL", ("  " + detail) if detail else ""))
        if not ok and name not in self.failed:
            self.failed.append(name)
        return ok


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def read_boot(img, limit):
    """Return (parts, header_info, problems) for the boot image in img[:limit]."""
    problems = []
    if img[:8] != b"ANDROID!":
        return None, None, ["no ANDROID! magic"]
    ksz, rsz, ssz, page, ver = u32(img, 8), u32(img, 16), u32(img, 24), u32(img, 36), u32(img, 40)
    dbo_sz = u32(img, 1632)
    dbo_off = struct.unpack_from("<Q", img, 1636)[0]
    hdr_sz = u32(img, 1644)
    dtb_sz = u32(img, 1648)
    if ver != 2:
        problems.append("header version %d" % ver)
    if page != 2048:
        problems.append("page size %d" % page)
    if hdr_sz != 1660:
        problems.append("header size %d" % hdr_sz)
    if page == 0:
        return None, None, problems
    up = lambda n: -(-n // page) * page
    parts, pos = {}, page
    for name, size in (("kernel", ksz), ("ramdisk", rsz), ("second", ssz), ("recovery_dtbo", dbo_sz), ("dtb", dtb_sz)):
        if name == "recovery_dtbo" and dbo_off != pos:
            problems.append("recovery dtbo offset field %d, layout says %d" % (dbo_off, pos))
        parts[name] = img[pos:pos + size]
        if img[pos + size:pos + up(size)].strip(b"\0"):
            problems.append("%s padding not zero" % name)
        pos += up(size)
    if img[1660:page].strip(b"\0"):
        problems.append("header page padding not zero")
    if pos != limit:
        problems.append("boot image ends at %d, footer says the image is %d bytes" % (pos, limit))
    info = {"page": page, "end": pos, "id": img[576:608], "header": img[:1660]}
    return parts, info, problems


def sha1_id(parts):
    h = hashlib.sha1()
    for name in ("kernel", "ramdisk", "second", "recovery_dtbo", "dtb"):
        h.update(parts[name] + struct.pack("<I", len(parts[name])))
    return h.digest().ljust(32, b"\0")


def read_cpio(gz):
    """gzip'd newc archive -> {name: (metadata tuple, data)}; raises on anything malformed."""
    raw = zlib.decompress(gz, 31)
    out, pos = {}, 0
    order = []
    while True:
        if raw[pos:pos + 6] != b"070701":
            raise ValueError("bad cpio magic at %d" % pos)
        f = [int(raw[pos + 6 + 8 * i:pos + 14 + 8 * i], 16) for i in range(13)]
        nlen, flen = f[11], f[6]
        name = raw[pos + 110:pos + 110 + nlen - 1].decode()
        dpos = (pos + 110 + nlen + 3) // 4 * 4
        data = raw[dpos:dpos + flen]
        pos = (dpos + flen + 3) // 4 * 4
        if name == "TRAILER!!!":
            break
        if name in out:
            raise ValueError("duplicate cpio entry %s" % name)
        # metadata compared: mode, uid, gid, nlink, mtime, dev major/minor, rdev major/minor
        out[name] = ((f[1], f[2], f[3], f[4], f[5], f[7], f[8], f[9], f[10]), data)
        order.append(name)
    if raw[pos:].strip(b"\0"):
        raise ValueError("data after cpio trailer")
    return out, order


def read_footer(img):
    magic, vmaj, vmin, orig, off, size = struct.unpack_from(">4sLLQQQ", img, len(img) - 64)
    return {"magic": magic, "ver": (vmaj, vmin), "orig": orig, "off": off, "size": size,
            "reserved_zero": not img[-28:].strip(b"\0")}


def read_vbmeta(blob):
    """Own parser for the vbmeta blob. Returns a dict or raises ValueError."""
    if blob[:4] != b"AVB0":
        raise ValueError("no AVB0 magic")
    (auth_sz, aux_sz, alg, hash_off, hash_sz, sig_off, sig_sz, pk_off, pk_sz, _pkmd_off, pkmd_sz,
     desc_off, desc_sz, rollback, flags) = struct.unpack_from(">QQLQQQQQQQQQQQL", blob, 12)
    if 256 + auth_sz + aux_sz != len(blob):
        raise ValueError("vbmeta sizes (256+%d+%d) do not add up to %d" % (auth_sz, aux_sz, len(blob)))
    auth, aux = blob[256:256 + auth_sz], blob[256 + auth_sz:]
    descs, pos = [], 0
    dbytes = aux[desc_off:desc_off + desc_sz]
    while pos < len(dbytes):
        tag, nbytes = struct.unpack_from(">QQ", dbytes, pos)
        body = dbytes[pos + 16:pos + 16 + nbytes]
        if tag == 2:      # hash descriptor
            image_size, halg, nlen, slen, dlen, dflags = struct.unpack_from(">Q32sLLLL", body, 0)
            p = 8 + 32 + 16 + 60
            descs.append({"kind": "hash", "image_size": image_size, "alg": halg.rstrip(b"\0").decode(),
                          "name": body[p:p + nlen].decode(), "salt": body[p + nlen:p + nlen + slen],
                          "digest": body[p + nlen + slen:p + nlen + slen + dlen], "flags": dflags})
        elif tag == 0:    # property descriptor
            klen, vlen = struct.unpack_from(">QQ", body, 0)
            descs.append({"kind": "property", "key": body[16:16 + klen].decode(),
                          "value": body[16 + klen + 1:16 + klen + 1 + vlen]})
        else:
            descs.append({"kind": "other", "tag": tag})
        pos += 16 + nbytes
    return {"alg": alg, "signed": blob[:256] + aux, "hash": auth[hash_off:hash_off + hash_sz],
            "sig": auth[sig_off:sig_off + sig_sz], "pubkey": aux[pk_off:pk_off + pk_sz],
            "pkmd_size": pkmd_sz, "rollback": rollback, "flags": flags, "descs": descs}


def rsa_ok(pubkey, sig, digest):
    """Verify PKCS#1 v1.5 / SHA-256 with an AVB-format public key. Also checks the key's helper fields."""
    bits, n0inv = struct.unpack_from(">LL", pubkey, 0)
    nb = bits // 8
    if bits != 2048 or len(pubkey) != 8 + 2 * nb or len(sig) != nb:
        return False, None, "key is not RSA-2048 in AVB format"
    n = int.from_bytes(pubkey[8:8 + nb], "big")
    rr = int.from_bytes(pubkey[8 + nb:], "big")
    if n % 2 == 0 or (n * n0inv + 1) % (1 << 32) != 0 or rr != pow(2, 2 * bits, n):
        return False, n, "key helper fields (n0inv, rr) do not belong to the modulus"
    em = pow(int.from_bytes(sig, "big"), 65537, n).to_bytes(nb, "big")
    want = b"\x00\x01" + b"\xff" * (nb - 3 - len(SHA256_DIGESTINFO) - 32) + b"\x00" + SHA256_DIGESTINFO + digest
    return em == want, n, ""


def main():
    ap = argparse.ArgumentParser(description="Independent checker for a recovery partition image")
    ap.add_argument("image")
    ap.add_argument("--stock", help="stock recovery.img to compare kernel, dtb, dtbo and ramdisk against")
    ap.add_argument("--lk", default=DEF_LK, help="backed-up lk.img that must contain the signing key")
    ap.add_argument("--expect-changed", help="comma-separated ramdisk names that must be exactly the changed set")
    a = ap.parse_args()
    r = Report()
    img = open(a.image, "rb").read()
    print("image: %s  (%d bytes, sha256 %s)" % (a.image, len(img), hashlib.sha256(img).hexdigest()))

    r.check("size", len(img) == PART_SIZE, "%d bytes" % len(img))
    if len(img) < 4096:
        print("RESULT: FAIL (%s)" % ",".join(r.failed))
        return 1

    ft = read_footer(img)
    foot_ok = (ft["magic"] == b"AVBf" and ft["ver"] == (1, 0) and ft["reserved_zero"]
               and 0 < ft["orig"] <= ft["off"] and ft["off"] % 4096 == 0
               and ft["off"] + ft["size"] <= len(img) - 64 and 256 < ft["size"] < 65536)
    r.check("footer", foot_ok, "image %d bytes, vbmeta at %d, %d bytes" % (ft["orig"], ft["off"], ft["size"]))
    if foot_ok:
        gaps_zero = not img[ft["orig"]:ft["off"]].strip(b"\0") and not img[ft["off"] + ft["size"]:-64].strip(b"\0")
        r.check("footer", gaps_zero, "space around the vbmeta blob is all zero" if gaps_zero else "non-zero bytes around the vbmeta blob")

    limit = ft["orig"] if foot_ok else len(img)
    parts, info, problems = read_boot(img, limit)
    r.check("boot-header", parts is not None and not problems, "; ".join(problems) or
            "kernel %d, ramdisk %d, recovery dtbo %d, dtb %d" % tuple(len(parts[k]) for k in ("kernel", "ramdisk", "recovery_dtbo", "dtb")))
    if parts is not None:
        r.check("boot-id", sha1_id(parts) == info["id"])

    vb = None
    if foot_ok:
        try:
            vb = read_vbmeta(img[ft["off"]:ft["off"] + ft["size"]])
        except (ValueError, struct.error) as e:
            r.check("vbmeta", False, str(e))
    else:
        for name in ("vbmeta", "image-hash", "vbmeta-hash", "signature", "key-in-lk"):
            r.check(name, False, "no usable footer")
    if vb is not None:
        hashes = [d for d in vb["descs"] if d["kind"] == "hash"]
        others = [d for d in vb["descs"] if d["kind"] == "other"]
        vb_ok = (vb["alg"] == 1 and len(hashes) == 1 and not others and hashes[0]["name"] == "recovery"
                 and hashes[0]["alg"] == "sha256" and hashes[0]["image_size"] == ft["orig"]
                 and vb["flags"] == 0 and vb["pkmd_size"] == 0)
        r.check("vbmeta", vb_ok, "algorithm %d, %d hash descriptor(s), %d property descriptor(s), flags %d, rollback index %d" % (
            vb["alg"], len(hashes), len(vb["descs"]) - len(hashes) - len(others), vb["flags"], vb["rollback"]))
        if hashes:
            h = hashes[0]
            calc = hashlib.sha256(h["salt"] + img[:h["image_size"]]).digest()
            r.check("image-hash", calc == h["digest"], "sha256(salt + first %d bytes) = %s" % (h["image_size"], calc.hex()))
        else:
            r.check("image-hash", False, "no hash descriptor")
        digest = hashlib.sha256(vb["signed"]).digest()
        r.check("vbmeta-hash", digest == vb["hash"])
        # The signature is checked over the hash we computed ourselves, not the stored one.
        ok, n, why = rsa_ok(vb["pubkey"], vb["sig"], digest)
        r.check("signature", ok, why)
        try:
            lk = open(a.lk, "rb").read()
        except OSError as e:
            lk, n = b"", None
            r.check("key-in-lk", False, "lk.img could not be read (%s); set BACKUP_DIR or give --lk" % e)
        if n is None:
            r.check("key-in-lk", False, "no usable key")
        else:
            mod = n.to_bytes(256, "big")
            at = lk.find(mod)
            r.check("key-in-lk", at >= 0, ("modulus %s... found in lk.img at offset %d" % (mod[:8].hex().upper(), at)) if at >= 0
                    else "modulus %s... is NOT in lk.img: the bootloader will not trust this image" % mod[:8].hex().upper())

    if a.stock:
        st = open(a.stock, "rb").read()
        sft = read_footer(st)
        sparts, sinfo, sproblems = read_boot(st, sft["orig"])
        if sparts is None or sproblems or parts is None:
            r.check("stock-compare", False, "cannot read the stock image or this image for comparison")
        else:
            for name in ("kernel", "dtb", "recovery_dtbo", "second"):
                r.check("same-" + name.replace("_", "-"), parts[name] == sparts[name],
                        "%d bytes, sha256 %s" % (len(parts[name]), hashlib.sha256(parts[name]).hexdigest()[:16]))
            # header: everything equal except ramdisk size (16:20), recovery dtbo offset (1636:1644) and id (576:608)
            mask = lambda h: h[:16] + h[20:576] + h[608:1636] + h[1644:]
            r.check("same-header", mask(info["header"]) == mask(sinfo["header"]),
                    "all header fields equal except ramdisk size, recovery dtbo offset and id")
            if vb is not None:
                svb = read_vbmeta(st[sft["off"]:sft["off"] + sft["size"]])
                props = lambda v: [(d["key"], d["value"]) for d in v["descs"] if d["kind"] == "property"]
                salts = lambda v: [d["salt"] for d in v["descs"] if d["kind"] == "hash"]
                r.check("same-vbmeta-props", props(vb) == props(svb) and salts(vb) == salts(svb)
                        and vb["rollback"] == svb["rollback"], "property descriptors, salt and rollback index as stock")
            try:
                new, _ = read_cpio(parts["ramdisk"])
                old, _ = read_cpio(sparts["ramdisk"])
            except (ValueError, zlib.error) as e:
                r.check("ramdisk", False, "cannot read a ramdisk: %s" % e)
            else:
                diff = []
                for name in sorted(set(new) | set(old)):
                    if name not in old:
                        diff.append(name)
                        print("    ramdisk added:   %s (%d bytes, mode %o, uid %d, gid %d)" % (
                            name, len(new[name][1]), new[name][0][0], new[name][0][1], new[name][0][2]))
                    elif name not in new:
                        diff.append(name)
                        print("    ramdisk removed: %s" % name)
                    elif new[name] != old[name]:
                        diff.append(name)
                        what = []
                        if new[name][0] != old[name][0]:
                            what.append("metadata")
                        if new[name][1] != old[name][1]:
                            what.append("content %d -> %d bytes" % (len(old[name][1]), len(new[name][1])))
                        print("    ramdisk changed: %s (%s)" % (name, ", ".join(what)))
                print("RAMDISK-DIFF: %s" % (",".join(diff) or "none"))
                if a.expect_changed is not None:
                    want = sorted(x for x in a.expect_changed.split(",") if x)
                    r.check("ramdisk", diff == want, "%d entries, %d differ from stock; expected exactly: %s" % (
                        len(new), len(diff), ",".join(want) or "none"))
                else:
                    r.check("ramdisk", True, "%d entries, %d differ from stock" % (len(new), len(diff)))

    if r.failed:
        print("RESULT: FAIL (%s)" % ",".join(r.failed))
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
