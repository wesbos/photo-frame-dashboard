#!/usr/bin/env python3
"""Check a PF1006 probe's 4 MiB capture. Do not change files.

This check does not prove hardware compatibility or a complete backup.
Header signatures are possible matches, not a verified partition map.
Keep captures private. They can contain firmware and device identifiers.
Requires Python 3.9 or later. Uses the standard library only.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import struct
import sys
from pathlib import Path

PREFIX_BYTES = 4 * 1024 * 1024
STATUS_LIMIT = 16 * 1024
STATUS_NAME = "pf1006-probe-status.txt"
PREFIX_NAME = "pf1006-probe.bin"
STATUS_KEYS = {
    "format", "run_id", "stage", "result", "start_sector", "sector_count",
    "read_bytes", "read1_sha256", "read2_sha256", "reread", "card_verify",
    "media", "extcsd_status", "extcsd_rev", "extcsd_sec0", "extcsd_sec1",
    "extcsd_sec2", "extcsd_sec3",
}


class VerificationError(ValueError):
    """The capture failed a required check."""


def read_regular(path, limit):
    """Read a regular file once. Reject links, excess size and detected changes."""
    path = Path(path)
    if not isinstance(limit, int) or limit < 0:
        raise VerificationError("file size limit is invalid")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise VerificationError("expected a regular file: " + path.name)
    flags = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with open(path, "rb", opener=lambda name, mode: os.open(name, mode | flags)) as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode):
            raise VerificationError("expected a regular file: " + path.name)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise VerificationError("file changed before the read: " + path.name)
        if opened.st_size > limit:
            raise VerificationError(f"file exceeds {limit} bytes: {path.name}")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(data) > limit:
        raise VerificationError(f"file exceeds {limit} bytes: {path.name}")
    if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise VerificationError("file changed during the read: " + path.name)
    return data


def parse_status_data(raw):
    if len(raw) > STATUS_LIMIT:
        raise VerificationError("status exceeds 16 KiB")
    if not raw.endswith(b"\0") or b"\0" in raw[:-1]:
        raise VerificationError("status must have exactly one final NUL terminator")
    try:
        text = raw[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise VerificationError("status is not ASCII") from exc
    if any(ord(char) < 32 and char != "\n" or ord(char) == 127 for char in text):
        raise VerificationError("status contains a control character; use LF line endings")
    if not text.endswith("\n"):
        raise VerificationError("status has an incomplete final line")
    fields = {}
    for line in text[:-1].split("\n"):
        key, separator, value = line.partition("=")
        if not separator or not key.startswith("pf1006_"):
            raise VerificationError("unexpected status line")
        name = key[len("pf1006_"):]
        if name in fields:
            raise VerificationError("duplicate status field: " + name)
        fields[name] = value
    if set(fields) != STATUS_KEYS:
        raise VerificationError("missing or unexpected status fields")
    return fields


def parse_status(path):
    return parse_status_data(read_regular(path, STATUS_LIMIT))


def signature_candidates(data):
    findings = []
    for name, magic in (("eGON boot0", b"eGON.BT0"),
                        ("Android boot", b"ANDROID!"),
                        ("FDT", b"\xd0\x0d\xfe\xed")):
        offset = 0
        for _ in range(64):
            offset = data.find(magic, offset)
            if offset < 0:
                break
            item = {"kind": name, "magic_offset": offset}
            if name == "eGON boot0" and offset >= 4 and offset + 16 <= len(data):
                start = offset - 4
                size = struct.unpack_from("<I", data, start + 16)[0]
                item.update(header_offset=start, declared_bytes=size,
                            declared_range_in_prefix=20 <= size <= len(data) - start)
            elif name == "FDT" and offset + 8 <= len(data):
                size = struct.unpack_from(">I", data, offset + 4)[0]
                item.update(declared_bytes=size,
                            declared_range_in_prefix=40 <= size <= len(data) - offset)
            findings.append(item)
            offset += len(magic)
        else:
            if data.find(magic, offset) >= 0:
                findings.append({"kind": name, "more_candidates_omitted": True})
    return findings


def verify_data(status_data, prefix_data, expected_run_id):
    """Check these exact bytes. Return the same report as verify()."""
    if not isinstance(expected_run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", expected_run_id):
        raise VerificationError("expected run ID must be 32 lowercase hexadecimal characters")
    fields = parse_status_data(status_data)
    if fields["run_id"] != expected_run_id:
        raise VerificationError("run ID mismatch: possible output from an earlier build")
    required = {
        "format": "1", "stage": "finished", "result": "VERIFIED_4MIB_PREFIX",
        "start_sector": "0", "sector_count": "0x2000", "read_bytes": "0x400000",
        "reread": "equal", "card_verify": "equal", "media": "mmc",
    }
    for key, value in required.items():
        if fields[key] != value:
            raise VerificationError("unexpected or incomplete " + key + ": " + fields[key])
    first_hash = fields["read1_sha256"]
    if not re.fullmatch(r"[0-9a-f]{64}", first_hash):
        raise VerificationError("invalid SHA-256 in status")
    if fields["read2_sha256"] != first_hash:
        raise VerificationError("independent read hashes differ")
    if len(prefix_data) != PREFIX_BYTES:
        raise VerificationError("prefix must be exactly 4 MiB")
    if hashlib.sha256(prefix_data).hexdigest() != first_hash:
        raise VerificationError("prefix SHA-256 differs from the on-frame reads")
    if b"\xcc" * 65536 in prefix_data:
        raise VerificationError("prefix contains a 64 KiB run of 0xCC filler")
    if prefix_data in (b"\0" * PREFIX_BYTES, b"\xff" * PREFIX_BYTES):
        raise VerificationError("prefix is entirely zero or 0xFF; not useful evidence")

    capacity = None
    revision = None
    values = []
    for key in ("extcsd_rev", "extcsd_sec0", "extcsd_sec1", "extcsd_sec2", "extcsd_sec3"):
        value = fields[key]
        if value == "unknown" and fields["extcsd_status"] == "unavailable":
            values.append(None)
        elif re.fullmatch(r"[0-9a-f]{1,2}", value):
            values.append(int(value, 16))
        else:
            raise VerificationError("invalid EXT_CSD byte: " + key)
    if fields["extcsd_status"] == "available":
        revision = values[0]
        sectors = int.from_bytes(bytes(values[1:]), "little")
        # A zero SEC_COUNT does not give a capacity.
        if sectors:
            capacity = sectors * 512
            if capacity < PREFIX_BYTES:
                raise VerificationError("reported capacity is smaller than the prefix")
    elif fields["extcsd_status"] != "unavailable":
        raise VerificationError("unexpected EXT_CSD status")

    return {
        "result": "verified_prefix_only", "run_id": expected_run_id,
        "bytes": len(prefix_data), "sha256": first_hash,
        "media": "MMC (not SD), according to U-Boot register check",
        "ext_csd_revision": revision, "ext_csd_capacity_bytes": capacity,
        "signature_candidates": signature_candidates(prefix_data),
        "limits": "4 MiB prefix only; not a full backup, unlock, or verified partition map",
    }


def verify(card, expected_run_id):
    card = Path(card)
    return verify_data(read_regular(card / STATUS_NAME, STATUS_LIMIT),
                       read_regular(card / PREFIX_NAME, PREFIX_BYTES), expected_run_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", type=Path, help="directory containing both probe output files")
    parser.add_argument("--run-id", required=True, help="expected token from this build")
    parser.add_argument("--compare", type=Path, help="independent prior capture to compare")
    parser.add_argument("--compare-run-id", help="expected token for the prior capture")
    parser.add_argument("--json", action="store_true", help="print structured metadata")
    args = parser.parse_args(argv)
    if bool(args.compare) != bool(args.compare_run_id):
        parser.error("--compare and --compare-run-id must be supplied together")
    if args.compare and args.compare_run_id == args.run_id:
        parser.error("use a different build run ID for the comparison capture")
    try:
        report = verify(args.card, args.run_id)
        if args.compare:
            other = verify(args.compare, args.compare_run_id)
            if report["sha256"] != other["sha256"]:
                raise VerificationError("independent capture differs")
            report["independent_capture"] = "same prefix hash; provenance must be checked separately"
    except (OSError, VerificationError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("PASS: The 4 MiB capture matches both frame reads and the SD readback.")
        print("SHA-256: " + report["sha256"])
        if report["ext_csd_capacity_bytes"] is not None:
            print("EXT_CSD user-area capacity: {} bytes".format(report["ext_csd_capacity_bytes"]))
        for candidate in report["signature_candidates"]:
            print("Possible header (not verified): " + json.dumps(candidate))
        if args.compare:
            print("The capture hashes match. Confirm that each capture came from a separate boot.")
        print(report["limits"] + ".")
        print("Keep the capture and device identifiers private.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
