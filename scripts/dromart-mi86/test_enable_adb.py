"""Host-only end-to-end tests of the ADB enabler, with mocked Android commands.

Run: python3 scripts/dromart-mi86/test_enable_adb.py
Requires Python 3 and Bash (or mksh). No ADB, root, SDK, network, or device is used.
Only the production script's two absolute device-path declarations are rebased;
its checks, key parsing, staging, traps, and rollback run unchanged.
"""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ENABLE = HERE / "enable-adb.sh"
FINGERPRINT = "rockchip/rk312x/rk312x:6.0.1/MXC89K/user.zcx.20250822.060141:user/release-keys"
LABEL = "u:object_r:adb_keys_file:s0"
COMMANDS = (
    "dirname date id getprop setprop stop start mkdir touch rm cp mv cmp mktemp "
    "stat ls chown chmod chcon base64 toybox busybox od tr cat sync sleep"
).split()
SHELL = shutil.which("mksh") or shutil.which("bash")


def public_key(seed: int) -> bytes:
    # Deterministic public-key-format fixtures, unrelated to anyone's ADB credentials.
    modulus = (1 << 2048) - 159 - 2 * seed
    n0inv = (-pow(modulus & 0xFFFFFFFF, -1, 1 << 32)) & 0xFFFFFFFF
    raw = struct.pack("<II", 64, n0inv)
    raw += modulus.to_bytes(256, "little")
    raw += pow(2, 4096, modulus).to_bytes(256, "little")
    raw += struct.pack("<I", 65537)
    return base64.b64encode(raw) + b" synthetic-fixture\n"


