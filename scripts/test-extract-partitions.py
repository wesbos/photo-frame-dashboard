#!/usr/bin/env python3
"""Synthetic extraction checks; no device or proprietary firmware required."""
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib


def disk_image():
    disk = bytearray(4 * 1024 * 1024)
    entries = bytearray(128 * 128)
    partitions = [('boot', 2048, 32), ('recovery', 2080, 32), ('super', 2112, 1024)]
    for i, (name, start, count) in enumerate(partitions):
        offset = i * 128
        entries[offset:offset+16] = bytes([i+1]) * 16
        struct.pack_into('<QQ', entries, offset+32, start, start+count-1)
        label = name.encode('utf-16-le')
        entries[offset+56:offset+56+len(label)] = label
        disk[start*512:(start+count)*512] = bytes([i+41]) * (count*512)
    disk[1024:1024+len(entries)] = entries
    header = bytearray(92)
    header[:8] = b'EFI PART'
    struct.pack_into('<IIII', header, 8, 0x10000, 92, 0, 0)
    struct.pack_into('<QQQQ', header, 24, 1, len(disk)//512-1, 34, len(disk)//512-34)
    struct.pack_into('<QIII', header, 72, 2, 128, 128, zlib.crc32(entries))
    struct.pack_into('<I', header, 16, zlib.crc32(header))
    disk[512:604] = header
    return disk, partitions


class ExtractTests(unittest.TestCase):
    def test_integrity_and_failures(self):
        raw, parts = disk_image()
        for mode in ['good', 'wronghash', 'truncated', 'badgpt', 'bounds',
                     'probe_good', 'probe_badhash', 'probe_mismatch']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                payload = bytearray(raw)
                if mode == 'badgpt':
                    payload[1028] ^= 1
                compressed = gzip.compress(payload)
                if mode == 'truncated':
                    compressed = compressed[:-8]
                source = root / 'disk.img.gz'
                source.write_bytes(compressed)
                record = dict(format='gzip', start_sector=0, sector_bytes=512,
                              gzip_readback_verified=True, raw_bytes=len(payload),
                              sectors=len(payload)//512, compressed_bytes=len(compressed),
                              raw_sha256=hashlib.sha256(payload).hexdigest())
                if mode == 'wronghash':
                    record['raw_sha256'] = '0' * 64
                if mode == 'bounds':
                    record['raw_bytes'] = 2048*512
                    record['sectors'] = 2048
                Path(str(source)+'.json').write_text(json.dumps(record))
                output = root / 'extracted'
                command = [sys.executable, str(Path(__file__).with_name('extract-partitions.py')),
                           str(source), '--output-dir', str(output)]
                if mode.startswith('probe_'):
                    # Straddle a streaming boundary to test partial comparisons.
                    sample = bytes(payload[1024*1024-512:1024*1024+512])
                    if mode == 'probe_mismatch':
                        sample = bytes([sample[0] ^ 1]) + sample[1:]
                    (root/'probe.img').write_bytes(sample)
                    sample_hash = hashlib.sha256(sample).hexdigest()
                    if mode == 'probe_badhash':
                        sample_hash = '0'*64
                    probe = dict(validated=True, samples=[dict(file='probe.img',
                                 lba=2047, bytes=1024, sha256=sample_hash)])
                    (root/'probes.json').write_text(json.dumps(probe))
                    command += ['--probe-manifest', str(root/'probes.json')]
                result = subprocess.run(command, capture_output=True, text=True)
                if mode in ('good', 'probe_good'):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    manifest = json.loads((output/'manifest.json').read_text())
                    self.assertEqual(len(manifest['partitions']), 3)
                    for name, start, count in parts:
                        self.assertEqual((output/(name+'.img')).read_bytes(),
                                         payload[start*512:(start+count)*512])
                    retry = subprocess.run(command, capture_output=True, text=True)
                    self.assertNotEqual(retry.returncode, 0)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertFalse(list(output.glob('*.img')))
                    self.assertFalse((output/'manifest.json').exists())
                self.assertEqual(source.read_bytes(), compressed)


if __name__ == '__main__':
    unittest.main()
