from pathlib import Path
import base64,json,subprocess
root=Path.cwd();work=root/'work/sp7-dualboot-20261019';source=(work/'Read-DualbootPreflight.ps1').read_text()
remote='powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(source.encode('utf-16le')).decode()
known=root/'work/sp7-windows-check-20261017/connection/known_hosts'
args=['ssh','-F','/dev/null','-i','/home/sp7-user/.ssh/sp7_windows_20261017','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'-o','ConnectTimeout=10','bjorn@192.0.2.10',remote]
r=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=100)
(work/'preflight.stdout.txt').write_text(r.stdout);(work/'preflight.stderr.txt').write_text(r.stderr)
if r.returncode:print('SSH failed',r.returncode,r.stderr[-1000:]);raise SystemExit(r.returncode)
data=json.loads(r.stdout.lstrip('\ufeff'));(work/'preflight.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(data,indent=2,ensure_ascii=False))
