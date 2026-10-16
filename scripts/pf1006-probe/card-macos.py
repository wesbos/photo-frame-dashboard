#!/usr/bin/env python3
"""Prepare an SD card for the experimental PF1006 probe.

The default action shows a plan. Select the disk and its exact size.
Preparation erases the card. Removal restores the boot area after format.
It cannot recover erased files. Build checks do not prove frame compatibility.
Use Python 3.9 or later on macOS.
"""

import argparse
import fcntl
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PIN = "e50b1e8715011def8aff1588081a2649a2c6cd47"
NAMES = {
    "u-boot-sunxi-with-spl.bin", "pf1006-probe.cmd", "pf1006-probe.scr",
    "run-id.txt", "pf1006.config", "u-boot.config", "pf1006-readonly.patch", "probe.cmd.in",
}
MARKERS = (
    b"pf1006 diagnostic: refused non-SD block write",
    b"pf1006 diagnostic: refused non-SD block erase",
    b"pf1006 diagnostic: refused persistent EXT_CSD change",
    b"pf1006 diagnostic: need at least 256 MiB DRAM",
    b"pf1006 diagnostic: PMIC operation failed; stopping",
    b"pf1006-probe.scr",
)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


CARD_IO = module("pf1006_card_upstream", ROOT / "scripts/a33-sdboot/card-macos.py")
VERIFY = module("pf1006_card_verify", HERE / "verify.py")
require = CARD_IO.require


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular_bytes(path, limit):
    try:
        return VERIFY.read_regular(path, limit)
    except VERIFY.VerificationError as error:
        raise RuntimeError(str(error)) from error


def check_config(profile, resolved):
    actual = dict(re.findall(r"^(CONFIG_\w+)=(.*)$", resolved, re.M))
    for line in profile.splitlines():
        enabled = re.fullmatch(r"(CONFIG_\w+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_\w+) is not set", line)
        if enabled:
            require(actual.get(enabled[1]) == enabled[2], "Resolved config mismatch: " + enabled[1])
        if disabled:
            require(actual.get(disabled[1], "n") == "n", "Forbidden config: " + disabled[1])
    for name, value in actual.items():
        require(not (re.fullmatch(r"CONFIG_(?:SPL_|TPL_)?ENV_IS_IN_\w+", name) and value == "y"),
                "Persistent environment backend: " + name)


def check_egon(image):
    """Check the SPL header and its additive checksum.

    See U-Boot tools/sunxi_egon.c, tools/mksunxiboot.c and sunxi_image.h.
    The checksum covers the declared SPL length. It excludes U-Boot proper.
    """
    require(len(image) >= 96, "Short eGON SPL header")
    require(image[4:12] == b"eGON.BT0", "Missing Allwinner SPL header")
    require(struct.unpack_from("<I", image, 0)[0] & 0xff000000 == 0xea000000,
            "Expected an ARM eGON branch instruction")
    stored, length = struct.unpack_from("<II", image, 12)
    require(96 <= length <= len(image) and length % 512 == 0, "Invalid declared SPL length")
    # Replace the stored checksum with the builder's stamp before the sum.
    computed = (sum(word[0] for word in struct.iter_unpack("<I", image[:length]))
                - stored + 0x5f0a6c39) & 0xffffffff
    require(stored == computed, "eGON SPL checksum mismatch")
    return length


