#!/usr/bin/env python3
"""Tests that the tools refuse what they must refuse. Offline; never touches the frame.

    python3 -I tools/test_refusals.py

Part A  fetch-keys.sh: a file with the wrong SHA-256 is refused and nothing is kept (runs without a backup or keys).
Part B  a backup with ONE changed byte is refused by each builder, and no image is written.
Part C  a `super` whose `product` sits somewhere else, or is longer, or whose table checksum is stale, is refused.
Part D  a key file with one changed byte is refused by bootbuild.py.

Parts B, C and D need your own backup (BACKUP_DIR) and the fetched keys (KEY_DIR); without them they print
SKIP and the file still exits 0. Altered copies are made in a temporary folder (copy-on-write clones on APFS)
and removed afterwards. BACKUP_DIR, KEY_DIR and BUILD_DIR are only read.
"""
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lp          # noqa: E402
import px110conf   # noqa: E402

BASE = px110conf.BASE
PY = [sys.executable, "-I"]
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    for folder in (px110conf.path("BACKUP_DIR"), tempfile.gettempdir(), BASE):
        if folder:
            detail = detail.replace(folder + os.sep, "")
    print(("PASS " if cond else "FAIL ") + name + ((" -- " + detail) if detail else ""))


def clone(src, dst):
    if subprocess.run(["cp", "-c", src, dst], capture_output=True).returncode != 0:
        shutil.copyfile(src, dst)
    os.chmod(dst, 0o600)


def flip(path, offset):
    with open(path, "r+b") as f:
        f.seek(offset)
        b = f.read(1)
        f.seek(offset)
        f.write(bytes([b[0] ^ 0x01]))


def altered_backup(tmp, label, name, offset):
    """A folder that looks like the backup, every file a link to the real one, except `name`: a copy with one bit changed."""
    real = px110conf.path("BACKUP_DIR")
    folder = os.path.join(tmp, "backup-" + label)
    os.makedirs(folder)
    for f in os.listdir(real):
        if f != name:
            os.symlink(os.path.join(real, f), os.path.join(folder, f))
    clone(os.path.join(real, name), os.path.join(folder, name))
    flip(os.path.join(folder, name), offset)
    return folder


def run(cmd, tmp, backup=None, keys=None):
    """Run a tool with its own empty BUILD_DIR. Returns (exit status, output, image files it left)."""
    build = os.path.join(tmp, "build")
    shutil.rmtree(build, ignore_errors=True)
    env = dict(os.environ, PX110_BUILD_DIR=build)
    if backup:
        env["PX110_BACKUP_DIR"] = backup
    if keys:
        env["PX110_KEY_DIR"] = keys
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    left = []
    for root, _dirs, files in os.walk(build):
        if os.sep + "work" in root[len(build):]:
            continue                      # scratch copies of the inputs are not outputs
        left += [f for f in files if f.endswith(".img")]
    return r.returncode, r.stdout + r.stderr, left


def last_reason(out):
    lines = [l for l in out.strip().splitlines() if "STOP" in l or "Error" in l or "ERROR" in l or "refus" in l]
    return (lines[-1] if lines else out.strip()[-200:])[:220]


def refused(name, cmd, tmp, wanted, backup=None, keys=None, allow=()):
    """The tool must exit non-zero, say `wanted`, and leave no image except those named in `allow`."""
    rc, out, left = run(cmd, tmp, backup, keys)
    extra = [f for f in left if f not in allow]
    check(name, rc != 0 and wanted in out and not extra, "exit %d, images left %s: %s" % (rc, extra or "none", last_reason(out)))


# ---------------------------------------------------------------- Part A: fetch-keys.sh
def part_a(tmp):
    script = os.path.join(BASE, "fetch-keys.sh")
    names = ["oem_prvk.pem", "recovery_prvk.pem", "boot_prvk.pem", "system_prvk.pem", "vendor_prvk.pem",
             "root_prvk.pem", "img_prvk.pem"]
    standin = os.path.join(tmp, "standin")
    os.makedirs(standin)
    for n in names:
        with open(os.path.join(standin, n), "w") as f:
            f.write("a stand-in, not a key: %s\n" % n)
    keydir = os.path.join(tmp, "keydir")
    env = dict(os.environ, PX110_CONF="/dev/null", PX110_KEY_DIR=keydir)
    r = subprocess.run(["bash", script, "--from", standin], capture_output=True, text=True, env=env)
    kept = os.listdir(keydir) if os.path.isdir(keydir) else []
    check("A1. fetch-keys.sh --from a folder of wrong files: exit 1, all seven REFUSED, nothing kept (not even a temporary file)",
          r.returncode == 1 and r.stdout.count("REFUSED") == 7 and "fetched" not in r.stdout and kept == [],
          "exit %d, %d refused, kept %s" % (r.returncode, r.stdout.count("REFUSED"), kept))
    r = subprocess.run(["bash", script, "--check"], capture_output=True, text=True, env=env)
    check("A2. fetch-keys.sh --check with no keys: exit 1, seven missing, downloads nothing",
          r.returncode == 1 and len(re.findall(r"^missing  ", r.stdout, re.M)) == 7 and os.listdir(keydir) == [])
    planted = os.path.join(keydir, "boot_prvk.pem")
    with open(planted, "w") as f:
        f.write("planted\n")
    before = open(planted).read()
    r = subprocess.run(["bash", script, "--check"], capture_output=True, text=True, env=env)
    check("A3. a wrong file already in KEY_DIR is REFUSED, reported, and left exactly as it was",
          r.returncode == 1 and "REFUSED  boot_prvk.pem" in r.stdout and open(planted).read() == before)
    src = "\n".join(l for l in open(script).read().splitlines() if not l.lstrip().startswith("#"))   # code, not comments
    check("A4. the script pipes nothing into a shell and evaluates nothing it downloads",
          not re.search(r"\|\s*(sh|bash|zsh|python3?)\b", src) and not re.search(r"(^|[;&|({]\s*)(eval|source|\.)\s", src, re.M))


