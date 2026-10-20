$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
if($env:COMPUTERNAME -ne 'BOGEBEARSP7'){throw 'Unexpected target computer'}
$result=[ordered]@{Schema='sp7-dualboot-readonly-preflight-v1';CollectedAt=(Get-Date).ToString('o');Computer=$env:COMPUTERNAME;ReadOnly=$true;Sections=[ordered]@{}}
function Read-Section($name,[scriptblock]$action){try{$result.Sections[$name]=@{ReadSucceeded=$true;Data=@(& $action)}}catch{$result.Sections[$name]=@{ReadSucceeded=$false;ErrorType=$_.Exception.GetType().Name;Error=$_.Exception.Message}}}
Read-Section 'System' {Get-CimInstance Win32_ComputerSystem|Select-Object Manufacturer,Model,TotalPhysicalMemory;Get-CimInstance Win32_OperatingSystem|Select-Object Caption,Version,BuildNumber,LastBootUpTime}
Read-Section 'Administrator' {([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)}
Read-Section 'Disks' {Get-Disk|Select-Object Number,FriendlyName,Size,PartitionStyle,HealthStatus,OperationalStatus,IsBoot,IsSystem}
Read-Section 'Partitions' {Get-Partition|Select-Object DiskNumber,PartitionNumber,DriveLetter,Type,GptType,Offset,Size,IsBoot,IsSystem}
Read-Section 'Volumes' {Get-Volume|Select-Object DriveLetter,FileSystemLabel,FileSystem,Size,SizeRemaining,HealthStatus,OperationalStatus}
Read-Section 'SupportedWindowsSize' {Get-PartitionSupportedSize -DriveLetter C|Select-Object SizeMin,SizeMax}
Read-Section 'BitLockerStatusOnly' {Get-BitLockerVolume|Select-Object MountPoint,VolumeStatus,ProtectionStatus,EncryptionMethod,LockStatus,EncryptionPercentage}
Read-Section 'SecureBoot' {Confirm-SecureBootUEFI}
Read-Section 'FirmwareEntries' {& bcdedit.exe /enum firmware;[pscustomobject]@{ExitCode=$LASTEXITCODE}}
Read-Section 'RecoveryEnvironment' {& reagentc.exe /info;[pscustomobject]@{ExitCode=$LASTEXITCODE}}
Read-Section 'WindowsFilesystemDirty' {& fsutil.exe dirty query C:;[pscustomobject]@{ExitCode=$LASTEXITCODE}}
Read-Section 'PowerAndPendingReboot' {[pscustomobject]@{HiberbootEnabled=(Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -ErrorAction SilentlyContinue).HiberbootEnabled;RebootPendingCBS=(Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending');RebootPendingWU=(Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')};Get-CimInstance Win32_Battery|Select-Object BatteryStatus,EstimatedChargeRemaining}
$result|ConvertTo-Json -Depth 9 -Compress
