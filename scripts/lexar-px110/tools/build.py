#!/usr/bin/env python3
"""Build the patched product image and re-signed vbmeta images. Offline only; never talks to the frame.

Run from anywhere:  python3 -I tools/build.py --kiosk-apk /path/to/your-kiosk.apk
Settings (unit.conf or the environment, see px110conf.py): BACKUP_DIR, KEY_DIR, BUILD_DIR, E2FSPROGS_DIR,
          KIOSK_APK, KIOSK_NAME.
Inputs  (never modified): BACKUP_DIR/{super,vbmeta,vbmeta_system,vbmeta_vendor,lk,boot}.img,
                          src/photoframe.rc, the kiosk APK, KEY_DIR/testkey_rsa2048.pem
Outputs: BUILD_DIR/out/{product.img,vbmeta_system.img,vbmeta.img,product.extents.txt}
         (run_tests.sh then checks them and writes BUILD_DIR/out/SHA256SUMS)
The run is deterministic: the same inputs and the same e2fsprogs give byte-identical outputs.

Refuses to start unless every stock image has the hash recorded for firmware PF1106_V2.06_20250527
and `product` sits in `super` exactly where rescue.sh and frame-doctor.sh expect it.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import avblib      # noqa: E402
import hashtree    # noqa: E402
import lp          # noqa: E402
import px110conf   # noqa: E402

WORK = px110conf.build_dir("work")
STOCK = os.path.join(WORK, "stock")
SRC = px110conf.SRC
OUT = px110conf.build_dir("out")
KEY = px110conf.key("testkey_rsa2048.pem")
STOCK_IMAGES = ("vbmeta.img", "vbmeta_system.img", "vbmeta_vendor.img", "lk.img", "boot.img", "super.img")
STOCK_TIME = 0x495C0780                     # 2009-01-01 00:00:00 UTC, on every stock inode
SELABEL = b"u:object_r:system_file:s0\0"    # read from the stock neighbours, checked below


def sha(path_or_bytes):
    if isinstance(path_or_bytes, (bytes, bytearray)):
        return hashlib.sha256(path_or_bytes).hexdigest()
    h = hashlib.sha256()
    with open(path_or_bytes, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def debugfs(img, cmds, write=False):
    args = [px110conf.e2fs("debugfs")] + (["-w"] if write else []) + ["-f", "-", os.path.basename(img)]
    # cwd=WORK and bare file names: debugfs splits arguments on spaces, and WORK's own path may hold some
    assert os.path.dirname(img) == WORK
    r = subprocess.run(args, input="\n".join(cmds) + "\n", capture_output=True, text=True, cwd=WORK)
    return r.stdout + r.stderr


def clone(src, dst):
    """Copy a file; on APFS this is a copy-on-write clone, so the 2.8 GB super takes no time or space."""
    if os.path.exists(dst):
        os.remove(dst)
    if subprocess.run(["cp", "-c", src, dst], capture_output=True).returncode != 0:
        shutil.copyfile(src, dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kiosk-apk", default=px110conf.path("KIOSK_APK"),
                    help="the kiosk APK to put in product as a system app (default: KIOSK_APK in unit.conf)")
    ap.add_argument("--kiosk-name", default=px110conf.get("KIOSK_NAME"),
                    help="its name in the image, /product/app/NAME/NAME.apk (default: KIOSK_NAME, else the APK's file name)")
    a = ap.parse_args()
    if not a.kiosk_apk:
        sys.exit("STOP: no kiosk APK given (--kiosk-apk, or KIOSK_APK in unit.conf)")
    if not os.path.isfile(a.kiosk_apk):
        sys.exit("STOP: the kiosk APK is not a file: %s" % a.kiosk_apk)
    with open(a.kiosk_apk, "rb") as f:
        if f.read(4) != b"PK\x03\x04":
            sys.exit("STOP: %s is not an APK (no zip signature)" % a.kiosk_apk)
    kiosk = a.kiosk_name or os.path.splitext(os.path.basename(a.kiosk_apk))[0]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}", kiosk):
        sys.exit("STOP: the kiosk name %r must be letters, digits, dot, dash or underscore (give --kiosk-name)" % kiosk)
    app_dir, app_file = "/app/%s" % kiosk, "/app/%s/%s.apk" % (kiosk, kiosk)

    # 0. The backup must be the stock firmware these tools are fixed to, with product where they expect it.
    #    Checked on the backup itself, before anything is copied or built (BACKUP_DIR is only ever read).
    try:
        for name in STOCK_IMAGES:
            px110conf.check_stock(px110conf.backup(name), name)
        px110conf.check_product_layout(px110conf.backup("super.img"))
    except (px110conf.NotSet, ValueError) as e:
        sys.exit("STOP: %s" % e)
    print("backup ok: six stock images have the hashes recorded for %s; product layout in super as expected"
          % px110conf.FIRMWARE)
    if not os.path.isfile(KEY):
        sys.exit("STOP: key file missing: %s (fetch-keys.sh gets it)" % KEY)

    os.makedirs(STOCK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    # Working copies of the stock images, made fresh on every run and checked again.
    for name in STOCK_IMAGES:
        dst = os.path.join(STOCK, name)
        clone(px110conf.backup(name), dst)
        if sha(dst) != px110conf.STOCK_SHA256[name]:
            sys.exit("STOP: the working copy of %s is damaged" % name)
    shutil.copyfile(os.path.join(SRC, "photoframe.rc"), os.path.join(WORK, "in-photoframe.rc"))
    shutil.copyfile(a.kiosk_apk, os.path.join(WORK, "in-kiosk.apk"))

    # 1. Key check: the private key must match the key inside stock vbmeta.
    key = avblib.load_private_key(KEY)
    testpub = avblib.encode_avb_pubkey(key[0], key[2])
    vb_stock = avblib.Vbmeta(open(os.path.join(STOCK, "vbmeta.img"), "rb").read())
    if vb_stock.public_key != testpub:
        sys.exit("STOP: private key does not match the key in stock vbmeta.img")
    vb_stock.verify()
    if avblib.sign_vbmeta(vb_stock.header, vb_stock.aux, key) != vb_stock.blob:
        sys.exit("STOP: signer does not reproduce the stock vbmeta signature")
    print("key ok: matches stock vbmeta; signer reproduces stock vbmeta byte for byte")

    # 2. Locate and extract product from super.
    super_img = os.path.join(STOCK, "super.img")
    extents = lp.partition_extents(super_img, "product")
    if extents != [(px110conf.PRODUCT_FIRST_BLOCK * 4096, px110conf.PRODUCT_BYTES)]:
        sys.exit("STOP: product is not where these tools expect it inside super: %r" % extents)
    stock_product = bytearray()
    with open(super_img, "rb") as f:
        for off, length in extents:
            f.seek(off)
            stock_product += f.read(length)
    stock_product = bytes(stock_product)
    if sha(stock_product) != px110conf.STOCK_PRODUCT_SHA256:
        sys.exit("STOP: the product region of super is not the stock one")
    open(os.path.join(STOCK, "product.img"), "wb").write(stock_product)

    vs_stock = avblib.Vbmeta(open(os.path.join(STOCK, "vbmeta_system.img"), "rb").read())
    idx = [i for i, d in enumerate(vs_stock.descriptors) if d["type"] == "hashtree" and d["name"] == "product"]
    assert len(idx) == 1
    idx = idx[0]
    ht = vs_stock.descriptors[idx]
    fs_size, tree_off, tree_size = ht["image_size"], ht["tree_offset"], ht["tree_size"]
    fec_off, fec_size, roots, salt = ht["fec_offset"], ht["fec_size"], ht["fec_num_roots"], ht["salt"]
    assert tree_off == fs_size and fec_off == tree_off + tree_size

    # Prove the generators on stock before trusting them on the patched image.
    root, tree = hashtree.build_hashtree(stock_product[:fs_size], salt, ht["hash_algorithm"])
    assert root == ht["root_digest"] and tree == stock_product[tree_off : tree_off + tree_size], "hashtree self-test"
    fec = hashtree.build_fec(stock_product[:fec_off], roots)
    assert fec == stock_product[fec_off : fec_off + fec_size], "FEC self-test"
    print("generators ok: stock hashtree and FEC reproduced byte for byte")

    footer = avblib.parse_footer(stock_product[-64:])
    assert footer and footer["original_image_size"] == fs_size and footer["vbmeta_offset"] == fec_off + fec_size
    fvb = avblib.Vbmeta(stock_product[footer["vbmeta_offset"] : footer["vbmeta_offset"] + footer["vbmeta_size"]])
    assert fvb.h["algorithm"] == 0 and fvb.descriptors[0]["raw"] == ht["raw"]

    # 3. Edit the ext4 filesystem in place.
    ext4 = os.path.join(WORK, "product.ext4")
    open(ext4, "wb").write(stock_product[:fs_size])
    for path in ("/app", "/app/LatinIME", "/app/LatinIME/LatinIME.apk", "/etc", "/etc/permissions",
                 "/etc/permissions/com.adups.fota.xml"):
        out = debugfs(ext4, ["ea_get -x %s security.selinux" % path])
        assert SELABEL.hex() in out.replace(" ", ""), "unexpected label on %s: %s" % (path, out)
    label_file = os.path.join(WORK, "selabel.bin")
    open(label_file, "wb").write(SELABEL)

    t = "set_current_time 20090101000000"
    cmds = [
        t,
        "rm /app/FotaApp/oat/arm/FotaApp.odex",
        "rm /app/FotaApp/oat/arm/FotaApp.vdex",
        "rmdir /app/FotaApp/oat/arm",
        "rmdir /app/FotaApp/oat",
        "rm /app/FotaApp/FotaApp.apk",
        "rmdir /app/FotaApp",
        "mkdir /etc/init",
        "write in-photoframe.rc /etc/init/photoframe.rc",
        "mkdir %s" % app_dir,
        "write in-kiosk.apk %s" % app_file,
    ]
    new = {"/etc/init": 0o40755, "/etc/init/photoframe.rc": 0o100644,
           app_dir: 0o40755, app_file: 0o100644}
    for path, mode in new.items():
        cmds += ["sif %s mode 0%o" % (path, mode), "sif %s uid 0" % path, "sif %s gid 0" % path]
        cmds += ["sif %s %s 0x%x" % (path, f, STOCK_TIME) for f in ("atime", "ctime", "mtime", "crtime")]
        cmds += ["sif %s %s 0" % (path, f) for f in ("atime_extra", "ctime_extra", "mtime_extra", "crtime_extra")]
        cmds += ["ea_set -f selabel.bin %s security.selinux" % path]
    # parents whose contents changed: keep the stock timestamp
    for path in ("/app", "/etc"):
        cmds += ["sif %s %s 0x%x" % (path, f, STOCK_TIME) for f in ("atime", "ctime", "mtime")]
        cmds += ["sif %s %s 0" % (path, f) for f in ("atime_extra", "ctime_extra", "mtime_extra")]
    log = debugfs(ext4, cmds, write=True)
    open(os.path.join(WORK, "debugfs.log"), "w").write(log)
    bad = [l for l in log.splitlines() if l and not l.startswith("debugfs") and "Allocated inode" not in l]
    if bad != ["Setting current time to Thu Jan  1 00:00:00 2009"]:
        sys.exit("STOP: unexpected debugfs output:\n  " + "\n  ".join(bad))
    # read the two new files back out of the image and compare with the sources
    for host, path, source in (("photoframe.rc", "/etc/init/photoframe.rc", os.path.join(SRC, "photoframe.rc")),
                               ("kiosk.apk", app_file, a.kiosk_apk)):
        back = os.path.join(WORK, "readback-" + host)
        if os.path.exists(back):
            os.remove(back)
        debugfs(ext4, ["dump %s readback-%s" % (path, host)])
        if not os.path.exists(back) or sha(back) != sha(source):
            sys.exit("STOP: %s read back from the image differs from the source" % path)
        print("read back ok: %s sha256 %s" % (path, sha(back)))
    assert os.path.getsize(ext4) == fs_size

    r = subprocess.run([px110conf.e2fs("e2fsck"), "-fn", ext4], capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        sys.exit("STOP: e2fsck -fn is not clean (exit %d)\n%s" % (r.returncode, r.stderr))

    # 4. Hashtree, FEC, footer vbmeta, then the full partition image.
    fs = open(ext4, "rb").read()
    root, tree = hashtree.build_hashtree(fs, salt, ht["hash_algorithm"])
    assert len(tree) == tree_size
    fec = hashtree.build_fec(fs + tree, roots)
    assert len(fec) == fec_size
    new_ht = dict(ht, root_digest=root)
    new_raw = avblib.build_hashtree_descriptor(new_ht)
    assert avblib.build_hashtree_descriptor(ht) == ht["raw"], "descriptor round-trip"
    assert len(new_raw) == len(ht["raw"])
    new_fvb = avblib.rebuild_vbmeta(fvb, {0: new_raw})
    product = bytearray(stock_product)
    product[:fs_size] = fs
    product[tree_off : tree_off + tree_size] = tree
    product[fec_off : fec_off + fec_size] = fec
    product[footer["vbmeta_offset"] : footer["vbmeta_offset"] + len(new_fvb)] = new_fvb
    product = bytes(product)
    assert len(product) == len(stock_product) == sum(l for _, l in extents)

    # 5. vbmeta_system: new product descriptor, test key as its public key, signed with the test key.
    new_vs = avblib.rebuild_vbmeta(vs_stock, {idx: new_raw}, public_key=testpub, key=key)
    # 6. vbmeta: chain descriptor for vbmeta_system now names the test key; re-signed with the test key.
    cidx = [i for i, d in enumerate(vb_stock.descriptors)
            if d["type"] == "chain_partition" and d["name"] == "vbmeta_system"]
    assert len(cidx) == 1
    chain = vb_stock.descriptors[cidx[0]]
    assert chain["public_key"] == vs_stock.public_key and chain["raw"].count(chain["public_key"]) == 1
    new_chain = chain["raw"].replace(chain["public_key"], testpub)
    new_vb = avblib.rebuild_vbmeta(vb_stock, {cidx[0]: new_chain}, key=key)

    def pad(blob, name):
        size = os.path.getsize(os.path.join(STOCK, name))
        return blob + b"\0" * (size - len(blob))

    outs = {"product.img": product, "vbmeta_system.img": pad(new_vs, "vbmeta_system.img"),
            "vbmeta.img": pad(new_vb, "vbmeta.img")}
    for name, data in outs.items():
        open(os.path.join(OUT, name), "wb").write(data)
    with open(os.path.join(OUT, "product.extents.txt"), "w") as f:
        f.write("# product.img is written to these byte ranges of the super partition, in order\n")
        f.write("# (LP metadata slot 0; slot 1 is identical). Sector = 512 bytes.\n")
        f.write("# product_img_offset  super_byte_offset  byte_length  super_sector  sectors\n")
        pos = 0
        for off, length in extents:
            f.write("%d %d %d %d %d\n" % (pos, off, length, off // 512, length // 512))
            pos += length
    with open(os.path.join(OUT, "kiosk-path.txt"), "w") as f:      # for run_tests.sh: where the kiosk sits in product
        f.write(app_file + "\n")
    print("kiosk: %s as %s" % (os.path.basename(a.kiosk_apk), "/product" + app_file))
    print("new product root digest:", root.hex())
    for name in sorted(outs):
        print("%s  %s" % (sha(outs[name]), name))


if __name__ == "__main__":
    main()
