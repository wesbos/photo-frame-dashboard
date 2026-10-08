#!/usr/bin/env python3
"""Read-only GPT/FIT integrity checks and Rockusb 0xCC filler detection.

No third-party dependencies. Reports JSON without GPT UUIDs or payload contents.
A passing result validates only the checks named, never an entire device backup.
"""
import argparse
import hashlib
import json
import mmap
import struct
import sys
import zlib
from pathlib import Path


class InvalidImage(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidImage(message)


def region(data, offset, size):
    require(offset >= 0 and size >= 0 and offset + size <= len(data),
            f"Truncated/out-of-range region: offset={offset}, size={size}")
    return data[offset:offset + size]


def inspect_gpt(data, sector_size):
    sector = region(data, sector_size, sector_size)
    require(sector[:8] == b'EFI PART', 'Missing primary GPT signature at LBA 1')
    header_size, expected_crc = struct.unpack_from('<II', sector, 12)
    require(92 <= header_size <= sector_size, 'Invalid GPT header size')
    header = bytearray(sector[:header_size])
    header[16:20] = bytes(4)
    require(zlib.crc32(header) == expected_crc, 'GPT header CRC32 mismatch')
    current_lba = struct.unpack_from('<Q', header, 24)[0]
    require(current_lba == 1, 'Primary GPT current LBA is not 1')
    first_usable, last_usable = struct.unpack_from('<QQ', header, 40)
    entries_lba, count, entry_size, entries_crc = struct.unpack_from('<QIII', header, 72)
    require(first_usable <= last_usable and entries_lba >= 2, 'Invalid GPT bounds')
    require(count > 0 and entry_size >= 128 and entry_size % 128 == 0,
            'Invalid GPT entry dimensions')
    entries = region(data, entries_lba * sector_size, count * entry_size)
    require(zlib.crc32(entries) == entries_crc, 'GPT partition array CRC32 mismatch')
    partitions = []
    for i in range(count):
        entry = entries[i * entry_size:(i + 1) * entry_size]
        if entry[:16] == bytes(16):
            continue
        first, last = struct.unpack_from('<QQ', entry, 32)
        require(first_usable <= first <= last <= last_usable,
                f'Partition {i + 1} lies outside GPT usable bounds')
        name = entry[56:128].decode('utf-16-le', errors='replace').split('\0', 1)[0]
        partitions.append(dict(name=name, first_lba=first, sectors=last-first+1))
    ordered = sorted(partitions, key=lambda p: p['first_lba'])
    for previous, current in zip(ordered, ordered[1:]):
        require(previous['first_lba'] + previous['sectors'] <= current['first_lba'],
                'Overlapping GPT partitions')
    return dict(primary_header_crc32='valid', partition_array_crc32='valid',
                partitions=partitions, scope='Primary GPT only; backup GPT and partition payloads not validated')


def parse_fdt(data):
    header = struct.unpack('>10I', region(data, 0, 40))
    magic, total, struct_offset, strings_offset = header[:4]
    require(magic == 0xd00dfeed and total >= 40, 'Missing/invalid FDT header')
    require(total <= len(data), 'Truncated FDT')
    strings = region(data[:total], strings_offset, header[8])
    body = region(data[:total], struct_offset, header[9])
    offset, stack, nodes = 0, [], {}
    while offset < len(body):
        token = struct.unpack('>I', region(body, offset, 4))[0]
        offset += 4
        if token == 1:
            end = body.find(b'\0', offset)
            require(end >= offset, 'Unterminated FDT node')
            stack.append(body[offset:end].decode('ascii'))
            path = '/'.join(stack)
            require(path not in nodes, 'Duplicate FDT node')
            nodes[path] = {}
            offset = (end + 4) & ~3
        elif token == 2:
            require(bool(stack), 'Unbalanced FDT end node')
            stack.pop()
        elif token == 3:
            size, name_offset = struct.unpack('>II', region(body, offset, 8))
            offset += 8
            end = strings.find(b'\0', name_offset)
            require(stack and 0 <= name_offset < len(strings) and end >= name_offset,
                    'Invalid FDT property name')
            name = strings[name_offset:end].decode('ascii')
            props = nodes['/'.join(stack)]
            require(name not in props, 'Duplicate FDT property')
            props[name] = region(body, offset, size)
            offset = (offset + size + 3) & ~3
        elif token == 9:
            require(not stack, 'Unclosed FDT node')
            return nodes, total
        else:
            require(token == 4, 'Unknown FDT token')
    raise InvalidImage('Missing FDT end token')


def inspect_fit(data):
    nodes, total = parse_fdt(data)
    images = []
    for path, props in nodes.items():
        if not path.startswith('/images/') or path.count('/') != 2:
            continue
        if 'data' in props:
            payload = props['data']
        else:
            require(len(props.get('data-size', b'')) == 4, f'{path}: missing data size')
            size = struct.unpack('>I', props['data-size'])[0]
            key = 'data-position' if 'data-position' in props else 'data-offset'
            require(len(props.get(key, b'')) == 4, f'{path}: missing data location')
            offset = struct.unpack('>I', props[key])[0]
            if key == 'data-offset':
                offset += (total + 3) & ~3
            payload = region(data, offset, size)
        hashes = [p for n, p in nodes.items() if n.startswith(path + '/')
                  and n.count('/') == 3 and p.get('algo') == b'sha256\0']
        require(bool(hashes), f'{path}: no SHA-256 hash available')
        actual = hashlib.sha256(payload).digest()
        require(all(p.get('value') == actual for p in hashes), f'{path}: SHA-256 mismatch')
        images.append(dict(image=path, bytes=len(payload), sha256=actual.hex(), valid=True))
    require(bool(images), 'No FIT image components found')
    return dict(images=images, scope='FIT component SHA-256 integrity only; signatures not authenticated')


def cc_runs(data, block_size):
    """Find aligned complete blocks of filler; do not classify short tails."""
    needle = bytes([0xcc]) * block_size
    runs, start = [], None
    for offset in range(0, len(data) - block_size + 1, block_size):
        if data[offset:offset + block_size] == needle:
            if start is None:
                start = offset
        elif start is not None:
            runs.append(dict(offset=start, bytes=offset-start))
            start = None
    if start is not None:
        runs.append(dict(offset=start, bytes=(len(data)//block_size)*block_size-start))
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--kind', choices=['auto', 'gpt', 'fit', 'raw'], default='auto')
    parser.add_argument('--sector-size', type=int, default=512)
    parser.add_argument('--cc-block-size', type=int, default=4096)
    args = parser.parse_args()
    require(args.sector_size >= 512 and args.sector_size & (args.sector_size-1) == 0,
            'Sector size must be a power of two >=512')
    require(args.cc_block_size > 0, 'CC block size must be positive')
    report = dict(file=args.image.name, kind=args.kind)
    with args.image.open('rb') as file:
        require(args.image.stat().st_size > 0, 'Empty image')
        with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as data:
            report['bytes'] = len(data)
            kind = args.kind
            if kind == 'auto':
                if data[args.sector_size:args.sector_size+8] == b'EFI PART':
                    kind = 'gpt'
                elif data[:4] == bytes.fromhex('d00dfeed'):
                    kind = 'fit'
                else:
                    kind = 'raw'
            report['kind'] = kind
            report['cc_block_size'] = args.cc_block_size
            report['suspicious_cc_runs'] = cc_runs(data, args.cc_block_size)
            try:
                if kind == 'gpt':
                    report['checks'] = inspect_gpt(data, args.sector_size)
                elif kind == 'fit':
                    report['checks'] = inspect_fit(data)
                else:
                    report['checks'] = {'scope': 'Filler scan only; no format integrity validation'}
            except (InvalidImage, struct.error, UnicodeError) as error:
                report['error'] = str(error)
    failed = bool(report.get('error') or report['suspicious_cc_runs'])
    report['result'] = ('FAIL_OR_SUSPICIOUS' if failed else
                        'SCAN_ONLY_NO_CC_FOUND' if report['kind'] == 'raw' else
                        'NAMED_CHECKS_PASSED')
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, InvalidImage) as error:
        print(json.dumps({'result': 'ERROR', 'error': str(error)}))
        sys.exit(2)
