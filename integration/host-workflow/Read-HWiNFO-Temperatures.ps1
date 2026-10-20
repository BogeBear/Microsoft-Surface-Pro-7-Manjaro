$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
function Zstr($b,$off,$length) { [Text.Encoding]::GetEncoding(1252).GetString($b,$off,$length).Split([char]0)[0] }
$m=$null;$v=$null;$mu=$null;$held=$false
try {
 $mu=[Threading.Mutex]::OpenExisting('Global\HWiNFO_SM2_MUTEX')
 $held=$mu.WaitOne(250)
 if(-not $held){throw 'HWiNFO sensor snapshot mutex timeout'}
 $m=[IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting('Global\HWiNFO_SENS_SM2',[IO.MemoryMappedFiles.MemoryMappedFileRights]::Read)
 $v=$m.CreateViewAccessor(0,0,[IO.MemoryMappedFiles.MemoryMappedFileAccess]::Read)
 $h=New-Object byte[] 48;[void]$v.ReadArray(0,$h,0,48)
 if([BitConverter]::ToUInt32($h,0) -ne 1399412552 -or [BitConverter]::ToUInt32($h,4) -ne 2 -or [BitConverter]::ToUInt32($h,8) -ne 1){throw 'Unknown/inactive HWiNFO layout'}
 $poll=[BitConverter]::ToInt64($h,12);$age=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-$poll
 if($age -lt -1 -or $age -gt 10){throw 'Stale HWiNFO polling time'}
 $so=[long][BitConverter]::ToUInt32($h,20);$ss=[long][BitConverter]::ToUInt32($h,24);$sn=[long][BitConverter]::ToUInt32($h,28)
 $ro=[long][BitConverter]::ToUInt32($h,32);$rs=[long][BitConverter]::ToUInt32($h,36);$rn=[long][BitConverter]::ToUInt32($h,40)
 if($ss -ne 392 -or $rs -ne 460 -or $sn -gt 256 -or $rn -gt 4096 -or $so -lt 48 -or $ro -lt ($so+$ss*$sn) -or ($ro+$rs*$rn) -gt $v.Capacity){throw 'Invalid or changed section bounds'}
 $sensors=@();$b=New-Object byte[] 264
 for($i=0;$i -lt $sn;$i++){[void]$v.ReadArray(($so+$ss*$i),$b,0,264);$sensors+=Zstr $b 8 128}
 $rows=@();$b=New-Object byte[] 316
 for($i=0;$i -lt $rn;$i++){
  $at=$ro+$rs*$i
  if($v.ReadUInt32($at) -ne 1){continue}
  [void]$v.ReadArray($at,$b,0,316)
  $idx=[BitConverter]::ToUInt32($b,4)
  if($idx -ge $sn){throw 'Invalid sensor index'}
  $sensor=$sensors[$idx];if($sensor -notmatch '^CPU \[#0\]'){continue}
  $label=Zstr $b 12 128;$unit=Zstr $b 268 16;$value=[BitConverter]::ToDouble($b,284)
  if([double]::IsNaN($value) -or [double]::IsInfinity($value) -or $value -lt -20 -or $value -gt 130 -or $unit -ne ([string][char]176+'C')){throw 'Unusable CPU temperature value/unit'}
  $rows+=[pscustomobject]@{Sensor=$sensor;SensorIndex=$idx;ReadingId=[BitConverter]::ToUInt32($b,8);Label=$label;Celsius=$value}
 }
 if($v.ReadInt64(12) -ne $poll -or $v.ReadUInt32(0) -ne 1399412552){throw 'Sensor snapshot changed'}
 $cores=@($rows|Where-Object {$_.Sensor -match ': DTS$' -and $_.Label -match '^Core [0-3]$'})
 $package=@($rows|Where-Object {$_.Sensor -match ': DTS$' -and $_.Label -eq 'CPU Package'})
 $labels=@($cores|ForEach-Object {$_.Label}|Sort-Object -Unique)
 $complete=($cores.Count -eq 4 -and $labels.Count -eq 4 -and $package.Count -eq 1)
 $selected=@($rows|Where-Object {$_.Label -eq 'CPU Package'})+@($cores)
 $below=($complete -and @($selected|Where-Object {$_.Celsius -ge 60}).Count -eq 0)
 [pscustomobject]@{Schema='sp7-hwinfo-cpu-temperature-v1';Utc=[DateTime]::UtcNow.ToString('o');Computer=$env:COMPUTERNAME;PollUnixSeconds=$poll;AgeSeconds=$age;CompletePackageAndFourCores=$complete;StrictlyBelow60=$below;Rows=$rows;ReadOnly=$true;RebootPerformed=$false}|ConvertTo-Json -Depth 4 -Compress
} finally {if($v){$v.Dispose()};if($m){$m.Dispose()};if($held){$mu.ReleaseMutex()};if($mu){$mu.Dispose()}}
