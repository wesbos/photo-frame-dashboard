"""Tests for the boot wrapper, its builder and its checker (offline; nothing here talks to the frame).

Run:   python3 -I tools/test_bootwrap.py
Needs your own backup (BACKUP_DIR), the fetched keys (KEY_DIR), BUILD_DIR/out/vbmeta.img (build.py) and the ARM
toolchain (clang, arm-none-eabi-ld, -strip, -objdump); without the backup or the keys it prints SKIP and exits 0.

Part A  the images: re-signed stock is byte-identical, kernel/dtb/command line untouched, the ramdisk
        differs in exactly the two expected files, the checker passes them and fails every tampered copy.
Part B  the wrapper itself: the real ARM program is run (test_bootwrap_armemu.py) against stand-in
        devices: empty, ours, foreign notes, missing, slow, read-only, failing, hanging.
Part C  the proof about the stock init's restart word (src/bootwrap/initscan.py).
Part D  the rig itself: fifteen deliberately broken wrappers must each be caught.
"""
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import avblib                      # noqa: E402
import px110conf                   # noqa: E402
import bootbuild as bb             # noqa: E402
import bootverify as bv            # noqa: E402  (used as a second, independent reader)
import test_bootwrap_armemu as emu  # noqa: E402

STOCK = bb.DEF_STOCK
KEY = bb.DEF_KEY
OTHER_KEY = px110conf.key("testkey_rsa2048.pem")
OUT = bb.DEF_OUT
VERIFY = os.path.join(HERE, "bootverify.py")
SCAN = os.path.join(px110conf.SRC, "bootwrap", "initscan.py")
WHY_SKIP = px110conf.missing(backup_files=("boot.img", "vbmeta.img"), key_files=("boot_prvk.pem", "testkey_rsa2048.pem"))

TMP = None
ELF = None
IMG = {}


def setUpModule():
    global TMP, ELF
    TMP = tempfile.mkdtemp(prefix="bootwrap-test-")
    ELF = bb.compile_wrapper()
    with open(os.path.join(TMP, "bootwrap.elf"), "wb") as f:
        f.write(ELF)
    for kind, (name, wrapped, patch) in bb.VARIANTS.items():
        IMG[kind] = bb.build(STOCK, KEY, ELF if wrapped else None, patch, log=lambda s: None)
        with open(os.path.join(TMP, name), "wb") as f:
            f.write(IMG[kind])


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


