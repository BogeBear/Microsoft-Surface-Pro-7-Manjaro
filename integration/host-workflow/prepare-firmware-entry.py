from pathlib import Path
import json,datetime
from live_transport import run_python
w=Path(__file__).resolve().parent
x=json.loads((w/'physical-signed-efi-files.json').read_text());assert x['ssh_exit']==0 and json.loads(x['stdout'])['complete']
source=r'''import pathlib,subprocess,json,base64,re
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
r={'boot_entries':subprocess.check_output(['efibootmgr','-v'],text=True),'variables':{}}
for p in P('/sys/firmware/efi/efivars').glob('Boot*-8be4df61-93ca-11d2-aa0d-00e098032b8c'):
 name=p.name.split('-')[0]
 if re.fullmatch(r'Boot(?:[0-9A-Fa-f]{4}|Order|Next|Current)',name):r['variables'][p.name]=base64.b64encode(p.read_bytes()).decode()
print(json.dumps(r))
'''
r=run_python(source);assert r.returncode==0,r.stderr;j=json.loads(r.stdout);j['host_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/before-signed-menu/boot-variables-before.json');assert not b.exists();b.write_text(json.dumps(j,indent=2)+'\n');(w/'firmware-before-create.json').write_text(json.dumps(j,indent=2)+'\n');print('Boot variables saved:',len(j['variables']));print(j['boot_entries'].splitlines()[:3])
