#!/usr/bin/env python3
"""Back up and verify the PF1007L eMMC through the read-only U-Boot `ums` disk (macOS or Linux).

Usage (run from the repository root, with sudo):
  sudo python3 -I scripts/a33-uboot/emmc-macos.py backup diskN <exact-bytes>
  sudo python3 -I scripts/a33-uboot/emmc-macos.py verify diskN <exact-bytes>
  sudo python3 -I scripts/a33-uboot/emmc-macos.py verify-original diskN <exact-bytes>
  sudo python3 -I scripts/a33-uboot/emmc-macos.py backup-resume diskN <exact-bytes>
  sudo python3 -I scripts/a33-uboot/emmc-macos.py verify-resume diskN <exact-bytes>
  sudo python3 -I scripts/a33-uboot/emmc-macos.py verify-original-resume diskN <exact-bytes>
  sudo python3 -I scripts/a33-uboot/emmc-macos.py verify-data diskN <exact-bytes>

<exact-bytes> is the eMMC size from `diskutil info diskN` (Disk Size, in bytes); on Linux
pass the whole disk (e.g. sdb) and its size from `lsblk -b`. It
guards against a disk number that changed after a replug. Both modes refuse a disk
that macOS reports as writable: only the read-only U-Boot build should be running.

backup  reads the whole disk to backups/a33-emmc-full.img, re-reads it independently,
        rejects 0xCC filler, gzips it and verifies the gzip readback.
verify  after the boot write: every byte must equal that backup, except the ranges in
        diagnostics/a33-boot-patch/plan.json, which must equal the patched payloads.
verify-original
        after restore-boot: every byte must equal the backup.
backup-resume, verify-resume, verify-original-resume
        the same checks in 1 GiB segments, with progress saved after each segment. Use these
        when the frame drops off USB partway (seen through bus-powered hubs): power-cycle the
        frame into FEL, load U-Boot again, and rerun the same command to continue. Each backup
        segment is read twice from the disk and once back from the image file, and all three
        must match. On resume, the disk must have the same fingerprint (first 4 MiB plus the
        start of the first partition, which is unique per unit) as when the run started.
        On Linux the page cache is dropped around every read, so re-reads come from the eMMC.
        verify-resume refuses to continue a saved run made with a different plan.json.
verify-data
        before or after write-data / restore-data: reads only the ranges in
        diagnostics/a33-data-patch/plan.json (from data-patch-prepare.py) and reports whether
        each holds the new bytes, the original bytes, or neither. It passes only when every
        range holds the new bytes, or every range holds the original bytes.
"""

import gzip
import hashlib
import json
import os
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKUPS = REPO / "backups"
IMAGE = BACKUPS / "a33-emmc-full.img"
PARTIAL = BACKUPS / "a33-emmc-full.img.partial"
GZIP_PATH = BACKUPS / "a33-emmc-full.img.gz"
PLAN = REPO / "diagnostics/a33-boot-patch/plan.json"
DATA_PLAN = REPO / "diagnostics/a33-data-patch/plan.json"
SECTOR = 512
CHUNK = 4 * 1024 * 1024
FILLER_RUN = 4096
SEGMENT = 1024 * 1024 * 1024
STATE = BACKUPS / "a33-emmc-resume.json"
VERIFY_STATE = BACKUPS / "a33-emmc-verify-resume.json"
ORIGINAL_VERIFY_STATE = BACKUPS / "a33-emmc-verify-original-resume.json"


def fail(message):
    sys.exit(f"STOP: {message}")


