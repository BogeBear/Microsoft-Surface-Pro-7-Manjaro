from pathlib import Path
import subprocess,json,base64,shlex,hashlib,datetime
from live_transport import BASE
w=Path(__file__).resolve().parent;out=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/before-signed-menu');out.mkdir(mode=0o700)
source=r'''import pathlib,subprocess,json,sys
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
x=json.loads(subprocess.check_output(['lsblk','--tree','-J','-b','-o','PATH,SIZE,MODEL,SERIAL,PARTUUID,MOUNTPOINTS'],text=True));d=next(p for p in x['blockdevices'] if p['path']=='/dev/nvme0n1');assert d['model']=='HFB1M8MO331C0MR' and d['serial']=='SAKKF63QB2306A013S38' and d['size']==256060514304
p=next(p for p in d['children'] if p['path']=='/dev/nvme0n1p1');assert p['partuuid']=='3f9e8859-9832-44c1-b881-62e8034abde8' and p['size']==272629760 and not any(p['mountpoints'])
with open('/dev/nvme0n1p1','rb',buffering=0) as f:
 left=272629760
 while left:
  b=f.read(min(left,1048576));assert b;sys.stdout.buffer.write(b);left-=len(b)
sys.stdout.buffer.flush()
'''
cmd='sudo -n python3 -c '+shlex.quote("exec(__import__('base64').b64decode('"+base64.b64encode(source.encode()).decode()+"'))")
p=out/'efi-before-signed-menu.raw'
with p.open('xb') as f:r=subprocess.run([*BASE,cmd],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.PIPE,timeout=120)
assert r.returncode==0 and p.stat().st_size==272629760,r.stderr
with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
x={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'/dev/nvme0n1p1','source_partition_guid':'3f9e8859-9832-44c1-b881-62e8034abde8','bytes':p.stat().st_size,'sha256':h,'complete':True,'read_only':True,'source_staging_on_sp7':False,'target':str(p)};(out/'receipt.json').write_text(json.dumps(x,indent=2)+'\n');(w/'pre-menu-efi-backup.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x,indent=2))
