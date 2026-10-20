from pathlib import Path
import ast
W=Path(__file__).resolve().parent;B=W/'current-surface-build';E=W/'dual-face-20261020';E.mkdir();d=E/'dual-face-probe-v1';d.mkdir();old=B/'ir-face-probe-v3'
for p in (B/'dual-calibration-probe-v1').iterdir():
 if not p.is_file():continue
 data=p.read_bytes()
 if p.suffix=='.py':data=data.decode().replace('sp7-dual-calibration-7_2_11-v1','sp7-dual-face-7_2_11-v1').replace('kernel7-dual-calibration-v1-plan','kernel7-dual-face-v1-plan').replace('printed_checkerboard_no_faces','single_present_user_face').encode()
 (d/p.name).write_bytes(data)
for n in ['presence.py','presence_action.py','dialog.py','test_presence.py','test_face_presence.py']:
 s=(old/n).read_text().replace('sp7-ir-face-7_2_11-v3','sp7-dual-face-7_2_11-v1')
 if n=='presence.py':s=s.replace('Redo för IR-prov','Redo för RGB/IR-prov').replace('Ett enda prov följer.','En kort bildserie tas: 30 RGB- och 30 IR-bilder.')
 if n=='dialog.py':s=s.replace('SP7 — IR-prov','SP7 — RGB/IR-ansiktsprov')
 (d/n).write_text(s)
p=d/'calibration_plan.py';s=p.read_text().replace("'scene'}","'scene','plan_created_utc'}");s+='''
 import datetime
 try:
  stamp=datetime.datetime.fromisoformat(plan['plan_created_utc']);now=datetime.datetime.now(datetime.timezone.utc)
  if stamp.tzinfo is None or not 0<=(now-stamp).total_seconds()<=900:raise ValueError('stale')
 except (ValueError,TypeError):raise RuntimeError('Fresh explicit face plan creation time required') from None
''';p.write_text(s)
p=d/'probe_backend.py';s=p.read_text().replace('class Backend(Metadata):','class RawBackend(Metadata):').replace("result['standby_light_arm']=self.arm_light()", "self.claim_presence();result['standby_light_arm']=self.arm_light()")
source=(old/'probe_backend.py').read_text();tree=ast.parse(source);cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Backend');lines=source.splitlines(keepends=True)
s+='''
# Presence is consumed by the fixed UID1000 helper immediately before the
# existing bounded light gate. Cleanup never requires continued presence.
class Backend(RawBackend):
 def configure(self):self.check_presence();return super().configure()
 def check_cancel(self):super().check_cancel();self.check_presence(cancel_only=True)
'''
for f in cls.body:
 if isinstance(f,ast.FunctionDef) and f.name in ['presence_folder','check_presence','claim_presence']:s+=''.join(lines[f.lineno-1:f.end_lineno])+'\n'
p.write_text(s)
p=d/'test_calibration_plan.py';s=p.read_text().replace('import unittest,copy','import unittest,copy,datetime').replace("schema=1,boot_id=", "schema=1,plan_created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),boot_id=");s=s.replace("[('scene','book_no_faces')", "[('plan_created_utc','2000-01-01T00:00:00+00:00'),('plan_created_utc','2099-01-01T00:00:00+00:00'),('plan_created_utc','2026-10-20'),('scene','book_no_faces')");p.write_text(s)
p=d/'test_book.py';s=p.read_text();a=s.index('class HashDelay');s=s[:a]+s[a:].replace('object.__new__(p.Backend)','object.__new__(p.RawBackend)').replace('b.arm_light=lambda:{}','b.arm_light=lambda:{};b.claim_presence=lambda:None');p.write_text(s)
p=d/'test_face_presence.py';s=p.read_text().replace('self.light_arm= self.arm_light()',"result['standby_light_arm']=self.arm_light()").replace("self.assertIn(\"'30','12499','375000'\",s)","self.assertIn(\"('ir',CAPTURE,12499,375000)\",s)");p.write_text(s)
for n in ['vm-stock','full-helper-v7','dual-route-driver-v3','book-recovery-v1','old-support.ko','rgb-bounded-driver-v1','vmlinuz-7.2.11','dual-probe-v1']:(E/n).symlink_to((B/n).resolve(),target_is_directory=(B/n).is_dir())
s=(B/'run-dual-calibration-v1-vm.py').read_text().replace('dual-calibration-probe-v1','dual-face-probe-v1').replace('dual-calibration-vm-v1','dual-face-vm-v1').replace('guest-dual-calibration-v1.py','guest-dual-face-v1.py');(E/'run-dual-face-v1-vm.py').write_text(s)
s=(B/'guest-dual-calibration-v1.py').read_text().replace("tests=['test_calibration_plan'", "tests=['test_presence','test_face_presence','test_calibration_plan'");(E/'guest-dual-face-v1.py').write_text(s)
print(E)
