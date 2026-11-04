#!/usr/bin/env python3
"""Offline-only guarded boot-ramdisk builder for the Frameo 159K (RK3326).

This script does not touch USB, the network, or flash. It takes the
verified 64 MiB `boot` partition, adds only the supplied ADB public key
and the boot-time TCP ADB trigger, and writes a candidate image, split
write/undo payloads and manifest to a new directory. It also requires
the pinned /system/etc/prop.default from the matching backup to verify
ro.adb.secure=1; the ramdisk contains only a symlink to that file.
The patch enables adbd on TCP 5555 at
boot-completed and leaves the USB configuration untouched.

The 159K boot image is Android header v0 with a 2 KiB page size. Its
second stage is a 4.3 MiB `RSCE` payload, not an Android recovery DTBO.
The original header ID does not match Android's legacy SHA-1 algorithm,
so this builder deliberately preserves it instead of rewriting it. The
kernel, `RSCE` second stage, cmdline, header fields other than
`ramdisk_size`, and the zero partition tail are preserved byte-for-byte.
The new gzip is required to remain in the same 2 KiB-aligned slot as the
stock ramdisk, so the `RSCE` offset does not move.

Usage:
    python3 scripts/build-frameo159k-boot.py \
        --source diagnostics/frameo-159k/boot-stock-read1.img \
        --public-key ~/.android/adbkey.pub \
        --system-default-prop diagnostics/frameo-159k/system-prop.default \
        --output-dir diagnostics/frameo-159k/boot-patched-review
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import struct
from pathlib import Path


SOURCE_BOOT_SHA256 = "8ab5a0be2740c86ee6af013a9675eb6a571e0dff0967574a4657d5415b8b717e"
SOURCE_RAMDISK_GZIP_SHA256 = "6f83c822fbe421e74e73c32e51671986a18a4eb3d05310b514c30c1a5319b4ca"
SOURCE_RAMDISK_CPIO_SHA256 = "8b46b9f21298f4743444d438545914998cf59c4f5e2a1ea0f20f588270ed0399"
SOURCE_INIT_ROOT_RC_SHA256 = "8a426c259b5051ac08c832cc3d91a8f78cd27bb8843e9e516a4e2a853ffc0323"
SOURCE_INIT_ROOT_RC_BYTES = 228
SOURCE_SECOND_SHA256 = "f858c17f67a1fee5c4ee973606b901ea2beeea87ff2b8a58f6ab394071362cf1"
SOURCE_SYSTEM_DEFAULT_PROP_SHA256 = "7f7514955dab69a06621b85eec79c39a22af7312b1d87c9e7558dd0a57d13692"

BOOT_BYTES = 64 * 1024 * 1024
BOOT_LBA = 0x22000
SECTOR_BYTES = 512
RAMDISK_OFFSET = 0x12F5000
RAMDISK_SLOT_BYTES = 1476608
PAGE_SIZE = 2048
CPIO_MAGIC = b"070701"
ADDITION = (
    b"\r\n"
    b"    setprop service.adb.tcp.port 5555\r\n"
    b"    restart adbd\r\n"
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def align(value: int, unit: int) -> int:
    return (value + unit - 1) // unit * unit


def parse_newc(data: bytes) -> tuple[list[dict], bytes]:
    """Parse newc while preserving each original record verbatim."""
    records: list[dict] = []
    files: set[str] = set()
    pos = 0
    while True:
        start = pos
        require(len(data) - pos >= 110 and data[pos:pos + 6] == CPIO_MAGIC,
                "ramdisk is not a complete newc archive")
        try:
            fields = [int(data[pos + 6 + i * 8:pos + 14 + i * 8], 16) for i in range(13)]
        except ValueError as exc:
            raise ValueError("invalid newc header field") from exc
        name_size, file_size = fields[11], fields[6]
        name_start = pos + 110
        name_end = name_start + name_size
        require(name_size >= 1 and name_end <= len(data) and data[name_end - 1] == 0,
                "invalid newc filename length")
        try:
            name = data[name_start:name_end - 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("newc filename is not UTF-8") from exc
        data_start = align(name_end, 4)
        data_end = data_start + file_size
        next_pos = align(data_end, 4)
        require(next_pos <= len(data), f"truncated newc entry: {name}")
        if name != "TRAILER!!!":
            require(name not in files, f"duplicate ramdisk path: {name}")
            files.add(name)
        records.append({
            "name": name,
            "fields": fields,
            "data": data[data_start:data_end],
            "raw": data[start:next_pos],
        })
        pos = next_pos
        if name == "TRAILER!!!":
            return records, data[pos:]


def encode_newc(name: str, data: bytes, fields: list[int]) -> bytes:
    fields = fields[:]
    fields[6] = len(data)
    header = CPIO_MAGIC + b"".join(f"{value:08x}".encode("ascii") for value in fields)
    name_bytes = name.encode("utf-8") + b"\0"
    body = header + name_bytes
    body += b"\0" * (-len(body) % 4)
    body += data
    body += b"\0" * (-len(body) % 4)
    return body


def validate_adb_public_key(line: bytes) -> bytes:
    """Return the canonical ADB RSA key line with its comment removed."""
    tokens = line.strip().split()
    require(bool(tokens), "ADB public-key file is empty")
    try:
        key = base64.b64decode(tokens[0], validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("ADB public key is not valid base64") from exc
    require(len(key) == 524 and struct.unpack_from("<I", key)[0] == 64,
            "expected a 2048-bit Android ADB RSA public key")
    n0inv = struct.unpack_from("<I", key, 4)[0]
    modulus = int.from_bytes(key[8:264], "little")
    rr = int.from_bytes(key[264:520], "little")
    exponent = struct.unpack_from("<I", key, 520)[0]
    require(modulus.bit_length() == 2048 and modulus % 2 == 1 and exponent == 65537,
            "ADB RSA key modulus or exponent is invalid")
    require(((n0inv * (modulus & 0xFFFFFFFF)) + 1) & 0xFFFFFFFF == 0,
            "ADB RSA key Montgomery inverse is invalid")
    require(rr == pow(2, 4096, modulus),
            "ADB RSA key Montgomery residue is invalid")
    return tokens[0] + b"\n"


def validate_system_default_prop(data: bytes) -> dict:
    """Verify the pinned system properties without changing the boot symlink."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("system default properties are not UTF-8") from exc
    secure_values: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        require(line.split()[0] != "import",
                "system default properties contain an unresolved import")
        if "=" in line:
            name, value = line.split("=", 1)
            if name.strip() == "ro.adb.secure":
                secure_values.append(value.strip())
    require(len(secure_values) == 1,
            "system default properties must contain exactly one ro.adb.secure assignment")
    require(secure_values[0] == "1", "system default properties require ro.adb.secure=1")
    require(sha256(data) == SOURCE_SYSTEM_DEFAULT_PROP_SHA256,
            "system default properties differ from the verified firmware")
    return {
        "path": "/system/etc/prop.default",
        "sha256": sha256(data),
        "bytes": len(data),
        "ro.adb.secure": "1",
        "ramdisk_symlink_preserved": True,
    }


