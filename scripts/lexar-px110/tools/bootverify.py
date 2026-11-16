"""Independent checker for a `boot` partition image (offline; never talks to the frame).

Shares no code with bootbuild.py or avblib.py: it has its own boot-header, cpio, ELF, AVB footer,
vbmeta, hash and RSA handling, so a mistake in the builder is not repeated here.

Checks, each reported by name:
    size          the file is exactly the 32 MiB partition size
    footer        AVB footer at the very end points at a vbmeta blob inside the image; zero around it
    boot-header   Android boot image v2, sizes consistent, zero padding, no second stage, no recovery dtbo
    boot-id       the header's id equals SHA-1 over the parts
    vbmeta        vbmeta header sane, algorithm SHA256_RSA2048, one hash descriptor named `boot`
    image-hash    SHA-256(salt + image) equals the digest in the hash descriptor
    vbmeta-hash   SHA-256(vbmeta header + aux block) equals the hash in the auth block
    signature     RSA PKCS#1 v1.5 signature over that hash verifies with the key inside the vbmeta
    chain-key     that key is, byte for byte, the key the `boot` chain entry names in every vbmeta given
                  (by default the stock one in BACKUP_DIR and the one build.py made, BUILD_DIR/out/vbmeta.img),
                  and each of those vbmeta images is itself correctly signed
and, when --stock is given:
    same-kernel, same-dtb, same-second, same-recovery-dtbo, same-cmdline, same-header, same-vbmeta-props
    ramdisk       lists every ramdisk entry that was added, removed or changed; with
                  --expect-changed a,b,c the list must be exactly those names
and, when the ramdisk has an init.real (our wrapper build):
    init-real     init.real is the stock init, byte for byte (--real stock), or differs from it in
                  exactly the ten bytes of the restart word, bootloader -> recovery (--real recovery)
    wrapper-elf   the new init is a small static 32-bit ARM program the kernel can load
    wrapper-file  with --wrapper FILE: the new init is exactly that file

Usage:  python3 -I tools/bootverify.py IMAGE [--stock STOCK] [--vbmeta V ...]
                                              [--expect-changed a,b,c] [--real stock|recovery] [--wrapper FILE]
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

DEF_VBMETA = [os.path.join(px110conf.path("BACKUP_DIR") or "BACKUP_DIR-not-set", "vbmeta.img"),
              px110conf.build_dir("out", "vbmeta.img")]
WORD_AT = 0x7740                       # where the restart word sits in the stock init
WORD_OLD, WORD_NEW = b"bootloader", b"recovery\0\0"


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
        return None, None, problems
    if hdr_sz != 1660:
        problems.append("header size %d" % hdr_sz)
    if ssz or dbo_sz or dbo_off:
        problems.append("second stage %d bytes, recovery dtbo %d bytes at %d (stock has none)" % (ssz, dbo_sz, dbo_off))
    up = lambda n: -(-n // page) * page
    parts, pos = {}, page
    for name, size in (("kernel", ksz), ("ramdisk", rsz), ("second", ssz), ("recovery_dtbo", dbo_sz), ("dtb", dtb_sz)):
        parts[name] = img[pos:pos + size]
        if pos + size > limit:
            problems.append("%s runs past the end of the image" % name)
        if img[pos + size:pos + up(size)].strip(b"\0"):
            problems.append("%s padding not zero" % name)
        pos += up(size)
    if img[1660:page].strip(b"\0"):
        problems.append("header page padding not zero")
    if pos != limit:
        problems.append("boot image ends at %d, footer says the image is %d bytes" % (pos, limit))
    info = {"page": page, "end": pos, "id": img[576:608], "header": img[:1660],
            "cmdline": img[64:576].rstrip(b"\0"), "extra_cmdline": img[608:1632].rstrip(b"\0")}
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
    while True:
        if raw[pos:pos + 6] != b"070701":
            raise ValueError("bad cpio magic at %d" % pos)
        f = [int(raw[pos + 6 + 8 * i:pos + 14 + 8 * i], 16) for i in range(13)]
        nlen, flen = f[11], f[6]
        name = raw[pos + 110:pos + 110 + nlen - 1].decode()
        dpos = (pos + 110 + nlen + 3) // 4 * 4
        data = raw[dpos:dpos + flen]
        if len(data) != flen:
            raise ValueError("cpio entry %s is cut short" % name)
        pos = (dpos + flen + 3) // 4 * 4
        if name == "TRAILER!!!":
            break
        if name in out:
            raise ValueError("duplicate cpio entry %s" % name)
        # metadata compared: mode, uid, gid, nlink, mtime, dev major/minor, rdev major/minor
        out[name] = ((f[1], f[2], f[3], f[4], f[5], f[7], f[8], f[9], f[10]), data)
    if raw[pos:].strip(b"\0"):
        raise ValueError("data after cpio trailer")
    return out


def read_footer(img):
    magic, vmaj, vmin, orig, off, size = struct.unpack_from(">4sLLQQQ", img, len(img) - 64)
    return {"magic": magic, "ver": (vmaj, vmin), "orig": orig, "off": off, "size": size,
            "reserved_zero": not img[-28:].strip(b"\0")}


def read_vbmeta(blob):
    """Own parser for a vbmeta blob (the blob may be followed by padding). Returns a dict or raises ValueError."""
    if blob[:4] != b"AVB0":
        raise ValueError("no AVB0 magic")
    (auth_sz, aux_sz, alg, hash_off, hash_sz, sig_off, sig_sz, pk_off, pk_sz, _pkmd_off, pkmd_sz,
     desc_off, desc_sz, rollback, flags) = struct.unpack_from(">QQLQQQQQQQQQQQL", blob, 12)
    total = 256 + auth_sz + aux_sz
    if total > len(blob) or auth_sz > 65536 or aux_sz > 1048576:
        raise ValueError("vbmeta sizes (256+%d+%d) do not fit in %d bytes" % (auth_sz, aux_sz, len(blob)))
    auth, aux = blob[256:256 + auth_sz], blob[256 + auth_sz:total]
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
        elif tag == 4:    # chain partition descriptor
            loc, nlen, klen = struct.unpack_from(">LLL", body, 0)
            p = 12 + 64
            descs.append({"kind": "chain", "location": loc, "name": body[p:p + nlen].decode(),
                          "pubkey": body[p + nlen:p + nlen + klen]})
        else:
            descs.append({"kind": "other", "tag": tag})
        pos += 16 + nbytes
    return {"alg": alg, "total": total, "signed": blob[:256] + aux, "hash": auth[hash_off:hash_off + hash_sz],
            "sig": auth[sig_off:sig_off + sig_sz], "pubkey": aux[pk_off:pk_off + pk_sz],
            "pkmd_size": pkmd_sz, "rollback": rollback, "flags": flags, "descs": descs}


def rsa_ok(pubkey, sig, digest):
    """Verify PKCS#1 v1.5 / SHA-256 with an AVB-format public key. Also checks the key's helper fields."""
    if len(pubkey) < 8:
        return False, None, "no key"
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


