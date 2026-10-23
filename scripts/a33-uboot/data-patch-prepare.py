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
# above regardless of how many ranges a given plan has.
BASE_ADDR = 0x58000000
SLOT = 0x10000

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


def restore_script(writes):
    """Undo, including after a write that stopped partway. Phase 1: every range must hold
    either the new bytes or the original bytes (and both payload CRC-32s must match);
    anything else means the eMMC is not in a state this plan made, so nothing is written.
    Phase 2: ranges that already hold the original bytes are left alone; the others get the
    original bytes back, each read back and compared, stopping at the first failure."""
    lines = ["# Undo the userdata patch. Load each range's orig/new payload with sunxi-fel first.",
             "# Phase 1: every range must hold the new or the original bytes, or nothing is written.",
             "# Phase 2: ranges holding the new bytes get the original bytes back.",
             "mmc dev 1",
             "setenv all_ok 1"]
    for w in writes:
        lines.append(f"mmc read {w['read_addr']:#x} {w['sector']:#x} {w['sectors']:#x}")
        lines.append(f"if crc32 -v {w['orig_addr']:#x} {w['length']:#x} {w['orig_crc32']} && "
                     f"crc32 -v {w['new_addr']:#x} {w['length']:#x} {w['new_crc32']}; then")
        lines.append(f"  if cmp.b {w['new_addr']:#x} {w['read_addr']:#x} {w['length']:#x}; then echo range {w['range']} holds the new bytes")
        lines.append(f"  elif cmp.b {w['orig_addr']:#x} {w['read_addr']:#x} {w['length']:#x}; then echo range {w['range']} is already original")
        lines.append(f"  else echo range {w['range']} holds unexpected bytes; setenv all_ok 0; fi")
        lines.append(f"else echo range {w['range']} payload CRC FAILED; setenv all_ok 0; fi")
    lines.append('if test "${all_ok}" = 1; then')
    lines.append("  setenv go 1")
    for w in writes:
        lines.append('  if test "${go}" = 1; then')
        lines.append(f"    mmc read {w['read_addr']:#x} {w['sector']:#x} {w['sectors']:#x}")
        lines.append(f"    if cmp.b {w['new_addr']:#x} {w['read_addr']:#x} {w['length']:#x}; then")
        lines.append(f"      if mmc write {w['orig_addr']:#x} {w['sector']:#x} {w['sectors']:#x} && "
                     f"mmc read {w['read_addr']:#x} {w['sector']:#x} {w['sectors']:#x} && "
                     f"cmp.b {w['orig_addr']:#x} {w['read_addr']:#x} {w['length']:#x}; then")
        lines.append(f"        echo range {w['range']} restored")
        lines.append(f"      else echo range {w['range']} restore FAILED; setenv go 0; fi")
        lines.append("    fi")
        lines.append("  fi")
    lines.append("fi")
    lines.append('if test "${all_ok}" != 1; then echo nothing written: the eMMC is not in a state this plan made; fi')
    lines.append("ums 0 mmc 1")
    return "\n".join(lines) + "\n"


def script_image(text):
    """Legacy U-Boot script image, as `mkimage -A arm -T script -C none` makes it."""
    body = struct.pack(">II", len(text), 0) + text
    header = bytearray(struct.pack(">IIIIIIIBBBB32s", 0x27051956, 0, int(time.time()), len(body),
                                   0, 0, zlib.crc32(body), 5, 2, 6, 0, b""))
    struct.pack_into(">I", header, 4, zlib.crc32(header))
    return bytes(header) + body


def guarded_script(writes, title, expect, write):
    """Two phases. First every range is checked (both CRC-32s, and the eMMC must hold the
    `expect` bytes); if any check fails, nothing is written, so the filesystem is never left
    half-edited by a range that was already wrong. Then a nested, fail-stop chain: range i's
    write only runs if its checks pass again, and range i+1 only runs if range i's write
    happened and read back correctly."""
    lines = [f"# {title}. Load each range's orig/new payload with sunxi-fel first.",
             f"# Phase 1 checks every range; nothing is written unless all hold the {expect} bytes.",
             "# Phase 2 writes the ranges in order and stops at the first check or write that fails.",
             "mmc dev 1",
             "setenv all_ok 1"]
    for w in writes:
        lines.append(f"mmc read {w['read_addr']:#x} {w['sector']:#x} {w['sectors']:#x}")
        lines.append(f"if crc32 -v {w['orig_addr']:#x} {w['length']:#x} {w['orig_crc32']} && "
                     f"crc32 -v {w['new_addr']:#x} {w['length']:#x} {w['new_crc32']} && "
                     f"cmp.b {w[f'{expect}_addr']:#x} {w['read_addr']:#x} {w['length']:#x}; then")
        lines.append(f"  echo range {w['range']} checked")
        lines.append("else")
        lines.append(f"  echo range {w['range']} FAILED its check; setenv all_ok 0")
        lines.append("fi")
    lines.append('if test "${all_ok}" = 1; then')
    closers = ["fi"]
    for w in writes:
        pad = "  " * len(closers)
        lines.append(f"{pad}mmc read {w['read_addr']:#x} {w['sector']:#x} {w['sectors']:#x}")
        checks = (f"crc32 -v {w['orig_addr']:#x} {w['length']:#x} {w['orig_crc32']} && "
                  f"crc32 -v {w['new_addr']:#x} {w['length']:#x} {w['new_crc32']} && "
                  f"cmp.b {w[f'{expect}_addr']:#x} {w['read_addr']:#x} {w['length']:#x}")
        lines.append(f"{pad}if {checks}; then")
        closers.append(f"{pad}fi")
        pad2 = pad + "  "
        write_check = (f"mmc write {w[f'{write}_addr']:#x} {w['sector']:#x} {w['sectors']:#x} && "
                       f"mmc read {w['read_addr']:#x} {w['sector']:#x} {w['sectors']:#x} && "
                       f"cmp.b {w[f'{write}_addr']:#x} {w['read_addr']:#x} {w['length']:#x}")
        lines.append(f"{pad2}if {write_check}; then")
        closers.append(f"{pad2}fi")
    # The innermost `if` needs a body: an empty then/fi is invalid in U-Boot's hush shell.
    lines.append(f"{pad2}  echo all ranges written")
    lines += reversed(closers)
    lines.append('if test "${all_ok}" != 1; then echo nothing written: a range did not hold the expected bytes; fi')
    lines.append("ums 0 mmc 1")
    return "\n".join(lines) + "\n"


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
    partition_start_byte = partition_start_sector * SECTOR

    size = orig_path.stat().st_size
    if edited_path.stat().st_size != size:
        fail("orig and edited images are different sizes")

    print("Coarse (1 MiB) scan...")
    regions = coarse_diff_regions(orig_path, edited_path, size)
    print(f"  {len(regions)} coarse region(s) differ")

    print("Fine (sector) scan of those regions...")
    ranges = fine_ranges(orig_path, edited_path, regions)
    print(f"  {len(ranges)} byte range(s) differ, {sum(e - s for s, e in ranges)} bytes total")

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
