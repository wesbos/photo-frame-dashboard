#!/usr/bin/env python3
"""Inert Android command doubles. Never call host firewall, properties, or devices."""
import fcntl
import json
import os
from pathlib import Path
import sys
import time

root = Path(os.environ['PF1506_MOCK'])
name, args = Path(sys.argv[0]).name, sys.argv[1:]
with (root / 'state.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    state = json.loads((root / 'state.json').read_text())
    state.setdefault('calls', []).append([name, *args])
    output, code = '', 0
    signature = ' '.join([name, *args])
    if signature == state.get('fail_once'):
        del state['fail_once']
        code = 1
    elif name == 'getprop':
        key = args[0]
        if key == 'persist.frame.adb_allow':
            state['allow_reads'] = state.get('allow_reads', 0) + 1
            if state['allow_reads'] >= 2 and 'changed_allow' in state:
                state['props'][key] = state['changed_allow']
        if key == 'init.svc.adbd' and state.get('start_reads', 0) > 0:
            state['start_reads'] -= 1
            if state['start_reads'] == 0:
                state['props'][key] = 'running'
        output = state['props'].get(key, '')
    elif name == 'setprop':
        key, value = args
        if key == 'ctl.stop':
            if not state.get('stop_stuck'):
                state['props']['init.svc.adbd'] = 'stopped'
                state['listen'] = []
        elif key == 'ctl.start':
            state['start_reads'] = state.get('start_delay', 0)
            state['props']['init.svc.adbd'] = 'starting' if state['start_reads'] else 'running'
            port = state['props'].get('service.adb.tcp.port') or state['props'].get('persist.adb.tcp.port', '-1')
            state['listen'] = [int(port)] if int(port) > 0 else []
        else:
            state['props'][key] = value
    elif name == 'cat':
        assert args == ['/proc/net/tcp', '/proc/net/tcp6'], args
        output = '  sl  local_address rem_address st\n' + '\n'.join(
            f'0: 00000000:{port:04X} 00000000:0000 0A' for port in state.get('listen', []))
    elif name in ('iptables', 'ip6tables'):
        table = state['tables'][name]
        op, chain, *tail = args
        if op == '-N':
            if chain in table:
                code = 1
            else:
                table[chain] = []
        elif chain not in table:
            code = 1
        elif op == '-S':
            prefix = '-P INPUT ACCEPT' if chain == 'INPUT' else '-N ' + chain
            output = '\n'.join([prefix] + ['-A ' + chain + ' ' + x for x in table[chain]])
        elif op == '-F':
            table[chain] = []
        elif op in ('-A', '-I'):
            pos = int(tail.pop(0)) - 1 if op == '-I' else len(table[chain])
            if '-p' in tail and '-m' not in tail:
                i = tail.index('-p')
                tail[i+2:i+2] = ['-m', tail[i+1]]
            table[chain].insert(pos, ' '.join(tail))
        elif op == '-D':
            assert len(tail) == 1 and tail[0].isdigit(), 'Only positional deletion of owned rules is expected'
            del table[chain][int(tail[0]) - 1]
        else:
            raise AssertionError(f'Unrecognized firewall operation {args}')
    elif name == 'mkdir':
        assert args == ['/dev/.frame-adb-wifi.lock']
        try:
            (root / 'instance.lock').mkdir()
        except FileExistsError:
            code = 1
    elif name == 'rmdir':
        assert args == ['/dev/.frame-adb-wifi.lock']
        (root / 'instance.lock').rmdir()
    elif name == 'log':
        state.setdefault('logs', []).append(' '.join(args[2:]))
    elif name == 'sleep':
        pass
    else:
        raise AssertionError(f'Unrecognized mock command {name}')
    (root / 'state.json').write_text(json.dumps(state))
if name == 'getprop' and args == ['service.adb.tcp.port'] and state.get('pause_initial'):
    time.sleep(0.3)
if output:
    print(output)
sys.exit(code)
