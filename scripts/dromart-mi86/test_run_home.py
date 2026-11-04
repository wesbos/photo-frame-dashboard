"""Host-only helper deployment tests; no ADB daemon or frame is contacted."""

import hashlib
from io import BytesIO
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import run_home as home


class FakeAdb:
    def __init__(self, fault="", fingerprint=home.FINGERPRINT):
        self.fault = fault
        self.fingerprint = fingerprint
        self.calls = []
        self.executions = []
        self.upload = None
        self.protected = None

    def call(self, *args, **kwargs):
        self.calls.append(("call", args))
        assert args[0] == "push"
        self.upload = Path(args[1]).read_bytes()
        if self.fault == "upload":
            raise home.HomeError("upload failed")
        if self.fault == "corrupt-upload":
            self.upload += b"changed by shell"
        return b""

    def checked(self, script, *, root=True):
        self.calls.append(("checked", script, root))
        if "getprop" in script:
            return self.fingerprint.encode() + b"\n"
        if "app_process" in script:
            if self.fault == "execution-check":
                raise home.HomeError("metadata changed before execution")
            self.executions.append((script, self.protected))
            if self.fault == "execute":
                raise home.HomeError("helper failed")
            return b"Resolved Home: fixture\n"
        if "umask 077" in script:
            phase = "mkdir"
        elif "cp /data/local/tmp/" in script:
            phase = "copy"
            self.protected = self.upload
            if self.fault == "replace-upload-after-copy":
                self.upload = b"changed by shell after copy"
        elif " && cat /data/mi86-home-" in script:
            phase = "readback"
        elif "chmod 750" in script:
            phase = "grant"
        elif "rmdir" in script:
            phase = "cleanup-protected"
        elif "rm -f /data/local/tmp/" in script:
            phase = "cleanup-upload"
        else:
            raise AssertionError(script)
        if self.fault == phase:
            raise home.HomeError(phase + " failed")
        if phase == "readback":
            return self.protected + (b"corrupt" if self.fault == "readback-mismatch" else b"")
        return b""


class RunHomeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "build with spaces"
        self.directory.mkdir()
        data = BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("classes.dex", b"dex\n035\0synthetic fixture")
        self.payload = data.getvalue()
        (self.directory / "persistent-home.jar").write_bytes(self.payload)
        self.manifest = {
            "source": home.SOURCE.name,
            "source_sha256": hashlib.sha256(home.SOURCE.read_bytes()).hexdigest(),
            "artifact": "persistent-home.jar",
            "artifact_bytes": len(self.payload),
            "artifact_sha256": hashlib.sha256(self.payload).hexdigest(),
            "min_api": 23,
        }
        self.write_manifest()

    def write_manifest(self):
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))

    def invoke(self, fake, operation="set"):
        with patch.object(home, "Adb", return_value=fake) as factory:
            output = home.run("selected-fixture", self.directory, operation)
        factory.assert_called_once_with("selected-fixture")
        return output

    def test_operations_execute_only_protected_verified_bytes_at_required_uid(self):
        for operation, uid in [("inspect", 0), ("set", 1000), ("clear", 1000)]:
            with self.subTest(operation=operation):
                fake = FakeAdb()
                self.assertIn(b"Resolved Home", self.invoke(fake, operation))
                self.assertEqual(len(fake.executions), 1)
                script, payload = fake.executions[0]
                self.assertEqual(payload, self.payload)
                self.assertIn(f"su {uid} env CLASSPATH=/data/mi86-home-", script)
                self.assertNotIn("/data/local/tmp", script)
                self.assertIn("'0 1000 750'", script)
                self.assertIn("'0 1000 640'", script)
                self.assertIn("[ ! -L /data/mi86-home-", script)
                self.assertTrue(any("rmdir /data/mi86-home-" in call[1] for call in fake.calls if call[0] == "checked"))
                self.assertTrue(any("rm -f /data/local/tmp/" in call[1] and not call[2]
                                    for call in fake.calls if call[0] == "checked"))

    def test_all_staging_or_comparison_failures_prevent_execution(self):
        for fault in ["mkdir", "upload", "copy", "readback", "readback-mismatch",
                      "corrupt-upload", "grant", "execution-check"]:
            with self.subTest(fault=fault):
                fake = FakeAdb(fault)
                with self.assertRaises(home.HomeError):
                    self.invoke(fake)
                self.assertEqual(fake.executions, [])

    def test_shell_replacement_of_upload_after_copy_cannot_change_executed_bytes(self):
        fake = FakeAdb("replace-upload-after-copy")
        self.invoke(fake)
        self.assertNotEqual(fake.upload, self.payload)
        self.assertEqual(fake.executions[0][1], self.payload)

    def test_wrong_or_missing_identity_stops_before_staging(self):
        for fingerprint in ["", home.FINGERPRINT + "-other"]:
            fake = FakeAdb(fingerprint=fingerprint)
            with self.assertRaisesRegex(home.HomeError, "fingerprint mismatch"):
                self.invoke(fake)
            self.assertEqual(len(fake.calls), 1)

    def test_manifest_mismatches_stop_before_adb(self):
        for key in self.manifest:
            with self.subTest(key=key):
                original = self.manifest[key]
                self.manifest[key] = "wrong"
                self.write_manifest()
                with patch.object(home, "Adb") as adb:
                    with self.assertRaisesRegex(home.HomeError, "manifest"):
                        home.run("fixture", self.directory, "inspect")
                    adb.assert_not_called()
                self.manifest[key] = original

    def test_cleanup_and_execution_failures_are_reported(self):
        for fault in ["cleanup-upload", "cleanup-protected", "execute"]:
            fake = FakeAdb(fault)
            with self.assertRaisesRegex(home.HomeError, "execution was attempted"):
                self.invoke(fake)
            if fault.startswith("cleanup"):
                self.assertTrue(any("rmdir" in call[1] for call in fake.calls if call[0] == "checked"))

    def test_invalid_operation_and_empty_serial_are_rejected(self):
        with self.assertRaises(home.HomeError):
            home.run("fixture", self.directory, "erase")
        with self.assertRaises(home.HomeError):
            home.Adb("")


