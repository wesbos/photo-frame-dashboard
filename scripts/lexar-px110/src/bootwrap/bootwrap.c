/* bootwrap: runs as /init in the Lexar frame's boot ramdisk, before anything else.
 *
 * Job: if the bootloader message (first 2048 bytes of the `para` partition) is all zero, write our
 * plain recovery note there ("boot-recovery", 13 bytes, then zeros; patch/out-recovery/STORE-FORMAT.md),
 * read it back, then start the real first-stage init (/init.real) with the same arguments and
 * environment. On ANY error it goes on to /init.real at once.
 *
 * Shape (so that nothing here can hold up a start):
 *   parent (pid 1): fork; wait for the child, at most PARENT_POLLS x POLL_MS; kill it if it is
 *                   still there; exec /init.real. Opens nothing, mounts nothing, writes nothing.
 *   child:          all the work, in a private directory /.bw (its own sysfs mount and device
 *                   nodes), which it removes again before it exits. It first takes a mount table of
 *                   its own (unshare), so its sysfs mount never exists for pid 1, not even if the
 *                   child is cut off half way: the real init moves every mount it sees when it
 *                   switches root and treats a mount it cannot move as fatal.
 *
 * Rules the tests hold it to:
 *   - the only write to `para` is one write() of exactly 2048 bytes at offset 0;
 *   - that write happens only if the 2048 bytes just read are all zero;
 *   - `para` is found by name (PARTNAME=para on mmcblk0, 1024 sectors), never by a fixed number;
 *   - /init.real is always exec'd, with argv and envp untouched.
 *
 * No C library: raw ARM EABI system calls only. Built by patch/tools/bootbuild.py.
 */

typedef unsigned int u32;
typedef unsigned char u8;

/* ---- ARM EABI system call numbers (arch/arm, kernel 4.14) ---- */
#define NR_exit 1
#define NR_fork 2
#define NR_read 3
#define NR_write 4
#define NR_open 5
#define NR_close 6
#define NR_unlink 10
#define NR_execve 11
#define NR_mknod 14
#define NR_lseek 19
#define NR_mount 21
#define NR_kill 37
#define NR_mkdir 39
#define NR_rmdir 40
#define NR_umount2 52
#define NR_wait4 114
#define NR_fsync 118
#define NR_nanosleep 162
#define NR_unshare 337

#define O_RDONLY 0
#define O_WRONLY 1
#define O_RDWR 2
#define O_DIRECT 0x10000 /* ARM value */
#define O_CLOEXEC 0x80000
#define S_IFCHR 0020000
#define S_IFBLK 0060000
#define WNOHANG 1
#define SIGKILL 9
#define MNT_DETACH 2
#define CLONE_NEWNS 0x20000
#define EINVAL 22

#define NOTE_SIZE 2048       /* the bootloader message; we never read or write beyond it */
#define PARA_SECTORS 1024    /* `para` is 524288 bytes on this frame */
#define MAX_PART 63          /* highest partition number looked at on mmcblk0 */
#define POLL_MS 50
#define DEVICE_POLLS 60      /* child: wait at most 60 x 50 ms = 3 s for `para` to appear */
#define PARENT_POLLS 100     /* parent: wait at most 100 x 50 ms = 5 s for the child */

static long sc(long nr, long a, long b, long c, long d, long e)
{
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r4 __asm__("r4") = e;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2), "r"(r3), "r"(r4) : "memory", "cc");
    return r0; /* a negative value is -errno */
}

/* The compiler may turn loops into calls to these; with no C library we supply them. */
void *memset(void *d, int c, unsigned long n)
{
    volatile u8 *p = d;
    while (n--) *p++ = (u8)c;
    return d;
}
void *memcpy(void *d, const void *s, unsigned long n)
{
    volatile u8 *p = d;
    const u8 *q = s;
    while (n--) *p++ = *q++;
    return d;
}

