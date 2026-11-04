#!/usr/bin/env python3
"""Load the matched RK3568 DDR and USB reader into RAM from MaskROM.

No reset, flash write, erase, or bootloader upgrade command is used.
Run without --load to check local files only. See docs/loader-research.md.
With --frame-ddr, the DDR stage comes from the frame's own idbloader instead of the official
v1.13 binary (newer 150-CAL firmware; see docs/skylight-150cal-ddr-v126.md).
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import time
import zlib

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTED_SECTORS = 30539776  # the eMMC of the unit in docs/next-session.md
# Rockchip idbloader copies in the first 32 MiB (sectors 64 and 1088).
IDB_COPIES = (0x8000, 0x88000)
COMPONENTS = {
    "rk3568_ddr_1056MHz_v1.13.bin": "6f165b37640eb876b5f41297bcce6451eb8a86fa56649633d4aca76047136a36",
    "rk356x_usbplug_v1.14.bin": "660886820e2a7b43002e6a5ca576b5cc363907b4d1537c3acd8993132ec17751",
}
PATCHED_NAME = "rk356x_usbplug_v1.14-read-unlimited.bin"
PATCHED_SHA256 = "38f7a4e06c06b75d476b059ea590f07033f3606ff7848189655727f00b6e84c2"
FASTBOOT_NAME = "rk356x_usbplug_v1.14-read-unlimited-fastboot.bin"
FASTBOOT_SHA256 = "f6f1cf8eb5ea6f0af76e41bb15f8d00a72ae416a1cf43d1a9fea2234cb5c1c31"


def run(command, cwd, timeout=60):
    result = subprocess.run([str(x) for x in command], cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=timeout)
    print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError(f"Command failed with exit {result.returncode}")
    return result.stdout


def helper_candidate(dev):
    # Historical usbplug v1.14 identifies as USB-MSC with bcdUSB=0x0200,
    # so rkdeveloptool's descriptor heuristic still calls it Maskrom.
    return dev["mode_from_descriptors"] == "Loader" or "USB-MSC" in dev.get("name", "").upper()


def frame_ddr(stock):
    """Return the DDR stage (first image) of the frame's v2 (RKNS) idbloader, fully verified.

    Layout from U-Boot tools/rkcommon.c (struct header0_info_v2 and struct image_entry):
    magic at 0, size_and_nimage at 8 ([31:16] image count, [15:0] header-hash offset in 4-byte
    words), boot_flag at 12 ([3:0] hash type, 1 = SHA-256), four 88-byte image entries from 0x78
    (size_and_off: [31:16] size, [15:0] offset, both in 512-byte sectors from the header; the
    image hash at +0x18). The header hash covers everything before the hash field.
    """
    copies = []
    for base in IDB_COPIES:
        header = stock[base:base + 2048]
        magic = header[:4]
        if magic == b"RKSS":
            raise RuntimeError(f"Signed (RKSS) idbloader at {base:#x}: secure boot is likely "
                               "enforced and unsigned RAM helpers are refused (issue #222)")
        if magic != b"RKNS":
            raise RuntimeError(f"No v2 (RKNS) idbloader at {base:#x}; --frame-ddr does not apply")
        size_and_nimage, boot_flag = struct.unpack_from("<II", header, 8)
        count, hash_offset = size_and_nimage >> 16, (size_and_nimage & 0xFFFF) * 4
        if boot_flag & 0xF != 1:
            raise RuntimeError(f"idbloader at {base:#x} does not use SHA-256 hashes")
        if not 1 <= count <= 4 or not 0x78 + 4 * 88 <= hash_offset <= len(header) - 32:
            raise RuntimeError(f"Unexpected idbloader header layout at {base:#x}")
        if hashlib.sha256(header[:hash_offset]).digest() != header[hash_offset:hash_offset + 32]:
            raise RuntimeError(f"idbloader header hash mismatch at {base:#x}")
        images, end = [], 0
        for i in range(count):
            size_and_off, = struct.unpack_from("<I", header, 0x78 + i * 88)
            offset, size = size_and_off & 0xFFFF, size_and_off >> 16
            image = stock[base + offset * 512:base + (offset + size) * 512]
            if size == 0 or len(image) != size * 512:
                raise RuntimeError(f"idbloader image {i + 1} at {base:#x} is out of range")
            stored = header[0x78 + i * 88 + 0x18:0x78 + i * 88 + 0x38]
            if hashlib.sha256(image).digest() != stored:
                raise RuntimeError(f"idbloader image {i + 1} hash mismatch at {base:#x}")
            images.append(image)
            end = max(end, (offset + size) * 512)
        copies.append(stock[base:base + end])
    if copies[0] != copies[1]:
        raise RuntimeError("The two idbloader copies differ; refusing to choose")
    return images[0]


def gpt_sector_count(stock):
    """Return the eMMC sector count from the primary GPT header's backup-header LBA, verified."""
    header = bytearray(stock[512:512 + 92])
    if header[:8] != b"EFI PART" or struct.unpack_from("<I", header, 12)[0] != 92:
        raise RuntimeError("No primary GPT header in the preserved first 32 MiB")
    stored_crc, = struct.unpack_from("<I", header, 16)
    struct.pack_into("<I", header, 16, 0)
    if zlib.crc32(header) != stored_crc:
        raise RuntimeError("Primary GPT header CRC mismatch")
    current, alternate, _, last_usable = struct.unpack_from("<QQQQ", header, 24)
    entries_lba, count, size, entries_crc = struct.unpack_from("<QIII", header, 72)
    entries = stock[entries_lba * 512:entries_lba * 512 + count * size]
    if current != 1 or not last_usable < alternate or zlib.crc32(entries) != entries_crc:
        raise RuntimeError("Primary GPT header fields or entry CRC are inconsistent")
    return alternate + 1


