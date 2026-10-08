#!/usr/bin/env python3
"""Read and validate small samples before trusting a full flash backup.

Specific to this unit's saved GPT and first-32-MiB backup. No writes to the
device are sent. Refuses existing output files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True, help="new filename prefix under backups/")
    args = parser.parse_args()
    if not args.prefix or Path(args.prefix).name != args.prefix:
        parser.error("prefix must be a single filename component")
    tool = ROOT / "diagnostics/tools/rkdeveloptool-src/rkdeveloptool"
    samples = [("above-a", 65536), ("above-b", 65536),
               ("recovery-a", 182272), ("recovery-b", 182272), ("low", 0)]
    paths = {name: ROOT / "backups" / f"{args.prefix}-{name}.img" for name, _ in samples}
    manifest = ROOT / "backups" / f"{args.prefix}.json"
    if any(p.exists() or p.is_symlink() for p in [*paths.values(), manifest]):
        raise RuntimeError("Refusing existing probe output")
    result = subprocess.run([str(tool), "ld"], cwd=tool.parent, capture_output=True,
                            text=True, timeout=90, check=True)
    devices = [s for s in result.stdout.splitlines() if s.startswith("DevNo=")]
    if len(devices) != 1 or "Vid=0x2207,Pid=0x350a" not in devices[0]:
        raise RuntimeError("Expected exactly one known Rockchip USB device")
    data = {}
    for name, lba in samples:
        result = subprocess.run([str(tool), "rl", str(lba), "8", str(paths[name])],
                                cwd=tool.parent, capture_output=True, text=True,
                                timeout=90, check=True)
        chunk = paths[name].read_bytes()
        if len(chunk) != 4096 or "(100%)" not in result.stdout:
            raise RuntimeError(f"Incomplete probe: {name}")
        if chunk == b"\xcc" * len(chunk):
            raise RuntimeError(f"Restricted filler returned: {name}")
        data[name] = chunk
        print(f"{name}: 4096 bytes, prefix {chunk[:16].hex()}", flush=True)
    if data["above-a"] != data["above-b"] or data["recovery-a"] != data["recovery-b"]:
        raise RuntimeError("Repeated reads differ")
    if data["recovery-a"][:8] != b"ANDROID!":
        raise RuntimeError("Expected recovery Android header missing")
    with (ROOT / "backups/first-32MiB.img").open("rb") as saved:
        if data["low"] != saved.read(4096):
            raise RuntimeError("Low sample differs from preserved flash")
    report = {"validated": True, "samples": [
        {"file": paths[name].name, "lba": lba, "bytes": 4096,
         "sha256": hashlib.sha256(data[name]).hexdigest()}
        for name, lba in samples]}
    with manifest.open("x") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
    print("Repeated high reads, recovery magic, and preserved low sample validated.")


if __name__ == "__main__":
    main()