def verify(path, *args):
    p = subprocess.run([sys.executable, "-I", VERIFY, path] + list(args), capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def rd(path):
    with open(path, "rb") as f:
        return f.read()


def tmpfile(name, data):
    path = os.path.join(TMP, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def full_args(kind):
    if kind == "resigned":
        return ["--stock", STOCK, "--expect-changed", ""]
    return ["--stock", STOCK, "--expect-changed", "init,init.real", "--wrapper", os.path.join(TMP, "bootwrap.elf"),
            "--real", "recovery" if kind == "wrap-recovery" else "stock"]


# ============================================================================ Part A: the images
class A_Images(unittest.TestCase):
    def test_01_resigned_stock_is_byte_identical(self):
        self.assertEqual(IMG["resigned"], rd(STOCK))

    def test_02_checker_passes_all_three(self):
        for kind, (name, _w, _p) in bb.VARIANTS.items():
            code, out = verify(os.path.join(TMP, name), *full_args(kind))
            self.assertEqual(code, 0, out)
            self.assertTrue(out.strip().endswith("RESULT: PASS"), out)

    def test_03_kernel_dtb_cmdline_and_header_untouched(self):
        stock = rd(STOCK)
        ksz, rsz = struct.unpack_from("<I", stock, 8)[0], struct.unpack_from("<I", stock, 16)[0]
        dtb_sz = struct.unpack_from("<I", stock, 1648)[0]
        up = lambda n: -(-n // 2048) * 2048
        for kind in ("wrap", "wrap-recovery"):
            img = IMG[kind]
            new_rsz = struct.unpack_from("<I", img, 16)[0]
            self.assertEqual(img[:16], stock[:16])                                   # magic, kernel size, kernel address
            self.assertEqual(img[20:576], stock[20:576])                             # addresses, page size, os version, name, cmdline
            self.assertEqual(img[608:2048], stock[608:2048])                         # extra cmdline, dtbo fields, header size, dtb fields
            self.assertEqual(img[64:576].rstrip(b"\0"), b"bootopt=64S3,32N2,32N2 buildvariant=user")
            self.assertEqual(img[2048:2048 + up(ksz)], stock[2048:2048 + up(ksz)])   # kernel, with its padding
            d_new, d_old = 2048 + up(ksz) + up(new_rsz), 2048 + up(ksz) + up(rsz)
            self.assertEqual(img[d_new:d_new + up(dtb_sz)], stock[d_old:d_old + up(dtb_sz)])
            self.assertEqual(hashlib.sha256(img[d_new:d_new + dtb_sz]).hexdigest(),
                             hashlib.sha256(stock[d_old:d_old + dtb_sz]).hexdigest())

    def test_04_ramdisk_differs_in_exactly_two_files(self):
        stock = rd(STOCK)
        sparts, _, _ = bv.read_boot(stock, bv.read_footer(stock)["orig"])
        old = bv.read_cpio(sparts["ramdisk"])
        for kind in ("wrap", "wrap-recovery"):
            img = IMG[kind]
            parts, _, problems = bv.read_boot(img, bv.read_footer(img)["orig"])
            self.assertEqual(problems, [])
            new = bv.read_cpio(parts["ramdisk"])
            self.assertEqual(sorted(set(new) ^ set(old)), ["init.real"])
            self.assertEqual([n for n in old if new[n] != old[n]], ["init"])
            self.assertEqual(new["init"][1], ELF)
            self.assertEqual(new["init"][0], old["init"][0])                         # same mode, owner, times
            self.assertEqual(new["init.real"][0], old["init"][0])
            real, sinit = new["init.real"][1], old["init"][1]
            if kind == "wrap":
                self.assertEqual(real, sinit)
            else:
                diff = [i for i in range(len(sinit)) if real[i] != sinit[i]]
                self.assertEqual(len(real), len(sinit))
                self.assertEqual(diff, list(range(0x7740, 0x774A)))
                self.assertEqual(sinit[0x773F:0x774B], b"\0bootloader\0")
                self.assertEqual(real[0x773F:0x774B], b"\0recovery\0\0\0")

    def test_05_build_is_repeatable(self):
        self.assertEqual(bb.compile_wrapper(), ELF)
        self.assertEqual(bb.build(STOCK, KEY, ELF, True, log=lambda s: None), IMG["wrap-recovery"])

    def test_06_flipped_byte_fails_the_checker(self):
        img = IMG["wrap-recovery"]
        ft = bv.read_footer(img)
        ksz = struct.unpack_from("<I", img, 8)[0]
        rsz = struct.unpack_from("<I", img, 16)[0]
        up = lambda n: -(-n // 2048) * 2048
        rd = 2048 + up(ksz)
        spots = {
            "header: command line": 70,
            "header: kernel load address": 12,
            "header: id": 580,
            "kernel, first byte": 2048,
            "kernel, middle": 2048 + ksz // 2,
            "kernel, last byte": 2048 + ksz - 1,
            "ramdisk, first byte": rd,
            "ramdisk, middle": rd + rsz // 2,
            "ramdisk, last byte": rd + rsz - 1,
            "dtb, middle": rd + up(rsz) + 20000,
            "padding after the image": ft["orig"] + 5,
            "vbmeta header": ft["off"] + 40,
            "vbmeta stored hash": ft["off"] + 256 + 3,
            "vbmeta signature": ft["off"] + 256 + 32 + 100,
            "vbmeta descriptor": ft["off"] + 256 + 320 + 150,
            "vbmeta public key": ft["off"] + ft["size"] - 300,
            "zero space after vbmeta": ft["off"] + ft["size"] + 9,
            "footer": len(img) - 40,
            "last byte": len(img) - 1,
        }
        for label, at in spots.items():
            for bit in (0x01, 0x80):
                bad = bytearray(img)
                bad[at] ^= bit
                code, out = verify(tmpfile("flip.img", bad), *full_args("wrap-recovery"))
                self.assertNotEqual(code, 0, "a flipped bit in %s (offset %d) was not noticed" % (label, at))
                self.assertIn("RESULT: FAIL", out)

    def test_07_checker_fails_stock_and_resigned_when_flipped(self):
        stock = bytearray(rd(STOCK))
        stock[2048 + 1234567] ^= 0x10
        code, _ = verify(tmpfile("flip-stock.img", stock), "--stock", STOCK, "--expect-changed", "")
        self.assertNotEqual(code, 0)

    def _resign(self, change):
        """A correctly signed image whose ramdisk was changed by `change(entries)`."""
        stock = rd(STOCK)
        ft, vb = bb.stock_vbmeta(stock)
        boot = bb.unpack_boot(stock[:ft["original_image_size"]])
        entries = bb.cpio_parse(bb.gunzip(boot["parts"]["ramdisk"]))
        bb.apply_changes(entries, ELF, True)
        change(entries)
        image = bb.pack_boot(boot, bb.gzip_like_stock(bb.cpio_build(entries)))
        return bb.add_footer(image, vb, avblib.load_private_key(KEY))

    def test_08_correctly_signed_but_wrong_contents_fail(self):
        def entry(entries, name):
            return [e for e in entries if e["name"] == name][0]

        def flip(name, at):
            def change(entries):
                e = entry(entries, name)
                d = bytearray(e["data"])
                d[at] ^= 1
                e["data"] = bytes(d)
            return change

        cases = {
            "one bit in the wrapper": (flip("init", 0x1100), "wrapper-file"),
            "one bit in init.real, away from the word": (flip("init.real", 0x5EF98 - 0x53280 + 0x42280), "init-real"),
            "one more byte next to the word": (flip("init.real", 0x774C), "init-real"),
            "an extra file": (lambda es: es.insert(1, dict(entry(es, "fstab.mt8167"), name="extra", data=b"x")), "ramdisk"),
            "a file removed": (lambda es: es.remove(entry(es, "avb/q-gsi.avbpubkey")), "ramdisk"),
            "fstab changed": (flip("fstab.mt8167", 100), "ramdisk"),
            "wrapper not executable": (lambda es: entry(es, "init").update(mode=0o100640), "wrapper-elf"),
            "init.real owned by someone else": (lambda es: entry(es, "init.real").update(uid=1000), "init-real"),
        }
        for label, (change, check) in cases.items():
            code, out = verify(tmpfile("wrong.img", self._resign(change)), *full_args("wrap-recovery"))
            self.assertNotEqual(code, 0, label)
            self.assertIn(check, out.strip().splitlines()[-1], "%s: %s" % (label, out.strip().splitlines()[-1]))
        # and the same rebuild with no change passes, so the cases above failed for their own reason
        self.assertEqual(self._resign(lambda es: None), IMG["wrap-recovery"])

    def test_09_wrong_variant_expectation_fails(self):
        code, out = verify(os.path.join(TMP, "boot-wrap.img"), "--stock", STOCK, "--real", "recovery")
        self.assertNotEqual(code, 0)
        self.assertIn("init-real", out.strip().splitlines()[-1])
        code, out = verify(os.path.join(TMP, "boot-wrap-recovery.img"), "--stock", STOCK, "--real", "stock")
        self.assertNotEqual(code, 0)

    def test_10_other_key_is_refused_by_builder_and_checker(self):
        with self.assertRaises(ValueError):
            bb.build(STOCK, OTHER_KEY, ELF, True, log=lambda s: None)
        img = bb.build(STOCK, OTHER_KEY, ELF, True, allow_other_key=True, log=lambda s: None)
        code, out = verify(tmpfile("otherkey.img", img), *full_args("wrap-recovery"))
        self.assertNotEqual(code, 0)
        self.assertIn("chain-key", out.strip().splitlines()[-1])
        self.assertIn("A DIFFERENT KEY", out)

    def test_11_builder_refuses_a_stock_image_that_is_not_the_recorded_one(self):
        bad = bytearray(rd(STOCK))
        bad[5000000] ^= 1
        with self.assertRaises(ValueError):
            bb.build(tmpfile("notstock.img", bad), KEY, ELF, True, log=lambda s: None)

    def test_12_word_patch_refuses_anything_but_the_proven_init(self):
        stock = rd(STOCK)
        parts, _, _ = bv.read_boot(stock, bv.read_footer(stock)["orig"])
        sinit = bv.read_cpio(parts["ramdisk"])["init"][1]
        self.assertEqual(hashlib.sha256(sinit).hexdigest(), bb.STOCK_INIT_SHA256)
        changed = bytearray(sinit)
        changed[100] ^= 1
        with self.assertRaises(ValueError):
            bb.patch_target(bytes(changed))
        patched = bb.patch_target(sinit)
        self.assertEqual(patched.count(b"bootloader"), 0)
        self.assertEqual(len(patched), len(sinit))

    def test_13_signing_key_is_the_one_both_vbmeta_images_name_for_boot(self):
        key = avblib.load_private_key(KEY)
        pub = avblib.encode_avb_pubkey(key[0], key[2])
        for path in bv.DEF_VBMETA:
            top = avblib.Vbmeta(rd(path))
            top.verify()
            chain = [d for d in top.descriptors if d["type"] == "chain_partition" and d["name"] == "boot"]
            self.assertEqual(len(chain), 1)
            self.assertEqual(chain[0]["public_key"], pub)

    def test_14_delivered_files_are_what_the_sources_build(self):
        sums = os.path.join(OUT, "SHA256SUMS")
        if not os.path.exists(sums):
            self.skipTest("out-boot not built yet")
        with open(sums) as f:
            listed = dict(reversed(line.split()) for line in f)
        fresh = {name: IMG[kind] for kind, (name, _w, _p) in bb.VARIANTS.items()}
        fresh["bootwrap.elf"] = ELF
        self.assertEqual(sorted(listed), sorted(fresh))
        for name, data in fresh.items():
            on_disk = rd(os.path.join(OUT, name))
            self.assertEqual(hashlib.sha256(on_disk).hexdigest(), listed[name], name)
            self.assertEqual(on_disk, data, "%s in out-boot is not what the sources build now" % name)


# ============================================================================ Part B: the wrapper
PARENT_MAY = {"fork", "wait4", "nanosleep", "kill", "execve", "exit"}
ARGV = ("/init", "--made-up-flag", "second arg")
ENVP = ("HOME=/", "TERM=linux", "androidboot.mode=normal")


def note(command=b"", status=b"", recovery=b""):
    """A 2048-byte bootloader message as Android lays it out: command[32] status[32] recovery[768] ..."""
    return (command.ljust(32, b"\0") + status.ljust(32, b"\0") + recovery.ljust(768, b"\0")).ljust(2048, b"\0")


def para_with(first_2048, tail_marker=True):
    para = bytearray(emu.PARA_SIZE)
    para[:2048] = first_2048
    if tail_marker:
        para[2048:2056] = b"\xAA\x55TAILMK"                 # right behind the note: must never change
        para[0x20000:0x20006] = b"ENV_v1"                    # the bootloader's own settings, as on the frame
        para[-4:] = b"END!"
    return para


class B_Wrapper(unittest.TestCase):
    def go(self, world, expect_exec=True, leftovers=False):
        """Run the wrapper in `world` and check everything that must hold in EVERY case.
        leftovers=True: the work directory /.bw may differ afterwards (a clean-up step was made to fail)."""
        before = bytes(world.para)
        fs_before = dict(world.fs)
        info = emu.run(ELF, world, ARGV, ENVP)
        # 1. the real init is started, once, as the last thing, with argv and envp untouched
        self.assertIsNotNone(world.exec, "init.real was never started")
        path, argv, envp, when, argv_ptr, envp_ptr = world.exec
        self.assertEqual(path, "/init.real")
        self.assertEqual(tuple(argv), ARGV)
        self.assertEqual(tuple(envp), ENVP)
        self.assertEqual((argv_ptr, envp_ptr), (info["argv_ptr"], info["envp_ptr"]))
        execs = [t for t in world.trace if t[1] == "execve"]
        self.assertEqual(len(execs), 1)
        if expect_exec:
            self.assertEqual(world.trace[-1][1], "execve")
        # 2. never later than 5 s, and the parent does nothing but wait and start init.real
        self.assertLessEqual(when, 5000)
        parent = [t[1] for t in world.trace if t[0] == "parent"]
        self.assertLessEqual(set(parent), PARENT_MAY, parent)
        self.assertEqual(parent.count("fork"), 1)
        # 3. the note: at most one write, of exactly bytes 0..2047, and only over an all-zero note
        for off, length in world.para_writes:
            self.assertEqual((off, length), (0, 2048))
        self.assertLessEqual(len(world.para_writes), 1)
        self.assertEqual(bytes(world.para[2048:]), before[2048:], "something beyond byte 2048 changed")
        for off, length in world.para_reads:
            self.assertLessEqual(off + length, 2048, "read beyond the note")
        if world.para_writes:
            self.assertEqual(before[:2048], bytes(2048), "wrote over a note that was not empty")
        if before[:2048] != bytes(2048):
            self.assertEqual(bytes(world.para), before)
            self.assertEqual(world.para_writes, [])
        self.assertIn(bytes(world.para[:2048]), (before[:2048], emu.PLAIN_NOTE, emu.PLAIN_NOTE[:512] + before[512:2048]))
        # 4. every file is opened close-on-exec; nothing but /.bw paths is created
        for p, flags in world.opens:
            self.assertTrue(flags & emu.O_CLOEXEC, p)
        for t in world.trace:
            if t[1] in ("mkdir", "mknod", "mount", "unlink", "rmdir", "umount2"):
                self.assertIn("/.bw", t[2])
        # 5. pid 1 never has a mount of ours in its table, finished child or not: the real init moves
        #    every mount it sees when it switches root, and one it cannot move is fatal
        self.assertEqual(world.mounts, {}, "a mount of ours is visible to pid 1")
        # 6. a child that finished left nothing behind
        if world.child_exit_ms is not None:
            self.assertEqual(world.exit_codes.get("child"), 0)
            outside = lambda fs: {k: v for k, v in fs.items() if not k.startswith("/.bw")}
            self.assertEqual(outside(world.fs), outside(fs_before))
            if not leftovers:
                self.assertEqual(world.fs, fs_before)
                self.assertIn(world.child_mounts, ({}, None))
                self.assertEqual(world.devs, {})
            self.assertEqual(world.killed, [])
        return world

    def log(self, world):
        return "\n".join(world.kmsg)

    # ---- the three kinds of note
    def test_01_empty_note_is_armed_and_read_back(self):
        w = self.go(emu.World(para_with(bytes(2048))))
        self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE)
        self.assertEqual(w.para_writes, [(0, 2048)])
        self.assertEqual(w.exec[3], 0, "no waiting when the device is there")
        self.assertIn("para was empty: armed boot-recovery, read back ok (dev 259:3)", self.log(w))
        self.assertEqual(w.kmsg[0], "<6>bootwrap: start")
        self.assertEqual(w.kmsg[-1], "<6>bootwrap: done, starting init.real")
        # read, write, sync, read back: in that order on the device
        dev = [t[1] for t in w.trace if t[0] == "child" and "(para)" in t[2]]
        self.assertEqual(dev, ["lseek", "read", "lseek", "write", "fsync", "lseek", "read"])
        self.assertTrue(all(f & emu.O_DIRECT for p, f in w.opens if p == "/.bw/para"))

    def test_02_whole_512k_device_all_zero(self):
        w = self.go(emu.World())
        self.assertEqual(bytes(w.para), emu.PLAIN_NOTE + bytes(emu.PARA_SIZE - 2048))

    def test_03_our_note_already_there_nothing_written(self):
        w = self.go(emu.World(para_with(emu.PLAIN_NOTE)))
        self.assertEqual(w.para_writes, [])
        self.assertIn("our plain note already", self.log(w))

    def test_04_foreign_notes_are_left_alone(self):
        foreign = {
            "factory reset": note(b"boot-recovery", b"", b"recovery\n--wipe_data\n"),
            "prompt and wipe": note(b"boot-recovery", b"", b"recovery\n--prompt_and_wipe_data\n"),
            "update package": note(b"boot-recovery", b"", b"recovery\n--update_package=/cache/x.zip\n"),
            "sideload": note(b"boot-recovery", b"", b"recovery\n--sideload\n"),
            "our just_exit": note(b"boot-recovery", b"", b"recovery\n--just_exit\n"),
            "ours with the recovery line": note(b"boot-recovery", b"", b"recovery\n"),
            "fastboot": note(b"boot-fastboot"),
            "status only": note(b"", b"OKAY"),
            "one stray byte at the very start": b"\x01" + bytes(2047),
            "one stray byte at offset 13": emu.PLAIN_NOTE[:13] + b"\n" + bytes(2034),
            "one stray byte at the very end": bytes(2047) + b"\x80",
            "our note with a stray last byte": emu.PLAIN_NOTE[:2047] + b"\x01",
            "command cut short": b"boot-recover" + bytes(2036),
            "all ones": b"\xFF" * 2048,
        }
        for label, first in foreign.items():
            w = self.go(emu.World(para_with(first)))
            self.assertEqual(w.para_writes, [], label)
            self.assertIn("a note that is not ours; left alone", self.log(w), label)

    def test_05_data_right_behind_the_note_does_not_stop_arming_and_is_untouched(self):
        para = para_with(bytes(2048))
        w = self.go(emu.World(para))
        self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE)
        self.assertEqual(bytes(w.para[2048:2056]), b"\xAA\x55TAILMK")
        self.assertEqual(bytes(w.para[0x20000:0x20006]), b"ENV_v1")

    # ---- finding the device
    def test_10_device_missing_gives_up_after_3_seconds(self):
        w = emu.World(para_with(bytes(2048)))
        w.sysfs = emu.sysfs_tree({n: v for n, v in emu.PARTITIONS.items() if n != 11})
        self.go(w)
        self.assertEqual(w.para_writes, [])
        self.assertEqual(w.child_exit_ms, 2950)                 # 60 looks, 50 ms apart
        self.assertEqual(w.exec[3], 2950)
        self.assertIn("para did not appear in 3 s", self.log(w))
        self.assertEqual([t for t in w.trace if t[1] == "mknod" and "para" in t[2]], [])

    def test_11_no_storage_at_all(self):
        w = emu.World(para_with(bytes(2048)))
        w.sysfs = {}
        self.go(w)
        self.assertEqual(w.para_writes, [])
        self.assertLessEqual(w.exec[3], 3000)

    def test_12_slow_device_is_waited_for(self):
        for appears, armed in ((50, True), (1000, True), (2900, True), (2950, True), (3000, False), (60000, False)):
            w = emu.World(para_with(bytes(2048)))
            w.sysfs_from_ms = appears
            self.go(w)
            self.assertEqual(bool(w.para_writes), armed, "device appearing at %d ms" % appears)
            self.assertEqual(w.exec[3], min(appears, 2950))
            self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE if armed else bytes(2048))

    def test_13_device_number_is_read_not_assumed(self):
        for numbers in (lambda n: (179, n), lambda n: (259, n + 300), lambda n: (8, 16 * n), lambda n: (259, 1048575 - n)):
            w = emu.World(para_with(bytes(2048)))
            w.sysfs = emu.sysfs_tree(numbers=numbers)
            w.para_dev = numbers(11)
            self.go(w)
            self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE, numbers(11))
            self.assertIn("(dev %d:%d)" % numbers(11), self.log(w))

    def test_14_para_at_another_partition_number(self):
        for n in (1, 7, 8, 30, 63):
            parts = {k: v for k, v in emu.PARTITIONS.items() if k not in (11, n)}
            parts[n] = ("para", 1024)
            w = emu.World(para_with(bytes(2048)))
            w.sysfs = emu.sysfs_tree(parts)
            w.para_dev = emu.devnum(n)
            self.go(w)
            self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE, n)

    def test_15_only_the_exact_name_on_the_built_in_storage_counts(self):
        cases = {
            "similar names": {11: ("para2", 1024), 12: ("xpara", 1024), 13: ("par", 1024), 14: ("PARA", 1024)},
            "wrong size": {11: ("para", 2048)},
            "size zero": {11: ("para", 0)},
        }
        for label, parts in cases.items():
            w = emu.World(para_with(bytes(2048)))
            w.sysfs = emu.sysfs_tree(parts)
            self.go(w)
            self.assertEqual(w.para_writes, [], label)
            self.assertEqual(w.opens.count(("/.bw/para", emu.O_DIRECT | emu.O_CLOEXEC | 2)), 0, label)
        # a memory card with a partition called para is not looked at
        w = emu.World(para_with(bytes(2048)))
        w.sysfs = emu.sysfs_tree({1: ("para", 1024)}, disk="mmcblk1")
        self.go(w)
        self.assertEqual(w.para_writes, [])
        self.assertIn("did not appear", self.log(w))

    def test_16_garbled_sysfs_entries_are_refused(self):
        good = emu.sysfs_tree()
        base = "class/block/mmcblk0p11/"
        for label, uevent in {
            "no MAJOR": "MINOR=3\nPARTNAME=para\n",
            "no MINOR": "MAJOR=259\nPARTNAME=para\n",
            "MAJOR not a number": "MAJOR=2x9\nMINOR=3\nPARTNAME=para\n",
            "MAJOR zero": "MAJOR=0\nMINOR=3\nPARTNAME=para\n",
            "huge MINOR": "MAJOR=259\nMINOR=99999999\nPARTNAME=para\n",
            "name inside another field": "MAJOR=259\nMINOR=3\nXPARTNAME=para\nPARTNAME=logo\n",
        }.items():
            w = emu.World(para_with(bytes(2048)))
            w.sysfs = dict(good)
            w.sysfs[base + "uevent"] = uevent
            self.go(w)
            self.assertEqual(w.para_writes, [], label)
        w = emu.World(para_with(bytes(2048)))
        w.sysfs = dict(good)
        del w.sysfs[base + "size"]
        self.go(w)
        self.assertEqual(w.para_writes, [])

    def test_17_wrong_device_behind_the_number(self):
        w = emu.World(para_with(bytes(2048)))
        w.para_dev = (259, 99)                                   # the node the wrapper makes leads nowhere
        self.go(w)
        self.assertEqual(w.para_writes, [])
        self.assertIn("ERROR open para errno 6", self.log(w))

    # ---- devices that refuse or fail
    def test_20_read_only_device(self):
        for knob, err, text in (("open:para", "EACCES", "open para errno 13"), ("open:para", "EROFS", "open para errno 30"),
                                ("write:para", "EPERM", "write para errno 1"), ("write:para", "EIO", "write para errno 5")):
            w = emu.World(para_with(bytes(2048)))
            w.fail[knob] = err
            self.go(w)
            self.assertEqual(bytes(w.para[:2048]), bytes(2048))
            self.assertIn("ERROR " + text, self.log(w))
            self.assertEqual(w.exec[3], 0, "an error must not cost time")

    def test_21_every_single_failing_step_still_ends_in_init_real(self):
        steps = ["fork", "unshare", "mkdir", "mkdir:dir", "mkdir:sys", "mknod", "mknod:kmsg", "mknod:para", "open", "open:kmsg",
                 "open:para", "mount", "read", "read:sysfs", "read:para", "lseek", "write", "write:kmsg", "write:para",
                 "fsync", "close", "unlink", "unlink:para", "rmdir", "umount2", "wait4", "nanosleep", "kill"]
        for step in steps:
            for err in ("EIO", "EACCES", "ENOMEM", "EINVAL"):
                w = emu.World(para_with(bytes(2048)))
                w.fail[step] = err
                # a failed clean-up step may leave /.bw behind; that is the one allowed leftover
                with self.subTest(step=step, err=err):
                    self.go(w, leftovers=step.split(":")[0] in ("unlink", "rmdir", "umount2"))
                self.assertEqual(w.exec[0], "/init.real", step)
                self.assertLessEqual(w.exec[3], 5000, step)

    def test_22_fork_failing_goes_straight_on(self):
        w = emu.World(para_with(bytes(2048)))
        w.fail["fork"] = "EAGAIN"
        self.go(w)
        self.assertEqual([t[1] for t in w.trace], ["fork", "execve"])
        self.assertEqual(w.para_writes, [])

    def test_23_device_without_direct_access_falls_back(self):
        w = emu.World(para_with(bytes(2048)))
        w.no_direct = True
        self.go(w)
        self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE)
        self.assertEqual([f & emu.O_DIRECT for p, f in w.opens if p == "/.bw/para"], [emu.O_DIRECT, 0])

    def test_24_reads_that_come_in_pieces(self):
        w = emu.World(para_with(bytes(2048)))
        w.short_read = True
        self.go(w)
        self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE)
        w = emu.World(para_with(note(b"boot-recovery", b"", b"recovery\n--wipe_data\n")))
        w.short_read = True
        self.go(w)
        self.assertEqual(w.para_writes, [])

    def test_25_write_cut_short_is_reported_and_harmless(self):
        w = emu.World(para_with(bytes(2048)))
        w.short_write = True
        self.go(w)
        self.assertIn("ERROR write para", self.log(w))
        self.assertEqual(len(w.para_writes), 1, "no second try")
        # over an all-zero note, any first part of our note IS our note
        self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE)

    def test_26_write_that_does_not_stick_is_reported(self):
        w = emu.World(para_with(bytes(2048)))
        w.lying_write = True
        self.go(w)
        self.assertIn("does not read back as ours", self.log(w))
        self.assertNotIn("read back ok", self.log(w))

    def test_27_sync_failing_is_reported(self):
        w = emu.World(para_with(bytes(2048)))
        w.fail["fsync"] = "EIO"
        self.go(w)
        self.assertIn("ERROR fsync para errno 5", self.log(w))

    def test_28_no_kernel_log_available_still_works(self):
        for knob in ("mknod:kmsg", "open:kmsg", "write:kmsg"):
            w = emu.World(para_with(bytes(2048)))
            w.fail[knob] = "EACCES"
            self.go(w)
            self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE, knob)
            self.assertEqual(w.kmsg, [])

    def test_29_leftover_work_directory_from_an_earlier_run(self):
        w = emu.World(para_with(bytes(2048)))
        w.fs.update({"/.bw": "dir", "/.bw/sys": "dir", "/.bw/para": "node", "/.bw/kmsg": "node"})
        w.devs.update({"/.bw/para": ("blk", 179, 9), "/.bw/kmsg": ("chr", 1, 3)})     # stale: `boot`, and /dev/null
        before = dict(w.fs)
        self.go(w, leftovers=True)
        self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE)
        self.assertEqual({k: v for k, v in before.items() if not k.startswith("/.bw")}, w.fs)   # and it tidied up
        self.assertEqual((w.mounts, w.child_mounts, w.devs), ({}, {}, {}))

    def test_30_sysfs_cannot_be_mounted(self):
        w = emu.World(para_with(bytes(2048)))
        w.fail["mount"] = "EPERM"
        self.go(w)
        self.assertEqual(w.para_writes, [])
        self.assertIn("ERROR mount sysfs errno 1", self.log(w))
        self.assertEqual(w.exec[3], 0)

    def test_32_no_mount_table_of_its_own_means_no_mount_and_no_work(self):
        w = emu.World(para_with(bytes(2048)))
        w.fail["unshare"] = "EPERM"
        self.go(w)
        self.assertEqual([t for t in w.trace if t[1] == "mount"], [])
        self.assertEqual(w.para_writes, [])
        self.assertIn("ERROR unshare errno 1", self.log(w))
        self.assertEqual(w.exec[3], 0)

    def test_33_the_mount_is_made_only_after_taking_an_own_mount_table(self):
        w = self.go(emu.World(para_with(bytes(2048))))
        names = [t[1] for t in w.trace if t[0] == "child"]
        self.assertLess(names.index("unshare"), names.index("mount"))
        self.assertEqual(names.count("unshare"), 1)

    def test_31_never_mounts_on_the_real_sys(self):
        w = self.go(emu.World(para_with(bytes(2048))))
        mounts = [t[2] for t in w.trace if t[1] == "mount"]
        self.assertEqual(mounts, ["sysfs on /.bw/sys type sysfs"])

    # ---- a device that hangs: the parent's 5 s limit
    def test_40_child_hanging_anywhere_is_cut_off_at_5_seconds(self):
        for where in ("unshare", "mkdir", "mknod", "mount", "open", "open:para", "read:sysfs", "read:para", "write:para", "write:kmsg",
                      "fsync", "lseek", "umount2", "rmdir", "close", "unlink"):
            w = emu.World(para_with(bytes(2048)))
            w.hang = where
            self.go(w)
            self.assertTrue(w.child_hung, where)
            self.assertEqual(w.exec[3], 5000, where)
            self.assertEqual(w.mounts, {}, "hung at %s: pid 1 must see no mount of ours" % where)
            self.assertEqual([(k[0], k[1]) for k in w.killed], [(100, 9)], where)
            parent = [t[1] for t in w.trace if t[0] == "parent"]
            self.assertEqual(parent, ["fork"] + ["wait4", "nanosleep"] * 100 + ["kill", "execve"], where)

    def test_41_hang_after_the_write_leaves_a_whole_note(self):
        w = emu.World(para_with(bytes(2048)))
        w.hang = "fsync"
        self.go(w)
        self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE)

    def test_42_slow_then_hanging(self):
        w = emu.World(para_with(bytes(2048)))
        w.sysfs_from_ms = 2000
        w.hang = "read:para"
        self.go(w)
        self.assertEqual(w.exec[3], 5000)
        self.assertEqual(w.para_writes, [])
        self.assertEqual(w.mounts, {})
        self.assertEqual(w.child_mounts, {"/.bw/sys": "sysfs"})      # stuck with it mounted, but only in its own table

    # ---- the real init
    def test_50_arguments_and_environment_pass_through(self):
        global ARGV, ENVP
        saved = ARGV, ENVP
        try:
            for argv, envp in ((("/init",), ()), (("/init", "selinux_setup"), ("A=1",)),
                               (("/init", "a", "b", "c", "d", "e"), tuple("V%d=%s" % (i, "x" * i) for i in range(40)))):
                ARGV, ENVP = argv, envp
                self.go(emu.World(para_with(bytes(2048))))
        finally:
            ARGV, ENVP = saved

    def test_51_init_real_missing_ends_the_program_instead_of_looping(self):
        w = emu.World(para_with(bytes(2048)))
        del w.fs["/init.real"]
        fs = dict(w.fs)
        emu.run(ELF, w, ARGV, ENVP)
        self.assertEqual(w.exec[0], "/init.real")
        self.assertEqual(w.exit_codes.get("parent"), 127)
        self.assertEqual(bytes(w.para[:2048]), emu.PLAIN_NOTE, "the note is armed before, so the restart leads to recovery")
        self.assertEqual(w.fs, fs)

    def test_52_only_the_expected_system_calls_and_no_others(self):
        seen = set()
        for hang, fail in ((None, {}), ("read:para", {}), (None, {"fork": "EAGAIN"}), (None, {"open:para": "EACCES"})):
            w = emu.World(para_with(bytes(2048)))
            w.hang, w.fail = hang, dict(fail)
            self.go(w)
            seen |= {t[1] for t in w.trace}
        self.assertEqual(seen, set(emu.SYSCALLS.values()))

    def test_53_program_is_small_and_plain(self):
        self.assertEqual(bv.elf_problems(ELF), [])
        self.assertLess(len(ELF), 16384)
        for needle in (b"/system", b"/data", b"/dev/block", b"mmcblk1", b"/bin/sh"):
            self.assertNotIn(needle, ELF)
        for needle in (b"/init.real\0", b"/.bw/para\0", b"PARTNAME=\0", b"mmcblk0p\0", b"sysfs\0"):
            self.assertIn(needle, ELF)


