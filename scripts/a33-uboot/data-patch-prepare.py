#!/usr/bin/env python3
"""Build a guarded userdata patch from YOUR OWN verified backup, the same way
boot-patch.py builds a boot patch: a generated U-Boot script that writes only
after every payload's CRC-32 matches and the eMMC still holds your recorded
original bytes. Uses this repo's existing READ-ONLY U-Boot build
(build-uboot.sh) — it never exposes the eMMC as a writable host disk.

Usage (from the repository root):
  python3 -I scripts/a33-uboot/data-patch-prepare.py [--nulldev] \
      <orig-data-partition.img> <edited-data-partition.img> <data-partition-start-sector>

The two images are copies of the SAME /data partition extracted from your own
verified eMMC backup: one untouched, one with your intended edit (made with
e.g. `debugfs -w` on the edited copy only, never on the backup itself).
<data-partition-start-sector> is that partition's start sector within the full
eMMC, from your own parsed partition table. The full backup and an edited clone
of it, with start sector 0, give the same plan without extracting /data.

--nulldev runs both generated scripts only after `setenv stdin nulldev`
succeeds, as the null-console U-Boot builds' ums-readonly.cmd does, so floating
serial input can't look like Ctrl-C and stop a script partway. If that command
fails, nothing in the script runs. Use it only with a U-Boot built with
CONFIG_SYS_DEVICE_NULLDEV=y; on other builds the guard stops every run.

This only reads the two local images and writes payloads + guarded scripts to
diagnostics/a33-data-patch/. Nothing here touches a device. Re-derive your own
plan from your own backup and partition table; a plan built from one unit's
diff (offsets, byte counts, CRCs) is not reusable on a different unit.

Writes diagnostics/a33-data-patch/:
  range-NN.orig, range-NN.new        each changed byte range, before and after
  plan.json                          sectors, sizes and CRC-32s
  write-data.cmd / write-data.scr    guarded U-Boot write script
  restore-data.cmd / restore-data.scr  guarded undo: writes the original bytes back
"""
import hashlib
import json
import struct
import sys
import time
import zlib
from pathlib import Path

SECTOR = 512
# Fine-grained scan granularity once a coarse (1 MiB) pass has found a hit.
COARSE = 1024 * 1024
FINE = SECTOR

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "diagnostics/a33-data-patch"

# RAM load addresses for this script's own payloads. U-Boot itself runs from
# 0x4A000000; boot-patch.py's own payloads use 0x50000000-0x55FFFFFF. Each
# range gets three buffers (orig, new, a scratch read-back buffer), spaced
# 64 KiB apart — generous for payloads this small, and clear of both ranges
# above. Refuse a plan that would exceed the reserved 16 MiB buffer window.
BASE_ADDR = 0x58000000
SLOT = 0x10000
BUFFER_END = 0x59000000

def with_nulldev(script):
    """--nulldev: the whole script sits in the `then` branch of `setenv stdin nulldev`, the
    same shape as the null-console ums-readonly.cmd, so nothing in it can run if that fails."""
    return ("# Ignore floating serial input (it can look like Ctrl-C); the script runs only if that works.\n"
            "if setenv stdin nulldev; then\n"
            + script
            + "else\n"
            "  echo STOP: could not disable serial input, nothing written\n"
            "  while true; do sleep 1; done\n"
            "fi\n")


def fail(message):
    sys.exit(f"STOP: {message}")


def coarse_diff_regions(orig_path, edited_path, size):
    regions = []
    with open(orig_path, "rb") as fo, open(edited_path, "rb") as fe:
        off = 0
        while off < size:
            chunk = min(COARSE, size - off)
            bo = fo.read(chunk)
            be = fe.read(chunk)
            if bo != be:
                regions.append((off, chunk))
            off += chunk
    return regions


def fine_ranges(orig_path, edited_path, regions):
    ranges = []
    with open(orig_path, "rb") as fo, open(edited_path, "rb") as fe:
        for base, length in regions:
            fo.seek(base)
            fe.seek(base)
            off = base
            end = base + length
            cur_start = None
            while off < end:
                bo = fo.read(FINE)
                be = fe.read(FINE)
                if bo != be:
                    if cur_start is None:
                        cur_start = off
                    cur_end = off + FINE
                else:
                    if cur_start is not None:
                        ranges.append((cur_start, cur_end))
                        cur_start = None
                off += FINE
            if cur_start is not None:
                ranges.append((cur_start, cur_end))
    return ranges