def load_artifacts(build, current_sources=True):
    build = Path(build).resolve()
    require(not os.path.lexists(build / "a33.scr"), "Generic a33.scr must not be present in this build")
    manifest = json.loads(regular_bytes(build / "build.json", 32768))
    for key, value in {"format": 1, "experimental": True, "hardware_tested": False,
                       "u_boot_commit": PIN, "min_ram_bytes": 0x10000000,
                       "text_base": "0x4a000000"}.items():
        require(manifest.get(key) == value, "Unexpected build manifest field: " + key)
    run_id = manifest.get("run_id", "")
    require(isinstance(run_id, str) and re.fullmatch(r"[0-9a-f]{32}", run_id), "Invalid build run ID")
    require(set(manifest.get("artifacts", {})) == NAMES, "Unexpected artifact manifest")
    checksums = {}
    for line in regular_bytes(build / "SHA256SUMS", 8192).decode("ascii").splitlines():
        matched = re.fullmatch(r"([0-9a-f]{64})  ([a-zA-Z0-9._-]+)", line)
        require(matched and matched[2] not in checksums, "Malformed/duplicate SHA256SUMS entry")
        checksums[matched[2]] = matched[1]
    require(set(checksums) == NAMES, "Unexpected checksum file set")
    data = {}
    for name in NAMES:
        limit = 1024 * 1024 if name == "u-boot-sunxi-with-spl.bin" else 256 * 1024
        data[name] = regular_bytes(build / name, limit)
        expected = manifest["artifacts"][name]
        require(expected == {"size": len(data[name]), "sha256": digest(data[name])},
                "Artifact size/hash mismatch: " + name)
        require(checksums[name] == expected["sha256"], "Checksum mismatch: " + name)
    require(data["run-id.txt"] == (run_id + "\n").encode("ascii"), "Run-ID file mismatch")
    references = {
        "probe.cmd.in": HERE / "probe.cmd.in",
        "pf1006.config": HERE / "pf1006.config",
        "pf1006-readonly.patch": ROOT / "scripts/a33-sdboot/pf1006-readonly.patch",
    }
    if current_sources:
        for name, reference in references.items():
            require(data[name] == reference.read_bytes(), "Build differs from reviewed source: " + name)
    template = data["probe.cmd.in"]
    require(set(re.findall(rb"@[A-Z_]+@", template)) == {b"@RUN_ID@"}, "Unexpected source placeholder")
    require(data["pf1006-probe.cmd"] == template.replace(b"@RUN_ID@", run_id.encode("ascii")),
            "Rendered script does not match the reviewed source and run ID")
    require(len(data["pf1006-probe.scr"]) <= 0x10000, "Probe script exceeds bootstrap load limit")
    CARD_IO.check_script(data["pf1006-probe.scr"], data["pf1006-probe.cmd"])
    require(data["pf1006-probe.scr"][29] == 2, "Expected ARM script image")
    check_config(data["pf1006.config"].decode("ascii"), data["u-boot.config"].decode("ascii"))
    image = data["u-boot-sunxi-with-spl.bin"]
    check_egon(image)
    require(CARD_IO.OFFSET + len(image) <= 1024 * 1024, "Boot image exceeds 1 MiB boot-area limit")
    require(all(marker in image for marker in MARKERS), "Guard/unique-script markers absent from U-Boot")
    require(b"a33.scr" not in image, "U-Boot contains generic upstream script name")
    return {"path": build, "manifest": manifest, "run_id": run_id, "data": data}


def configure(build, exact_bytes):
    # Configure this private instance of the shared card I/O module.
    work = ROOT / "diagnostics/pf1006-probe/cards" / build["run_id"]
    CARD_IO.EXPECTED_BYTES = exact_bytes
    CARD_IO.WORK = work
    CARD_IO.STATE = work / "target.json"
    CARD_IO.BACKUP = work / "card-prefix-after-format.bin.gz"
    return work


def chown_owner(path):
    if os.geteuid() == 0:
        os.chown(path, int(os.environ.get("SUDO_UID", os.getuid())),
                 int(os.environ.get("SUDO_GID", os.getgid())))


