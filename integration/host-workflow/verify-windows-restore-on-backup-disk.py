"""Apply verified Windows WIM to a private ordinary NTFS file, never a VM/device."""
from pathlib import Path
import hashlib,json,os,subprocess,time
os.umask(0o077);w=Path(__file__).resolve().parent;b=Path('/mnt/sp7-backup/BACKUP/SP7-Windows-before-dualboot-20261019/image-attempt2');state=json.loads((b/'status.json').read_text());assert state['complete'] is True and state['phase']=='standard_wim_verified_on_bogebear'
image=Path(state['standard_wim']['path']);assert image==b/'windows-before-dualboot.wim' and image.is_file()
target=b/'windows-restore-test.ntfs.raw';assert not target.exists();assert os.statvfs(b).f_bavail*os.statvfs(b).f_frsize>75*1024**3
with target.open('xb') as f:f.truncate(128*1024**3)
report={'schema':'windows-ordinary-file-ntfs-restore-test-v1','complete':False,'real_device_or_vm_used':False,'source_wim_sha256':state['standard_wim']['sha256'],'phase':'format_new_private_file','target':str(target),'started_epoch':time.time()}
def save():(b/'restore-test.json').write_text(json.dumps(report,indent=2)+'\n')
def run(args,name):
 with (b/(name+'.log')).open('xb') as log:r=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log,timeout=7200)
 report[name+'_rc']=r.returncode;save();assert r.returncode==0,(name,r.returncode)
save()
run([str(w/'portable-tools/ntfsprogs/usr/bin/mkntfs'),'-F','-Q','-s','512','-c','4096','-p','567296','-L','SP7_RECOVERY_TEST',str(target)],'ntfs-format')
report['phase']='apply_wim_to_ordinary_file';save()
run([str(w/'portable-tools/wimlib-1.14.5/wimlib-imagex'),'apply',str(image),'1',str(target),'--check','--strict-acls'],'actual-windows-apply')
# The preceding --check reads WIM integrity and all applied stream hashes.
# No individual private files are opened for inspection or exposed to a VM.
report.update(complete=True,phase='all_wim_streams_applied_with_ntfs_metadata',finished_epoch=time.time(),logical_bytes=target.stat().st_size,allocated_bytes=target.stat().st_blocks*512,physical_windows_boot_tested=False,no_credentials_inspected=True);save();target.unlink();report['derived_restore_test_file_removed_after_success']=True;save();print(json.dumps(report,indent=2),flush=True)
