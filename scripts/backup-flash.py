#!/usr/bin/env python3
"""Stream only rkdeveloptool rl into a validated gzip backup (POSIX/macOS)."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import tempfile
import time


def backup(args):
    output = args.output.expanduser().absolute()
    if not str(output).endswith(".img.gz"):
        raise ValueError("--output must end with .img.gz")
    partial = Path(str(output) + ".partial")
    manifest = Path(str(output) + ".json")
    manifest_partial = Path(str(manifest) + ".partial")
    log = Path(str(output) + ".log")
    for path in (output, partial, manifest, manifest_partial, log):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing existing path: {path}")
    tool = Path(args.tool).expanduser().resolve(strict=True)
    expected = args.sectors * 512
    deadline = time.monotonic() + args.timeout
    raw_hash = hashlib.sha256()
    total = 0
    cc_tail = 0
    suspicious = re.compile(b"\xcc{65536}")
    child = None

    def check_deadline():
        if time.monotonic() > deadline:
            raise TimeoutError(f"Backup exceeded {args.timeout} seconds")

    try:
        with partial.open("xb") as compressed, log.open("xb") as log_file:
            with tempfile.TemporaryDirectory(prefix="skylight-read-") as directory:
                fifo = Path(directory) / "flash.fifo"
                os.mkfifo(fifo, 0o600)
                # Holding a writer avoids a startup EOF before the child opens wb+.
                fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
                try:
                    command = [str(tool), "rl", "0", str(args.sectors), str(fifo)]
                    child = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
                    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed,
                                       compresslevel=1, mtime=0) as zipped:
                        while True:
                            check_deadline()
                            readable, _, _ = select.select([fd], [], [], 0.2)
                            if not readable:
                                if child.poll() is not None:
                                    break
                                continue
                            try:
                                data = os.read(fd, 1024 * 1024)
                            except BlockingIOError:
                                continue
                            if not data:
                                continue
                            leading = len(data) - len(data.lstrip(b"\xcc"))
                            if cc_tail + leading >= 65536 or suspicious.search(data):
                                raise ValueError("Rejected >=64 KiB consecutive 0xCC filler; loader may restrict reads")
                            cc_tail = (cc_tail + len(data) if leading == len(data)
                                       else len(data) - len(data.rstrip(b"\xcc")))
                            total += len(data)
                            if total > expected:
                                raise ValueError(f"Read exceeded expected {expected} bytes")
                            raw_hash.update(data)
                            zipped.write(data)
                    if child.wait(timeout=max(0.1, deadline - time.monotonic())) != 0:
                        raise ValueError(f"Reader exited with status {child.returncode}; see {log}")
                finally:
                    os.close(fd)
            compressed.flush()
            os.fsync(compressed.fileno())
        if total != expected:
            raise ValueError(f"Truncated backup: expected {expected} bytes, received {total}")
        transcript = log.read_bytes()
        if b"Read LBA to file (100%)" not in transcript or re.search(b"fail|quit", transcript, re.I):
            raise ValueError(f"Reader did not report an unambiguous 100% read; see {log}")
        # Verify actual persisted gzip content, including trailer/CRC and raw hash.
        verified_hash = hashlib.sha256()
        verified_size = 0
        with gzip.open(partial, "rb") as saved:
            while data := saved.read(1024 * 1024):
                check_deadline()
                verified_hash.update(data)
                verified_size += len(data)
        if verified_size != expected or verified_hash.digest() != raw_hash.digest():
            raise ValueError("Persisted gzip verification failed")
        compressed_hash = hashlib.sha256()
        with partial.open("rb") as saved:
            while data := saved.read(1024 * 1024):
                check_deadline()
                compressed_hash.update(data)
        record = {
            "format": "gzip", "start_sector": 0, "sectors": args.sectors,
            "sector_bytes": 512, "raw_bytes": total,
            "raw_sha256": raw_hash.hexdigest(),
            "compressed_bytes": partial.stat().st_size,
            "compressed_sha256": compressed_hash.hexdigest(),
            "reader": str(tool), "reader_exit_status": child.returncode,
            "read_command": [str(tool), "rl", "0", str(args.sectors), "<temporary FIFO>"],
            "gzip_readback_verified": True, "cc_run_rejection_bytes": 65536,
            "note": "Length/hash validation does not prove all flash contents are authentic; compare independent reads.",
        }
        with manifest_partial.open("x") as saved:
            json.dump(record, saved, indent=2)
            saved.write("\n")
            saved.flush()
            os.fsync(saved.fileno())
        # Hard links publish without overwriting an output created concurrently.
        os.link(partial, output)
        partial.unlink()
        os.link(manifest_partial, manifest)
        manifest_partial.unlink()
        print(json.dumps(record, indent=2))
        print(f"Validated backup: {output}")
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--sectors", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    if not 0 < args.sectors <= 0xFFFFFFFF or args.timeout <= 0:
        parser.error("Require 1..0xffffffff sectors and positive timeout")
    try:
        backup(args)
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Backup failed: {error}\nIncomplete .partial files are retained; no validated backup was announced.\n")


if __name__ == "__main__":
    main()