def elf_problems(elf):
    """What would stop the frame's 32-bit ARM kernel from running this as a static program. [] = fine."""
    p = []
    if len(elf) < 52 or elf[:4] != b"\x7fELF":
        return ["not an ELF file"]
    if elf[4:7] != b"\x01\x01\x01":
        p.append("not 32-bit little-endian ELF version 1")
    etype, machine, _ver, entry, phoff, _shoff, flags, _ehsz, phentsz, phnum = struct.unpack_from("<HHIIIIIHHH", elf, 16)
    if etype != 2:
        p.append("type %d, not a fixed-address executable" % etype)
    if machine != 40:
        p.append("machine %d, not ARM" % machine)
    if flags >> 24 != 5:
        p.append("not ARM EABI version 5")
    if flags & 0x400:
        p.append("built for hard-float")
    if entry & 3:
        p.append("entry point %#x is not ARM code on a 4-byte boundary" % entry)
    if phentsz != 32 or not 1 <= phnum <= 16 or phoff + phnum * 32 > len(elf):
        return p + ["program headers unreadable"]
    loads, entry_ok, stack = 0, False, None
    for i in range(phnum):
        typ, off, vaddr, _paddr, filesz, memsz, pflags, align = struct.unpack_from("<8I", elf, phoff + 32 * i)
        if typ in (2, 3):
            p.append("has a dynamic section or asks for an interpreter: not static")
        if typ == 0x6474e551:
            stack = pflags
        if typ != 1:
            continue
        loads += 1
        if off + filesz > len(elf) or filesz > memsz:
            p.append("segment %d runs past the end of the file" % i)
        if align != 4096 or (off - vaddr) % 4096:
            p.append("segment %d is not laid out on 4096-byte pages" % i)
        if vaddr < 0x10000 or vaddr + memsz > 0x1000000:
            p.append("segment %d sits at %#x, outside the plain low range a static program uses" % (i, vaddr))
        if pflags & 1 and pflags & 2:
            p.append("segment %d is both writable and executable" % i)
        if pflags & 1 and vaddr <= entry < vaddr + filesz:
            entry_ok = True
    if not loads:
        p.append("nothing to load")
    if not entry_ok:
        p.append("entry point %#x is not inside an executable segment" % entry)
    if stack is None or stack & 1:
        p.append("stack is not marked non-executable")
    return p


