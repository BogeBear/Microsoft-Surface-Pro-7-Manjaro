from pathlib import Path
import json,base64,datetime
from live_transport import run_python
w=Path(__file__).resolve().parent
check=json.loads((w/'physical-btrfs-check.json').read_text());assert check['ssh_exit']==0 and json.loads(check['stdout'])['exit']==0
source=r'''import pathlib,subprocess,json,hashlib,base64,os
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
assert not subprocess.run(['findmnt','-rn','-S','/dev/nvme0n1p5'],capture_output=True,text=True).stdout.strip()
mount=P('/run/sp7-restored-inspect');mount.mkdir(mode=0o700,exist_ok=True)
subprocess.run(['mount','-t','btrfs','-o','ro,rescue=nologreplay,subvolid=5','/dev/nvme0n1p5',str(mount)],check=True)
r={'schema':'sp7-restored-manjaro-selected-metadata-v1','read_only':True,'selected_files':{},'kernel_files':{},'enablement_links':[],'user_autostart_files':[]}
try:
 r['subvolumes']=subprocess.check_output(['btrfs','subvolume','list','-a',str(mount)],text=True)
 paths=['@/etc/fstab','@/etc/systemd/system/sp7-camera-prepare.service','@home/sp7-user/.config/systemd/user/sp7-camera-auto.service','@home/sp7-user/.config/systemd/user/sp7-camera.service','@home/sp7-user/Documents/Codex/2026-10-04/ir-sensor-ansiktsinloggning/work/resume-state.json']
 for rel in paths:
  p=mount/rel;assert not p.is_symlink() and p.is_file(),rel;assert p.stat().st_size<=2*1024**2
  b=p.read_bytes();st=p.stat();r['selected_files'][rel]={'sha256':hashlib.sha256(b).hexdigest(),'base64':base64.b64encode(b).decode(),'uid':st.st_uid,'gid':st.st_gid,'mode':st.st_mode&0o777}
 for rel in ['@/boot/vmlinuz-linux-surface','@/boot/initramfs-linux-surface.img','@/boot/intel-ucode.img']:
  p=mount/rel;assert p.is_file() and not p.is_symlink(),rel
  with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
  r['kernel_files'][rel]={'bytes':p.stat().st_size,'sha256':h}
 for basedir in ['@/etc/systemd/system','@home/sp7-user/.config/systemd/user']:
  for p in (mount/basedir).rglob('*'):
   if p.is_symlink() and any(t in p.name for t in ['sp7','camera','sshd','ir-']):r['enablement_links'].append({'path':str(p.relative_to(mount)),'target':os.readlink(p)})
 auto=mount/'@home/sp7-user/.config/autostart'
 if auto.exists():
  for p in auto.glob('*.desktop'):
   if p.is_file():
    item={'path':str(p.relative_to(mount)),'bytes':p.stat().st_size}
    if any(v in p.name.lower() for v in ['sp7','ir-','chatgpt','codex']):
     b=p.read_bytes();assert len(b)<100000;item.update(sha256=hashlib.sha256(b).hexdigest(),text=b.decode(errors='replace'))
    r['user_autostart_files'].append(item)
 p=mount/'@/etc/ssh/ssh_host_ed25519_key.pub'
 if p.is_file():r['restored_ssh_host_public_key']=p.read_text().strip();r['restored_ssh_host_fingerprint']=subprocess.check_output(['ssh-keygen','-lf',str(p)],text=True).strip()
 p=mount/'@home/sp7-user/.ssh/authorized_keys'
 if p.is_file():r['restored_authorized_public_key_fingerprints']=subprocess.check_output(['ssh-keygen','-lf',str(p)],text=True).splitlines()
 # Only module names from known public PAM config; never passwords/shadow/wallets.
 r['pam_face_module_mentions']={}
 for name in ['system-auth','sddm','login','sudo']:
  p=mount/'@/etc/pam.d'/name
  if p.is_file():r['pam_face_module_mentions'][name]=[line for line in p.read_text().splitlines() if not line.lstrip().startswith('#') and any(v in line.lower() for v in ['howdy','face','pam_python'])]
finally:
 q=subprocess.run(['umount',str(mount)],capture_output=True,text=True);r['unmount_exit']=q.returncode
print(json.dumps(r))
'''
r=run_python(source,timeout=90);(w/'restored-actual-inventory.json').write_text(r.stdout);(w/'restored-actual-inventory.stderr.txt').write_text(r.stderr);assert r.returncode==0,r.stderr;x=json.loads(r.stdout);assert x['unmount_exit']==0
out=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/restored-config-before-adjustment');out.mkdir(mode=0o700,parents=True)
for rel,meta in x['selected_files'].items():
 b=base64.b64decode(meta['base64']);target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
(out/'inventory.json').write_text(json.dumps(x,indent=2)+'\n');brief={k:v for k,v in x.items() if k!='selected_files'};brief['selected_file_hashes']={k:v['sha256'] for k,v in x['selected_files'].items()};print(json.dumps(brief,indent=2))
