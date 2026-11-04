"""Host-only tests for data-patch-prepare.py --nulldev and emmc-macos.py verify-data.

Uses small image files in a temporary folder; never opens a real disk.
  python3 -I scripts/a33-uboot/test_data_patch.py
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
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


# Command doubles operate only on JSON byte arrays in a temporary directory. Bash evaluates
# the generated control flow; this does not simulate U-Boot hardware or prove hush behavior.
FAKE_COMMAND = r"""
import json, os, sys, zlib
from pathlib import Path
path = Path(os.environ["DATA_PATCH_FAKE"])
s = json.loads(path.read_text())
cmd, args = sys.argv[1], sys.argv[2:]
event = [cmd] + args
s['events'].append(event)
number = len(s['events'])
rc = 0
if number == s.get('fail'):
    rc = 1  # In particular a failed read leaves its old RAM buffer unchanged.
elif cmd == 'mmc':
    if args[0] == 'dev':
        s['selected'] = args[1] == '1'
        rc = 0 if s['selected'] else 1
    else:
        assert s['selected'], 'disk command before successful device selection'
        addr, sector, sectors = map(lambda x: int(x, 0), args[1:])
        lo, hi = sector * 512, (sector + sectors) * 512
        disk = bytearray.fromhex(s['disk'])
        if args[0] == 'read':
            data = disk[lo:hi]
            if number == s.get('corrupt_read'): data[0] ^= 1
            s['memory'][str(addr)] = data.hex()
        elif args[0] == 'write':
            data = bytes.fromhex(s['memory'][str(addr)])
            assert len(data) == hi-lo
            disk[lo:hi] = data
            s['disk'] = disk.hex()
            s['writes'].append(sector)
        else: raise AssertionError(args)
elif cmd == 'crc32':
    flag, addr, length, expected = args
    data = bytes.fromhex(s['memory'][str(int(addr, 0))])[:int(length, 0)]
    rc = 0 if zlib.crc32(data) == int(expected, 16) else 1
elif cmd == 'cmp.b':
    left, right, length = (int(x, 0) for x in args)
    rc = 0 if (bytes.fromhex(s['memory'][str(left)])[:length]
               == bytes.fromhex(s['memory'][str(right)])[:length]) else 1
