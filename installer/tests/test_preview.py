# SPDX-License-Identifier: GPL-3.0-only
import unittest,types
from pathlib import Path
from unittest.mock import patch,Mock
import sp7_setup as s
class Tests(unittest.TestCase):
 def manager(self):return types.SimpleNamespace(base=Path('/opt/sp7-research'),use_lease=Mock(return_value=42),current=lambda:dict(release='releases/0.4.0-0123456789ab'))
 def test_root_never_opens_preview(self):
  m=self.manager()
  with patch.object(s,'Installer',return_value=m),patch.object(s.os,'geteuid',return_value=0):
   with self.assertRaises(s.Refused):s.main(['preview'])
  m.use_lease.assert_not_called()
 def test_user_preview_is_only_the_fixed_demo_and_holds_lease(self):
  m=self.manager()
  with patch.object(s,'Installer',return_value=m),patch.object(s.os,'geteuid',return_value=1000),patch.object(s.Path,'is_file',return_value=True),patch.object(s.os,'execv',side_effect=RuntimeError('captured exec')) as call:
   with self.assertRaisesRegex(RuntimeError,'captured exec'):s.main(['preview'])
  m.use_lease.assert_called_once();self.assertEqual(call.call_args.args,('/usr/lib/qt6/bin/qml',['/usr/lib/qt6/bin/qml','/opt/sp7-research/releases/0.4.0-0123456789ab/app/interface/ui/Demo.qml']))
if __name__=='__main__':unittest.main()
