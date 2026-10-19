#!/usr/bin/env python3
"""Execute the device script only with inert command doubles and a private lock."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / 'frame-adb-wifi.sh'
GUARD = '-p tcp -m tcp --dport 5555 -j frame_adb_guard'
ALLOW = '-p tcp -m tcp --dport 5555 -j frame_adb'

class WifiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        binary = self.root / 'bin'
        binary.mkdir()
        mock = HERE / 'mock_android.py'
        for name in ['iptables', 'ip6tables', 'getprop', 'setprop', 'cat', 'log', 'mkdir', 'rmdir', 'sleep']:
            (binary / name).symlink_to(mock)
        self.env = dict(os.environ, PF1506_MOCK=str(self.root), PATH=str(binary)+os.pathsep+os.environ['PATH'])
        self.state = {
            'props': {'service.adb.tcp.port': '', 'persist.adb.tcp.port': '5555',
                      'init.svc.adbd': 'running', 'persist.frame.adb_allow': '192.0.2.10', 'persist.frame.adb_wifi': ''},
            'listen': [5555],
            'tables': {name: {'INPUT': ['-m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT', '-j ACCEPT']}
                       for name in ['iptables', 'ip6tables']}}
    def tearDown(self):
        self.tmp.cleanup()
    def save(self):
        (self.root / 'state.json').write_text(json.dumps(self.state))
    def run_script(self, ok=True):
        self.save()
        result = subprocess.run(['/bin/sh', str(SCRIPT)], env=self.env, capture_output=True, text=True, timeout=20)
        self.state = json.loads((self.root / 'state.json').read_text())
        self.assertEqual(result.returncode == 0, ok, result.stdout+result.stderr+str(self.state.get('logs')))
        return result
    def test_persisted_listener_with_empty_runtime_is_closed(self):
        self.state['props']['persist.frame.adb_wifi'] = '0'
        self.run_script()
        self.assertEqual(self.state['listen'], [])
        self.assertEqual(self.state['props']['persist.adb.tcp.port'], '-1')
        self.assertEqual(self.state['props']['init.svc.adbd'], 'running')
        self.assertIn(['setprop', 'ctl.stop', 'adbd'], self.state['calls'])
        self.assertTrue(any('verified USB-only' in s for s in self.state['logs']))
    def test_missing_allow_list_keeps_usb_and_guards(self):
        self.state['props']['persist.frame.adb_allow'] = ''
        self.run_script()
        self.assertEqual(self.state['listen'], [])
        for table in self.state['tables'].values():
            self.assertEqual(table['INPUT'][0], GUARD)
    def test_malformed_config(self):
        for bad in ['192.0.2.999', '192.0.2.10,,192.0.2.11', '127.1', '192.0.2.10;', '01.2.3.4']:
            with self.subTest(bad=bad):
                self.state['props']['persist.frame.adb_allow'] = bad
                self.run_script(False)
                self.assertEqual(self.state['listen'], [])
                self.assertFalse(any('verified USB-only' in s for s in self.state.get('logs', [])))
    def test_order_revocation_and_idempotence(self):
        table = self.state['tables']['iptables']
        table['INPUT'] += [ALLOW, GUARD, ALLOW]
        table['frame_adb'] = ['-j RETURN', '-j DROP']
        table['frame_adb_guard'] = ['-j DROP']
        self.run_script()
        first = self.state['tables']
        self.assertEqual(first['iptables']['INPUT'], [ALLOW, '-m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT', '-j ACCEPT'])
        self.assertEqual(first['ip6tables']['INPUT'][0], GUARD)
        self.assertEqual(first['iptables']['frame_adb'], ['-s 192.0.2.10/32 -j RETURN', '-j DROP'])
        self.assertEqual(self.state['listen'], [5555])
        self.run_script()
        self.assertEqual(self.state['tables'], first)
        self.state['props']['persist.frame.adb_allow'] = '192.0.2.11'
        self.run_script()
        self.assertEqual(self.state['tables']['iptables']['frame_adb'], ['-s 192.0.2.11/32 -j RETURN', '-j DROP'])
        self.assertEqual(self.state['tables']['iptables']['INPUT'][0], ALLOW)
    def test_failures_never_claim_verified_usb(self):
        for command in ['getprop service.adb.tcp.port', 'getprop persist.adb.tcp.port',
                        'getprop persist.frame.adb_allow', 'getprop persist.frame.adb_wifi',
                        'iptables -I INPUT 1 -p tcp --dport 5555 -j frame_adb_guard',
                        'ip6tables -I INPUT 1 -p tcp --dport 5555 -j frame_adb_guard',
                        'setprop service.adb.tcp.port -1', 'setprop persist.adb.tcp.port -1',
                        'setprop ctl.stop adbd', 'iptables -F frame_adb',
                        'iptables -A frame_adb -j DROP', 'iptables -D INPUT 1',
                        'setprop service.adb.tcp.port 5555', 'setprop ctl.start adbd']:
            with self.subTest(command=command):
                self.state['fail_once'] = command
                self.state['logs'] = []
                self.run_script(False)
                self.assertFalse(any('verified USB-only' in s for s in self.state['logs']))
                self.assertEqual(self.state['tables']['iptables']['INPUT'][0], GUARD)
    def test_delayed_daemon_start_is_awaited(self):
        self.state['start_delay'] = 2
        self.run_script()
        self.assertEqual(self.state['props']['init.svc.adbd'], 'running')

    def test_unclosed_listener_is_failure(self):
        self.state['stop_stuck'] = True
        self.run_script(False)
        self.assertEqual(self.state['listen'], [5555])
        self.assertIn('not guaranteed', self.state['logs'][-1])
    def test_concurrent_run_is_rejected_without_mutation(self):
        self.state['pause_initial'] = True
        self.save()
        first = subprocess.Popen(['/bin/sh', str(SCRIPT)], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            limit = time.monotonic() + 5
            while not (self.root / 'instance.lock').exists():
                self.assertLess(time.monotonic(), limit)
                time.sleep(0.01)
            second = subprocess.run(['/bin/sh', str(SCRIPT)], env=self.env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(second.returncode, 0)
            out, err = first.communicate(timeout=20)
            self.assertEqual(first.returncode, 0, out+err)
            state = json.loads((self.root / 'state.json').read_text())
            self.assertEqual(sum(c == ['setprop', 'ctl.stop', 'adbd'] for c in state['calls']), 1)
        finally:
            if first.poll() is None:
                first.kill(); first.communicate()
    def test_config_changes_in_flight_fail_closed(self):
        self.state['changed_allow'] = '192.0.2.11'
        self.run_script(False)
        self.assertEqual(self.state['listen'], [])
    def test_init_baseline_and_owned_single_instance(self):
        rc = SCRIPT.with_suffix('.rc').read_text()
        self.assertIn('on early-init\n    setprop service.adb.tcp.port -1', rc)
        self.assertIn('on property:ro.persistent_properties.ready=true\n    start frame-adb-wifi', rc)
        self.assertIn('service frame-adb-wifi /system/bin/sh', rc)
        self.assertNotIn('exec_background', rc)
        self.assertIn('    disabled\n    oneshot', rc)

if __name__ == '__main__':
    unittest.main()
