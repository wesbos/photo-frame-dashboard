#!/usr/bin/env python3
"""Verify the known stock DDR blob and find full matches in a local flash dump."""

import argparse
import hashlib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("ddr", type=Path)
    parser.add_argument("--extract", type=Path)
    args = parser.parse_args()
    blob = args.ddr.read_bytes()
    expected = "6f165b37640eb876b5f41297bcce6451eb8a86fa56649633d4aca76047136a36"
    digest = hashlib.sha256(blob).hexdigest()
    if digest != expected:
        parser.error(f"DDR hash differs from known official 1056 MHz v1.13 binary: {digest}")
    dump = args.dump.read_bytes()
    offsets = []
    position = 0
    while True:
        position = dump.find(blob, position)
        if position < 0:
            break
        offsets.append(position)
        position += 1
    if not offsets:
        parser.error("No complete byte-for-byte match in dump")
    print(f"Verified {len(blob):,} bytes; SHA256 {digest}")
    print("Full matches: " + ", ".join(hex(offset) for offset in offsets))
    if args.extract:
        with args.extract.open("xb") as output:
            output.write(dump[offsets[0]:offsets[0] + len(blob)])
        print(f"Extracted first matching region to {args.extract}")


if __name__ == "__main__":
    main()
