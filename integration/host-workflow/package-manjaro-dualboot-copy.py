"""Encode the resized private ordinary file; sources mounted read-only in bwrap."""
from pathlib import Path
import hashlib,json,os,subprocess,time
os.umask(0o077)
w=Path(__file__).resolve().parent;b=Path('/mnt/sp7-backup/BACKUP');d=b/'SP7-Manjaro-dualboot-working-copy-20261019';runtime=b/'SP7-system-image-20261014/runtime';source=d/'manjaro-working-copy.img';target=d/'manjaro-108GiB.btrfs.pcl.zst';assert not target.exists()
r=json.loads((w/'manjaro-copy-resize-receipt.json').read_text());c=json.loads((w/'manjaro-resized-btrfs-check.json').read_text());assert r['completed'] and r['final_loop_detached'] and r['final_unmounted'] and c['rc']==0 and source.stat().st_size==115964116992
base=['bwrap','--unshare-all','--die-with-parent','--ro-bind',str(runtime),'/', '--ro-bind',str(d),'/out','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--chdir','/tmp','/lib64/ld-linux-x86-64.so.2','--library-path','/usr/lib/x86_64-linux-gnu']
started=time.time();report={'schema':'resized-manjaro-partclone-package-v1','complete':False,'physical_device_used':False,'root_used':False,'source_readonly_to_encoder':True,'source':str(source),'source_logical_bytes':source.stat().st_size,'target':str(target)}
def save():(d/'package-status.json').write_text(json.dumps(report,indent=2)+'\n')
save()
with target.open('xb') as output,(w/'manjaro-partclone-encode.log').open('xb') as log:
 clone=subprocess.Popen(base+['/usr/sbin/partclone.btrfs','-c','-s','/out/'+source.name,'-o','-','-L','/tmp/clone.log'],stdout=subprocess.PIPE,stderr=log)
 zip=subprocess.Popen(['zstd','-T4','-3','-c'],stdin=clone.stdout,stdout=output,stderr=log);clone.stdout.close()
 cr=clone.wait();zr=zip.wait()
 report.update(clone_rc=cr,compress_rc=zr);save();assert cr==0 and zr==0,(cr,zr)
report['phase']='verify_partclone_crc';save()
with (w/'manjaro-partclone-package-verify.log').open('xb') as log:
 z=subprocess.Popen(['zstd','-dc',str(target)],stdout=subprocess.PIPE,stderr=log)
 v=subprocess.Popen(base+['/usr/sbin/partclone.chkimg','-s','-','-L','/tmp/verify.log'],stdin=z.stdout,stdout=log,stderr=log);z.stdout.close();vr=v.wait();zr=z.wait()
report.update(verify_rc=vr,decompress_verify_rc=zr);save();assert vr==0 and zr==0
report.update(complete=True,phase='verified_resized_partclone_image',compressed_bytes=target.stat().st_size,compressed_sha256=hashlib.file_digest(target.open('rb'),'sha256').hexdigest(),seconds=time.time()-started,original_backup_untouched=True,physical_boot_after_restore_tested=False)
save();print(json.dumps(report,indent=2),flush=True)
