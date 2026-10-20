import os,json,subprocess
from pathlib import Path
from windows_transport import command,run
os.umask(0o077)
w=Path(__file__).resolve().parent
src=(w/'Backup-Windows.ps1').read_text()
r=run("$b=Join-Path $env:USERPROFILE 'sp7-dualboot-20261019'; [pscustomobject]@{StatusExists=(Test-Path (Join-Path $b 'backup-status.json'));ImageExists=(Test-Path (Join-Path $b 'windows-before-dualboot.wim'))}|ConvertTo-Json -Compress")
if r.returncode:raise SystemExit('Precheck SSH failed')
x=json.loads(r.stdout.lstrip('\ufeff').strip())
if x['StatusExists'] or x['ImageExists']:raise SystemExit('Existing backup state requires investigation')
with (w/'backup-session-v3.stdout.txt').open('xb') as out,(w/'backup-session-v3.stderr.txt').open('xb') as err:
 p=subprocess.run(command("& powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File 'C:\\Users\\bjorn\\sp7-dualboot-20261019\\Backup-Windows.ps1'"),stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=5400)
print('Backup SSH exit',p.returncode,flush=True)
if p.returncode==0:
 x=json.loads((w/'backup-session-v3.stdout.txt').read_text(encoding='utf-8-sig').strip());(w/'windows-backup-source-receipt.json').write_text(json.dumps(x,indent=2)+'\n')
raise SystemExit(p.returncode)
