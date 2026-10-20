"""Host decompression/hash; physical receiver writes ONLY validated Linux5, checks CRC."""
from pathlib import Path
import os,sys,json,datetime,time,subprocess,base64,hashlib,shlex
from live_transport import BASE
w=Path(__file__).resolve().parent
p=w/'physical-manjaro-restore-result.json';assert not p.exists(),'Prior restore attempt exists; inspect actual state, never blindly retry'
assert json.loads((w/'protective-mbr-physical-preservation.json').read_text())['complete']
pack=Path('/mnt/sp7-backup/BACKUP/SP7-Manjaro-dualboot-working-copy-20261019');status=json.loads((pack/'package-status.json').read_text());source=pack/'manjaro-108GiB.btrfs.pcl.zst';assert status['complete'] and source.stat().st_size==35108126331 and status['compressed_sha256']=='da51e96917e1ab5944acebbf27918af9ab6b4133107033f8ae51639e159dd047'
code=base64.b64encode((w/'gpt_partition5.py').read_bytes()).decode()
receiver=r'''import pathlib,os,stat,subprocess,json,base64,types,hashlib,sys,time
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
assert P('/sys/class/dmi/id/product_name').read_text().strip()=='Surface Pro 7'
assert subprocess.check_output(['findmnt','-n','-o','FSTYPE','/'],text=True).strip()=='overlay'
assert 'boot=live' in P('/proc/cmdline').read_text().split()
assert P('/sys/class/power_supply/ADP1/online').read_text().strip()=='1'
assert P('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c').read_bytes()[4]==1
ls=json.loads(subprocess.check_output(['lsblk','--tree','-J','-b','-o','PATH,SIZE,MODEL,SERIAL,MOUNTPOINTS,PARTUUID'],text=True));disk=next(x for x in ls['blockdevices'] if x['path']=='/dev/nvme0n1');assert disk['model']=='HFB1M8MO331C0MR' and disk['serial']=='SAKKF63QB2306A013S38' and disk['size']==256060514304 and len(disk['children'])==5 and all(not any(p['mountpoints']) for p in disk['children'])
target='/dev/nvme0n1p5';part=next(x for x in disk['children'] if x['path']==target);assert part['size']==117212971008 and part['partuuid']=='bf612ca5-d2c9-4eec-b8b9-99f5321fbfe0'
assert stat.S_ISBLK(P(target).stat().st_mode) and int(P('/sys/class/block/nvme0n1p5/start').read_text())*512==137729409024
m=types.ModuleType('g');exec(base64.b64decode('CODE'),m.__dict__)
def bound():
 t=m.read_table('/dev/nvme0n1');assert hashlib.sha256(t['primary']).hexdigest()=='2db64ccac0d0500761a35eda5c2d35f0bdb08cf4776fbe0959b35001027110e1' and hashlib.sha256(t['secondary']).hexdigest()=='3246c22cb5bba2acf5671160636b30a1a9b3413ff4a74eb08ad4aaf8887c6dd5'
bound();root=P('/run/sp7-dualboot-restore');root.mkdir(mode=0o700)
r={'schema':'sp7-physical-manjaro-restore-receiver-v1','target':target,'target_partition_guid':part['partuuid'],'started_monotonic':time.monotonic(),'phase':'precheck_passed','crc_and_device_size_checks_enabled':True,'internal_other_partitions_unmounted':True}
(root/'status.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
with (root/'console.log').open('xb') as log:
 q=subprocess.run(['partclone.restore','-s','-','-o',target,'-L',str(root/'partclone.log'),'-B'],stdin=sys.stdin.buffer,stdout=log,stderr=log)
r.update(partclone_exit=q.returncode,finished_monotonic=time.monotonic(),phase='restore_failed' if q.returncode else 'restore_written');(root/'status.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True);assert q.returncode==0
with open(target,'rb',buffering=0) as f:os.fsync(f.fileno())
bound();meta=subprocess.check_output(['blkid','-p','-o','export',target],text=True);fields=dict(line.split('=',1) for line in meta.splitlines() if '=' in line);assert fields['TYPE']=='btrfs' and fields['UUID']=='b7e9ce03-4b90-4c6a-8091-643c8c5879e5'
r.update(phase='restore_complete_unmounted',filesystem_type=fields['TYPE'],filesystem_uuid=fields['UUID'],gpt_after_restore_unchanged=True);(root/'status.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
'''.replace('CODE',code)
encoded=base64.b64encode(receiver.encode()).decode();remote='sudo -n python3 -c '+shlex.quote("exec(__import__('base64').b64decode('"+encoded+"'))")
record={'schema':'sp7-host-stream-restore-v1','started_host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'starting','source':str(source),'source_bytes':source.stat().st_size,'source_expected_sha256':status['compressed_sha256'],'target_partition_guid':'bf612ca5-d2c9-4eec-b8b9-99f5321fbfe0','source_image_not_staged_on_sp7':True,'crc_and_device_size_checks_enabled':True};p.write_text(json.dumps(record,indent=2)+'\n')
start=time.monotonic();count=0;next_report=128*1024**2;h=hashlib.sha256();z=None;ssh=None
try:
 with (w/'physical-restore-zstd.stderr.txt').open('xb') as zlog,(w/'physical-restore-ssh.stderr.txt').open('xb') as slog,(w/'physical-restore-receiver.jsonl').open('xb') as out:
  z=subprocess.Popen(['zstd','-dc'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=zlog)
  ssh=subprocess.Popen([*BASE,remote],stdin=z.stdout,stdout=out,stderr=slog);z.stdout.close()
  with source.open('rb') as stream:
   while block:=stream.read(8*1024*1024):
    h.update(block);z.stdin.write(block);count+=len(block)
    if count>=next_report:
     elapsed=time.monotonic()-start
     progress={'compressed_bytes_queued_to_decompressor':count,'total_compressed_bytes':record['source_bytes'],'elapsed_seconds':elapsed,'percent':100*count/record['source_bytes']}
     (w/'physical-restore-progress.json').write_text(json.dumps(progress)+'\n');print(json.dumps(progress),flush=True);next_report=count+128*1024**2
  z.stdin.close();zr=z.wait();sr=ssh.wait()
  record.update(zstd_exit=zr,ssh_exit=sr,compressed_bytes=count,compressed_sha256=h.hexdigest(),elapsed_seconds=time.monotonic()-start)
  assert zr==0 and sr==0 and count==record['source_bytes'] and h.hexdigest()==record['source_expected_sha256'],'Restore stream/hash/exit did not verify'
  results=[json.loads(line) for line in (w/'physical-restore-receiver.jsonl').read_text().splitlines() if line.strip()]
  assert results[-1]['phase']=='restore_complete_unmounted';record['receiver']=results[-1];record['phase']='complete_unmounted_pending_physical_btrfs_check'
except BaseException as e:
 record.update(phase='failed_inspect_before_retry',error=type(e).__name__+': '+str(e),compressed_bytes=count,elapsed_seconds=time.monotonic()-start)
 for child in [z,ssh]:
  if child is not None and child.poll() is None:child.terminate()
 for child in [z,ssh]:
  if child is not None:
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:child.kill();child.wait()
 raise
finally:
 record['finished_host_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();p.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2),flush=True)
