#!/usr/bin/env python3
"""Exercise FIFO backup validation with synthetic tools; never contacts USB."""

import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class BackupTests(unittest.TestCase):
    def test_mock_cases(self):
        wrapper = Path(__file__).with_name("backup-flash.py")
        for mode in ("good", "cc", "truncated", "failed", "timeout"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                tool = root / "mock-reader"
                tool.write_text(f"#!{sys.executable}\n" + '''
import os, sys, time
assert sys.argv[1:3] == ['rl', '0']
mode = os.environ['MOCK_MODE']
if mode == 'timeout':
    time.sleep(30)
    sys.exit(0)
size = int(sys.argv[3]) * 512
data = bytes(range(256)) * (size // 256)
if mode == 'cc':
    data = data[:123] + b'\\xcc' * 65536 + data[123 + 65536:]
if mode == 'truncated':
    data = data[:-512]
# libc fopen("wb+") used by rkdeveloptool works on a FIFO; Python's
# BufferedRandom additionally demands seekability, so model its fd directly.
with os.fdopen(os.open(sys.argv[4], os.O_RDWR), 'wb') as output:
    for offset in range(0, len(data), 7000):
        output.write(data[offset:offset + 7000])
print('Read LBA to file (100%)', flush=True)
if mode == 'failed':
    print('Read LBA failed!', flush=True)
''')
                tool.chmod(0o700)
                output = root / "backup.img.gz"
                command = [sys.executable, str(wrapper), "--tool", str(tool),
                           "--sectors", "512", "--output", str(output),
                           "--timeout", "0.5" if mode == "timeout" else "10"]
                result = subprocess.run(command, env={**os.environ, "MOCK_MODE": mode},
                                        capture_output=True, text=True, timeout=15)
                if mode == "good":
                    self.assertEqual(result.returncode, 0, result.stderr)
                    expected = bytes(range(256)) * 1024
                    self.assertEqual(gzip.decompress(output.read_bytes()), expected)
                    manifest = json.loads(Path(str(output) + ".json").read_text())
                    self.assertEqual(manifest["raw_sha256"], hashlib.sha256(expected).hexdigest())
                    self.assertEqual(manifest["compressed_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
                    self.assertEqual(manifest["raw_bytes"], len(expected))
                    self.assertFalse(Path(str(output) + ".partial").exists())
                    retry = subprocess.run(command, env={**os.environ, "MOCK_MODE": mode},
                                           capture_output=True, text=True, timeout=15)
                    self.assertNotEqual(retry.returncode, 0)
                    self.assertIn("Refusing existing path", retry.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertFalse(output.exists())
                    self.assertTrue(Path(str(output) + ".partial").exists())
                    message = {"cc": "0xCC filler", "truncated": "Truncated backup",
                               "failed": "unambiguous", "timeout": "exceeded"}[mode]
                    self.assertIn(message, result.stderr)


if __name__ == "__main__":
    unittest.main()
