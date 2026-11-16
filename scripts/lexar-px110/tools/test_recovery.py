#!/usr/bin/env python3
"""Offline tests for the recovery build (tests 1-15).

    python3 -I tools/test_recovery.py

Needs your own backup (BACKUP_DIR) and the fetched keys (KEY_DIR); without them it prints SKIP and exits 0.
Never touches the frame. Tests 7-13 run the real src/recovery/rescue.sh with /bin/sh against
stand-in files in a temporary folder (removed afterwards); `mount`, `umount`, `reboot`, `stop`,
`sleep` and `sync` are replaced there by stubs that only record that they were called (so waits take no time).
Reads BUILD_DIR/out-recovery/ (build it first with recbuild.py) and writes nothing else.
"""
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import px110conf  # noqa: E402
import recbuild   # noqa: E402  (the builder, for tests 3 and 6)
import recverify  # noqa: E402  (the independent checker's own cpio reader, for tests 6 and 14)

BACKUP = px110conf.path("BACKUP_DIR")
STOCK = os.path.join(BACKUP, "recovery.img")
OUT = px110conf.build_dir("out-recovery")
RESIGNED = os.path.join(OUT, "recovery-stock-resigned.img")
RESCUE_IMG = os.path.join(OUT, "recovery-rescue.img")
SRC = os.path.join(px110conf.SRC, "recovery")
SCRIPT = os.path.join(SRC, "rescue.sh")
BUILD = [sys.executable, "-I", os.path.join(HERE, "recbuild.py")]
VERIFY = [sys.executable, "-I", os.path.join(HERE, "recverify.py")]

PRODUCT_OFF, PRODUCT_LEN = 4096 * 32512, 109813760
SIZES = {"vbmeta_system": 4194304, "vbmeta": 4194304, "logo": 8388608, "boot": 33554432}

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ((" -- " + detail) if detail else ""))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path, off=0, length=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        f.seek(off)
        left = os.path.getsize(path) - off if length is None else length
        while left > 0:
            b = f.read(min(1 << 20, left))
            if not b:
                break
            h.update(b)
            left -= len(b)
    return h.hexdigest()


def verify(image, *extra):
    """Run the independent checker. Returns (passed, failed-check names, full output)."""
    r = subprocess.run(VERIFY + [image] + list(extra), capture_output=True, text=True)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    m = re.match(r"RESULT: FAIL \((.*)\)", last)
    return r.returncode == 0 and last == "RESULT: PASS", (m.group(1).split(",") if m else []), r.stdout + r.stderr


def flipped(src, dst, off):
    d = bytearray(open(src, "rb").read())
    d[off] ^= 0x01
    open(dst, "wb").write(d)


# ---------------------------------------------------------------- stand-in world for rescue.sh
def clone(src, dst):
    """Copy a folder; on APFS this is a copy-on-write clone, so it is quick and takes no space."""
    if subprocess.run(["cp", "-cR", src, dst], capture_output=True).returncode != 0:
        shutil.copytree(src, dst)


def make_base(tmp):
    """Stand-in partitions (real stock contents), a `para` with the note set, gzip'd known-good copies."""
    base = os.path.join(tmp, "base")
    by, store = os.path.join(base, "by-name"), os.path.join(base, "cache", "rescue")
    os.makedirs(by)
    os.makedirs(store)
    good = {}
    for name in SIZES:
        data = open(os.path.join(BACKUP, name + ".img"), "rb").read()
        assert len(data) == SIZES[name]
        open(os.path.join(by, name), "wb").write(data)
        good[name] = data
    with open(os.path.join(BACKUP, "super.img"), "rb") as f:
        f.seek(PRODUCT_OFF)
        product = f.read(PRODUCT_LEN)
    good["product"] = product
    with open(os.path.join(by, "super"), "wb") as f:      # sparse: only the product region and two guards are real
        f.seek(PRODUCT_OFF - 4096)
        f.write(b"\xA5" * 4096 + product + b"\x5A" * 4096)
    for name in ("lk", "recovery"):                        # must never be written
        shutil.copy(os.path.join(BACKUP, name + ".img"), os.path.join(by, name))
    para = bytearray(open(os.path.join(BACKUP, "para.img"), "rb").read())
    para[0:13] = b"boot-recovery"
    para[64:64 + 9] = b"recovery\n"
    open(os.path.join(by, "para"), "wb").write(para)
    info = {}
    for name, data in good.items():
        gz = gzip.compress(data, 6, mtime=0)
        open(os.path.join(store, name + ".gz"), "wb").write(gz)
        info[name] = {"good": sha(data), "gz": sha(gz), "file": name + ".gz"}
    stubs = os.path.join(base, "stubs")
    os.makedirs(stubs)
    for cmd, status in (("reboot", 0), ("mount", 1), ("umount", 0), ("sleep", 0), ("stop", 0), ("sync", 0)):
        p = os.path.join(stubs, cmd)
        open(p, "w").write('#!/bin/sh\necho "%s $*" >> "$RESCUE_TEST_CALLS"\nexit %d\n' % (cmd, status))
        os.chmod(p, 0o755)
    return base, info, good


class World:
    def __init__(self, tmp, base, label):
        self.dir = os.path.join(tmp, label)
        clone(base, self.dir)
        self.by = os.path.join(self.dir, "by-name")
        self.cache = os.path.join(self.dir, "cache")
        self.store = os.path.join(self.cache, "rescue")
        self.calls = os.path.join(self.dir, "calls.txt")
        self.snap = os.path.join(self.dir, "snap.note")
        self.own_session = False     # True for the cut-off test, whose stub kills the script's whole process group
        self.before = None

    def write_list(self, entries, head="rescue-list 1", tail="end", guarded=True):
        # guarded=True: the list carries the `guarded` line, i.e. "restore at once" (the behaviour the older tests
        # check); guarded=False is a list as the always-armed note meets it: the ladder decides.
        lines = ([head] if head else []) + (["guarded"] if guarded else []) + [" ".join(e) for e in entries] + ([tail] if tail else [])
        open(os.path.join(self.store, "list"), "w").write("\n".join(lines) + "\n")

    def snapshot(self):
        return {n: (sha_file(os.path.join(self.by, n)), os.stat(os.path.join(self.by, n)).st_mtime_ns)
                for n in sorted(os.listdir(self.by))}

    def run(self, *args, **env_extra):
        self.before = self.snapshot()
        env = {"PATH": os.path.join(self.dir, "stubs") + ":/usr/bin:/bin:/usr/sbin:/sbin",
               "RESCUE_BYNAME": self.by, "RESCUE_MNT": self.cache, "RESCUE_MOUNT": "0", "RESCUE_WAIT": "1",
               "RESCUE_TMPLOG": os.path.join(self.dir, "tmp-rescue.log"),
               "RESCUE_TMPMARK": os.path.join(self.dir, "tmp-rescue.marker"), "RESCUE_TEST_CALLS": self.calls,
               # always inside the temporary folder: a stray /tmp/rescue.note or a real /dev/kmsg can never matter
               "RESCUE_SNAP": self.snap, "RESCUE_KMSG": os.path.join(self.dir, "no-kmsg")}
        self.cache_before = self.cache_listing()
        env.update(env_extra)
        r = subprocess.run(["/bin/sh", SCRIPT] + list(args), env=env, start_new_session=self.own_session, capture_output=True, text=True, cwd=self.dir)
        self.after = self.snapshot()
        self.status = r.returncode
        self.stderr = r.stderr
        return r

    def changed(self):
        """Names of stand-in partitions whose content changed."""
        return sorted(n for n in self.before if self.before[n][0] != self.after[n][0])

    def touched(self):
        """Names of stand-in partitions that were written at all (content or modification time)."""
        return sorted(n for n in self.before if self.before[n] != self.after[n])

    def reboots(self):
        if not os.path.exists(self.calls):
            return 0
        return sum(1 for l in open(self.calls) if l.startswith("reboot"))

    def cache_listing(self):
        out = []
        for d, _, files in os.walk(self.cache):
            out += [(os.path.relpath(os.path.join(d, f), self.cache), os.stat(os.path.join(d, f)).st_mtime_ns) for f in files]
        return sorted(out)

    def cache_untouched(self):
        return self.cache_listing() == self.cache_before

    def call_list(self, cmd=None):
        if not os.path.exists(self.calls):
            return []
        lines = [l.rstrip("\n") for l in open(self.calls)]
        return [l for l in lines if cmd is None or l.split()[0] == cmd]

    def set_snapshot(self, command=b"boot-recovery", args=b""):
        open(self.snap, "wb").write((command.ljust(32, b"\0") + bytes(32) + args.ljust(768, b"\0")).ljust(2048, b"\0"))

    def set_note(self, command=b"boot-recovery", args=b""):
        with open(os.path.join(self.by, "para"), "r+b") as f:
            f.write(command.ljust(32, b"\0") + bytes(32) + args.ljust(768, b"\0"))

    def stops(self):
        """How many times the script stopped the stock recovery program."""
        if not os.path.exists(self.calls):
            return 0
        return sum(1 for l in open(self.calls) if l.strip() == "stop recovery")

    def marker(self):
        for p in (os.path.join(self.cache, "rescue.marker"), os.path.join(self.dir, "tmp-rescue.marker")):
            if os.path.exists(p):
                return open(p).read()
        return ""

    def log(self):
        for p in (os.path.join(self.cache, "rescue.log"), os.path.join(self.dir, "tmp-rescue.log")):
            if os.path.exists(p):
                return open(p).read()
        return ""

    def note(self):
        return open(os.path.join(self.by, "para"), "rb").read(32)

    def corrupt(self, name, off=1000):
        with open(os.path.join(self.by, "super" if name == "product" else name), "r+b") as f:
            f.seek((PRODUCT_OFF if name == "product" else 0) + off)
            b = f.read(4)
            f.seek(-4, 1)
            f.write(bytes(x ^ 0xFF for x in b))


def entry(info, name, want=None):
    i = info[name]
    return (name, want or i["good"], i["file"], i["gz"], i["good"])


NOTE_SET = b"boot-recovery" + b"\0" * 19
NOTE_CLEAR = b"\0" * 32
MARK_HEAD = "rescue.sh run\ntime: "


def elf_needed(data):
    """The DT_NEEDED names of a 32-bit little-endian ELF file (what a dynamic program loads at start)."""
    import struct
    assert data[:4] == b"\x7fELF" and data[4] == 1 and data[5] == 1
    shoff, = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x2E)
    secs = [struct.unpack_from("<IIIIIIIIII", data, shoff + i * shentsize) for i in range(shnum)]
    needed, strtab = [], None
    for name, typ, flags, addr, off, size, link, info, align, entsize in secs:
        if typ == 6:                                    # SHT_DYNAMIC
            strtab = secs[link]
            for j in range(off, off + size, 8):
                tag, val = struct.unpack_from("<iI", data, j)
                if tag == 1:
                    needed.append(val)
    out = []
    for val in needed:
        a = strtab[4] + val
        out.append(data[a:data.index(b"\0", a)].decode())
    return out


