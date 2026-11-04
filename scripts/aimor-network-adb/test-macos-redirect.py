#!/usr/bin/env python3
"""Offline pfctl/ifconfig doubles: never contacts a frame or changes host networking."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('macos-redirect.sh')
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
root = pathlib.Path(os.environ['MOCK_ROOT'])
with (root/'calls').open('a') as out: out.write(json.dumps([name, *args])+'\n')
if name == 'ifconfig':
    print(os.environ.get('BRIDGE_INFO', 'bridge103: flags=8863\n\tinet 192.168.2.1 netmask 0xffffff00 broadcast 192.168.2.255'))
    sys.exit(0)
if name == 'arp':
    print('? (192.168.2.7) at 00:00:00:00:00:00 on bridge103')
    sys.exit(0)
assert name == 'sudo' and args[0] == 'pfctl', args
args = args[1:]
failure = os.environ.get('PF_FAIL', '')
state = root/'rules'
if args == ['-s', 'info']:
    if failure == 'status': sys.exit(20)
    print('Status: Enabled')
elif args == ['-s', 'nat']:
    print('rdr-anchor "com.apple/*" all' if failure != 'root-anchor' else '')
elif args[-2:] == ['-s', 'nat']:
    if failure == 'readback' and state.exists(): sys.exit(21)
    print(state.read_text() if state.exists() else os.environ.get('OCCUPIED', ''), end='')
elif '-f' in args:
    rule = sys.stdin.read()
    if '-n' in args:
        if failure == 'parse': sys.exit(22)
    else:
        if failure == 'load': sys.exit(23)
        if failure != 'noop':
            if failure == 'wrong-rule': rule=rule.replace('from 192.168.2.7','from 192.168.2.8')
            if os.environ.get('CANONICAL'):
                rule=rule.replace('port 7806 ->','port = 7806 ->').replace('from 192.168.2.7','from 192.168.2.7/32')
            state.write_text(rule)
elif args[0] == '-k':
    if failure == 'kill': sys.exit(24)
elif args[-2:] == ['-F', 'nat']:
    if failure == 'flush': sys.exit(25)
    state.unlink(missing_ok=True)
else: raise AssertionError(args)
'''

class Redirect(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root/'bin'; self.bin.mkdir()
        for name in ('sudo', 'ifconfig', 'arp'):
            path=self.bin/name;path.write_text(MOCK);path.chmod(0o755)
        self.env={**os.environ, 'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],
                  'MOCK_ROOT':str(self.root), 'BRIDGE':'bridge103'}
    def tearDown(self): self.temp.cleanup()
    def run_script(self,*args,**env):
        return subprocess.run(['bash',str(SCRIPT),*args],env={**self.env,**env},capture_output=True,text=True)
    def calls(self):
        p=self.root/'calls'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
    def test_selected_frame_only_and_scoped_cleanup(self):
        result=self.run_script('on','192.168.2.7');self.assertEqual(result.returncode,0,result.stderr)
        rule=(self.root/'rules').read_text()
        self.assertIn('from 192.168.2.7 to any port 7806',rule);self.assertNotIn('/24',rule)
        self.assertIn(['sudo','pfctl','-k','192.168.2.7'],self.calls())
        self.assertEqual(self.run_script('off').returncode,0)
        self.assertFalse((self.root/'rules').exists())
        for call in self.calls():
            if '-F' in call: self.assertEqual(call,['sudo','pfctl','-a','com.apple/aimor-t3c','-F','nat'])
    def test_rejects_invalid_peers_before_sudo(self):
        for peer in ('192.168.2.0','192.168.2.255','192.168.2.1','192.168.3.7','127.0.0.1',
                     '192.168.2.7/24','192.168.002.7','192.168.2.7\npass all','-k'):
            with self.subTest(peer=peer): self.assertNotEqual(self.run_script('on',peer).returncode,0)
        self.assertFalse(any(c[0]=='sudo' for c in self.calls()))
    def test_ambiguous_bridge_and_bad_interface(self):
        self.assertNotEqual(self.run_script('on','192.168.2.7',BRIDGE='bridge103;false').returncode,0)
        info='\tinet 192.168.2.1 netmask 0xffffff00\n\tinet 192.168.2.3 netmask 0xffffff00'
        self.assertNotEqual(self.run_script('on','192.168.2.7',BRIDGE_INFO=info).returncode,0)
        self.assertFalse(any(c[0]=='sudo' for c in self.calls()))
    def test_existing_anchor_not_overwritten(self):
        result=self.run_script('on','192.168.2.7',OCCUPIED='another rule\n')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any('-f' in c or '-k' in c or '-F' in c for c in self.calls()))
    def test_failures_never_report_success(self):
        for failure in ('status','root-anchor','parse','load','kill','readback','noop','wrong-rule'):
            with self.subTest(failure=failure):
                result=self.run_script('on','192.168.2.7',PF_FAIL=failure)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('Redirect active',result.stdout)
                self.assertFalse((self.root/'rules').exists())
    def test_canonical_pf_format_is_accepted(self):
        result=self.run_script('on','192.168.2.7',CANONICAL='1')
        self.assertEqual(result.returncode,0,result.stderr)
    def test_bad_readback_cleans_anchor_without_resetting_states(self):
        for failure in ('noop','wrong-rule'):
            with self.subTest(failure=failure):
                (self.root/'calls').write_text('')
                result=self.run_script('on','192.168.2.7',PF_FAIL=failure)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(['sudo','pfctl','-a','com.apple/aimor-t3c','-F','nat'],self.calls())
                self.assertFalse(any('-k' in call for call in self.calls()))
                self.assertFalse((self.root/'rules').exists())
    def test_cleanup_failure_visible(self):
        self.assertEqual(self.run_script('on','192.168.2.7').returncode,0)
        result=self.run_script('off',PF_FAIL='flush')
        self.assertNotEqual(result.returncode,0);self.assertTrue((self.root/'rules').exists())
        self.assertNotIn('Removed redirect',result.stdout)

if __name__=='__main__': unittest.main()
