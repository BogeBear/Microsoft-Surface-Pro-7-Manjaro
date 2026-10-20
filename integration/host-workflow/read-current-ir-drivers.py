from pathlib import Path
import datetime,json
from installed_transport import run_python
W=Path(__file__).resolve().parent
source=r'''import pathlib,subprocess,os,json,hashlib,stat
P=pathlib.Path;r={'boot_id':P('/proc/sys/kernel/random/boot_id').read_text().strip(),'kernel':os.uname().release}
def cmd(name,a):
 try:
  p=subprocess.run(a,text=True,capture_output=True,timeout=25);r[name]={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 except Exception as e:r[name]={'error':type(e).__name__+': '+str(e)}
def file(p):
 try:
  s=p.lstat();d={'uid':s.st_uid,'gid':s.st_gid,'mode':oct(stat.S_IMODE(s.st_mode)),'symlink':p.is_symlink()}
  if p.is_symlink():d['target']=os.readlink(p)
  elif p.is_file():d.update(size=s.st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
  return d
 except Exception as e:return {'error':type(e).__name__}
cp=P('/srv/sp7-project/target/work/resume-state.json');j=json.loads(cp.read_text())
r['checkpoint']={'sha256':hashlib.sha256(cp.read_bytes()).hexdigest(),**{k:j.get(k) for k in ['active','phase','hardware_tests_blocked_until_recovery','reviewed_presence_plan']}}
assert not j['active'] and j['hardware_tests_blocked_until_recovery']
cmd('secureboot',['mokutil','--sb-state'])
cmd('kernel_packages',['pacman','-Q'])
if 'stdout' in r['kernel_packages']:r['kernel_packages']['stdout']='\n'.join(s for s in r['kernel_packages']['stdout'].splitlines() if any(x in s.lower() for x in ['surface','libcamera','v4l','linux-firmware','ipu','linux72','linux619']))
cmd('system_camera_service',['systemctl','show','sp7-camera-prepare.service','-p','ActiveState','-p','UnitFileState'])
env=os.environ.copy();env['XDG_RUNTIME_DIR']='/run/user/1000';env['DBUS_SESSION_BUS_ADDRESS']='unix:path=/run/user/1000/bus'
p=subprocess.run(['systemctl','--user','show','sp7-camera-auto.service','-p','ActiveState','-p','UnitFileState'],env=env,text=True,capture_output=True,timeout=15);r['user_camera_service']={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
r['loaded_modules']={};r['selected_modules']={}
for name in ['intel_ipu4','intel_ipu4_isys','intel_ipu4p','intel_ipu4p_isys','intel_ipu4p_psys','ov7251','ov5693','ov8865','leds_tps68470','intel_skl_int3472_discrete','intel_skl_int3472_tps68470']:
 p=P('/sys/module')/name
 if p.exists():
  d={}
  for n in ['srcversion','version','taint','refcnt']:
   try:d[n]=(p/n).read_text().strip()
   except Exception as e:d[n]={'error':type(e).__name__}
  d['parameters']={}
  if (p/'parameters').is_dir():
   for x in (p/'parameters').iterdir():
    try:d['parameters'][x.name]=x.read_text().strip()
    except Exception as e:d['parameters'][x.name]={'error':type(e).__name__}
  r['loaded_modules'][name]=d
 q=subprocess.run(['modinfo',name],text=True,capture_output=True,timeout=10)
 if q.returncode==0:
  fields={}
  for line in q.stdout.splitlines():
   if ':' in line:
    k,v=line.split(':',1)
    if k in ['filename','vermagic','srcversion','signer','depends']:fields[k]=v.strip()
  if 'filename' in fields:fields['file']=file(P(fields['filename']))
  r['selected_modules'][name]=fields
r['helpers']={}
for folder in ['sp7-ir-project','sp7-ir-idle','sp7-ir-strobe','sp7-ir-session','sp7-ir-remove']:
 p=P('/usr/local/libexec')/folder
 if p.exists():
  r['helpers'][str(p)]=file(p)
  try:
   for x in p.iterdir():r['helpers'][str(x)]=file(x)
  except Exception as e:r['helpers'][str(p)]['list_error']=type(e).__name__
r['media_inventory']={}
for cl in ['video4linux','media']:
 p=P('/sys/class')/cl
 if p.is_dir():
  for x in p.iterdir():
   r['media_inventory'][str(x)]={'path':str(x.resolve()),'name':(x/'name').read_text().strip() if (x/'name').exists() else None}
r['runtime_devices']={}
for x in P('/sys/bus/pci/devices').iterdir():
 try:
  cls=(x/'class').read_text().strip()
  if cls in ['0x048000','0x040000','0x038000']:
   r['runtime_devices'][str(x)]={n:(x/n).read_text().strip() for n in ['vendor','device','class','power/runtime_status'] if (x/n).exists()}
 except OSError:pass
for bus in ['i2c','platform']:
 for x in (P('/sys/bus')/bus/'devices').iterdir():
  if any(s in x.name.lower() for s in ['ov7251','ov5693','ov8865','int347','tps68470','int33be','int347e','int347a']):
   r['runtime_devices'][str(x)]={n:(x/n).read_text().strip() for n in ['name','power/runtime_status'] if (x/n).exists()}
r['temperatures']={}
for h in P('/sys/class/hwmon').glob('hwmon*'):
 try:
  if (h/'name').read_text().strip()=='coretemp':
   for p in h.glob('temp*_label'):r['temperatures'][p.read_text().strip()]=int(p.with_name(p.name.replace('_label','_input')).read_text())/1000
 except OSError:pass
cmd('kernel_camera_messages',['journalctl','-k','-b','--no-pager','-o','cat'])
if 'stdout' in r['kernel_camera_messages']:r['kernel_camera_messages']['stdout']='\n'.join(s for s in r['kernel_camera_messages']['stdout'].splitlines() if any(x in s.lower() for x in ['ipu','ov7251','ov5693','ov8865','tps68470','int347','module verification']))[-15000:]
print(json.dumps(r))
'''
r=run_python(source,timeout=120)
out={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
(W/'ir-drivers-current-audit.json').write_text(json.dumps(out,indent=2)+'\n')
assert r.returncode==0,(r.stdout,r.stderr)
j=json.loads(r.stdout)
(W/'ir-drivers-current-details.json').write_text(json.dumps(j,indent=2)+'\n')
print(json.dumps(j,indent=2))