# ---------------------------------------------------------------- test 14 helper
def blank_strings(text):
    """Return the script with comments and quoted text blanked, keeping $( ) command substitutions."""
    out, stack, i, n = [], ["n"], 0, len(text)
    while i < n:
        c, mode = text[i], stack[-1]
        if mode == "s":
            if c == "'":
                stack.pop()
            out.append(" " if c != "\n" else c)
        elif mode in ("d", "a"):
            if text.startswith("$((", i):
                stack.append("a"); out.append("   "); i += 3; continue
            if text.startswith("$(", i):
                stack.append("n"); out.append("$("); i += 2; continue
            if mode == "d" and c == "\\":
                out.append("  "); i += 2; continue
            if mode == "d" and c == '"':
                stack.pop()
            elif mode == "a" and text.startswith("))", i):
                stack.pop(); out.append("  "); i += 2; continue
            out.append(" " if c != "\n" else c)
        else:
            if c == "#" and (i == 0 or text[i - 1] in " \t\n"):
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if c == "'":
                stack.append("s"); out.append(" ")
            elif c == '"':
                stack.append("d"); out.append(" ")
            elif text.startswith("$((", i):
                stack.append("a"); out.append("   "); i += 3; continue
            elif text.startswith("$(", i):
                stack.append("n"); out.append("$("); i += 2; continue
            elif c == ")" and len(stack) > 1:
                stack.pop(); out.append(")")
            else:
                out.append(c)
        i += 1
    return "".join(out)


SHELL_WORDS = set("if then else elif fi while do done case esac in return exit continue break shift set read "
                  "echo [ : true false test".split())


def script_commands(text):
    """Every word that the script uses in command position, minus shell words and its own functions."""
    clean = blank_strings(text)
    funcs = set(re.findall(r"^(\w+)\(\) \{", clean, re.M))
    found, in_case = set(), False
    for line in clean.split("\n"):
        s = line.strip()
        if in_case:
            if s == "esac" or s.startswith("esac"):
                in_case = False
                continue
            if ")" in s:                        # one case arm per line: drop the pattern
                s = s.split(")", 1)[1]
        if re.match(r"case\b", s):
            in_case = "esac" not in s
            continue
        s = re.sub(r"^\w+\(\) \{", "", s)
        for seg in re.split(r"[;|&]|\$\(", s):             # each piece starts a new simple command
            words = seg.split()
            while words and words[0] in ("if", "then", "else", "elif", "while", "do", "!"):
                words.pop(0)                               # a command follows these
            if words and re.fullmatch(r"[A-Za-z_\[:][\w.\-]*", words[0]):
                found.add(words[0])                        # assignments (x=...) and $VAR do not match
    return sorted(found - SHELL_WORDS - funcs), sorted(funcs)