def open_disk_linux(identifier, expected_size):
    if not re.fullmatch(r"sd[a-z]+", identifier):
        fail("pass a whole disk like sdb, not a partition")
    sys_block = Path("/sys/block") / identifier
    model = (sys_block / "device/model").read_text().strip()
    if not re.fullmatch(r"UMS disk \d+", model):
        fail(f"unexpected model {model!r}; expected U-Boot's 'UMS disk N'")
    size = int((sys_block / "size").read_text()) * SECTOR
    if size != expected_size:
        fail(f"size {size} != expected {expected_size}")
    if "/usb" not in str(sys_block.resolve()):
        fail("not a USB disk")
    if (sys_block / "ro").read_text().strip() != "1":
        fail("disk is writable; the read-only U-Boot build is not the one running")
    if re.search(rf"^/dev/{identifier}\d* ", Path("/proc/mounts").read_text(), re.M):
        fail(f"unmount every partition of {identifier} first")
    return f"/dev/{identifier}"


def open_disk(identifier, expected_size):
    if sys.platform == "linux":
        return open_disk_linux(identifier, expected_size)
    if not re.fullmatch(r"disk\d+", identifier):
        fail("pass a whole disk like disk4, not a partition")
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", identifier]))
    if not re.fullmatch(r"UMS disk \d+", info.get("MediaName", "")):
        fail(f"unexpected media name {info.get('MediaName')!r}; expected U-Boot's 'UMS disk N'")
    if info.get("TotalSize") != expected_size:
        fail(f"size {info.get('TotalSize')} != expected {expected_size}")
    if info.get("Internal", True) or info.get("BusProtocol") != "USB":
        fail("not an external USB disk")
    if info.get("WritableMedia", True):
        fail("disk is writable; the read-only U-Boot build is not the one running")
    subprocess.check_call(["diskutil", "unmountDisk", identifier])
    return f"/dev/r{identifier}"


def drop_cache(fd, start=0, length=0):
    """Linux keeps block-device reads in the page cache. Drop them so a second pass really
    re-reads the eMMC instead of memory. macOS uses the uncached /dev/rdiskN instead."""
    if sys.platform == "linux":
        os.posix_fadvise(fd, start, length, os.POSIX_FADV_DONTNEED)


def chunks(path, total, label, start=0):
    done, started = 0, time.time()
    with open(path, "rb", buffering=0) as source:
        drop_cache(source.fileno())
        source.seek(start)
        while done < total:
            block = source.read(min(CHUNK, total - done))
            if not block:
                fail(f"short read at byte {done}")
            drop_cache(source.fileno(), start + done, len(block))
            yield start + done, block
            done += len(block)
            rate = done / max(time.time() - started, 0.001) / 1e6
            print(f"\r  {label}: {done * 100 // total:3d}%  {rate:5.1f} MB/s", end="", flush=True)
    print()


