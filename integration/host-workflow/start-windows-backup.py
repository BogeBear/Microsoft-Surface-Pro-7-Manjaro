import json,os,subprocess
from pathlib import Path
from windows_transport import run,command,OPTIONS,TARGET
os.umask(0o077);w=Path(__file__).resolve().parent
r=run("$ErrorActionPreference='Stop';if($env:COMPUTERNAME -ne 'BOGEBEARSP7'){throw 'Wrong computer'};$p=Join-Path $env:USERPROFILE 'sp7-dualboot-20261019';if(Test-Path (Join-Path $p 'backup-status.json')){throw 'Previous backup run exists'};New-Item -ItemType Directory -Path $p -Force|Out-Null;[Console]::Write($p)")
r.check_returncode();print('Remote staging directory',r.stdout.strip(),flush=True)
files=[w/'portable-tools/windows-wimlib'/name for name in ('wimlib-imagex.exe','libwim-15.dll')]+[w/'Backup-Windows.ps1']
subprocess.run(['scp',*OPTIONS,*map(str,files),TARGET+':C:/Users/bjorn/sp7-dualboot-20261019/'],check=True,capture_output=True)
source="$ProgressPreference='SilentlyContinue';& 'C:\\Users\\bjorn\\sp7-dualboot-20261019\\Backup-Windows.ps1'"
with (w/'backup-session.stdout.txt').open('xb') as out,(w/'backup-session.stderr.txt').open('xb') as err:
 p=subprocess.run(command(source),stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=5400)
print('Backup SSH exit',p.returncode,flush=True)
if p.returncode:raise SystemExit(p.returncode)
obj=json.loads((w/'backup-session.stdout.txt').read_text(encoding='utf-8-sig'));(w/'windows-backup-source-receipt.json').write_text(json.dumps(obj,indent=2)+'\n');print('Windows capture verified',obj['Complete'],flush=True)
