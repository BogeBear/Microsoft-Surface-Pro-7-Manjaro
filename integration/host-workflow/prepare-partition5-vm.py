from pathlib import Path
import subprocess,json,shutil,base64
w=Path(__file__).resolve().parent
s=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/partition5-transaction-vm');s.mkdir(mode=0o700)
fixture=s/'synthetic-empty-gpt.raw'
with fixture.open('xb') as f:f.truncate(256060514304)
script='label: gpt\nunit: sectors\n\n'
for start,size,typ,name in [(2048,532480,'C12A7328-F81F-11D2-BA4B-00A0C93EC93B','SYNTHETIC EFI'),(534528,32768,'E3C9E316-0B5C-4DB8-817D-F92DF00215AE','SYNTHETIC MSR'),(567296,268435456,'EBD0A0A2-B9E5-4433-87C0-68B6B72699C7','SYNTHETIC WINDOWS EMPTY'),(497934336,2183168,'DE94BBA4-06D1-4D40-A16A-BFD50179D6AC','SYNTHETIC RECOVERY EMPTY')]:
 script+=f'start={start},size={size},type={typ},name="{name}"'+(',attrs="RequiredPartition GUID:63"' if 'RECOVERY' in name else '')+'\n'
r=subprocess.run(['sfdisk','--no-reread',str(fixture)],input=script,capture_output=True,text=True,check=True);(s/'fixture-build.log').write_text(r.stdout+r.stderr)
old=s.parent/'wifi-overlay-v2-vm';a=json.loads((old/'launch.json').read_text());shutil.copyfile(old/'OVMF_VARS.fd',s/'OVMF_VARS.fd')
for i,v in enumerate(a):
 if v.startswith('if=pflash,format=raw,file='):a[i]='if=pflash,format=raw,file='+str(s/'OVMF_VARS.fd')
 if v=='-qmp':a[i+1]='unix:/tmp/sp7-partition5-vm.sock,server=on,wait=off'
a.extend(['-drive','if=none,id=emptyFixture,format=raw,file='+str(fixture),'-device','virtio-blk-pci,drive=emptyFixture,serial=SYNTHETIC_SP7_GPT_ONLY'])
(s/'launch.json').write_text(json.dumps(a,indent=2)+'\n')
source=base64.b64encode((w/'gpt_partition5.py').read_bytes()).decode()
tests='''import types,base64,hashlib,subprocess,json
m=types.ModuleType('gpt_partition5');exec(base64.b64decode('SOURCE'),m.__dict__)
p='/dev/vda';b=m.read_table(p);m.validate_existing(b)
h=lambda key:hashlib.sha256(b[key]).hexdigest()
def unchanged():
 c=m.read_table(p);assert c['primary']==b['primary'] and c['secondary']==b['secondary']
def refusal(fn,label):
 try:fn()
 except RuntimeError:unchanged();print('PASS:'+label,flush=True)
 else:raise AssertionError('Guard accepted '+label)
refusal(lambda:m.append(p,'0'*64,h('secondary')),'wrong_hash')
refusal(lambda:m.append('/dev/nvme0n1',h('primary'),h('secondary')),'wrong_disk_size')
old=m.START;m.START+=1
refusal(lambda:m.append(p,h('primary'),h('secondary')),'not_exact_free_gap');m.START=old
refusal(lambda:m.append(p,h('primary'),h('secondary'),runner=lambda *a,**k:subprocess.CompletedProcess(a,9,'','injected tool refusal')),'tool_failure_without_mutation')
r=m.append(p,h('primary'),h('secondary'));print('PASS:exact_append_preserves_windows_mbr_and_old_entries',flush=True)
try:m.append(p,h('primary'),h('secondary'))
except RuntimeError:print('PASS:no_blind_second_append',flush=True)
else:raise AssertionError('Second append unexpectedly accepted')
assert m.read_table(p)['entries'][4][:16]!=bytes(16)
print('SP7_PARTITION5_VM_ALL_PASS',flush=True)
print(json.dumps(r),flush=True)
'''.replace('SOURCE',source)
guest="#!/bin/bash\nset -euo pipefail\nexec >/dev/ttyS0 2>&1\ntrap 'echo SP7_PARTITION5_TEST_DONE; sync; poweroff -f' EXIT\npython3 - <<'PYTEST'\n"+tests+"\nPYTEST\n"
(w/'partition5-guest-test.sh').write_text(guest)
runner=(w/'test-wifi-live-vm-v2.py').read_text();start=runner.index(";s=Path(");end=runner.index("\na=json.loads",start);runner=runner[:start]+";s=Path('"+str(s)+"')"+runner[end:]
runner=runner.replace('/tmp/sp7-wifi-v2-vm.sock','/tmp/sp7-partition5-vm.sock').replace('test-wifi-live-guest-v2.sh','partition5-guest-test.sh').replace("command=\"stty -echo; printf '%s' '\"+b+\"' | base64 -d | sudo bash\\n\"","command='stty -echo\\n'+''.join(\"printf '%s' '\"+b[i:i+1000]+\"' >>/run/partition5-test.b64\\n\" for i in range(0,len(b),1000))+\"base64 -d /run/partition5-test.b64 | sudo bash\\n\"")
runner=runner.replace("b'SP7_WIFI_TEST_FINISHED'","b'SP7_PARTITION5_TEST_DONE'");a=runner.index('passed=all(');b=runner.index('\nr=',a);runner=runner[:a]+"passed=b'SP7_PARTITION5_VM_ALL_PASS' in seen"+runner[b:]
runner=runner.replace("'schema':'sp7-live-wifi-overlay-and-ssh-v1'","'schema':'sp7-partition5-transaction-vm-v1'").replace('secureboot-live-candidate/wifi-overlay-vm-receipt.json','secureboot-live-candidate/partition5-vm-receipt.json').replace("'test_server_loopback_only_started_and_stopped':True","'synthetic_empty_gpt_only_no_user_data':True")
(w/'test-partition5-vm.py').write_text(runner);compile(runner,'test-partition5-vm.py','exec');print('Synthetic-only GPT fixture and isolated VM test prepared.')