def save_state(work, state):
    # A unique file lets recovery proceed after an interrupted state update.
    with tempfile.NamedTemporaryFile(mode="w", dir=work, prefix=".state-",
                                     encoding="utf-8", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            chown_owner(temporary)
            temporary.replace(work / "state.json")
        finally:
            temporary.unlink(missing_ok=True)


def load_state(work, build):
    state = json.loads(regular_bytes(work / "state.json", 32768))
    require(state.get("run_id") == build["run_id"], "Saved run ID mismatch")
    require(state.get("artifacts") == build["manifest"]["artifacts"], "Build changed since card preparation")
    return state


def diskutil(*args):
    subprocess.run(["/usr/sbin/diskutil", *args], check=True)


def raw_device(disk):
    raw = "/dev/r" + disk
    require(stat.S_ISCHR(os.lstat(raw).st_mode), "Expected a non-symlink raw card device")
    return raw


def card_files_match(mount, build, require_fresh=False):
    require(not os.path.lexists(mount / "a33.scr"), "Unexpected generic a33.scr on the card")
    script = mount / "pf1006-probe.scr"
    if os.path.lexists(script):
        require(not require_fresh, "Probe script already present on freshly formatted card")
        require(regular_bytes(script, 65536) == build["data"]["pf1006-probe.scr"], "Card script mismatch")
    else:
        require(require_fresh, "Probe script is missing from card")
    if require_fresh:
        for name in (VERIFY.STATUS_NAME, VERIFY.PREFIX_NAME):
            require(not os.path.lexists(mount / name),
                    "Stale probe output on card: " + name)


def plan(build, disk, exact_bytes):
    work = configure(build, exact_bytes)
    current = CARD_IO.card_disk(disk)
    print("PLAN ONLY: no disk or filesystem changes made.")
    print("Card: {} / {} / {} bytes".format(disk, current["MediaName"], current["TotalSize"]))
    print("Build: {} (experimental; no hardware validation)".format(build["run_id"]))
    print("Preparation erases this card and creates MBR/FAT32 after a 16 MiB gap.")
    print("It saves the first 4 MiB after format, then writes the bootloader and script.")
    print("The bootloader starts at byte 8192. The script is pf1006-probe.scr.")
    print("The tool checks the saved data and ejects the card. It does not access the frame.")
    if work.exists():
        print("This build already has card state; prepare refuses reuse. Use a fresh build for a new attempt.")


def prepare(build, disk, exact_bytes):
    require(os.geteuid() == 0, "Run prepare with sudo")
    work = configure(build, exact_bytes)
    require(not work.exists(), "Build already used or preparation interrupted; do not reuse its run ID")
    original = CARD_IO.card_disk(disk)
    require(original.get("Writable") is True, "Unlock the card before preparation.")
    print("Erase {}: {}, {} bytes".format(disk, original["MediaName"], original["TotalSize"]))
    require(input("Type ERASE {}: ".format(disk)) == "ERASE " + disk, "Cancelled")
    current = CARD_IO.card_disk(disk)
    require(all(current.get(k) == original.get(k) for k in CARD_IO.DISK_KEYS + ("DeviceTreePath",)),
            "Disk changed before format")
    work.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    chown_owner(work.parent)
    work.mkdir(mode=0o700, exist_ok=False)
    chown_owner(work)
    state = {"format": 1, "run_id": build["run_id"], "phase": "format_requested",
             "artifacts": build["manifest"]["artifacts"]}
    save_state(work, state)
    diskutil("partitionDisk", disk, "MBR", "Free Space", "%noformat%", "16M",
             "MS-DOS FAT32", "PF1006PROBE", "0b")
    formatted = CARD_IO.card_disk(disk)
    require(all(formatted.get(k) == original.get(k) for k in CARD_IO.DISK_KEYS + ("DeviceTreePath",)),
            "Disk changed during format; do not continue")
    target = CARD_IO.save_target(disk)
    diskutil("unmountDisk", disk)
    require(CARD_IO.verify_target(target, disk) is None, "Card is still mounted")
    raw = raw_device(disk)
    image = build["data"]["u-boot-sunxi-with-spl.bin"]
    before = CARD_IO.load_prefix_backup(raw, CARD_IO.BACKUP, image)
    chown_owner(CARD_IO.BACKUP)
    state.update(phase="prefix_backed_up", prefix_sha256=digest(before))
    save_state(work, state)
    diskutil("mount", disk + "s1")
    mount = CARD_IO.verify_target(target, disk)
    require(mount is not None, "Card did not mount")
    card_files_match(mount, build, require_fresh=True)
    space = os.statvfs(mount)
    require(space.f_bavail * space.f_frsize >= 32 * 1024 * 1024, "Need 32 MiB free on card")
    CARD_IO.write_file(mount / "pf1006-probe.scr", build["data"]["pf1006-probe.scr"])
    diskutil("unmountDisk", disk)
    require(CARD_IO.verify_target(target, disk) is None, "Card is still mounted")
    CARD_IO.write_boot_image(raw, before, image)
    CARD_IO.verify_target(target, disk)
    state["phase"] = "prepared"
    save_state(work, state)
    diskutil("eject", disk)
    print("Prepared, readback verified, and ejected. No frame has been accessed.")
    print("This is an experimental read probe, not an ADB installer. Review the frame boot step separately.")


def saved_target():
    return json.loads(regular_bytes(CARD_IO.STATE, 16384))


def collect(build, disk, exact_bytes):
    require(os.geteuid() != 0, "Run collect without sudo")
    work = configure(build, exact_bytes)
    state = load_state(work, build)
    require(state.get("phase") == "prepared", "Expected a prepared, not-yet-collected card")
    target = saved_target()
    mount = CARD_IO.verify_target(target, disk)
    if mount is None:
        diskutil("mount", "readOnly", disk + "s1")
        mount = CARD_IO.verify_target(target, disk)
    require(mount is not None, "Card did not mount")
    card_files_match(mount, build)
    status_data = regular_bytes(mount / VERIFY.STATUS_NAME, 16384)
    prefix_data = regular_bytes(mount / VERIFY.PREFIX_NAME, VERIFY.PREFIX_BYTES)
    report = VERIFY.verify_data(status_data, prefix_data, build["run_id"])
    destination = ROOT / "backups/pf1006-probe" / build["run_id"]
    partial = destination.with_name(destination.name + ".partial")
    require(not destination.exists() and not partial.exists(), "Capture destination already exists; refusing overwrite")
    partial.mkdir(mode=0o700, parents=True, exist_ok=False)
    CARD_IO.write_file(partial / VERIFY.STATUS_NAME, status_data)
    CARD_IO.write_file(partial / VERIFY.PREFIX_NAME, prefix_data)
    saved = VERIFY.verify(partial, build["run_id"])
    require(saved == report, "Saved capture differs from card verification")
    CARD_IO.verify_target(target, disk)
    CARD_IO.write_file(partial / "verification.json", (json.dumps(report, indent=2) + "\n").encode("utf-8"))
    partial.rename(destination)
    state.update(phase="collected", capture_sha256=report["sha256"])
    save_state(work, state)
    diskutil("eject", disk)
    print("Verified 4 MiB prefix saved privately; card ejected.")
    print("Capture: " + str(destination))
    print("This is not a complete backup and does not enable ADB.")


def restore_boot_prefix(raw, before, image):
    expected = CARD_IO.planned_prefix(before, image)
    require(CARD_IO.read_prefix(raw) == expected and CARD_IO.read_prefix(raw) == expected,
            "Card boot area changed; refusing restore")
    descriptor = os.open(raw, os.O_RDWR | os.O_NOFOLLOW)
    try:
        require(os.pwrite(descriptor, before, 0) == CARD_IO.PREFIX, "Short restore write; preserve the backup")
        fcntl.ioctl(descriptor, CARD_IO.DKIOCSYNCHRONIZECACHE)
    finally:
        os.close(descriptor)
    require(CARD_IO.read_prefix(raw) == before, "Card restore readback failed; preserve the backup")


def remove(build, disk, exact_bytes):
    require(os.geteuid() == 0, "Run remove with sudo")
    work = configure(build, exact_bytes)
    state = load_state(work, build)
    # A crash can occur after the boot write and before the state update.
    # Recovery still requires a complete match with the installed boot image.
    require(state.get("phase") in ("prefix_backed_up", "prepared", "collected"),
            "No verified prefix backup available for removal")
    target = saved_target()
    CARD_IO.verify_target(target, disk)
    compressed = regular_bytes(CARD_IO.BACKUP, CARD_IO.PREFIX + 65536)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as saved:
        before = saved.read(CARD_IO.PREFIX + 1)
    require(len(before) == CARD_IO.PREFIX and digest(before) == state.get("prefix_sha256"), "Saved prefix backup mismatch")
    require(input("Type REMOVE BOOTLOADER {}: ".format(disk)) == "REMOVE BOOTLOADER " + disk, "Cancelled")
    CARD_IO.verify_target(target, disk)
    diskutil("unmountDisk", disk)
    require(CARD_IO.verify_target(target, disk) is None, "Card is still mounted")
    restore_boot_prefix(raw_device(disk), before, build["data"]["u-boot-sunxi-with-spl.bin"])
    state["phase"] = "removed"
    save_state(work, state)
    diskutil("eject", disk)
    print("Post-format boot area restored and verified; card ejected.")
    print("Card files remain. Files erased by the original format are not restored.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path, help="completed per-run build directory")
    parser.add_argument("disk", help="explicit diskN from diskutil list external physical")
    parser.add_argument("exact_bytes", type=int, help="exact Disk Size in bytes from diskutil info")
    parser.add_argument("--action", choices=("plan", "prepare", "collect", "remove"), default="plan")
    args = parser.parse_args(argv)
    require(sys.platform == "darwin", "Run on macOS")
    os.umask(0o077)
    # Use saved build data for collection and removal after source changes.
    build = load_artifacts(args.build, current_sources=args.action in ("plan", "prepare"))
    {"plan": plan, "prepare": prepare, "collect": collect, "remove": remove}[args.action](
        build, args.disk, args.exact_bytes)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit("STOP: " + str(error)) from error
