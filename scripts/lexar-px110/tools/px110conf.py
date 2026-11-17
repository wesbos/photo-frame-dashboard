"""Where this unit's files are, and what the stock firmware must look like.

One settings file, `unit.conf` next to the `tools` folder (copy `unit.conf.example`), or the
environment: `PX110_<NAME>` wins over the same NAME in unit.conf. `PX110_CONF` names another
settings file. Nothing here is unit-specific and nothing here talks to the frame.

    python3 -I tools/px110conf.py show          print every setting as the tools see it
    python3 -I tools/px110conf.py get NAME      print one setting (empty if unset)
    python3 -I tools/px110conf.py check-backup  is BACKUP_DIR the stock firmware these tools are fixed to?

The tools are tied to one firmware on purpose: PF1106_V2.06_20250527. The hashes of its stock
partition images are below; a backup that does not match is refused.
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)                       # scripts/lexar-px110
SRC = os.path.join(BASE, "src")
CONF = os.environ.get("PX110_CONF") or os.path.join(BASE, "unit.conf")

FIRMWARE = "PF1106_V2.06_20250527"

# SHA-256 of the stock partition images of that firmware, as read from the frame before any change.
# These are firmware images, the same on every unit that runs it; none holds a serial or an address.
STOCK_SHA256 = {
    "boot.img": "d232adc9af4f5dfe12c6c8bc6548519ef2dc113693e1cc7ad9665b7041718172",
    "recovery.img": "14950f348b4722a99b7695f2fee1a25e23f3d450f5f180743ff9ee9b02a2943f",
    "logo.img": "b2e2fc50b1243f0716a94b51fc9bc37e1489d2f3c1c1dcab91df5b4df328ab93",
    "lk.img": "7ed3ad77a4f0ad9803b2ba490f0bbe5b307856e3983dbc5d967e5e0e643e672c",
    "vbmeta.img": "e8ceb4834050f0a0c49a05d8f2dabf73671b5aafefa9520e301e3e3cf1c8a6c4",
    "vbmeta_system.img": "cecf0e040df5d2c59735b10815b867227ebeb541e9b1a6fb8ad902c697194cbb",
    "vbmeta_vendor.img": "60841f7a0debc3f64e7bbc83ca8295037bd5ad1a1bd6cb65577f432b260558e0",
    "super.img": "47a75dd03635c7a1d40e757a034ade0bce057f8429c15f2e732116cd3c231d01",
}

# Where `product` sits inside `super` on this firmware. rescue.sh and frame-doctor.sh have these
# numbers fixed in them, so a `super` laid out differently must never be built for.
PRODUCT_FIRST_BLOCK = 32512                        # 4096-byte blocks from the start of super
PRODUCT_BYTES = 109813760
STOCK_PRODUCT_SHA256 = "c5384ae1b53f444af60ef53735086c5e6c284df42912bbcedb314a2fb560d788"   # that region, stock


class NotSet(Exception):
    """A setting the tool needs is missing. Tests turn this into a skip, tools into a clear stop."""


def _read_conf():
    out = {}
    if not os.path.isfile(CONF):
        return out
    with open(CONF) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            out[key.strip()] = value
    return out


_CONF = _read_conf()


def get(name, default=""):
    """The setting NAME: environment PX110_NAME, else unit.conf, else the default."""
    value = os.environ.get("PX110_" + name)
    if value is None or value == "":
        value = _CONF.get(name, "")
    return value if value != "" else default


def path(name, default=""):
    """A setting that is a file or folder: `~` is expanded, a relative path is taken from BASE."""
    value = get(name, default)
    if not value:
        return ""
    value = os.path.expanduser(value)
    return value if os.path.isabs(value) else os.path.normpath(os.path.join(BASE, value))


def build_dir(*parts):
    """Where the tools write: BUILD_DIR (default `build/` here, which git ignores)."""
    return os.path.join(path("BUILD_DIR", "build"), *parts)


def backup(name):
    """A file in the user's own backup of the frame (BACKUP_DIR). Raises NotSet without one."""
    folder = path("BACKUP_DIR")
    if not folder:
        raise NotSet("BACKUP_DIR is not set (unit.conf or PX110_BACKUP_DIR): the folder holding your own "
                     "backup of the frame's partitions, as <name>.img")
    return os.path.join(folder, name)


def key(name):
    """A key file in KEY_DIR (default `keys/` here, which git ignores; fetch-keys.sh fills it)."""
    return os.path.join(path("KEY_DIR", "keys"), name)


def tool(name, default):
    """A program: the setting if given, else `default`, which is then looked up on the PATH."""
    value = get(name)
    return os.path.expanduser(value) if value else default


def e2fs(program):
    """debugfs, e2fsck or dumpe2fs from e2fsprogs: in E2FSPROGS_DIR if set, else on the PATH."""
    folder = path("E2FSPROGS_DIR")
    return os.path.join(folder, program) if folder else program