# ---------------------------------------------------------------- the tests
def main():
    why = px110conf.missing(backup_files=("recovery.img", "lk.img", "super.img", "para.img", "vbmeta.img", "vbmeta_system.img",
                                          "logo.img", "boot.img", "mmcblk0boot0.img"),
                            key_files=("recovery_prvk.pem", "root_prvk.pem", "img_prvk.pem"))
    if why:
        print("SKIP test_recovery.py: " + why)
        return 0
    for p in (RESIGNED, RESCUE_IMG):
        if not os.path.exists(p):
            print("missing %s: run  python3 -I tools/recbuild.py  first" % p)
            return 1
    stock = open(STOCK, "rb").read()
    with tempfile.TemporaryDirectory() as tmp:
        # 1
        ok, failed, out = verify(STOCK)
        check("1. checker on the stock recovery.img", ok, "failed: %s" % failed if failed else "")

        # 2
        t2 = os.path.join(tmp, "resigned.img")
        r = subprocess.run(BUILD + ["--only", "resigned", "--out", t2], capture_output=True, text=True)
        check("2a. stock taken apart, rebuilt and re-signed with the published key is byte-identical to stock",
              r.returncode == 0 and open(t2, "rb").read() == stock)
        check("2b. out-recovery/recovery-stock-resigned.img is byte-identical to stock",
              open(RESIGNED, "rb").read() == stock)

        # 3
        ft, vb = recbuild.stock_vbmeta(stock)
        boot = recbuild.unpack_boot(stock[:ft["original_image_size"]])
        gz = boot["parts"]["ramdisk"]
        cpio = recbuild.gunzip(gz)
        entries, _ = recbuild.cpio_parse(cpio)
        rebuilt = recbuild.cpio_build(entries)
        check("3a. stock ramdisk unpacked and repacked unchanged: decompressed archive byte-identical",
              rebuilt == cpio, "%d entries, %d bytes" % (len(entries), len(cpio)))
        check("3b. (extra) recompressed ramdisk and whole repacked boot image byte-identical too",
              recbuild.gzip_like_stock(rebuilt) == gz and recbuild.pack_boot(boot, gz) == stock[:ft["original_image_size"]])

        # 4
        kernel_off = 2048 + 1000
        ramdisk_off = 2048 + recbuild._pages(len(boot["parts"]["kernel"]), 2048) + 5000
        sig_off = ft["vbmeta_offset"] + 256 + 32 + 10              # inside the 256-byte signature
        digest_off = ft["vbmeta_offset"] + 256 + 320 + 200         # inside the descriptor's digest
        footer_off = len(stock) - 64 + 20                          # inside the AVBf footer's size fields
        for label, off, want in (("4a. one kernel byte flipped: fails at the image hash", kernel_off, "image-hash"),
                                 ("4b. one ramdisk byte flipped: fails at the image hash", ramdisk_off, "image-hash"),
                                 ("4c. one footer byte flipped (in the signature): fails at the signature", sig_off, "signature"),
                                 ("4d. (extra) one byte of the stored digest flipped: fails at the vbmeta hash", digest_off, "vbmeta-hash"),
                                 ("4e. (extra) one byte of the 64-byte AVB footer flipped: fails at the footer", footer_off, "footer")):
            p = os.path.join(tmp, "flip.img")
            flipped(STOCK, p, off)
            ok, failed, out = verify(p)
            check(label, not ok and want in failed, "byte %d, failed checks: %s" % (off, ",".join(failed)))

        # 5
        tkey = os.path.join(tmp, "throwaway.pem")
        subprocess.run(["openssl", "genrsa", "-out", tkey, "2048"], capture_output=True, check=True)
        t5 = os.path.join(tmp, "otherkey.img")
        r = subprocess.run(BUILD + ["--only", "rescue", "--key", tkey, "--out", t5], capture_output=True, text=True)
        check("5a. the builder refuses a key that is not the stock recovery key", r.returncode != 0 and not os.path.exists(t5))
        r = subprocess.run(BUILD + ["--only", "rescue", "--key", tkey, "--out", t5, "--allow-other-key"], capture_output=True, text=True)
        ok, failed, out = verify(t5) if r.returncode == 0 else (True, [], r.stderr)
        check("5b. image signed with a throwaway key: checker fails, and only because the key is not in lk.img",
              r.returncode == 0 and not ok and failed == ["key-in-lk"], "failed checks: %s" % ",".join(failed))

        # 6
        changed = ",".join(recbuild.CHANGED_FILES)
        ok, failed, out = verify(RESCUE_IMG, "--stock", STOCK, "--expect-changed", changed)
        same = all(re.search(r"^same-%s\s+ok" % n, out, re.M) for n in ("kernel", "dtb", "recovery-dtbo"))
        check("6a. recovery-rescue.img passes the checker; kernel, dtb, dtbo identical to stock; ramdisk differs only in "
              + changed, ok and same, "failed: %s" % failed if failed else "")
        check("6b. recovery-rescue.img is exactly 32 MiB", os.path.getsize(RESCUE_IMG) == 33554432)
        t6 = os.path.join(tmp, "rebuilt.img")
        r = subprocess.run(BUILD + ["--only", "rescue", "--out", t6], capture_output=True, text=True)
        check("6c. (extra) rebuilding from src/recovery gives the same file, byte for byte",
              r.returncode == 0 and open(t6, "rb").read() == open(RESCUE_IMG, "rb").read())
        rimg = open(RESCUE_IMG, "rb").read()
        new, _ = recverify.read_cpio(recverify.read_boot(rimg, recverify.read_footer(rimg)["orig"])[0]["ramdisk"])
        old, old_order = recverify.read_cpio(gz)
        rc = new[recbuild.INIT_RC][1].decode()
        props_new, props_old = new["prop.default"][1].decode().split("\n"), old["prop.default"][1].decode().split("\n")
        prop_diff = [(a, b) for a, b in zip(props_old, props_new) if a != b]
        check("6d. (extra) in the image: rescue.sh equals the source file; prop.default differs in one line (ro.adb.secure=0); "
              "adbd runs in the recovery domain without --root_seclabel; the stock recovery program is byte-identical and its "
              "service unchanged; one service (rescue) added",
              new["system/bin/rescue.sh"][1] == open(SCRIPT, "rb").read()
              and len(props_new) == len(props_old) and prop_diff == [("ro.adb.secure=1", "ro.adb.secure=0")]
              and "service adbd /system/bin/adbd --device_banner=recovery\n    disabled\n    socket adbd stream 660 system system\n    seclabel u:r:recovery:s0\n" in rc
              and "root_seclabel" not in rc and "u:r:su:s0" not in rc
              and "service rescue /system/bin/sh /system/bin/rescue.sh\n    user root\n    group root\n    seclabel u:r:recovery:s0\n    oneshot\n" in rc
              and "service recovery /system/bin/recovery\n    socket recovery stream 422 system system\n    seclabel u:r:recovery:s0\n\nservice adbd" in rc
              and rc.count("service ") == old[recbuild.INIT_RC][1].decode().count("service ") + 1
              and new["system/bin/recovery"] == old["system/bin/recovery"])
        adbd = new["system/bin/adbd"][1]
        need = elf_needed(adbd)
        libs = [n for n in need if "system/lib/" + n not in new]
        usb_rc = new["init.recovery.mt8167.rc"][1].decode()
        check("6f. (extra) root adb in recovery comes from the ramdisk's own adbd (kept byte for byte): every library it needs "
              "is in the ramdisk (%s), nothing missing; init starts it on sys.usb.config=adb and from init.recovery.mt8167.rc; "
              "its service has no `user` line (so root) and runs in the recovery domain; ro.adb.secure=0. Android's adbd is "
              "NOT used: it lives in the com.android.adbd APEX and would need the APEX's libraries and linker config"
              % " ".join(need),
              adbd == old["system/bin/adbd"][1] and need and not libs and "on property:sys.usb.config=adb\n    start adbd" in rc
              and "start adbd" in usb_rc and "service adbd /system/bin/adbd --device_banner=recovery\n    disabled\n    socket adbd stream 660 system system\n    seclabel u:r:recovery:s0\n" in rc,
              "missing libraries: %s" % libs if libs else "")
        sums = dict(reversed(l.split()) for l in open(os.path.join(OUT, "SHA256SUMS")) if l.strip())
        check("6e. (extra) SHA256SUMS matches both images",
              sums.get("recovery-rescue.img") == sha(rimg) and sums.get("recovery-stock-resigned.img") == sha(stock))

        # ---- rescue.sh against stand-in files
        base, info, good = make_base(tmp)
        all_names = ["product", "vbmeta_system", "vbmeta", "logo", "boot"]

        # 7
        w = World(tmp, base, "t7")
        w.write_list([entry(info, n) for n in all_names])
        w.run()
        log = w.log()
        check("7. all five partitions match: nothing written, note cleared, restart requested",
              w.status == 0 and w.touched() == ["para"] and w.note() == NOTE_CLEAR and w.reboots() == 1
              and all("%s: matches the expected hash" % n in log for n in all_names),
              "written: %s; restarts: %d" % (w.touched(), w.reboots()))
        m = w.marker()
        check("7b. (extra) the run leaves /cache/rescue.marker (time, note found, list accepted, nothing restored, restarting) "
              "and stopped the stock recovery program once before checking",
              m.startswith(MARK_HEAD) and "note at start: boot-recovery (ours)\n" in m and "list: accepted\n" in m
              and "restored: none\n" in m and "wrong but not restored: none\n" in m and m.endswith("state: finished; restarting\n")
              and w.stops() == 1, m.replace("\n", " | "))

        # 8
        w = World(tmp, base, "t8a")
        w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")])
        w.corrupt("vbmeta")
        w.run()
        log = w.log()
        check("8a. vbmeta wrong: only vbmeta rewritten, equals the known-good afterwards, logged, restart",
              w.status == 0 and w.touched() == ["para", "vbmeta"] and w.after["vbmeta"][0] == info["vbmeta"]["good"]
              and "vbmeta: MISMATCH" in log and "vbmeta: RESTORED" in log and w.reboots() == 1 and w.note() == NOTE_CLEAR,
              "written: %s" % w.touched())
        check("8a2. (extra) the marker names what was restored", "restored: vbmeta\n" in w.marker()
              and "wrong but not restored: none\n" in w.marker())
        w = World(tmp, base, "t8b")
        w.write_list([entry(info, n) for n in all_names])
        w.corrupt("product", off=50_000_000)
        w.run()
        sup = os.path.join(w.by, "super")
        guards = open(sup, "rb")
        guards.seek(PRODUCT_OFF - 4096); g1 = guards.read(4096)
        guards.seek(PRODUCT_OFF + PRODUCT_LEN); g2 = guards.read()
        check("8b. product region of super wrong: only that region rewritten, equals the known-good afterwards; "
              "the bytes just before and after it untouched; super not grown",
              w.status == 0 and w.touched() == ["para", "super"]
              and sha_file(sup, PRODUCT_OFF, PRODUCT_LEN) == info["product"]["good"]
              and g1 == b"\xA5" * 4096 and g2 == b"\x5A" * 4096 and w.after["super"][0] == sha_file(os.path.join(base, "by-name", "super"))
              and "product: RESTORED" in w.log() and w.reboots() == 1, "written: %s" % w.touched())
        w = World(tmp, base, "t8c")
        flashed = bytearray(good["logo"]); flashed[5000:5004] = b"NEW!"
        open(os.path.join(w.by, "logo"), "wb").write(flashed)
        w.write_list([entry(info, "logo", want=sha(bytes(flashed))), entry(info, "vbmeta")])
        w.run()
        check("8c. (extra) list expects a newly flashed image and the partition holds exactly that: left alone",
              w.status == 0 and w.touched() == ["para"] and w.reboots() == 1)

        # 9
        def corrupt_copy(w, how):
            p = os.path.join(w.store, "vbmeta.gz")
            if how == "file":                      # the .gz file itself damaged
                d = bytearray(open(p, "rb").read()); d[len(d) // 2] ^= 0x10; open(p, "wb").write(d)
                return entry(info, "vbmeta")
            if how == "content":                   # a valid .gz of the wrong content, listed with its own file hash
                d = bytearray(good["vbmeta"]); d[100] ^= 1; gzb = gzip.compress(bytes(d), 6, mtime=0); open(p, "wb").write(gzb)
                return ("vbmeta", info["vbmeta"]["good"], "vbmeta.gz", sha(gzb), info["vbmeta"]["good"])
            if how == "length":                    # consistent hashes, but not the partition's length
                d = good["vbmeta"][:-4096]; gzb = gzip.compress(d, 6, mtime=0); open(p, "wb").write(gzb)
                return ("vbmeta", info["vbmeta"]["good"], "vbmeta.gz", sha(gzb), sha(d))
            os.remove(p)                           # "missing"
            return entry(info, "vbmeta")
        for label, how, phrase in (("9a. known-good copy corrupt (.gz file hash wrong)", "file", "corrupt (file hash differs)"),
                                   ("9b. (extra) known-good copy unpacks to the wrong content", "content", "corrupt (unpacked hash differs)"),
                                   ("9c. (extra) known-good copy has the wrong length", "length", "wrong length"),
                                   ("9d. (extra) known-good copy missing", "missing", "is missing")):
            w = World(tmp, base, "t9" + how)
            e = corrupt_copy(w, how)
            w.write_list([e, entry(info, "logo")])
            w.corrupt("vbmeta")
            w.corrupt("logo")
            w.run()
            log = w.log()
            check(label + ": that partition not written, logged, the other one still restored; no restart while a listed partition is "
                  "still wrong: the script stays with our note armed",
                  w.status == 0 and w.touched() == ["logo", "para"] and phrase in log and "vbmeta: " in log
                  and "NOT restored" in log and "logo: RESTORED" in log and w.reboots() == 0 and w.note() == NOTE_SET
                  and "restored: logo\n" in w.marker() and "wrong but not restored: vbmeta\n" in w.marker(),
                  "written: %s" % w.touched())

        # 10
        w = World(tmp, base, "t10a")
        shutil.rmtree(w.store)
        w.corrupt("vbmeta")
        w.run()
        check("10a. no list (no store at all), plain note: the ladder starts (rung 1 recorded, store folder made), nothing "
              "written to a partition, note cleared (unarmed restart), restart",
              w.status == 0 and w.touched() == ["para"] and w.note() == NOTE_CLEAR and w.reboots() == 1 and "rung 1" in w.log()
              and w.stops() == 0 and open(os.path.join(w.store, "rung")).read() == "1\n")
        w = World(tmp, base, "t10b")
        w.write_list([entry(info, "vbmeta")])
        w.corrupt("vbmeta")
        w.run(RESCUE_MNT=os.path.join(w.dir, "no-such-cache"))
        check("10b. cache unreadable (folder absent): the ladder cannot be counted, so: nothing written, note left as it is, "
              "no restart, stock program stopped, logged",
              w.status == 0 and w.touched() == ["para"] and w.note() == NOTE_SET and w.reboots() == 0 and w.stops() == 1
              and "cache could not be mounted" in w.log() and "cannot be counted" in w.log())
        w = World(tmp, base, "t10c")
        w.write_list([entry(info, "vbmeta")])
        w.corrupt("vbmeta")
        open(os.path.join(w.by, "cache"), "wb").write(b"\0" * 4096)
        w.run(RESCUE_MOUNT="1")
        want_mount = "mount -t ext4 -o noatime,nosuid,nodev %s %s" % (os.path.join(w.by, "cache"), w.cache)
        check("10c. cache does not mount (mount fails every time): tried 5 times at the script's own directory, then "
              "nothing written, note left as it is, no restart (the ladder cannot be counted); nothing ever unmounted",
              w.status == 0 and w.touched() == ["para"] and w.note() == NOTE_SET and w.reboots() == 0
              and w.call_list("mount") == [want_mount] * 5 and w.call_list("umount") == []
              and "cache could not be mounted" in w.log())
        w = World(tmp, base, "t10c2")
        w.write_list([entry(info, "vbmeta")])
        w.corrupt("vbmeta")
        open(os.path.join(w.by, "cache"), "wb").write(b"\0" * 4096)
        open(os.path.join(w.dir, "stubs", "mount"), "w").write(
            '#!/bin/sh\necho "mount $*" >> "$RESCUE_TEST_CALLS"\nn=$(grep -c "^mount " "$RESCUE_TEST_CALLS")\n[ "$n" -ge 3 ]\n')
        w.run(RESCUE_MOUNT="1")
        want_mount = "mount -t ext4 -o noatime,nosuid,nodev %s %s" % (os.path.join(w.by, "cache"), w.cache)
        check("10c2. (extra) mount is 'busy' twice, then works: the script retries, restores from the store, and at the "
              "end unmounts only its own directory",
              w.status == 0 and w.touched() == ["para", "vbmeta"] and w.reboots() == 1
              and w.call_list("mount") == [want_mount] * 3 and w.call_list("umount") == ["umount " + w.cache]
              and "vbmeta: RESTORED" in w.log())
        text0 = open(SCRIPT).read()
        check("10c3. (extra) the script never names /cache (only the cache device and its own directory): its mount point is /tmp/rescue_cache and the store, log and "
              "marker are under it", "/cache" not in re.sub(r"(?m)^\s*#.*$", "", text0).replace("/tmp/rescue_cache", "").replace("$BYNAME/cache", "")
              and "MNT=${RESCUE_MNT:-/tmp/rescue_cache}" in text0 and "STORE=${RESCUE_STORE:-$MNT/rescue}" in text0
              and "NEWLOG=$MNT/rescue.log" in text0 and "MARKFILE=$MNT/rescue.marker" in text0)
        bad_lists = (
            ("10d. (extra) list cut short (no 'end' line)", dict(tail=None), None, "no 'end' line"),
            ("10e. (extra) list with a wrong first line", dict(head="rescue-list 2"), None, "first line"),
            ("10f. (extra) list with a malformed hash", {}, ("vbmeta", "XYZ", "vbmeta.gz", info["vbmeta"]["gz"], info["vbmeta"]["good"]), "malformed line"),
            ("10g. (extra) list with a path instead of a plain file name", {}, ("vbmeta", info["vbmeta"]["good"], "../by-name/lk", info["vbmeta"]["gz"], info["vbmeta"]["good"]), "malformed line"),
            ("10h. (extra) list naming one partition twice", {}, entry(info, "logo"), "listed twice"),
        )
        for label, kw, extra_entry, phrase in bad_lists:
            w = World(tmp, base, "t" + label[:3])
            w.write_list([entry(info, "logo")] + ([extra_entry] if extra_entry else []), **kw)
            w.corrupt("logo")
            w.corrupt("vbmeta")
            w.run()
            check(label + ": whole list refused, nothing written to a partition; a `guarded` flash cannot be vouched for by a refused "
                  "list, so no restart: the script stays with the note armed",
                  w.status == 0 and w.touched() == ["para"] and w.reboots() == 0 and phrase in w.log() and "list refused" in w.log()
                  and "list: refused\n" in w.marker() and w.stops() == 1 and w.note() == NOTE_SET)

        # 11
        for i, bad in enumerate(("lk", "recovery", "para", "super", "preloader", "../by-name/lk", "/dev/block/mmcblk0")):
            w = World(tmp, base, "t11_%d" % i)
            gzb = gzip.compress(b"\0" * 4096, 6, mtime=0)
            open(os.path.join(w.store, "evil.gz"), "wb").write(gzb)
            w.write_list([entry(info, "vbmeta"), (bad, "0" * 64, "evil.gz", sha(gzb), sha(b"\0" * 4096))])
            w.corrupt("vbmeta")
            w.run()
            check("11%s. list names '%s' (not on the allow-list): refused, nothing written anywhere" % ("abcdefg"[i], bad),
                  w.status == 0 and w.touched() == ["para"] and "is not on the allow-list" in w.log() and w.reboots() == 0 and w.note() == NOTE_SET)

        # 12
        def stay_world(label, content, corrupt=None, **env):
            w = World(tmp, base, label)
            w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")])
            open(os.path.join(w.store, "stay"), "w").write(content)
            if corrupt:
                w.corrupt(corrupt)
            w.run(**env)
            return w
        w = stay_world("t12a", "30\n")
        calls = w.call_list()
        order_ok = ("stop recovery" in calls and "reboot " in calls and
                    calls.index("stop recovery") < calls.index("sleep 10") < len(calls) - 1 - calls[::-1].index("sleep 10") < calls.index("reboot "))
        check("12a. stay file holding 30: the stock program is stopped, the script waits 30 s (3 steps of 10), then clears "
              "the note and restarts; nothing else written",
              w.status == 0 and w.touched() == ["para"] and w.note() == NOTE_CLEAR and w.reboots() == 1
              and w.call_list("sleep").count("sleep 10") == 3 and order_ok
              and "staying 30 s" in w.log() and w.marker().endswith("state: finished; restarting\n"),
              "sleep 10 calls: %d" % w.call_list("sleep").count("sleep 10"))
        for k, content in enumerate(("", "abc\n", "0\n", "5000\n", "12 x\n", "-5\n", "007\n")):
            w = stay_world("t12b%d" % k, content)
            check("12b%d. stay file holding %r (invalid): falls back to 600 s (60 steps of 10), then note cleared and restart" % (k, content),
                  w.status == 0 and w.call_list("sleep").count("sleep 10") == 60 and w.note() == NOTE_CLEAR and w.reboots() == 1
                  and "staying 600 s" in w.log())
        for content, want in (("1\n", ["sleep 1"]), ("3600\n", ["sleep 3600"]), ("25", ["sleep 25"])):
            w = stay_world("t12c" + content.strip(), content, RESCUE_STAY_STEP="5000")
            got = [c for c in w.call_list("sleep") if c not in ("sleep 2",)]
            check("12c. (extra) stay file holding %r with the step set large: one wait of exactly that many seconds, then home" % content,
                  w.status == 0 and got[-1:] == want and w.note() == NOTE_CLEAR and w.reboots() == 1, "waits: %s" % got[-2:])
        w = stay_world("t12d", "20\n", corrupt="logo")
        check("12d. (extra) stay with one partition wrong: it is restored first, then the wait, then note cleared and restart",
              w.status == 0 and w.touched() == ["logo", "para"] and w.after["logo"][0] == info["logo"]["good"]
              and w.call_list("sleep").count("sleep 10") == 2 and w.note() == NOTE_CLEAR and w.reboots() == 1)

        # 13
        w = World(tmp, base, "t13a")
        w.write_list([])                              # a `guarded` list with no entries: the clear-and-restart path, no ladder
        p_before = open(os.path.join(w.by, "para"), "rb").read()
        w.run()
        p_after = open(os.path.join(w.by, "para"), "rb").read()
        diff = [i for i in range(len(p_before)) if p_before[i] != p_after[i]]
        real = open(os.path.join(BACKUP, "para.img"), "rb").read()
        check("13a. clearing the note: the first 2048 bytes of para become zero (the command at 0-12 and the arguments at "
              "64-72 were set); ENV_v1 block 0x20000-0x23FFF and everything from byte 2048 on byte-identical, and identical to the backup's",
              p_before[:13] == b"boot-recovery" and diff == list(range(13)) + list(range(64, 73)) and p_after[:2048] == b"\0" * 2048
              and len(p_after) == len(p_before) == 524288 and p_after[2048:] == p_before[2048:] == real[2048:]
              and p_after[0x20000:0x24000] == real[0x20000:0x24000] and real[0x20000:0x20006] == b"ENV_v1"
              and real[0x23FF4:0x23FFA] == b"ENV_v1", "changed bytes: %s" % (diff[:20],))
        w = World(tmp, base, "t13b")
        shutil.rmtree(w.store)
        shutil.copy(os.path.join(BACKUP, "para.img"), os.path.join(w.by, "para"))
        w.run()
        check("13b. (extra) no note set (para as in the backup): nothing written, no restart requested",
              w.status == 0 and w.touched() == [] and w.reboots() == 0)
        w = World(tmp, base, "t13d")
        w.write_list([])                              # a `guarded` list with no entries: the clear-and-restart path, no ladder
        os.chmod(os.path.join(w.by, "para"), 0o444)
        w.run()
        check("13d. (extra) note cannot be cleared (para read-only): no restart, so no loop",
              w.status == 1 and w.note() == NOTE_SET and w.reboots() == 0 and "not restarting" in w.log())
        w = World(tmp, base, "t13e")
        w.write_list([])                              # a `guarded` list with no entries: the clear-and-restart path, no ladder
        # a stand-in for the stock recovery program writing the note back once, just after the first clearing
        open(os.path.join(w.dir, "stubs", "sleep"), "w").write(
            '#!/bin/sh\n[ "$1" = 2 ] || exit 0\n[ -e "$RESCUE_TMPLOG.once" ] && exit 0\n: > "$RESCUE_TMPLOG.once"\n'
            'printf boot-recovery | dd of="$RESCUE_BYNAME/para" conv=notrunc 2>/dev/null\n')
        w.run()
        check("13e. (extra) the note is written back once after the first clearing (as the stock program does at start): "
              "cleared again, then restart", w.status == 0 and w.note() == NOTE_CLEAR and w.reboots() == 1)
        os.chmod(os.path.join(w.by, "para"), 0o644)

        # 16: act only on our own note
        z = lambda b, n: b + b"\0" * (n - len(b))
        consts = dict(re.findall(r"^(CMD_\w+|ARGS_\w+)=([0-9a-f]{64})$", open(SCRIPT).read(), re.M))
        check("16a. the note hashes in the script are those of: command boot-recovery, command empty, arguments empty, "
              "'recovery\\n', 'recovery\\n--just_exit\\n' (each zero-padded to its field)",
              consts == {"CMD_RECOVERY": sha(z(b"boot-recovery", 32)), "CMD_NONE": sha(bytes(32)), "ARGS_EMPTY": sha(bytes(768)),
                         "ARGS_PLAIN": sha(z(b"recovery\n", 768)), "ARGS_JUST_EXIT": sha(z(b"recovery\n--just_exit\n", 768))})

        def note_world(label, command, args, **env):
            w = World(tmp, base, label)
            w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")])
            w.corrupt("vbmeta")                       # there IS something to restore, to show it is left alone
            w.set_note(command, args)
            w.run(**env)
            return w
        for label, args in (("16b. our note with no arguments", b""), ("16c. our note with arguments 'recovery\\n'", b"recovery\n")):
            w = note_world("t" + label[:3], b"boot-recovery", args)
            check(label + ": the script does its work (vbmeta restored, note cleared, restart)",
                  w.status == 0 and w.touched() == ["para", "vbmeta"] and w.note() == NOTE_CLEAR and w.reboots() == 1 and w.stops() == 1)
        w = note_world("t16d", b"boot-recovery", b"recovery\n--just_exit\n")
        calls = w.call_list()
        check("16d. our note with --just_exit and a list present: the list is NOT used (vbmeta left wrong), the stock program is "
              "not stopped, marker and log written; only after waiting 120 s (12 steps) with the frame still up does the "
              "script clear the note and restart",
              w.status == 0 and w.touched() == ["para"] and w.stops() == 0 and w.reboots() == 1 and w.note() == NOTE_CLEAR
              and calls.count("sleep 10") == 12 and len(calls) - 1 - calls[::-1].index("sleep 10") < calls.index("reboot ")
              and "the list is NOT used" in w.log() and "list: present but not used (--just_exit)\n" in w.marker()
              and "note at start: boot-recovery --just_exit (ours)\n" in w.marker())
        w = World(tmp, base, "t16d2")
        w.write_list([entry(info, "vbmeta")])
        w.corrupt("vbmeta")
        w.set_note(b"boot-recovery", b"recovery\n--just_exit\n")
        # a stand-in for the stock program restarting the frame during the wait: the first long sleep kills the script
        open(os.path.join(w.dir, "stubs", "sleep"), "w").write('#!/bin/sh\n[ "$1" = 10 ] && kill -9 $PPID\nexit 0\n')
        w.run()
        check("16d2. (extra) --just_exit and the script is cut off during its wait (as the stock program's restart does): "
              "by then it has written nothing but its log and marker",
              w.status != 0 and w.touched() == [] and w.reboots() == 0 and w.note()[:13] == b"boot-recovery"
              and "state: waiting for the stock program to restart the frame\n" in w.marker() and "rescue start" in w.log())
        foreign = (
            ("16e. factory reset note (--wipe_data)", b"boot-recovery", b"recovery\n--wipe_data\n"),
            ("16f. --prompt_and_wipe_data", b"boot-recovery", b"recovery\n--prompt_and_wipe_data\n"),
            ("16g. --update_package", b"boot-recovery", b"recovery\n--update_package=/cache/update.zip\n"),
            ("16h. --sideload", b"boot-recovery", b"recovery\n--sideload\n"),
            ("16i. --just_exit followed by --wipe_data", b"boot-recovery", b"recovery\n--just_exit\n--wipe_data\n"),
            ("16j. 'recovery' without its line end", b"boot-recovery", b"recovery"),
            ("16k. our arguments with stray bytes later in the field", b"boot-recovery", b"recovery\n".ljust(700, b"\0") + b"x"),
            ("16l. command boot-fastboot", b"boot-fastboot", b""),
            ("16m. command boot-recovery with extra letters", b"boot-recovery2", b"recovery\n"),
            ("16n. no note at all", b"", b""),
            ("16o. no command but arguments present", b"", b"recovery\n"),
        )
        for label, command, args in foreign:
            w = World(tmp, base, "t" + label[:3])
            w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")])
            open(os.path.join(w.store, "stay"), "w").write("30\n")
            w.corrupt("vbmeta")
            open(os.path.join(w.by, "cache"), "wb").write(b"\0" * 4096)
            w.set_note(command, args)
            w.run(RESCUE_MOUNT="1")
            names = set(c.split()[0] for c in w.call_list())
            check(label + ": not ours, so nothing at all: no partition or para write, nothing mounted, the store not touched, "
                  "stock program not stopped, no restart requested; log and marker only in /tmp",
                  w.status == 0 and w.touched() == [] and w.cache_untouched() and names <= {"sleep", "sync"}
                  and w.reboots() == 0 and w.stops() == 0 and "the note is not ours" in w.log()
                  and w.marker().endswith("state: finished; note not ours, nothing done\n"), "programs called: %s" % sorted(names))

        # 17: the note is judged from the snapshot init takes before the stock program starts
        w = World(tmp, base, "t17a")
        w.write_list([entry(info, "vbmeta")])
        w.corrupt("vbmeta")
        with open(os.path.join(w.by, "para"), "r+b") as f:      # make bytes around the 2048 boundary tell-tale
            f.seek(2040); f.write(b"\x11" * 8 + b"\x22" * 8)
        para_now = open(os.path.join(w.by, "para"), "rb").read()
        w.run("snapshot")
        made = sorted(set(os.listdir(w.dir)) - {"by-name", "cache", "stubs"})
        check("17a. snapshot mode: copies exactly the first 2048 bytes of para and writes nothing else (no partition, "
              "no store, no log, no marker, nothing mounted or stopped, no restart)",
              w.status == 0 and open(w.snap, "rb").read() == para_now[:2048] and para_now[2040:2048] == b"\x11" * 8
              and w.touched() == [] and w.cache_untouched() and made == ["snap.note"]
              and set(c.split()[0] for c in w.call_list()) <= {"sleep"}, "files made: %s" % made)

        def snap_world(label, snap, live, kmsg=None):
            w = World(tmp, base, label)
            w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")])
            w.corrupt("vbmeta")
            if snap is not None:
                if isinstance(snap, bytes):
                    open(w.snap, "wb").write(snap)
                else:
                    w.set_snapshot(*snap)
            w.set_note(*live)
            if kmsg:
                w.run(RESCUE_KMSG=kmsg)
            else:
                w.run()
            return w
        ours, cleared, wipe = (b"boot-recovery", b"recovery\n"), (b"", b""), (b"boot-recovery", b"recovery\n--wipe_data\n")
        w = snap_world("t17b", ours, cleared)
        check("17b. snapshot says ours (plain), live para already cleared to zeros (what happens on the frame): the script "
              "does its work (vbmeta restored, stock program stopped, restart requested); para is set for the retry and "
              "cleared again, ending as it began",
              w.status == 0 and w.touched() == ["para", "vbmeta"] and w.changed() == ["vbmeta"] and w.after["vbmeta"][0] == info["vbmeta"]["good"]
              and w.stops() == 1 and w.reboots() == 1 and "judged from the snapshot" in w.log()
              and "note at start: boot-recovery (ours)\n" in w.marker(), "written: %s" % w.touched())
        w = snap_world("t17c", wipe, cleared)
        check("17c. snapshot says --wipe_data, live para cleared: nothing at all (no write, store untouched, nothing "
              "stopped, no restart)",
              w.status == 0 and w.touched() == [] and w.cache_untouched() and w.stops() == 0 and w.reboots() == 0
              and "the note is not ours" in w.log())
        w = snap_world("t17c2", wipe, ours)
        check("17c2. (extra) snapshot says --wipe_data but live para looks ours: the snapshot wins, nothing at all",
              w.status == 0 and w.touched() == [] and w.cache_untouched() and w.stops() == 0 and w.reboots() == 0)
        w = snap_world("t17c3", cleared, ours)
        check("17c3. (extra) snapshot says no note but live para looks ours: the snapshot wins, nothing at all",
              w.status == 0 and w.touched() == [] and w.cache_untouched() and w.reboots() == 0)
        w = snap_world("t17d", None, ours)
        check("17d. no snapshot file: falls back to the live read of para (ours: work done, note cleared, restart)",
              w.status == 0 and w.touched() == ["para", "vbmeta"] and w.reboots() == 1 and "no snapshot; note judged from para" in w.log())
        w = snap_world("t17d2", None, wipe)
        check("17d2. (extra) no snapshot and live para says --wipe_data: nothing at all",
              w.status == 0 and w.touched() == [] and w.cache_untouched() and w.reboots() == 0)
        w = snap_world("t17e", b"", ours)
        check("17e. an empty snapshot file counts as no snapshot: live read used (ours: work done, restart)",
              w.status == 0 and w.touched() == ["para", "vbmeta"] and w.reboots() == 1 and "no snapshot; note judged from para" in w.log())
        w = snap_world("t17e2", b"", wipe)
        check("17e2. (extra) empty snapshot and live para says --wipe_data: nothing at all",
              w.status == 0 and w.touched() == [] and w.cache_untouched() and w.reboots() == 0)
        w = snap_world("t17f", b"boot-recovery" + b"\0" * 87, ours)
        check("17f. (extra) a cut-short snapshot (100 bytes) is not trusted as ours and is not replaced by the live read: nothing at all",
              w.status == 0 and w.touched() == [] and w.cache_untouched() and w.reboots() == 0 and "the note is not ours" in w.log())
        w = snap_world("t17g", ours, (b"boot-recovery", b"recovery\n--wipe_data\n"))
        check("17g. (extra) snapshot says ours but live para now holds a foreign note: our note is not set over it, so no "
              "partition is written; the foreign note is NOT cleared and there is no restart",
              w.status == 0 and w.touched() == [] and w.reboots() == 0
              and "not setting ours over it" in w.log() and "no longer ours" in w.log())

        # kernel-log copy of each log line: only to a character device, and never this computer's own
        kfile = os.path.join(tmp, "kmsg-regular-file")
        open(kfile, "w").close()
        w = snap_world("t17h", ours, cleared, kmsg=kfile)
        check("17h. RESCUE_KMSG is a regular file: no kernel-log line is written to it; the run is otherwise normal",
              w.status == 0 and os.path.getsize(kfile) == 0 and w.reboots() == 1)
        master, slave = os.openpty()
        w = snap_world("t17i", ours, cleared, kmsg=os.ttyname(slave))
        os.set_blocking(master, False)
        got = b""
        try:
            while True:
                chunk = os.read(master, 65536)
                if not chunk:
                    break
                got += chunk
        except (BlockingIOError, OSError):
            pass
        os.close(master); os.close(slave)
        klines = [l for l in got.decode().replace("\r", "").split("\n") if l]
        loglines = [l[20:] for l in w.log().split("\n") if l]
        check("17i. RESCUE_KMSG is a character device (a pseudo-terminal made by the test): every log line also goes there "
              "as 'rescue.sh: ...'", w.status == 0 and len(klines) > 5 and klines == ["rescue.sh: " + l for l in loglines],
              "%d lines" % len(klines))
        w = World(tmp, base, "t17j")
        master, slave = os.openpty()
        w.run("snapshot", RESCUE_KMSG=os.ttyname(slave))
        os.set_blocking(master, False)
        try:
            got = os.read(master, 4096)
        except (BlockingIOError, OSError):
            got = b""
        os.close(master); os.close(slave)
        check("17j. (extra) snapshot mode writes its one kernel-log line to a character device, and none without one (17a)",
              got.decode().replace("\r", "") == "rescue.sh: snapshot of the note taken\n" and not os.path.exists(os.path.join(w.dir, "no-kmsg")))
        text17 = open(SCRIPT).read()
        check("17k. every run of the script in these tests had RESCUE_SNAP and RESCUE_KMSG inside the temporary folder; "
              "the script's own defaults are /tmp/rescue.note and /dev/kmsg",
              "SNAP=${RESCUE_SNAP:-/tmp/rescue.note}" in text17 and "KMSG=${RESCUE_KMSG:-/dev/kmsg}" in text17
              and not os.path.exists(os.path.join(tmp, "base", "no-kmsg")))

        # 18: the note is set again before the first partition write; a counter caps the retries
        real_para = open(os.path.join(BACKUP, "para.img"), "rb").read()
        PLAIN_NOTE = b"boot-recovery".ljust(2048, b"\0")

        def para_of(w):
            return open(os.path.join(w.by, "para"), "rb").read()

        def env_ok(w):
            p = para_of(w)
            return len(p) == 524288 and p[2048:] == real_para[2048:] and p[0x20000:0x20006] == b"ENV_v1"

        def attempts_of(w):
            p = os.path.join(w.store, "attempts")
            return open(p).read() if os.path.exists(p) else None

        def probe_dd(w, kill):
            """Replace dd by a wrapper that, at each partition write, records what para and the counter hold at that
            moment. With kill=True the first partition write stores only 8192 bytes and then kills the script."""
            body = ('#!/bin/sh\ncase " $* " in\n*" seek="*)\n'
                    '  echo "write $1 para=$(/bin/dd if="$RESCUE_BYNAME/para" bs=2048 count=1 2>/dev/null | /sbin/sha256sum | /usr/bin/cut -c1-64)'
                    ' attempts=$(/bin/cat "$RESCUE_MNT/rescue/attempts" 2>/dev/null)" >> "$RESCUE_TEST_CALLS"\n')
            if kill:
                body += '  /usr/bin/head -c 8192 | /bin/dd "$@" 2>/dev/null\n  kill -9 $PPID\n  exit 1\n'
            body += '  ;;\nesac\nexec /bin/dd "$@"\n'
            path = os.path.join(w.dir, "stubs", "dd")
            open(path, "w").write(body)
            os.chmod(path, 0o755)

        def arm_world(label, wrong=("vbmeta",), attempts=None, kill=False):
            w = World(tmp, base, label)
            w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")])
            for n in wrong:
                w.corrupt(n, off=1_000_000)               # beyond the 8192 bytes the cut-off write stores
            if attempts is not None:
                open(os.path.join(w.store, "attempts"), "w").write(attempts)
            w.set_snapshot(b"boot-recovery", b"recovery\n")
            w.set_note(b"", b"")                          # as on the frame: the stock program has cleared it
            probe_dd(w, kill)
            w.own_session = kill
            w.run()
            w.own_session = False
            return w
        w = arm_world("t18a", wrong=("vbmeta", "logo"))
        writes = w.call_list("write")
        check("18a. a run that needs writes sets our plain note in para BEFORE the first partition byte changes (seen from "
              "inside each partition write: para holds exactly our note and the counter is 1), once for the run; at the "
              "end everything is restored, the note cleared, the counter removed, restart requested",
              w.status == 0 and len(writes) == 2 and all(x.endswith("para=%s attempts=1" % sha(PLAIN_NOTE)) for x in writes)
              and w.log().count("note set again in para") == 1 and w.changed() == ["logo", "vbmeta"]
              and para_of(w)[:2048] == bytes(2048) and attempts_of(w) is None and w.reboots() == 1 and env_ok(w),
              "partition writes seen: %d" % len(writes))
        cleared_para = lambda w: para_of(w)[:2048] == bytes(2048)
        w = arm_world("t18b", wrong=())
        check("18b. a run where everything matches writes no partition and makes no counter; para is written only to set our note "
              "at the start and to clear it at the end (snapshot ours, live already cleared)",
              w.status == 0 and w.touched() == ["para"] and w.call_list("write") == [] and attempts_of(w) is None and w.reboots() == 1
              and env_ok(w) and cleared_para(w) and "note set again in para (try" not in w.log())
        w = arm_world("t18c", kill=True)
        cut = (w.status != 0 and w.reboots() == 0 and para_of(w)[:2048] == PLAIN_NOTE and attempts_of(w) == "1\n"
               and w.after["vbmeta"][0] != info["vbmeta"]["good"] and env_ok(w))
        check("18c. cut off in the middle of the first partition write: para holds our plain note, the counter is 1, "
              "the partition is half written, ENV_v1 untouched", cut,
              "exit status %s, restarts %d, counter %r, partition writes seen %d" % (w.status, w.reboots(), attempts_of(w), len(w.call_list("write"))))
        os.remove(os.path.join(w.dir, "stubs", "dd"))
        w.set_snapshot(b"boot-recovery", b"")            # what init would copy at the next start
        os.remove(w.calls)
        w.run()
        check("18d. the next start (snapshot = our plain note) finishes the restore, clears the note, removes the counter "
              "and asks for the restart", w.status == 0 and w.after["vbmeta"][0] == info["vbmeta"]["good"]
              and para_of(w)[:2048] == bytes(2048) and attempts_of(w) is None and w.reboots() == 1 and env_ok(w)
              and "try 2 of 3" in w.log())
        for k, content in enumerate(("3\n", "7\n", "03\n", "100\n", "999999999999\n")):
            w = arm_world("t18e%d" % k, attempts=content)
            check("18e%d. counter holds %r (3 or more): no partition write, counter left, no restart while the partition is still wrong: "
                  "the script stays with our note armed (set at the start)" % (k, content.strip()),
                  w.status == 0 and w.touched() == ["para"] and para_of(w)[:2048] == PLAIN_NOTE and w.call_list("write") == []
                  and attempts_of(w) == content and w.reboots() == 0 and "gave up after 3 tries" in w.log() and "wrong but not restored: vbmeta\n" in w.marker()
                  and env_ok(w))
        for k, (content, tries) in enumerate((("", 1), ("abc\n", 1), ("1 x\n", 1), ("-1\n", 1), ("0\n", 1), ("1\n", 2), ("2\n", 3), ("02\n", 3))):
            w = arm_world("t18f%d" % k, attempts=content)
            check("18f%d. counter holds %r: counts as %d, so this is try %d: restored, note cleared, counter removed, restart"
                  % (k, content.strip(), tries - 1, tries),
                  w.status == 0 and w.changed() == ["vbmeta"] and w.call_list("write")[0].endswith("attempts=%d" % tries)
                  and "try %d of 3" % tries in w.log() and attempts_of(w) is None and w.reboots() == 1 and env_ok(w))
        w = World(tmp, base, "t18g")
        w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")])
        w.corrupt("vbmeta")
        w.set_snapshot(b"boot-recovery", b"recovery\n")
        w.set_note(b"", b"")
        os.chmod(os.path.join(w.by, "para"), 0o444)
        probe_dd(w, False)
        w.run()
        os.chmod(os.path.join(w.by, "para"), 0o644)
        check("18g. the note cannot be set (para read-only): no partition is written in this run; logged; with a partition still wrong "
              "the script stays (no restart)",
              w.status == 0 and w.touched() == [] and w.call_list("write") == [] and w.reboots() == 0
              and "did not read back as ours" in w.log() and "wrong but not restored: vbmeta\n" in w.marker())
        w = World(tmp, base, "t18h")
        w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")])
        w.corrupt("vbmeta")
        w.set_snapshot(b"boot-recovery", b"recovery\n")
        w.set_note(b"", b"")
        os.chmod(w.store, 0o555)                          # the counter cannot be written
        probe_dd(w, False)
        w.run()
        os.chmod(w.store, 0o755)
        check("18h. (extra) the counter cannot be recorded (store read-only): no partition is written; the partition is still wrong, so the "
              "script stays with the note armed (no restart)",
              w.status == 0 and w.touched() == ["para"] and w.call_list("write") == [] and w.reboots() == 0
              and "could not record the try" in w.log())

        # 19: the escalation ladder (counter `rung` in the store; our plain note with no "guarded" line in the list).
        # An entry first checks the list and restores what is wrong, then counts: rung 1 restart, rung 2 safe + restart,
        # rung 3 and above stay. Every restart from the ladder is UNARMED (note cleared); only a resume restarts armed.
        def ladder_world(label, rung=None, guarded=False, wrong=("vbmeta",), snap=(b"boot-recovery", b"recovery\n"),
                         live=(b"", b""), attempts=None, readonly=False, run=True):
            w = World(tmp, base, label)
            w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")], guarded=guarded)
            for n in wrong:
                w.corrupt(n, off=1_000_000)
            if rung is not None:
                open(os.path.join(w.store, "rung"), "w").write(rung)
            if attempts is not None:
                open(os.path.join(w.store, "attempts"), "w").write(attempts)
            w.set_snapshot(*snap)
            w.set_note(*live)                             # as on the frame: the stock program has cleared it already
            if readonly:
                os.chmod(w.store, 0o555)
                if rung is not None:
                    os.chmod(os.path.join(w.store, "rung"), 0o444)
            if run:
                w.run()
            if readonly:
                os.chmod(w.store, 0o755)
                if rung is not None:
                    os.chmod(os.path.join(w.store, "rung"), 0o644)
            return w

        def parts_changed(w):
            return [n for n in w.changed() if n != "para"]

        def armed(w):
            return para_of(w)[:2048] == PLAIN_NOTE

        def cleared(w):
            return para_of(w)[:2048] == bytes(2048)

        def rung_of(w):
            p = os.path.join(w.store, "rung")
            return open(p).read() if os.path.exists(p) else None

        def safe_of(w):
            return os.path.exists(os.path.join(w.store, "safe"))

        def next_start(w):
            """What init and the stock program do at a new start of recovery: init snapshots the note, then the stock
            program clears it. Returns whether the previous run left our plain note armed (LK would have come here)."""
            was = para_of(w)[:2048]
            w.set_snapshot(*(b"boot-recovery", b"") if was == PLAIN_NOTE else (b"", b""))
            w.set_note(b"", b"")
            if os.path.exists(w.calls):
                os.remove(w.calls)
            return was == PLAIN_NOTE

        red_states = []
        VERIFIED = ("vbmeta", "vbmeta_system", "boot", "logo")       # LK-verified stand-ins (product is never damaged in these tests)

        def lk_bad(w):
            cur = getattr(w, "after", None) or w.snapshot()
            return [n for n in VERIFIED if cur[n][0] != info[n]["good"]]

        def no_part_written(w):
            return [n for n in w.touched() if n != "para"] == []

        def lk_next(w, android="fail"):
            """What happens after a run, modelling LK: the frame restarted or was power cycled. If our note is set in para,
            LK starts recovery again. If not and a verified partition is wrong, that is Red State for ever (recorded; the
            tests fail on it). Otherwise Android runs: it fails (re-arming the note at its early start, so recovery is
            entered again) or, with android="ok", it is healthy (no more recovery). Returns "recovery", "android" or "red"."""
            if not armed(w):
                if lk_bad(w):
                    red_states.append((w.dir, lk_bad(w)))
                    return "red"
                if android == "ok":
                    return "android"
                with open(os.path.join(w.by, "para"), "r+b") as f:
                    f.write(PLAIN_NOTE)
            next_start(w)
            return "recovery"

        def re_enter(w):
            """Like lk_next; returns whether the note was already armed before Android could arm it."""
            was = armed(w)
            lk_next(w)
            return was

        # (b) Android fails, all partitions good: restart, safe + restart, stay
        w = ladder_world("t19a", wrong=())
        check("19a. rung 1 (no counter yet), everything good: counter 1, nothing written to any partition, the note is "
              "CLEARED (unarmed restart: Android arms it again itself), restart; no safe flag",
              w.status == 0 and rung_of(w) == "1\n" and w.reboots() == 1 and no_part_written(w) and cleared(w) and not safe_of(w)
              and w.call_list("write") == [] and "rung 1" in w.log() and env_ok(w))
        w = ladder_world("t19b", rung="1\n", wrong=())
        check("19b. rung 2: the safe flag is written, counter 2, note cleared, restart",
              w.status == 0 and rung_of(w) == "2\n" and safe_of(w) and w.reboots() == 1 and no_part_written(w) and cleared(w)
              and open(os.path.join(w.store, "safe")).read() == "ladder\n"
              and "rung 2" in w.log() and env_ok(w))
        w = ladder_world("t19c", rung="2\n", wrong=())
        check("19c. rung 3: stay: counter 3, no restart, stock program stopped, nothing written to any partition, the note "
              "cleared (nothing is wrong, so a power cycle goes to Android), logged",
              w.status == 0 and rung_of(w) == "3\n" and w.reboots() == 0 and w.stops() >= 1 and no_part_written(w) and cleared(w)
              and "rung 3" in w.log() and "staying in recovery" in w.log() and "staying in recovery" in w.marker() and env_ok(w))
        for k, content in enumerate(("3\n", "4\n", "5\n", "99\n", "100\n", "999999999999\n", "03\n", "04\n")):
            w = ladder_world("t19e%d" % k, rung=content, wrong=())
            check("19e%d. counter already holds %r (3 or more): stay again, counter not rewritten, no restart, nothing written"
                  % (k, content.strip()),
                  w.status == 0 and rung_of(w) == content and w.reboots() == 0 and w.stops() >= 1 and no_part_written(w)
                  and "rung 3" in w.log())
        # (a) Red State: a bad vbmeta_system: the first entry puts it back and restarts unarmed
        w = ladder_world("t20a", wrong=("vbmeta_system",))
        check("20a. Red State case: bad vbmeta_system and our note: the FIRST entry restores it (vbmeta_system only, read back "
              "good), counts rung 1, clears the note, removes the restore-try counter, restarts (unarmed)",
              w.status == 0 and parts_changed(w) == ["vbmeta_system"] and cleared(w) and rung_of(w) == "1\n" and attempts_of(w) is None
              and w.reboots() == 1 and not safe_of(w) and "vbmeta_system: RESTORED" in w.log() and env_ok(w))
        # the whole ladder, no healthy clear, partition wrong at the start: restore + restart; safe + restart; stay; stay
        w = ladder_world("t19f", run=False)
        seen = []
        for i in range(4):
            if i:
                re_enter(w)
            elif os.path.exists(w.calls):
                os.remove(w.calls)
            w.run()
            seen.append((rung_of(w), w.reboots(), safe_of(w), parts_changed(w), armed(w)))
        check("19f. (c) Android keeps failing even after a restore: entry 1 restores and restarts, entry 2 writes safe and "
              "restarts, entries 3 and 4 stay; no restart is ever armed; nothing is restored again (no endless restore)",
              seen == [("1\n", 1, False, ["vbmeta"], False), ("2\n", 1, True, [], False), ("3\n", 0, True, [], False),
                       ("3\n", 0, True, [], False)], str(seen))
        # (e) Android's healthy clear: rung counter removed, note zeroed. The next entry starts at rung 1 again.
        w = ladder_world("t19g", run=False)
        for i in range(2):
            if i:
                re_enter(w)
            else:
                w.set_snapshot(b"boot-recovery", b"recovery\n")
            w.run()
        for n in ("rung", "attempts"):
            if os.path.exists(os.path.join(w.store, n)):
                os.remove(os.path.join(w.store, n))
        with open(os.path.join(w.by, "para"), "r+b") as f:
            f.write(bytes(2048))
        left = sorted(os.listdir(w.store))
        with open(os.path.join(w.by, "para"), "r+b") as f:       # Android's next start arms the note again
            f.write(PLAIN_NOTE)
        next_start(w)
        w.run()
        check("19g. (e) a healthy clear (counter and attempts removed, note zeroed) resets the ladder: the store is the stored "
              "set plus the safe flag; the next entry is rung 1 again (restart, unarmed)",
              left == sorted(["list", "safe"] + [n + ".gz" for n in all_names]) and w.status == 0 and rung_of(w) == "1\n"
              and w.reboots() == 1 and cleared(w))
        w = ladder_world("t19h", rung="3\n", guarded=True)
        check("19h. a list that says `guarded` restores at once whatever the counter says (3 here), leaves the counter "
              "alone, clears the note, restarts",
              w.status == 0 and rung_of(w) == "3\n" and parts_changed(w) == ["vbmeta"] and cleared(w)
              and w.reboots() == 1 and "mode: manual" in w.log() and env_ok(w))
        w = ladder_world("t19i", attempts="1\n")
        check("19i. a restore cut off earlier (counter attempts 1) with a list that does not say guarded: it is finished "
              "at once, the ladder counter is neither created nor raised, the note is cleared and the frame restarts",
              w.status == 0 and rung_of(w) is None and parts_changed(w) == ["vbmeta"] and attempts_of(w) is None
              and w.reboots() == 1 and "mode: resume" in w.log() and cleared(w) and env_ok(w))
        w = ladder_world("t19j", rung="1\n", attempts="3\n")
        check("19j. attempts at 3 (restores given up) and a partition still wrong: the restore writes nothing, the counter "
              "still rises (rung 2), but there is NO restart while a listed partition is wrong: the script stays, note armed",
              w.status == 0 and rung_of(w) == "2\n" and not safe_of(w) and no_part_written(w) and w.reboots() == 0
              and "gave up after 3 tries" in w.log() and armed(w))
        for k, (snap, args) in enumerate(((b"boot-recovery", b"recovery\n--wipe_data\n"),
                                          (b"boot-recovery", b"recovery\n--wipe_data\n--locale=en_GB\n"),
                                          (b"boot-recovery", b"recovery\n--prompt_and_wipe_data\n"),
                                          (b"boot-recovery", b"--update_package=/cache/x.zip"),
                                          (b"boot-fastboot", b""))):
            w = ladder_world("t19k%d" % k, rung="1\n", snap=(snap, args), live=(snap, args))
            check("19k%d. an always-armed setup (counter at 1, list present, a partition wrong) meeting a foreign note %r: nothing "
                  "done at all (no mount, no counter change, no safe flag, no restore, no restart, stock program not stopped)"
                  % (k, args[:30]),
                  w.status == 0 and rung_of(w) == "1\n" and not safe_of(w) and w.reboots() == 0 and w.stops() == 0
                  and no_part_written(w) and w.cache_untouched() and w.note() == snap.ljust(32, b"\0")
                  and "nothing mounted, nothing written" in w.log())
        for k, (content, want) in enumerate((("", "1\n"), ("abc\n", "1\n"), ("1 x\n", "1\n"), ("-1\n", "1\n"), ("0\n", "1\n"),
                                            ("00\n", "1\n"), ("\n\n", "1\n"), ("01\n", "2\n"), ("1\n", "2\n"), ("02\n", "3\n"),
                                            (" 2\n", "3\n"))):
            w = ladder_world("t19l%d" % k, rung=content, wrong=())
            check("19l%d. counter holds %r: counts as %d, so this entry is rung %s"
                  % (k, content.strip(), int(want) - 1, want.strip()),
                  w.status == 0 and rung_of(w) == want and w.reboots() == (0 if want == "3\n" else 1) and env_ok(w))
        # the counter cannot be written (full or read-only cache): with nothing wrong the note is cleared and a power cycle
        # reaches Android (which can free space); with a partition still wrong the script stays armed
        w = ladder_world("t19m", readonly=True, wrong=())
        st = lk_next(w, android="ok")
        check("19m. the store cannot be written (read-only folder), no counter yet, nothing wrong: stay (no restart, nothing "
              "written, stock program stopped, logged), the note CLEARED; a power cycle then starts Android (LK model)",
              w.status == 0 and rung_of(w) is None and w.reboots() == 0 and w.stops() >= 1 and no_part_written(w)
              and "cannot be written" in w.log() and cleared(w) and st == "android" and env_ok(w))
        w = ladder_world("t19m2", readonly=True)
        check("19m2. the same with a partition still wrong: stay with the note ARMED; a power cycle comes back to recovery",
              w.status == 0 and rung_of(w) is None and w.reboots() == 0 and armed(w) and no_part_written(w)
              and lk_next(w, android="ok") == "recovery")
        w = ladder_world("t19n", run=False, wrong=())
        shutil.rmtree(w.store)
        os.chmod(w.cache, 0o555)
        w.run()
        os.chmod(w.cache, 0o755)
        st = lk_next(w, android="ok")
        check("19n. the cache has no store folder and cannot be written, nothing wrong: stay, no restart, nothing written, "
              "note cleared, a power cycle starts Android",
              w.status == 0 and w.reboots() == 0 and w.stops() >= 1 and no_part_written(w) and not os.path.exists(w.store)
              and cleared(w) and st == "android")
        w = ladder_world("t19o", rung="1\n", readonly=True, wrong=())
        st = lk_next(w, android="ok")
        check("19o. the store becomes unwritable at rung 2 (counter 1 cannot be raised), nothing wrong: stay, the safe flag is "
              "not written, no restart, note cleared, a power cycle starts Android",
              w.status == 0 and rung_of(w) == "1\n" and not safe_of(w) and w.reboots() == 0 and w.stops() >= 1
              and no_part_written(w) and cleared(w) and st == "android")
        # a guarded flash whose list is refused cannot be vouched for: stay armed, no restart
        w = ladder_world("t19r", guarded=True, wrong=(), run=False)
        w.write_list([entry(info, n) for n in ("vbmeta_system", "vbmeta", "logo")], tail=None, guarded=True)
        w.run()
        check("19r. a `guarded` run whose list is refused (cut short): no restart, the script stays with the note armed",
              w.status == 0 and w.reboots() == 0 and armed(w) and w.stops() >= 1 and no_part_written(w)
              and "manual with a refused list" in w.log() and lk_next(w, android="ok") == "recovery")
        w = ladder_world("t19p", rung="1\n", snap=(b"boot-recovery", b"recovery\n--just_exit\n"))
        check("19p. --just_exit still wins over the ladder: list and counter untouched, the 120 s wait, then clear and restart",
              w.status == 0 and rung_of(w) == "1\n" and no_part_written(w) and w.stops() == 0 and w.reboots() == 1
              and "--just_exit: leaving the note" in w.log() and w.call_list().count("sleep 10") == 12)
        # at the stay, a restore that completed cleanly leaves no armed note behind; one that did not, leaves the resume going
        w = ladder_world("t19q", rung="2\n")
        check("19q. rung 3 with a wrong partition: it is restored, the note it set for the write is cleared again (a power cycle "
              "starts Android), no restart, stay",
              w.status == 0 and parts_changed(w) == ["vbmeta"] and cleared(w) and w.reboots() == 0 and rung_of(w) == "3\n"
              and attempts_of(w) is None and w.stops() >= 1)
        # (d) power cut mid-restore at entry 1: resume finishes (armed restart), then the ladder goes on
        w = ladder_world("t20d", run=False)
        probe_dd(w, True)
        w.run()
        cut_ok = (w.status != 0 and w.reboots() == 0 and armed(w) and attempts_of(w) == "1\n" and rung_of(w) == "1\n"
                  and w.after["vbmeta"][0] != info["vbmeta"]["good"])
        os.remove(os.path.join(w.dir, "stubs", "dd"))
        kept = next_start(w)
        w.run()
        done = (w.status == 0 and w.after["vbmeta"][0] == info["vbmeta"]["good"] and attempts_of(w) is None and rung_of(w) == "1\n"
                and w.reboots() == 1 and cleared(w) and "mode: resume" in w.log())
        trail = []
        for i in range(3):
            again = re_enter(w)
            w.run()
            trail.append((again, rung_of(w), w.reboots(), safe_of(w), armed(w)))
        check("20d. (d) power cut in the middle of the restore at entry 1: our note is already set; the next start resumes, "
              "finishes the restore, clears the note and restarts (rung still 1); Android fails; then the ladder goes on: "
              "rung 2 (safe, restart), rung 3 stay, stay",
              cut_ok and kept and done and trail == [(False, "2\n", 1, True, False), (False, "3\n", 0, True, False),
                                                    (False, "3\n", 0, True, False)], str(trail))
        # a restore that cannot finish (one copy corrupt) must not turn into an endless resume
        w = ladder_world("t21a", wrong=("vbmeta", "logo"), run=False)
        gzp = os.path.join(w.store, "logo.gz")
        raw = bytearray(open(gzp, "rb").read())
        raw[len(raw) // 2] ^= 0xFF
        open(gzp, "wb").write(raw)
        trail = []
        for i in range(4):
            if i:
                re_enter(w)
            w.run()
            trail.append((rung_of(w), attempts_of(w), w.reboots(), armed(w)))
        check("21a. one good copy (vbmeta) and one corrupt copy (logo): entry 1 restores vbmeta (attempts 1) but does NOT restart "
              "(logo is still wrong): it stays with our note armed; every later entry (a power cycle comes back here) stays "
              "armed too: the resume writes nothing and drops the restore-try counter, then rungs 2 and 3; never a restart, "
              "never an endless resume, never Red State",
              trail == [("1\n", "1\n", 0, True), ("1\n", None, 0, True), ("2\n", None, 0, True), ("3\n", None, 0, True)],
              str(trail))
        w = ladder_world("t21e", wrong=(), run=False)
        trail = []
        for i in range(4):
            if i:
                re_enter(w)
            w.run()
            if i == 0:                                    # the list is damaged on cache: cut short; a restore-try counter is left
                lines = open(os.path.join(w.store, "list")).read().splitlines()
                open(os.path.join(w.store, "list"), "w").write("\n".join(lines[:-1]) + "\n")
                open(os.path.join(w.store, "attempts"), "w").write("1\n")
            trail.append((rung_of(w), w.reboots(), armed(w)))
        check("21e. the list is damaged (cut short) while a restore-try counter is left: the next entry resumes, refuses the "
              "list, wrote nothing, drops the counter and restarts (note cleared); then rung 2; then rung 3: stay; never an "
              "endless resume",
              trail == [("1\n", 1, False), ("1\n", 1, False), ("2\n", 1, False), ("3\n", 0, False)]
              and "list refused" in w.log() and "mode: resume" in w.log(), str(trail))
        # resume that cannot arm its note: stay, never an unarmed restart from a resume
        w = ladder_world("t20c", attempts="1\n", run=False)
        os.chmod(os.path.join(w.by, "para"), 0o444)
        w.run()
        os.chmod(os.path.join(w.by, "para"), 0o644)
        check("20c. a resume whose note cannot be set again at the end (para read-only): no restart, the script stays (stock "
              "program stopped)",
              w.status == 0 and w.reboots() == 0 and w.stops() >= 1 and "could not be set again" in w.log() and w.note() == NOTE_CLEAR)
        w = ladder_world("t20f", attempts="1\n", live=(b"boot-recovery", b"recovery\n--wipe_data\n"))
        check("20f. another program's note in para after the snapshot (--wipe_data): not our run any more: nothing mounted-and-"
              "changed, no partition written, no restart, the stock program left running, the foreign note left alone",
              w.status == 0 and w.reboots() == 0 and w.stops() == 0 and no_part_written(w)
              and para_of(w)[64:64 + 21] == b"recovery\n--wipe_data\n" and "no longer ours" in w.log() and attempts_of(w) == "1\n")
        # the order: the counter is on disk before the restart
        w = ladder_world("t20e", wrong=(), run=False)
        open(os.path.join(w.dir, "stubs", "reboot"), "w").write(
            '#!/bin/sh\necho "reboot rung=$(cat "$RESCUE_MNT/rescue/rung" 2>/dev/null)" >> "$RESCUE_TEST_CALLS"\n')
        w.run()
        check("20e. at the moment of the restart the counter on disk is already 1",
              w.call_list("reboot") == ["reboot rung=1"], str(w.call_list("reboot")))
        for k, (label, kw) in enumerate((("ladder, rung 1", dict(rung="1\n")), ("resume", dict(attempts="1\n")),
                                         ("ladder, no counter yet", {}), ("a guarded list", dict(guarded=True)))):
            w = ladder_world("t21c%d" % k, run=False, **kw)
            os.makedirs(os.path.join(w.cache, "recovery"))
            open(os.path.join(w.cache, "recovery", "command"), "w").write("--update_package=/cache/ota.zip\n")
            w.run()
            check("21c%d. (%s) /cache/recovery/command holds a command: not our run; nothing written, counters untouched, no "
                  "restart, stock program not stopped, nothing left mounted" % (k, label),
                  w.status == 0 and no_part_written(w) and w.reboots() == 0 and w.stops() == 0
                  and rung_of(w) == kw.get("rung") and attempts_of(w) == kw.get("attempts") and w.note() == NOTE_CLEAR
                  and "recovery/command in the cache is not empty" in w.log() and not safe_of(w))
        w = ladder_world("t21d", rung="1\n", wrong=(), run=False)
        os.makedirs(os.path.join(w.cache, "recovery"))
        open(os.path.join(w.cache, "recovery", "command"), "w").write("")
        w.run()
        check("21d. an EMPTY /cache/recovery/command does not stop the ladder: rung 2",
              w.status == 0 and rung_of(w) == "2\n" and w.reboots() == 1 and cleared(w))

        # 22: changes after the LK review: our note is set again at the start; no restart while a partition is wrong
        w = ladder_world("t22a", run=False)
        kill_body = ('#!/bin/sh\ncase " $* " in\n*if=*/vbmeta_system\\ *skip=*)\n'
                     '  echo "hashing $1" >> "$RESCUE_TEST_CALLS"\n'
                     '  echo "para-at-first-read $(/bin/dd if="$RESCUE_BYNAME/para" bs=13 count=1 2>/dev/null)" >> "$RESCUE_TEST_CALLS"\n'
                     '  p=$PPID\n  while :; do\n'
                     '    q=$(/bin/ps -o ppid= -p $p | /usr/bin/tr -d " ")\n    c=$(/bin/ps -o command= -p $q)\n'
                     '    case "$c" in *rescue.sh*) p=$q ;; *) break ;; esac\n  done\n'
                     '  kill -9 $p\n  exit 1\n  ;;\nesac\nexec /bin/dd "$@"\n')
        open(os.path.join(w.dir, "stubs", "dd"), "w").write(kill_body)
        os.chmod(os.path.join(w.dir, "stubs", "dd"), 0o755)
        w.run()
        reads = w.call_list()
        cut_hash = (w.status != 0 and w.reboots() == 0 and armed(w) and attempts_of(w) is None and no_part_written(w)
                    and any(l.startswith("hashing") for l in reads)
                    and any(l.startswith("para-at-first-read boot-recovery") for l in reads))
        os.remove(os.path.join(w.dir, "stubs", "dd"))
        state = lk_next(w)
        w.run()
        check("22a. power cut while hashing (before any partition read finished): our note was already set when the first "
              "partition was read, so the frame comes back to recovery (LK model: recovery, not Red State); nothing was written, "
              "no restore-try counter was made; the next entry carries on (rung 2, safe, restart)",
              cut_hash and state == "recovery" and rung_of(w) == "2\n" and safe_of(w) and w.reboots() == 1 and cleared(w),
              str((cut_hash, state, rung_of(w))))
        for k, how in enumerate(("file", "missing")):
            w = ladder_world("t22b%d" % k, wrong=("vbmeta",), run=False)
            if how == "file":
                gz = os.path.join(w.store, "vbmeta.gz")
                d = bytearray(open(gz, "rb").read()); d[len(d) // 2] ^= 0x10; open(gz, "wb").write(d)
            else:
                os.remove(os.path.join(w.store, "vbmeta.gz"))
            w.run()
            first = (w.reboots() == 0 and armed(w) and rung_of(w) == "1\n" and not safe_of(w) and w.stops() >= 1
                     and "still wrong; staying in recovery with our plain note armed" in w.log())
            lk = lk_next(w)
            w.run()
            check("22b%d. rung 1 with a wrong partition whose copy is %s: no restart (that would be Red State for ever), the "
                  "script stays with the note armed; a power cycle comes back to recovery; the next entry stays too" % (k, how),
                  first and lk == "recovery" and w.reboots() == 0 and armed(w) and rung_of(w) == "2\n" and not safe_of(w), str(first))
        w = ladder_world("t22c", rung="2\n", wrong=("logo",), run=False)
        os.remove(os.path.join(w.store, "logo.gz"))
        w.run()
        check("22c. rung 3 (stay) with a wrong partition that cannot be restored: the note stays ARMED (a power cycle comes back "
              "to recovery); with everything good the same entry leaves it cleared (19c)",
              w.reboots() == 0 and armed(w) and rung_of(w) == "3\n")
        w = ladder_world("t22d", guarded=True, wrong=("vbmeta",), run=False)
        os.remove(os.path.join(w.store, "vbmeta.gz"))
        w.run()
        check("22d. a `guarded` flash whose restore cannot finish: no restart, stays with the note armed",
              w.reboots() == 0 and armed(w) and "mode: manual" in w.log())
        check("22e. in every ladder, resume and stay scenario above, no restart ever left the frame in a state LK would refuse "
              "(a wrong verified partition and no note: Red State)", red_states == [], str(red_states))

        # 14
        text = open(SCRIPT).read()
        cmds, funcs = script_commands(text)
        bins = set(n[len("system/bin/"):] for n in old if n.startswith("system/bin/"))
        missing = [c for c in cmds if c not in bins]
        expected = ["cat", "date", "dd", "gunzip", "mkdir", "mount", "mv", "printf", "rm", "sha256sum", "sleep", "stop", "sync", "umount", "wc"]
        default_reboot = re.search(r"^REBOOT=\$\{RESCUE_REBOOT:-(\w+)\}$", text, re.M)
        rc_extra = open(os.path.join(SRC, "init.rescue.rc")).read()
        check("14a. every program rescue.sh runs is in the stock recovery ramdisk's /system/bin",
              cmds == expected and not missing and default_reboot and default_reboot.group(1) in bins and "sh" in bins
              and "setprop" not in cmds, "programs: %s + %s; functions: %s; missing: %s" % (
                  " ".join(cmds), default_reboot.group(1) if default_reboot else "?", " ".join(funcs), missing or "none"))
        planted, _ = script_commands(text + '\nif notinramdisk1 "$x"; then log "a; b" | notinramdisk2; fi\nx=$(notinramdisk3 -f)\n')
        check("14c. (extra) the scanner itself works: three made-up programs planted in a copy of the script are all found",
              [c for c in planted if c not in bins] == ["notinramdisk1", "notinramdisk2", "notinramdisk3"])
        check("14b. (extra) the script has no carriage returns, tabs or non-ASCII bytes, and the init section is exactly the rescue "
              "service plus one post-fs-data action running the same script with `snapshot` in the recovery domain; it starts "
              "only /system/bin/sh and /system/bin/rescue.sh",
              all(b in (10,) or 32 <= b < 127 for b in open(SCRIPT, "rb").read())
              and re.findall(r"^service \S+ (.*)$", rc_extra, re.M) == ["/system/bin/sh /system/bin/rescue.sh"]
              and [l for l in rc_extra.split("\n") if l and not l.startswith("#")] == [
                  "service rescue /system/bin/sh /system/bin/rescue.sh", "    user root", "    group root",
                  "    seclabel u:r:recovery:s0", "    oneshot", "on post-fs-data",
                  "    exec u:r:recovery:s0 root root -- /system/bin/sh /system/bin/rescue.sh snapshot"])

        # 15
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "test_logosign.py")], capture_output=True, text=True)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        check("15a. logo signing tests still pass 22/22", r.returncode == 0 and last == "ALL PASS (22 checks)", last)
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "test_logocodec.py")], capture_output=True, text=True)
        n = sum(1 for l in r.stdout.splitlines() if l.startswith("PASS "))
        check("15b. test_logocodec.py still 9/9", r.returncode == 0 and n == 9, "%d PASS lines" % n)

    bad = results.count(False)
    print("ALL PASS (%d checks)" % len(results) if not bad else "FAILED: %d of %d checks" % (bad, len(results)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
