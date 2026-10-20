from pathlib import Path
import json,datetime
from live_transport import run_python
w=Path(__file__).resolve().parent
source=r'''import pathlib,subprocess,json,hashlib,os
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
r={'boot_id':P('/proc/sys/kernel/random/boot_id').read_text().strip(),'boot_entries':subprocess.check_output(['efibootmgr','-v'],text=True),'efibootmgr_help':subprocess.run(['efibootmgr','--help'],capture_output=True,text=True).stdout,'efi_files':{},'efi_directories':[]}
assert not subprocess.run(['findmnt','-rn','-S','/dev/nvme0n1p1'],capture_output=True,text=True).stdout.strip()
m=P('/run/sp7-efi-inspect');m.mkdir(mode=0o700,exist_ok=True)
subprocess.run(['mount','-t','vfat','-o','ro,umask=0077','/dev/nvme0n1p1',str(m)],check=True)
try:
 assert not (m/'EFI/SP7Manjaro').exists()
 for p in sorted(m.rglob('*')):
  assert not p.is_symlink()
  if p.is_dir():r['efi_directories'].append(str(p.relative_to(m)))
  elif p.is_file():
   with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
   r['efi_files'][str(p.relative_to(m))]={'bytes':p.stat().st_size,'sha256':h}
 r['space_free_bytes']=os.statvfs(m).f_bavail*os.statvfs(m).f_frsize
finally:r['efi_unmount_exit']=subprocess.run(['umount',str(m)]).returncode
m=P('/run/sp7-root-readback');m.mkdir(mode=0o700,exist_ok=True)
subprocess.run(['mount','-t','btrfs','-o','ro,rescue=nologreplay,subvolid=5','/dev/nvme0n1p5',str(m)],check=True)
try:
 def sha(rel):
  with (m/rel).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
 r['root_hashes']={p:sha(p) for p in ['@/etc/fstab','@/boot/grub/sp7-dualboot.cfg','@/boot/grub/grub.cfg','@/boot/vmlinuz-linux-surface','@home/sp7-user/Documents/Codex/2026-10-04/ir-sensor-ansiktsinloggning/work/resume-state.json']}
 r['camera_links_absent']=all(not (m/p).is_symlink() for p in ['@/etc/systemd/system/multi-user.target.wants/sp7-camera-prepare.service','@home/sp7-user/.config/systemd/user/default.target.wants/sp7-camera-auto.service'])
finally:r['root_unmount_exit']=subprocess.run(['umount',str(m)]).returncode
print(json.dumps(r))
'''
r=run_python(source,timeout=120);assert r.returncode==0,r.stderr;j=json.loads(r.stdout);assert j['efi_unmount_exit']==j['root_unmount_exit']==0 and j['camera_links_absent'];j['host_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/before-signed-menu');p=b/'file-manifest-and-bootentries.json';assert not p.exists();p.write_text(json.dumps(j,indent=2)+'\n');(w/'pre-efi-file-inventory.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps({k:v for k,v in j.items() if k not in ['efi_files','efi_directories','efibootmgr_help']},indent=2));print(j['efibootmgr_help']);print('EFI files:',len(j['efi_files']))