def split_payloads(original: bytes, candidate: bytes) -> tuple[dict[str, bytes], dict]:
    """Return fixed-sector payloads that exactly reconstruct candidate and stock."""
    require(len(original) == len(candidate) == BOOT_BYTES,
            "split payloads require complete boot partitions")
    end = RAMDISK_OFFSET + RAMDISK_SLOT_BYTES
    require(candidate[SECTOR_BYTES:RAMDISK_OFFSET] == original[SECTOR_BYTES:RAMDISK_OFFSET]
            and candidate[end:] == original[end:],
            "candidate changes bytes outside the header sector and ramdisk slot")
    payloads = {
        "orig_header": original[:SECTOR_BYTES],
        "new_header": candidate[:SECTOR_BYTES],
        "orig_ramdisk": original[RAMDISK_OFFSET:end],
        "new_ramdisk": candidate[RAMDISK_OFFSET:end],
    }
    metadata = {}
    for name, data in payloads.items():
        offset = RAMDISK_OFFSET if name.endswith("ramdisk") else 0
        expected_size = RAMDISK_SLOT_BYTES if offset else SECTOR_BYTES
        require(len(data) == expected_size and len(data) % SECTOR_BYTES == 0,
                f"invalid split payload size: {name}")
        metadata[name] = {
            "file": name.replace("_", "-") + ".bin",
            "lba": BOOT_LBA + offset // SECTOR_BYTES,
            "sectors": len(data) // SECTOR_BYTES,
            "bytes": len(data),
            "sha256": sha256(data),
        }
    for start, prefix, expected in ((original, "new", candidate), (candidate, "orig", original)):
        rebuilt = bytearray(start)
        rebuilt[RAMDISK_OFFSET:end] = payloads[f"{prefix}_ramdisk"]
        rebuilt[:SECTOR_BYTES] = payloads[f"{prefix}_header"]
        require(rebuilt == expected, f"split {prefix} payloads failed reconstruction")
    return payloads, metadata


