#!/usr/bin/env python3
"""Offline-only guarded debug ramdisk builder for the documented verified boot.
Preserves the entire partition outside the existing ramdisk slot, ramdisk-size
field and Android SHA1 image ID. No USB, subprocesses, network, or flashing.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SOURCE_SHA = '2728e3c86a20b0a7ab73acc81a2bdca61096059d40c51a92f694560841ec1e61'
CPIO_SHA = 'c4f2e398a4a18693dd6cdab0be7483a67cf3296440558d01b046d07a0c944921'
DISK_SHA = '040f0a6f2d3a2b8b8da85069bedf1bcb37af26532ed2b7606edc8abb000eda78'
ADDITIONS = {'force_debuggable': b'',
             'adb_debug.prop': b'ro.debuggable=1\nro.force.debuggable=1\n'}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def align(n, unit):
    return (n+unit-1)//unit*unit

def components(image):
    require(image[:8] == b'ANDROID!', 'Not an Android image')
    require(struct.unpack_from('<II', image, 36) == (2048, 2), 'Unexpected page/version')
    require(struct.unpack_from('<I', image, 1644)[0] == 1660, 'Unexpected header size')
    result = {}; offset = 2048
    for name, field in [('kernel', 8), ('ramdisk', 16), ('second', 24),
                        ('recovery_dtbo', 1632), ('dtb', 1648)]:
        size = struct.unpack_from('<I', image, field)[0]
        require(offset+size <= len(image), 'Component exceeds image')
        result[name] = (offset, size, image[offset:offset+size])
        offset += align(size, 2048)
    require(result['recovery_dtbo'][1] == 0 and image[1636:1644] == bytes(8),
            'Unexpected recovery DTBO')
    return result, offset

def image_id(parts):
    digest = hashlib.sha1()
    for name in ['kernel', 'ramdisk', 'second', 'recovery_dtbo', 'dtb']:
        _, size, data = parts[name]
        digest.update(data); digest.update(struct.pack('<I', size))
    return digest.digest()

def newc(name, content, inode):
    name = name.encode()+b'\0'
    fields = [inode, 0o100644, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(name), 0]
    result = b'070701'+b''.join(f'{x:08x}'.encode() for x in fields)+name
    result += bytes(align(len(result), 4)-len(result))
    result += content
    return result+bytes(align(len(result), 4)-len(result))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path, help='Must not exist')
    args = parser.parse_args()
    original = args.source.read_bytes()
    require(len(original) == 67108864 and sha(original) == SOURCE_SHA, 'Unknown boot source')
    extraction = json.loads((args.source.parent/'manifest.json').read_text())
    require(extraction.get('gzip_eof_verified') is True and
            extraction.get('source_raw_sha256') == DISK_SHA, 'Unverified source extraction')
    require(any(p.get('name') == 'boot' and p.get('sha256') == SOURCE_SHA and
                p.get('bytes') == len(original) for p in extraction['partitions']),
            'Extraction manifest does not identify this boot')
    require(not args.output_dir.exists(), 'Output directory already exists')
    parts, end = components(original)
    require(original[576:596] == image_id(parts), 'Stock Android image ID mismatch')
    require(original[-64:-60] != b'AVBf', 'Unexpected AVB footer')
    raw = gzip.decompress(parts['ramdisk'][2])
    require(sha(raw) == CPIO_SHA, 'Unknown boot CPIO')
    spec = importlib.util.spec_from_file_location('recovery_builder',
                    Path(__file__).with_name('build-diagnostic-recovery.py'))
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    records = list(helper.cpio_records(raw))
    require(records[-1][0] == 'TRAILER!!!', 'Missing trailer')
    require(len({n for n, _, _ in records}) == len(records), 'Duplicate CPIO entries')
    require(not set(ADDITIONS).intersection(n.removeprefix('./') for n, _, _ in records),
            'Debug files already exist')
    inodes = [int(record[6:14], 16) for _, record, _ in records]
    next_inode = max(inodes)+1
    modified_raw = b''.join(record for _, record, _ in records[:-1])
    for i, (name, data) in enumerate(ADDITIONS.items()):
        modified_raw += newc(name, data, next_inode+i)
    modified_raw += records[-1][1]
    modified_raw += bytes(align(len(modified_raw), 512)-len(modified_raw))
    after = list(helper.cpio_records(modified_raw))
    by_name = {name: (record, data) for name, record, data in after}
    require(len(by_name) == len(records)+2, 'Unexpected modified entry count')
    for name, record, data in records:
        require(by_name[name] == (record, data), f'Original CPIO entry changed: {name}')
    for name, data in ADDITIONS.items():
        require(by_name[name][1] == data, 'Added content mismatch')
    compressed = gzip.compress(modified_raw, compresslevel=7, mtime=0)
    require(gzip.decompress(compressed) == modified_raw, 'Gzip round-trip failed')
    start, old_size, _ = parts['ramdisk']; slot = align(old_size, 2048)
    require(align(len(compressed), 2048) == slot, 'New ramdisk would relocate other components')
    result = bytearray(original)
    result[start:start+slot] = compressed+bytes(slot-len(compressed))
    struct.pack_into('<I', result, 16, len(compressed))
    newparts, newend = components(result)
    result[576:596] = image_id(newparts)
    require(newend == end, 'Declared image end changed')
    for name, (offset, size, data) in parts.items():
        if name != 'ramdisk':
            require(newparts[name] == (offset, size, data), f'Component changed: {name}')
    reverted = bytearray(result)
    for lo, hi in [(16, 20), (576, 596), (start, start+slot)]:
        reverted[lo:hi] = original[lo:hi]
    require(reverted == original, 'Unexpected bytes outside allowed intervals changed')
    require(result[end:] == original[end:], 'Partition tail changed')
    manifest = {
        'status': 'BUILT_VERIFIED_OFFLINE_NOT_FLASHED_NOT_BOOTED',
        'source_sha256': SOURCE_SHA, 'source_disk_sha256': DISK_SHA,
        'output_bytes': len(result), 'output_sha256': sha(result),
        'original_cpio_sha256': CPIO_SHA, 'modified_cpio_sha256': sha(modified_raw),
        'original_records_preserved': len(records),
        'added_files': [{'path': n, 'bytes': len(d), 'sha256': sha(d),
                         'uid': 0, 'gid': 0, 'mode': '0100644'} for n, d in ADDITIONS.items()],
        'ramdisk': {'offset': start, 'slot_bytes': slot, 'old_bytes': old_size,
                    'new_bytes': len(compressed), 'gzip_level': 7},
        'header_changes': ['ramdisk_size at 16:20', 'SHA1 image ID at 576:596'],
        'preserved_components': {n: {'offset': o, 'bytes': z, 'sha256': sha(d)}
                                 for n, (o, z, d) in parts.items() if n != 'ramdisk'},
        'tail': {'offset': end, 'bytes': len(original)-end,
                 'nonzero_bytes': sum(x != 0 for x in original[end:]),
                 'sha256': sha(original[end:]), 'preserved_at_original_offset': True},
        'avb_footer_found': False,
        'boot_avb0_magic_occurrences': original.count(b'AVB0'),
        'caveats': ['Preserving the tail does not preserve a signature over modified boot contents.',
                    'No conclusion that installed bootloader accepts modified boot.',
                    'Source vbmeta verification-disabled observations do not prove writable boot.',
                    'No tested restore/write route; firmware writes require separate authorization.',
                    'ADB authentication and ro.secure are not changed.',
                    'Output is the full 64 MiB partition, not a demonstrated flashable artifact.']}
    args.output_dir.mkdir(parents=True)
    (args.output_dir/'boot.img').write_bytes(result)
    require(sha((args.output_dir/'boot.img').read_bytes()) == sha(result), 'Output readback failed')
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'bytes': len(result), 'sha256': sha(result), 'ramdisk': manifest['ramdisk']}, indent=2))

if __name__ == '__main__':
    main()
