from pathlib import Path
import json,hashlib,datetime
from live_transport import run_python
w=Path(__file__).resolve().parent
source=r'''import pathlib,json,subprocess,hashlib,base64
P=pathlib.Path;r={'schema':'sp7-dualboot-installed-before-first-boot-audit-v1'}
r['boot_id']=P('/proc/sys/kernel/random/boot_id').read_text().strip();assert r['boot_id']=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
r['gpt_hashes']={}
with open('/dev/nvme0n1','rb',buffering=0) as f:
 for name,off,n,expected in [('primary',0,17408,'2db64ccac0d0500761a35eda5c2d35f0bdb08cf4776fbe0959b35001027110e1'),('secondary',256060497408,16896,'3246c22cb5bba2acf5671160636b30a1a9b3413ff4a74eb08ad4aaf8887c6dd5')]:
  f.seek(off);h=hashlib.sha256(f.read(n)).hexdigest();assert h==expected;r['gpt_hashes'][name]=h
r['partitions']=json.loads(subprocess.check_output(['sfdisk','--json','/dev/nvme0n1'],text=True))
r['internal_mounts']={d:subprocess.run(['findmnt','-rn','-S',d],capture_output=True,text=True).stdout.strip() for d in ['/dev/nvme0n1p1','/dev/nvme0n1p3','/dev/nvme0n1p4','/dev/nvme0n1p5']};assert not any(r['internal_mounts'].values())
r['restore_workers']=[]
for p in P('/proc').iterdir():
 if p.name.isdigit():
  try:
   comm=(p/'comm').read_text().strip()
   if comm.startswith('partclone') or comm=='btrfs':r['restore_workers'].append({'pid':p.name,'comm':comm})
  except FileNotFoundError:pass
assert not r['restore_workers']
r['efi_security']={name:int(next(P('/sys/firmware/efi/efivars').glob(name+'-*')).read_bytes()[4]) for name in ['SecureBoot','SetupMode']};assert r['efi_security']=={'SecureBoot':1,'SetupMode':0}
r['boot_entries']=subprocess.check_output(['efibootmgr','-v'],text=True);assert 'BootOrder: 0006,0005,0001,0004,0000,0002' in r['boot_entries']
r['ac_online']=P('/sys/class/power_supply/ADP1/online').read_text().strip();assert r['ac_online']=='1'
r['cpu_temperature_millicelsius']={}
for hw in P('/sys/class/hwmon').glob('hwmon*'):
 if (hw/'name').read_text().strip()=='coretemp':
  for lp in hw.glob('temp*_label'):r['cpu_temperature_millicelsius'][lp.read_text().strip()]=int(lp.with_name(lp.name.replace('_label','_input')).read_text())
r['ram_log_files']={}
for rel in ['sp7-dualboot-restore/status.json','sp7-dualboot-restore/partclone.log','sp7-dualboot-restore/btrfs-check.log','sp7-config-adjust-result.json','sp7-efi-file-deployment.json','sp7-firmware-create-result.json']:
 p=P('/run')/rel;assert p.is_file() and p.stat().st_size<2000000;r['ram_log_files'][rel]=base64.b64encode(p.read_bytes()).decode()
q=subprocess.run(['mokutil','--test-key','/run/live/medium/SP7-DUALBOOT/certificates/surface.cer'],capture_output=True,text=True);r['surface_cert_test']={'exit':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
r['windows_partition_type']=subprocess.check_output(['blkid','-s','TYPE','-o','value','/dev/nvme0n1p3'],text=True).strip();assert r['windows_partition_type']=='BitLocker'
r['installed_and_unmounted']=True;r['physical_os_boot_tests_pending']=True;print(json.dumps(r))
'''
r=run_python(source,timeout=60);assert r.returncode==0,r.stderr;j=json.loads(r.stdout);j['host_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(w/'physical-installed-final-audit.json').write_text(json.dumps(j,indent=2)+'\n');b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019');(b/'installed-final-audit.json').write_text(json.dumps(j,indent=2)+'\n')
for rel,data in j['ram_log_files'].items():
 p=b/'final-ram-receipts'/rel;p.parent.mkdir(parents=True,exist_ok=True);import base64;p.write_bytes(base64.b64decode(data))
print(json.dumps({k:v for k,v in j.items() if k not in ['ram_log_files','boot_entries','partitions']},indent=2))
