"""One running backup job continuation, not a scheduler or autostart."""
import os,time,json,subprocess
from pathlib import Path
from windows_transport import run
os.umask(0o077);w=Path(__file__).resolve().parent;b=Path('/mnt/sp7-backup/BACKUP/SP7-Windows-before-dualboot-20261019');state=b/'image-attempt2/status.json';started=time.monotonic()
while True:
 x=json.loads(state.read_text())
 if x.get('complete') is True:break
 if x.get('phase')=='failed':raise SystemExit('Windows capture failed; no restore test or cleanup attempted')
 if time.monotonic()-started>7200:raise SystemExit('Backup not yet complete; no cleanup attempted')
 time.sleep(2)
print('Verified standard Windows backup ready; applying to private ordinary test file',flush=True)
r=subprocess.run(['/usr/bin/python',str(w/'verify-windows-restore-on-backup-disk.py')],stdin=subprocess.DEVNULL)
if r.returncode:raise SystemExit(r.returncode)
assert json.loads((b/'disk-metadata/receipt.json').read_text())['complete'] is True
src="$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$b='C:\\Users\\bjorn\\sp7-dualboot-20261019';if(@(Get-CimInstance Win32_Process -Filter \"Name='wimlib-imagex.exe'\"|Where-Object {$_.ExecutablePath -eq (Join-Path $b 'wimlib-imagex.exe')}).Count){throw 'Capture still running'};$files=@(Get-ChildItem -LiteralPath $b);if($files.Count -ne 3 -or @($files|Where-Object {$_.Name -notin @('wimlib-imagex.exe','libwim-15.dll','capture-exclusions.ini')}).Count){throw 'Unexpected staging files'};if((Get-FileHash -LiteralPath (Join-Path $b 'wimlib-imagex.exe')).Hash.ToLower() -ne '34c0c4165591ad1f592837ed99d08273c58d6ed3fe0ed6360cf34e7b0739b353' -or (Get-FileHash -LiteralPath (Join-Path $b 'libwim-15.dll')).Hash.ToLower() -ne 'ba853ee1e3fc5f5798581f02e8e066ba07a0a2375f0bf444fe981431fd508495'){throw 'Tool hashes differ'};foreach($n in @('wimlib-imagex.exe','libwim-15.dll','capture-exclusions.ini')){Remove-Item -LiteralPath (Join-Path $b $n)};Remove-Item -LiteralPath $b;[pscustomobject]@{TemporaryProjectStagingRemoved=(-not(Test-Path -LiteralPath $b));PhysicalPartitionsChanged=$false}|ConvertTo-Json -Compress"
r=run(src);(w/'sp7-temporary-backup-tools-cleanup.json').write_text(r.stdout);(w/'sp7-temporary-backup-tools-cleanup.stderr.txt').write_text(r.stderr);assert r.returncode==0,r.returncode
out={'schema':'sp7-windows-backup-validation-complete-v1','complete':True,'backup_base':str(b),'image_status':str(state),'ntfs_restore_test':str(b/'image-attempt2/restore-test.json'),'disk_metadata':str(b/'disk-metadata/receipt.json'),'sp7_cleanup':json.loads(r.stdout),'physical_windows_boot_restore_tested':False,'original_backup_and_windows_preserved':True,'timestamp_epoch':time.time()}
(b/'VALIDATION-COMPLETE.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2),flush=True)
