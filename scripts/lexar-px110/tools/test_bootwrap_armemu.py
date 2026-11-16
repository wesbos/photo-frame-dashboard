"""Test rig for the boot wrapper: runs the real ARM program on this computer (no frame, no emulator to install).

Two parts, both small and standard-library only:

  Cpu      an interpreter for the plain ARM (A32) instructions the wrapper is built from. Anything it
           does not know stops the run with an error, so a test can never pass by skipping code.
  World    a stand-in for the frame's kernel: a tiny file tree, a sysfs that can show `para` late or
           never, a 512 KiB stand-in `para` device, /dev/kmsg, fork/wait/kill/exec, and a clock that
           only moves when the program sleeps. Every system call is recorded.

run(elf, world) loads the program as the kernel would (argc/argv/envp on the stack, no open files),
runs parent and child, and returns what happened. It is used by test_bootwrap.py.
"""
import copy
import struct

M32 = 0xFFFFFFFF


class EmuError(Exception):
    """The program did something the rig does not allow or understand: always a test failure."""


class _Exit(Exception):
    def __init__(self, code):
        self.code = code


class _Exec(Exception):
    pass


class _Hang(Exception):
    pass


# ------------------------------------------------------------------ memory
class Memory:
    def __init__(self):
        self.regions = []          # (base, bytearray, writable)

    def map(self, base, data, writable):
        self.regions.append((base, bytearray(data), writable))

    def _find(self, addr, n, write=False):
        for base, data, writable in self.regions:
            if base <= addr and addr + n <= base + len(data):
                if write and not writable:
                    raise EmuError("write to read-only memory at %#x" % addr)
                return data, addr - base
        raise EmuError("memory access outside the program at %#x (%d bytes)" % (addr, n))

    def read(self, addr, n):
        data, off = self._find(addr, n)
        return bytes(data[off:off + n])

    def write(self, addr, blob):
        data, off = self._find(addr, len(blob), True)
        data[off:off + len(blob)] = blob

    def r32(self, addr):
        return struct.unpack("<I", self.read(addr, 4))[0]

    def w32(self, addr, v):
        self.write(addr, struct.pack("<I", v & M32))

    def cstr(self, addr, limit=4096):
        out = bytearray()
        while len(out) < limit:
            c = self.read(addr + len(out), 1)[0]
            if c == 0:
                return out.decode("latin1")
            out.append(c)
        raise EmuError("unterminated string at %#x" % addr)


# ------------------------------------------------------------------ ARM interpreter
def _ror(v, n):
    n &= 31
    return ((v >> n) | (v << (32 - n))) & M32 if n else v


