"""Card publication regression tests with a mocked APK builder; no SDK/card needed."""

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_card as card
from test_enable_adb import public_key


class PrepareCardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.out = self.root / "card with spaces"
        self.key = self.root / "adbkey.pub"
        self.key.write_bytes(public_key(1))
        self.approved = ["p_frameo_jb", "Frameo_utilities/frameo_utilities.config",
                         "Frameo_utilities/" + card.APK_NAME, "mi86-adb-v2/adbkey.pub"]

    def invoke(self, replace=False, mode="adb", builder=None):
        def build(path, version):
            path.write_bytes(b"validated fixture apk")
        with patch.object(card, "build_apk", side_effect=builder or build), redirect_stdout(StringIO()) as output:
            card.stage(self.out, mode, 80322, self.key if mode == "adb" else None, replace)
        return output.getvalue()

    def existing(self):
        for name in self.approved:
            destination = self.out / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"original " + name.encode())

    def test_fresh_probe_and_adb_have_complete_bundle_and_insertion_warning(self):
        for mode in ["probe", "adb"]:
            with self.subTest(mode=mode):
                self.out = self.root / mode
                output = self.invoke(mode=mode)
                self.assertEqual((self.out / "p_frameo_jb").read_bytes(),
                                 (card.PROBE if mode == "probe" else card.ENABLE).read_bytes())
                self.assertEqual((self.out / "Frameo_utilities/frameo_utilities.config").read_text(), card.CONFIG)
                self.assertEqual([p.name for p in (self.out / "Frameo_utilities").glob("*.apk")], [card.APK_NAME])
                self.assertIn("approval before EVERY insertion", output)
                self.assertIn("even in probe mode", output)

    def test_each_existing_leaf_requires_explicit_replacement(self):
        for index, name in enumerate(self.approved):
            with self.subTest(name=name):
                self.out = self.root / str(index)
                destination = self.out / name
                destination.parent.mkdir(parents=True)
                destination.write_bytes(b"keep")
                with self.assertRaisesRegex(SystemExit, "--replace"):
                    self.invoke()
                self.assertEqual(destination.read_bytes(), b"keep")
                self.assertFalse((self.out / "p_frameo_jb").exists() and name != "p_frameo_jb")

    def test_dangling_and_live_leaf_symlinks_require_replacement(self):
        target = self.root / "external"
        for target_exists in [False, True]:
            if target_exists:
                target.write_bytes(b"outside")
            for index, name in enumerate(self.approved):
                with self.subTest(name=name, target_exists=target_exists):
                    self.out = self.root / f"links-{target_exists}-{index}"
                    destination = self.out / name
                    destination.parent.mkdir(parents=True)
                    destination.symlink_to(target)
                    with self.assertRaisesRegex(SystemExit, "--replace"):
                        self.invoke()
                    self.assertTrue(destination.is_symlink())
                    self.assertEqual(target.read_bytes() if target_exists else target.exists(),
                                     b"outside" if target_exists else False)

    def test_explicit_replace_never_follows_leaf_links_and_retains_recovery(self):
        target = self.root / "external"
        target.write_bytes(b"outside")
        for name in self.approved:
            destination = self.out / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(target)
        recovery = self.out / "mi86-adb-v2/attempt.saved/adb_keys.raw"
        recovery.parent.mkdir()
        recovery.write_bytes(b"recovery fixture")
        unrelated = self.out / "keep.txt"
        unrelated.write_bytes(b"keep")
        self.invoke(replace=True)
        self.assertEqual(target.read_bytes(), b"outside")
        self.assertEqual(recovery.read_bytes(), b"recovery fixture")
        self.assertEqual(unrelated.read_bytes(), b"keep")
        self.assertEqual((self.out / self.approved[2]).read_bytes(), b"validated fixture apk")
        for name in self.approved:
            self.assertFalse((self.out / name).is_symlink())

    def test_linked_managed_directories_are_refused_even_with_replace(self):
        target = self.root / "external-directory"
        target.mkdir()
        for index, name in enumerate(["", "Frameo_utilities", "mi86-adb-v2"]):
            self.out = self.root / f"linked-dir-{index}"
            if name:
                self.out.mkdir()
            (self.out / name).symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(SystemExit, "symlink|real directory"):
                self.invoke(replace=True)
        self.assertEqual(list(target.iterdir()), [])

    def test_nonregular_leaf_and_appledouble_are_refused(self):
        for index, name in enumerate([*self.approved, "Frameo_utilities/._extra.apk"]):
            self.out = self.root / f"invalid-{index}"
            destination = self.out / name
            destination.mkdir(parents=True)
            with self.assertRaises(SystemExit):
                self.invoke(replace=True)

    def test_build_failure_preserves_existing_setup_and_creates_no_new_output(self):
        def failed_build(path, version):
            path.write_bytes(b"partial apk")
            raise RuntimeError("failed build")
        with self.assertRaisesRegex(RuntimeError, "failed build"):
            self.invoke(builder=failed_build)
        self.assertFalse(self.out.exists())
        self.existing()
        before = {name: (self.out / name).read_bytes() for name in self.approved}
        with self.assertRaises(RuntimeError):
            self.invoke(replace=True, builder=failed_build)
        self.assertEqual(before, {name: (self.out / name).read_bytes() for name in self.approved})

    def test_publish_failures_disarm_config_including_after_config_rename(self):
        original = card.publish
        for index, failed_name in enumerate(["p_frameo_jb", card.APK_NAME, "adbkey.pub", "frameo_utilities.config"]):
            self.out = self.root / f"failure-{index}"
            self.existing()

            def failing(directory, name, contents, replace):
                if name == failed_name:
                    original(directory, name, contents, replace)
                    raise OSError("publication failed after rename")
                original(directory, name, contents, replace)

            with patch.object(card, "publish", side_effect=failing):
                with self.assertRaisesRegex(OSError, "publication failed"):
                    self.invoke(replace=True)
            self.assertFalse(os.path.lexists(self.out / "Frameo_utilities/frameo_utilities.config"))

    def test_disarm_failure_prevents_any_other_replacement(self):
        self.existing()
        before = {name: (self.out / name).read_bytes() for name in self.approved}
        original = os.unlink

        def unlink(name, *args, **kwargs):
            if name == "frameo_utilities.config":
                raise PermissionError("cannot disarm")
            return original(name, *args, **kwargs)

        with patch.object(card.os, "unlink", side_effect=unlink):
            with self.assertRaisesRegex(PermissionError, "cannot disarm"):
                self.invoke(replace=True)
        self.assertEqual(before, {name: (self.out / name).read_bytes() for name in self.approved})

    def test_bundle_tamper_is_caught_before_config_publication(self):
        original = card.publish

        def tamper(directory, name, contents, replace):
            original(directory, name, contents, replace)
            if name == "adbkey.pub":
                (self.out / "p_frameo_jb").write_bytes(b"unexpected")

        with patch.object(card, "publish", side_effect=tamper):
            with self.assertRaisesRegex(RuntimeError, "changed before arming"):
                self.invoke()
        self.assertFalse((self.out / "Frameo_utilities/frameo_utilities.config").exists())

    def test_unrelated_utility_files_are_preserved_and_refused(self):
        for index, name in enumerate(["other.apk", "keep.txt", "._utility.apk"]):
            self.out = self.root / f"unrelated-{index}"
            unrelated = self.out / "Frameo_utilities" / name
            unrelated.parent.mkdir(parents=True)
            unrelated.write_bytes(b"keep")
            with self.assertRaisesRegex(SystemExit, "unrelated/AppleDouble"):
                self.invoke(replace=True)
            self.assertEqual(unrelated.read_bytes(), b"keep")

    def test_invalid_public_key_and_extra_line_are_rejected_before_build(self):
        for contents in [b"QAAAA" + b"A" * 694 + b"= invalid\n", public_key(1) + b"\n"]:
            self.key.write_bytes(contents)
            with patch.object(card, "build_apk") as builder:
                with self.assertRaises(SystemExit):
                    self.invoke(builder=builder)
                builder.assert_not_called()
            self.assertFalse(self.out.exists())

    def test_config_is_published_last_while_disarmed(self):
        self.existing()
        original = card.publish
        targets = []

        def observe(directory, name, contents, replace):
            self.assertFalse((self.out / "Frameo_utilities/frameo_utilities.config").exists())
            targets.append(name)
            original(directory, name, contents, replace)

        with patch.object(card, "publish", side_effect=observe):
            self.invoke(replace=True)
        self.assertEqual(targets, ["p_frameo_jb", card.APK_NAME, "adbkey.pub", "frameo_utilities.config"])

    def test_actual_config_readback_corruption_disarms(self):
        original = os.replace

        def corrupt(src, dest, **kwargs):
            original(src, dest, **kwargs)
            if dest == "frameo_utilities.config":
                (self.out / "Frameo_utilities" / dest).write_bytes(b"bad config")

        with patch.object(card.os, "replace", side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError, "published card readback differs"):
                self.invoke()
        self.assertFalse((self.out / "Frameo_utilities/frameo_utilities.config").exists())

    def test_symlinked_output_ancestor_is_refused(self):
        linked = self.root / "linked-parent"
        linked.symlink_to(self.root, target_is_directory=True)
        self.out = linked / "new-output"
        with self.assertRaisesRegex(SystemExit, "symlink in output path"):
            self.invoke(replace=True)
        self.assertFalse((self.root / "new-output").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
