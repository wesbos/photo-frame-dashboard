#!/usr/bin/env python3
"""Exercise staging failures with synthetic APKs; no SDK, card or device required."""
import importlib.util
import base64
import struct
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC=importlib.util.spec_from_file_location('prepare_card',Path(__file__).with_name('prepare_card.py'))
module=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(module)

class Staging(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.out=self.root/'card'
        self.key=self.root/'adbkey.pub'
        raw=struct.pack('<I',64)+bytes(516)+struct.pack('<I',65537)
        self.key.write_bytes(base64.b64encode(raw)+b' synthetic-fixture\n')
        self.build=mock.patch.object(module,'build_apk',lambda p,v:p.write_bytes(b'synthetic APK'))
        self.build.start()
    def tearDown(self):self.build.stop();self.temp.cleanup()
    def stage(self,mode='probe',replace=False):module.stage(self.out,mode,80322,self.key if mode=='adb' else None,replace)
    def config(self):return self.out/'Frameo_utilities/frameo_utilities.config'
    def test_config_published_last_and_recovery_kept(self):
        self.stage('adb')
        recovery=self.out/'mi86-adb-v2/adb_keys.before';recovery.write_bytes(b'keep this snapshot')
        publish=module.os.replace;targets=[]
        def observe(src,dest):
            self.assertFalse(self.config().exists())
            targets.append(Path(dest).name);publish(src,dest)
        with mock.patch.object(module.os,'replace',observe):self.stage('adb',True)
        self.assertEqual(targets[-1],'frameo_utilities.config')
        self.assertEqual(recovery.read_bytes(),b'keep this snapshot')
    def test_build_failure_leaves_old_payload_untouched(self):
        self.stage();before={p.relative_to(self.out):p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
        with mock.patch.object(module,'build_apk',side_effect=RuntimeError('SDK failed')):
            with self.assertRaises(RuntimeError):self.stage('adb',True)
        after={p.relative_to(self.out):p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_new_failed_build_never_arms(self):
        with mock.patch.object(module,'build_apk',side_effect=RuntimeError('SDK failed')):
            with self.assertRaises(RuntimeError):self.stage()
        self.assertFalse(self.config().exists())
    def test_every_publication_failure_disarms(self):
        for fail_at in range(1,5):
            with self.subTest(fail_at=fail_at):
                self.stage('adb',True);real=module.os.replace;count=0
                def broken(src,dest):
                    nonlocal count
                    count+=1
                    if count==fail_at:raise OSError('injected publication failure')
                    real(src,dest)
                with mock.patch.object(module.os,'replace',broken):
                    with self.assertRaises(OSError):self.stage('adb',True)
                self.assertFalse(self.config().exists())
    def test_readback_failure_disarms_even_after_config_publish(self):
        self.stage();real=module.os.replace
        def corrupt(src,dest):
            real(src,dest)
            if Path(dest).name=='frameo_utilities.config':Path(dest).write_bytes(b'bad config')
        with mock.patch.object(module.os,'replace',corrupt):
            with self.assertRaises(SystemExit):self.stage(replace=True)
        self.assertFalse(self.config().exists())
    def test_symlink_and_unrelated_files_refused(self):
        outside=self.root/'outside';outside.mkdir();self.out.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(SystemExit):self.stage(replace=True)
        self.out.unlink();self.stage();(self.out/'Frameo_utilities/other.apk').write_bytes(b'keep')
        with self.assertRaises(SystemExit):self.stage(replace=True)
        self.assertEqual((self.out/'Frameo_utilities/other.apk').read_bytes(),b'keep')
        (self.out/'Frameo_utilities/other.apk').unlink()
        self.config().unlink();self.config().symlink_to(outside/'missing')
        with self.assertRaises(SystemExit):self.stage(replace=True)
        self.assertFalse((outside/'missing').exists())
    def test_invalid_public_key_rejected_before_build(self):
        self.key.write_text('QAAAA'+'A'*694+'= invalid\n')
        with mock.patch.object(module,'build_apk') as build:
            with self.assertRaises(SystemExit):self.stage('adb')
            build.assert_not_called()
        self.assertFalse(self.config().exists())
    def test_explicit_replace_required(self):
        self.stage()
        with self.assertRaises(SystemExit):self.stage()

if __name__=='__main__':unittest.main()
