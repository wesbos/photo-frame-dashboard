"""Proof, from the code of the stock first-stage init, of where its "restart after a fatal error" word is used.

Claim checked here (offline, reads the backed-up boot.img, runs nothing from it):

  1. The word "bootloader" occurs once in the program, at file offset 0x7740 (address 0x17740).
  2. Exactly one instruction pair in the whole program forms that address: inside the static
     initialiser of reboot_utils.cpp, which builds the text object init_fatal_reboot_target from it.
  3. That object (address 0x16f048) is used in exactly one other place: InitFatalReboot, which hands it
     to RebootSystem, which passes its text to the reboot system call (number 88, RESTART2).
  4. No other direct way of forming either address was found in the file: no absolute pointer, no movw/movt pair,
     no ARM-mode pair, and every other literal-load/add-pc pair within 4 KiB whose sum happens to land
     there is ruled out one by one (the register is loaded again before the add, and no jump lands
     between that load and the add).

So changing those ten bytes to "recovery" changes one thing only: the word given to the kernel when
first-stage init gives up. What the kernel and the bootloader then do with that word is NOT proven here;
see the report.

Method: objdump (arm-none-eabi binutils) disassembles .text as Thumb; each "add rX, pc" is paired with
the latest "ldr rX, [pc, #n]" before it. Limits, stated plainly: (a) jump-table targets are not listed by
objdump, so "no jump lands in between" covers direct jumps only; (b) only code that forms one of the two
exact addresses is found: a use reached as "nearby base address plus offset" would not be seen; (c) indirect
calls are not followed. PROVEN below therefore means "no other direct reference exists", not a formal proof. Function names come from the program's own compressed symbol table (.gnu_debugdata).

Usage:  python3 -I src/bootwrap/initscan.py [--boot BACKUP_DIR/boot.img]
Exit status 0 and a last line "RESULT: PROVEN" only if every point holds.
"""
import argparse
import bisect
import hashlib
import lzma
import os
import re
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(PATCH, "tools"))
import avblib      # noqa: E402
import bootbuild   # noqa: E402

WORD = b"bootloader"
WORD_FILE, WORD_ADDR = 0x7740, 0x17740
OBJ_ADDR, OBJ_SIZE = 0x16F048, 12            # a 32-bit libc++ std::string
EXPECT_WORD_REFS = [0x5F098]
EXPECT_OBJ_REFS = [0x5EF96, 0x5F096]
EXPECT_FUNCS = {0x5F098: "_GLOBAL__sub_I_reboot_utils.cpp", 0x5F096: "_GLOBAL__sub_I_reboot_utils.cpp",
                0x5EF96: "android::init::InitFatalReboot(int)"}


def stock_init(boot_path):
    img = open(boot_path, "rb").read()
    ft, _vb = bootbuild.stock_vbmeta(img)
    boot = bootbuild.unpack_boot(img[:ft["original_image_size"]])
    entries = bootbuild.cpio_parse(bootbuild.gunzip(boot["parts"]["ramdisk"]))
    return [e for e in entries if e["name"] == "init"][0]["data"]


