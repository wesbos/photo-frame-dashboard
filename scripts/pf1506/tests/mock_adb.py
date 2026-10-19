#!/usr/bin/env python3
"""Small deterministic partition streams; never invokes ADB or opens a device."""
import hashlib
import os
import re
import sys
args = sys.argv[1:]
if args == ['get-state']:
    print('device')
elif args == ['shell', 'su', '0', 'id', '-u']:
    print('0')
else:
    assert len(args) == 2 and args[0] in ['shell', 'exec-out'], args
    command = args[1]
    match = re.search(r'/dev/block/by-name/(\w+)', command)
    assert match, args
    name = match.group(1)
    part = bytes([sum(name.encode()) % 250 + 1]) * (32 + len(name))
    if name == 'super':
        part = b''.join(bytes([i]) * 16 for i in range(64))
    if 'blockdev --getsize64' in command:
        print(len(part))
    else:
        assert 'dd if=' in command and 'of=' not in command, args
        skip = re.search(r'skip=(\d+)', command)
        if skip:
            i = int(skip.group(1))
            part = part[i*16:(i+1)*16]
        if args[0] == 'exec-out':
            sys.stdout.buffer.write(part + b'dd status trailing text')
        else:
            assert '| sha256sum' in command, args
            digest = hashlib.sha256(part).hexdigest()
            if os.environ.get('PF1506_BAD_HASH') == name:
                digest = '0' * 64
            print(digest + '  -')
