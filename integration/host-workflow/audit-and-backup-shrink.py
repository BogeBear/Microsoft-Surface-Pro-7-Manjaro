from pathlib import Path
import subprocess,json,datetime,hashlib,zlib,struct,uuid
from windows_transport import command,run
w=Path(__file__).resolve().parent
out=Path('/mnt/sp7-backup/BACKUP/SP7-Windows-before-dualboot-20261019/post-shrink-20261019');out.mkdir(mode=0o700,exist_ok=True)
assert not (out/'gpt-primary.bin').exists() and not (out/'gpt-secondary.bin').exists()
ps=r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$d=Get-Disk -Number 0;$v=Get-Volume -DriveLetter C;$b=Get-BitLockerVolume -MountPoint C:;if($env:COMPUTERNAME -ne 'BOGEBEARSP7' -or $d.FriendlyName -ne 'HFB1M8MO331C0MR' -or $d.Size -ne 256060514304 -or (Get-Partition -DriveLetter C).Size -ne 137438953472){throw 'Unexpected post-shrink identity/layout'};[pscustomobject]@{Computer=$env:COMPUTERNAME;BootUtc=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');Disk=($d|Select-Object Number,FriendlyName,SerialNumber,Size,HealthStatus,OperationalStatus);Partitions=@(Get-Partition -DiskNumber 0|Sort-Object PartitionNumber|Select-Object PartitionNumber,Offset,Size,GptType,Guid);CVolume=($v|Select-Object FileSystem,HealthStatus,OperationalStatus,Size,SizeRemaining);BitLocker=($b|Select-Object LockStatus,VolumeStatus,ProtectionStatus,EncryptionPercentage,EncryptionMethod);SecureBoot=(Confirm-SecureBootUEFI);ACOnline=@(Get-CimInstance -Namespace root\WMI BatteryStatus|ForEach-Object {$_.PowerOnline});DirtyQuery=(@(& fsutil.exe dirty query C:)-join ' ')}|ConvertTo-Json -Depth 6 -Compress'''
r=run(ps,timeout=80);assert r.returncode==0,r.stderr
x=json.loads(r.stdout);(w/'native-shrink-post-audit.json').write_text(json.dumps(x,indent=2)+'\n');(out/'windows-post-shrink-audit.json').write_text(json.dumps(x,indent=2)+'\n')
assert x['SecureBoot'] is True and x['CVolume']['HealthStatus']=='Healthy' and x['CVolume']['FileSystem']=='NTFS'
# BitLocker enums are numeric; Storage CIM health fields are strings.
assert x['BitLocker']['LockStatus']==0 and x['BitLocker']['VolumeStatus']==1 and x['BitLocker']['ProtectionStatus']==1 and x['BitLocker']['EncryptionPercentage']==100
before=json.loads(json.loads((w/'native-shrink-fresh-preflight.json').read_text())['stdout'])['Before'];assert len(x['Partitions'])==len(before)==4
for a,b in zip(before,x['Partitions']):
 assert a['Offset']==b['Offset'] and a['Guid']==b['Guid'] and a['GptType']==b['GptType'] and b['Size']==(137438953472 if a['PartitionNumber']==3 else a['Size'])
records=[]
for name,offset,length in [('gpt-primary.bin',0,34*512),('gpt-secondary.bin',256060514304-33*512,33*512)]:
 src=r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';if($env:COMPUTERNAME -ne 'BOGEBEARSP7' -or (Get-Disk -Number 0).Size -ne 256060514304 -or (Get-Partition -DriveLetter C).Size -ne 137438953472){throw 'Layout changed'};$f=[IO.File]::Open('\\.\PhysicalDrive0',[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite);try{$null=$f.Seek(OFFSET,[IO.SeekOrigin]::Begin);$out=[Console]::OpenStandardOutput();$buffer=New-Object byte[] LENGTH;$n=$f.Read($buffer,0,$buffer.Length);if($n -ne $buffer.Length){throw 'Short GPT read'};$out.Write($buffer,0,$n);$out.Flush()}finally{$f.Dispose()}'''.replace('OFFSET',str(offset)).replace('LENGTH',str(length))
 with (out/name).open('xb') as f:q=subprocess.run(command(src),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.PIPE,timeout=30)
 assert q.returncode==0 and (out/name).stat().st_size==length,q.stderr.decode(errors='replace')
 records.append({'name':name,'offset':offset,'bytes':length,'sha256':hashlib.sha256((out/name).read_bytes()).hexdigest()})
primary=(out/'gpt-primary.bin').read_bytes();secondary=(out/'gpt-secondary.bin').read_bytes();h=primary[512:1024];hs=struct.unpack_from('<I',h,12)[0];assert h[:8]==b'EFI PART' and hs==92
check=bytearray(h[:hs]);crc=struct.unpack_from('<I',check,16)[0];check[16:20]=b'\0'*4;assert zlib.crc32(check)==crc
count,esz,ecrc=struct.unpack_from('<III',h,80);assert count==128 and esz==128
entries=primary[1024:1024+count*esz];assert zlib.crc32(entries)==ecrc and secondary[:count*esz]==entries
sh=secondary[-512:];check=bytearray(sh[:92]);crc=struct.unpack_from('<I',check,16)[0];check[16:20]=b'\0'*4;assert sh[:8]==b'EFI PART' and zlib.crc32(check)==crc
for i,p in enumerate(x['Partitions']):
 e=entries[i*128:(i+1)*128];start,end=struct.unpack_from('<QQ',e,32);assert start*512==p['Offset'] and (end-start+1)*512==p['Size'];assert str(uuid.UUID(bytes_le=e[16:32]))==p['Guid'].strip('{}').lower()
receipt={'schema':'sp7-post-native-shrink-gpt-backup-v1','host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete':True,'primary_secondary_crc_valid':True,'partition_arrays_identical':True,'partition_guids_and_sizes_match_native_audit':True,'backups_not_on_sp7':True,'files':records,'physical_disk_written_by_this_script':False}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');(w/'native-shrink-gpt-backup.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(x,indent=2));print(json.dumps(receipt,indent=2))
