"""Explicit serial/UUID; changes fallback boot FILE only after complete verified payload."""
from pathlib import Path
import os,json,hashlib,subprocess,tempfile,shutil,time
w=Path(__file__).resolve().parent;m=json.loads((w/'usb-overlay-manifest.json').read_text());mount=Path('/run/media/sp7-user/C48C-B988');backup=Path(m['original_efi_backup']);old=json.loads((backup/'manifest.json').read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def require(ok,msg):
 if not ok:raise RuntimeError(msg)
fm=json.loads(subprocess.check_output(['findmnt','--json','--target',str(mount),'-o','SOURCE,TARGET,FSTYPE,OPTIONS']));fs=fm['filesystems'][0]
require(fs['target']==str(mount) and fs['fstype']=='vfat' and 'rw' in fs['options'].split(','),'Expected writable FAT volume mount only')
a=json.loads(subprocess.check_output(['lsblk','-J','-b','-o','NAME,PATH,SIZE,MODEL,SERIAL,FSTYPE,UUID,MOUNTPOINTS','/dev/disk/by-id/usb-Verbatim_STORE_N_GO_072128E995155590-0:0']))['blockdevices']
require(len(a)==1 and a[0]['serial']==m['usb_serial'] and a[0]['size']==31042043904,'USB identity changed')
parts=a[0]['children'];require(len(parts)==1 and parts[0]['uuid']==m['usb_uuid'] and str(mount) in parts[0]['mountpoints'],'USB partition identity changed')
require(old['all_files_byte_verified'] is True,'Missing original EFI backup')
for f in old['files']:
 require(sha(backup/f['path'])==f['sha256'],'Original backup changed')
 require(sha(mount/f['path'])==f['sha256'],'Existing EFI changed since backup')
require(shutil.disk_usage(mount).free>sum(x['bytes'] for x in m['files'])+100*1024**2,'Insufficient USB space')
for f in m['files']:
 rel=Path(f['path']);require(not rel.is_absolute() and '..' not in rel.parts,'Invalid manifest path')
 require(sha(w/'usb-overlay'/rel)==f['sha256'],'Prepared payload hash differs')
 if f['path']!='EFI/Boot/bootx64.efi':require(not (mount/rel).exists(),'Unreviewed existing path collision: '+f['path'])
receipt={'schema':'sp7-additive-live-usb-install-v1','complete':False,'usb_serial':m['usb_serial'],'usb_uuid':m['usb_uuid'],'partition_tables_formatted_or_changed':False,'internal_sp7_changed':False,'original_efi_backup':str(backup),'started_epoch':time.time(),'new_files':[]}
def save():(w/'usb-install-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
def atomic_copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.parent/(dst.name+'.sp7-copy-temp')
 require(not tmp.exists(),'Temporary path already exists')
 try:
  with src.open('rb') as a,tmp.open('xb') as b:shutil.copyfileobj(a,b);b.flush();os.fsync(b.fileno())
  require(sha(tmp)==sha(src),'USB temporary copy verification failed');os.replace(tmp,dst)
  fd=os.open(dst.parent,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 finally:
  if tmp.exists():tmp.unlink()
save()
try:
 ordered=sorted(m['files'],key=lambda f:f['path']=='EFI/Boot/bootx64.efi')
 for f in ordered:
  atomic_copy(w/'usb-overlay'/f['path'],mount/f['path']);require(sha(mount/f['path'])==f['sha256'],'Written USB file differs');receipt['new_files'].append(f);save()
 for f in old['files']:
  if f['path']!='EFI/Boot/bootx64.efi':require(sha(mount/f['path'])==f['sha256'],'Original Windows EFI file unexpectedly changed')
 receipt.update(complete=True,windows_recovery_efi_unchanged_except_backed_up_fallback=True,finished_epoch=time.time());save();print(json.dumps(receipt,indent=2))
except BaseException as e:
 # Restore only the original fallback FILE. Other newly added files remain inactive.
 try:atomic_copy(backup/'EFI/Boot/bootx64.efi',mount/'EFI/Boot/bootx64.efi');receipt['original_fallback_restored_after_failure']=True
 except Exception as rollback:receipt['rollback_error']=type(rollback).__name__+': '+str(rollback)
 receipt.update(error=type(e).__name__+': '+str(e));save();raise