class AdbCompletionTests(unittest.TestCase):
    def test_zero_client_status_without_remote_success_suffix_is_rejected(self):
        adb = home.Adb("fixture")
        with patch.object(adb, "call", return_value=b"failed command but old client returned zero"):
            with self.assertRaisesRegex(home.HomeError, "completion"):
                adb.checked("false")

    @unittest.skipUnless(shutil.which("bash"), "Bash is required for remote wrapper tests")
    def test_real_shell_wrapper_only_emits_suffix_after_success_and_preserves_binary(self):
        adb = home.Adb("fixture")

        def remote(*args, **kwargs):
            self.assertEqual(args[0], "exec-out")
            words = shlex.split(args[1])
            self.assertEqual(words[:4], ["su", "0", "sh", "-c"])
            # Execute only harmless fixture commands, without su/ADB/device paths.
            return subprocess.run(["bash", "-c", words[4]], capture_output=True).stdout

        with patch.object(adb, "call", side_effect=remote):
            self.assertEqual(adb.checked("printf '\\000\\377fixture'"), b"\0\xfffixture")
            with self.assertRaises(home.HomeError):
                adb.checked("false")

    def test_nonzero_adb_status_is_rejected(self):
        with patch.object(home.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"disconnected")):
            with self.assertRaisesRegex(home.HomeError, "ADB failed"):
                home.Adb("fixture").call("push", "fixture", "/fixture")

    @unittest.skipUnless(shutil.which("bash"), "Bash is required for remote metadata tests")
    def test_ancestry_rejects_symlinks_nonroot_and_shell_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "data"
            parent.mkdir()
            link = Path(temporary) / "linked-data"
            link.symlink_to(parent, target_is_directory=True)
            for uid, group, mode, path, success in [
                (0, 0, "755", parent, True), (0, 1000, "771", parent, True),
                (0, 2000, "770", parent, False), (0, 0, "777", parent, False),
                (2000, 1000, "750", parent, False), (0, 1000, "771", link, False),
            ]:
                with self.subTest(uid=uid, group=group, mode=mode, path=path):
                    script = home.trusted_ancestry().replace(
                        "for parent in / /data; do", "for parent in " + shlex.quote(str(path)) + "; do")
                    stat = ("stat() { case \"$2\" in %u) echo " + str(uid)
                            + ";; %g) echo " + str(group) + ";; %a) echo " + mode + ";; esac; };\n")
                    result = subprocess.run(["bash", "-c", stat + script], capture_output=True)
                    self.assertEqual(result.returncode == 0, success, result.stderr)

    @unittest.skipUnless(shutil.which("bash"), "Bash is required for remote metadata tests")
    def test_protected_checks_gate_execution_on_metadata_and_file_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "protected"
            directory.mkdir()
            jar = directory / "persistent-home.jar"
            jar.write_bytes(b"fixture")
            linked = directory / "linked.jar"
            linked.symlink_to(jar)
            for dir_metadata, jar_metadata, target, success in [
                ("0 1000 750", "0 1000 640", jar, True),
                ("2000 1000 750", "0 1000 640", jar, False),
                ("0 1000 777", "0 1000 640", jar, False),
                ("0 1000 750", "2000 1000 640", jar, False),
                ("0 1000 750", "0 1000 666", jar, False),
                ("0 1000 750", "0 1000 640", linked, False),
                ("0 1000 750", "0 1000 640", directory, False),
            ]:
                with self.subTest(dir_metadata=dir_metadata, jar_metadata=jar_metadata, target=target):
                    stat = ("stat() { if [ \"$3\" = " + shlex.quote(str(directory))
                            + " ]; then echo " + shlex.quote(dir_metadata) + "; else echo "
                            + shlex.quote(jar_metadata) + "; fi; };\n")
                    script = (home.protected_directory(str(directory)) + " && "
                              + home.protected_jar(str(target)) + " && echo EXECUTED")
                    result = subprocess.run(["bash", "-c", stat + script], capture_output=True)
                    self.assertEqual(b"EXECUTED" in result.stdout, success, result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