def backup(raw_path, size):
    for path in (PARTIAL, IMAGE, GZIP_PATH):
        if path.exists():
            fail(f"{path.name} already exists; refusing to overwrite")
    BACKUPS.mkdir(exist_ok=True)
    os.umask(0o077)

    first, filler = hashlib.sha256(), 0
    with open(PARTIAL, "xb") as out:
        for _, block in chunks(raw_path, size, "pass 1 (copy)"):
            first.update(block)
            out.write(block)
            filler += block.count(b"\xcc" * FILLER_RUN)
    print(f"  pass 1 SHA-256: {first.hexdigest()}  (0xCC runs: {filler})")
    if filler:
        fail("0xCC filler found; this may not be real flash data")

    second = hashlib.sha256()
    for _, block in chunks(raw_path, size, "pass 2 (re-read)"):
        second.update(block)
    if second.hexdigest() != first.hexdigest():
        fail("independent re-read differs")

    stored = hashlib.sha256()
    for _, block in chunks(PARTIAL, size, "image file"):
        stored.update(block)
    if stored.hexdigest() != first.hexdigest():
        fail("image file differs from the disk")

    print("  compressing...")
    with open(PARTIAL, "rb") as source, gzip.open(GZIP_PATH, "xb", compresslevel=6) as target:
        shutil.copyfileobj(source, target, CHUNK)
    readback = hashlib.sha256()
    with gzip.open(GZIP_PATH, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            readback.update(block)
    if readback.hexdigest() != first.hexdigest():
        fail("gzip readback differs")

    PARTIAL.rename(IMAGE)
    (BACKUPS / "a33-emmc-full.sha256").write_text(f"{first.hexdigest()}  {IMAGE.name}\n")
    print(f"Verified full eMMC backup: {IMAGE} ({size} bytes), SHA-256 {first.hexdigest()}")


def verify_original(raw_path, size):
    verify(raw_path, size, patched=False)


def verify(raw_path, size, patched=True):
    plan = json.loads(PLAN.read_text()) if patched else {"writes": []}
    patches = []
    for write in plan["writes"]:
        data = (PLAN.parent / write["file"]).read_bytes()
        if len(data) != write["sectors"] * SECTOR:
            fail(f"{write['file']} has the wrong size")
        patches.append((write["sector"] * SECTOR, data))
    if IMAGE.stat().st_size != size:
        fail("backup image size differs from the disk")

    mismatches = []
    with open(IMAGE, "rb") as backup_file:
        for offset, got in chunks(raw_path, size, "verify"):
            want = bytearray(backup_file.read(len(got)))
            for start, data in patches:
                lo, hi = max(start, offset), min(start + len(data), offset + len(got))
                if lo < hi:
                    want[lo - offset:hi - offset] = data[lo - start:hi - start]
            if got != want:
                mismatches.append(offset)
                if len(mismatches) > 10:
                    break
    if mismatches:
        fail(f"mismatch in 4 MiB chunks at byte offsets {mismatches}")
    if patched:
        print("Verified: the eMMC equals the backup plus exactly the planned boot patch.")
    else:
        print("Verified: the eMMC equals the original backup.")


def segments(size):
    return [(i, i * SEGMENT, min(SEGMENT, size - i * SEGMENT)) for i in range((size + SEGMENT - 1) // SEGMENT)]


def load_state(path, size, kind):
    if not path.exists():
        return {"kind": kind, "size": size, "done": {}}
    state = json.loads(path.read_text())
    if state.get("kind") != kind or state.get("size") != size:
        fail(f"{path.name} is for a different disk size or mode")
    return state


def save_state(path, state):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    os.replace(tmp, path)


def fingerprint(raw_path):
    """SHA-256 of the first 4 MiB plus 64 KiB at the start of the first MBR partition.

    The first 4 MiB (MBR, boot0) is the same on every unit with the same firmware. The first
    partition is UDISK (/data); its ext4 superblock holds a filesystem UUID that differs per
    unit, so the fingerprint tells two frames apart. Booting Android between runs changes the
    superblock, so the fingerprint then no longer matches and the run must start over.
    """
    with open(raw_path, "rb", buffering=0) as disk:
        drop_cache(disk.fileno())
        head = disk.read(CHUNK)
        if len(head) != CHUNK or head[510:512] != b"\x55\xaa":
            fail("no MBR at the start of the disk")
        first = struct.unpack_from("<I", head, 446 + 8)[0]
        if not head[446 + 4] or not first:
            fail("the first MBR partition is empty")
        disk.seek(first * SECTOR)
        part = disk.read(64 * 1024)
    return hashlib.sha256(head + part).hexdigest()


def backup_hash():
    path = BACKUPS / "a33-emmc-full.sha256"
    if not path.exists():
        fail(f"{path.name} is missing; verify needs the finished backup")
    return path.read_text().split()[0]


def run_segments(state_path, state, size, work, label):
    todo = [seg for seg in segments(size) if str(seg[0]) not in state["done"]]
    print(f"  {len(segments(size)) - len(todo)} of {len(segments(size))} segments already done")
    for index, start, length in todo:
        try:
            state["done"][str(index)] = work(index, start, length)
        except OSError as error:
            save_state(state_path, state)
            fail(f"{error} during segment {index} ({label}). Progress is saved. Power-cycle the frame "
                 f"into FEL, load U-Boot again, then rerun the same command to continue.")
        save_state(state_path, state)


def backup_resume(raw_path, size):
    for path in (IMAGE, GZIP_PATH):
        if path.exists():
            fail(f"{path.name} already exists; refusing to overwrite")
    BACKUPS.mkdir(exist_ok=True)
    os.umask(0o077)
    disk_id = fingerprint(raw_path)
    if STATE.exists():
        state = load_state(STATE, size, "backup")
        if not PARTIAL.exists():
            fail(f"{STATE.name} exists but {PARTIAL.name} is missing")
        if state.get("fingerprint") != disk_id:
            fail("this disk is not the one the saved run started on (different frame, or Android "
                 f"booted in between). Move {STATE.name} and {PARTIAL.name} aside to start over.")
    elif PARTIAL.exists():
        fail(f"{PARTIAL.name} exists without resume state (left by a plain backup?); remove it first")
    else:
        state = {"kind": "backup", "size": size, "done": {}, "fingerprint": disk_id}
        with open(PARTIAL, "xb") as out:
            out.truncate(size)
        save_state(STATE, state)

    def work(index, start, length):
        name = f"segment {index + 1}/{len(segments(size))}"
        first, filler = hashlib.sha256(), 0
        with open(PARTIAL, "r+b") as out:
            out.seek(start)
            for _, block in chunks(raw_path, length, f"{name} pass 1", start):
                first.update(block)
                out.write(block)
                filler += block.count(b"\xcc" * FILLER_RUN)
            out.flush()
            os.fsync(out.fileno())
        if filler:
            fail(f"0xCC filler found in {name}; this may not be real flash data")
        second = hashlib.sha256()
        for _, block in chunks(raw_path, length, f"{name} pass 2", start):
            second.update(block)
        stored = hashlib.sha256()
        for _, block in chunks(PARTIAL, length, f"{name} image file", start):
            stored.update(block)
        if not first.hexdigest() == second.hexdigest() == stored.hexdigest():
            state["done"].pop(str(index), None)
            fail(f"{name}: disk passes or image file differ; not marked done")
        return first.hexdigest()

    run_segments(STATE, state, size, work, "backup")

    whole = hashlib.sha256()
    for index, start, length in segments(size):
        part = hashlib.sha256()
        for _, block in chunks(PARTIAL, length, f"image file segment {index + 1}", start):
            part.update(block)
            whole.update(block)
        if part.hexdigest() != state["done"].get(str(index)):
            fail(f"image file segment {index + 1} differs from the hash saved when it was read")
    print("  compressing...")
    with open(PARTIAL, "rb") as source, gzip.open(GZIP_PATH, "xb", compresslevel=6) as target:
        shutil.copyfileobj(source, target, CHUNK)
    readback = hashlib.sha256()
    with gzip.open(GZIP_PATH, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            readback.update(block)
    if readback.hexdigest() != whole.hexdigest():
        fail("gzip readback differs")
    PARTIAL.rename(IMAGE)
    (BACKUPS / "a33-emmc-full.sha256").write_text(f"{whole.hexdigest()}  {IMAGE.name}\n")
    STATE.rename(STATE.with_suffix(".done.json"))
    print(f"Verified full eMMC backup: {IMAGE} ({size} bytes), SHA-256 {whole.hexdigest()}")
    print(f"  {len(segments(size))} segments, each read twice from the disk and once from the file.")


def verify_resume(raw_path, size, patched=True):
    plan = json.loads(PLAN.read_text()) if patched else {"writes": [], "crc32": None}
    state_path, kind = (VERIFY_STATE, "verify") if patched else (ORIGINAL_VERIFY_STATE, "verify-original")
    patches = []
    for write in plan["writes"]:
        data = (PLAN.parent / write["file"]).read_bytes()
        if len(data) != write["sectors"] * SECTOR:
            fail(f"{write['file']} has the wrong size")
        patches.append((write["sector"] * SECTOR, data))
    if IMAGE.stat().st_size != size:
        fail("backup image size differs from the disk")
    state = load_state(state_path, size, kind)
    if state.setdefault("plan", plan["crc32"]) != plan["crc32"]:
        fail(f"{state_path.name} was saved with a different plan.json; move it aside to start over")
    if state.setdefault("backup", backup_hash()) != backup_hash():
        fail(f"{state_path.name} was saved against a different backup; move it aside to start over")

    def work(index, start, length):
        with open(IMAGE, "rb") as backup_file:
            backup_file.seek(start)
            for offset, got in chunks(raw_path, length, f"verify segment {index + 1}/{len(segments(size))}", start):
                want = bytearray(backup_file.read(len(got)))
                for pstart, data in patches:
                    lo, hi = max(pstart, offset), min(pstart + len(data), offset + len(got))
                    if lo < hi:
                        want[lo - offset:hi - offset] = data[lo - pstart:hi - pstart]
                if got != want:
                    fail(f"mismatch in the 4 MiB chunk at byte offset {offset}")
        return "ok"

    run_segments(state_path, state, size, work, kind)
    state_path.rename(state_path.with_suffix(".done.json"))
    if patched:
        print("Verified: the eMMC equals the backup plus exactly the planned boot patch.")
    else:
        print("Verified: the eMMC equals the original backup.")


def verify_original_resume(raw_path, size):
    verify_resume(raw_path, size, patched=False)


def verify_data(raw_path, size, plan_path=DATA_PLAN):
    """Read-only check of a data-patch-prepare.py plan: each range must hold its new or its
    original bytes, and all ranges must agree. Only the planned sectors are read."""
    plan = json.loads(plan_path.read_text())
    states = []
    with open(raw_path, "rb", buffering=0) as disk:
        for write in plan["writes"]:
            name = f"range {write['range']}"
            payloads = {}
            for kind in ("new", "orig"):
                data = (plan_path.parent / write[f"{kind}_file"]).read_bytes()
                if len(data) != write["length"] or hashlib.sha256(data).hexdigest() != write[f"{kind}_sha256"]:
                    fail(f"{write[f'{kind}_file']} does not match plan.json")
                payloads[kind] = data
            start = write["sector"] * SECTOR
            if write["length"] <= 0 or write["length"] != write["sectors"] * SECTOR:
                fail(f"{name} is not a whole number of sectors in plan.json")
            if start != plan["partition_start_sector"] * SECTOR + write["partition_relative_byte"]:
                fail(f"{name}'s sector does not match its partition offset in plan.json")
            if start + write["length"] > size:
                fail(f"{name} is past the end of the disk")
            drop_cache(disk.fileno(), start, write["length"])
            disk.seek(start)
            got = disk.read(write["length"])
            state = "new" if got == payloads["new"] else "original" if got == payloads["orig"] else "UNEXPECTED"
            states.append(state)
            print(f"  {name} (sector {write['sector']}, {write['length']} bytes): {state}")
    if not states:
        fail("plan.json has no ranges")
    if set(states) == {"new"}:
        print(f"Verified: all {len(states)} range(s) hold the new bytes.")
    elif set(states) == {"original"}:
        print(f"Verified: all {len(states)} range(s) hold the original bytes; nothing of this plan is written.")
    else:
        fail("the ranges are mixed or unexpected; don't boot Android. restore-data.scr puts back "
             "ranges that hold the new bytes, and writes nothing if any range is UNEXPECTED")


ACTIONS = {"backup": backup, "verify": verify, "verify-original": verify_original,
           "backup-resume": backup_resume, "verify-resume": verify_resume,
           "verify-original-resume": verify_original_resume, "verify-data": verify_data}


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ACTIONS:
        sys.exit(__doc__)
    if os.geteuid() != 0:
        fail("run with sudo")
    action, identifier, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
    raw_path = open_disk(identifier, size)
    ACTIONS[action](raw_path, size)


if __name__ == "__main__":
    main()
