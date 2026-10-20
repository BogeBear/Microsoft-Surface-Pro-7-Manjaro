from pathlib import Path
import json,datetime,hashlib
from installed_transport import run_python
w=Path(__file__).resolve().parent;b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/plasma-widget-workaround');backup=json.loads((b/'before.json').read_text());assert hashlib.sha256((b/'plasma-org.kde.plasma.desktop-appletsrc.original').read_bytes()).hexdigest()==backup['sha256']
source=r'''import pathlib,subprocess,json,os,hashlib,time
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='b3921440-7264-458e-bd4a-8f27d20fa0c2'
cp=json.loads(P('/srv/sp7-project/target/work/resume-state.json').read_text());assert not cp['active'] and cp['hardware_tests_blocked_until_recovery']
p=P('/home/sp7-user/.config/plasma-org.kde.plasma.desktop-appletsrc');assert hashlib.sha256(p.read_bytes()).hexdigest()=='EXPECTED'
e=os.environ.copy();e['DBUS_SESSION_BUS_ADDRESS']='unix:path=/run/user/1000/bus';e['XDG_RUNTIME_DIR']='/run/user/1000'
r={'schema':'sp7-user-only-plasma-systemmonitor-workaround-v1','no_root_or_system_package_change':True}
q=subprocess.run(['journalctl','--user','-b','-n','0','--show-cursor','--no-pager'],env=e,capture_output=True,text=True,check=True);cursor=q.stdout.split('-- cursor: ')[-1].strip();r['journal_cursor_before']=cursor
script="""var d=desktopById(26);if(!d){throw new Error('Expected desktop missing');}var expected={27:'org.kde.plasma.systemmonitor.memory',28:'org.kde.plasma.systemmonitor.net',33:'org.kde.plasma.systemmonitor'};var ids=[27,28,33];ids.forEach(function(id){var w=d.widgetById(id);if(!w||w.type!==expected[id]){throw new Error('Widget changed: '+id);}});ids.forEach(function(id){d.widgetById(id).remove();});print(JSON.stringify({removed:ids,desktop:26}));"""
q=subprocess.run(['qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.evaluateScript',script],env=e,capture_output=True,text=True,timeout=20);r['remove']={'exit':q.returncode,'stdout':q.stdout,'stderr':q.stderr};assert q.returncode==0,q.stderr;assert json.loads(q.stdout)['removed']==[27,28,33]
time.sleep(2)
q=subprocess.run(['systemctl','--user','restart','plasma-plasmashell.service'],env=e,capture_output=True,text=True,timeout=30);r['restart_plasmashell']={'exit':q.returncode,'stderr':q.stderr};assert q.returncode==0,q.stderr
time.sleep(4)
q=subprocess.run(['qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.evaluateScript','var x=[];desktops().forEach(function(d){d.widgets().forEach(function(w){x.push({desktop:d.id,id:w.id,type:w.type});});});print(JSON.stringify(x));'],env=e,capture_output=True,text=True,timeout=15);r['widgets_after']={'exit':q.returncode,'stdout':q.stdout,'stderr':q.stderr};assert q.returncode==0;assert not any('systemmonitor' in x['type'] for x in json.loads(q.stdout))
q=subprocess.run(['journalctl','--user','-b','--after-cursor',cursor,'--no-pager','-o','cat'],env=e,capture_output=True,text=True,timeout=15);r['new_qml_errors']=[line for line in q.stdout.splitlines() if any(s in line for s in ['error when loading applet','IconPropertiesGroup','Type Kirigami.InlineMessage unavailable'])];r['journal_read_exit']=q.returncode
q=subprocess.run(['nmcli','-t','-f','DEVICE,TYPE,STATE','device','status'],capture_output=True,text=True);r['network_after']=q.stdout
r['config_sha256_after']=hashlib.sha256(p.read_bytes()).hexdigest();r['desktop_alive']=subprocess.run(['systemctl','--user','is-active','plasma-plasmashell.service'],env=e,capture_output=True,text=True).stdout.strip();r['user_visual_confirmation_pending']=True;print(json.dumps(r))
'''.replace('EXPECTED',backup['sha256'])
assert not (w/'plasma-widget-workaround-result.json').exists()
r=run_python(source,timeout=95);j={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(w/'plasma-widget-workaround-result.json').write_text(json.dumps(j,indent=2)+'\n');(b/'workaround-result.json').write_text(json.dumps(j,indent=2)+'\n');assert r.returncode==0,r.stderr;print(r.stdout)