# ============================================================================ Part D: the rig itself
class D_RigCatchesBrokenWrappers(unittest.TestCase):
    """Deliberately broken copies of the wrapper must FAIL the checks of part B. This shows that the
    rig (the ARM interpreter and the stand-in kernel) really sees what the program does."""
    BROKEN = {
        "writes 512 bytes too many": ("r = sc(NR_write, fd, (long)want, NOTE_SIZE, 0, 0);",
                                      "r = sc(NR_write, fd, (long)want, NOTE_SIZE + 512, 0, 0);"),
        "writes over a foreign note": ("    if (!zero) {", "    if (!zero && 0) {"),
        "writes without looking": ("    if (ours) {", "    zero = 1;\n    if (ours && 0) {"),
        "starts the wrong program": ('static const char REAL[] = "/init.real";', 'static const char REAL[] = "/init.reel";'),
        "drops the first argument": ("(long)REAL, (long)argv, (long)envp", "(long)REAL, (long)(argv + 1), (long)envp"),
        "drops the environment": ("(long)REAL, (long)argv, (long)envp", "(long)REAL, (long)argv, (long)(envp + 1)"),
        "waits 50 s for a hung child": ("#define PARENT_POLLS 100 ", "#define PARENT_POLLS 1000 "),
        "never cuts a hung child off": ("if (r != 0) break;", "if (r > 0) break; i = 0;"),
        "mounts where pid 1 can see it": ("long r = sc(NR_unshare, CLONE_NEWNS, 0, 0, 0, 0);", "long r = 0;"),
        "mounts on the real /sys": ('static const char SYS[] = "/.bw/sys";', 'static const char SYS[] = "/sys";'),
        "leaves the device file open across exec": ("O_RDWR | O_DIRECT | O_CLOEXEC", "O_RDWR | O_DIRECT"),
        "does the work in pid 1 itself": ("    if (pid == 0) {\n        child();", "    if (pid > 0) {\n        child();"),
        "leaves its work directory behind": ("    sc(NR_rmdir, (long)DIR, 0, 0, 0, 0);\n", ""),
        "takes any partition whose name starts with para": ("    return *v == '\\n' || *v == 0;", "    return 1;"),
        "does not check the size": ("if (number(text) != PARA_SECTORS) return -3;", ""),
    }

    def worlds(self):
        """(label, world, should the note end up armed?)"""
        yield "empty", emu.World(para_with(bytes(2048))), True
        yield "foreign", emu.World(para_with(note(b"boot-recovery", b"", b"recovery\n--wipe_data\n"))), False
        w = emu.World(para_with(bytes(2048)))
        w.hang = "read:para"
        yield "hang", w, False
        w = emu.World(para_with(bytes(2048)))                 # the device behind a look-alike name
        w.sysfs = emu.sysfs_tree({5: ("parameters", 1024)})
        w.para_dev = emu.devnum(5)
        yield "look-alike name", w, False
        w = emu.World(para_with(bytes(2048)))                 # the right name on a partition of the wrong size
        w.sysfs = emu.sysfs_tree({11: ("para", 4096)})
        yield "wrong size", w, False

    def run_all(self, b):
        for label, world, armed in self.worlds():
            try:
                b.go(world)
                b.assertEqual(bytes(world.para[:2048]) == emu.PLAIN_NOTE, armed, "note armed?")
            except (AssertionError, emu.EmuError) as e:
                yield "%s: %s" % (label, str(e).splitlines()[0][:90])

    def test_01_the_unbroken_wrapper_passes_these_worlds(self):
        self.assertEqual(list(self.run_all(B_Wrapper("go"))), [])

    def test_02_every_broken_wrapper_is_caught(self):
        global ELF
        with open(bb.DEF_SRC) as f:
            src = f.read()
        good = ELF
        b = B_Wrapper("go")
        try:
            for label, (old, new) in self.BROKEN.items():
                self.assertEqual(src.count(old), 1, "source line for %r not found exactly once" % label)
                path = os.path.join(TMP, "broken.c")
                with open(path, "w") as f:
                    f.write(src.replace(old, new))
                ELF = bb.compile_wrapper(path)
                self.assertNotEqual(ELF, good, label)
                caught = list(self.run_all(b))
                self.assertTrue(caught, "a wrapper that %s passed every check" % label)
                print("\n      broken wrapper that %s -> caught (%s)" % (label, caught[0]), end="")
        finally:
            ELF = good