def _sx(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


class Cpu:
    def __init__(self, mem):
        self.mem = mem
        self.r = [0] * 16
        self.n = self.z = self.c = self.v = 0
        self.steps = 0

    def clone(self):
        other = Cpu(copy.deepcopy(self.mem))
        other.r = list(self.r)
        other.n, other.z, other.c, other.v = self.n, self.z, self.c, self.v
        return other

    def _cond(self, cc):
        n, z, c, v = self.n, self.z, self.c, self.v
        return (z, not z, c, not c, n, not n, v, not v, c and not z, (not c) or z,
                n == v, n != v, (not z) and n == v, z or n != v, True)[cc]

    def _reg(self, i):
        return (self.r[15] + 8) & M32 if i == 15 else self.r[i]

    def _addc(self, a, b, carry):
        full = a + b + carry
        res = full & M32
        return res, int(full > M32), int((~(a ^ b) & (a ^ res)) >> 31 & 1)

    def _shift(self, val, typ, amt, carry, immediate):
        """Shifted register operand. Returns (value, carry out)."""
        if immediate:
            if amt == 0:
                if typ == 0:
                    return val, carry
                if typ == 3:                               # RRX
                    return ((carry << 31) | (val >> 1)) & M32, val & 1
                amt = 32
        elif amt == 0:
            return val, carry
        if typ == 0:
            if amt > 32:
                return 0, 0
            return (val << amt) & M32, (val >> (32 - amt)) & 1
        if typ == 1:
            if amt > 32:
                return 0, 0
            return (val >> amt) & M32 if amt < 32 else 0, (val >> (amt - 1)) & 1
        if typ == 2:
            if amt >= 32:
                bit = val >> 31
                return (M32 if bit else 0), bit
            return (_sx(val, 32) >> amt) & M32, (val >> (amt - 1)) & 1
        res = _ror(val, amt)
        return res, res >> 31

    def step(self, svc):
        pc = self.r[15]
        if pc & 3:
            raise EmuError("pc %#x is not ARM code" % pc)
        ins = self.mem.r32(pc)
        self.steps += 1
        cc = ins >> 28
        if cc == 15:
            raise EmuError("unsupported instruction %08x at %#x" % (ins, pc))
        nxt = (pc + 4) & M32
        if not self._cond(cc):
            self.r[15] = nxt
            return
        self.r[15] = pc                                     # so _reg(15) is right during execution
        if (ins & 0x0FF000F0) == 0x07F000F0:
            raise EmuError("undefined-instruction trap at %#x (the program ran off its end)" % pc)
        top = (ins >> 25) & 7
        if (ins & 0x0FFFFFD0) == 0x012FFF10:                # bx / blx register
            target = self._reg(ins & 15)
            if ins & 0x20:
                self.r[14] = nxt
            if target & 1:
                raise EmuError("switch to Thumb at %#x" % pc)
            self.r[15] = target
            return
        if (ins & 0x0F000000) == 0x0F000000:                # svc
            self.r[15] = nxt
            svc(self)
            return
        if top == 5:                                        # b / bl
            if ins & 0x01000000:
                self.r[14] = nxt
            self.r[15] = (pc + 8 + (_sx(ins & 0xFFFFFF, 24) << 2)) & M32
            return
        if top == 4:                                        # ldm / stm
            self._block(ins)
            if self.r[15] == pc:
                self.r[15] = nxt
            return
        if top in (2, 3):
            if top == 3 and ins & 0x10:
                self._media(ins, pc)
            else:
                self._loadstore(ins)
            if self.r[15] == pc:
                self.r[15] = nxt
            return
        if top in (0, 1):
            self._dp(ins, pc)
            if self.r[15] == pc:
                self.r[15] = nxt
            return
        raise EmuError("unsupported instruction %08x at %#x" % (ins, pc))

    def _setpc(self, v):
        if v & 1:
            raise EmuError("switch to Thumb")
        self.r[15] = v & M32
        if self.r[15] == 0:
            raise EmuError("jump to address 0")

    def _media(self, ins, pc):
        rd, rm = (ins >> 12) & 15, ins & 15
        if (ins & 0x0FE00070) == 0x07E00050:                # ubfx
            lsb, width = (ins >> 7) & 31, ((ins >> 16) & 31) + 1
            self.r[rd] = (self.r[rm] >> lsb) & ((1 << width) - 1)
        elif (ins & 0x0FFF03F0) == 0x06EF0070:              # uxtb
            self.r[rd] = self.r[rm] & 0xFF
        elif (ins & 0x0FFF03F0) == 0x06FF0070:              # uxth
            self.r[rd] = self.r[rm] & 0xFFFF
        elif (ins & 0x0FFF03F0) == 0x06AF0070:              # sxtb
            self.r[rd] = _sx(self.r[rm] & 0xFF, 8) & M32
        elif (ins & 0x0FFF03F0) == 0x06BF0070:              # sxth
            self.r[rd] = _sx(self.r[rm] & 0xFFFF, 16) & M32
        else:
            raise EmuError("unsupported instruction %08x at %#x" % (ins, pc))

    def _block(self, ins):
        p, u, s, w, load = [(ins >> b) & 1 for b in (24, 23, 22, 21, 20)]
        rn = (ins >> 16) & 15
        regs = [i for i in range(16) if ins & (1 << i)]
        if s or rn == 15 or not regs:
            raise EmuError("unsupported block transfer %08x" % ins)
        base = self.r[rn]
        count = 4 * len(regs)
        addr = base if u else base - count
        if p == u:
            addr += 4
        final = (base + count if u else base - count) & M32
        newpc = None
        for i in regs:
            if load:
                val = self.mem.r32(addr & M32)
                if i == 15:
                    newpc = val
                else:
                    self.r[i] = val
            else:
                self.mem.w32(addr & M32, self._reg(i))
            addr += 4
        if w and not (load and rn in regs):
            self.r[rn] = final
        if newpc is not None:
            self._setpc(newpc)

    def _loadstore(self, ins):
        i, p, u, b, w, load = [(ins >> k) & 1 for k in (25, 24, 23, 22, 21, 20)]
        rn, rd = (ins >> 16) & 15, (ins >> 12) & 15
        if i:
            off, _ = self._shift(self._reg(ins & 15), (ins >> 5) & 3, (ins >> 7) & 31, self.c, True)
        else:
            off = ins & 0xFFF
        base = self._reg(rn)
        target = (base + off if u else base - off) & M32
        addr = target if p else base
        if load:
            val = self.mem.read(addr, 1)[0] if b else self.mem.r32(addr)
        else:
            val = self._reg(rd)
            self.mem.write(addr, bytes([val & 0xFF]) if b else struct.pack("<I", val))
        if not p or w:
            if rn == 15:
                raise EmuError("writeback to pc")
            self.r[rn] = target
        if load:
            if rd == 15:
                self._setpc(val)
            else:
                self.r[rd] = val

    def _dp(self, ins, pc):
        imm, s = (ins >> 25) & 1, (ins >> 20) & 1
        op, rn, rd = (ins >> 21) & 15, (ins >> 16) & 15, (ins >> 12) & 15
        if not imm and (ins & 0x90) == 0x90:                # multiplies and halfword transfers
            return self._mul_or_half(ins, pc)
        if imm and (ins & 0x0FF00000) == 0x03000000:        # movw
            self.r[rd] = ((ins >> 4) & 0xF000) | (ins & 0xFFF)
            return
        if imm and (ins & 0x0FF00000) == 0x03400000:        # movt
            self.r[rd] = (self.r[rd] & 0xFFFF) | ((((ins >> 4) & 0xF000) | (ins & 0xFFF)) << 16)
            return
        if 8 <= op <= 11 and not s:
            if (ins & 0x0FFF0FF0) == 0x016F0F10:            # clz
                v = self.r[ins & 15]
                self.r[rd] = 32 - v.bit_length()
                return
            raise EmuError("unsupported instruction %08x at %#x" % (ins, pc))
        if imm:
            rot = (ins >> 8) & 15
            b = _ror(ins & 0xFF, 2 * rot)
            sc = self.c if rot == 0 else b >> 31
        elif ins & 0x10:
            if ins & 0x80:
                raise EmuError("unsupported instruction %08x at %#x" % (ins, pc))
            b, sc = self._shift(self._reg(ins & 15), (ins >> 5) & 3, self.r[(ins >> 8) & 15] & 0xFF, self.c, False)
        else:
            b, sc = self._shift(self._reg(ins & 15), (ins >> 5) & 3, (ins >> 7) & 31, self.c, True)
        a = self._reg(rn)
        carry, over = sc, self.v
        if op in (0, 8):
            res = a & b
        elif op in (1, 9):
            res = a ^ b
        elif op in (2, 10):
            res, carry, over = self._addc(a, ~b & M32, 1)
        elif op == 3:
            res, carry, over = self._addc(b, ~a & M32, 1)
        elif op in (4, 11):
            res, carry, over = self._addc(a, b, 0)
        elif op == 5:
            res, carry, over = self._addc(a, b, self.c)
        elif op == 6:
            res, carry, over = self._addc(a, ~b & M32, self.c)
        elif op == 7:
            res, carry, over = self._addc(b, ~a & M32, self.c)
        elif op == 12:
            res = a | b
        elif op == 13:
            res = b
        elif op == 14:
            res = a & ~b & M32
        else:
            res = ~b & M32
        if s:
            if rd == 15 and not 8 <= op <= 11:
                raise EmuError("unsupported return-from-exception form %08x" % ins)
            self.n, self.z, self.c, self.v = res >> 31, int(res == 0), carry, over
        if not 8 <= op <= 11:
            if rd == 15:
                self._setpc(res)
            else:
                self.r[rd] = res

    def _mul_or_half(self, ins, pc):
        if (ins & 0x0FC000F0) == 0x00000090:                # mul / mla
            rd, ra, rs, rm = (ins >> 16) & 15, (ins >> 12) & 15, (ins >> 8) & 15, ins & 15
            res = self.r[rm] * self.r[rs] + (self.r[ra] if ins & 0x200000 else 0)
            self.r[rd] = res & M32
            if ins & 0x100000:
                self.n, self.z = self.r[rd] >> 31, int(self.r[rd] == 0)
            return
        if (ins & 0x0F8000F0) == 0x00800090:                # umull / umlal / smull / smlal
            hi, lo, rs, rm = (ins >> 16) & 15, (ins >> 12) & 15, (ins >> 8) & 15, ins & 15
            a, b = self.r[rm], self.r[rs]
            if ins & 0x400000:
                a, b = _sx(a, 32), _sx(b, 32)
            res = a * b
            if ins & 0x200000:
                res += (self.r[hi] << 32) | self.r[lo]
            res &= (1 << 64) - 1
            self.r[lo], self.r[hi] = res & M32, res >> 32
            if ins & 0x100000:
                self.n, self.z = res >> 63, int(res == 0)
            return
        kind = (ins >> 5) & 3
        p, u, i, w, load = [(ins >> k) & 1 for k in (24, 23, 22, 21, 20)]
        if kind == 0 or (not load and kind != 1):
            raise EmuError("unsupported instruction %08x at %#x" % (ins, pc))
        rn, rd = (ins >> 16) & 15, (ins >> 12) & 15
        off = (((ins >> 4) & 0xF0) | (ins & 15)) if i else self.r[ins & 15]
        base = self._reg(rn)
        target = (base + off if u else base - off) & M32
        addr = target if p else base
        if load:
            if kind == 1:
                val = struct.unpack("<H", self.mem.read(addr, 2))[0]
            elif kind == 2:
                val = _sx(self.mem.read(addr, 1)[0], 8) & M32
            else:
                val = _sx(struct.unpack("<H", self.mem.read(addr, 2))[0], 16) & M32
        else:
            self.mem.write(addr, struct.pack("<H", self.r[rd] & 0xFFFF))
        if not p or w:
            self.r[rn] = target
        if load:
            self.r[rd] = val


# ------------------------------------------------------------------ the stand-in kernel
E = {"EPERM": 1, "ENOENT": 2, "EIO": 5, "ENXIO": 6, "EBADF": 9, "ECHILD": 10, "EAGAIN": 11, "ENOMEM": 12,
     "EACCES": 13, "EBUSY": 16, "EEXIST": 17, "ENOTDIR": 20, "EINVAL": 22, "EROFS": 30, "ENOTEMPTY": 39}
SYSCALLS = {1: "exit", 2: "fork", 3: "read", 4: "write", 5: "open", 6: "close", 10: "unlink", 11: "execve",
            14: "mknod", 19: "lseek", 21: "mount", 37: "kill", 39: "mkdir", 40: "rmdir", 52: "umount2",
            114: "wait4", 118: "fsync", 162: "nanosleep", 337: "unshare"}
O_DIRECT, O_CLOEXEC = 0x10000, 0x80000
PARA_SIZE = 524288
NOTE_SIZE = 2048
PLAIN_NOTE = b"boot-recovery" + b"\0" * (NOTE_SIZE - 13)

# The frame's partition table (partition-table.txt in the backup): number -> (name, sectors)
PARTITIONS = {1: ("proinfo", 6144), 2: ("nvram", 10240), 3: ("protect1", 20480), 4: ("protect2", 20480),
              5: ("persist", 98304), 6: ("seccfg", 512), 7: ("lk", 1024), 8: ("lk2", 1024), 9: ("boot", 65536),
              10: ("recovery", 65536), 11: ("para", 1024), 12: ("logo", 16384), 13: ("dtbo", 16384),
              14: ("expdb", 20480), 15: ("frp", 2048), 16: ("tee1", 10240), 17: ("tee2", 10240), 18: ("kb", 4096),
              19: ("dkb", 4096), 20: ("md_udc", 45056), 21: ("metadata", 67584), 22: ("nvdata", 8192),
              23: ("vbmeta", 8192), 24: ("vbmeta_system", 8192), 25: ("vbmeta_vendor", 8192),
              26: ("super", 5505024), 27: ("cache", 226304), 28: ("userdata", 54859264)}


def devnum(n):
    """Device number Linux gives partition n of mmcblk0 when the driver keeps 8 minors per card."""
    return (179, n) if n < 8 else (259, n - 8)


def sysfs_tree(partitions=None, disk="mmcblk0", numbers=devnum):
    """The files under /sys the wrapper reads, as {relative path: text}."""
    tree = {}
    for n, (name, sectors) in (PARTITIONS if partitions is None else partitions).items():
        major, minor = numbers(n)
        base = "class/block/%sp%d/" % (disk, n)
        tree[base + "uevent"] = "MAJOR=%d\nMINOR=%d\nDEVNAME=%sp%d\nDEVTYPE=partition\nPARTN=%d\nPARTNAME=%s\n" % (
            major, minor, disk, n, n, name)
        tree[base + "size"] = "%d\n" % sectors
    return tree


class World:
    """Everything outside the program. Set the knobs before run(); read the results after."""

    def __init__(self, para=None):
        self.para = bytearray(para if para is not None else bytes(PARA_SIZE))
        assert len(self.para) == PARA_SIZE
        self.para_dev = devnum(11)
        self.sysfs = sysfs_tree()
        self.sysfs_from_ms = 0          # sysfs shows the partitions only from this time on
        self.fs = {"/": "dir", "/init.real": "file", "/dev": "dir", "/sys": "dir", "/proc": "dir"}
        self.devs = {}                  # path -> (kind, major, minor)
        self.mounts = {}                # pid 1's mount table: what the real init will see
        self.child_mounts = None        # the child's own table, once it has asked for one (unshare)
        self.kmsg = []
        self.fail = {}                  # "syscall" or "syscall:what" -> errno name, e.g. {"open:para": "EACCES"}
        self.hang = None                # "syscall:what": the child never comes back from it
        self.short_read = False         # para reads give 512 bytes at a time
        self.short_write = False        # the para write stores and reports 512 bytes only
        self.lying_write = False        # the para write reports success but stores nothing
        self.no_direct = False          # opening para with O_DIRECT gives EINVAL
        self.exec_fails = False
        self.trace = []                 # (who, name, detail, result)
        self.para_writes = []           # (offset, length)
        self.para_reads = []            # (offset, length)
        self.opens = []                 # (path, flags)
        self.killed = []
        self.exec = None                # (path, argv, envp, time_ms, argv pointer, envp pointer)
        self.exit_codes = {}
        self.child_exit_ms = None
        self.child_hung = False
        self.child_fds_left = {}
        self.reaped = False

    def _knob(self, name, what=""):
        for key in (name + ":" + what, name):
            if key in self.fail:
                return -E[self.fail[key]]
        return None


class _Proc:
    def __init__(self, who, cpu, now=0):
        self.who, self.cpu, self.now = who, cpu, now
        self.fds = {}
        self.mounts = None              # None: shares pid 1's mount table

    def newfd(self, obj):
        fd = 0
        while fd in self.fds:
            fd += 1
        self.fds[fd] = obj
        return fd


def _parent(path):
    return path.rsplit("/", 1)[0] or "/"


def _syscall(world, proc, cpu):
    nr = cpu.r[7]
    a, b, c = cpu.r[0], cpu.r[1], cpu.r[2]
    name = SYSCALLS.get(nr)
    if name is None:
        raise EmuError("system call %d is not one the wrapper may use" % nr)
    mem = cpu.mem
    detail = ""
    mounts = world.mounts if proc.mounts is None else proc.mounts

    def done(result):
        world.trace.append((proc.who, name, detail, result))
        cpu.r[0] = result & M32

    def what_of(path):
        return {"/.bw/para": "para", "/.bw/kmsg": "kmsg", "/.bw/sys": "sys", "/.bw": "dir"}.get(path, path)

    if name in ("open", "unlink", "mknod", "mkdir", "rmdir", "umount2", "execve"):
        path = mem.cstr(a)
        detail = path
    elif name == "mount":
        path = mem.cstr(b)
        detail = "%s on %s type %s" % (mem.cstr(a), path, mem.cstr(c))
    else:
        path = None
    target = what_of(path) if path else ""
    if name in ("read", "write", "lseek", "fsync"):
        obj = proc.fds.get(a)
        target = obj["kind"] if obj else ""
        detail = "fd %d (%s)" % (a, target)
    if proc.who == "child" and world.hang in (name, name + ":" + target):
        world.trace.append((proc.who, name, detail, "HANGS"))
        raise _Hang()
    forced = world._knob(name, target)
    if forced is not None and name not in ("exit",):
        return done(forced)

    if name == "exit":
        world.trace.append((proc.who, name, str(a), None))
        raise _Exit(a)
    if name == "fork":
        if proc.who != "parent" or world.child_exit_ms is not None or world.child_hung:
            raise EmuError("unexpected fork")
        kid = _Proc("child", cpu.clone(), proc.now)
        kid.cpu.r[0] = 0
        world.trace.append((proc.who, name, "", 100))
        try:
            _run(world, kid)
        except _Hang:
            world.child_hung = True
        except _Exec:
            raise EmuError("the child started init.real; only the parent (pid 1) may")
        else:
            world.child_exit_ms = kid.now
            world.child_fds_left = dict(kid.fds)
        cpu.r[0] = 100
        return
    if name == "unshare":
        if proc.who != "child" or a != 0x20000:
            raise EmuError("unshare by the parent, or of something other than the mount table")
        if proc.mounts is None:
            proc.mounts = world.child_mounts = dict(world.mounts)
        return done(0)
    if name == "wait4":
        if a != 100 or not (c & 1):
            raise EmuError("wait4 must wait for the child with WNOHANG")
        if world.child_exit_ms is not None and proc.now >= world.child_exit_ms:
            if world.reaped:
                return done(-E["ECHILD"])
            world.reaped = True
            mem.w32(b, world.exit_codes.get("child", 0) << 8)
            return done(100)
        return done(0)
    if name == "nanosleep":
        sec, nsec = mem.r32(a), mem.r32(a + 4)
        if sec != 0 or not 0 < nsec <= 100000000:
            raise EmuError("unexpected sleep of %d s %d ns" % (sec, nsec))
        proc.now += nsec // 1000000
        detail = "%d ms" % (nsec // 1000000)
        return done(0)
    if name == "kill":
        if a != 100 or b != 9:
            raise EmuError("kill of something that is not the child, or not SIGKILL")
        world.killed.append((a, b, proc.now))
        return done(0)
    if name == "execve":
        def strings(ptr):
            out = []
            while True:
                p = mem.r32(ptr + 4 * len(out))
                if p == 0:
                    return out
                out.append(mem.cstr(p))
        world.exec = (path, strings(b), strings(c), proc.now, b, c)
        if world.exec_fails or world.fs.get(path) != "file":
            return done(-E["ENOENT"])
        world.trace.append((proc.who, name, detail, "replaces the program"))
        raise _Exec()
    if name == "mkdir":
        if path in world.fs:
            return done(-E["EEXIST"])
        if world.fs.get(_parent(path)) != "dir":
            return done(-E["ENOENT"])
        world.fs[path] = "dir"
        return done(0)
    if name == "rmdir":
        if world.fs.get(path) != "dir":
            return done(-E["ENOENT"])
        if path in world.mounts or path in mounts:
            return done(-E["EBUSY"])
        if any(p != path and _parent(p) == path for p in world.fs):
            return done(-E["ENOTEMPTY"])
        del world.fs[path]
        return done(0)
    if name == "unlink":
        if world.fs.get(path) not in ("node", "file"):
            return done(-E["ENOENT"])
        del world.fs[path]
        world.devs.pop(path, None)
        return done(0)
    if name == "mknod":
        if path in world.fs:
            return done(-E["EEXIST"])
        if world.fs.get(_parent(path)) != "dir" or _parent(path) in mounts:
            return done(-E["ENOENT"])
        kind = {0o020000: "chr", 0o060000: "blk"}.get(b & 0o170000)
        if kind is None or (b & 0o7777) != 0o600:
            raise EmuError("mknod with mode %o" % b)
        world.fs[path] = "node"
        world.devs[path] = (kind, (c >> 8) & 0xFFF, (c & 0xFF) | ((c >> 12) & 0xFFF00))
        detail += " %s %d:%d" % world.devs[path]
        return done(0)
    if name == "mount":
        if mem.cstr(c) != "sysfs" or cpu.r[3] != 0:
            raise EmuError("unexpected mount: " + detail)
        if world.fs.get(path) != "dir":
            return done(-E["ENOENT"])
        if path in mounts:
            return done(-E["EBUSY"])
        if path == "/sys":
            raise EmuError("sysfs mounted on /sys: the real init's own mount there would then fail")
        mounts[path] = "sysfs"
        return done(0)
    if name == "umount2":
        if path not in mounts:
            return done(-E["EINVAL"])
        del mounts[path]
        return done(0)
    if name == "open":
        flags = b
        world.opens.append((path, flags))
        mount = next((m for m in mounts if path.startswith(m + "/")), None)
        if mount:
            if flags & 3:
                return done(-E["EACCES"])
            text = world.sysfs.get(path[len(mount) + 1:]) if proc.now >= world.sysfs_from_ms else None
            if text is None:
                return done(-E["ENOENT"])
            return done(proc.newfd({"kind": "sysfs", "data": text.encode(), "pos": 0}))
        if world.fs.get(path) != "node":
            return done(-E["ENOENT"])
        kind, major, minor = world.devs[path]
        if (kind, major, minor) == ("chr", 1, 11):
            return done(proc.newfd({"kind": "kmsg"}))
        if kind == "blk" and (major, minor) == world.para_dev:
            if (flags & 3) != 2:
                raise EmuError("para opened without read+write")
            if flags & O_DIRECT and world.no_direct:
                return done(-E["EINVAL"])
            return done(proc.newfd({"kind": "para", "pos": 0, "direct": bool(flags & O_DIRECT)}))
        return done(-E["ENXIO"])
    obj = proc.fds.get(a)
    if name == "close":
        detail = "fd %d" % a
        if obj is None:
            return done(-E["EBADF"])
        del proc.fds[a]
        return done(0)
    if obj is None:
        return done(-E["EBADF"])
    if name == "lseek":
        if obj["kind"] != "para" or c != 0:
            raise EmuError("unexpected seek")
        obj["pos"] = b
        return done(b)
    if name == "fsync":
        return done(0)
    if name == "read":
        if obj["kind"] == "sysfs":
            chunk = obj["data"][obj["pos"]:obj["pos"] + c]
            obj["pos"] += len(chunk)
            mem.write(b, chunk)
            return done(len(chunk))
        if obj["kind"] != "para":
            return done(-E["EBADF"])
        if obj["direct"] and (b % 512 or c % 512 or obj["pos"] % 512):
            return done(-E["EINVAL"])
        n = min(c, 512) if world.short_read else c
        n = max(0, min(n, PARA_SIZE - obj["pos"]))
        world.para_reads.append((obj["pos"], n))
        mem.write(b, bytes(world.para[obj["pos"]:obj["pos"] + n]))
        obj["pos"] += n
        return done(n)
    if name == "write":
        data = mem.read(b, c)
        if obj["kind"] == "kmsg":
            if not data.endswith(b"\n") or len(data) > 512 or b"\n" in data[:-1]:
                raise EmuError("kernel log write is not one clean line: %r" % data)
            world.kmsg.append(data[:-1].decode("latin1"))
            return done(c)
        if obj["kind"] != "para":
            return done(-E["EBADF"])
        world.para_writes.append((obj["pos"], c))
        if obj["direct"] and (b % 512 or c % 512 or obj["pos"] % 512):
            return done(-E["EINVAL"])
        n = 512 if world.short_write else c
        if not world.lying_write:
            world.para[obj["pos"]:obj["pos"] + n] = data[:n]
        obj["pos"] += n
        return done(n)
    raise EmuError("unhandled system call " + name)


def _run(world, proc, max_steps=20000000):
    try:
        while True:
            proc.cpu.step(lambda cpu: _syscall(world, proc, cpu))
            if proc.cpu.steps > max_steps:
                raise EmuError("%s ran %d instructions without finishing" % (proc.who, max_steps))
    except _Exit as e:
        world.exit_codes[proc.who] = e.code


def load(elf, argv, envp):
    """Lay the program out as the kernel does. Returns a Cpu ready at its entry point."""
    mem = Memory()
    entry, phoff, phnum = struct.unpack_from("<I", elf, 24)[0], struct.unpack_from("<I", elf, 28)[0], struct.unpack_from("<H", elf, 44)[0]
    for i in range(phnum):
        typ, off, vaddr, _p, filesz, memsz, flags, _al = struct.unpack_from("<8I", elf, phoff + 32 * i)
        if typ == 1:
            mem.map(vaddr, elf[off:off + filesz] + bytes(memsz - filesz), bool(flags & 2))
    top, size = 0x7F000000, 0x20000
    stack = bytearray(size)
    pos = size
    ptrs = []
    for group in (argv, envp):
        addrs = []
        for s in group:
            raw = s.encode() + b"\0"
            pos -= len(raw)
            stack[pos:pos + len(raw)] = raw
            addrs.append(top - size + pos)
        ptrs.append(addrs)
    words = [len(argv)] + ptrs[0] + [0] + ptrs[1] + [0] + [0, 0]          # ..., then an empty auxv
    pos = (pos - 4 * len(words)) & ~15
    stack[pos:pos + 4 * len(words)] = struct.pack("<%dI" % len(words), *words)
    mem.map(top - size, stack, True)
    cpu = Cpu(mem)
    cpu.r[13] = top - size + pos
    cpu.r[15] = entry
    info = {"argv_ptr": cpu.r[13] + 4, "envp_ptr": cpu.r[13] + 4 + 4 * (len(argv) + 1)}
    return cpu, info


def run(elf, world, argv=("/init",), envp=("HOME=/", "TERM=linux")):
    """Run the wrapper as pid 1. Returns the layout info; everything else is in `world`."""
    cpu, info = load(elf, list(argv), list(envp))
    try:
        _run(world, _Proc("parent", cpu))
    except _Exec:
        pass
    return info
