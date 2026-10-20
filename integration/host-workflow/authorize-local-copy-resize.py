import hashlib,json,os,subprocess,time
from pathlib import Path
w=Path(__file__).resolve().parent
started=time.monotonic()
while not (w/'manjaro-copy-relocated.json').exists():
 if time.monotonic()-started>600:raise SystemExit('Local copy relocation not ready; no authorization attempted')
 time.sleep(1)
script=w/'Resize-Manjaro-Copy.py';sha=hashlib.sha256(script.read_bytes()).hexdigest()
(w/'local-copy-resize-authorization.json').write_text(json.dumps({'script':str(script),'sha256':sha,'authorization':'normal one-shot pkexec','target':'BACKUP/SP7-Manjaro-dualboot-working-copy-20261019/manjaro-working-copy.img','new_persistent_privileges':False},indent=2)+'\n')
code='import hashlib,pathlib; p=pathlib.Path('+repr(str(script))+'); b=p.read_bytes(); assert hashlib.sha256(b).hexdigest()=='+repr(sha)+'; exec(compile(b,str(p),"exec"))'
print('Opening normal development-host system authorization for the local COPY only',flush=True)
with (w/'local-copy-resize-system.log').open('xb') as log:
 r=subprocess.run(['pkexec','/usr/bin/python','-I','-S','-c',code],stdin=subprocess.DEVNULL,stdout=log,stderr=log,timeout=1800)
print('One-shot resize exit',r.returncode,flush=True)
if r.returncode:raise SystemExit(r.returncode)
image=Path('/mnt/sp7-backup/BACKUP/SP7-Manjaro-dualboot-working-copy-20261019/manjaro-working-copy.img')
with (w/'manjaro-resized-btrfs-check.log').open('xb') as log:
 r=subprocess.run(['btrfs','check','--readonly','--check-data-csum',str(image)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,timeout=1800)
(w/'manjaro-resized-btrfs-check.json').write_text(json.dumps({'target':str(image),'rc':r.returncode,'data_checksums':True,'physical_sp7_changed':False},indent=2)+'\n');print('Post-shrink Btrfs check exit',r.returncode,flush=True)
raise SystemExit(r.returncode)
