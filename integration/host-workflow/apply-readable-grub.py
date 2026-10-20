from pathlib import Path
import json,base64,hashlib,subprocess,datetime
from windows_transport import OPTIONS,TARGET
w=Path(__file__).resolve().parent;c=w/'readable-grub-candidate';b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/readable-grub-20261019')
vm=json.loads((c/'built-in-vm-receipt.json').read_text());assert vm['passed'] and vm['vm_off'];new=(c/'grub-built-in.cfg').read_bytes();h=hashlib.sha256(new).hexdigest();assert h==vm['menu_sha256'];old=(b/'grub.cfg.before').read_bytes();assert hashlib.sha256(old).hexdigest()=='a6d646f016c845c1e0827bc6b291c0267a7b8b909710941c8f124ead4c114917';pre=json.loads((b/'efi-before.json').read_text())
ps=r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
if($env:COMPUTERNAME -ne 'BOGEBEARSP7' -or !(Confirm-SecureBootUEFI)){throw 'Wrong host or Secure Boot state'}
if((Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o') -ne 'EXPECTEDBOOT'){throw 'Boot changed'}
$p=Get-Partition -DiskNumber 0 -PartitionNumber 1;if($p.Guid -ne '{3f9e8859-9832-44c1-b881-62e8034abde8}' -or $p.Size -ne 272629760 -or $p.Offset -ne 1048576){throw 'Wrong EFI target'}
$root=@($p.AccessPaths|Where-Object{$_ -like '\\?\Volume*'})[0];if(!$root){throw 'No volume path'};$cfg=$root+'EFI\SP7Manjaro\grub.cfg';$stage=$cfg+'.sp7-new';if([IO.File]::Exists($stage)){throw 'Staging collision'}
function HashBytes([byte[]]$v){$a=[Security.Cryptography.SHA256]::Create();try{[BitConverter]::ToString($a.ComputeHash($v)).Replace('-','').ToLower()}finally{$a.Dispose()}}
$old=[IO.File]::ReadAllBytes($cfg);if((HashBytes $old) -ne 'a6d646f016c845c1e0827bc6b291c0267a7b8b909710941c8f124ead4c114917'){throw 'Original config changed'}
$new=[Convert]::FromBase64String('NEWBASE64');if((HashBytes $new) -ne 'NEWHASH'){throw 'Payload mismatch'}
try{
 $f=[IO.FileStream]::new($stage,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough);try{$f.Write($new,0,$new.Length);$f.Flush($true)}finally{$f.Dispose()}
 if((HashBytes ([IO.File]::ReadAllBytes($stage))) -ne 'NEWHASH'){throw 'Staged hash mismatch'}
 # Move-Item on a volume GUID path is provider-dependent; use the public Windows file API through the built-in VisualBasic assembly.
 [void][Reflection.Assembly]::LoadWithPartialName('Microsoft.VisualBasic');[Microsoft.VisualBasic.FileIO.FileSystem]::MoveFile($stage,$cfg,$true)
 if((HashBytes ([IO.File]::ReadAllBytes($cfg))) -ne 'NEWHASH'){throw 'Installed readback mismatch'}
}catch{
 $problem=$_.Exception.Message
 [IO.File]::WriteAllBytes($cfg,$old)
 if([IO.File]::Exists($stage)){[IO.File]::Delete($stage)}
 throw ('Config update failed; original restored: '+$problem)
}
$manifest=@{};foreach($fn in [IO.Directory]::EnumerateFiles($root+'EFI','*',[IO.SearchOption]::AllDirectories)){$rel=$fn.Substring($root.Length).Replace('\','/');try{$st=[IO.File]::Open($fn,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete));try{$a=[Security.Cryptography.SHA256]::Create();$hash=[BitConverter]::ToString($a.ComputeHash($st)).Replace('-','').ToLower();$manifest[$rel]=@{SHA256=$hash;Bytes=$st.Length}}finally{$st.Dispose();$a.Dispose()}}catch{$manifest[$rel]=@{ReadError=$_.Exception.GetType().Name}}}
[pscustomobject]@{ConfigSHA256=(HashBytes ([IO.File]::ReadAllBytes($cfg)));Files=$manifest;SecureBoot=(Confirm-SecureBootUEFI);BitLockerProtection=[string](Get-BitLockerVolume -MountPoint C:).ProtectionStatus;Firmware=(& bcdedit /enum firmware|Out-String);HWiNFOProcesses=@(Get-Process -Name 'HWiNFO64' -ErrorAction SilentlyContinue|Select-Object ProcessName,Id);NoBCDOrWindowsLoaderWrite=$true;NoPartitionOrFirmwareWrite=$true;NoPersistentStagingFile=[bool](![IO.File]::Exists($stage))}|ConvertTo-Json -Depth 6 -Compress
'''.replace('EXPECTEDBOOT',pre['Boot']).replace('NEWBASE64',base64.b64encode(new).decode()).replace('NEWHASH',h)
(c/'apply-reviewed.ps1').write_text(ps)
bootstrap="$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false);$source=[Console]::In.ReadToEnd();& ([ScriptBlock]::Create($source))"
remote='powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(bootstrap.encode('utf-16le')).decode()
assert not (c/'physical-apply-result.json').exists(),'Existing apply result; inspect before any repeat'
r=subprocess.run(['ssh',*OPTIONS,TARGET,remote],input=ps,text=True,capture_output=True,encoding='utf-8',errors='replace',timeout=100);o={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(c/'physical-apply-result.json').write_text(json.dumps(o,indent=2)+'\n');(b/'physical-apply-result.json').write_text(json.dumps(o,indent=2)+'\n');assert r.returncode==0,r.stderr;j=json.loads(r.stdout.lstrip('\ufeff'));assert j['ConfigSHA256']==h and j['SecureBoot'] and j['NoPersistentStagingFile'];before=pre['Files'];after=j['Files'];assert set(before)==set(after),'EFI file list changed';changed={k:{'before':before[k],'after':after[k]} for k in before if before[k]!=after[k]};assert set(changed)=={'EFI/SP7Manjaro/grub.cfg'},changed
receipt={'host_utc':o['host_utc'],'changed_files':changed,'all_other_readable_efi_files_unchanged':True,'unreadable_live_bcd_files':[k for k,v in before.items() if 'ReadError' in v],'live_BCD_not_readable_or_modified':True,'current_active_menu':'EFI/SP7Manjaro/grub.cfg','historical_Btrfs_menu_unchanged_and_no_longer_loaded':True,'menu_sha256':h,'secure_boot':True,'bitlocker_protection':j['BitLockerProtection'],'physical_windows_via_grub_test_pending':True,'firmware':j['Firmware'],'hwinfo_processes':j['HWiNFOProcesses']};(c/'physical-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');(b/'physical-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
