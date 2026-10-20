$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
if($env:COMPUTERNAME -ne 'BOGEBEARSP7'){throw 'Unexpected target'}
$admin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if(-not $admin){throw 'Administrator token required'}
$base=Join-Path $env:USERPROFILE 'sp7-dualboot-20261019'
$exe=Join-Path $base 'wimlib-imagex.exe'
$image=Join-Path $base 'windows-before-dualboot.wim'
$report=Join-Path $base 'backup-status.json'
if(Test-Path -LiteralPath $image){throw 'Refusing to overwrite previous image'}
if((Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash.ToLower() -ne '34c0c4165591ad1f592837ed99d08273c58d6ed3fe0ed6360cf34e7b0739b353'){throw 'Portable executable hash mismatch'}
if((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $base 'libwim-15.dll')).Hash.ToLower() -ne 'ba853ee1e3fc5f5798581f02e8e066ba07a0a2375f0bf444fe981431fd508495'){throw 'Portable library hash mismatch'}
$disk=Get-Disk -Number 0
if($disk.Size -ne 256060514304 -or $disk.PartitionStyle -ne 'GPT'){throw 'Disk changed'}
if((Get-Volume -DriveLetter C).SizeRemaining -lt 90GB){throw 'Insufficient staging space'}
$partitions=@(Get-Partition -DiskNumber 0|Select-Object PartitionNumber,Offset,Size,DriveLetter,GptType)
$result=[ordered]@{Schema='sp7-windows-pre-dualboot-backup-v1';Computer=$env:COMPUTERNAME;StartedAt=(Get-Date).ToString('o');DiskSize=$disk.Size;Partitions=$partitions;Phase='capture';Complete=$false;PhysicalPartitionsChanged=$false;SecretsPrinted=$false}
function Save-Status { $result|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $report -Encoding UTF8 }
Save-Status
$config=Join-Path $base 'capture-exclusions.ini'
@'
[ExclusionList]
\$ntfs.log
\hiberfil.sys
\pagefile.sys
\swapfile.sys
\System Volume Information
\RECYCLER
\$RECYCLE.BIN
\$Recycle.Bin
\Windows\CSC
\Users\bjorn\sp7-dualboot-20261019
'@|Set-Content -LiteralPath $config -Encoding ASCII
try {
 & $exe capture 'C:\' $image 'SP7 Windows before dualboot' --snapshot --compress=XPRESS --threads=1 --strict-acls --check ('--config='+$config) *> (Join-Path $base 'capture.log')
 $result.CaptureExit=$LASTEXITCODE
 if($LASTEXITCODE -ne 0){throw 'WIM capture failed; preserve partial output'}
 $result.Phase='verify';Save-Status
 & $exe verify $image *> (Join-Path $base 'verify.log')
 $result.VerifyExit=$LASTEXITCODE
 if($LASTEXITCODE -ne 0){throw 'WIM verification failed'}
 $result.Phase='disk-metadata';Save-Status
 function Save-Range([string]$name,[long]$offset,[long]$length){
  $target=Join-Path $base $name
  if(Test-Path -LiteralPath $target){throw 'Range destination already exists'}
  $source=[IO.File]::Open('\\.\PhysicalDrive0',[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
  try{
   $null=$source.Seek($offset,[IO.SeekOrigin]::Begin)
   $output=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
   try{$buffer=New-Object byte[] (1MB);$left=$length
    while($left -gt 0){$wanted=[int][Math]::Min($left,$buffer.Length);$n=$source.Read($buffer,0,$wanted);if($n -le 0){throw 'Short physical read'};$output.Write($buffer,0,$n);$left-=$n}
    $output.Flush($true)
   }finally{$output.Dispose()}
  }finally{$source.Dispose()}
 }
 Save-Range 'gpt-prefix.bin' 0 1048576
 Save-Range 'gpt-suffix.bin' ($disk.Size-33792) 33792
 foreach($number in @(1,2,4)){$p=$partitions|Where-Object {$_.PartitionNumber -eq $number};Save-Range ('partition-'+$number+'.raw') $p.Offset $p.Size}
 & bcdedit.exe /export (Join-Path $base 'BCD.export') *> (Join-Path $base 'BCD-export.log')
 $result.BcdExportExit=$LASTEXITCODE
 if($LASTEXITCODE -ne 0){throw 'BCD export failed'}
 $result.Phase='hashes';Save-Status
 $names=@('windows-before-dualboot.wim','gpt-prefix.bin','gpt-suffix.bin','partition-1.raw','partition-2.raw','partition-4.raw','BCD.export')
 $result.Files=@($names|ForEach-Object {$p=Join-Path $base $_;[pscustomobject]@{Name=$_;Bytes=(Get-Item -LiteralPath $p).Length;Sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLower()}})
 $result.Complete=$true;$result.Phase='captured_and_verified_on_source';$result.FinishedAt=(Get-Date).ToString('o');Save-Status
}catch{
 $result.Phase='failed';$result.ErrorType=$_.Exception.GetType().Name;Save-Status;throw
}
$result|ConvertTo-Json -Depth 6 -Compress
