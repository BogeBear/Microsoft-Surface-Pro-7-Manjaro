from pathlib import Path
import os,json,hashlib,subprocess,time
from windows_transport import command
os.umask(0o077);w=Path(__file__).resolve().parent;dest=Path('/mnt/sp7-backup/BACKUP/SP7-Windows-before-dualboot-20261019/disk-metadata');dest.mkdir(mode=0o700,exist_ok=False)
ranges=[('gpt-prefix.bin',0,1048576),('gpt-suffix.bin',256060514304-33792,33792),('partition-1-efi.raw',1048576,272629760),('partition-2-msr.raw',273678336,16777216),('partition-4-winre.raw',254942380032,1117782016)]
report={'schema':'windows-physical-read-stream-backup-v1','physical_disk_written':False,'source_staging_files':False,'complete':False,'files':[]}
for name,offset,length in ranges:
 src="$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';if($env:COMPUTERNAME -ne 'BOGEBEARSP7' -or (Get-Disk -Number 0).Size -ne 256060514304 -or (Get-Partition -DiskNumber 0 -PartitionNumber 3).Offset -ne 290455552 -or (Get-Partition -DiskNumber 0 -PartitionNumber 3).Size -ne 254651924480){throw 'Disk layout changed'};$f=[IO.File]::Open('\\\\.\\PhysicalDrive0',[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite);try{$null=$f.Seek("+str(offset)+",[IO.SeekOrigin]::Begin);$out=[Console]::OpenStandardOutput();$buffer=New-Object byte[] (1MB);$left="+str(length)+";while($left -gt 0){$want=[int][Math]::Min($left,$buffer.Length);$n=$f.Read($buffer,0,$want);if($n -le 0){throw 'Short read'};$out.Write($buffer,0,$n);$left-=$n};$out.Flush()}finally{$f.Dispose()}"
 target=dest/name
 with target.open('xb') as output,(dest/(name+'.ssh.log')).open('xb') as log:
  r=subprocess.run(command(src),stdin=subprocess.DEVNULL,stdout=output,stderr=log,timeout=900)
 assert r.returncode==0 and target.stat().st_size==length,(name,r.returncode,target.stat().st_size)
 h=hashlib.file_digest(target.open('rb'),'sha256').hexdigest();report['files'].append({'name':name,'source_offset':offset,'bytes':length,'sha256':h})
 (dest/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print('Read-only disk metadata saved:',name,length,flush=True)
report['complete']=True;report['finished_epoch']=time.time();(dest/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
b=(dest/'partition-1-efi.raw').read_bytes()[:512];assert b[82:90]==b'FAT32   ';id=int.from_bytes(b[67:71],'little');report={'fat_uuid':f'{id>>16:04X}-{id&65535:04X}','fat_type':'FAT32','efi_not_formatted':True};(w/'windows-efi-id.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
