"""Fake-file tests: never accesses a disk device or invokes diskutil."""

import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zlib

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("pf1006_card", HERE / "card-macos.py")
CARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CARD)
SOURCE_ROOT = CARD.ROOT
RUN_ID = "0123456789abcdef0123456789abcdef"
CARD_BYTES = 32000000000


def legacy_script(source):
    payload = struct.pack(">II", len(source), 0) + source
    header = bytearray(64)
    struct.pack_into(">7I", header, 0, 0x27051956, 0, 0, len(payload), 0, 0, zlib.crc32(payload))
    header[28:32] = bytes((5, 2, 6, 0))
    struct.pack_into(">I", header, 4, zlib.crc32(header))
    return bytes(header) + payload


def with_egon_checksum(data, length=None):
    image = bytearray(data)
    if length is None:
        length = len(image)
    struct.pack_into("<I", image, 0, 0xea000016)
    struct.pack_into("<II", image, 12, 0x5f0a6c39, length)
    total = sum(struct.unpack_from("<I", image, offset)[0] for offset in range(0, length, 4))
    struct.pack_into("<I", image, 12, total & 0xffffffff)
    return bytes(image)


def blank_prefix():
    before = bytearray(CARD.CARD_IO.PREFIX)
    before[510:512] = b"\x55\xaa"
    before[450] = 0x0c
    struct.pack_into("<II", before, 454, 32768, 60000000)
    return bytes(before)


def disk_info():
    return {
        "MediaName": "Synthetic SD card", "TotalSize": CARD_BYTES, "DeviceBlockSize": 512,
        "Internal": False, "WholeDisk": True, "RemovableMedia": True, "BusProtocol": "USB",
        "VirtualOrPhysical": "Physical", "DeviceTreePath": "synthetic-slot",
        "Content": "FDisk_partition_scheme", "Writable": True,
    }


class CardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.here = self.root / "scripts/pf1006-probe"
        self.here.mkdir(parents=True)
        upstream = self.root / "scripts/a33-sdboot"
        upstream.mkdir()
        for name in ("probe.cmd.in", "pf1006.config"):
            (self.here / name).write_bytes((HERE / name).read_bytes())
        (upstream / "pf1006-readonly.patch").write_bytes(
            (SOURCE_ROOT / "scripts/a33-sdboot/pf1006-readonly.patch").read_bytes())
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(CARD, "ROOT", self.root).start()
        mock.patch.object(CARD, "HERE", self.here).start()
        # An accidental diskutil invocation or absolute raw device open is a bug.
        self.diskutil = mock.patch.object(CARD, "diskutil", side_effect=AssertionError("No diskutil in tests")).start()
        self.build_dir = self.root / "build" / RUN_ID
        self.build_dir.mkdir(parents=True)
        source = (self.here / "probe.cmd.in").read_bytes()
        rendered = source.replace(b"@RUN_ID@", RUN_ID.encode())
        image = bytearray(16384)
        image[4:12] = b"eGON.BT0"
        markers = b"\0".join(CARD.MARKERS) + b"\0"
        image[1024:1024 + len(markers)] = markers
        self.files = {
            "u-boot-sunxi-with-spl.bin": with_egon_checksum(image),
            "pf1006-probe.cmd": rendered, "pf1006-probe.scr": legacy_script(rendered),
            "run-id.txt": (RUN_ID + "\n").encode(), "probe.cmd.in": source,
            "pf1006.config": (self.here / "pf1006.config").read_bytes(),
            "u-boot.config": (self.here / "pf1006.config").read_bytes(),
            "pf1006-readonly.patch": (upstream / "pf1006-readonly.patch").read_bytes(),
        }
        self.write_build()

    def write_build(self):
        artifacts = {}
        for name, data in self.files.items():
            (self.build_dir / name).write_bytes(data)
            artifacts[name] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        manifest = {"format": 1, "experimental": True, "hardware_tested": False,
                    "u_boot_commit": CARD.PIN, "min_ram_bytes": 0x10000000,
                    "text_base": "0x4a000000", "run_id": RUN_ID, "artifacts": artifacts}
        (self.build_dir / "build.json").write_text(json.dumps(manifest))
        (self.build_dir / "SHA256SUMS").write_text("".join(
            "{}  {}\n".format(artifacts[name]["sha256"], name) for name in sorted(artifacts)))

    def test_valid_build_contract(self):
        self.assertEqual(CARD.load_artifacts(self.build_dir)["run_id"], RUN_ID)

    def test_artifact_tamper_is_rejected(self):
        path = self.build_dir / "pf1006-probe.scr"
        path.write_bytes(path.read_bytes()[:-1] + b"x")
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            CARD.load_artifacts(self.build_dir)

    def test_rehashed_wrong_script_rejected(self):
        self.files["pf1006-probe.scr"] = legacy_script(b"mmc write 42000000 0 2000\n")
        self.write_build()
        with self.assertRaisesRegex(RuntimeError, "Compiled script"):
            CARD.load_artifacts(self.build_dir)

    def test_generic_script_is_rejected(self):
        (self.build_dir / "a33.scr").write_bytes(b"old writer")
        with self.assertRaisesRegex(RuntimeError, "Generic a33.scr"):
            CARD.load_artifacts(self.build_dir)

    def test_unreviewed_source_rejected_even_with_consistent_hashes(self):
        self.files["pf1006-readonly.patch"] += b"\n# local change\n"
        self.write_build()
        with self.assertRaisesRegex(RuntimeError, "reviewed source"):
            CARD.load_artifacts(self.build_dir)

    def test_missing_binary_guard_rejected(self):
        self.files["u-boot-sunxi-with-spl.bin"] = with_egon_checksum(
            self.files["u-boot-sunxi-with-spl.bin"].replace(CARD.MARKERS[0], b"x" * len(CARD.MARKERS[0])))
        self.write_build()
        with self.assertRaisesRegex(RuntimeError, "markers absent"):
            CARD.load_artifacts(self.build_dir)

    def test_rehashed_corrupt_spl_checksum_is_rejected(self):
        image = bytearray(self.files["u-boot-sunxi-with-spl.bin"])
        image[4096] ^= 1
        self.files["u-boot-sunxi-with-spl.bin"] = bytes(image)
        self.write_build()  # outer SHA-256 matches; the independent SPL checksum does not
        with self.assertRaisesRegex(RuntimeError, "eGON SPL checksum mismatch"):
            CARD.load_artifacts(self.build_dir)

    def test_invalid_declared_spl_lengths(self):
        original = self.files["u-boot-sunxi-with-spl.bin"]
        for length in (0, 64, 513, len(original) + 512):
            with self.subTest(length=length):
                image = bytearray(original)
                struct.pack_into("<I", image, 16, length)
                self.files["u-boot-sunxi-with-spl.bin"] = bytes(image)
                self.write_build()
                with self.assertRaisesRegex(RuntimeError, "Invalid declared SPL length"):
                    CARD.load_artifacts(self.build_dir)

    def test_big_endian_header_fields_are_rejected(self):
        original = self.files["u-boot-sunxi-with-spl.bin"]
        for offset, message in ((12, "checksum mismatch"), (16, "declared SPL length")):
            with self.subTest(offset=offset):
                image = bytearray(original)
                value = struct.unpack_from("<I", image, offset)[0]
                struct.pack_into(">I", image, offset, value)
                self.files["u-boot-sunxi-with-spl.bin"] = bytes(image)
                self.write_build()
                with self.assertRaisesRegex(RuntimeError, message):
                    CARD.load_artifacts(self.build_dir)

    def test_spl_checksum_excludes_appended_uboot_proper(self):
        image = self.files["u-boot-sunxi-with-spl.bin"]
        self.assertEqual(CARD.check_egon(image + b"UBOOT-PROPER"), len(image))

    def test_short_header_and_wrong_branch(self):
        with self.assertRaisesRegex(RuntimeError, "Short eGON"):
            CARD.check_egon(b"\0" * 20)
        image = bytearray(self.files["u-boot-sunxi-with-spl.bin"])
        image[:4] = b"\0" * 4
        with self.assertRaisesRegex(RuntimeError, "ARM eGON branch"):
            CARD.check_egon(image)

    def test_resolved_unsafe_config_rejected(self):
        self.files["u-boot.config"] += b"\nCONFIG_ENV_IS_IN_MMC=y\n"
        self.write_build()
        with self.assertRaisesRegex(RuntimeError, "Forbidden config"):
            CARD.load_artifacts(self.build_dir)

    def test_oversized_boot_image_rejected(self):
        data = self.files["u-boot-sunxi-with-spl.bin"]
        self.files["u-boot-sunxi-with-spl.bin"] = data + bytes(1024 * 1024 - len(data))
        self.write_build()
        with self.assertRaisesRegex(RuntimeError, "1 MiB boot-area"):
            CARD.load_artifacts(self.build_dir)

    def test_symlink_artifact_rejected(self):
        path = self.build_dir / "run-id.txt"
        content = path.read_bytes()
        path.unlink()
        external = self.root / "external.txt"
        external.write_bytes(content)
        path.symlink_to(external)
        with self.assertRaisesRegex(RuntimeError, "regular file"):
            CARD.load_artifacts(self.build_dir)

    def test_card_identity_guards_and_exact_size(self):
        CARD.CARD_IO.EXPECTED_BYTES = CARD_BYTES
        good = disk_info()
        with mock.patch.object(CARD.CARD_IO, "info", return_value=good):
            self.assertEqual(CARD.CARD_IO.card_disk("disk9")["TotalSize"], CARD_BYTES)
        for field, value in (("Internal", True), ("WholeDisk", False), ("RemovableMedia", False),
                             ("BusProtocol", "PCI"), ("VirtualOrPhysical", "Virtual"),
                             ("TotalSize", CARD_BYTES + 512), ("DeviceBlockSize", 4096)):
            with self.subTest(field=field), mock.patch.object(CARD.CARD_IO, "info", return_value=dict(good, **{field: value})):
                with self.assertRaises(RuntimeError):
                    CARD.CARD_IO.card_disk("disk9")
        with mock.patch.object(CARD.CARD_IO, "info", side_effect=AssertionError("invalid name reached info")):
            for disk in ("disk0", "disk9s1", "/dev/disk9", "disk9;echo bad"):
                with self.assertRaises(RuntimeError):
                    CARD.CARD_IO.card_disk(disk)

    def test_plan_does_not_create_state_or_run_diskutil(self):
        build = CARD.load_artifacts(self.build_dir)
        with mock.patch.object(CARD.CARD_IO, "info", return_value=disk_info()), contextlib.redirect_stdout(io.StringIO()):
            CARD.plan(build, "disk9", CARD_BYTES)
        self.assertFalse((self.root / "diagnostics").exists())
        self.diskutil.assert_not_called()

    def test_cancelled_or_swapped_disk_never_formats(self):
        build = CARD.load_artifacts(self.build_dir)
        with mock.patch.object(CARD.os, "geteuid", return_value=0), mock.patch("builtins.input", return_value="no"), \
                mock.patch.object(CARD.CARD_IO, "info", return_value=disk_info()), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "Cancelled"):
                CARD.prepare(build, "disk9", CARD_BYTES)
        self.assertFalse((self.root / "diagnostics").exists())
        changed = dict(disk_info(), DeviceTreePath="different-reader")
        with mock.patch.object(CARD.os, "geteuid", return_value=0), mock.patch("builtins.input", return_value="ERASE disk9"), \
                mock.patch.object(CARD.CARD_IO, "info", side_effect=[disk_info(), changed]), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "changed before format"):
                CARD.prepare(build, "disk9", CARD_BYTES)
        self.diskutil.assert_not_called()

    def test_used_run_refuses_prepare_before_confirmation(self):
        build = CARD.load_artifacts(self.build_dir)
        work = CARD.configure(build, CARD_BYTES)
        work.mkdir(parents=True)
        with mock.patch.object(CARD.os, "geteuid", return_value=0), \
                mock.patch("builtins.input", side_effect=AssertionError("must not ask")):
            with self.assertRaisesRegex(RuntimeError, "already used"):
                CARD.prepare(build, "disk9", CARD_BYTES)

    def test_locked_card_stops_before_confirmation_or_format(self):
        build = CARD.load_artifacts(self.build_dir)
        with mock.patch.object(CARD.os, "geteuid", return_value=0), \
                mock.patch.object(CARD.CARD_IO, "info", return_value=dict(disk_info(), Writable=False)), \
                mock.patch("builtins.input", side_effect=AssertionError("must not ask")):
            with self.assertRaisesRegex(RuntimeError, "Unlock the card"):
                CARD.prepare(build, "disk9", CARD_BYTES)
        self.assertFalse((self.root / "diagnostics").exists())
        self.diskutil.assert_not_called()

    def test_state_update_ignores_leftover_temporary_file(self):
        work = self.root / "state"
        work.mkdir()
        leftover = work / "state.json.tmp"
        leftover.write_text("interrupted update")
        CARD.save_state(work, {"phase": "prepared"})
        CARD.save_state(work, {"phase": "collected"})
        self.assertEqual(json.loads((work / "state.json").read_text()), {"phase": "collected"})
        self.assertEqual(leftover.read_text(), "interrupted update")
        self.assertEqual(list(work.glob(".state-*")), [])

    def test_generic_script_symlink_is_rejected(self):
        (self.build_dir / "a33.scr").symlink_to(self.root / "missing")
        with self.assertRaisesRegex(RuntimeError, "Generic a33.scr"):
            CARD.load_artifacts(self.build_dir)

    def test_prefix_gap_existing_loader_and_partition_count_guards(self):
        image = self.files["u-boot-sunxi-with-spl.bin"]
        before = blank_prefix()
        valid = CARD.CARD_IO.planned_prefix(before, image)
        self.assertEqual(valid[:CARD.CARD_IO.OFFSET], before[:CARD.CARD_IO.OFFSET])
        for changed in (valid, before[:1024]):
            with self.assertRaises(RuntimeError):
                CARD.CARD_IO.planned_prefix(changed, image)
        early = bytearray(before)
        struct.pack_into("<I", early, 454, 2048)
        with self.assertRaisesRegex(RuntimeError, "overlaps"):
            CARD.CARD_IO.planned_prefix(bytes(early), image)
        extra = bytearray(before)
        extra[466] = 0x0c
        with self.assertRaisesRegex(RuntimeError, "exactly one partition"):
            CARD.CARD_IO.planned_prefix(bytes(extra), image)

    def test_fakefile_boot_write_and_restore_preserve_original_prefix(self):
        before = blank_prefix()
        image = self.files["u-boot-sunxi-with-spl.bin"][:-7]  # deliberately not sector-aligned
        raw = self.root / "fake-raw.bin"
        raw.write_bytes(before)
        with mock.patch.object(CARD.CARD_IO.fcntl, "ioctl", return_value=0):
            CARD.CARD_IO.write_boot_image(str(raw), before, image)
            self.assertEqual(raw.read_bytes(), CARD.CARD_IO.planned_prefix(before, image))
            CARD.restore_boot_prefix(str(raw), before, image)
        self.assertEqual(raw.read_bytes(), before)

    def test_changed_prefix_refuses_restore_without_opening_for_write(self):
        before = blank_prefix()
        image = self.files["u-boot-sunxi-with-spl.bin"]
        damaged = bytearray(CARD.CARD_IO.planned_prefix(before, image))
        damaged[10000] ^= 1
        raw = self.root / "fake-raw.bin"
        raw.write_bytes(damaged)
        with mock.patch.object(CARD.os, "open", side_effect=AssertionError("must not write")):
            with self.assertRaisesRegex(RuntimeError, "boot area changed"):
                CARD.restore_boot_prefix(str(raw), before, image)
        self.assertEqual(raw.read_bytes(), damaged)

    def test_state_binds_original_build_after_checkout_changes(self):
        build = CARD.load_artifacts(self.build_dir)
        work = CARD.configure(build, CARD_BYTES)
        work.mkdir(parents=True)
        CARD.save_state(work, {"run_id": RUN_ID, "artifacts": build["manifest"]["artifacts"]})
        (self.here / "probe.cmd.in").write_text("updated source\n")
        old_build = CARD.load_artifacts(self.build_dir, current_sources=False)
        CARD.load_state(work, old_build)
        self.files["run-id.txt"] = b"x" * 32 + b"\n"
        self.write_build()
        with self.assertRaisesRegex(RuntimeError, "Run-ID file mismatch"):
            CARD.load_artifacts(self.build_dir, current_sources=False)

    def test_card_file_guard_rejects_stale_results_and_generic_script(self):
        build = CARD.load_artifacts(self.build_dir)
        mount = self.root / "card"
        mount.mkdir()
        CARD.card_files_match(mount, build, require_fresh=True)
        (mount / "a33.scr").write_bytes(b"old script")
        with self.assertRaisesRegex(RuntimeError, "generic a33.scr"):
            CARD.card_files_match(mount, build, require_fresh=True)
        (mount / "a33.scr").unlink()
        (mount / CARD.VERIFY.STATUS_NAME).write_bytes(b"old status")
        with self.assertRaisesRegex(RuntimeError, "Stale probe output"):
            CARD.card_files_match(mount, build, require_fresh=True)

    def capture_files(self, mount, run_id=RUN_ID):
        payload = bytes(range(256)) * (CARD.VERIFY.PREFIX_BYTES // 256)
        digest = hashlib.sha256(payload).hexdigest()
        fields = {"format": "1", "run_id": run_id, "stage": "finished",
                  "result": "VERIFIED_4MIB_PREFIX", "start_sector": "0", "sector_count": "0x2000",
                  "read_bytes": "0x400000", "read1_sha256": digest, "read2_sha256": digest,
                  "reread": "equal", "card_verify": "equal", "media": "mmc",
                  "extcsd_status": "unavailable", "extcsd_rev": "unknown",
                  "extcsd_sec0": "unknown", "extcsd_sec1": "unknown", "extcsd_sec2": "unknown",
                  "extcsd_sec3": "unknown"}
        (mount / CARD.VERIFY.STATUS_NAME).write_bytes(
            ("".join("pf1006_{}={}\n".format(k, v) for k, v in fields.items())).encode() + b"\0")
        (mount / CARD.VERIFY.PREFIX_NAME).write_bytes(payload)

    def ready_for_collect(self, mount):
        build = CARD.load_artifacts(self.build_dir)
        work = CARD.configure(build, CARD_BYTES)
        work.mkdir(parents=True)
        CARD.save_state(work, {"run_id": RUN_ID, "phase": "prepared", "artifacts": build["manifest"]["artifacts"]})
        CARD.CARD_IO.STATE.write_text("{}")
        mount.mkdir()
        (mount / "pf1006-probe.scr").write_bytes(build["data"]["pf1006-probe.scr"])
        return build

    def test_collect_rejects_stale_run_before_creating_backup(self):
        mount = self.root / "card"
        build = self.ready_for_collect(mount)
        self.capture_files(mount, "f" * 32)
        with mock.patch.object(CARD.os, "geteuid", return_value=501), \
                mock.patch.object(CARD.CARD_IO, "verify_target", return_value=mount):
            with self.assertRaisesRegex(CARD.VERIFY.VerificationError, "run ID mismatch"):
                CARD.collect(build, "disk9", CARD_BYTES)
        self.assertFalse((self.root / "backups").exists())
        self.diskutil.assert_not_called()

    def test_collect_refuses_destination_overwrite(self):
        mount = self.root / "card"
        build = self.ready_for_collect(mount)
        self.capture_files(mount)
        destination = self.root / "backups/pf1006-probe" / RUN_ID
        destination.mkdir(parents=True)
        (destination / "valuable.txt").write_text("keep me")
        with mock.patch.object(CARD.os, "geteuid", return_value=501), \
                mock.patch.object(CARD.CARD_IO, "verify_target", return_value=mount):
            with self.assertRaisesRegex(RuntimeError, "refusing overwrite"):
                CARD.collect(build, "disk9", CARD_BYTES)
        self.assertEqual((destination / "valuable.txt").read_text(), "keep me")
        self.diskutil.assert_not_called()

    @contextlib.contextmanager
    def fake_card(self):
        """Use regular files to model card contents and mount state."""
        build = CARD.load_artifacts(self.build_dir)
        mount = self.root / "card"
        mount.mkdir()
        raw = self.root / "fake-device.bin"
        raw.write_bytes(blank_prefix())
        mounted = True
        commands = []

        def info(identifier):
            if identifier == "disk9":
                return disk_info()
            self.assertEqual(identifier, "disk9s1")
            result = {"VolumeUUID": "SYNTHETIC", "PartitionMapPartitionOffset": 16 * 1024 * 1024,
                      "IOKitSize": CARD_BYTES - 16 * 1024 * 1024,
                      "FilesystemName": "MS-DOS FAT32", "FilesystemType": "msdos"}
            if mounted:
                result["MountPoint"] = str(mount)
            return result

        def diskutil(*args):
            nonlocal mounted
            commands.append(args)
            if args[0] == "partitionDisk":
                self.assertEqual(args, ("partitionDisk", "disk9", "MBR", "Free Space", "%noformat%",
                                       "16M", "MS-DOS FAT32", "PF1006PROBE", "0b"))
                raw.write_bytes(blank_prefix())
                mounted = True
            elif args[0] == "mount":
                mounted = True
            elif args[0] in ("unmountDisk", "eject"):
                mounted = False
            else:
                self.fail("Unexpected command: " + str(args))

        with mock.patch.object(CARD, "diskutil", side_effect=diskutil), \
                mock.patch.object(CARD.CARD_IO, "info", side_effect=info), \
                mock.patch.object(CARD, "raw_device", return_value=str(raw)), \
                mock.patch.object(CARD.os, "chown"), \
                mock.patch.object(CARD.fcntl, "ioctl", return_value=0), \
                contextlib.redirect_stdout(io.StringIO()):
            yield build, mount, raw, commands

    def test_fake_prepare_collect_remove_lifecycle(self):
        with self.fake_card() as (build, mount, raw, commands):
            with mock.patch.object(CARD.os, "geteuid", return_value=0), \
                    mock.patch("builtins.input", return_value="ERASE disk9"):
                CARD.prepare(build, "disk9", CARD_BYTES)
            self.assertEqual(raw.read_bytes(), CARD.CARD_IO.planned_prefix(
                blank_prefix(), self.files["u-boot-sunxi-with-spl.bin"]))
            self.assertEqual((mount / "pf1006-probe.scr").read_bytes(), self.files["pf1006-probe.scr"])
            self.capture_files(mount)
            with mock.patch.object(CARD.os, "geteuid", return_value=501):
                CARD.collect(build, "disk9", CARD_BYTES)
            destination = self.root / "backups/pf1006-probe" / RUN_ID
            self.assertTrue((destination / CARD.VERIFY.PREFIX_NAME).is_file())
            with mock.patch.object(CARD.os, "geteuid", return_value=0), \
                    mock.patch("builtins.input", return_value="REMOVE BOOTLOADER disk9"):
                CARD.remove(build, "disk9", CARD_BYTES)
            self.assertEqual(raw.read_bytes(), blank_prefix())
            self.assertIn(("mount", "readOnly", "disk9s1"), commands)
            self.assertEqual(sum(command[0] == "partitionDisk" for command in commands), 1)
            self.assertEqual(json.loads((CARD.CARD_IO.WORK / "state.json").read_text())["phase"], "removed")

    def interrupted_prepare_remove(self, damage_prefix):
        original_save = CARD.save_state

        def fail_final_state_save(work, state):
            if state["phase"] == "prepared":
                raise RuntimeError("simulated interruption after complete boot write")
            original_save(work, state)

        with self.fake_card() as (build, mount, raw, commands), \
                mock.patch.object(CARD.os, "geteuid", return_value=0):
            with mock.patch("builtins.input", return_value="ERASE disk9"), \
                    mock.patch.object(CARD, "save_state", side_effect=fail_final_state_save):
                with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                    CARD.prepare(build, "disk9", CARD_BYTES)
            self.assertEqual(raw.read_bytes(), CARD.CARD_IO.planned_prefix(
                blank_prefix(), self.files["u-boot-sunxi-with-spl.bin"]))
            state_path = CARD.CARD_IO.WORK / "state.json"
            self.assertEqual(json.loads(state_path.read_text())["phase"], "prefix_backed_up")
            self.assertNotIn(("eject", "disk9"), commands)
            if damage_prefix:
                damaged = bytearray(raw.read_bytes())
                damaged[CARD.CARD_IO.OFFSET + 100] ^= 1
                raw.write_bytes(damaged)
            with mock.patch("builtins.input", return_value="REMOVE BOOTLOADER disk9"):
                if damage_prefix:
                    with self.assertRaisesRegex(RuntimeError, "boot area changed"):
                        CARD.remove(build, "disk9", CARD_BYTES)
                    self.assertEqual(raw.read_bytes(), damaged)
                    self.assertEqual(json.loads(state_path.read_text())["phase"], "prefix_backed_up")
                    self.assertNotIn(("eject", "disk9"), commands)
                else:
                    CARD.remove(build, "disk9", CARD_BYTES)
                    self.assertEqual(raw.read_bytes(), blank_prefix())
                    self.assertEqual(json.loads(state_path.read_text())["phase"], "removed")
                    self.assertEqual(commands[-1], ("eject", "disk9"))

    def test_remove_recovers_interruption_after_complete_boot_write(self):
        self.interrupted_prepare_remove(damage_prefix=False)

    def test_interrupted_prepare_with_partial_prefix_still_refuses_remove(self):
        self.interrupted_prepare_remove(damage_prefix=True)


if __name__ == "__main__":
    unittest.main()