static const char DIR[] = "/.bw";
static const char SYS[] = "/.bw/sys";
static const char KMSG[] = "/.bw/kmsg";
static const char PARA[] = "/.bw/para";
static const char REAL[] = "/init.real";
static const char NOTE[13] = {'b', 'o', 'o', 't', '-', 'r', 'e', 'c', 'o', 'v', 'e', 'r', 'y'};

/* O_DIRECT needs block-aligned buffers. */
static u8 buf[NOTE_SIZE] __attribute__((aligned(4096)));
static u8 want[NOTE_SIZE] __attribute__((aligned(4096)));
static char text[512];

static void nap(void)
{
    long ts[2];
    ts[0] = 0;
    ts[1] = POLL_MS * 1000000L;
    sc(NR_nanosleep, (long)ts, 0, 0, 0, 0);
}

/* ---- kernel log ---- */
static int kfd = -1;
static char line[160];
static u32 ll;

static void l_s(const char *s)
{
    while (*s && ll < sizeof(line) - 1) line[ll++] = *s++;
}
static void l_n(u32 v) /* decimal, without a division routine */
{
    static const u32 pw[10] = {1000000000u, 100000000u, 10000000u, 1000000u, 100000u, 10000u, 1000u, 100u, 10u, 1u};
    int i, on = 0;
    for (i = 0; i < 10; i++) {
        char c = '0';
        while (v >= pw[i]) {
            v -= pw[i];
            c++;
        }
        if (c != '0' || on || i == 9) {
            on = 1;
            if (ll < sizeof(line) - 1) line[ll++] = c;
        }
    }
}
static void l_begin(void)
{
    ll = 0;
    l_s("<6>bootwrap: ");
}
static void l_end(void)
{
    line[ll++] = '\n';
    if (kfd >= 0) sc(NR_write, kfd, (long)line, ll, 0, 0);
}
static void say(const char *s)
{
    l_begin();
    l_s(s);
    l_end();
}
static void fail(const char *what, long err)
{
    l_begin();
    l_s("ERROR ");
    l_s(what);
    l_s(" errno ");
    l_n((u32)(-err));
    l_s("; going on");
    l_end();
}

/* ---- small text helpers ---- */
static char *put(char *p, const char *s)
{
    while (*s) *p++ = *s++;
    *p = 0;
    return p;
}
static char *putn(char *p, u32 v) /* 0..99 */
{
    char t = '0';
    while (v >= 10) {
        v -= 10;
        t++;
    }
    if (t != '0') *p++ = t;
    *p++ = (char)('0' + v);
    *p = 0;
    return p;
}
static long slurp(const char *path, char *out, u32 max)
{
    long fd = sc(NR_open, (long)path, O_RDONLY | O_CLOEXEC, 0, 0, 0);
    long n;
    if (fd < 0) return fd;
    n = sc(NR_read, fd, (long)out, max - 1, 0, 0);
    sc(NR_close, fd, 0, 0, 0, 0);
    if (n < 0) return n;
    out[n] = 0;
    return n;
}
/* Value of a whole line "KEY=value" in a uevent text. Returns the value's start, or 0. */
static const char *field(const char *t, const char *key)
{
    while (*t) {
        const char *a = t, *k = key;
        while (*k && *a == *k) {
            a++;
            k++;
        }
        if (!*k) return a;
        while (*t && *t != '\n') t++;
        if (*t) t++;
    }
    return 0;
}
static int is_word(const char *v, const char *w) /* value equals w up to the end of its line */
{
    while (*w) {
        if (*v++ != *w++) return 0;
    }
    return *v == '\n' || *v == 0;
}
static long number(const char *v) /* decimal up to end of line; -1 if not a clean number */
{
    u32 n = 0;
    int digits = 0;
    while (*v >= '0' && *v <= '9') {
        if (++digits > 7) return -1;
        n = n * 10 + (u32)(*v++ - '0');
    }
    if (!digits || (*v != '\n' && *v != 0)) return -1;
    return (long)n;
}

