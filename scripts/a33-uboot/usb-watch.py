#!/usr/bin/env python3
"""Print a timestamped line each time the frame's USB identity changes (macOS). Read-only.

Usage (from the repository root, no sudo; Ctrl+C to stop):
  python3 -I scripts/a33-uboot/usb-watch.py
  python3 -I scripts/a33-uboot/usb-watch.py --vendor 1f3a --vendor 18d1 --interval 0.25

It polls `ioreg -p IOUSB` and prints every device whose vendor ID is in the list (default
1f3a Allwinner and 18d1 Google), with product ID, product and vendor strings and link speed.
Use it for the T3 timeline: plug the cable in with no SD card and watch for 90 s. The IDs to
expect are in the T3 table of docs/pf1007l-start-here.md: 1f3a:1000 on stock AiMOR, 1f3a:efe8
in FEL, 1f3a:1002 after a boot patch. It only reads the USB tree; it sends nothing to the device.
"""

import argparse
import datetime
import plistlib
import subprocess
import sys
import time


def walk(node, vendors, out):
    if isinstance(node, dict):
        if node.get("idVendor") in vendors:
            speed = node.get("Device Speed", node.get("UsbDeviceSpeed", "?"))
            out.append(f'{node["idVendor"]:04x}:{node.get("idProduct", 0):04x} '
                       f'"{node.get("USB Product Name", "?")}" / '
                       f'"{node.get("USB Vendor Name", "?")}" speed={speed}')
        for value in node.values():
            walk(value, vendors, out)
    elif isinstance(node, list):
        for value in node:
            walk(value, vendors, out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vendor", action="append", metavar="HEX",
                        help="USB vendor ID to watch, in hex (repeatable; default 1f3a and 18d1)")
    parser.add_argument("--interval", type=float, default=0.25, help="seconds between polls")
    args = parser.parse_args()
    if sys.platform != "darwin":
        sys.exit("STOP: this helper reads macOS's ioreg. On Linux use: watch -n 0.5 'lsusb | grep -i -e 1f3a -e 18d1'")
    vendors = {int(v, 16) for v in (args.vendor or ["1f3a", "18d1"])}
    names = "/".join(f"{v:04x}" for v in sorted(vendors))
    last = None
    try:
        while True:
            found = []
            tree = plistlib.loads(subprocess.check_output(["ioreg", "-p", "IOUSB", "-l", "-a"]))
            walk(tree, vendors, found)
            now = "; ".join(sorted(found)) or f"(no {names} device)"
            if now != last:
                stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(stamp, now, flush=True)
                last = now
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