# ---------------------------------------------------------------- Part C helper: a super with another layout
def layout_variants(tmp):
    """The first 4 MiB of the real super (all the table lives there), with product moved, lengthened, or
    moved without fixing the checksums. Only the table is read by the layout check."""
    real = px110conf.backup("super.img")
    head = open(real, "rb").read(4 * 1024 * 1024)
    geom, _metas = lp.parse(real)
    size, base = geom["metadata_max_size"], 4096 * 3

    def variant(name, d_start, d_len, fix):
        d = bytearray(head)
        for slot in range(geom["slot_count"]):
            o = base + slot * size
            raw = bytearray(d[o:o + size])
            magic, _major, _minor, hsize = struct.unpack("<LHHL", raw[:12])
            if magic != lp.HEADER_MAGIC:
                continue
            tsize, = struct.unpack("<L", raw[44:48])
            tables = bytearray(raw[hsize:hsize + tsize])
            p_off, p_n, p_sz, e_off, _e_n, e_sz = struct.unpack("<6L", raw[80:104])
            for i in range(p_n):
                nm, _attrs, first, _n, _grp = struct.unpack("<36sLLLL", tables[p_off + i * p_sz:p_off + i * p_sz + 52])
                if nm.rstrip(b"\0") == b"product":
                    eo = e_off + first * e_sz
                    ns, tt, td, ts = struct.unpack("<QLQL", tables[eo:eo + 24])
                    struct.pack_into("<QLQL", tables, eo, ns + d_len, tt, td + d_start, ts)
            raw[hsize:hsize + tsize] = tables
            if fix:
                raw[48:80] = hashlib.sha256(tables).digest()
                raw[12:44] = hashlib.sha256(raw[:12] + b"\0" * 32 + raw[44:hsize]).digest()
            d[o:o + size] = raw
        p = os.path.join(tmp, name)
        with open(p, "wb") as f:
            f.write(d)
        return p

    with open(os.path.join(tmp, "super-head.img"), "wb") as f:
        f.write(head)
    return {"same": os.path.join(tmp, "super-head.img"),
            "moved": variant("super-moved.img", 8, 0, True),
            "longer": variant("super-longer.img", 0, 8, True),
            "stale": variant("super-stale.img", 8, 0, False)}