elif cmd == 'ums': pass
else: raise AssertionError(event)
s['statuses'].append(rc)
path.write_text(json.dumps(s))
sys.exit(rc)
"""


class GeneratedScriptTests(DataPatchTests):
    def execute(self, *, restore=False, partial=False, fail=None, corrupt_read=None,
                unexpected=False, stale_flags=False, nulldev=None):
        # Use two real planner ranges/payloads, but no device files.
        output = self.tmp / 'out'
        if not output.exists(): self.run_prepare()
        plan = json.loads((output / 'plan.json').read_text())
        disk = bytearray(bytes(START * SECTOR) + bytes(self.edited if restore else self.orig))
        if partial:
            w = plan['writes'][0]
            at = w['sector'] * SECTOR
            disk[at:at+w['length']] = (output/w['orig_file']).read_bytes()
        if unexpected: disk[plan['writes'][-1]['sector'] * SECTOR] ^= 0x33
        state = dict(disk=disk.hex(), memory={}, selected=False, events=[], writes=[],
                     statuses=[], fail=fail, corrupt_read=corrupt_read)
        for w in plan['writes']:
            for kind in ('orig','new'):
                state['memory'][str(w[kind+'_addr'])] = (output/w[kind+'_file']).read_bytes().hex()
            # A failed first or phase-2 read must not be rescued by matching stale RAM.
            state['memory'][str(w['read_addr'])] = state['memory'][str(w[('new' if restore else 'orig')+'_addr'])]
        path=self.tmp/'fake-state.json'; path.write_text(json.dumps(state))
        fake=self.tmp/'fake-command.py'; fake.write_text(FAKE_COMMAND)
        command = f'"{sys.executable}" "{fake}"'
        harness = '\n'.join(f'{name}() {{ {command} {name} "$@"; }}'
                            for name in ('mmc','crc32','cmp.b','ums')) + '\n'
        if stale_flags: harness += 'all_ok=1; go=1; setenv() { return 1; }\n'
        script=(output/('restore-data.cmd' if restore else 'write-data.cmd')).read_text()
        if nulldev is not None:
            script=prepare.with_nulldev(script)
            # End the intentional infinite failure wait in the host harness only.
            harness += f'setenv() {{ return {0 if nulldev else 1}; }}\n'
            harness += 'sleep() { exit 0; }\n'
        env=dict(os.environ, DATA_PATCH_FAKE=str(path))
        result=subprocess.run(['bash','--noprofile','--norc'], input=harness+script,
                              text=True,capture_output=True,env=env,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('command not found',result.stderr)
        return json.loads(path.read_text()), plan

    def test_generated_install_restore_and_partial_undo(self):
        for restore, partial in ((False,False),(True,False),(True,True)):
            with self.subTest(restore=restore,partial=partial):
                got, plan=self.execute(restore=restore,partial=partial,stale_flags=True)
                expected=self.orig if restore else self.edited
                self.assertEqual(bytes.fromhex(got['disk'])[START*SECTOR:],expected)
                self.assertEqual(got['writes'],[w['sector'] for w in plan['writes'][1 if partial else 0:]])

    def test_every_successful_device_or_payload_command_can_fail_closed(self):
        for restore in (False, True):
            baseline,_=self.execute(restore=restore)
            for index,(event,status) in enumerate(zip(baseline['events'],baseline['statuses']),1):
                if status or event[0]=='ums': continue
                with self.subTest(restore=restore,failed=event,index=index):
                    got,_=self.execute(restore=restore,fail=index,stale_flags=True)
                    # Even when UMS returns, a failure cannot fall through into later writes.
                    self.assertFalse(any(e[:2]==['mmc','write'] for e in got['events'][index:]))
                    if not any(e[:2]==['mmc','write'] for e in baseline['events'][:index-1]):
                        self.assertEqual(got['writes'],[])

    def test_readback_mismatch_stops_before_next_range(self):
        for restore in (False,True):
            baseline,_=self.execute(restore=restore)
            first_write=next(i for i,e in enumerate(baseline['events']) if e[:2]==['mmc','write'])
            readback=first_write+2  # one-based command number, immediately after write
            got,_=self.execute(restore=restore,corrupt_read=readback)
            self.assertEqual(len(got['writes']),1)
            self.assertFalse(any(e[:2]==['mmc','write'] for e in got['events'][readback:]))

    def test_unknown_range_prevents_all_writes(self):
        for restore in (False,True):
            got,_=self.execute(restore=restore,unexpected=True)
            self.assertEqual(got['writes'],[])

    def test_null_console_failure_never_enters_writer(self):
        for restore in (False,True):
            got,_=self.execute(restore=restore,nulldev=False)
            self.assertEqual(got['events'],[])
            self.assertEqual(got['writes'],[])
            got,_=self.execute(restore=restore,nulldev=True)
            self.assertEqual(len(got['writes']),2)

    def test_prepare_rejects_negative_and_partial_sector_inputs(self):
        with unittest.mock.patch.object(sys,'argv',['data-patch-prepare.py',str(self.tmp/'orig.img'),
                                                   str(self.tmp/'edited.img'),'-1']):
            with self.assertRaisesRegex(SystemExit,'nonnegative'): prepare.main()
        (self.tmp/'orig.img').write_bytes(b'a'*513)
        (self.tmp/'edited.img').write_bytes(b'b'*513)
        with self.assertRaisesRegex(SystemExit,'whole-sector'): self.run_prepare()

    def test_prepare_rejects_empty_changes_and_buffer_overflow(self):
        (self.tmp/'edited.img').write_bytes(self.orig)
        with self.assertRaisesRegex(SystemExit,'no changed sectors'): self.run_prepare()
        (self.tmp/'edited.img').write_bytes(self.edited)
        with unittest.mock.patch.object(prepare,'BUFFER_END',prepare.BASE_ADDR + 3*prepare.SLOT):
            with self.assertRaisesRegex(SystemExit,'RAM buffer window'): self.run_prepare()
        self.assertFalse(prepare.OUT.exists())

    def test_verify_rejects_negative_offsets_and_payload_escape(self):
        self.run_prepare()
        disk=self.disk(self.orig)
        self.edit_plan(lambda p:p['writes'][0].update(sector=-1))
        self.verify_fails(disk,'invalid sector')
        self.edit_plan(lambda p:p['writes'][0].update(sector=10,orig_file='../outside'))
        self.verify_fails(disk,'inside the plan folder')


if __name__ == "__main__":
    unittest.main()
