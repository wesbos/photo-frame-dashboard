#!/usr/bin/env python3
"""Extract selected GPT partitions from a validated full-flash gzip backup.

Reads the compressed source once without expanding the whole disk. Requires the
backup-flash.py manifest and checks its whole-disk raw SHA-256 and byte count.
Only publishes .img names after reaching gzip EOF and passing all checks.
Failed runs retain .partial outputs for diagnosis; they are not valid images.
"""

import argparse
from contextlib import ExitStack
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--manifest', type=Path, help='Defaults to SOURCE.json')
    parser.add_argument('--probe-manifest', type=Path,
                        help='Compare saved independent read samples at their exact LBAs')
    parser.add_argument('--output-dir', required=True, type=Path, help='Must not already exist')
    parser.add_argument('--partitions', nargs='+', default=['boot', 'recovery', 'super'])
    args = parser.parse_args()
    require(len(set(args.partitions)) == len(args.partitions), 'Duplicate requested partitions')
    require(all(re.fullmatch(r'[A-Za-z0-9_-]+', n) for n in args.partitions),
            'Partition names must contain only letters, digits, hyphens, underscores')
    manifest_path = args.manifest or Path(str(args.source) + '.json')
    record = json.loads(manifest_path.read_text())
    require(record.get('format') == 'gzip' and record.get('start_sector') == 0
            and record.get('sector_bytes') == 512 and record.get('gzip_readback_verified') is True,
            'Require a validated gzip full-disk manifest with 512-byte sectors')
    expected = record.get('raw_bytes')
    sectors = record.get('sectors')
    require(isinstance(expected, int) and isinstance(sectors, int)
            and 0 < sectors <= 0xffffffff and expected == sectors * 512,
            'Invalid expected disk size')
    require(bool(re.fullmatch('[0-9a-f]{64}', record.get('raw_sha256', ''))),
            'Invalid manifest raw SHA-256')
    require(args.source.stat().st_size == record.get('compressed_bytes'),
            'Compressed file size differs from manifest')
    probes = []
    if args.probe_manifest:
        probe_record = json.loads(args.probe_manifest.read_text())
        require(probe_record.get('validated') is True, 'Probe manifest is not marked validated')
        samples = probe_record.get('samples')
        require(isinstance(samples, list) and 0 < len(samples) <= 256,
                'Require 1..256 independent samples')
        for sample in samples:
            name, lba, size = sample.get('file'), sample.get('lba'), sample.get('bytes')
            require(isinstance(name, str) and Path(name).name == name and name not in ('.', '..'),
                    'Probe filename must be a basename beside its manifest')
            require(isinstance(lba, int) and lba >= 0 and isinstance(size, int)
                    and 0 < size <= 16 * 1024 * 1024 and lba * 512 + size <= expected,
                    'Probe range is invalid or exceeds 16 MiB per sample')
            probe_path = args.probe_manifest.parent / name
            require(probe_path.stat().st_size == size, f'Probe size mismatch: {name}')
            content = probe_path.read_bytes()
            require(hashlib.sha256(content).hexdigest() == sample.get('sha256'),
                    f'Probe saved-file SHA-256 mismatch: {name}')
            probes.append(dict(file=name, offset=lba*512, bytes=size,
                               sha256=sample['sha256'], content=content, compared=0))
    spec = importlib.util.spec_from_file_location('inspect_backup',
                                                 Path(__file__).with_name('inspect-backup.py'))
    inspector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inspector)
    args.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    with ExitStack() as stack:
        source = stack.enter_context(gzip.open(args.source, 'rb'))
        # This device's GPT fits in 34 sectors. Bound header parsing to 1 MiB;
        # larger partition arrays require an explicit future implementation.
        first = source.read(min(1024 * 1024, expected))
        gpt = inspector.inspect_gpt(first, 512)
        selected = []
        for name in args.partitions:
            matches = [p for p in gpt['partitions'] if p['name'] == name]
            require(len(matches) == 1, f'Expected exactly one GPT partition named {name}')
            p = matches[0]
            offset, size = p['first_lba'] * 512, p['sectors'] * 512
            require(offset + size <= expected, f'{name} exceeds backup bounds')
            selected.append(dict(name=name, offset=offset, bytes=size))
        needed = sum(p['bytes'] for p in selected)
        require(shutil.disk_usage(args.output_dir).free >= needed + 64 * 1024 * 1024,
                'Insufficient disk space for selected partitions plus 64 MiB reserve')
        streams, hashes, counts = {}, {}, {}
        for p in selected:
            streams[p['name']] = stack.enter_context(
                (args.output_dir / (p['name'] + '.img.partial')).open('xb'))
            hashes[p['name']] = hashlib.sha256()
            counts[p['name']] = 0
        raw_hash, offset = hashlib.sha256(), 0
        data = first
        while data:
            require(offset + len(data) <= expected, 'Decompressed source exceeds expected size')
            raw_hash.update(data)
            for probe in probes:
                lo = max(offset, probe['offset'])
                hi = min(offset + len(data), probe['offset'] + probe['bytes'])
                if lo < hi:
                    require(data[lo-offset:hi-offset] ==
                            probe['content'][lo-probe['offset']:hi-probe['offset']],
                            f"Independent read mismatch: {probe['file']} at byte {lo}")
                    probe['compared'] += hi-lo
            for p in selected:
                lo = max(offset, p['offset'])
                hi = min(offset + len(data), p['offset'] + p['bytes'])
                if lo < hi:
                    piece = data[lo-offset:hi-offset]
                    name = p['name']
                    streams[name].write(piece)
                    hashes[name].update(piece)
                    counts[name] += len(piece)
            offset += len(data)
            data = source.read(1024 * 1024)
        require(offset == expected, 'Truncated decompressed source')
        require(raw_hash.hexdigest() == record['raw_sha256'], 'Whole-disk raw SHA-256 mismatch')
        require(all(p['compared'] == p['bytes'] for p in probes), 'Incomplete probe comparison')
        for p in selected:
            require(counts[p['name']] == p['bytes'], f"Incomplete partition {p['name']}")
            p['sha256'] = hashes[p['name']].hexdigest()
            streams[p['name']].flush()
            os.fsync(streams[p['name']].fileno())
    report = dict(source=args.source.name, source_raw_bytes=expected,
                  source_raw_sha256=record['raw_sha256'], gzip_eof_verified=True,
                  partitions=selected,
                  independent_samples=[{k: p[k] for k in ('file', 'offset', 'bytes', 'sha256')}
                                       for p in probes],
                  scope='Extraction integrity against source manifest; firmware authenticity not established')
    manifest_partial = args.output_dir / 'manifest.json.partial'
    with manifest_partial.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    for p in selected:
        temporary = args.output_dir / (p['name'] + '.img.partial')
        os.link(temporary, args.output_dir / (p['name'] + '.img'))
        temporary.unlink()
    os.link(manifest_partial, args.output_dir / 'manifest.json')
    manifest_partial.unlink()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, EOFError, KeyError, TypeError) as error:
        print(f'Extraction failed: {error}. Partial files are not validated outputs.', file=sys.stderr)
        sys.exit(1)