class Sandbox:
    def __init__(self, root: Path, baseline: str, faults: tuple[str, ...] = ()) -> None:
        self.root = root.resolve()
        self.card = self.root / "card with spaces"
        self.results = self.card / "mi86-adb-v2"
        self.results.mkdir(parents=True)
        self.trigger = self.card / "Frameo_utilities/frameo_utilities.config"
        self.trigger.parent.mkdir()
        self.trigger.write_text("auto_run=action_update_version\n")
        self.supplied = public_key(1)
        (self.results / "adbkey.pub").write_bytes(self.supplied)
        self.keys = self.root / "keys/adb_keys"
        self.keys.parent.mkdir(parents=True)
        self.original = {
            "absent": None,
            "empty": b"",
            "present": b"," + public_key(3) + public_key(2),
        }[baseline]
        self.original_metadata = {"uid": 1000, "gid": 2000, "mode": "640", "label": LABEL}
        if self.original is not None:
            self.keys.write_bytes(self.original)
        listeners = [self.root / "listeners/tcp", self.root / "listeners/tcp6"]
        listeners[0].parent.mkdir(parents=True)
        for listener in listeners:
            listener.write_text("")
        self.properties = {
            "ro.build.fingerprint": FINGERPRINT,
            "ro.adb.secure": "1",
            "ro.secure": "1",
            "ro.debuggable": "0",
            "service.adb.tcp.port": "",
            "persist.adb.tcp.port": "4321",
            "init.svc.adbd": "running",
        }
        self.state = {
            "keys": str(self.keys),
            "listeners": list(map(str, listeners)),
            "metadata": {str(self.keys): self.original_metadata.copy()} if self.original is not None else {},
            "properties": self.properties.copy(),
            "uid": 0,
            "base64_tool": "toybox",  # Android 6 path; standalone is also tested below.
            "phase": "before",
            "faults": list(faults),
            "fired": [],
            "calls": [],
        }
        self.state_file = self.root / "state.json"
        mock_bin = self.root / "bin"
        mock_bin.mkdir()
        mock = mock_bin / "mock.py"
        mock.write_text(f"#!{sys.executable}\n" + (HERE / "tests/mock_android.py").read_text())
        mock.chmod(0o755)
        for command in COMMANDS:
            (mock_bin / command).symlink_to(mock.name)
        # No production test hook or configurable target path: redirect literals only here.
        source = ENABLE.read_text()
        replacements = {
            "keys=/data/misc/adb/adb_keys": "keys=" + shlex.quote(str(self.keys)),
            "for listener_table in /proc/net/tcp /proc/net/tcp6; do":
                "for listener_table in " + " ".join(shlex.quote(str(p)) for p in listeners) + "; do",
        }
        for old, new in replacements.items():
            assert source.count(old) == 1, f"production path declaration changed: {old}"
            source = source.replace(old, new)
        assert "/data/misc/adb/" not in source and "/proc/net/" not in source
        self.script = self.card / "p_frameo_jb"
        self.script.write_text(source)
        self.env = {
            "PATH": str(mock_bin),  # Unmocked tools cannot fall through to host commands.
            "MI86_MOCK_ROOT": str(self.root),
            "MI86_MOCK_STATE": str(self.state_file),
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.log = ""

    def run(self) -> subprocess.CompletedProcess:
        self.state_file.write_text(json.dumps(self.state))
        result = subprocess.run(
            [SHELL, str(self.script)], cwd=self.root, env=self.env,
            capture_output=True, text=True, timeout=30,
        )
        self.state = json.loads(self.state_file.read_text())
        result_file = self.results / "result.txt"
        self.log = result_file.read_text() if result_file.exists() else ""
        if "Traceback" in self.log + result.stderr:
            raise AssertionError(self.log + result.stderr)
        return result


@unittest.skipUnless(SHELL, "Bash or mksh is required")
class EnableAdbTests(unittest.TestCase):
    def sandbox(self, baseline: str = "present", faults: tuple[str, ...] = ()) -> Sandbox:
        temp = tempfile.TemporaryDirectory(prefix="mi86-adb-test-")
        self.addCleanup(temp.cleanup)
        return Sandbox(Path(temp.name), baseline, faults)

    def assert_unchanged(self, box: Sandbox) -> None:
        self.assertEqual(box.keys.exists(), box.original is not None)
        if box.original is not None:
            self.assertEqual(box.keys.read_bytes(), box.original)
            self.assertEqual(box.state["metadata"][str(box.keys)], box.original_metadata)
        self.assertEqual(box.state["properties"], box.properties)
        self.assertFalse((box.results / "done").exists())
        self.assertEqual(list(box.keys.parent.glob("adb_keys.frameo.*")), [])

    def assert_no_live_changes(self, box: Sandbox) -> None:
        for call in box.state["calls"]:
            self.assertNotIn(call["command"], {"setprop", "stop", "start"})
            if call["command"] == "mv":
                self.assertNotEqual(call["args"][-1], str(box.keys))

    def test_fingerprint_mismatch_empty_and_read_failure_stop_before_snapshot(self) -> None:
        for fingerprint, faults in [("other/firmware", ()), ("", ()), (FINGERPRINT, ("fingerprint_read",))]:
            with self.subTest(fingerprint=fingerprint, faults=faults):
                box = self.sandbox(faults=faults)
                box.properties["ro.build.fingerprint"] = fingerprint
                box.state["properties"] = box.properties.copy()
                result = box.run()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fingerprint", box.log)
                if faults:
                    self.assertIn("cannot read firmware fingerprint", box.log)
                self.assert_unchanged(box)
                self.assert_no_live_changes(box)
                self.assertTrue(box.trigger.exists())
                self.assertEqual(list(box.results.glob("attempt.*")), [])
                self.assertFalse(any(c["command"] in {"chown", "chmod", "chcon"} for c in box.state["calls"]))

    def test_fingerprint_requires_exact_match(self) -> None:
        box = self.sandbox()
        box.properties["ro.build.fingerprint"] += "-different-build"
        box.state["properties"] = box.properties.copy()
        self.assertNotEqual(box.run().returncode, 0)
        self.assertIn("firmware fingerprint mismatch", box.log)
        self.assert_unchanged(box)
        self.assertTrue(box.trigger.exists())

    def test_non_root_stops_before_configuration_changes(self) -> None:
        box = self.sandbox()
        box.state["uid"] = 2000
        self.assertNotEqual(box.run().returncode, 0)
        self.assertIn("root is required", box.log)
        self.assert_unchanged(box)
        self.assertTrue(box.trigger.exists())

    def test_success_from_absent_empty_and_existing_keys(self) -> None:
        for baseline in ["absent", "empty", "present"]:
            with self.subTest(baseline=baseline):
                box = self.sandbox(baseline)
                result = box.run()
                self.assertEqual(result.returncode, 0, box.log + result.stderr)
                expected = (public_key(2) if baseline == "present" else b"") + box.supplied
                self.assertEqual(box.keys.read_bytes(), expected)
                self.assertEqual(box.state["metadata"][str(box.keys)], box.original_metadata)
                for prop in ["service.adb.tcp.port", "persist.adb.tcp.port"]:
                    self.assertEqual(box.state["properties"][prop], "5555")
                self.assertEqual(box.state["properties"]["init.svc.adbd"], "running")
                self.assertTrue((box.results / "done").is_file())
                self.assertFalse(box.trigger.exists())
                self.assertNotIn("ROLLBACK", box.log)
                snapshot = next(box.results.glob("attempt.*/adb_keys.raw"))
                self.assertEqual(snapshot.read_bytes(), box.original or b"")
                self.assertEqual((snapshot.parent / "metadata").read_text(), "1000 2000 640\n")
                self.assertEqual((snapshot.parent / "selinux").read_text(), LABEL + "\n")
                self.assertEqual((box.results / "adb_keys.before.state").read_text().strip(), baseline)
                backup = box.results / "adb_keys.before"
                if box.original is None:
                    self.assertFalse(backup.exists())
                else:
                    self.assertEqual(backup.read_bytes(), box.original)

    def test_standalone_and_busybox_base64_fallbacks(self) -> None:
        for tool in ["standalone", "busybox"]:
            with self.subTest(tool=tool):
                box = self.sandbox()
                box.state["base64_tool"] = tool
                self.assertEqual(box.run().returncode, 0, box.log)
                self.assertIn("Base64 implementation: " + tool, box.log)

    def test_post_mutation_failures_restore_all_three_key_baselines(self) -> None:
        failures = {
            "replace_before": "key replacement failed",
            "replace_after": "key replacement failed",
            "set_service.adb.tcp.port": "cannot set service port",
            "set_persist.adb.tcp.port": "cannot set persistent port",
            "stop_adbd": "cannot stop adbd",
            "start_adbd": "cannot start adbd",
            "adbd_start_timeout": "adbd did not start",
            "key_readback": "installed key bytes differ",
            "metadata_readback": "installed key metadata differs",
            "property_readback": "persistent port verification failed",
            "listener": "TCP 5555 did not enter LISTEN state",
        }
        for baseline in ["absent", "empty", "present"]:
            for fault, message in failures.items():
                with self.subTest(baseline=baseline, fault=fault):
                    box = self.sandbox(baseline, (fault,))
                    result = box.run()
                    self.assertNotEqual(result.returncode, 0, box.log)
                    self.assertIn(fault, box.state["fired"])
                    self.assertIn(message, box.log)
                    self.assertIn("ROLLBACK: verified", box.log)
                    self.assertNotIn("ROLLBACK FAILED", box.log)
                    self.assert_unchanged(box)

    def test_rollback_restores_original_stopped_daemon(self) -> None:
        box = self.sandbox(faults=("key_readback",))
        box.properties["init.svc.adbd"] = "stopped"
        box.state["properties"] = box.properties.copy()
        self.assertNotEqual(box.run().returncode, 0)
        self.assertIn("ROLLBACK: verified", box.log)
        self.assert_unchanged(box)

    def test_rollback_preserves_nondefault_owner_mode_and_label(self) -> None:
        box = self.sandbox(faults=("key_readback",))
        box.original_metadata = {
            "uid": 1001, "gid": 1002, "mode": "600",
            "label": "u:object_r:alternate_adb_keys:s0",
        }
        box.state["metadata"][str(box.keys)] = box.original_metadata.copy()
        self.assertNotEqual(box.run().returncode, 0)
        self.assertIn("ROLLBACK: verified", box.log)
        self.assert_unchanged(box)

    def test_concurrent_changes_are_preserved_without_installing_keys(self) -> None:
        for fault, baseline in [("concurrent_content", "present"), ("concurrent_metadata", "empty"), ("concurrent_creation", "absent")]:
            with self.subTest(fault=fault):
                box = self.sandbox(baseline, (fault,))
                self.assertNotEqual(box.run().returncode, 0)
                self.assertIn(fault, box.state["fired"])
                self.assertIn("before replacement", box.log)
                self.assertNotIn("ROLLBACK", box.log)
                self.assert_no_live_changes(box)
                self.assertFalse((box.results / "done").exists())
                if fault == "concurrent_metadata":
                    self.assertEqual(box.keys.read_bytes(), b"")
                    self.assertEqual(box.state["metadata"][str(box.keys)]["mode"], "400")
                else:
                    self.assertEqual(box.keys.read_bytes(), b"concurrent edit\n" if baseline == "present" else b"concurrent creation\n")

    def test_snapshot_sync_failure_does_not_mutate_configuration(self) -> None:
        box = self.sandbox(faults=("snapshot_sync",))
        self.assertNotEqual(box.run().returncode, 0)
        self.assertIn("cannot persist recovery snapshots", box.log)
        self.assertNotIn("ROLLBACK", box.log)
        self.assert_unchanged(box)
        self.assert_no_live_changes(box)

    def test_failed_rollback_is_reported_and_snapshot_is_retained(self) -> None:
        for failure in ["rollback_replace", "rollback_property"]:
            with self.subTest(failure=failure):
                box = self.sandbox(faults=("key_readback", failure))
                self.assertNotEqual(box.run().returncode, 0)
                self.assertIn(failure, box.state["fired"])
                self.assertIn("ROLLBACK FAILED", box.log)
                self.assertNotIn("ROLLBACK: verified", box.log)
                self.assertFalse((box.results / "done").exists())
                snapshot = next(box.results.glob("attempt.*/adb_keys.raw"))
                self.assertEqual(snapshot.read_bytes(), box.original)

    def test_invalid_supplied_key_and_symlink_target_fail_before_install(self) -> None:
        for invalid in ["key", "symlink"]:
            with self.subTest(invalid=invalid):
                box = self.sandbox()
                if invalid == "key":
                    (box.results / "adbkey.pub").write_bytes(b"invalid\n")
                else:
                    other = box.root / "other-keys"
                    box.keys.rename(other)
                    box.keys.symlink_to(other)
                self.assertNotEqual(box.run().returncode, 0)
                self.assertIn("invalid supplied public key" if invalid == "key" else "active key path is a symlink", box.log)
                self.assert_no_live_changes(box)
                self.assertEqual(box.keys.read_bytes(), box.original)

    def test_repeat_triggers_preserve_previous_log_and_configuration(self) -> None:
        for marker in ["started", "done"]:
            with self.subTest(marker=marker):
                box = self.sandbox()
                (box.results / marker).touch()
                (box.results / "result.txt").write_text("previous result\n")
                self.assertEqual(box.run().returncode, 0)
                self.assertEqual(box.log, "previous result\n")
                self.assertEqual(box.keys.read_bytes(), box.original)
                self.assertEqual(box.state["properties"], box.properties)
                self.assertTrue(box.trigger.exists())
                self.assertEqual([c["command"] for c in box.state["calls"]], ["dirname"])

    def test_preparation_source_pins_match_current_scripts(self) -> None:
        spec = importlib.util.spec_from_file_location("mi86_prepare_card", HERE / "prepare_card.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.check_sources()


if __name__ == "__main__":
    unittest.main(verbosity=2)
