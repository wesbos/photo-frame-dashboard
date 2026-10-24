#!/usr/bin/env python3
"""Read Rockchip USB descriptors on macOS or Linux, without opening the device.

Output omits device serial numbers. --watch prints only state changes.
This does not approve accessories or change USB modes.
"""

import argparse
import datetime
import json
from pathlib import Path
import platform
import plistlib
import subprocess
import time


def mode_for(vid, pid, bcd):
    if vid == 0x2207 and pid == 0x0007:
        return "normal/MTP candidate"
    if vid == 0x2207 and pid == 0x350A and isinstance(bcd, int):
        # Rockchip's RKScan.cpp uses the low bit of bcdUSB.
        return "Loader" if bcd & 1 else "MaskROM"
    return "unknown"


def linux_devices(vendors):
    """The same fields from sysfs. Linux has no enumeration state; the field is always None."""
    found = []
    for node in sorted(Path("/sys/bus/usb/devices").iterdir()):
        def attr(name):
            try:
                return (node / name).read_text().strip()
            except OSError:
                return ""
        if not attr("idVendor") or int(attr("idVendor"), 16) not in vendors:
            continue
        vid, pid = int(attr("idVendor"), 16), int(attr("idProduct"), 16)
        # sysfs prints bcdUSB as "%2x.%02x", so "2.01" is 0x0201.
        major, _, minor = attr("version").partition(".")
        bcd = (int(major, 16) << 8 | int(minor, 16)) if major and minor else None
        found.append({
            "usb_id": f"{vid:04x}:{pid:04x}",
            "name": attr("product"),
            "bcdUSB": f"0x{bcd:04x}" if isinstance(bcd, int) else None,
            "mode_from_descriptors": mode_for(vid, pid, bcd),
            "configuration": int(attr("bConfigurationValue")) if attr("bConfigurationValue") else None,
            "enumeration_state": None,
        })
    return found


def devices(vendors=(0x2207,)):
    if platform.system() == "Linux":
        return linux_devices(vendors)
    raw = subprocess.check_output(["ioreg", "-a", "-l", "-p", "IOUSB"], timeout=10)
    found = []

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get("idVendor") in vendors:
            vid = node.get("idVendor")
            pid = node.get("idProduct")
            bcd = node.get("bcdUSB")
            name = node.get("USB Product Name", node.get("IORegistryEntryName", ""))
            mode = "unknown"
            if vid == 0x2207 and pid == 0x0007:
                mode = "normal/MTP candidate"
            elif vid == 0x2207 and pid == 0x350A and isinstance(bcd, int):
                # Rockchip's RKScan.cpp uses the low bit of bcdUSB.
                mode = "Loader" if bcd & 1 else "MaskROM"
            found.append({
                "usb_id": f"{vid:04x}:{pid:04x}",
                "name": name,
                "bcdUSB": f"0x{bcd:04x}" if isinstance(bcd, int) else None,
                "mode_from_descriptors": mode,
                "configuration": node.get("kUSBCurrentConfiguration"),
                "enumeration_state": node.get("UsbEnumerationState"),
            })
        for child in node.get("IORegistryEntryChildren", []):
            walk(child)

    for root in raw_roots(plistlib.loads(raw)):
        walk(root)
    return found


def raw_roots(value):
    return value if isinstance(value, list) else [value]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", type=int, metavar="SECONDS", default=0)
    parser.add_argument("--android", action="store_true",
                        help="also show Google-vendor Android/recovery/fastboot USB nodes")
    args = parser.parse_args()
    if args.watch < 0:
        parser.error("--watch must be nonnegative")
    deadline = time.monotonic() + args.watch
    previous = None
    while True:
        state = devices((0x2207, 0x18d1) if args.android else (0x2207,))
        if state != previous:
            print(json.dumps({"time": datetime.datetime.now().astimezone().isoformat(),
                              "devices": state}), flush=True)
            previous = state
        if time.monotonic() >= deadline:
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
