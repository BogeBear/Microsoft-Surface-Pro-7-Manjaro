"""Windows VSS capture streamed over SSH. No backup image staged on SP7."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,time
from windows_transport import OPTIONS,TARGET,run
os.umask(0o077);w=Path(__file__).resolve().parent;dest=w/'windows-backup';dest.mkdir(mode=0o700,exist_ok=False)
exe=w/'portable-tools/wimlib-1.14.5/wimlib-imagex'
status={'schema':'windows-direct-host-backup-v1','complete':False,'phase':'preflight','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'backup_file_staged_on_sp7':False,'physical_partition_changed':False}
def save():
 (dest/'status.json').write_text(json.dumps(status,indent=2)+'\n')
def run_local(args,name,timeout=7200):
 with (dest/(name+'.log')).open('xb') as log:r=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log,timeout=timeout)
 if r.returncode:raise RuntimeError(name+' failed: '+str(r.returncode))
save()
try:
 r=run("$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$b='C:\\Users\\bjorn\\sp7-dualboot-20261019';if($env:COMPUTERNAME -ne 'BOGEBEARSP7' -or (Get-Disk -Number 0).Size -ne 256060514304){throw 'Target differs'};if(Test-Path (Join-Path $b 'windows-before-dualboot.wim')){throw 'Unexpected C-staged backup'};[pscustomobject]@{Computer=$env:COMPUTERNAME;Boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime;Disk=(Get-Disk -Number 0|Select-Object Number,Size,PartitionStyle,FriendlyName);Partitions=@(Get-Partition -DiskNumber 0|Select-Object PartitionNumber,Offset,Size,GptType);ShadowIDs=@(Get-CimInstance Win32_ShadowCopy|ForEach-Object {[string]$_.ID});CFree=(Get-Volume -DriveLetter C).SizeRemaining}|ConvertTo-Json -Depth 5 -Compress")
 if r.returncode:raise RuntimeError('Remote preflight failed')
 before=json.loads(r.stdout.lstrip('\ufeff'));(dest/'source-before.json').write_text(json.dumps(before,indent=2)+'\n')
 status['phase']='capture_stream_to_bogebear';save()
 remote=r'C:\Users\bjorn\sp7-dualboot-20261019\wimlib-imagex.exe capture C:\ - SP7-Windows-before-dualboot --snapshot --pipable --compress=XPRESS --threads=2 --strict-acls --config=C:\Users\bjorn\sp7-dualboot-20261019\capture-exclusions.ini'
 partial=dest/'windows-before-dualboot.pwim'
 with partial.open('xb') as output,(dest/'capture-stream.log').open('xb') as log:
  result=subprocess.run(['ssh',*OPTIONS,'-T',TARGET,remote],stdin=subprocess.DEVNULL,stdout=output,stderr=log,timeout=7200)
 status['capture_ssh_rc']=result.returncode
 if result.returncode:raise RuntimeError('Capture stream interrupted; preserve output and check specific VSS cleanup')
 status['phase']='verify_pipable_on_host';save();run_local([str(exe),'verify',str(partial)],'verify-pipable')
 status['phase']='export_standard_wim_on_host';save()
 standard=dest/'windows-before-dualboot.wim'
 run_local([str(exe),'export',str(partial),'all',str(standard),'--check','--compress=XPRESS','--threads=4'],'export-standard')
 status['phase']='verify_standard_on_host';save();run_local([str(exe),'verify',str(standard)],'verify-standard')
 status['phase']='hash_standard';save()
 h=hashlib.file_digest(standard.open('rb'),'sha256').hexdigest()
 status['standard_wim']={'path':str(standard),'bytes':standard.stat().st_size,'sha256':h,'wimlib_verify_rc':0,'standard_nonpipable':standard.open('rb').read(8)==b'MSWIM\0\0\0'}
 assert status['standard_wim']['standard_nonpipable']
 r=run("$ProgressPreference='SilentlyContinue';[pscustomobject]@{ShadowIDs=@(Get-CimInstance Win32_ShadowCopy|ForEach-Object {[string]$_.ID});OurCaptureProcesses=@(Get-CimInstance Win32_Process -Filter \"Name='wimlib-imagex.exe'\"|Where-Object {$_.ExecutablePath -eq 'C:\\Users\\bjorn\\sp7-dualboot-20261019\\wimlib-imagex.exe'}|Select-Object ProcessId,CommandLine);CFree=(Get-Volume -DriveLetter C).SizeRemaining;CStagedBackupExists=(Test-Path 'C:\\Users\\bjorn\\sp7-dualboot-20261019\\windows-before-dualboot.wim')}|ConvertTo-Json -Depth 4 -Compress")
 if r.returncode:raise RuntimeError('Source cleanup verification unavailable')
 after=json.loads(r.stdout.lstrip('\ufeff'));(dest/'source-after.json').write_text(json.dumps(after,indent=2)+'\n')
 assert not after['OurCaptureProcesses'] and not after['CStagedBackupExists']
 assert set(after['ShadowIDs'])==set(before['ShadowIDs']),'VSS inventory changed; investigate'
 # Delete only the now redundant host pipable copy after standard WIM verification.
 partial.unlink();status.update(complete=True,phase='standard_wim_verified_on_bogebear',finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_snapshot_inventory_restored=True,pipable_intermediate_removed_locally=True,boot_restore_verified=False,disk_metadata_backup_pending=True);save();print(json.dumps(status,indent=2),flush=True)
except BaseException as e:
 status.update(phase='failed',error_type=type(e).__name__,error=str(e));save();raise