/* Look once for `para` among mmcblk0's partitions. 1 = found (major/minor set), 0 = not there yet,
 * negative = found by name but something about it is not as expected. */
static long find_para(u32 *major, u32 *minor)
{
    static char path[64];
    u32 n;
    for (n = 1; n <= MAX_PART; n++) {
        char *p = put(path, SYS);
        const char *v;
        long ma, mi;
        p = put(p, "/class/block/mmcblk0p");
        p = putn(p, n);
        char *leaf = p;
        put(leaf, "/uevent");
        if (slurp(path, text, sizeof(text)) <= 0) continue;
        v = field(text, "PARTNAME=");
        if (!v || !is_word(v, "para")) continue;
        v = field(text, "MAJOR=");
        ma = v ? number(v) : -1;
        v = field(text, "MINOR=");
        mi = v ? number(v) : -1;
        if (ma <= 0 || ma > 4095 || mi < 0 || mi > 1048575) return -1;
        put(leaf, "/size");
        if (slurp(path, text, sizeof(text)) <= 0) return -2;
        if (number(text) != PARA_SECTORS) return -3;
        *major = (u32)ma;
        *minor = (u32)mi;
        return 1;
    }
    return 0;
}

static long read_note(long fd, u8 *out)
{
    u32 got = 0;
    long r = sc(NR_lseek, fd, 0, 0 /* SEEK_SET */, 0, 0);
    if (r != 0) return r < 0 ? r : -EINVAL;
    while (got < NOTE_SIZE) {
        r = sc(NR_read, fd, (long)(out + got), NOTE_SIZE - got, 0, 0);
        if (r < 0) return r;
        if (r == 0) return -EINVAL; /* shorter than a note: not our device */
        got += (u32)r;
    }
    return 0;
}

static void work(void)
{
    u32 major = 0, minor = 0, i, dev;
    long r, fd;
    int zero = 1, ours = 1;

    r = find_para(&major, &minor);
    for (i = 1; r == 0 && i < DEVICE_POLLS; i++) {
        nap();
        r = find_para(&major, &minor);
    }
    if (r == 0) {
        say("para did not appear in 3 s; note not touched, going on");
        return;
    }
    if (r < 0) {
        fail("para found by name but not as expected, check", r);
        return;
    }

    dev = (minor & 0xff) | (major << 8) | ((minor & ~0xffu) << 12);
    sc(NR_unlink, (long)PARA, 0, 0, 0, 0);
    r = sc(NR_mknod, (long)PARA, S_IFBLK | 0600, dev, 0, 0);
    if (r < 0) {
        fail("mknod para", r);
        return;
    }
    fd = sc(NR_open, (long)PARA, O_RDWR | O_DIRECT | O_CLOEXEC, 0, 0, 0);
    if (fd == -EINVAL) fd = sc(NR_open, (long)PARA, O_RDWR | O_CLOEXEC, 0, 0, 0);
    if (fd < 0) {
        fail("open para", fd);
        goto out;
    }
    r = read_note(fd, buf);
    if (r < 0) {
        fail("read para", r);
        goto close;
    }

    for (i = 0; i < NOTE_SIZE; i++) want[i] = i < sizeof(NOTE) ? (u8)NOTE[i] : 0;
    for (i = 0; i < NOTE_SIZE; i++) {
        if (buf[i]) zero = 0;
        if (buf[i] != want[i]) ours = 0;
    }
    if (ours) {
        say("para holds our plain note already; nothing written");
        goto close;
    }
    if (!zero) {
        say("para holds a note that is not ours; left alone, nothing written");
        goto close;
    }

    r = sc(NR_lseek, fd, 0, 0, 0, 0);
    if (r != 0) {
        fail("seek para", r);
        goto close;
    }
    r = sc(NR_write, fd, (long)want, NOTE_SIZE, 0, 0); /* the one and only write to para */
    if (r != NOTE_SIZE) {
        fail("write para", r < 0 ? r : -EINVAL);
        goto close;
    }
    r = sc(NR_fsync, fd, 0, 0, 0, 0);
    if (r < 0) {
        fail("fsync para", r);
        goto close;
    }
    r = read_note(fd, buf);
    if (r < 0) {
        fail("read back para", r);
        goto close;
    }
    for (i = 0; i < NOTE_SIZE; i++) {
        if (buf[i] != want[i]) {
            say("ERROR note written but it does not read back as ours; going on");
            goto close;
        }
    }
    l_begin();
    l_s("para was empty: armed boot-recovery, read back ok (dev ");
    l_n(major);
    l_s(":");
    l_n(minor);
    l_s(")");
    l_end();

close:
    sc(NR_close, fd, 0, 0, 0, 0);
out:
    sc(NR_unlink, (long)PARA, 0, 0, 0, 0);
}