def verify_flash_info(rk, sectors):
    info = run([rk, "rfi"], rk.parent)
    if "Flash Size:" not in info or f"{sectors} Sectors" not in info:
        raise RuntimeError("Flash query did not match this device's known sector count")
    print("Flash query responds with expected size. This does NOT establish unrestricted reads; "
          "the historical USB helper has also returned 0xCC above 32 MiB.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load", action="store_true", help="actually upload to RAM")
    parser.add_argument("--patched", action="store_true",
                        help="select the exact reviewed read-limit patch (still RAM-only)")
    parser.add_argument("--fastboot-reset", action="store_true",
                        help="select reviewed read helper whose later rd 6 requests Fastboot; does not reset now")
    parser.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                        help="wait for the host to configure the MaskROM interface")
    parser.add_argument("--frame-ddr", action="store_true",
                        help="use the DDR stage from the frame's own idbloader, verified against its "
                             "header hashes, and the sector count from its GPT "
                             "(docs/skylight-150cal-ddr-v126.md)")
    args = parser.parse_args()
    if args.wait < 0:
        parser.error("--wait must be nonnegative")

    component_dir = ROOT / "diagnostics/stock-loader-research"
    paths = [component_dir / name for name in COMPONENTS]
    for path in paths[1:] if args.frame_ddr else paths:
        if hashlib.sha256(path.read_bytes()).hexdigest() != COMPONENTS[path.name]:
            raise RuntimeError(f"Incorrect component hash: {path.name}")
    if args.patched:
        patched = component_dir / PATCHED_NAME
        if hashlib.sha256(patched.read_bytes()).hexdigest() != PATCHED_SHA256:
            raise RuntimeError("Incorrect patched helper hash; create it with patch-usb-reader.py")
        paths[1] = patched
    if args.fastboot_reset:
        patched = component_dir / FASTBOOT_NAME
        if hashlib.sha256(patched.read_bytes()).hexdigest() != FASTBOOT_SHA256:
            raise RuntimeError("Incorrect Fastboot-reset helper hash; create it with patch-fastboot-reader.py")
        paths[1] = patched
    stock = (ROOT / "backups/first-32MiB.img").read_bytes()
    sectors = DOCUMENTED_SECTORS
    if args.frame_ddr:
        if len(stock) != 32 * 1024 * 1024:
            raise RuntimeError("The preserved first-32-MiB image has the wrong size")
        ddr = frame_ddr(stock)
        sectors = gpt_sector_count(stock)
        digest = hashlib.sha256(ddr).hexdigest()
        paths[0] = component_dir / f"frame-ddr-{digest[:16]}.bin"
        if paths[0].exists() and paths[0].read_bytes() != ddr:
            raise RuntimeError(f"Refusing existing, different file: {paths[0]}")
        if not paths[0].exists():
            with paths[0].open("xb") as out:
                out.write(ddr)
        version = re.search(rb"ddr-v[0-9.]+-[0-9a-f]+", ddr)
        print(f"Frame DDR stage: {len(ddr)} bytes, SHA256 {digest}, "
              f"{version.group().decode() if version else 'no version string'}; "
              f"GPT sector count {sectors}", flush=True)
    ddr = paths[0].read_bytes()
    # With --frame-ddr, frame_ddr() has already matched the DDR stage against the idbloader.
    if len(stock) != 32 * 1024 * 1024 or (not args.frame_ddr and stock[0x8800:0x8800 + len(ddr)] != ddr):
        raise RuntimeError("The preserved first-32-MiB image does not match the DDR helper. Newer "
                           "firmware carries a different DDR build: see --frame-ddr and "
                           "docs/skylight-150cal-ddr-v126.md")
    rk = ROOT / "diagnostics/tools/rkdeveloptool-src/rkdeveloptool"
    xrock = ROOT / "diagnostics/tools/xrock-src/xrock"
    if not rk.is_file() or not xrock.is_file():
        raise RuntimeError("Build the host tools first; see the research log")
    print("Local component hashes and stock DDR match verified.", flush=True)
    if not args.load:
        print("Check only. No device was opened and no upload was performed.")
        return

    spec = importlib.util.spec_from_file_location("usb_status", ROOT / "scripts/usb-status.py")
    status = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(status)
    deadline = time.monotonic() + args.wait
    previous = None
    while True:
        devices = status.devices()
        if devices != previous:
            print(json.dumps(devices), flush=True)
            previous = devices
        if len(devices) > 1:
            raise RuntimeError("More than one Rockchip device connected; refusing to choose")
        if len(devices) == 1:
            dev = devices[0]
            if dev["usb_id"] == "2207:350a" and helper_candidate(dev):
                if dev["configuration"] != 1:
                    raise RuntimeError("A loader/helper is already present but unconfigured; refusing another upload")
                print("A loader/helper is already present. No upload will be sent.", flush=True)
                verify_flash_info(rk, sectors)
                return
            if dev["usb_id"] != "2207:350a" or dev["mode_from_descriptors"] != "MaskROM":
                raise RuntimeError("Expected this RK3568 in MaskROM; refusing other modes")
            if dev["configuration"] == 1:
                break
        if time.monotonic() >= deadline:
            raise RuntimeError("MaskROM is not configured by macOS; accessory approval may be pending")
        time.sleep(2)

    listing = run([rk, "ld"], rk.parent)
    lines = [line for line in listing.splitlines() if line.startswith("DevNo=")]
    if len(lines) != 1 or "Vid=0x2207,Pid=0x350a" not in lines[0] or "Maskrom" not in lines[0]:
        raise RuntimeError("rkdeveloptool did not confirm exactly one expected MaskROM device")
    print("Uploading matched DDR and USB helper to RAM only.", flush=True)
    run([xrock, "maskrom", *paths, "--rc4-off"], xrock.parent)
    print("Upload command returned. Checking for a responding USB helper.", flush=True)
    # xrock's upload function does not propagate all transfer errors; its exit code
    # alone must never be represented as successful initialization or a backup.
    deadline = time.monotonic() + 30
    while True:
        devices = status.devices()
        if (len(devices) == 1 and devices[0]["usb_id"] == "2207:350a"
                and helper_candidate(devices[0])
                and devices[0]["configuration"] == 1):
            break
        if time.monotonic() >= deadline:
            print(json.dumps(devices), flush=True)
            raise RuntimeError("Upload is UNVERIFIED: helper did not become configured; check accessory approval")
        time.sleep(1)
    listing = run([rk, "ld"], rk.parent)
    lines = [line for line in listing.splitlines() if line.startswith("DevNo=")]
    if len(lines) != 1 or "Vid=0x2207,Pid=0x350a" not in lines[0]:
        raise RuntimeError("Upload is UNVERIFIED: host tool did not confirm one expected device")
    verify_flash_info(rk, sectors)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error))