def build(source: Path, public_key: Path, output_dir: Path, *, system_default_prop: Path) -> dict:
    require(not output_dir.exists(), "output directory already exists")
    system_properties = validate_system_default_prop(system_default_prop.read_bytes())
    original = source.read_bytes()
    require(len(original) == BOOT_BYTES and sha256(original) == SOURCE_BOOT_SHA256,
            "source is not the verified Frameo 159K boot partition")
    require(original[:8] == b"ANDROID!", "source does not start with ANDROID!")
    kernel_size, ramdisk_size, second_size, page, header_version = (
        struct.unpack_from("<I", original, 8)[0],
        struct.unpack_from("<I", original, 16)[0],
        struct.unpack_from("<I", original, 24)[0],
        struct.unpack_from("<I", original, 36)[0],
        struct.unpack_from("<I", original, 40)[0],
    )
    require(page == PAGE_SIZE and header_version == 0,
            "source page size or header version differs from the verified image")
    require(second_size > 0, "source has no RSCE second stage")
    kernel_offset = page
    ramdisk_offset = kernel_offset + align(kernel_size, page)
    second_offset = ramdisk_offset + align(ramdisk_size, page)
    ramdisk_slot = align(ramdisk_size, page)
    image_end = second_offset + align(second_size, page)
    require(ramdisk_offset == RAMDISK_OFFSET and second_offset == 0x145D800,
            "source component offsets differ from the verified image")
    require(ramdisk_slot == RAMDISK_SLOT_BYTES, "source ramdisk slot size differs")
    require(image_end == 0x1878000, "source image end differs from the verified image")
    require(second_offset + second_size <= BOOT_BYTES, "source components exceed the partition")

    kernel = original[kernel_offset:kernel_offset + kernel_size]
    second = original[second_offset:second_offset + second_size]
    require(sha256(second) == SOURCE_SECOND_SHA256,
            "RSCE second stage hash differs from the verified image")
    require(second[:4] == b"RSCE", "second stage is not RSCE")
    require(all(byte == 0 for byte in original[image_end:]),
            "source partition tail is not zero-filled")
    require(original.count(b"AVB0") == 0 and original[-64:-60] != b"AVBf",
            "source unexpectedly contains Android Verified Boot data")

    compressed = original[ramdisk_offset:ramdisk_offset + ramdisk_size]
    require(sha256(compressed) == SOURCE_RAMDISK_GZIP_SHA256,
            "source ramdisk gzip hash differs from the verified image")
    try:
        ramdisk = gzip.decompress(compressed)
    except (OSError, EOFError) as exc:
        raise ValueError("source ramdisk is not a complete gzip stream") from exc
    require(sha256(ramdisk) == SOURCE_RAMDISK_CPIO_SHA256,
            "source ramdisk CPIO hash differs from the verified image")

    records, trailer = parse_newc(ramdisk)
    require(records[-1]["name"] == "TRAILER!!!", "source CPIO has no trailer")
    require(len({record["name"] for record in records}) == len(records),
            "source CPIO contains duplicate names")
    by_name = {record["name"]: record for record in records}
    default_prop = by_name.get("default.prop")
    require(default_prop is not None
            and default_prop["fields"][1] & 0o170000 == 0o120000
            and default_prop["data"] == b"system/etc/prop.default",
            "source default.prop is not the expected system property symlink")
    require("adb_keys" not in by_name, "source ramdisk already contains adb_keys")
    require("init.root.rc" in by_name, "source ramdisk is missing init.root.rc")
    init_record = by_name["init.root.rc"]
    init_data = init_record["data"]
    require(len(init_data) == SOURCE_INIT_ROOT_RC_BYTES
            and sha256(init_data) == SOURCE_INIT_ROOT_RC_SHA256,
            "source init.root.rc differs from the verified image")
    require(init_data.endswith(b"start rootservice"),
            "source init.root.rc does not end at the expected boot trigger")
    require(b"setprop service.adb.tcp.port" not in init_data,
            "source init.root.rc already contains an ADB trigger")

    key_line = validate_adb_public_key(public_key.read_bytes())
    new_init = init_data + ADDITION
    require(new_init.count(b"\n") == init_data.count(b"\n") + 3,
            "unexpected line count in the modified init.root.rc")

    inode = max(record["fields"][0] for record in records if record["name"] != "TRAILER!!!") + 1
    key_fields = [
        inode, 0o100644, 0, 0, 1, 0, len(key_line), 0, 0, 0, 0,
        len(b"adb_keys\0"), 0,
    ]
    output_records: list[bytes] = []
    for record in records:
        if record["name"] == "TRAILER!!!":
            output_records.append(encode_newc("adb_keys", key_line, key_fields))
            output_records.append(record["raw"])
        elif record["name"] == "init.root.rc":
            output_records.append(encode_newc(record["name"], new_init, record["fields"]))
        else:
            output_records.append(record["raw"])
    new_ramdisk = b"".join(output_records) + trailer
    new_ramdisk += b"\0" * (-len(new_ramdisk) % 512)
    require(gzip.decompress(gzip.compress(new_ramdisk, compresslevel=7, mtime=0)) == new_ramdisk,
            "patched ramdisk failed gzip round-trip validation")
    new_gzip = gzip.compress(new_ramdisk, compresslevel=7, mtime=0)
    require(align(len(new_gzip), PAGE_SIZE) == ramdisk_slot,
            "patched ramdisk no longer occupies the original 2 KiB-aligned slot")
    require(len(new_gzip) <= ramdisk_slot, "patched ramdisk exceeds the original slot")

    candidate = bytearray(original)
    struct.pack_into("<I", candidate, 16, len(new_gzip))
    candidate[ramdisk_offset:ramdisk_offset + ramdisk_slot] = (
        new_gzip + b"\0" * (ramdisk_slot - len(new_gzip))
    )

    # The legacy header ID is deliberately preserved: the stock ID does not
    # match Android's legacy SHA-1 algorithm, and no AVB footer is present.
    require(candidate[:16] == original[:16], "header prefix changed unexpectedly")
    require(candidate[20:ramdisk_offset] == original[20:ramdisk_offset],
            "header or kernel changed unexpectedly")
    require(candidate[576:608] == original[576:608], "legacy header ID changed")
    require(candidate[ramdisk_offset + ramdisk_slot:] == original[ramdisk_offset + ramdisk_slot:],
            "bytes after the ramdisk slot changed unexpectedly")
    require(candidate[second_offset:second_offset + second_size] == second,
            "RSCE second stage changed unexpectedly")
    require(candidate[second_offset + second_size:] == b"\0" * (BOOT_BYTES - (second_offset + second_size)),
            "candidate partition tail is not zero-filled")
    require(len(candidate) == BOOT_BYTES, "candidate size differs from the boot partition")

    verified_records, _ = parse_newc(gzip.decompress(candidate[ramdisk_offset:ramdisk_offset + len(new_gzip)]))
    verified = {record["name"]: record for record in verified_records}
    require(len(verified) == len(records) + 1, "unexpected patched CPIO entry count")
    for record in records:
        if record["name"] in ("init.root.rc", "TRAILER!!!"):
            continue
        require(verified[record["name"]]["raw"] == record["raw"],
                f"original CPIO entry changed: {record['name']}")
    require(verified["init.root.rc"]["data"] == new_init,
            "patched init.root.rc did not verify")
    require(verified["adb_keys"]["data"] == key_line,
            "patched adb_keys did not verify")
    require(verified["adb_keys"]["fields"][1] == 0o100644
            and verified["adb_keys"]["fields"][2] == 0
            and verified["adb_keys"]["fields"][3] == 0,
            "patched adb_keys ownership or mode is wrong")
    require(verified["TRAILER!!!"]["raw"] == by_name["TRAILER!!!"]["raw"],
            "patched CPIO trailer changed")

    payloads, payload_metadata = split_payloads(original, bytes(candidate))
    manifest = {
        "format": 2,
        "device": "Frameo Digital Photo Frame 159K / RK3326 / RK3326_8.1_AY_FRAMEO_202605131837",
        "status": "BUILT_VERIFIED_OFFLINE_NOT_FLASHED_NOT_BOOTED",
        "source_boot_sha256": SOURCE_BOOT_SHA256,
        "candidate_boot_sha256": sha256(bytes(candidate)),
        "source_boot_bytes": len(original),
        "candidate_boot_bytes": len(candidate),
        "page_size": PAGE_SIZE,
        "system_default_prop": system_properties,
        "payloads": payload_metadata,
        "write_order": ["ramdisk", "header"],
        "kernel": {
            "offset": kernel_offset,
            "bytes": kernel_size,
            "sha256": sha256(kernel),
        },
        "ramdisk": {
            "offset": ramdisk_offset,
            "slot_bytes": ramdisk_slot,
            "old_compressed_bytes": ramdisk_size,
            "new_compressed_bytes": len(new_gzip),
            "old_cpio_sha256": SOURCE_RAMDISK_CPIO_SHA256,
            "new_cpio_sha256": sha256(new_ramdisk),
            "new_cpio_bytes": len(new_ramdisk),
            "gzip_level": 7,
        },
        "second_rsce": {
            "offset": second_offset,
            "bytes": second_size,
            "sha256": SOURCE_SECOND_SHA256,
            "relocated": False,
        },
        "header": {
            "header_version": header_version,
            "cmdline": original[64:576].split(b"\0")[0].decode("ascii", "replace"),
            "os_version": f"0x{struct.unpack_from('<I', original, 44)[0]:08x}",
            "id_preserved": True,
            "id_hex": original[576:596].hex(),
            "only_changed_field": "ramdisk_size at offset 16",
        },
        "changed_ramdisk_paths": ["init.root.rc", "adb_keys"],
        "added_files": [{
            "path": "adb_keys",
            "bytes": len(key_line),
            "sha256": sha256(key_line),
            "uid": 0,
            "gid": 0,
            "mode": "0100644",
            "comment_stripped": True,
        }],
        "modified_files": [{
            "path": "init.root.rc",
            "old_bytes": len(init_data),
            "new_bytes": len(new_init),
            "old_sha256": SOURCE_INIT_ROOT_RC_SHA256,
            "new_sha256": sha256(new_init),
            "appended": "service.adb.tcp.port=5555; restart adbd",
        }],
        "preserved": [
            "kernel",
            "RSCE second stage and its offset",
            "cmdline",
            "os_version, addresses, page size and legacy header ID",
            "all other CPIO entries and their metadata",
            "zero partition tail",
            "USB configuration untouched",
        ],
        "adb_authentication": (
            "pinned system default properties verify ro.adb.secure=1; supplied public key added; "
            "existing userdata authorizations untouched"
        ),
        "caveats": [
            "The stock header ID is deliberately preserved and is not a signature.",
            "This candidate has not been flashed or booted; bootloader acceptance is unproven.",
            "The patch adds no su binary; root is expected from the shipped SuperSU su and rootservice/daemonsu startup.",
            "TCP ADB starts on all interfaces after every boot; an authorized session can obtain root through shipped su. Unknown-key rejection is untested.",
            "Split writes are not atomic; a failed write requires reviewed Loader recovery, not a reset.",
            "Flashing requires separate approval and a verified stock-boot rollback.",
        ],
    }

    output_dir.mkdir(parents=True)
    outputs = {"boot.img": bytes(candidate)}
    outputs.update({payload_metadata[name]["file"]: data for name, data in payloads.items()})
    for filename, data in outputs.items():
        destination = output_dir / filename
        destination.write_bytes(data)
        require(destination.read_bytes() == data, f"output readback failed: {filename}")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--system-default-prop", required=True, type=Path,
                        help="pinned /system/etc/prop.default from the matching verified backup")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = build(args.source, args.public_key, args.output_dir,
                         system_default_prop=args.system_default_prop)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "status": manifest["status"],
        "candidate_boot_sha256": manifest["candidate_boot_sha256"],
        "candidate_boot_bytes": manifest["candidate_boot_bytes"],
        "ramdisk": manifest["ramdisk"],
        "payloads": manifest["payloads"],
        "system_default_prop": manifest["system_default_prop"],
        "second_rsce": manifest["second_rsce"],
        "changed_ramdisk_paths": manifest["changed_ramdisk_paths"],
    }, indent=2))


if __name__ == "__main__":
    main()
