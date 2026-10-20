# INACTIVE CANDIDATE. Never invoked automatically. No Linux restore or firmware writes.
param([switch]$Apply,[string]$ApprovedPlanSha256,[string]$ValidatedBackupReceiptSha256)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$expectedPlan='PLAN_BINDING_NOT_FINAL'
$expectedReceipt='BACKUP_VALIDATION_NOT_FINAL'
if($env:COMPUTERNAME -ne 'BOGEBEARSP7'){throw 'Wrong computer'}
$sys=Get-CimInstance Win32_ComputerSystem
if($sys.Manufacturer -ne 'Microsoft Corporation' -or $sys.Model -ne 'Surface Pro 7'){throw 'Wrong model'}
$d=Get-Disk -Number 0
if($d.FriendlyName -ne 'HFB1M8MO331C0MR' -or $d.Size -ne 256060514304 -or $d.PartitionStyle -ne 'GPT' -or $d.HealthStatus -ne 'Healthy' -or $d.OperationalStatus -ne 'Online'){throw 'Disk identity/health differs'}
$parts=@(Get-Partition -DiskNumber 0|Sort-Object PartitionNumber)
$expected=@(@(1,1048576,272629760),@(2,273678336,16777216),@(3,290455552,254651924480),@(4,254942380032,1117782016))
if($parts.Count -ne 4){throw 'Partition count differs; stop, do not repeat shrink'}
for($i=0;$i -lt 4;$i++){if($parts[$i].PartitionNumber -ne $expected[$i][0] -or $parts[$i].Offset -ne $expected[$i][1] -or $parts[$i].Size -ne $expected[$i][2]){throw 'Partition layout differs'}}
if($parts[2].DriveLetter -ne 'C'){throw 'C drive is not the expected partition'}
$target=137438953472L
$limits=Get-PartitionSupportedSize -DriveLetter C
if($limits.SizeMin -gt $target -or $limits.SizeMax -lt $target){throw '128 GiB is not currently supported'}
if(-not(Confirm-SecureBootUEFI)){throw 'Secure Boot unexpectedly disabled'}
if((Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') -or (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')){throw 'Pending Windows servicing reboot'}
$power=@(Get-CimInstance -Namespace root\WMI -ClassName BatteryStatus)
if($power.Count -eq 0 -or @($power|Where-Object {-not $_.PowerOnline}).Count){throw 'External power is not confirmed'}
$b=Get-BitLockerVolume -MountPoint 'C:'
if($b.LockStatus -ne 'Unlocked' -or $b.VolumeStatus -ne 'FullyEncrypted' -or $b.ProtectionStatus -ne 'On'){throw 'Unexpected BitLocker state'}
$before=@($parts|Select-Object PartitionNumber,Offset,Size,GptType,Guid)
if(-not $Apply){[pscustomobject]@{Mode='ReadOnlyCandidatePreflight';WritePerformed=$false;Before=$before;ProposedCBytes=$target;FreshSizeMin=$limits.SizeMin}|ConvertTo-Json -Depth 5;return}
if($expectedPlan -eq 'PLAN_BINDING_NOT_FINAL' -or $expectedReceipt -eq 'BACKUP_VALIDATION_NOT_FINAL'){throw 'Candidate is not released for physical writes'}
if($ApprovedPlanSha256 -ne $expectedPlan -or $ValidatedBackupReceiptSha256 -ne $expectedReceipt){throw 'Plan/validated-backup binding differs'}
$paused=$false;$resized=$false
try {
 Suspend-BitLocker -MountPoint 'C:' -RebootCount 1|Out-Null
 $paused=$true
 if((Get-BitLockerVolume -MountPoint 'C:').ProtectionStatus -ne 'Off'){throw 'BitLocker protector pause not confirmed'}
 Resize-Partition -DriveLetter C -Size $target
 $resized=$true
 $after=@(Get-Partition -DiskNumber 0|Sort-Object PartitionNumber)
 if($after.Count -ne 4){throw 'Unexpected post-shrink partition count'}
 for($i=0;$i -lt 4;$i++){
  $size=if($i -eq 2){$target}else{$before[$i].Size}
  if($after[$i].Offset -ne $before[$i].Offset -or $after[$i].Size -ne $size -or $after[$i].Guid -ne $before[$i].Guid -or $after[$i].GptType -ne $before[$i].GptType){throw 'Unexpected post-shrink layout'}
 }
} finally {
 if($paused){Resume-BitLocker -MountPoint 'C:'|Out-Null;if((Get-BitLockerVolume -MountPoint 'C:').ProtectionStatus -ne 'On'){throw 'IMPORTANT: BitLocker protection did not resume; no reboot'}}
}
[pscustomobject]@{Schema='sp7-native-c-shrink-receipt-v1';Success=$resized;CBytes=(Get-Partition -DriveLetter C).Size;BitLockerProtectorsResumed=$true;LinuxPartitionCreated=$false;EFIChanged=$false;FirmwareChanged=$false;RebootPerformed=$false}|ConvertTo-Json -Compress
