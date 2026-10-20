from pathlib import Path
import json,shutil,base64,subprocess
w=Path(__file__).resolve().parent;base=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/partition5-transaction-vm')
new=base/'synthetic-windows-mbr.raw'
assert not (base/'launch-mbr.json').exists()
if new.exists():new.unlink() # Own interrupted scratch copy only; source remains untouched.
subprocess.run(['cp','--reflink=auto','--sparse=always',str(base/'synthetic-empty-gpt.raw'),str(new)],check=True)
assert new.stat().st_size==256060514304 and new.stat().st_blocks*512<10*1024**2
code=base64.b64encode((w/'gpt_partition5.py').read_bytes()).decode()
test='''import types,base64,hashlib,os,subprocess
m=types.ModuleType('g');exec(base64.b64decode('CODE'),m.__dict__)
p='/dev/vda';t=m.read_table(p);original=bytearray(t['primary'][:512]);original[451:454]=bytes([254,127,153]);original[458:462]=bytes([255]*4)
with open(p,'r+b',buffering=0) as f:f.write(original);os.fsync(f.fileno())
q=subprocess.run(['sfdisk','--part-label',p,'5','Manjaro'],capture_output=True,text=True);assert q.returncode==0,q.stderr
b=m.read_table(p);assert b['primary'][:512]!=bytes(original)
h=lambda x:hashlib.sha256(x).hexdigest()
for label,orig,sha in [('wrong_hash',bytes(original),'0'*64),('unexpected_source_change',bytes(original[:10]+b'X'+original[11:]),h(b['primary']))]:
 try:m.preserve_windows_protective_mbr(p,orig,sha,h(b['secondary']))
 except RuntimeError:assert m.read_table(p)['primary']==b['primary'];print('PASS:'+label,flush=True)
 else:raise AssertionError(label)
r=m.preserve_windows_protective_mbr(p,bytes(original),h(b['primary']),h(b['secondary']))
a=m.read_table(p);assert a['primary'][:512]==bytes(original) and a['primary'][512:]==b['primary'][512:] and a['secondary']==b['secondary']
print('SP7_WINDOWS_MBR_PRESERVATION_ALL_PASS',flush=True)
'''.replace('CODE',code)
(w/'partition5-mbr-guest-test.sh').write_text("#!/bin/bash\nset -euo pipefail\nexec >/dev/ttyS0 2>&1\ntrap 'echo SP7_PARTITION5_TEST_DONE; sync; poweroff -f' EXIT\npython3 - <<'PYTEST'\n"+test+"\nPYTEST\n")
a=json.loads((base/'launch.json').read_text());a=[v.replace('synthetic-empty-gpt.raw','synthetic-windows-mbr.raw').replace('OVMF_VARS.fd','OVMF_VARS_mbr.fd').replace('/tmp/sp7-partition5-vm.sock','/tmp/sp7-mbr-test.sock') for v in a];shutil.copyfile(base/'OVMF_VARS.fd',base/'OVMF_VARS_mbr.fd');(base/'launch-mbr.json').write_text(json.dumps(a,indent=2)+'\n')
r=(w/'test-partition5-vm.py').read_text().replace("s/'launch.json'","s/'launch-mbr.json'").replace('/tmp/sp7-partition5-vm.sock','/tmp/sp7-mbr-test.sock').replace('partition5-guest-test.sh','partition5-mbr-guest-test.sh').replace('serial-attempt2.log','serial-mbr.log').replace('qemu-attempt2.log','qemu-mbr.log').replace('SP7_PARTITION5_VM_ALL_PASS','SP7_WINDOWS_MBR_PRESERVATION_ALL_PASS').replace('secureboot-live-candidate/partition5-vm-receipt.json','secureboot-live-candidate/protective-mbr-vm-receipt.json');(w/'test-protective-mbr-vm.py').write_text(r)
print('Sparse synthetic fixture prepared:',new.stat().st_blocks*512,'allocated bytes',flush=True)
