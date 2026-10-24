#!/usr/bin/env python3
"""Synthetic checks for load-usb-reader.py's idbloader and GPT parsing; never contacts USB."""

import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

spec = importlib.util.spec_from_file_location("load_usb_reader",
                                              Path(__file__).with_name("load-usb-reader.py"))
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)

DDR = bytes(range(256)) * 232  # 116 sectors, like the real DDR stage
SPL = bytes([0x5A]) * (472 * 512)


def idbloader(magic=b"RKNS", hash_type=1):
    header = bytearray(2048)
    header[:4] = magic
    struct.pack_into("<II", header, 8, (2 << 16) | 384, hash_type)
    offset = 4
    for i, image in enumerate((DDR, SPL)):
        entry = 0x78 + i * 88
        struct.pack_into("<IIII", header, entry, (len(image) // 512) << 16 | offset, 0xFFFFFFFF, 0, i + 1)
        header[entry + 0x18:entry + 0x38] = hashlib.sha256(image).digest()
        offset += len(image) // 512
    header[0x600:0x620] = hashlib.sha256(header[:0x600]).digest()
    return bytes(header) + DDR + SPL


def first_32mib(sectors=30785536, idb=None, second=None):
    disk = bytearray(32 * 1024 * 1024)
    entries = bytearray(128 * 128)
    entries[:16] = b"\x01" * 16
    header = bytearray(92)
    header[:8] = b"EFI PART"
    struct.pack_into("<IIII", header, 8, 0x10000, 92, 0, 0)
    struct.pack_into("<QQQQ", header, 24, 1, sectors - 1, 34, sectors - 34)
    struct.pack_into("<QIII", header, 72, 2, 128, 128, zlib.crc32(entries))
    struct.pack_into("<I", header, 16, zlib.crc32(header))
    disk[512:604] = header
    disk[1024:1024 + len(entries)] = entries
    idb = idbloader() if idb is None else idb
    disk[0x8000:0x8000 + len(idb)] = idb
    second = idb if second is None else second
    disk[0x88000:0x88000 + len(second)] = second
    return disk


class FrameDdrTests(unittest.TestCase):
    def test_good(self):
        disk = first_32mib()
        self.assertEqual(loader.frame_ddr(disk), DDR)
        self.assertEqual(loader.gpt_sector_count(disk), 30785536)

    def test_rejects(self):
        bad_image = bytearray(idbloader())
        bad_image[2048 + 100] ^= 1
        bad_header = bytearray(idbloader())
        bad_header[0x40] ^= 1
        other = bytearray(idbloader())
        other[2048 + 100] ^= 1
        other[0x78 + 0x18:0x78 + 0x38] = hashlib.sha256(bytes(other[2048:2048 + len(DDR)])).digest()
        other[0x600:0x620] = hashlib.sha256(bytes(other[:0x600])).digest()
        cases = {
            "image hash": first_32mib(idb=bytes(bad_image)),
            "header hash": first_32mib(idb=bytes(bad_header)),
            "signed": first_32mib(idb=idbloader(magic=b"RKSS")),
            "no v2 header": first_32mib(idb=bytes(4096)),
            "sha512": first_32mib(idb=idbloader(hash_type=2)),
            "copies differ": first_32mib(second=bytes(other)),
        }
        for name, disk in cases.items():
            with self.subTest(name), self.assertRaises(RuntimeError):
                loader.frame_ddr(disk)

    def test_gpt_rejects(self):
        crc = first_32mib()
        crc[512 + 40] ^= 1  # first usable LBA, covered by the header CRC
        entries = first_32mib()
        entries[1024] ^= 1
        for name, disk in {"header crc": crc, "entry crc": entries,
                           "no gpt": bytearray(32 * 1024 * 1024)}.items():
            with self.subTest(name), self.assertRaises(RuntimeError):
                loader.gpt_sector_count(disk)


if __name__ == "__main__":
    unittest.main()
