"""One-shot local copy resize. Normal pkexec authorization required.
Does not install a service, policy, or privilege grant. No physical SP7 disk.
No image file contents, wallet files or credentials are accessed.
"""
import fcntl,json,os,pathlib,stat,struct,subprocess,time
BASE=pathlib.Path('/srv/sp7-project/host/work/sp7-dualboot-20261019')
IMAGE=pathlib.Path('/mnt/sp7-backup/BACKUP/SP7-Manjaro-dualboot-working-copy-20261019/manjaro-working-copy.img')
BEFORE=255743810560
AFTER=108*1024**3
EXPECTED_UUID=bytes.fromhex('b7e9ce034b904c6a8091643c8c5879e5')
OWNER=1000
report={'schema':'sp7-local-copy-shrink-v1','physical_disk_changed':False,'original_compressed_backup_changed':False,'secrets_read':False,'started_epoch':time.time(),'completed':False}
def cmd(args,**kw):
 return subprocess.run(args,check=True,capture_output=True,text=True,timeout=1800,**kw).stdout
assert os.geteuid()==0,'Normal system authorization is required'
receipt=json.loads((BASE/'manjaro-copy-restored-v5.json').read_text())
assert receipt['btrfs_check_rc']==0 and receipt['source_hash_matches'] is True
relocated=json.loads((BASE/'manjaro-copy-relocated.json').read_text())
assert receipt['target']==relocated['source'] and relocated['target']==str(IMAGE)
assert relocated['byte_for_byte_cmp_exit']==0 and relocated['logical_bytes']==BEFORE
assert not (BASE/'manjaro-copy-resize-receipt.json').exists()
fd=os.open(IMAGE,os.O_RDWR|os.O_NOFOLLOW)
loop=None;mounted=False;mountpoint=None
try:
 fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 s=os.fstat(fd)
 assert stat.S_ISREG(s.st_mode) and s.st_uid==OWNER and s.st_size==BEFORE
 assert s.st_nlink==1 and not (s.st_mode&0o077),'Private ordinary copy required'
 sb=os.pread(fd,4096,65536)
 assert sb[0x40:0x48]==b'_BHRfS_M' and sb[0x20:0x30]==EXPECTED_UUID
 assert struct.unpack_from('<Q',sb,0x70)[0]==BEFORE-3072,'Original filesystem size differs'
 assert struct.unpack_from('<Q',sb,0x88)[0]==1,'Single-device Btrfs required'
 os.unshare(os.CLONE_NEWNS)
 cmd(['/usr/bin/mount','--make-rprivate','/'])
 mountpoint=pathlib.Path('/run/sp7-copy-resize-'+str(os.getpid()))
 mountpoint.mkdir(mode=0o700)
 # Refuse an already attached copy before creating our temporary loop.
 existing=json.loads(cmd(['/usr/bin/losetup','--json','--list','--output','NAME,BACK-FILE']))
 assert all(x.get('back-file')!=str(IMAGE) for x in existing.get('loopdevices',[])), 'Copy already attached'
 # Loop device attaches only the already-open, checked ordinary file.
 loop=cmd(['/usr/bin/losetup','--find','--show','--nooverlap','--sizelimit',str(BEFORE),'/proc/self/fd/'+str(fd)],pass_fds=(fd,)).strip()
 assert loop.startswith('/dev/loop') and loop[9:].isdigit()
 cmd(['/usr/bin/mount','-t','btrfs','-o','rw,nosuid,nodev,noexec,subvolid=5',loop,str(mountpoint)])
 mounted=True
 report['resize_output']=cmd(['/usr/bin/btrfs','filesystem','resize',str(AFTER),str(mountpoint)]).strip()
 cmd(['/usr/bin/sync','-f',str(mountpoint)])
 cmd(['/usr/bin/umount',str(mountpoint)]);mounted=False
 cmd(['/usr/bin/losetup','--detach',loop]);loop=None
 sb=os.pread(fd,4096,65536)
 assert sb[0x40:0x48]==b'_BHRfS_M' and sb[0x20:0x30]==EXPECTED_UUID
 assert struct.unpack_from('<Q',sb,0x70)[0]==AFTER,'Do not truncate before successful resize'
 assert os.stat(IMAGE).st_ino==s.st_ino and os.stat(IMAGE).st_dev==s.st_dev
 os.ftruncate(fd,AFTER);os.fsync(fd)
 report.update(completed=True,finished_epoch=time.time(),before_bytes=BEFORE,after_bytes=AFTER,loop_detached=True,filesystem_unmounted=True,private_mount_namespace=True)
finally:
 if mounted:
  try:cmd(['/usr/bin/umount',str(mountpoint)]);mounted=False
  except BaseException:report['unmount_failed']=True
 if loop and not mounted:
  try:cmd(['/usr/bin/losetup','--detach',loop]);loop=None
  except BaseException:report['detach_failed']=True
 if mountpoint and not mounted:
  try:mountpoint.rmdir()
  except OSError:pass
 os.close(fd)
 report['final_unmounted']=not mounted;report['final_loop_detached']=loop is None
 target=BASE/'manjaro-copy-resize-receipt.json'
 with target.open('x') as out:json.dump(report,out,indent=2);out.write('\n')
 os.chmod(target,0o600);os.chown(target,OWNER,OWNER)
print('Local Manjaro COPY shrink complete; physical disks unchanged')