def main():
    ap = argparse.ArgumentParser(description="Independent checker for a boot partition image")
    ap.add_argument("image")
    ap.add_argument("--stock", help="stock boot.img to compare kernel, dtb, command line and ramdisk against")
    ap.add_argument("--vbmeta", action="append", help="vbmeta image whose `boot` chain entry must name the signing key "
                                                      "(repeatable; default: BACKUP_DIR/vbmeta.img and BUILD_DIR/out/vbmeta.img)")
    ap.add_argument("--expect-changed", help="comma-separated ramdisk names that must be exactly the changed set")
    ap.add_argument("--real", choices=("stock", "recovery"), help="what init.real must be")
    ap.add_argument("--wrapper", help="file the new init must equal")
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
               and 0 < ft["orig"] <= ft["off"] and ft["off"] % 4096 == 0 and ft["off"] - ft["orig"] < 4096
               and ft["off"] + ft["size"] <= len(img) - 64 and 256 < ft["size"] < 65536)
    r.check("footer", foot_ok, "image %d bytes, vbmeta at %d, %d bytes" % (ft["orig"], ft["off"], ft["size"]))
    if foot_ok:
        gaps_zero = not img[ft["orig"]:ft["off"]].strip(b"\0") and not img[ft["off"] + ft["size"]:-64].strip(b"\0")
        r.check("footer", gaps_zero, "space around the vbmeta blob is all zero" if gaps_zero else "non-zero bytes around the vbmeta blob")

    limit = ft["orig"] if foot_ok else len(img)
    parts, info, problems = read_boot(img, limit)
    r.check("boot-header", parts is not None and not problems, "; ".join(problems) or
            "kernel %d, ramdisk %d, dtb %d, command line %r" % (len(parts["kernel"]), len(parts["ramdisk"]),
                                                               len(parts["dtb"]), info["cmdline"].decode("latin1")))
    if parts is not None:
        r.check("boot-id", sha1_id(parts) == info["id"])

    vb = None
    if foot_ok:
        try:
            vb = read_vbmeta(img[ft["off"]:ft["off"] + ft["size"]])
            if vb["total"] != ft["size"]:
                raise ValueError("vbmeta blob is %d bytes, footer says %d" % (vb["total"], ft["size"]))
        except (ValueError, struct.error, UnicodeDecodeError) as e:
            vb = None
            r.check("vbmeta", False, str(e))
    if vb is None:
        for name in ("vbmeta", "image-hash", "vbmeta-hash", "signature", "chain-key"):
            r.check(name, False, "no usable footer or vbmeta")
    else:
        hashes = [d for d in vb["descs"] if d["kind"] == "hash"]
        extra = [d for d in vb["descs"] if d["kind"] in ("other", "chain")]
        vb_ok = (vb["alg"] == 1 and len(hashes) == 1 and not extra and hashes[0]["name"] == "boot"
                 and hashes[0]["alg"] == "sha256" and hashes[0]["image_size"] == ft["orig"]
                 and hashes[0]["flags"] == 0 and vb["flags"] == 0 and vb["pkmd_size"] == 0)
        r.check("vbmeta", vb_ok, "algorithm %d, %d hash descriptor(s), %d property descriptor(s), flags %d, rollback index %d" % (
            vb["alg"], len(hashes), len(vb["descs"]) - len(hashes) - len(extra), vb["flags"], vb["rollback"]))
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
        r.check("signature", ok, why or ("key modulus %s..." % n.to_bytes(256, "big")[:8].hex().upper()))
        for path in (a.vbmeta or DEF_VBMETA):
            label = os.path.join(os.path.basename(os.path.dirname(path)), os.path.basename(path))
            try:
                top = read_vbmeta(open(path, "rb").read())
            except (OSError, ValueError, struct.error, UnicodeDecodeError) as e:
                r.check("chain-key", False, "%s: %s" % (label, e))
                continue
            top_ok, _, _ = rsa_ok(top["pubkey"], top["sig"], hashlib.sha256(top["signed"]).digest())
            top_ok = top_ok and hashlib.sha256(top["signed"]).digest() == top["hash"]
            chains = [d for d in top["descs"] if d["kind"] == "chain" and d["name"] == "boot"]
            if not top_ok:
                r.check("chain-key", False, "%s is not correctly signed itself" % label)
            elif len(chains) != 1:
                r.check("chain-key", False, "%s has %d chain entries for boot" % (label, len(chains)))
            else:
                same = chains[0]["pubkey"] == vb["pubkey"]
                r.check("chain-key", same and vb["rollback"] == 0, "%s: its `boot` entry (rollback slot %d) names %s" % (
                    label, chains[0]["location"], "exactly this image's key" if same else "A DIFFERENT KEY: the bootloader will refuse this image"))

    new = None
    if parts is not None:
        try:
            new = read_cpio(parts["ramdisk"])
        except (ValueError, zlib.error, UnicodeDecodeError) as e:
            r.check("ramdisk", False, "cannot read the ramdisk: %s" % e)

    old = None
    if a.stock:
        st = open(a.stock, "rb").read()
        sft = read_footer(st)
        sparts, sinfo, sproblems = read_boot(st, sft["orig"])
        if sparts is None or sproblems or parts is None:
            r.check("stock-compare", False, "cannot read the stock image or this image for comparison")
        else:
            for name in ("kernel", "dtb", "second", "recovery_dtbo"):
                r.check("same-" + name.replace("_", "-"), parts[name] == sparts[name],
                        "%d bytes, sha256 %s" % (len(parts[name]), hashlib.sha256(parts[name]).hexdigest()[:16]))
            r.check("same-cmdline", info["cmdline"] == sinfo["cmdline"] and info["extra_cmdline"] == sinfo["extra_cmdline"],
                    repr(info["cmdline"].decode("latin1")))
            # header: everything equal except the ramdisk size (16:20) and the id (576:608)
            mask = lambda h: h[:16] + h[20:576] + h[608:]
            r.check("same-header", mask(info["header"]) == mask(sinfo["header"]),
                    "all header fields equal except ramdisk size and id")
            if vb is not None:
                svb = read_vbmeta(st[sft["off"]:sft["off"] + sft["size"]])
                props = lambda v: [(d["key"], d["value"]) for d in v["descs"] if d["kind"] == "property"]
                salts = lambda v: [d["salt"] for d in v["descs"] if d["kind"] == "hash"]
                r.check("same-vbmeta-props", props(vb) == props(svb) and salts(vb) == salts(svb)
                        and vb["rollback"] == svb["rollback"] and vb["pubkey"] == svb["pubkey"],
                        "property descriptors, salt, rollback index and key as stock")
            try:
                old = read_cpio(sparts["ramdisk"])
            except (ValueError, zlib.error) as e:
                r.check("ramdisk", False, "cannot read the stock ramdisk: %s" % e)
            if new is not None and old is not None:
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

    wrapped = new is not None and "init.real" in new
    if (a.real or a.wrapper) and not wrapped:
        r.check("init-real", False, "the ramdisk has no init.real")
    if wrapped:
        meta, real = new["init.real"]
        wmeta, wrapper = new.get("init", ((), b""))
        want_meta = (0o100750, 0, 0, 1)
        r.check("wrapper-elf", not elf_problems(wrapper) and 1024 <= len(wrapper) <= 65536 and wmeta[:4] == want_meta,
                "; ".join(elf_problems(wrapper)) or "init: %d bytes, static 32-bit ARM, mode %o, root" % (len(wrapper), wmeta[0] if wmeta else 0))
        if a.wrapper:
            r.check("wrapper-file", wrapper == open(a.wrapper, "rb").read(), "init equals %s" % os.path.basename(a.wrapper))
        if old is None or "init" not in old:
            r.check("init-real", False, "needs --stock to compare init.real with the stock init")
        else:
            sinit = old["init"][1]
            where = [i for i in range(min(len(real), len(sinit))) if real[i] != sinit[i]]
            if len(real) != len(sinit):
                kind = "other"
            elif not where:
                kind = "stock"
            elif (sinit[WORD_AT - 1:WORD_AT + 11] == b"\0" + WORD_OLD + b"\0"
                  and real == sinit[:WORD_AT] + WORD_NEW + sinit[WORD_AT + 10:]):
                kind = "recovery"
            else:
                kind = "other"
            say = {"stock": "init.real is the stock init, byte for byte (%d bytes)" % len(real),
                   "recovery": "init.real is the stock init except %d bytes at %#x..%#x: restart word bootloader -> recovery" % (
                       len(where), where[0] if where else 0, where[-1] if where else 0),
                   "other": "init.real differs from the stock init in %d places that are not the restart word" % (
                       len(where) + abs(len(real) - len(sinit)))}[kind]
            ok = kind != "other" and meta[:4] == want_meta and (a.real is None or a.real == kind)
            if a.real and kind != "other" and a.real != kind:
                say += "; expected --real %s" % a.real
            r.check("init-real", ok, say)

    if r.failed:
        print("RESULT: FAIL (%s)" % ",".join(r.failed))
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
