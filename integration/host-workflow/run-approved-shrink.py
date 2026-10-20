from pathlib import Path
import subprocess,json,datetime,hashlib,sys
from windows_transport import command
w=Path(__file__).resolve().parent
review=json.loads((w/'PHYSICAL-REVIEW-READY.json').read_text())
approval=json.loads((w/'USER-DUALBOOT-APPROVAL.json').read_text())
assert approval['approved_plan_sha256']==review['plan_sha256']==hashlib.sha256((w/'EXACT-DISK-WRITE-PLAN.json').read_bytes()).hexdigest()
b=Path('/mnt/sp7-backup/BACKUP/SP7-Windows-before-dualboot-20261019/VALIDATION-COMPLETE.json')
assert hashlib.sha256(b.read_bytes()).hexdigest()==review['windows_backup_validation_receipt_sha256'] and json.loads(b.read_text())['complete']
source=(w/'Shrink-Windows-Only.approved-20261019.ps1').read_text()
apply='--apply' in sys.argv
if apply:
 assert (w/'native-shrink-fresh-preflight.json').exists()
 assert not (w/'native-shrink-apply-result.json').exists(),'Prior physical attempt exists; inspect it, never blindly retry'
args=' -Apply -ApprovedPlanSha256 '+review['plan_sha256']+' -ValidatedBackupReceiptSha256 '+review['windows_backup_validation_receipt_sha256'] if apply else ''
ps="$s=[Console]::In.ReadToEnd(); & ([scriptblock]::Create($s))"+args
record={'host_started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'apply':apply,'script_sha256':hashlib.sha256(source.encode()).hexdigest(),'plan_sha256':review['plan_sha256']}
name='native-shrink-apply-result.json' if apply else 'native-shrink-fresh-preflight.json'
if apply:(w/name).write_text(json.dumps(record,indent=2)+'\n')
r=subprocess.run(command(ps),input=source,text=True,capture_output=True,encoding='utf-8',errors='replace',timeout=1200 if apply else 180)
record.update(host_finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit=r.returncode,stdout=r.stdout,stderr=r.stderr)
(w/name).write_text(json.dumps(record,indent=2)+'\n');print(r.stdout,flush=True)
if r.returncode:print(r.stderr,flush=True)
assert r.returncode==0,'Native shrink operation did not complete cleanly; inspect saved status before any next change'
json.loads(r.stdout.lstrip('\ufeff').strip())
