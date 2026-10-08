#!/usr/bin/env python3
"""Build the D156 Wi-Fi startup boot image offline from verified debug boot.

Only adb_debug.prop, ramdisk padding, ramdisk-size and Android image ID change.
The referenced init wrapper must be installed on first-stage-mounted /metadata
before this image is written. This program never accesses the device.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    b = load('debug_boot', 'build-debug-boot.py')
    c = load('cpio_builder', 'build-diagnostic-recovery.py')
    original = args.source.read_bytes()
    b.require(b.sha(original) == 'f6e2c27c89a3db7835089fa8037909dc5e7eb62745eb90471fabab58b49821b3',
              'Source is not the verified installed debug boot')
    b.require(not args.output_dir.exists(), 'Output directory already exists')
    parts, end = b.components(original)
    b.require(original[576:596] == b.image_id(parts), 'Bad source image ID')
    records = list(c.cpio_records(gzip.decompress(parts['ramdisk'][2])))
    prop = b'ro.debuggable=1\nro.force.debuggable=1\nro.boot.init_rc=/metadata/skylight-wifi/init.rc\n'
    changed = []
    found = 0
    for name, record, data in records:
        if name == 'adb_debug.prop':
            b.require(data == b'ro.debuggable=1\nro.force.debuggable=1\n', 'Unexpected debug properties')
            record = b.newc(name, prop, int(record[6:14], 16))
            found += 1
        changed.append(record)
    b.require(found == 1, 'Expected exactly one debug property entry')
    raw = b''.join(changed)
    raw += bytes(b.align(len(raw), 512) - len(raw))
    after = list(c.cpio_records(raw))
    b.require(len(after) == len(records), 'Entry count changed')
    for before, current in zip(records, after):
        if before[0] != 'adb_debug.prop':
            b.require(before == current, 'Unrelated CPIO entry changed')
        else:
            b.require(current[2] == prop, 'Property content mismatch')
    compressed = gzip.compress(raw, compresslevel=7, mtime=0)
    start, size, _ = parts['ramdisk']
    slot = b.align(size, 2048)
    b.require(b.align(len(compressed), 2048) == slot, 'Would relocate boot components')
    result = bytearray(original)
    result[start:start + slot] = compressed + bytes(slot - len(compressed))
    struct.pack_into('<I', result, 16, len(compressed))
    newparts, newend = b.components(result)
    result[576:596] = b.image_id(newparts)
    b.require(newend == end, 'Image end moved')
    for name in parts:
        if name != 'ramdisk':
            b.require(parts[name] == newparts[name], f'{name} changed')
    reverted = bytearray(result)
    for lo, hi in [(16, 20), (576, 596), (start, start + slot)]:
        reverted[lo:hi] = original[lo:hi]
    b.require(reverted == original, 'Unexpected bytes changed')
    args.output_dir.mkdir(parents=True)
    (args.output_dir / 'boot.img').write_bytes(result)
    manifest = {
        'source_sha256': b.sha(original), 'output_sha256': b.sha(result),
        'bytes': len(result), 'ramdisk_bytes': len(compressed),
        'ramdisk_slot_bytes': slot, 'modified_cpio_file': 'adb_debug.prop',
        'init_rc': '/metadata/skylight-wifi/init.rc',
        'preserved': ['kernel', 'resource/second', 'dtb', 'partition tail', 'all other CPIO records'],
        'requires': 'Install and verify metadata init wrapper before writing boot; preserve it across resets.'
    }
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    b.require(b.sha((args.output_dir / 'boot.img').read_bytes()) == manifest['output_sha256'],
              'File readback mismatch')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
