from pathlib import Path
import json,datetime
from installed_transport import run_python
w=Path(__file__).resolve().parent
source=r'''import pathlib,subprocess,json,hashlib,os,re
P=pathlib.Path
r={'schema':'sp7-installed-manjaro-first-boot-readonly-v1','boot_id':P('/proc/sys/kernel/random/boot_id').read_text().strip(),'kernel':os.uname().release,'cmdline':P('/proc/cmdline').read_text().strip()}
cp=P('/srv/sp7-project/target/work/resume-state.json');b=cp.read_bytes();r['checkpoint_sha256']=hashlib.sha256(b).hexdigest();j=json.loads(b);r['checkpoint']={k:j.get(k) for k in ['active','boot_id','phase','hardware_tests_blocked_until_recovery','reviewed_presence_plan','pending_reboot','dualboot_restore']}
def cmd(name,args):
 try:q=subprocess.run(args,capture_output=True,text=True,timeout=15);r[name]={'exit':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
 except BaseException as e:r[name]={'error':type(e).__name__+': '+str(e)}
cmd('secureboot',['mokutil','--sb-state']);cmd('enrolled_public_certificates',['mokutil','--list-enrolled'])
cmd('mounts',['findmnt','--json','--mountpoint','/','/home','/boot/efi'])
for n in ['root','home','boot/efi']:
 target='/' if n=='root' else '/'+n
 cmd('mount_'+n,['findmnt','--json','--target',target,'-o','SOURCE,TARGET,FSTYPE,OPTIONS,UUID'])
cmd('disk_layout',['lsblk','-b','-J','-o','NAME,SIZE,TYPE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS','/dev/nvme0n1'])
cmd('system_services',['systemctl','show','sshd.service','NetworkManager.service','sp7-camera-prepare.service','sddm.service','-p','Id','-p','ActiveState','-p','SubState','-p','UnitFileState'])
cmd('user_camera_services',['systemctl','--user','show','sp7-camera-auto.service','sp7-camera.service','-p','Id','-p','ActiveState','-p','SubState','-p','UnitFileState'])
cmd('system_failed_units',['systemctl','--failed','--no-legend','--no-pager'])
cmd('network_devices',['nmcli','-t','-f','DEVICE,TYPE,STATE','device','status'])
r['selected_file_hashes']={}
for name in ['/etc/fstab','/boot/grub/grub.cfg','/boot/grub/sp7-dualboot.cfg','/boot/vmlinuz-linux-surface']:
 try:
  with P(name).open('rb') as f:r['selected_file_hashes'][name]={'sha256':hashlib.file_digest(f,'sha256').hexdigest()}
 except PermissionError:r['selected_file_hashes'][name]={'unreadable':'PermissionError; no privilege escalation attempted'}
r['camera_enablement_links_absent']=all(not P(p).is_symlink() for p in ['/etc/systemd/system/multi-user.target.wants/sp7-camera-prepare.service','/home/sp7-user/.config/systemd/user/default.target.wants/sp7-camera-auto.service'])
r['camera_related_loaded_modules']=[line for line in P('/proc/modules').read_text().splitlines() if any(t in line.lower() for t in ['ipu','ov7251','ov9734','ov5693','int3472'])]
r['runtime_status']={}
for p in P('/sys/devices').glob('pci*/*/power/runtime_status'):
 if p.is_file():
  try:r['runtime_status'][str(p)]=p.read_text().strip()
  except PermissionError:pass
r['cpu_temperatures']={}
for hw in P('/sys/class/hwmon').glob('hwmon*'):
 if (hw/'name').read_text().strip()=='coretemp':
  for p in hw.glob('temp*_label'):r['cpu_temperatures'][p.read_text().strip()]=int(p.with_name(p.name.replace('_label','_input')).read_text())
r['read_only']=True;r['no_camera_stream_or_light_started']=True;print(json.dumps(r))
'''
r=run_python(source,timeout=130);out={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(w/'installed-first-boot-audit.json').write_text(json.dumps(out,indent=2)+'\n');assert r.returncode==0,r.stderr;j=json.loads(r.stdout)
print(json.dumps({k:v for k,v in j.items() if k not in ['enrolled_public_certificates','checkpoint','runtime_status']},indent=2));print('Certificate metadata:',j['enrolled_public_certificates']['exit'],j['enrolled_public_certificates'].get('stdout','')[:1700]);print('Checkpoint:',j['checkpoint']['phase'],j['checkpoint']['active'])