# ============================================================================ Part C: the proof about init
class C_StockInit(unittest.TestCase):
    def test_01_restart_word_has_exactly_one_use(self):
        p = subprocess.run([sys.executable, "-I", SCAN], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(p.stdout.strip().endswith("RESULT: PROVEN"))
        self.assertNotIn("FAIL", p.stdout)

    def test_02_proof_notices_a_different_program(self):
        stock = rd(STOCK)
        ft, vb = bb.stock_vbmeta(stock)
        boot = bb.unpack_boot(stock[:ft["original_image_size"]])
        entries = bb.cpio_parse(bb.gunzip(boot["parts"]["ramdisk"]))
        e = [x for x in entries if x["name"] == "init"][0]
        d = bytearray(e["data"])
        # make a second place form the word's address: copy the literal the initialiser uses over a
        # literal that another add-pc reads would be fragile; changing the program at all must be enough.
        d[0x42280 + 0x100] ^= 0xFF
        e["data"] = bytes(d)
        img = bb.add_footer(bb.pack_boot(boot, bb.gzip_like_stock(bb.cpio_build(entries))), vb, avblib.load_private_key(KEY))
        p = subprocess.run([sys.executable, "-I", SCAN, "--boot", tmpfile("scan.img", img)], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("NOT PROVEN", p.stdout)


if __name__ == "__main__":
    if WHY_SKIP:
        print("SKIP test_bootwrap.py: " + WHY_SKIP)
        sys.exit(0)
    unittest.main(verbosity=2)
