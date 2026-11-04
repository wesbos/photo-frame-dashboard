"""Host-only tests for data-patch-prepare.py --nulldev and emmc-macos.py verify-data.

Uses small image files in a temporary folder; never opens a real disk.
  python3 -I scripts/a33-uboot/test_data_patch.py
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load("data_patch_prepare", "data-patch-prepare.py")
emmc = load("emmc_macos", "emmc-macos.py")

SECTOR = 512
START = 8  # partition start sector inside the fake disk


class DataPatchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.orig = bytearray(i * 7 % 251 for i in range(64 * SECTOR))
        self.edited = bytearray(self.orig)
        self.edited[2 * SECTOR:3 * SECTOR] = b"\x11" * SECTOR
        self.edited[40 * SECTOR + 10] ^= 0xFF
        (self.tmp / "orig.img").write_bytes(self.orig)
        (self.tmp / "edited.img").write_bytes(self.edited)
        patcher = unittest.mock.patch.object(prepare, "OUT", self.tmp / "out")
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_prepare(self, *flags, out=None):
        if out:
            prepare.OUT = out
        argv = ["data-patch-prepare.py", *flags,
                str(self.tmp / "orig.img"), str(self.tmp / "edited.img"), str(START)]
        with unittest.mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            prepare.main()
        return json.loads((prepare.OUT / "plan.json").read_text())

    def scripts(self):
        return {name: (prepare.OUT / f"{name}.cmd").read_text() for name in ("write-data", "restore-data")}

    def disk(self, partition):
        path = self.tmp / "disk.img"
        path.write_bytes(bytes(START * SECTOR) + bytes(partition) + bytes(4 * SECTOR))
        return path

    def verify(self, disk):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            emmc.verify_data(str(disk), disk.stat().st_size, prepare.OUT / "plan.json")
        return out.getvalue()

    def verify_fails(self, disk, message):
        out = io.StringIO()
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(out):
            emmc.verify_data(str(disk), disk.stat().st_size, prepare.OUT / "plan.json")
        self.assertIn(message, str(stop.exception))
        return out.getvalue()

    def edit_plan(self, change):
        path = prepare.OUT / "plan.json"
        plan = json.loads(path.read_text())
        change(plan)
        path.write_text(json.dumps(plan))

    def test_default_scripts_have_no_guard(self):
        plan = self.run_prepare()
        self.assertFalse(plan["nulldev"])
        for name, text in self.scripts().items():
            self.assertNotIn("nulldev", text)
            self.assertTrue(text.startswith("# "), name)
            self.assertIn(text.encode(), (prepare.OUT / f"{name}.scr").read_bytes())

    def test_nulldev_wraps_the_unchanged_script(self):
        self.run_prepare()
        plain = self.scripts()
        plan = self.run_prepare("--nulldev", out=self.tmp / "out-nulldev")
        self.assertTrue(plan["nulldev"])
        for name, text in self.scripts().items():
            self.assertEqual(text, prepare.with_nulldev(plain[name]))
            lines = text.splitlines()
            self.assertEqual(lines[1], "if setenv stdin nulldev; then")
            self.assertEqual(lines[-1], "fi")
            # Nothing but the STOP branch follows the wrapped script.
            self.assertEqual(lines[-5:-1], ["ums 0 mmc 1", "else",
                                            "  echo STOP: could not disable serial input, nothing written",
                                            "  while true; do sleep 1; done"])
            self.assertIn(text.encode(), (prepare.OUT / f"{name}.scr").read_bytes())

    def test_unknown_flag_shows_usage(self):
        with self.assertRaises(SystemExit) as stop:
            self.run_prepare("--nuldev")
        self.assertIn("Usage", str(stop.exception))

    def test_verify_data_original_and_new(self):
        plan = self.run_prepare()
        self.assertEqual(len(plan["writes"]), 2)
        out = self.verify(self.disk(self.orig))
        self.assertEqual(out.count(": original"), 2)
        self.assertIn("all 2 range(s) hold the original bytes", out)
        out = self.verify(self.disk(self.edited))
        self.assertEqual(out.count(": new"), 2)
        self.assertIn("all 2 range(s) hold the new bytes", out)

    def test_verify_data_mixed_fails(self):
        self.run_prepare()
        half = bytearray(self.orig)
        half[2 * SECTOR:3 * SECTOR] = self.edited[2 * SECTOR:3 * SECTOR]
        out = self.verify_fails(self.disk(half), "mixed or unexpected")
        self.assertIn("range 0 (sector 10, 512 bytes): new", out)
        self.assertIn("range 1 (sector 48, 512 bytes): original", out)

    def test_verify_data_unexpected_fails(self):
        self.run_prepare()
        other = bytearray(self.orig)
        other[40 * SECTOR] ^= 0x01
        out = self.verify_fails(self.disk(other), "mixed or unexpected")
        self.assertIn("range 1 (sector 48, 512 bytes): UNEXPECTED", out)

    def test_verify_data_rejects_changed_payload(self):
        self.run_prepare()
        (prepare.OUT / "range-00.new").write_bytes(b"\x00" * SECTOR)
        self.verify_fails(self.disk(self.edited), "range-00.new does not match plan.json")

    def test_verify_data_rejects_inconsistent_plan(self):
        self.run_prepare()
        self.edit_plan(lambda p: p["writes"][0].update(sectors=2))
        self.verify_fails(self.disk(self.edited), "not a whole number of sectors")
        self.run_prepare(out=self.tmp / "out-2")
        self.edit_plan(lambda p: p["writes"][1].update(sector=47))
        self.verify_fails(self.disk(self.edited), "does not match its partition offset")

    def test_verify_data_rejects_past_end_and_empty_plan(self):
        self.run_prepare()
        short = self.tmp / "short.img"
        short.write_bytes(bytes(START * SECTOR) + bytes(self.orig[:20 * SECTOR]))
        self.verify_fails(short, "past the end of the disk")
        self.edit_plan(lambda p: p.update(writes=[]))
        self.verify_fails(self.disk(self.orig), "no ranges")


if __name__ == "__main__":
    unittest.main()
