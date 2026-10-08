#!/usr/bin/env python3
"""Build a diagnostic recovery for the one validated firmware documented here.

Local files only: never contacts USB, boots, flashes, or changes the calendar.
Requires the verified extraction manifest and pinned AOSP mkbootimg. Changes
exactly three bytes in /prop.default; verifies all declared other components.
An unreferenced partition tail is intentionally omitted, not silently preserved.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

SOURCE_SHA256 = 'c151881e17a158362968267cc3a591858e300a0dfc0fdd587ab129ce44f1af13'
DISK_SHA256 = '040f0a6f2d3a2b8b8da85069bedf1bcb37af26532ed2b7606edc8abb000eda78'
CPIO_SHA256 = 'f4537e5395951ba254e9e25299362fbab5130f1f63dba032b2d259cb7444baad'
PROP_SHA256 = '53414700b2bd5b8c0dad69d8c85f188a75672b708fa7b612a53c36dc81f072cf'
MKBOOTIMG_SHA256 = '2a8d05d34110f66c463668f43fc812ce2e46e66459c347eaadb080271df69aa8'
MKBOOTIMG_COMMIT = 'b7c1a63df33e6763d2482bc9d33007f67706d131'
TRIM_MODULES = {
    'pcba/lib/modules/rkwifi/bcmdhd/bcmdhd.ko',
    'pcba/lib/modules/rtl8723cs/8723cs.ko',
    'pcba/lib/modules/rtl8821cs/8821cs.ko',
    'pcba/lib/modules/rtl8822bs/8822bs.ko',
}
AP6256_ASSETS = {
    'pcba/lib/modules/rkwifi/bcmdhd/bcmdhd.ko',
    'vendor/etc/firmware/fw_bcm43456c5_ag.bin',
    'vendor/etc/firmware/nvram_ap6256.txt',
    'vendor/etc/firmware/config.txt',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def align(number, page):
    return (number + page - 1) // page * page


def parse_image(data):
    require(len(data) >= 1660 and data[:8] == b'ANDROID!', 'Invalid Android header')
    page, version = struct.unpack_from('<II', data, 36)
    require(page == 2048 and version == 2, 'Only the documented 2048-byte/v2 image is supported')
    require(struct.unpack_from('<I', data, 1644)[0] == 1660, 'Unexpected v2 header size')
    sizes = dict(kernel=struct.unpack_from('<I', data, 8)[0],
                 ramdisk=struct.unpack_from('<I', data, 16)[0],
                 second=struct.unpack_from('<I', data, 24)[0],
                 recovery_dtbo=struct.unpack_from('<I', data, 1632)[0],
                 dtb=struct.unpack_from('<I', data, 1648)[0])
    components, offset = {}, page
    for name, size in sizes.items():
        if name == 'recovery_dtbo':
            require(struct.unpack_from('<Q', data, 1636)[0] == offset,
                    'Recovery DTBO offset differs from sequential layout')
        require(size > 0 and offset+size <= len(data), f'Invalid component bounds: {name}')
        components[name] = data[offset:offset+size]
        offset += align(size, page)
    # Independent Android v2 image-ID calculation.
    digest = hashlib.sha1()
    for name in ['kernel', 'ramdisk', 'second']:
        digest.update(components[name])
        digest.update(struct.pack('<I', sizes[name]))
    digest.update(components['recovery_dtbo'])
    digest.update(struct.pack('<I', sizes['recovery_dtbo']))
    digest.update(components['dtb'])
    digest.update(struct.pack('<I', sizes['dtb']))
    require(data[576:596] == digest.digest(), 'Android image ID mismatch')
    return components, offset


def patch_cpio(cpio):
    require(sha(cpio) == CPIO_SHA256, 'Unrecognized stock recovery CPIO')
    offset, matches = 0, []
    while offset < len(cpio):
        require(cpio[offset:offset+6] == b'070701', 'Unsupported CPIO header')
        fields = [int(cpio[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        offset += 110
        require(namesize > 0 and offset+namesize <= len(cpio), 'CPIO filename exceeds bounds')
        name = cpio[offset:offset+namesize-1]
        offset = align(offset+namesize, 4)
        if name == b'TRAILER!!!':
            break
        require(offset+size <= len(cpio), 'CPIO content exceeds bounds')
        if name in (b'prop.default', b'./prop.default'):
            matches.append((offset, size))
        offset = align(offset+size, 4)
    require(len(matches) == 1, 'Expected exactly one /prop.default entry')
    offset, size = matches[0]
    props = cpio[offset:offset+size]
    require(sha(props) == PROP_SHA256, 'Unrecognized /prop.default contents')
    changes = [('ro.secure=1', 'ro.secure=0'), ('ro.adb.secure=1', 'ro.adb.secure=0'),
               ('ro.debuggable=0', 'ro.debuggable=1')]
    patched = bytearray(cpio)
    locations = []
    for before, after in changes:
        needle, replacement = (before+'\n').encode(), (after+'\n').encode()
        require(props.count(needle) == 1, f'Expected one property: {before}')
        local = props.index(needle)
        require(local == 0 or props[local-1] == 10, 'Property is not a standalone line')
        position = offset+local
        patched[position:position+len(needle)] = replacement
        locations.append(position+len(needle)-2)
    require(all(cpio[i] != patched[i] for i in locations), 'Property edit failed')
    # Reverse exactly the expected edits and require complete archive equality.
    reverted = bytearray(patched)
    for i in locations:
        reverted[i] = cpio[i]
    require(reverted == cpio, 'Unexpected CPIO bytes changed')
    return bytes(patched), changes


def cpio_records(cpio):
    """Yield unchanged complete newc records, including the trailer."""
    offset = 0
    while offset < len(cpio):
        start = offset
        require(cpio[offset:offset+6] == b'070701', 'Unsupported CPIO record')
        fields = [int(cpio[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        offset += 110
        require(namesize > 0 and offset+namesize <= len(cpio), 'Invalid CPIO name bounds')
        name = cpio[offset:offset+namesize-1].decode('utf-8')
        offset = align(offset+namesize, 4)
        content = cpio[offset:offset+size]
        require(len(content) == size, 'Truncated CPIO record')
        offset = align(offset+size, 4)
        yield name, cpio[start:offset], content
        if name == 'TRAILER!!!':
            require(not any(cpio[offset:]), 'Unexpected nonzero CPIO tail')
            return
    raise ValueError('Missing CPIO trailer')


def trim_pcba_modules(cpio, broadcom_firmware=False, wifi_profile='ap6256'):
    modules_to_remove = set(TRIM_MODULES)
    bcm_module = 'pcba/lib/modules/rkwifi/bcmdhd/bcmdhd.ko'
    ssv_module = 'pcba/lib/modules/ssv6x5x/ssv6x5x.ko'
    keep_firmware = set()
    if wifi_profile == 'ap6256':
        modules_to_remove.remove(bcm_module)
        modules_to_remove.add(ssv_module)
        keep_firmware.add('vendor/etc/firmware/fw_bcm43456c5_ag.bin')
    records, removed, remaining = [], [], {}
    for name, record, content in cpio_records(cpio):
        require(name not in remaining, 'Duplicate CPIO name')
        firmware = (broadcom_firmware and name.startswith('vendor/etc/firmware/fw_bcm')
                    and name not in keep_firmware)
        if name in modules_to_remove or firmware:
            removed.append(dict(path=name, bytes=len(content), sha256=sha(content)))
        else:
            remaining[name] = sha(record)
            records.append(record)
    modules = [p for p in removed if p['path'] in modules_to_remove]
    require({p['path'] for p in modules} == modules_to_remove and len(modules) == 4,
            'Expected all four profile-specific unused PCBA modules exactly once')
    firmware = [p for p in removed if p['path'] not in modules_to_remove]
    expected_count = 50 if wifi_profile == 'ap6256' else 51
    expected_bytes = 24605602 - (606190 if wifi_profile == 'ap6256' else 0)
    require((not broadcom_firmware and not firmware) or
            (broadcom_firmware and len(firmware) == expected_count and
             sum(p['bytes'] for p in firmware) == expected_bytes),
            'Unexpected documented Broadcom firmware set')
    required = AP6256_ASSETS if wifi_profile == 'ap6256' else {ssv_module}
    require(required <= remaining.keys(), 'Missing required Wi-Fi profile assets')
    result = b''.join(records)
    result += bytes(align(len(result), 512)-len(result))
    require({name: sha(record) for name, record, _ in cpio_records(result)} == remaining,
            'A retained CPIO entry changed during trimming')
    return result, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--source-manifest', type=Path, help='Defaults to source parent/manifest.json')
    parser.add_argument('--mkbootimg', required=True, type=Path, help='Pinned AOSP Python script')
    parser.add_argument('--output-dir', required=True, type=Path, help='Must be new')
    parser.add_argument('--trim-pcba-modules', action='store_true',
                        help='Remove exactly four unused profile-specific PCBA modules')
    parser.add_argument('--trim-broadcom-firmware', action='store_true',
                        help='Remove unused fw_bcm* assets while preserving the selected Wi-Fi profile')
    parser.add_argument('--wifi-profile', choices=['ap6256', 'ssv6x5x'], default='ap6256',
                        help='ap6256 matches live hardware; ssv6x5x only reproduces the obsolete DTB-based candidate')
    args = parser.parse_args()
    require(not args.trim_broadcom_firmware or args.trim_pcba_modules,
            'Broadcom firmware trimming requires --trim-pcba-modules')
    source = args.source.read_bytes()
    require(sha(source) == SOURCE_SHA256, 'Source recovery does not match documented firmware')
    manifest_path = args.source_manifest or args.source.parent/'manifest.json'
    extraction = json.loads(manifest_path.read_text())
    require(extraction.get('gzip_eof_verified') is True and
            extraction.get('source_raw_sha256') == DISK_SHA256,
            'Require extraction from the validated full-disk source')
    matches = [p for p in extraction.get('partitions', []) if p.get('name') == 'recovery']
    require(len(matches) == 1 and matches[0].get('sha256') == SOURCE_SHA256
            and matches[0].get('bytes') == len(source), 'Extraction manifest recovery mismatch')
    require(sha(args.mkbootimg.read_bytes()) == MKBOOTIMG_SHA256, 'Unrecognized mkbootimg script')
    original, end = parse_image(source)
    cpio = gzip.decompress(original['ramdisk'])
    patched, changes = patch_cpio(cpio)
    removed = []
    if args.trim_pcba_modules:
        patched, removed = trim_pcba_modules(patched, args.trim_broadcom_firmware, args.wifi_profile)
    args.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    # Intermediate files remain local; payload paths contain no shell expansion.
    payloads = args.output_dir/'components'
    payloads.mkdir(mode=0o700)
    for name, content in original.items():
        if name == 'ramdisk':
            content = gzip.compress(patched, compresslevel=9, mtime=0)
        (payloads/name).write_bytes(content)
    command = [sys.executable, str(args.mkbootimg), '--header_version', '2', '--pagesize', '2048',
               '--base', '0', '--os_version', '12.0.0', '--os_patch_level', '2022-03']
    for name in original:
        command += ['--'+name, str(payloads/name)]
    for name, position, fmt in [('kernel', 12, '<I'), ('ramdisk', 20, '<I'),
                               ('second', 28, '<I'), ('tags', 32, '<I'), ('dtb', 1652, '<Q')]:
        command += ['--'+name+'_offset', str(struct.unpack_from(fmt, source, position)[0])]
    board = source[48:64].split(b'\0', 1)[0].decode()
    cmdline = (source[64:576].split(b'\0', 1)[0] +
               source[608:1632].split(b'\0', 1)[0]).decode()
    partial = args.output_dir/'recovery.img.partial'
    command += ['--board', board, '--cmdline', cmdline, '--output', str(partial)]
    subprocess.run(command, check=True)
    candidate = partial.read_bytes()
    if args.trim_pcba_modules:
        require(len(candidate) < 64*1024*1024, 'Trimmed image does not fit the 64 MiB download limit')
    rebuilt, candidate_end = parse_image(candidate)
    require(candidate_end == len(candidate), 'Unexpected candidate trailing data')
    for name in original:
        if name != 'ramdisk':
            require(original[name] == rebuilt[name], f'Changed declared component: {name}')
    require(gzip.decompress(rebuilt['ramdisk']) == patched, 'Rebuilt ramdisk mismatch')
    # Ramdisk size, image ID, and DTBO location are the only changing header fields.
    for start, stop in [(0, 16), (20, 576), (608, 1636), (1644, 1660)]:
        require(source[start:stop] == candidate[start:stop], 'Unexpected boot-header change')
    report = dict(status='BUILT_AND_VERIFIED_OFFLINE_NOT_BOOTED', source_recovery_sha256=SOURCE_SHA256,
                  candidate_sha256=sha(candidate), candidate_bytes=len(candidate),
                  mkbootimg_commit=MKBOOTIMG_COMMIT, mkbootimg_sha256=MKBOOTIMG_SHA256,
                  changes=[dict(before=a, after=b) for a, b in changes], cpio_property_bytes_changed=3,
                  removed_cpio_entries=removed,
                  wifi_profile=args.wifi_profile if args.trim_pcba_modules else 'all-stock-assets',
                  retained_wifi_assets=[dict(path=n, bytes=len(c), sha256=sha(c))
                                        for n, _, c in cpio_records(patched) if n in AP6256_ASSETS],
                  cpio_change_scope='Three property bytes; optional exact module/firmware record removals. All retained record metadata preserved.',
                  unchanged_components={n: dict(bytes=len(v), sha256=sha(v))
                                        for n, v in original.items() if n != 'ramdisk'},
                  unreferenced_source_partition_tail=dict(bytes=len(source)-end, preserved=False,
                                                         avb_footer_found=source[-64:-60] == b'AVBf'),
                  note='Declared components preserved; source partition tail omitted. No USB operations performed.')
    with (args.output_dir/'manifest.json.partial').open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    os.link(partial, args.output_dir/'recovery.img')
    partial.unlink()
    os.link(args.output_dir/'manifest.json.partial', args.output_dir/'manifest.json')
    (args.output_dir/'manifest.json.partial').unlink()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, EOFError, struct.error, subprocess.CalledProcessError) as error:
        print(f'Build failed: {error}', file=sys.stderr)
        sys.exit(1)
