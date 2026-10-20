$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$rows=@()
foreach($n in @('Global\HWiNFO_SENS_SM2','HWiNFO_SENS_SM2')) {
 try {
  $m=[IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting($n,[IO.MemoryMappedFiles.MemoryMappedFileRights]::Read)
  try {$v=$m.CreateViewAccessor(0,0,[IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read);try{$b=New-Object byte[] 128;$read=$v.ReadArray(0,$b,0,$b.Length);$rows+=[pscustomobject]@{Name=$n;Opened=$true;Capacity=$v.Capacity;HeaderBase64=[Convert]::ToBase64String($b)}}finally{$v.Dispose()}}finally{$m.Dispose()}
 }catch{$rows+=[pscustomobject]@{Name=$n;Opened=$false;ErrorType=$_.Exception.GetType().Name;Detail=$_.Exception.GetBaseException().Message;NativeCode=$_.Exception.GetBaseException().HResult}}
}
[pscustomobject]@{Schema='sp7-hwinfo-named-public-sensor-header-v1';Computer=$env:COMPUTERNAME;Utc=(Get-Date).ToUniversalTime().ToString('o');Maps=$rows;ReadOnly=$true;ProcessMemoryRead=$false}|ConvertTo-Json -Depth 4 -Compress