def _read(w):
    return f"mmc read {w['read_addr']:#x} {w['sector']:#x} {w['sectors']:#x}"


def _payload_checks(w):
    return (f"crc32 -v {w['orig_addr']:#x} {w['length']:#x} {w['orig_crc32']} && "
            f"crc32 -v {w['new_addr']:#x} {w['length']:#x} {w['new_crc32']}")


def _compare(w, kind):
    return f"cmp.b {w[f'{kind}_addr']:#x} {w['read_addr']:#x} {w['length']:#x}"


def _write_checked(w, kind):
    return (f"mmc write {w[f'{kind}_addr']:#x} {w['sector']:#x} {w['sectors']:#x} && "
            f"{_read(w)} && {_compare(w, kind)}")


def _script(writes, title, expect, write, restore=False):
    """Nest every continuation inside successful checks, without mutable environment flags.

    All ranges pass phase 1 before any write. Phase 2 rechecks both payloads and makes a fresh
    read before each write. An already-original restore range is skipped, but an unknown range
    or any command failure prevents every later write. Even if read-only ums returns, there is
    no remaining write command outside the successful conditional branches.
    """
    if not writes:
        raise ValueError("cannot generate a write script with no ranges")
    lines = [f"# {title}. Load every orig/new payload with sunxi-fel first.",
             "# Phase 1 checks all ranges; phase 2 rechecks each before writing and verifying it."]
    closers = []

    def guard(command, message):
        pad = "  " * len(closers)
        lines.append(f"{pad}if {command}; then")
        closers.append((pad, message))

    guard("mmc dev 1", "could not select eMMC, nothing written")
    for w in writes:
        guard(f"{_read(w)} && {_payload_checks(w)}", f"range {w['range']} read or payload check failed, nothing written")
        acceptable = _compare(w, expect)
        if restore:
            acceptable += f" || {_compare(w, 'orig')}"
        guard(acceptable, f"range {w['range']} has unexpected bytes, nothing written")
    for w in writes:
        guard(f"{_read(w)} && {_payload_checks(w)}", f"range {w['range']} fresh read or payload check failed, no further writes")
        if restore:
            # A compound if has the status of its last executed command (U-Boot hush).
            # Both branches must succeed before the next range is reachable; no go/all_ok flag.
            pad = "  " * len(closers)
            lines += [f"{pad}if", f"{pad}  if {_compare(w, 'orig')}; then",
                      f"{pad}    true", f"{pad}  else",
                      f"{pad}    {_compare(w, 'new')} && {_write_checked(w, 'orig')}",
                      f"{pad}  fi", f"{pad}then"]
            closers.append((pad, f"range {w['range']} restore failed, no further writes"))
        else:
            guard(f"{_compare(w, expect)} && {_write_checked(w, write)}",
                  f"range {w['range']} check or write/readback failed, no further writes")
    lines.append("  " * len(closers) + "echo all ranges verified")
    for pad, message in reversed(closers):
        lines += [f"{pad}else", f"{pad}  echo STOP: {message}", f"{pad}fi"]
    lines.append("ums 0 mmc 1")
    return "\n".join(lines) + "\n"


def restore_script(writes):
    """Undo a complete or partial write, leaving already-original ranges untouched."""
    return _script(writes, "Undo the userdata patch", "new", "orig", restore=True)


def script_image(text):
    """Legacy U-Boot script image, as `mkimage -A arm -T script -C none` makes it."""
    body = struct.pack(">II", len(text), 0) + text
    header = bytearray(struct.pack(">IIIIIIIBBBB32s", 0x27051956, 0, int(time.time()), len(body),
                                   0, 0, zlib.crc32(body), 5, 2, 6, 0, b""))
    struct.pack_into(">I", header, 4, zlib.crc32(header))
    return bytes(header) + body


def guarded_script(writes, title, expect, write):
    """Check all original ranges first, then write and verify in a fail-closed chain."""
    return _script(writes, title, expect, write)


