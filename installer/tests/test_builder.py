# SPDX-License-Identifier: GPL-3.0-only
import tempfile,unittest,hashlib,io,contextlib
from pathlib import Path
from unittest.mock import patch
import build_package as b
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.src=self.root/'source';self.src.mkdir();self.p=self.src/'README.md';self.p.write_bytes(b'reviewed source');self.sums=hashlib.sha256(self.p.read_bytes()).hexdigest()+'  README.md\n';(self.src/'SHA256SUMS').write_text(self.sums);self.patch=patch.object(b,'CAMERA_MANIFEST_SHA256',hashlib.sha256(self.sums.encode()).hexdigest());self.patch.start();self.addCleanup(self.patch.stop)
 def build(self,name='out'):
  with contextlib.redirect_stdout(io.StringIO()):return b.build(self.src,self.root/name)
 def test_valid_inactive_package(self):
  m=self.build();self.assertEqual(m['activation'],dict(camera=False,drivers=False,login=False,autostart=False));self.assertEqual(m['version'],'0.2.0');self.assertNotIn('app/model.pb',m['files'])
 def test_changed_source_is_rejected_before_output(self):
  self.p.write_bytes(b'changed')
  with self.assertRaises(ValueError):self.build()
  self.assertFalse((self.root/'out').exists())
 def test_manifest_changed(self):
  (self.src/'SHA256SUMS').write_text('0'*64+'  README.md\n')
  with self.assertRaises(ValueError):self.build()
 def test_symlink_and_hardlink_inputs_refused(self):
  import os
  other=self.root/'other';other.write_bytes(b'reviewed source');self.p.unlink();self.p.symlink_to(other)
  with self.assertRaises(OSError):self.build()
  self.p.unlink();os.link(other,self.p)
  with self.assertRaises(ValueError):self.build()
 def test_output_cannot_replace_existing_package(self):
  self.build();before=(self.root/'out/sp7-independent-workbench-0.2.0-x86_64.tar.gz').read_bytes()
  with self.assertRaises(FileExistsError):self.build()
  self.assertEqual((self.root/'out/sp7-independent-workbench-0.2.0-x86_64.tar.gz').read_bytes(),before)
 def test_expected_manifest_still_rejects_path_escape(self):
  text='0'*64+'  ../outside\n';(self.src/'SHA256SUMS').write_text(text)
  with patch.object(b,'CAMERA_MANIFEST_SHA256',hashlib.sha256(text.encode()).hexdigest()):
   with self.assertRaises(b.s.Refused):self.build()
if __name__=='__main__':unittest.main()
