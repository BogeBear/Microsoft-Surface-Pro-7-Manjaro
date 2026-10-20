from pathlib import Path
import datetime, hashlib, json, re
from installed_transport import run_python

W = Path(__file__).resolve().parent
B = Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/plasma-widgets-restored-20261019')
O = B.parent / 'plasma-widget-workaround'
original = (O / 'plasma-org.kde.plasma.desktop-appletsrc.original').read_text()
assert hashlib.sha256(original.encode()).hexdigest() == json.loads((O/'before.json').read_text())['sha256']
pre = json.loads((W/'widgets-restore-preflight.json').read_text())
B.mkdir(exist_ok=False)
receipt = {'host_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'boot': pre['boot'], 'root_changes': False}

common = '''import pathlib,os,json,hashlib,subprocess,time
P=pathlib.Path
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
cp=P('/srv/sp7-project/target/work/resume-state.json')
assert hashlib.sha256(cp.read_bytes()).hexdigest()==CHECKPOINT
p=P('/home/sp7-user/.config/plasma-org.kde.plasma.desktop-appletsrc')
e=os.environ.copy();e['DBUS_SESSION_BUS_ADDRESS']='unix:path=/run/user/1000/bus';e['XDG_RUNTIME_DIR']='/run/user/1000'
def cmd(a):
 r=subprocess.run(a,env=e,text=True,capture_output=True,timeout=30)
 return dict(exit=r.returncode,out=r.stdout,err=r.stderr)
'''.replace('BOOT', repr(pre['boot'])).replace('CHECKPOINT',repr(pre['checkpoint_sha']))

def remote(src):
    r=run_python(common+src,timeout=70)
    assert r.returncode==0,(r.stdout,r.stderr)
    return json.loads(r.stdout)

stopped = False
try:
    stopped = True
    before = remote('''q=cmd(['systemctl','--user','stop','plasma-plasmashell.service']);assert q['exit']==0,q
assert cmd(['systemctl','--user','is-active','plasma-plasmashell.service'])['out'].strip()=='inactive'
s=p.read_text();st=p.stat()
print(json.dumps(dict(layout=s,sha256=hashlib.sha256(s.encode()).hexdigest(),mode=st.st_mode&0o777,uid=st.st_uid,gid=st.st_gid,stop=q)))
''')
    stopped = True
    (B/'plasma-org.kde.plasma.desktop-appletsrc.before').write_text(before.pop('layout'))
    (B/'before.json').write_text(json.dumps(before,indent=2)+'\n')
    current = (B/'plasma-org.kde.plasma.desktop-appletsrc.before').read_text()
    def sections(s):
        return re.split(r'(?m)(?=^\[)',s)
    old_sections=sections(original)
    widget_sections=[s for s in old_sections if re.match(r'^\[Containments\]\[26\]\[Applets\]\[(27|28|33)\](?:\[|\n)',s)]
    assert len(widget_sections)==30,len(widget_sections)
    assert not any(re.match(r'^\[Containments\]\[26\]\[Applets\]\[(27|28|33)\]',s) for s in sections(current))
    # Restore only desktop geometry and the three removed applet trees.
    old_desktop=next(s for s in old_sections if s.startswith('[Containments][26]\n'))
    geometry={x.split('=',1)[0]:x for x in old_desktop.splitlines() if x.startswith('ItemGeometries')}
    out=[]
    for section in sections(current):
        if section.startswith('[Containments][26]\n'):
            lines=section.splitlines(keepends=True)
            assert set(geometry)<=set(x.split('=',1)[0] for x in lines)
            section=''.join(geometry[x.split('=',1)[0]]+'\n' if x.split('=',1)[0] in geometry else x for x in lines)
        out.append(section)
    merged=''.join(out).rstrip()+'\n\n'+''.join(widget_sections)
    (B/'plasma-org.kde.plasma.desktop-appletsrc.restored').write_text(merged)
    payload=json.dumps(merged)
    applied=remote('''assert cmd(['systemctl','--user','is-active','plasma-plasmashell.service'])['out'].strip()=='inactive'
assert hashlib.sha256(p.read_bytes()).hexdigest()==EXPECTED
st=p.stat();data=PAYLOAD.encode();tmp=p.with_name(p.name+'.restore-widgets.tmp')
fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,st.st_mode&0o777)
try:
 with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
finally:
 if tmp.exists():tmp.unlink()
assert hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256(data).hexdigest()
print(json.dumps(dict(sha256=hashlib.sha256(data).hexdigest(),mode=p.stat().st_mode&0o777)))
'''.replace('EXPECTED',repr(before['sha256'])).replace('PAYLOAD',payload))
    receipt['applied']=applied
finally:
    if stopped:
        receipt['start']=remote("q=cmd(['systemctl','--user','start','plasma-plasmashell.service']);print(json.dumps(q))\n")
        (W/'widgets-restore-result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        (B/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
