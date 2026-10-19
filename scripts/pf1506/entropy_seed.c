/*
 * entropy_seed: carry kernel RNG entropy across reboots on the PF1506 frame.
 *
 * The 4.9 kernel has no hardware RNG, so the CRNG only initialises after ~67 s of
 * interrupt entropy, and boringssl_self_test32 (init.rc "on init") blocks boot
 * until then. In the spirit of systemd-random-seed (but much simpler, and not
 * equivalent), we save 512 random bytes once boot has completed and credit them
 * at the next early-init, before the self test.
 *
 *   entropy_seed load <file>   credit <file> to the input pool, then delete it
 *   entropy_seed save <file>   write a fresh seed (never blocks)
 *
 * Every path exits quickly: a missing/short seed is skipped, and save uses
 * GRND_NONBLOCK. A seed is credited only after its deletion has been synced to
 * storage, so a crash or power cut can't make this device credit the same file
 * twice. That doesn't cover a seed that is copied: restoring /metadata from a
 * backup, or cloning it to another frame, would credit a seed that was already
 * used. Don't copy /metadata/entropy_seed between devices or restore it.
 */
#include <errno.h>
#include <libgen.h>
#include <fcntl.h>
#include <linux/random.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/random.h>
#include <sys/stat.h>
#include <unistd.h>

#define SEED_BYTES 512

static void klog(const char *msg) {
    int fd = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
    if (fd < 0) return;
    char line[256];
    int n = snprintf(line, sizeof line, "<6>entropy_seed: %s\n", msg);
    if (n > 0) write(fd, line, (size_t)n);
    close(fd);
}

static int load(const char *path) {
    struct {
        struct rand_pool_info info;
        unsigned char buf[SEED_BYTES];
    } req;
    char msg[128];

    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) { klog("no saved seed"); return 0; }
    ssize_t n = read(fd, req.buf, sizeof req.buf);
    close(fd);

    /* Delete the seed and sync the directory BEFORE crediting it. If either step
     * fails, the seed is not credited: boot is then just slow once. */
    if (unlink(path) != 0) {
        snprintf(msg, sizeof msg, "could not delete seed (%s), not credited", strerror(errno));
        klog(msg);
        memset(req.buf, 0, sizeof req.buf);
        return 0;
    }
    char dir[256];
    snprintf(dir, sizeof dir, "%s", path);
    int dfd = open(dirname(dir), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (dfd < 0 || fsync(dfd) != 0) {
        klog("could not sync the seed's deletion, not credited");
        if (dfd >= 0) close(dfd);
        memset(req.buf, 0, sizeof req.buf);
        return 0;
    }
    close(dfd);
    if (n < 64) { klog("seed too short, skipped"); return 0; }

    req.info.entropy_count = (int)n * 8;
    req.info.buf_size = (int)n;
    fd = open("/dev/urandom", O_WRONLY | O_CLOEXEC);
    if (fd < 0) { klog("cannot open /dev/urandom"); return 0; }
    if (ioctl(fd, RNDADDENTROPY, &req.info) != 0) {
        snprintf(msg, sizeof msg, "RNDADDENTROPY failed: %s", strerror(errno));
        klog(msg);
    } else {
        snprintf(msg, sizeof msg, "credited %d bits", req.info.entropy_count);
        klog(msg);
    }
    close(fd);
    memset(req.buf, 0, sizeof req.buf);
    return 0;
}

static int save(const char *path) {
    unsigned char buf[SEED_BYTES];
    char tmp[512];
    if (getrandom(buf, sizeof buf, GRND_NONBLOCK) != (ssize_t)sizeof buf) {
        klog("CRNG not ready, seed not saved");
        return 0;
    }
    snprintf(tmp, sizeof tmp, "%s.tmp", path);
    int fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) { klog("cannot write seed"); return 0; }
    int ok = write(fd, buf, sizeof buf) == (ssize_t)sizeof buf && fsync(fd) == 0;
    close(fd);
    memset(buf, 0, sizeof buf);
    if (!ok || rename(tmp, path) != 0) { unlink(tmp); klog("seed save failed"); return 0; }
    klog("seed saved");
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s load|save <file>\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "load") == 0) return load(argv[2]);
    if (strcmp(argv[1], "save") == 0) return save(argv[2]);
    return 2;
}
