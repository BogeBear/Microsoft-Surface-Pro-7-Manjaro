from pathlib import Path
import datetime,json
from live_transport import run_python
w=Path(__file__).resolve().parent
source=r'''import pathlib,subprocess,json,time,math
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='bde5de33-e0b3-4db1-82db-142ccee99c18'
assert P('/sys/class/dmi/id/product_name').read_text().strip()=='Surface Pro 7'
assert subprocess.check_output(['findmnt','-n','-o','FSTYPE','/'],text=True).strip()=='overlay'
ls=json.loads(subprocess.check_output(['lsblk','-J','-b','--tree','-o','PATH,SIZE,MODEL,SERIAL,TYPE,MOUNTPOINTS']))
disk=next(d for d in ls['blockdevices'] if d['path']=='/dev/nvme0n1')
assert disk['model']=='HFB1M8MO331C0MR' and disk['serial']=='SAKKF63QB2306A013S38' and disk['size']==256060514304
assert len(disk['children'])==4 and all(not any(p['mountpoints']) for p in disk['children'])
assert P('/sys/class/power_supply/ADP1/online').read_text().strip()=='1'
boot=subprocess.check_output(['efibootmgr','-v'],text=True)
assert 'BootOrder: 0005,0001,0004,0000,0002' in boot
assert 'Boot0005* Windows Boot Manager' in boot and '3f9e8859-9832-44c1-b881-62e8034abde8' in boot
for i in range(4):
 data=json.loads(subprocess.check_output(['sensors','-j'],text=True));cpu=data['coretemp-isa-0000']
 vals={label:next(float(v) for k,v in cpu[label].items() if k.endswith('_input')) for label in ['Package id 0','Core 0','Core 1','Core 2','Core 3']}
 safe=all(math.isfinite(v) and -20<=v<60 for v in vals.values())
 print(json.dumps({'sample':i+1,'final':i==3,'monotonic':time.monotonic(),'celsius':vals,'below60':safe}),flush=True)
 assert safe,'Hot/unknown CPU: reboot blocked; cool down, next check in five minutes'
 if i<3:time.sleep(2.3)
assert P('/sys/class/power_supply/ADP1/online').read_text().strip()=='1'
print('SP7_FINAL_REBOOT_GUARD_PASS_REBOOT_TO_EXISTING_WINDOWS_REQUEST',flush=True)
p=subprocess.run(['systemctl','reboot'],capture_output=True,text=True)
print(json.dumps({'reboot_request_exit':p.returncode,'stderr':p.stderr,'internal_partitions_changed':False}),flush=True)
assert p.returncode==0
'''
r=run_python(source,timeout=40);(w/'live-connection/reboot-to-windows.json').write_text(json.dumps({'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stdout':r.stdout,'stderr':r.stderr,'exit':r.returncode,'boot_observation_still_pending':True},indent=2)+'\n');print(r.stdout,flush=True)
if r.returncode:print(r.stderr,flush=True)
assert 'SP7_FINAL_REBOOT_GUARD_PASS_REBOOT_TO_EXISTING_WINDOWS_REQUEST' in r.stdout
