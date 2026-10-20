from pathlib import Path
import json,datetime
from installed_transport import run_python
w=Path(__file__).resolve().parent
source=r'''import pathlib,subprocess,json,os
P=pathlib.Path;r={'boot_id':P('/proc/sys/kernel/random/boot_id').read_text().strip()}
cp=P('/srv/sp7-project/target/work/resume-state.json');j=json.loads(cp.read_text());r['checkpoint']={'active':j.get('active'),'phase':j.get('phase')}
def cmd(n,a,limit=30):
 try:q=subprocess.run(a,capture_output=True,text=True,timeout=limit);r[n]={'exit':q.returncode,'stdout':q.stdout,'stderr':q.stderr}
 except Exception as e:r[n]={'error':str(e)}
cmd('network',['nmcli','-t','-f','DEVICE,TYPE,STATE','device','status'])
cmd('sessions',['loginctl','list-sessions','--no-legend'])
cmd('sddm',['systemctl','show','sddm','-p','ActiveState','-p','SubState'])
cmd('package_versions',['pacman','-Q','plasma-nm','kirigami','qt6-base','qt6-declarative','plasma-workspace','plasma-desktop','qqc2-desktop-style','breeze'])
cmd('kirigami_integrity',['pacman','-Qkk','kirigami'])
cmd('plasma_journal',['journalctl','--user','-b','--no-pager','-n','1000','-o','cat'])
if 'stdout' in r['plasma_journal']:r['plasma_journal']['stdout']='\n'.join(line for line in r['plasma_journal']['stdout'].splitlines() if any(s in line.lower() for s in ['qml','kirigami','networkmanagement','cannot load','undefined symbol','not found','typeerror','referenceerror']))[-25000:]
r['qml_files']={}
for p in P('/usr/lib/qt6/qml/org/kde/kirigami').rglob('*'):
 if p.name in ['InlineMessage.qml','qmldir']:
  r['qml_files'][str(p)]=p.read_text()[:9000]
r['kirigami_shared_libraries']=[str(p) for p in P('/usr/lib/qt6/qml/org/kde/kirigami').rglob('*.so')]
for i,p in enumerate(r['kirigami_shared_libraries']):cmd('ldd_'+str(i),['ldd',p])
print(json.dumps(r))
'''
r=run_python(source,timeout=140);o={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(w/'plasma-network-readonly-diagnosis.json').write_text(json.dumps(o,indent=2)+'\n');assert r.returncode==0,r.stderr;j=json.loads(r.stdout)
print(json.dumps({k:v for k,v in j.items() if k!='qml_files'},indent=2))
for p,t in j['qml_files'].items():
 if p.endswith('InlineMessage.qml'):print(p);print('\n'.join(t.splitlines()[:65]))
