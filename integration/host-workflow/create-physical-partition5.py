from pathlib import Path
import sys,json,base64,hashlib,datetime
from live_transport import run_python
w=Path(__file__).resolve().parent
assert json.loads((w/'secureboot-live-candidate/partition5-vm-receipt.json').read_text())['passed']
approval=json.loads((w/'USER-DUALBOOT-APPROVAL.json').read_text());assert approval['approved_plan_sha256']==hashlib.sha256((w/'EXACT-DISK-WRITE-PLAN.json').read_bytes()).hexdigest()
p=w/'physical-partition5-apply.json';assert not p.exists(),'Existing physical attempt: inspect actual status, do not repeat'
code=(w/'gpt_partition5.py').read_bytes();encoded=base64.b64encode(code).decode();record={'host_started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state':'pending','code_sha256':hashlib.sha256(code).hexdigest(),'plan_sha256':approval['approved_plan_sha256']};p.write_text(json.dumps(record,indent=2)+'\n')
source=r'''import pathlib,subprocess,json,hashlib,base64,types,stat,math
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
assert P('/sys/class/dmi/id/product_name').read_text().strip()=='Surface Pro 7'
assert 'boot=live' in P('/proc/cmdline').read_text().split()
assert subprocess.check_output(['findmnt','-n','-o','FSTYPE','/'],text=True).strip()=='overlay'
assert P('/sys/class/power_supply/ADP1/online').read_text().strip()=='1'
assert P('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c').read_bytes()[4]==1
ls=json.loads(subprocess.check_output(['lsblk','--tree','-J','-b','-o','PATH,SIZE,MODEL,SERIAL,MOUNTPOINTS'],text=True))
d=next(d for d in ls['blockdevices'] if d['path']=='/dev/nvme0n1');assert d['size']==256060514304 and d['model']=='HFB1M8MO331C0MR' and d['serial']=='SAKKF63QB2306A013S38'
assert len(d['children'])==4 and all(not any(p['mountpoints']) for p in d['children'])
cpu=json.loads(subprocess.check_output(['sensors','-j'],text=True))['coretemp-isa-0000'];temperatures={k:next(float(v) for n,v in cpu[k].items() if n.endswith('_input')) for k in ['Package id 0','Core 0','Core 1','Core 2','Core 3']};assert all(math.isfinite(v) and -20<=v<60 for v in temperatures.values())
code=base64.b64decode('CODE');assert hashlib.sha256(code).hexdigest()=='CODESHA'
m=types.ModuleType('gpt_partition5');exec(code,m.__dict__)
r=m.append('/dev/nvme0n1','5ebc4e587c4e64554cd1146d16add8ab026c531b145b266bc47090aff9b28605','8a9f119780421747de08fa7fac436c72d6f79bd97034c5ba2facd7d206aa04b0')
subprocess.run(['udevadm','settle','--timeout=10'],check=True)
assert stat.S_ISBLK(P('/dev/nvme0n1p5').stat().st_mode)
assert int(subprocess.check_output(['blockdev','--getsize64','/dev/nvme0n1p5'],text=True))==117212971008
assert int(P('/sys/class/block/nvme0n1p5/start').read_text())*512==137729409024
r.update(boot_id=P('/proc/sys/kernel/random/boot_id').read_text().strip(),temperatures=temperatures,table=json.loads(subprocess.check_output(['sfdisk','--json','/dev/nvme0n1'],text=True)))
t=m.read_table('/dev/nvme0n1');r['gpt_primary_base64']=base64.b64encode(t['primary']).decode();r['gpt_secondary_base64']=base64.b64encode(t['secondary']).decode()
print(json.dumps(r))
'''.replace('CODESHA',hashlib.sha256(code).hexdigest()).replace('CODE',encoded)
r=run_python(source,timeout=70);record.update(host_finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit=r.returncode,stdout=r.stdout,stderr=r.stderr);p.write_text(json.dumps(record,indent=2)+'\n');assert r.returncode==0,r.stderr
result=json.loads(r.stdout);backup=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/after-partition5');backup.mkdir(mode=0o700,parents=True)
for key,name,sha in [('gpt_primary_base64','gpt-primary.bin','primary_sha256'),('gpt_secondary_base64','gpt-secondary.bin','secondary_sha256')]:
 b=base64.b64decode(result.pop(key));assert hashlib.sha256(b).hexdigest()==result[sha];(backup/name).write_bytes(b)
(backup/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');record.update(state='complete',result=result,raw_gpt_backup=str(backup));p.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(result,indent=2))
