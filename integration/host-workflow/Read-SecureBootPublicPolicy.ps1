$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class Sp7EfiRead {
 [StructLayout(LayoutKind.Sequential)] public struct Priv { public uint Count; public uint Low; public int High; public uint Attr; }
 [DllImport("advapi32.dll",SetLastError=true)] public static extern bool OpenProcessToken(IntPtr p,uint access,out IntPtr token);
 [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentProcess();
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern bool LookupPrivilegeValue(string system,string name,out long luid);
 [DllImport("advapi32.dll",SetLastError=true)] public static extern bool AdjustTokenPrivileges(IntPtr token,bool disable,ref Priv state,uint length,out Priv previous,out uint returned);
 [DllImport("kernel32.dll",SetLastError=true)] public static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern uint GetFirmwareEnvironmentVariable(string name,string guid,byte[] data,uint length);
}
'@
$t=[IntPtr]::Zero;$l=[long]0
if(-not [Sp7EfiRead]::OpenProcessToken([Sp7EfiRead]::GetCurrentProcess(),40,[ref]$t)){throw 'Cannot open own process token'}
$old=New-Object Sp7EfiRead+Priv;$ret=[uint32]0;$changed=$false
try {
 if(-not [Sp7EfiRead]::LookupPrivilegeValue($null,'SeSystemEnvironmentPrivilege',[ref]$l)){throw 'Privilege lookup failed'}
 $v=New-Object Sp7EfiRead+Priv;$v.Count=1;$v.Low=[uint32]($l -band 0xffffffff);$v.High=[int32]($l -shr 32);$v.Attr=2
 if(-not [Sp7EfiRead]::AdjustTokenPrivileges($t,$false,[ref]$v,16,[ref]$old,[ref]$ret) -or [Runtime.InteropServices.Marshal]::GetLastWin32Error() -ne 0){throw 'Cannot enable existing read privilege on own process token'}
 $changed=$true
 $rows=@()
 foreach($n in @('MokList','MokListRT','MokListTrusted','MokListTrustedRT','MokSBState','MokIgnoreDB','SbatLevel')) {
  $b=New-Object byte[] (1MB);$count=[Sp7EfiRead]::GetFirmwareEnvironmentVariable($n,'{605dab50-e046-4300-abb6-3dd810dd8b23}',$b,$b.Length);$err=if($count -eq 0){[Runtime.InteropServices.Marshal]::GetLastWin32Error()}else{0}
  $rows+=[pscustomobject]@{Name=$n;Bytes=$count;Win32Error=$err;Base64=if($count -gt 0){[Convert]::ToBase64String($b,0,$count)}else{$null}}
 }
 $public=@()
 foreach($n in @('db','dbx','PK','KEK')) {
  try {$v=Get-SecureBootUEFI -Name $n;$public+=[pscustomobject]@{Name=$n;Bytes=$v.Bytes.Length;Base64=[Convert]::ToBase64String($v.Bytes)}}catch{$public+=[pscustomobject]@{Name=$n;ErrorType=$_.Exception.GetType().Name}}
 }
 [pscustomobject]@{Schema='sp7-public-secureboot-policy-read-v1';Computer=$env:COMPUTERNAME;Timestamp=(Get-Date).ToString('o');SecureBoot=(Confirm-SecureBootUEFI);ShimVariables=$rows;PublicSecureBootDatabases=$public;FirmwareWritten=$false;OnlyExistingOwnTokenPrivilegeTemporarilyEnabled=$true}|ConvertTo-Json -Depth 5 -Compress
} finally {
 if($changed){$unused=New-Object Sp7EfiRead+Priv;$n=[uint32]0;$null=[Sp7EfiRead]::AdjustTokenPrivileges($t,$false,[ref]$old,16,[ref]$unused,[ref]$n)}
 if($t -ne [IntPtr]::Zero){$null=[Sp7EfiRead]::CloseHandle($t)}
}