# ---------------------------------------------------------------- Parts B, C, D
def parts_bcd(tmp):
    build_py = PY + [os.path.join(HERE, "build.py")]
    rec = PY + [os.path.join(HERE, "recbuild.py")]
    boot = PY + [os.path.join(HERE, "bootbuild.py")]
    splash = PY + [os.path.join(HERE, "logo-from-splash.py")]
    wrapper = os.path.join(tmp, "wrapper-standin.elf")       # never used: the refusal comes before the wrapper is looked at
    with open(wrapper, "wb") as f:
        f.write(b"\x7fELF stand-in")
    apk = os.path.join(tmp, "kiosk.apk")                     # a stand-in zip: the refusal comes before it is used
    with open(apk, "wb") as f:
        f.write(b"PK\x03\x04" + b"\0" * 64)
    picture = os.path.join(tmp, "picture.bgra")              # 2000x1200 B,G,R,A, alpha 255: a valid picture
    with open(picture, "wb") as f:
        f.write(b"\x10\x20\x30\xff" * (2000 * 1200))
    kiosk = ["--kiosk-apk", apk, "--kiosk-name", "kiosk"]
    stock_words = "is not the stock"

    # B: one changed byte
    for label, name, offset in (("vbmeta", "vbmeta.img", 700), ("vbmeta_system", "vbmeta_system.img", 1440),
                                ("vbmeta_vendor", "vbmeta_vendor.img", 700), ("lk", "lk.img", 1000), ("boot", "boot.img", 4000000),
                                ("super-outside-product", "super.img", 2000000000),
                                ("super-inside-product", "super.img", 32512 * 4096 + 5000),
                                ("super-in-its-table", "super.img", 4096 * 3 + 200)):
        b = altered_backup(tmp, "b-" + label, name, offset)
        refused("B. build.py refuses a backup with one bit changed in %s (%s)" % (name, label), build_py + kiosk, tmp, stock_words, backup=b)
        shutil.rmtree(b)
    b = altered_backup(tmp, "b-rec", "recovery.img", 4000000)
    refused("B. recbuild.py refuses a backup with one bit changed in recovery.img (not even the re-signed copy is written)",
            rec, tmp, "does not have the hash recorded", backup=b)
    b = altered_backup(tmp, "b-boot", "boot.img", 4000000)
    refused("B. bootbuild.py refuses a backup with one bit changed in boot.img",
            boot + ["--wrapper", wrapper], tmp, "does not have its recorded hash", backup=b)
    b = altered_backup(tmp, "b-logo", "logo.img", 900000)
    refused("B. logo-from-splash.py refuses a backup with one bit changed in logo.img",
            splash + [picture, os.path.join(tmp, "build", "logo.img")], tmp, "not the factory logo", backup=b)
    rc, out, left = run(rec, tmp)
    check("B. (control) recbuild.py with the untouched backup builds both images, so the refusals above are not a broken set-up",
          rc == 0 and sorted(left) == ["recovery-rescue.img", "recovery-stock-resigned.img"], last_reason(out))

    # C: another layout
    v = layout_variants(tmp)
    for label, words in (("moved", "these tools are fixed to"), ("longer", "these tools are fixed to"),
                         ("stale", "cannot read the dynamic-partition table")):
        try:
            px110conf.check_product_layout(v[label])
            check("C. check_product_layout refuses a super with product %s" % label, False, "it was accepted")
        except ValueError as e:
            check("C. check_product_layout refuses a super with product %s" % label, words in str(e), str(e)[:160])
        refused("C. recbuild.py --super refuses that super (product %s): no rescue image is written" % label,
                rec + ["--super", v[label]], tmp, words, allow=("recovery-stock-resigned.img",))
    check("C. (control) check_product_layout accepts the real table",
          px110conf.check_product_layout(v["same"]) == [(32512 * 4096, 109813760)])
    refused("C. recbuild.py with no super at all refuses to build the rescue image",
            rec + ["--super", ""], tmp, "cannot be checked", allow=("recovery-stock-resigned.img",))
    real = px110conf.path("BACKUP_DIR")
    b = os.path.join(tmp, "backup-layout")
    os.makedirs(b)
    for f in os.listdir(real):
        if f != "super.img":
            os.symlink(os.path.join(real, f), os.path.join(b, f))
    os.symlink(v["moved"], os.path.join(b, "super.img"))
    refused("C. build.py refuses a backup whose super has product moved", build_py + kiosk, tmp, stock_words, backup=b)
    script = open(os.path.join(px110conf.SRC, "recovery", "rescue.sh")).read()
    src2 = os.path.join(tmp, "src-recovery")
    shutil.copytree(os.path.join(px110conf.SRC, "recovery"), src2)
    with open(os.path.join(src2, "rescue.sh"), "w") as f:
        f.write(script.replace("SKIP=32512; COUNT=26810", "SKIP=32520; COUNT=26810"))
    refused("C. recbuild.py refuses a rescue.sh whose own product position is not the one checked in super",
            rec + ["--src", src2], tmp, "does not carry exactly the product position", allow=("recovery-stock-resigned.img",))

    # D: a changed key
    keys = os.path.join(tmp, "keys")
    os.makedirs(keys)
    realkeys = os.path.dirname(px110conf.key("x"))
    for f in os.listdir(realkeys):
        if f.endswith(".pem"):
            os.symlink(os.path.realpath(os.path.join(realkeys, f)), os.path.join(keys, f))
    os.remove(os.path.join(keys, "boot_prvk.pem"))
    with open(os.path.realpath(os.path.join(realkeys, "boot_prvk.pem")), "rb") as f:
        data = f.read()
    with open(os.path.join(keys, "boot_prvk.pem"), "wb") as f:
        f.write(data + b"\n")                                 # the same key, one byte longer: still not the pinned file
    os.chmod(os.path.join(keys, "boot_prvk.pem"), 0o600)
    refused("D. bootbuild.py refuses a boot key file that does not have its pinned hash",
            boot + ["--wrapper", wrapper], tmp, "does not have its pinned hash", keys=keys)
    shutil.rmtree(keys)


def main():
    with tempfile.TemporaryDirectory(prefix="px110-refusals-") as tmp:
        part_a(tmp)
        why = px110conf.missing(backup_files=tuple(px110conf.STOCK_SHA256) + ("para.img", "mmcblk0boot0.img"),
                                key_files=("testkey_rsa2048.pem", "recovery_prvk.pem", "boot_prvk.pem", "root_prvk.pem", "img_prvk.pem"))
        if why:
            print("SKIP test_refusals.py parts B, C and D: " + why)
        else:
            parts_bcd(tmp)
    bad = results.count(False)
    print("ALL PASS (%d checks)" % len(results) if not bad else "FAILED: %d of %d checks" % (bad, len(results)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
