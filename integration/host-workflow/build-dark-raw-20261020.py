from pathlib import Path
import ast
W=Path(__file__).resolve().parent;B=W/'current-surface-build';E=W/'calibration-unlit-20261020';E.mkdir();d=E/'dual-unlit-probe-v1';d.mkdir()
for p in (B/'dual-calibration-probe-v1').iterdir():
 if not p.is_file():continue
 b=p.read_bytes()
 if p.suffix=='.py':b=b.decode().replace('sp7-dual-calibration-7_2_11-v1','sp7-dual-unlit-7_2_11-v1').replace('kernel7-dual-calibration-v1-plan','kernel7-dual-unlit-v1-plan').encode()
 (d/p.name).write_bytes(b)
p=d/'calibration_plan.py';p.write_text(p.read_text().replace("plan['illumination'] is not True", "plan['illumination'] is not False"))
p=d/'test_calibration_plan.py';p.write_text(p.read_text().replace('illumination=True','illumination=False').replace("('illumination',False)","('illumination',True)"))
p=d/'dual_coordinator.py';p.write_text(p.read_text().replace("'illumination_requested':True", "'illumination_requested':False"))
p=d/'probe_backend.py';s=p.read_text().replace('from light_gate import arm,verify_events','from dark_gate import verify_dark')
a=s.index(' def arm_light(self):');z=s.index(' def reserve(self):',a)
s=s[:a]+" def verify_dark(self):return verify_dark(STROBE.read_text().strip())\n"+s[z:]
s=s.replace("result['standby_light_arm']=self.arm_light()", "result['dark_before_native']=self.verify_dark()")
p.write_text(s)
p=d/'dual_evidence.py';s=p.read_text().replace('from light_gate import verify_events\n light=verify_events(log)',"from dark_gate import verify_log\n light=verify_log(log,metadata.get('dark_before_native'),metadata.get('post_native_dark'))")
s=s.replace("'illumination_enabled':True", "'illumination_enabled':False");p.write_text(s)
for n in ['vm-stock','full-helper-v7','dual-route-driver-v3','book-recovery-v1','old-support.ko','rgb-bounded-driver-v1','vmlinuz-7.2.11','dual-probe-v1']:(E/n).symlink_to((B/n).resolve(),target_is_directory=(B/n).is_dir())
s=(B/'run-dual-calibration-v1-vm.py').read_text().replace('dual-calibration-probe-v1','dual-unlit-probe-v1').replace('dual-calibration-vm-v1','dual-unlit-vm-v1').replace('guest-dual-calibration-v1.py','guest-dual-unlit-v1.py');(E/'run-dual-unlit-v1-vm.py').write_text(s)
s=(B/'guest-dual-calibration-v1.py').read_text().replace("tests=['test_calibration_plan'","tests=['test_dark_gate','test_calibration_plan'");(E/'guest-dual-unlit-v1.py').write_text(s)
print(E)
