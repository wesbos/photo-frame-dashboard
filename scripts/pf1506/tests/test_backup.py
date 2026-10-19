#!/usr/bin/env python3
"""End-to-end mocked transfers with byte constants scaled down, not real partitions."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
HERE = Path(__file__).resolve().parent
class BackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'bin').mkdir()
        (self.root/'bin/adb').symlink_to(HERE/'mock_adb.py')
        self.env = dict(os.environ, PATH=str(self.root/'bin')+os.pathsep+os.environ['PATH'])
        # Exercise the actual script's transfer/verification/order/manifest logic at 1 KiB.
        source=(HERE.parent/'backup.sh').read_text().replace('2147483648','1024').replace('33554432','16')
        (self.root/'backup.sh').write_text(source)
    def tearDown(self): self.tmp.cleanup()
    def run_script(self):
        return subprocess.run(['/bin/bash',str(self.root/'backup.sh'),str(self.root/'output')],
                              env=self.env,capture_output=True,text=True,timeout=20)
    def test_retained_manifest_and_chunk_transfer_evidence(self):
        r=self.run_script()
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        output=self.root/'output'
        lines=(output/'MANIFEST.sha256.txt').read_text().splitlines()
        self.assertEqual(len(lines),12)
        self.assertFalse(any('super.' in l and not l.endswith('super.img') for l in lines))
        for line in lines:
            digest,name=line.split()
            self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(),digest)
        chunks=(output/'TRANSFER-CHUNKS.sha256.txt').read_text().splitlines()
        self.assertEqual([line.split()[1] for line in chunks],[f'super.{i}' for i in range(64)])
        self.assertFalse(list(output.glob('super.[0-9]*')))
        self.assertEqual((output/'super.img').read_bytes(),b''.join(bytes([i])*16 for i in range(64)))
    def test_mismatch_stops_before_success(self):
        self.env['PF1506_BAD_HASH']='boot'
        r=self.run_script()
        self.assertNotEqual(r.returncode,0)
        self.assertIn('MISMATCH',r.stderr)
        self.assertFalse((self.root/'output/super.img').exists())
        self.assertNotIn('Done.',r.stdout)
if __name__ == '__main__': unittest.main()