static void child(void)
{
    sc(NR_mkdir, (long)DIR, 0700, 0, 0, 0); /* may exist already; the next steps tell */
    sc(NR_unlink, (long)KMSG, 0, 0, 0, 0);
    if (sc(NR_mknod, (long)KMSG, S_IFCHR | 0600, (1 << 8) | 11, 0, 0) == 0)
        kfd = (int)sc(NR_open, (long)KMSG, O_WRONLY | O_CLOEXEC, 0, 0, 0);
    sc(NR_unlink, (long)KMSG, 0, 0, 0, 0);
    say("start");

    {
        /* A mount table of our own first. Without it nothing is mounted and no work is done. */
        long r = sc(NR_unshare, CLONE_NEWNS, 0, 0, 0, 0);
        if (r < 0) {
            fail("unshare", r);
        } else {
            sc(NR_mkdir, (long)SYS, 0700, 0, 0, 0);
            r = sc(NR_mount, (long)"sysfs", (long)SYS, (long)"sysfs", 0, 0);
            if (r < 0) {
                fail("mount sysfs", r);
            } else {
                work();
                sc(NR_umount2, (long)SYS, MNT_DETACH, 0, 0, 0);
            }
        }
    }
    sc(NR_rmdir, (long)SYS, 0, 0, 0, 0);
    sc(NR_rmdir, (long)DIR, 0, 0, 0, 0);
    say("done, starting init.real");
    sc(NR_exit, 0, 0, 0, 0, 0);
}

void cmain(long *sp)
{
    long argc = sp[0];
    char **argv = (char **)(sp + 1);
    char **envp = argv + argc + 1;
    long pid = sc(NR_fork, 0, 0, 0, 0, 0);

    if (pid == 0) {
        child();
        for (;;) sc(NR_exit, 0, 0, 0, 0, 0);
    }
    if (pid > 0) {
        int i;
        for (i = 0; i < PARENT_POLLS; i++) {
            long st = 0;
            long r = sc(NR_wait4, pid, (long)&st, WNOHANG, 0, 0);
            if (r != 0) break; /* the child is gone, or waiting failed: go on */
            nap();
        }
        if (i == PARENT_POLLS) sc(NR_kill, pid, SIGKILL, 0, 0, 0);
    }
    sc(NR_execve, (long)REAL, (long)argv, (long)envp, 0, 0);
    /* Only reached if /init.real cannot be started. Nothing else can be: leaving ends pid 1, the
     * kernel restarts the frame, and an armed note takes it to recovery. */
    for (;;) sc(NR_exit, 127, 0, 0, 0, 0);
}

__asm__(".text\n"
        ".arm\n"
        ".global _start\n"
        ".type _start, %function\n"
        "_start:\n"
        "    mov fp, #0\n"
        "    mov lr, #0\n"
        "    mov r0, sp\n"
        "    bic sp, sp, #7\n"
        "    bl cmain\n"
        "    udf #0\n");
