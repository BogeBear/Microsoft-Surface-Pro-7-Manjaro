from pathlib import Path
import json,datetime
from installed_transport import run_python
w=Path(__file__).resolve().parent
source=r'''import pathlib,subprocess,json,time,math,os
P=pathlib.Path
expected='b3921440-7264-458e-bd4a-8f27d20fa0c2'
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()==expected
assert P('/sys/class/dmi/id/product_name').read_text().strip()=='Surface Pro 7'
c=json.loads(P('/srv/sp7-project/target/work/resume-state.json').read_text());assert not c['active'] and c['hardware_tests_blocked_until_recovery']
assert subprocess.check_output(['findmnt','-n','-o','SOURCE','/'],text=True).strip()=='/dev/nvme0n1p5[/@]'
boot=subprocess.check_output(['efibootmgr'],text=True);assert 'BootCurrent: 0006' in boot and 'BootOrder: 0006,0005,0001,0004,0000,0002' in boot
menu=P('/boot/grub/sp7-dualboot.cfg').read_text();assert 'set default=0' in menu and "menuentry 'Windows 11'" in menu and 'set timeout=12' in menu
assert subprocess.check_output(['mokutil','--sb-state'],text=True).strip()=='SecureBoot enabled'
print(json.dumps({'event':'preflight','boot_id':expected,'default_target':os.readlink('/etc/systemd/system/default.target'),'boot_current':'0006','default_os':'Windows 11','countdown_seconds':12}),flush=True)
labels=['Package id 0','Core 0','Core 1','Core 2','Core 3']
def sample():
 assert P('/sys/class/power_supply/ADP1/online').read_text().strip()=='1'
 groups=[h for h in P('/sys/class/hwmon').glob('hwmon*') if (h/'name').read_text().strip()=='coretemp'];assert len(groups)==1
 vals={p.read_text().strip():int(p.with_name(p.name.replace('_label','_input')).read_text())/1000 for p in groups[0].glob('temp*_label')};assert all(k in vals for k in labels)
 vals={k:vals[k] for k in labels};safe=all(math.isfinite(v) and -20<=v<60 for v in vals.values())
 return {'monotonic':time.monotonic(),'boot_id':P('/proc/sys/kernel/random/boot_id').read_text().strip(),'celsius':vals,'below60':safe}
for i in range(3):
 s=sample();assert s['boot_id']==expected;print(json.dumps({'event':'temperature_sample','index':i+1,**s}),flush=True)
 assert s['below60'],'Hot or unknown: no reboot; only cooling checks every five minutes'
 if i<2:time.sleep(5)
s=sample();assert s['boot_id']==expected;print(json.dumps({'event':'final_temperature_sample',**s}),flush=True);assert s['below60']
print('SP7_INSTALLED_FINAL_REBOOT_GUARD_PASS',flush=True)
q=subprocess.run(['systemctl','reboot'],capture_output=True,text=True);print(json.dumps({'event':'reboot_request','exit':q.returncode,'stdout':q.stdout,'stderr':q.stderr,'no_sudo_or_new_privileges':True}),flush=True)
'''
assert not (w/'installed-reboot-windows-test.json').exists(),'Existing result; do not repeat blindly'
r=run_python(source,timeout=45);j={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'windows_boot_observation_pending':True};(w/'installed-reboot-windows-test.json').write_text(json.dumps(j,indent=2)+'\n');print(r.stdout);print(r.stderr);assert 'SP7_INSTALLED_FINAL_REBOOT_GUARD_PASS' in r.stdout
