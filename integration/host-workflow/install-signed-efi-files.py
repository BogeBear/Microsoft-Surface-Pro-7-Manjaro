from pathlib import Path
import json,hashlib,base64,datetime
from live_transport import run_python
w=Path(__file__).resolve().parent
before=json.loads((w/'pre-efi-file-inventory.json').read_text());backup=json.loads((w/'pre-menu-efi-backup.json').read_text());assert backup['complete']
files={}
for name,src,h in [
 ('shimx64.efi','secureboot-candidate/shimx64.efi','637d7916c0b0b9cb505612f39e8c47b47894957f15a1e711b22a2ae5bbec286d'),
 ('grubx64.efi','secureboot-candidate/debian-grub-2.14-4.efi','dc5cac61abfd5bf457e67b79ffa1e02ab511e55052628d66a37122b2334aaafa'),
 ('mmx64.efi','secureboot-candidate/mmx64.efi','3480a42892865d356a15759cb2271bfeb009d5687c153896d3983c354cd2d949'),
 ('surface.cer','secureboot-candidate/surface.cer','081202cf3ea30519046bbb9faf5dafe24c3fdf56b79afea62778f24913ab6d64'),
 ('grub.cfg','dualboot-config-candidate/efi-grub.cfg','ca1936dee4b97b480105db3e081dcab27128286306d2fd288b82c3196a57bbe7')]:
 b=(w/src).read_bytes();assert hashlib.sha256(b).hexdigest()==h;files[name]={'sha256':h,'bytes':len(b),'base64':base64.b64encode(b).decode()}
payload={'files':files,'original':before['efi_files'],'raw_sha256':backup['sha256']}
source=r'''import pathlib,json,hashlib,base64,subprocess,os
P=pathlib.Path;D=PAYLOAD
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
assert subprocess.check_output(['blkid','-s','UUID','-o','value','/dev/nvme0n1p1'],text=True).strip()=='9E39-0F59'
assert not subprocess.run(['findmnt','-rn','-S','/dev/nvme0n1p1'],capture_output=True,text=True).stdout.strip()
with open('/dev/nvme0n1p1','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==D['raw_sha256']
m=P('/run/sp7-efi-deploy');m.mkdir(mode=0o700,exist_ok=True)
r={'schema':'sp7-signed-efi-file-deployment-v1','complete':False}
def manifest():
 out={}
 for p in sorted(m.rglob('*')):
  assert not p.is_symlink()
  if p.is_file():
   with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
   out[str(p.relative_to(m))]={'bytes':p.stat().st_size,'sha256':h}
 return out
subprocess.run(['mount','-t','vfat','-o','rw,umask=0077','/dev/nvme0n1p1',str(m)],check=True)
try:
 assert manifest()==D['original'],'EFI original manifest changed'
 stage=m/'EFI/.SP7Manjaro-stage-20261019';dest=m/'EFI/SP7Manjaro';assert not stage.exists() and not dest.exists()
 stage.mkdir()
 for name,meta in D['files'].items():
  assert '/' not in name;data=base64.b64decode(meta['base64']);assert hashlib.sha256(data).hexdigest()==meta['sha256']
  with (stage/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 stage.rename(dest);subprocess.run(['sync','-f',str(m)],check=True)
 r['write_complete']=True
finally:r['write_unmount_exit']=subprocess.run(['umount',str(m)]).returncode
assert r['write_unmount_exit']==0
subprocess.run(['mount','-t','vfat','-o','ro,umask=0077','/dev/nvme0n1p1',str(m)],check=True)
try:
 actual=manifest();new={'EFI/SP7Manjaro/'+n:{k:v for k,v in meta.items() if k!='base64'} for n,meta in D['files'].items()}
 assert actual=={**D['original'],**new},'Readback differs from originals plus exactly new folder'
 r.update(complete=True,original_files_count=len(D['original']),original_files_byte_identical=True,new_files=new,firmware_not_yet_changed=True)
finally:r['readback_unmount_exit']=subprocess.run(['umount',str(m)]).returncode
P('/run/sp7-efi-file-deployment.json').write_text(json.dumps(r));print(json.dumps(r))
'''.replace('PAYLOAD',repr(payload))
assert not (w/'physical-signed-efi-files.json').exists(),'Existing result: do not rerun'
r=run_python(source,timeout=120);out={'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};(w/'physical-signed-efi-files.json').write_text(json.dumps(out,indent=2)+'\n');print(r.stdout);assert r.returncode==0,r.stderr
x=json.loads(r.stdout);assert x['complete'] and x['readback_unmount_exit']==0
b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019');(b/'signed-efi-file-deployment.json').write_text(json.dumps(out,indent=2)+'\n')
