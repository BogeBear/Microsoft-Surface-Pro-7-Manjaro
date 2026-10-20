import os,json,subprocess,hashlib
from pathlib import Path
from windows_transport import OPTIONS,TARGET,run
os.umask(0o077);w=Path(__file__).resolve().parent;out=w/'stream-fixture';out.mkdir(exist_ok=False)
src="$ErrorActionPreference='Stop';$p='C:\\Users\\bjorn\\sp7-dualboot-20261019\\stream-fixture';if(Test-Path -LiteralPath $p){throw 'Fixture exists'};New-Item -ItemType Directory -Path $p|Out-Null;[IO.File]::WriteAllBytes((Join-Path $p 'payload.bin'),[byte[]](0..255));[Console]::Write('FixtureReady')"
r=run(src);assert r.returncode==0,(r.stdout,r.stderr[-500:])
exe=r'C:\Users\bjorn\sp7-dualboot-20261019\wimlib-imagex.exe'
command=exe+r' capture C:\Users\bjorn\sp7-dualboot-20261019\stream-fixture - SP7-stream-fixture --pipable --compress=XPRESS --threads=1 --strict-acls'
with (out/'fixture.pwim').open('xb') as dst,(out/'remote.log').open('xb') as log:
 r=subprocess.run(['ssh',*OPTIONS,'-T',TARGET,command],stdin=subprocess.DEVNULL,stdout=dst,stderr=log,timeout=180)
assert r.returncode==0,r.returncode
local=w/'portable-tools/wimlib-1.14.5/wimlib-imagex'
for args,name in [(['verify',str(out/'fixture.pwim')],'verify'),(['extract',str(out/'fixture.pwim'),'1','payload.bin','--dest-dir='+str(out/'output')],'extract')]:
 r=subprocess.run([str(local),*args],capture_output=True);(out/(name+'.log')).write_bytes(r.stdout+r.stderr);assert r.returncode==0,name
x=(out/'output/payload.bin').read_bytes();assert x==bytes(range(256))
r=run("$p='C:\\Users\\bjorn\\sp7-dualboot-20261019\\stream-fixture';Remove-Item -LiteralPath (Join-Path $p 'payload.bin') -ErrorAction Stop;Remove-Item -LiteralPath $p -ErrorAction Stop;[Console]::Write('FixtureRemoved')")
assert r.returncode==0
report={'schema':'windows-binary-ssh-stream-test-v1','all_256_byte_values_exact':True,'fixture_sha256':hashlib.sha256(x).hexdigest(),'wim_verify_rc':0,'remote_fixture_removed':True,'backup_image_stored_on_sp7':False,'stdout_binary_ssh_verified':True}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
