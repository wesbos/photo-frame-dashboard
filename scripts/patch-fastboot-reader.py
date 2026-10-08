#!/usr/bin/env python3
"""Offline only: make rd 6 request stock Fastboot from the RAM read helper."""

import argparse
import hashlib
import json
from pathlib import Path

INPUT_SHA256 = "38f7a4e06c06b75d476b059ea590f07033f3606ff7848189655727f00b6e84c2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    original = args.input.read_bytes()
    if hashlib.sha256(original).hexdigest() != INPUT_SHA256:
        parser.error("Input must be the exact reviewed read-limit-patched helper")
    guards = {0x94B8: "09008012", 0x9894: "13609852", 0x9898: "5348aa72",
              0x98E4: "73060011", 0x99DC: "60050054", 0x9A88: "e003132a",
              0x9A8C: "5ff0ff97", 0x5C1C: "000100b9"}
    for offset, expected in guards.items():
        if original[offset:offset + 4] != bytes.fromhex(expected):
            parser.error(f"Instruction mismatch at {offset:#x}")
    patched = original[:0x98E4] + bytes.fromhex("73260011") + original[0x98E8:]
    manifest = Path(str(args.output) + ".json")
    for path in (args.output, manifest):
        if path.exists() or path.is_symlink():
            parser.error(f"Refusing existing output: {path}")
    record = {
        "input_sha256": INPUT_SHA256,
        "output_sha256": hashlib.sha256(patched).hexdigest(),
        "bytes": len(patched), "patch_offset": "0x98e4",
        "before": "73060011: add w19, w19, #1",
        "after": "73260011: add w19, w19, #9",
        "effect": "rd 6 writes boot flag 0x5242c309 to MMIO 0xfdc20200, then resets",
        "retained": "Read-limit patch; rd 3 MaskROM reset behavior",
        "scope": "RAM helper only; never install to flash",
        "status": "Offline-reviewed candidate, not proof of successful Fastboot entry",
        "warning": "Reset path changes no flash image; subsequent stock boot behavior is not controlled by this patch",
    }
    with args.output.open("xb") as output:
        output.write(patched)
    with manifest.open("x") as output:
        json.dump(record, output, indent=2)
        output.write("\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
