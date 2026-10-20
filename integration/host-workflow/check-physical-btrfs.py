from pathlib import Path
import datetime,json,hashlib
from live_transport import run_python
w=Path(__file__).resolve().parent
x=json.loads((w/'physical-manjaro-restore-result.json').read_text());assert x['phase']=='complete_unmounted_pending_physical_btrfs_check'
source=r'''import pathlib,subprocess,json,hashlib,time
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
assert json.loads(P('/run/sp7-dualboot-restore/status.json').read_text())['phase']=='restore_complete_unmounted'
assert not subprocess.run(['findmnt','-rn','-S','/dev/nvme0n1p5'],capture_output=True,text=True).stdout.strip()
assert int(subprocess.check_output(['blockdev','--getsize64','/dev/nvme0n1p5'],text=True))==117212971008
start=time.monotonic();q=subprocess.run(['btrfs','check','--readonly','--check-data-csum','/dev/nvme0n1p5'],capture_output=True,text=True,timeout=1200)
log=q.stdout+q.stderr;P('/run/sp7-dualboot-restore/btrfs-check.log').write_text(log)
r={'schema':'sp7-restored-btrfs-physical-check-v1','exit':q.returncode,'read_only':True,'data_checksums_enabled':True,'seconds':time.monotonic()-start,'log':log}
print(json.dumps(r),flush=True)
'''
r=run_python(source,timeout=1250);record={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(w/'physical-btrfs-check.json').write_text(json.dumps(record,indent=2)+'\n');assert r.returncode==0,r.stderr;x=json.loads(r.stdout);assert x['exit']==0,x['log'];print(json.dumps({k:v for k,v in x.items() if k!='log'}));print(x['log'][-1800:])
