#!/usr/bin/env python3
"""Create a guarded, local-only unrestricted-read candidate from usbplug v1.14.

This script never opens USB or uploads anything. The patched binary is intended
only for a separately reviewed RAM upload, never installation to device flash.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

ORIGINAL_SHA256 = "660886820e2a7b43002e6a5ca576b5cc363907b4d1537c3acd8993132ec17751"
OFFSET = 0x94B8
EXPECTED = bytes.fromhex("e9031032")  # mov w9, #0x10000
REPLACEMENT = bytes.fromhex("09008012")  # mov w9, #-1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    original = args.input.read_bytes()
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        parser.error("Input is not the exact known official usbplug v1.14 binary")
    if original[OFFSET:OFFSET + 4] != EXPECTED:
        parser.error("Initializer instruction differs from reviewed bytes")
    # Guard the store and both read-limit branches used in the offline analysis.
    guards = {0x94CC: "09c505b9", 0x9D2C: "02030054", 0x9E28: "c2000054"}
    for offset, expected in guards.items():
        if original[offset:offset + 4] != bytes.fromhex(expected):
            parser.error(f"Reviewed surrounding instruction differs at {offset:#x}")
    patched = original[:OFFSET] + REPLACEMENT + original[OFFSET + 4:]
    manifest = Path(str(args.output) + ".json")
    for path in (args.output, manifest):
        if path.exists() or path.is_symlink():
            parser.error(f"Refusing existing output: {path}")
    record = {
        "input_sha256": ORIGINAL_SHA256,
        "output_sha256": hashlib.sha256(patched).hexdigest(),
        "bytes": len(patched), "patch_offset": hex(OFFSET),
        "original_instruction_bytes": EXPECTED.hex(),
        "patched_instruction_bytes": REPLACEMENT.hex(),
        "original_instruction": "mov w9, #0x10000",
        "patched_instruction": "mov w9, #-1",
        "purpose": "Initialize flash read-limit sector to 0xffffffff instead of 0x10000",
        "status": "Offline candidate; no USB access or live validation performed by this script",
        "scope": "RAM upload only; do not flash or install this binary",
        "integrity_note": "No secure-boot signature has been regenerated or verified. xrock generates transport CRC16 separately.",
    }
    with args.output.open("xb") as output:
        output.write(patched)
        output.flush()
        os.fsync(output.fileno())
    with manifest.open("x") as output:
        json.dump(record, output, indent=2)
        output.write("\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