def sha256_file(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_stock(file_path, name=None):
    """Stop unless the file is the stock image of this firmware. name: which image it must be."""
    name = name or os.path.basename(file_path)
    want = STOCK_SHA256[name]
    if not os.path.isfile(file_path):
        raise ValueError("%s is missing: %s" % (name, file_path))
    got = sha256_file(file_path)
    if got != want:
        raise ValueError("%s is not the stock %s image (sha256 %s, expected %s). These tools only build for "
                         "that firmware; refusing" % (file_path, FIRMWARE, got, want))


def check_product_layout(super_path):
    """Stop unless `product` sits in this `super` exactly where rescue.sh and frame-doctor.sh expect:
    one extent, 4096-byte blocks 32512 onward, 109,813,760 bytes, the same in every metadata slot."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import lp
    try:
        _geom, metas = lp.parse(super_path)
    except (ValueError, OSError) as e:
        raise ValueError("%s: cannot read the dynamic-partition table (%s); refusing" % (super_path, e))
    want = [(PRODUCT_FIRST_BLOCK * 4096, PRODUCT_BYTES)]
    valid = [m["slot"] for m in metas if m.get("valid")]
    if 0 not in valid:
        raise ValueError("%s: metadata slot 0 is not valid; refusing" % super_path)
    for slot in valid:
        try:
            got = lp.partition_extents(super_path, "product", slot)
        except (KeyError, ValueError) as e:
            raise ValueError("%s: no usable `product` in metadata slot %d (%r); refusing" % (super_path, slot, e))
        if got != want:
            raise ValueError("%s: `product` is at %r (byte offset, length) in metadata slot %d, but these tools are "
                             "fixed to %r. A different layout needs the offsets in rescue.sh and frame-doctor.sh "
                             "worked out again; refusing" % (super_path, got, slot, want))
    return want


def missing(backup_files=(), key_files=()):
    """For the test scripts: one sentence saying which input is not there, or "" when all are.
    A test that gets a sentence prints it as a SKIP and exits 0: nothing can be tested without the
    user's own backup and the fetched keys, and nothing private is shipped to stand in for them."""
    folder = path("BACKUP_DIR")
    if backup_files and not folder:
        return "BACKUP_DIR is not set (unit.conf or PX110_BACKUP_DIR): no backup of the frame to test against"
    for name in backup_files:
        if not os.path.isfile(os.path.join(folder, name)):
            return "%s is not in BACKUP_DIR" % name
    for name in key_files:
        if not os.path.isfile(key(name)):
            return "key file %s is not in KEY_DIR (fetch-keys.sh gets it)" % name
    return ""


NAMES = ("SERIAL", "BACKUP_DIR", "KEY_DIR", "BUILD_DIR", "KIOSK_APK", "KIOSK_NAME", "KIOSK_PREVIOUS_APK",
         "E2FSPROGS_DIR", "CLANG", "ARM_LD", "ARM_STRIP", "ANDROID_BUILD_TOOLS", "JAVA_HOME", "ADB", "MTK_DIR",
         "LIBUSB_DIR", "GOOD_DIGEST")
PATHS = ("BACKUP_DIR", "KEY_DIR", "BUILD_DIR", "KIOSK_APK", "KIOSK_PREVIOUS_APK", "E2FSPROGS_DIR",
         "ANDROID_BUILD_TOOLS", "JAVA_HOME", "MTK_DIR", "LIBUSB_DIR")
DEFAULTS = {"KEY_DIR": "keys", "BUILD_DIR": "build"}


def value(name):
    return path(name, DEFAULTS.get(name, "")) if name in PATHS else get(name)


def main(argv):
    if len(argv) == 3 and argv[1] == "get" and argv[2] in NAMES:
        print(value(argv[2]))
        return 0
    if len(argv) == 2 and argv[1] == "show":
        print("settings file: %s%s" % (CONF, "" if os.path.isfile(CONF) else " (not there)"))
        for name in NAMES:
            print("%-20s %s" % (name, value(name) or "(not set)"))
        return 0
    if len(argv) == 2 and argv[1] == "check-backup":
        try:
            for name in sorted(STOCK_SHA256):
                check_stock(backup(name), name)
                print("ok   %-18s %s" % (name, STOCK_SHA256[name]))
            where = check_product_layout(backup("super.img"))
            with open(backup("super.img"), "rb") as f:
                f.seek(where[0][0])
                region = hashlib.sha256(f.read(where[0][1])).hexdigest()
            if region != STOCK_PRODUCT_SHA256:
                raise ValueError("the product region of super.img is not the stock one")
            print("ok   product in super   byte offset %d, %d bytes, sha256 %s" % (where[0][0], where[0][1], region))
        except (NotSet, ValueError) as e:
            print("STOP: %s" % e)
            return 1
        print("RESULT: the backup is stock %s and laid out as the tools expect." % FIRMWARE)
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
