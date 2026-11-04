#!/usr/bin/env python3
"""Synthetic Frameo 159K builder/recipe regressions; never uses USB or real keys.

Run directly with Python's unittest runner. Firmware hash constants are patched
only inside these tests, and the documented recipe receives a test-only stock
hash substitution. Every rkdeveloptool call resolves to a temporary fake tool.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("frameo159k_builder", ROOT / "scripts/build-frameo159k-boot.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
BOOT_BYTES = 64 * 1024 * 1024
BOOT_LBA = 0x22000
RAMDISK_OFFSET = 0x12F5000
RAMDISK_SLOT_BYTES = 1476608
RAMDISK_LBA = 0x2B7A8
STOCK_PIN = "8ab5a0be2740c86ee6af013a9675eb6a571e0dff0967574a4657d5415b8b717e"
PROP_PIN = "7f7514955dab69a06621b85eec79c39a22af7312b1d87c9e7558dd0a57d13692"
PROPERTIES = b"# Synthetic fixture, not firmware\nro.secure=1\nro.adb.secure=1\n"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(name, data=b"", mode=0o100644, inode=1):
    fields = [inode, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0,
              len(name.encode()) + 1, 0]
    return builder.encode_newc(name, data, fields)


def synthetic_key():
    # A mathematically consistent Android RSA serialization, not a real keypair.
    modulus = (1 << 2047) | int.from_bytes(random.Random(159).randbytes(256), "little") | 1
    n0inv = (-pow(modulus & 0xFFFFFFFF, -1, 1 << 32)) & 0xFFFFFFFF
    raw = (struct.pack("<II", 64, n0inv) + modulus.to_bytes(256, "little")
           + pow(2, 4096, modulus).to_bytes(256, "little") + struct.pack("<I", 65537))
    return raw, base64.b64encode(raw) + b" synthetic-test-only\n"


def synthetic_boot():
    init = b"on property:sys.boot_completed=1\r\n    start rootservice"
    init = b"#" + b"x" * (228 - len(init) - 3) + b"\r\n" + init
    noise = random.Random(159213).randbytes(RAMDISK_SLOT_BYTES - 2200)
    archive = (record("init.root.rc", init, inode=1)
               + record("default.prop", b"system/etc/prop.default", 0o120777, 2)
               + record("unchanged.bin", noise, 0o100640, 3)
               + record("TRAILER!!!", inode=0))
    archive += b"\0" * (-len(archive) % 512)
    compressed = gzip.compress(archive, compresslevel=7, mtime=0)
    assert builder.align(len(compressed), 2048) == RAMDISK_SLOT_BYTES
    second_offset = RAMDISK_OFFSET + RAMDISK_SLOT_BYTES
    second = b"RSCE" + b"\0" * (0x1878000 - second_offset - 4)
    boot = bytearray(BOOT_BYTES)
    boot[:8] = b"ANDROID!"
    for offset, value in ((8, RAMDISK_OFFSET - 2048), (16, len(compressed)),
                          (24, len(second)), (36, 2048), (40, 0)):
        struct.pack_into("<I", boot, offset, value)
    boot[64:81] = b"buildvariant=user"
    boot[576:596] = b"synthetic-header-id!".ljust(20, b"!")
    boot[RAMDISK_OFFSET:RAMDISK_OFFSET + len(compressed)] = compressed
    boot[second_offset:second_offset + len(second)] = second
    pins = dict(SOURCE_BOOT_SHA256=digest(boot),
                SOURCE_RAMDISK_GZIP_SHA256=digest(compressed),
                SOURCE_RAMDISK_CPIO_SHA256=digest(archive),
                SOURCE_INIT_ROOT_RC_SHA256=digest(init),
                SOURCE_INIT_ROOT_RC_BYTES=len(init), SOURCE_SECOND_SHA256=digest(second),
                SOURCE_SYSTEM_DEFAULT_PROP_SHA256=digest(PROPERTIES))
    return bytes(boot), archive, pins


FAKE_RKDEVELOPTOOL = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
args = sys.argv[1:]
with open(os.environ["FAKE_RK_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
command = args[0]
lba = int(args[1], 0)
offset = (lba - 0x22000) * 512
fault = os.environ.get("FAKE_RK_FAULT", "")
is_ramdisk = lba == 0x2b7a8
if command == "rl":
    if is_ramdisk and fault == "read_error":
        sys.exit(7)
    size = int(args[2], 0) * 512
    with open(os.environ["FAKE_RK_DISK"], "rb") as disk:
        disk.seek(offset)
        data = disk.read(size)
    if is_ramdisk and fault == "read_mismatch":
        data = bytes([data[0] ^ 1]) + data[1:]
    if (is_ramdisk and fault == "read_short") or (size == 67108864 and fault == "current_short"):
        data = data[:-512]
    Path(args[3]).write_bytes(data)
elif command == "wl":
    if is_ramdisk and fault == "write_error":
        sys.exit(8)
    data = Path(args[2]).read_bytes()
    assert offset >= 0 and offset + len(data) <= 67108864
    with open(os.environ["FAKE_RK_DISK"], "r+b") as disk:
        disk.seek(offset)
        disk.write(data)
else:
    sys.exit("unexpected fake command: " + command)
'''


class SyntheticFixture:
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="frameo159k-synthetic-")
        cls.root = Path(cls.temp.name)
        cls.original, cls.archive, cls.pins = synthetic_boot()
        cls.source = cls.root / "stock.img"
        cls.source.write_bytes(cls.original)
        cls.key_raw, cls.key_line = synthetic_key()
        cls.key = cls.root / "synthetic-adbkey.pub"
        cls.key.write_bytes(cls.key_line)
        cls.properties = cls.root / "synthetic-prop.default"
        cls.properties.write_bytes(PROPERTIES)
        cls.output = cls.root / "built"
        with mock.patch.multiple(builder, **cls.pins):
            cls.manifest = builder.build(cls.source, cls.key, cls.output,
                                         system_default_prop=cls.properties)
        cls.candidate = (cls.output / "boot.img").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()


class BuilderTests(SyntheticFixture, unittest.TestCase):
    def test_production_pins_and_required_property_input(self):
        self.assertEqual(builder.SOURCE_BOOT_SHA256, STOCK_PIN)
        self.assertEqual(builder.SOURCE_SYSTEM_DEFAULT_PROP_SHA256, PROP_PIN)
        with self.assertRaises(TypeError):
            builder.build(self.source, self.key, self.root / "missing-argument")
        with self.assertRaises(FileNotFoundError):
            builder.build(self.source, self.key, self.root / "missing-file",
                          system_default_prop=self.root / "absent.properties")
        self.assertFalse((self.root / "missing-file").exists())
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build-frameo159k-boot.py"),
                                 "--source", str(self.source), "--public-key", str(self.key),
                                 "--output-dir", str(self.root / "cli-missing")],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--system-default-prop", result.stderr)
        self.assertFalse((self.root / "cli-missing").exists())

    def test_property_guards_fail_before_creating_output(self):
        cases = {
            "missing": b"ro.secure=1\n",
            "insecure": b"ro.adb.secure=0\n",
            "duplicate": b"ro.adb.secure=1\nro.adb.secure=1\n",
            "conflict": b"ro.adb.secure=1\nro.adb.secure=0\n",
            "import": b"ro.adb.secure=1\nimport /other.properties\n",
            "import_spaces": b"  import\t/other.properties\nro.adb.secure=1\n",
            "wrong_hash": PROPERTIES + b"# changed\n",
            "invalid_utf8": b"ro.adb.secure=1\n\xff",
        }
        errors = {
            "missing": "exactly one", "insecure": "require ro.adb.secure=1",
            "duplicate": "exactly one", "conflict": "exactly one",
            "import": "unresolved import", "import_spaces": "unresolved import",
            "wrong_hash": "differ from the verified firmware", "invalid_utf8": "not UTF-8",
        }
        for name, data in cases.items():
            with self.subTest(name=name):
                prop = self.root / (name + ".properties")
                prop.write_bytes(data)
                output = self.root / ("rejected-" + name)
                with mock.patch.multiple(builder, **self.pins), self.assertRaisesRegex(ValueError, errors[name]):
                    builder.build(self.source, self.key, output, system_default_prop=prop)
                self.assertFalse(output.exists())
        with mock.patch.multiple(builder, **self.pins):
            result = builder.validate_system_default_prop(PROPERTIES)
        self.assertEqual(result["ro.adb.secure"], "1")
        self.assertEqual(result["sha256"], digest(PROPERTIES))
        self.assertTrue(result["ramdisk_symlink_preserved"])

    def test_key_mode_ownership_and_preserved_archive(self):
        ramdisk_size = struct.unpack_from("<I", self.candidate, 16)[0]
        compressed = self.candidate[RAMDISK_OFFSET:RAMDISK_OFFSET + ramdisk_size]
        records, _ = builder.parse_newc(gzip.decompress(compressed))
        patched = {item["name"]: item for item in records}
        original, _ = builder.parse_newc(self.archive)
        key = patched["adb_keys"]
        self.assertEqual(key["fields"][1:4], [0o100644, 0, 0])
        self.assertEqual(key["data"], base64.b64encode(self.key_raw) + b"\n")
        for entry in original:
            if entry["name"] != "init.root.rc":
                self.assertEqual(patched[entry["name"]]["raw"], entry["raw"])
        old_init = next(item["data"] for item in original if item["name"] == "init.root.rc")
        self.assertEqual(patched["init.root.rc"]["data"], old_init + builder.ADDITION)
        self.assertEqual(self.manifest["added_files"][0]["mode"], "0100644")
        self.assertEqual(self.manifest["added_files"][0]["uid"], 0)
        self.assertEqual(self.manifest["added_files"][0]["gid"], 0)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_adb_public_key_validation(self):
        self.assertEqual(builder.validate_adb_public_key(self.key_line), base64.b64encode(self.key_raw) + b"\n")
        malformed = [b"", b"%%%", base64.b64encode(b"too short")]
        for offset in (0, 4, 8, 264, 520):
            key = bytearray(self.key_raw)
            key[offset] ^= 1
            malformed.append(base64.b64encode(key))
        key = bytearray(self.key_raw)
        key[263] &= 0x7F
        malformed.append(base64.b64encode(key))
        for index, line in enumerate(malformed):
            with self.subTest(index=index), self.assertRaises(ValueError):
                builder.validate_adb_public_key(line)

    def test_archive_validation(self):
        valid = record("example", b"data") + record("TRAILER!!!", inode=0)
        records, tail = builder.parse_newc(valid + b"\0" * 4)
        self.assertEqual([item["name"] for item in records], ["example", "TRAILER!!!"])
        self.assertEqual(tail, b"\0" * 4)
        bad_hex = bytearray(valid)
        bad_hex[6] = ord("z")
        no_nul = bytearray(valid)
        no_nul[110 + len("example")] = ord("x")
        invalid_utf8 = bytearray(valid)
        invalid_utf8[110] = 0xFF
        zero_name = bytearray(valid)
        zero_name[94:102] = b"00000000"
        malformed = [b"", b"070702" + valid[6:], bytes(bad_hex), bytes(no_nul),
                     bytes(invalid_utf8), bytes(zero_name), valid[:-1],
                     record("duplicate") + record("duplicate") + record("TRAILER!!!", inode=0)]
        for index, data in enumerate(malformed):
            with self.subTest(index=index), self.assertRaises(ValueError):
                builder.parse_newc(data)

    def test_split_payload_metadata_and_bidirectional_reconstruction(self):
        payloads, metadata = builder.split_payloads(self.original, self.candidate)
        self.assertEqual(set(payloads), {"orig_header", "new_header", "orig_ramdisk", "new_ramdisk"})
        self.assertEqual(self.manifest["format"], 2)
        self.assertEqual(self.manifest["payloads"], metadata)
        self.assertEqual(self.manifest["write_order"], ["ramdisk", "header"])
        for name, data in payloads.items():
            with self.subTest(payload=name):
                ramdisk = name.endswith("ramdisk")
                expected = dict(file=name.replace("_", "-") + ".bin",
                                lba=RAMDISK_LBA if ramdisk else BOOT_LBA,
                                sectors=2884 if ramdisk else 1,
                                bytes=RAMDISK_SLOT_BYTES if ramdisk else 512,
                                sha256=digest(data))
                self.assertEqual(metadata[name], expected)
                self.assertEqual((self.output / expected["file"]).read_bytes(), data)
        for start, prefix, expected in ((self.original, "new", self.candidate),
                                        (self.candidate, "orig", self.original)):
            restored = bytearray(start)
            restored[:512] = payloads[prefix + "_header"]
            restored[RAMDISK_OFFSET:RAMDISK_OFFSET + RAMDISK_SLOT_BYTES] = payloads[prefix + "_ramdisk"]
            self.assertEqual(restored, expected)
        self.assertEqual(digest(self.candidate), self.manifest["candidate_boot_sha256"])
        self.assertEqual(len(self.candidate), BOOT_BYTES)

    def test_split_payload_rejects_partial_or_outside_changes(self):
        for original, candidate in ((self.original[:-1], self.candidate),
                                    (self.original, self.candidate[:-512])):
            with self.subTest(lengths=(len(original), len(candidate))), self.assertRaises(ValueError):
                builder.split_payloads(original, candidate)
        for offset in (512, RAMDISK_OFFSET - 1, RAMDISK_OFFSET + RAMDISK_SLOT_BYTES, BOOT_BYTES - 1):
            candidate = bytearray(self.candidate)
            candidate[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                builder.split_payloads(self.original, bytes(candidate))


class DocumentedRecipeTests(SyntheticFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        doc = (ROOT / "docs/frameo-159k.md").read_text()
        blocks = re.findall(r"python3 - \"\$operation\" <<'PY'\n(.*?)\nPY", doc, flags=re.S)
        if len(blocks) != 1:
            raise AssertionError("expected one actual install/undo Python recipe in docs")
        if blocks[0].count(STOCK_PIN) != 1:
            raise AssertionError("recipe must retain exactly one pinned production stock hash")
        cls.recipe = blocks[0].replace(STOCK_PIN, digest(cls.original))

    def run_recipe(self, operation, fault="", mutate=None):
        with tempfile.TemporaryDirectory(prefix="frameo159k-recipe-") as folder:
            root = Path(folder)
            output = root / "diagnostics/frameo-159k/boot-patched-review"
            output.mkdir(parents=True)
            stock = output.parent / "boot-stock-read1.img"
            stock.symlink_to(self.source)
            for path in self.output.iterdir():
                if path.name == "manifest.json":
                    shutil.copyfile(path, output / path.name)
                else:
                    (output / path.name).symlink_to(path)
            disk = root / "fake-disk.img"
            shutil.copyfile(self.source if operation == "install" else self.output / "boot.img", disk)
            if mutate:
                mutate(output, disk)
            fakebin = root / "fake-bin"
            fakebin.mkdir()
            fake = fakebin / "rkdeveloptool"
            # Absolute interpreter prevents reliance on any installed rkdeveloptool.
            fake.write_text("#!" + sys.executable + "\n" + FAKE_RKDEVELOPTOOL.split("\n", 1)[1])
            fake.chmod(0o755)
            log = root / "calls.jsonl"
            environment = dict(os.environ, PATH=str(fakebin) + os.pathsep + os.environ.get("PATH", ""),
                               FAKE_RK_DISK=str(disk), FAKE_RK_LOG=str(log), FAKE_RK_FAULT=fault)
            result = subprocess.run([sys.executable, "-", operation], input=self.recipe, text=True,
                                    capture_output=True, cwd=root, env=environment, timeout=60)
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            final_hash = digest(disk.read_bytes())
            return result, calls, final_hash

    def test_recipe_install_and_undo_verify_ramdisk_before_header(self):
        for operation, expected in (("install", self.candidate), ("undo", self.original)):
            with self.subTest(operation=operation):
                result, calls, final_hash = self.run_recipe(operation)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(final_hash, digest(expected))
                writes = [(i, int(call[1], 0)) for i, call in enumerate(calls) if call[0] == "wl"]
                self.assertEqual([lba for _, lba in writes], [RAMDISK_LBA, BOOT_LBA])
                first, header = writes[0][0], writes[1][0]
                self.assertTrue(any(call[0] == "rl" and int(call[1], 0) == RAMDISK_LBA
                                    and int(call[2], 0) == 2884 for call in calls[first + 1:header]))
                self.assertTrue(any(call[0] == "rl" and int(call[1], 0) == BOOT_LBA
                                    and int(call[2], 0) == 131072 for call in calls[header + 1:]))

    def test_recipe_withholds_header_after_ramdisk_failure(self):
        for operation in ("install", "undo"):
            for fault in ("write_error", "read_error", "read_mismatch", "read_short"):
                with self.subTest(operation=operation, fault=fault):
                    result, calls, _ = self.run_recipe(operation, fault)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    writes = [int(call[1], 0) for call in calls if call[0] == "wl"]
                    self.assertEqual(writes, [RAMDISK_LBA])

    def test_recipe_rejects_unknown_or_short_current_image_without_writes(self):
        def unknown_current(output, disk):
            with disk.open("r+b") as stream:
                stream.seek(4096)
                stream.write(b"unknown-device-state")
        for operation in ("install", "undo"):
            for fault, mutation in (("", unknown_current), ("current_short", None)):
                with self.subTest(operation=operation, fault=fault):
                    result, calls, _ = self.run_recipe(operation, fault, mutation)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertFalse([call for call in calls if call[0] == "wl"])

    def test_recipe_rejects_corrupt_payloads_and_bounds_without_writes(self):
        def corrupt(output, disk):
            manifest = json.loads((output / "manifest.json").read_text())
            path = output / manifest["payloads"]["new_ramdisk"]["file"]
            data = path.read_bytes()
            path.unlink()  # Never mutate the shared fixture through its symlink.
            path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
        def wrong_bounds(output, disk):
            path = output / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["payloads"]["orig_ramdisk"]["lba"] += 1
            path.write_text(json.dumps(manifest))
        for operation in ("install", "undo"):
            for mutation in (corrupt, wrong_bounds):
                with self.subTest(operation=operation, mutation=mutation.__name__):
                    result, calls, _ = self.run_recipe(operation, mutate=mutation)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertFalse([call for call in calls if call[0] == "wl"])


if __name__ == "__main__":
    unittest.main()
