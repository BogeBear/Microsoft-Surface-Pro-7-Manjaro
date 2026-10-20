"""Add verified RAM-live firmware overlay; preserve exact existing USB helper."""
from pathlib import Path
import datetime, hashlib, json, os, shutil, subprocess
w=Path(__file__).resolve().parent
mount=Path('/run/media/sp7-user/C48C-B988')
manifest=json.loads((w/'wifi-update-manifest.json').read_text())
assert json.loads((w/'secureboot-live-candidate/wifi-overlay-vm-receipt.json').read_text())['passed']
assert json.loads((w/'wifi-update-usb-before-verification.json').read_text())['all_match']
device='/dev/disk/by-id/usb-Verbatim_STORE_N_GO_072128E995155590-0:0'
a=json.loads(subprocess.check_output(['lsblk','-J','-b','-o','NAME,SERIAL,SIZE,UUID,MOUNTPOINTS',device]))['blockdevices'][0]
assert a['serial']=='072128E995155590' and a['size']==31042043904
assert len(a['children'])==1 and a['children'][0]['uuid']=='C48C-B988' and str(mount) in a['children'][0]['mountpoints']
assert not list((mount/'live').glob('*.module'))
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
old=json.loads((w/'usb-overlay-manifest.json').read_text())
helper='SP7-DUALBOOT/enable-temporary-ssh.sh'
expected=next(f['sha256'] for f in old['files'] if f['path']==helper)
assert sha(mount/helper)==expected
assert not (mount/'live/zzz-sp7-wifi.squashfs').exists()
backup=Path('/mnt/sp7-backup/BACKUP/SP7-USB-before-wifi-fix-20261019')
backup.mkdir(mode=0o700)
(backup/'SP7-DUALBOOT').mkdir(mode=0o700)
shutil.copyfile(mount/helper,backup/helper)
assert sha(backup/helper)==expected
(backup/'receipt.json').write_text(json.dumps({'original_helper_sha256':expected,'usb_serial':a['serial'],'original_live_image_and_efi_not_modified':True},indent=2)+'\n')
receipt={'schema':'sp7-usb-wifi-update-v1','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'usb_serial':a['serial'],'uuid':'C48C-B988','original_helper_backup':str(backup/helper),'changes':[],'complete':False,'internal_sp7_disk_changed':False,'efi_and_base_live_files_changed':False,'ssh_autostart_enabled':False}
def save():(w/'wifi-usb-update-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
def atomic_copy(src,dst):
 tmp=dst.with_name(dst.name+'.sp7-update-temp')
 assert not tmp.exists()
 with src.open('rb') as a,tmp.open('xb') as b:shutil.copyfileobj(a,b);b.flush();os.fsync(b.fileno())
 assert sha(tmp)==sha(src)
 os.replace(tmp,dst)
 fd=os.open(dst.parent,os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
save()
try:
 for f in manifest['files']:
  rel=Path(f['path']);assert not rel.is_absolute() and '..' not in rel.parts
  src=w/'usb-wifi-update'/rel;assert sha(src)==f['sha256']
  atomic_copy(src,mount/rel);assert sha(mount/rel)==f['sha256']
  receipt['changes'].append(f);save()
 os.sync()
 receipt.update(complete=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
except BaseException:
 atomic_copy(backup/helper,mount/helper)
 receipt['helper_rolled_back']=True;save();raise
print(json.dumps(receipt,indent=2))