def sections(elf):
    shoff, shentsize, shnum, shstrndx = struct.unpack_from("<I", elf, 32)[0], *struct.unpack_from("<HHH", elf, 46)
    raw = [struct.unpack_from("<10I", elf, shoff + i * shentsize) for i in range(shnum)]
    names = raw[shstrndx]
    out = {}
    for s in raw:
        name = elf[names[4] + s[0]:elf.index(b"\0", names[4] + s[0])].decode()
        out[name] = {"addr": s[3], "off": s[4], "size": s[5]}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--boot", default=bootbuild.DEF_STOCK)
    a = ap.parse_args()
    ok = True

    def point(good, text):
        nonlocal ok
        ok = ok and good
        print("%s  %s" % ("ok  " if good else "FAIL", text))

    init = stock_init(a.boot)
    digest = hashlib.sha256(init).hexdigest()
    point(digest == bootbuild.STOCK_INIT_SHA256, "stock init, %d bytes, sha256 %s" % (len(init), digest))
    sec = sections(init)
    text, ro = sec[".text"], sec[".rodata"]

    hits = [m.start() for m in re.finditer(re.escape(WORD), init)]
    point(hits == [WORD_FILE] and init[WORD_FILE - 1] == 0 and init[WORD_FILE + 10] == 0
          and ro["off"] <= WORD_FILE < ro["off"] + ro["size"] and WORD_FILE - ro["off"] + ro["addr"] == WORD_ADDR,
          '1. "bootloader" occurs once: file offset %s, address %#x, in .rodata, a whole string' % (
              [hex(h) for h in hits], WORD_ADDR))

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "init")
        open(path, "wb").write(init)
        dis = subprocess.run([os.environ.get("PX110_ARM_OBJDUMP") or "arm-none-eabi-objdump", "-d", "-M", "force-thumb", "-j", ".text", path],
                             check=True, capture_output=True, text=True).stdout
        dbg = sec.get(".gnu_debugdata")
        syms = []
        if dbg:
            sym_path = os.path.join(tmp, "syms.elf")
            open(sym_path, "wb").write(lzma.decompress(init[dbg["off"]:dbg["off"] + dbg["size"]]))
            for line in subprocess.run(["arm-none-eabi-nm", "-C", sym_path], check=True, capture_output=True,
                                       text=True).stdout.splitlines():
                p = line.split(None, 2)
                if len(p) == 3 and p[1] in "tTwW":
                    syms.append((int(p[0], 16) & ~1, p[2]))
    syms.sort()
    starts = [s[0] for s in syms]

    def func(addr):
        i = bisect.bisect_right(starts, addr) - 1
        return syms[i][1] if i >= 0 else "?"

    def word_at(addr):
        return struct.unpack_from("<I", init, addr - text["addr"] + text["off"])[0]

    ldr_re = re.compile(r"^\s*([0-9a-f]+):\s+[0-9a-f ]+\tldr(?:\.w)?\s+(\w+), \[pc, #-?\d+\]\s+@ \(0x([0-9a-f]+)\)")
    add_re = re.compile(r"^\s*([0-9a-f]+):\s+[0-9a-f ]+\tadd\s+(\w+), pc$")
    mov_re = re.compile(r"^\s*([0-9a-f]+):\s+[0-9a-f ]+\tmov([wt])\s+(\w+), #(\d+)")
    lines = dis.splitlines()
    ldrs = {}                                    # register -> sorted [(address, literal address)]
    adds, movs = [], []
    for line in lines:
        m = ldr_re.match(line)
        if m:
            lit = int(m.group(3), 16)
            if text["addr"] <= lit <= text["addr"] + text["size"] - 4:
                ldrs.setdefault(m.group(2), []).append((int(m.group(1), 16), lit))
            continue
        m = add_re.match(line)
        if m:
            adds.append((int(m.group(1), 16), m.group(2)))
            continue
        m = mov_re.match(line)
        if m:
            movs.append((int(m.group(1), 16), m.group(2), m.group(3), int(m.group(4))))
    print("      scanned %d instructions: %d literal loads, %d add-pc" % (
        sum(1 for l in lines if "\t" in l), sum(len(v) for v in ldrs.values()), len(adds)))

    def in_word(t):
        return WORD_ADDR <= t <= WORD_ADDR + len(WORD)

    def in_obj(t):
        return OBJ_ADDR <= t < OBJ_ADDR + OBJ_SIZE

    # Straight-line pairing: an add-pc takes the latest literal load into the same register before it.
    # Every other (earlier load, add) pair that would land on one of the two addresses is a coincidence
    # only if a later load of that register sits before the add and no jump lands between that load and
    # the add; each one is checked, not assumed.
    # Literal words sit between the functions and objdump prints them as if they were instructions;
    # a "jump" that is really one half of a literal word some ldr loads is data and is left out.
    pool = set()
    for regs in ldrs.values():
        for _addr, lit in regs:
            pool.update((lit, lit + 2))
    targets = sorted(int(m.group(2), 16) for m in re.finditer(
        r"(?m)^\s*([0-9a-f]+):\s+[0-9a-f ]+\t(?:b[a-z]{0,2}(?:\.[nw])?|cbn?z)\t(?:\w+, )?0x([0-9a-f]+)", dis)
        if int(m.group(1), 16) not in pool)
    tables = len(re.findall(r"\ttb[bh]\t", dis))
    word_refs, obj_refs, ruled_out, open_cases = set(), set(), 0, []
    for addr, reg in adds:
        cands = ldrs.get(reg, [])
        hi = bisect.bisect_left(cands, (addr, 0))
        i = bisect.bisect_left(cands, (addr - 4096, 0))
        for k in range(i, hi):
            target = (word_at(cands[k][1]) + addr + 4) & 0xFFFFFFFF
            if not (in_word(target) or in_obj(target)):
                continue
            if k == hi - 1:                                   # the latest load before the add: a real reference
                (word_refs if in_word(target) else obj_refs).add(addr)
                continue
            later = cands[hi - 1][0]                          # a later load of the same register
            j = bisect.bisect_right(targets, later)
            if j < len(targets) and targets[j] <= addr:
                open_cases.append((cands[k][0], addr))
            else:
                ruled_out += 1
    for found, expect, label in ((word_refs, EXPECT_WORD_REFS, "2. the word's address is formed"),
                                 (obj_refs, EXPECT_OBJ_REFS, "3. the text object's address is formed")):
        point(sorted(found) == expect and all(func(x) == EXPECT_FUNCS[x] for x in found),
              "%s at: %s" % (label, ", ".join("%#x in %s" % (x, func(x)) for x in sorted(found)) or "nowhere"))
    point(not open_cases, "4. other load/add pairs within 4 KiB whose sum happens to land there: %d, of which %d "
                          "ruled out (register reloaded before the add, no jump lands in between), %d open %s" % (
                              ruled_out + len(open_cases), ruled_out, len(open_cases),
                              ["%#x/%#x" % c for c in open_cases] or ""))
    print("      (%d direct jump targets considered; the program has %d jump tables, whose targets are not listed)" % (
        len(targets), tables))

    # 4a. absolute pointers anywhere in the file, at any alignment
    absolute = [i for i in range(len(init) - 3)
                if in_word(struct.unpack_from("<I", init, i)[0]) or in_obj(struct.unpack_from("<I", init, i)[0])]
    point(not absolute, "4. absolute pointers to either address anywhere in the file: %d" % len(absolute))
    # 4b. movw/movt pairs
    pairs, low = [], {}
    for addr, wt, reg, val in movs:
        if wt == "w":
            low[reg] = (val, addr)
        elif reg in low and addr - low[reg][1] <= 64:
            t = (val << 16) | low[reg][0]
            if in_word(t) or in_obj(t):
                pairs.append(addr)
    point(not pairs, "4. movw/movt pairs forming either address: %d" % len(pairs))
    # 4c. ARM-mode pairs (the few ARM-mode routines are libc assembly): ldr rX, [pc, #n] followed within
    # 16 instructions by an add that uses pc and rX.
    arm = []
    code = init[text["off"]:text["off"] + text["size"]]
    for i in range(0, len(code) - 3, 4):
        w = struct.unpack_from("<I", code, i)[0]
        if (w & 0x0E5F0000) != 0x041F0000 or (w >> 28) != 0xE:           # ldr rt, [pc, #+-imm12]
            continue
        rt, off = (w >> 12) & 15, (w & 0xFFF) * (1 if w & 0x800000 else -1)
        lit = i + 8 + off
        if not 0 <= lit <= len(code) - 4:
            continue
        val = struct.unpack_from("<I", code, lit)[0]
        for j in range(i + 4, min(len(code) - 3, i + 68), 4):
            x = struct.unpack_from("<I", code, j)[0]
            if (x & 0x0FE00010) == 0x00800000 and {(x >> 16) & 15, x & 15} == {15, rt}:
                t = (val + text["addr"] + j + 8) & 0xFFFFFFFF
                if in_word(t) or in_obj(t):
                    arm.append(text["addr"] + j)
    point(not arm, "4. ARM-mode load/add-pc pairs forming either address: %d" % len(arm))

    # What happens with the object: show the hand-over to RebootSystem and the system call.
    def show(lo, hi):
        for line in lines:
            m = re.match(r"^\s*([0-9a-f]+):", line)
            if m and lo <= int(m.group(1), 16) <= hi:
                print("      " + line.strip().replace("\t", "  "))

    print("      InitFatalReboot, last instructions (r0 = 0xdead0003 = RESTART2, r1 = the text object):")
    show(0x5EF8E, 0x5EF98)
    reboot_sys = [s for s in syms if s[1].startswith("android::init::RebootSystem(")]
    called = [l for l in lines if re.match(r"^\s*5ef98:.*\tbl\t0x%x\b" % (reboot_sys[0][0] if reboot_sys else 0), l)]
    point(bool(called), "3. InitFatalReboot ends by calling RebootSystem at %#x" % (reboot_sys[0][0] if reboot_sys else 0))
    print("      RebootSystem, the call (r0 = 88 = reboot, magic numbers, then the text pointer on the stack):")
    show(0x5EC94, 0x5ECAE)
    sysc = any(re.match(r"^\s*5eca0:.*\tmovs\tr0, #88\b", l) for l in lines)
    point(sysc, "3. RebootSystem makes system call 88 (reboot) with that text")

    print("RESULT: %s" % ("PROVEN" if ok else "NOT PROVEN"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
