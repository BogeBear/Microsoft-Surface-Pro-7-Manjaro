from pathlib import Path
import json,base64,datetime
from live_transport import run_python
w=Path(__file__).resolve().parent
before=json.loads((w/'firmware-before-create.json').read_text())
source=r'''import pathlib,subprocess,json,base64,re,struct,uuid
P=pathlib.Path;D=BEFORE;guid='8be4df61-93ca-11d2-aa0d-00e098032b8c';V=P('/sys/firmware/efi/efivars')
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
assert json.loads(P('/run/sp7-efi-file-deployment.json').read_text())['complete']
def variables():
 return {p.name:base64.b64encode(p.read_bytes()).decode() for p in V.glob('Boot*-'+guid) if re.fullmatch(r'Boot(?:[0-9A-Fa-f]{4}|Order|Next|Current)',p.name.split('-')[0])}
def bootnums(raw):
 b=base64.b64decode(raw)[4:];assert len(b)%2==0;return list(struct.unpack('<'+'H'*(len(b)//2),b))
assert variables()==D['variables'],'Boot variables changed since saved backup'
ordername='BootOrder-'+guid;oldorder=bootnums(D['variables'][ordername]);assert oldorder==[5,1,4,0,2]
assert subprocess.check_output(['sfdisk','--part-uuid','/dev/nvme0n1','1'],text=True).strip().lower()=='3f9e8859-9832-44c1-b881-62e8034abde8'
r={'schema':'sp7-signed-menu-firmware-entry-v1','complete':False,'old_order':[f'{n:04X}' for n in oldorder]}
q=subprocess.run(['efibootmgr','--create-only','--gpt','--disk','/dev/nvme0n1','--part','1','--label','Manjaro (Secure Boot)','--loader',r'\EFI\SP7Manjaro\shimx64.efi'],capture_output=True,text=True)
r.update(create_exit=q.returncode,create_stdout=q.stdout,create_stderr=q.stderr)
P('/run/sp7-firmware-create-result.json').write_text(json.dumps(r));assert q.returncode==0,q.stderr
now=variables();assert all(now.get(k)==v for k,v in D['variables'].items()),'Existing boot variable changed during create-only'
new=set(now)-set(D['variables']);assert len(new)==1,new;name=new.pop();assert re.fullmatch(r'Boot[0-9A-Fa-f]{4}-'+guid,name)
num=int(name[4:8],16);raw=base64.b64decode(now[name]);attrs,pathlen=struct.unpack_from('<IH',raw,4);assert attrs&1
pos=10
while raw[pos:pos+2]!=b'\0\0':pos+=2;assert pos<len(raw)
desc=raw[10:pos].decode('utf-16-le');assert desc=='Manjaro (Secure Boot)';dp=raw[pos+2:pos+2+pathlen];nodes=[];i=0
while i<len(dp):
 t,st,l=struct.unpack_from('<BBH',dp,i);assert l>=4 and i+l<=len(dp);nodes.append((t,st,dp[i+4:i+l]));i+=l
hd=[n[2] for n in nodes if n[:2]==(4,1)];paths=[n[2] for n in nodes if n[:2]==(4,4)];assert len(hd)==len(paths)==1
part,start,size,sig,fmt,stype=struct.unpack('<IQQ16sBB',hd[0]);assert (part,start,size,uuid.UUID(bytes_le=sig),fmt,stype)==(1,2048,532480,uuid.UUID('3f9e8859-9832-44c1-b881-62e8034abde8'),2,2)
path=paths[0].decode('utf-16-le').rstrip('\0');assert path.lower()==r'\EFI\SP7Manjaro\shimx64.efi'.lower(),path
neworder=[num,*oldorder];r.update(new_entry=f'{num:04X}',new_entry_verified={'label':desc,'loader':path,'efi_partition_guid':str(uuid.UUID(bytes_le=sig))},new_order=[f'{n:04X}' for n in neworder])
P('/run/sp7-firmware-create-result.json').write_text(json.dumps(r))
q=subprocess.run(['efibootmgr','--bootorder',','.join(r['new_order'])],capture_output=True,text=True);r.update(order_exit=q.returncode,order_stderr=q.stderr)
if q.returncode!=0:
 restore=subprocess.run(['efibootmgr','--bootorder',','.join(r['old_order'])],capture_output=True,text=True);r['restore_old_order_exit']=restore.returncode
else:
 after=variables();assert bootnums(after[ordername])==neworder;assert all(after.get(k)==v for k,v in now.items() if k!=ordername)
 r.update(complete=True,existing_boot_entries_byte_identical=True,after_variables=after,after_text=subprocess.check_output(['efibootmgr','-v'],text=True))
P('/run/sp7-firmware-create-result.json').write_text(json.dumps(r));print(json.dumps(r));raise SystemExit(0 if r['complete'] else 1)
'''.replace('BEFORE',repr(before))
assert not (w/'physical-firmware-entry.json').exists(),'Existing result: inspect rather than rerun'
r=run_python(source,timeout=90);out={'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};(w/'physical-firmware-entry.json').write_text(json.dumps(out,indent=2)+'\n');assert r.returncode==0,r.stderr
j=json.loads(r.stdout);b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019');(b/'firmware-entry-result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in j.items() if k not in ['create_stdout','after_text','after_variables']},indent=2))