def main():
    args = sys.argv[1:]
    nulldev = "--nulldev" in args
    if nulldev:
        args.remove("--nulldev")
    if len(args) != 3:
        sys.exit(__doc__)
    orig_path = Path(args[0]).resolve(strict=True)
    edited_path = Path(args[1]).resolve(strict=True)
    partition_start_sector = int(args[2])
    if partition_start_sector < 0:
        fail("partition start sector must be nonnegative")
    partition_start_byte = partition_start_sector * SECTOR

    size = orig_path.stat().st_size
    if size == 0 or size % SECTOR:
        fail("images must have a positive, whole-sector size")
    if edited_path.stat().st_size != size:
        fail("orig and edited images are different sizes")

    print("Coarse (1 MiB) scan...")
    regions = coarse_diff_regions(orig_path, edited_path, size)
    print(f"  {len(regions)} coarse region(s) differ")

    print("Fine (sector) scan of those regions...")
    ranges = fine_ranges(orig_path, edited_path, regions)
    print(f"  {len(ranges)} byte range(s) differ, {sum(e - s for s, e in ranges)} bytes total")

    if not ranges:
        fail("images contain no changed sectors")
    if BASE_ADDR + len(ranges) * 3 * SLOT > BUFFER_END:
        fail("changed ranges exceed the reserved RAM buffer window")
    if any(e - s > SLOT for s, e in ranges):
        fail(f"a changed range exceeds the {SLOT}-byte RAM slot")
    if OUT.exists():
        fail(f"{OUT} already exists; remove it first to re-prepare")
    OUT.mkdir(parents=True)

    writes = []
    with open(orig_path, "rb") as fo, open(edited_path, "rb") as fe:
        for i, (s, e) in enumerate(ranges):
            fo.seek(s)
            fe.seek(s)
            orig_bytes = fo.read(e - s)
            new_bytes = fe.read(e - s)
            assert orig_bytes != new_bytes
            orig_file = f"range-{i:02d}.orig"
            new_file = f"range-{i:02d}.new"
            (OUT / orig_file).write_bytes(orig_bytes)
            (OUT / new_file).write_bytes(new_bytes)
            abs_byte = partition_start_byte + s
            if abs_byte % SECTOR:
                fail(f"range {i} is not sector-aligned")
            if e - s > SLOT:
                fail(f"range {i} is {e - s} bytes; this script's RAM slots hold at most {SLOT} bytes per range")
            base = BASE_ADDR + i * 3 * SLOT
            writes.append({
                "range": i,
                "partition_relative_byte": s,
                "sector": abs_byte // SECTOR,
                "sectors": (e - s) // SECTOR,
                "length": e - s,
                "orig_file": orig_file,
                "new_file": new_file,
                "orig_sha256": hashlib.sha256(orig_bytes).hexdigest(),
                "new_sha256": hashlib.sha256(new_bytes).hexdigest(),
                "orig_crc32": f"{zlib.crc32(orig_bytes):08x}",
                "new_crc32": f"{zlib.crc32(new_bytes):08x}",
                "orig_addr": base,
                "new_addr": base + SLOT,
                "read_addr": base + 2 * SLOT,
            })

    plan = {
        "partition_start_sector": partition_start_sector,
        "source_orig_image": str(orig_path),
        "source_edited_image": str(edited_path),
        "nulldev": nulldev,
        "writes": writes,
    }
    (OUT / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")

    for name, script in (
        ("write-data", guarded_script(writes, "Userdata patch", "orig", "new")),
        ("restore-data", restore_script(writes)),
    ):
        if nulldev:
            script = with_nulldev(script)
        (OUT / f"{name}.cmd").write_text(script)
        (OUT / f"{name}.scr").write_bytes(script_image(script.encode()))

    print(f"\nWrote plan and guarded scripts for {len(writes)} range(s) to {OUT}")
    for w in writes:
        print(f"  range {w['range']}: sector {w['sector']}, {w['sectors']} sector(s), "
              f"{w['length']} bytes, RAM {w['orig_addr']:#x}/{w['new_addr']:#x}/{w['read_addr']:#x}")
    print("\nLoad every orig/new payload with sunxi-fel, then run write-data.scr the same way")
    print("this repo's existing write-boot.scr is run: against the READ-ONLY U-Boot build,")
    print("over FEL. It checks every range first and writes nothing unless all of them hold")
    print("the original bytes; then it writes them in order and stops at the first write that")
    print("does not read back correctly. Undo the same way with restore-data.scr.")
    print("Before and after, check the ranges over the read-only UMS disk with")
    print("`emmc-macos.py verify-data diskN <exact-bytes>`.")


if __name__ == "__main__":
    main()
