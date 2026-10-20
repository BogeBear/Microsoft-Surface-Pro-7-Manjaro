from pathlib import Path
import subprocess,base64,json,datetime
from windows_transport import OPTIONS,TARGET
w=Path(__file__).resolve().parent
ps=r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
if($env:COMPUTERNAME -ne 'BOGEBEARSP7'){throw 'Wrong computer'}
$o=Get-CimInstance Win32_OperatingSystem
$r=[ordered]@{Computer=$env:COMPUTERNAME;BootUTC=$o.LastBootUpTime.ToUniversalTime().ToString('o');Version=$o.Version;SecureBoot=(Confirm-SecureBootUEFI);ReadOnly=$true;NoCameraOrBiometricCapture=$true}
$d=Get-Disk -Number 0;$r.Disk=$d|Select-Object Number,FriendlyName,Size,Guid,HealthStatus,OperationalStatus
$r.Partitions=@(Get-Partition -DiskNumber 0|Select-Object PartitionNumber,DriveLetter,Offset,Size,Guid,GptType)
$r.CVolume=Get-Volume -DriveLetter C|Select-Object FileSystemType,HealthStatus,OperationalStatus,Size,SizeRemaining
$v=Get-BitLockerVolume -MountPoint C:;$r.BitLocker=[pscustomobject]@{ProtectionStatus=[string]$v.ProtectionStatus;VolumeStatus=[string]$v.VolumeStatus;EncryptionPercentage=$v.EncryptionPercentage;EncryptionMethod=[string]$v.EncryptionMethod;LockStatus=[string]$v.LockStatus}
$t=Get-Tpm;$r.TPM=$t|Select-Object TpmPresent,TpmReady,TpmEnabled,TpmActivated,TpmOwned,RestartPending
$r.Services=@(Get-Service sshd,WbioSrvc,Winmgmt|Select-Object Name,Status,StartType)
$r.PresentDevicesWithProblems=@(Get-PnpDevice -PresentOnly|Where-Object{$_.Status -ne 'OK'}|Select-Object Class,FriendlyName,Status,Problem)
$r.CameraBiometricNetworkDevices=@(Get-PnpDevice -PresentOnly|Where-Object{$_.Class -in @('Camera','Biometric','Net')}|Select-Object Class,FriendlyName,Status,Problem)
$r.PendingCBSReboot=Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$r.NTFSDirtyQuery=& fsutil dirty query C: 2>&1|Out-String;$r.NTFSDirtyQueryExit=$LASTEXITCODE
$r.BootManager=& bcdedit /enum '{bootmgr}' 2>&1|Out-String;$r.BootManagerReadExit=$LASTEXITCODE
$r.CurrentWindowsLoader=& bcdedit /enum '{current}' 2>&1|Out-String;$r.CurrentWindowsLoaderReadExit=$LASTEXITCODE
$r.Firmware=& bcdedit /enum firmware 2>&1|Out-String;$r.FirmwareReadExit=$LASTEXITCODE
$p=Get-Partition -DiskNumber 0 -PartitionNumber 1;$root=@($p.AccessPaths|Where-Object{$_ -like '\\?\Volume*'})[0];$b=[IO.File]::ReadAllBytes($root+'EFI\SP7Manjaro\grub.cfg');$a=[Security.Cryptography.SHA256]::Create();try{$r.ActiveGrubConfigSHA256=[BitConverter]::ToString($a.ComputeHash($b)).Replace('-','').ToLower()}finally{$a.Dispose()}
try{$events=@(Get-WinEvent -FilterHashtable @{LogName='System';StartTime=$o.LastBootUpTime;Level=1,2} -MaxEvents 80 -ErrorAction Stop);$r.SystemCriticalErrorsSinceBoot=[pscustomobject]@{Complete=$true;Events=@($events|Select-Object TimeCreated,ProviderName,Id,LevelDisplayName,RecordId)}}catch{if($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*'){$r.SystemCriticalErrorsSinceBoot=[pscustomobject]@{Complete=$true;Events=@()}}else{$r.SystemCriticalErrorsSinceBoot=[pscustomobject]@{Complete=$false;ErrorType=$_.Exception.GetType().Name;ErrorId=$_.FullyQualifiedErrorId}}}
$r|ConvertTo-Json -Depth 8 -Compress
'''
bootstrap="$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false);$source=[Console]::In.ReadToEnd();& ([ScriptBlock]::Create($source))"
remote='powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(bootstrap.encode('utf-16le')).decode()
r=subprocess.run(['ssh',*OPTIONS,TARGET,remote],input=ps,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=160)
out={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(w/'windows-after-grub-boot-audit.json').write_text(json.dumps(out,indent=2)+'\n');assert r.returncode==0,r.stderr
j=json.loads(r.stdout.lstrip('\ufeff'));(w/'windows-after-grub-boot-details.json').write_text(json.dumps(j,indent=2,ensure_ascii=False)+'\n');print(json.dumps(j,indent=2,ensure_ascii=False))
