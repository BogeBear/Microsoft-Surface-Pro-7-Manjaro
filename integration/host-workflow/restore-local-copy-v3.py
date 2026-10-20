"""Restore the existing Manjaro image to a new regular sparse file only.
Never mounts or boots it, reads individual files, or writes a disk device.
"""
from pathlib import Path
import datetime,hashlib,json,os,shutil,subprocess,time
os.umask(0o077)
root=Path.cwd();work=root/'work/sp7-dualboot-20261019';backup=Path('/mnt/sp7-backup/BACKUP/SP7-system-image-20261014');runtime=backup/'runtime';stage=work/'staging';stage.mkdir(mode=0o700,exist_ok=True)
source=backup/'nvme0n1p2.btrfs.pcl.zst';info=json.loads((backup/'image-manifest.json').read_bytes())[source.name]
assert source.stat().st_size==info['bytes'] and shutil.disk_usage(work).free>90*1024**3
out=stage/'manjaro-original-copy-v3.img';assert not out.exists()
assert (runtime/'usr/sbin/partclone.restore').is_file()
cmd=['bwrap','--unshare-all','--die-with-parent','--ro-bind',str(runtime),'/', '--bind',str(stage),'/out','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--chdir','/tmp','/lib64/ld-linux-x86-64.so.2','--library-path','/usr/lib/x86_64-linux-gnu','/usr/sbin/partclone.restore','-s','-','-o','/out/manjaro-original-copy-v3.img','-W','-C','-L','/tmp/restore.log']
start=time.time();h=hashlib.sha256();count=0
with (work/'restore-local-copy-v3.log').open('xb') as log:
 z=subprocess.Popen(['zstd','-dc'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
 r=subprocess.Popen(cmd,stdin=z.stdout,stdout=log,stderr=log);z.stdout.close()
 try:
  with source.open('rb') as stream:
   while block:=stream.read(8*1024*1024):
    h.update(block);z.stdin.write(block);count+=len(block)
    if count%(512*1024*1024)==0:
     (work/'restore-progress.json').write_text(json.dumps(dict(compressed_bytes_read=count,total_compressed_bytes=info['bytes'],elapsed_seconds=time.time()-start))+'\n')
  z.stdin.close();zr=z.wait();rr=r.wait()
 except BaseException:
  z.kill();r.kill();z.wait();r.wait();raise
assert rr==0 and zr==0 and h.hexdigest()==info['sha256'],(rr,zr,h.hexdigest())
with (work/'manjaro-copy-btrfs-check-v3.log').open('xb') as log:
 result=subprocess.run(['btrfs','check','--readonly','--check-data-csum',str(out)],stdout=log,stderr=log)
receipt=dict(schema='sp7-local-manjaro-image-copy-v1',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=str(source),source_sha256=h.hexdigest(),source_hash_matches=True,restore_rc=rr,decompress_rc=zr,btrfs_check_rc=result.returncode,target=str(out),logical_bytes=out.stat().st_size,allocated_bytes=out.stat().st_blocks*512,seconds=time.time()-start,ordinary_file_only=True,partclone_device_size_free_space_check_skipped_only_for_sparse_file=True,minimum_real_free_bytes=90*1024**3,no_filesystem_mounted=True,no_guest_vm_used=True,no_secrets_extracted=True,physical_disk_written=False,original_backup_written=False)
(work/'manjaro-copy-restored.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));raise SystemExit(result.returncode)
