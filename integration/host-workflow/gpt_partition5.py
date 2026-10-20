"""Append only approved GPT slot5, with complete before/after checks. No formatting."""
import os,stat,struct,hashlib,zlib,subprocess,uuid
DISK_BYTES=256060514304
START=137729409024//512
SECTORS=117212971008//512
TYPE='0fc63daf-8483-4772-8e79-3d69d8477de4'
SHAPE=[(1048576,272629760),(273678336,16777216),(290455552,137438953472),(254942380032,1117782016)]
TYPES=['c12a7328-f81f-11d2-ba4b-00a0c93ec93b','e3c9e316-0b5c-4db8-817d-f92df00215ae','ebd0a0a2-b9e5-4433-87c0-68b6b72699c7','de94bba4-06d1-4d40-a16a-bfd50179d6ac']
def require(ok,msg):
 if not ok:raise RuntimeError(msg)
def header(b):
 require(len(b)==512 and b[:8]==b'EFI PART','Invalid GPT header')
 n=struct.unpack_from('<I',b,12)[0];require(n==92,'Unexpected GPT header size')
 x=bytearray(b[:n]);crc=struct.unpack_from('<I',x,16)[0];x[16:20]=b'\0'*4;require(zlib.crc32(x)==crc,'GPT header CRC differs')
 return {'disk_guid':b[56:72],'current':struct.unpack_from('<Q',b,24)[0],'alternate':struct.unpack_from('<Q',b,32)[0],'first':struct.unpack_from('<Q',b,40)[0],'last':struct.unpack_from('<Q',b,48)[0],'entry_lba':struct.unpack_from('<Q',b,72)[0],'count':struct.unpack_from('<I',b,80)[0],'entry_bytes':struct.unpack_from('<I',b,84)[0],'entry_crc':struct.unpack_from('<I',b,88)[0]}
def read_table(path):
 require(stat.S_ISBLK(os.stat(path).st_mode),'Target must be the explicitly validated block fixture/device')
 size=int(subprocess.check_output(['blockdev','--getsize64',path],text=True));require(size==DISK_BYTES,'Disk size differs')
 with open(path,'rb',buffering=0) as f:
  primary=f.read(17408);f.seek(size-16896);secondary=f.read(16896)
 a=header(primary[512:1024]);b=header(secondary[-512:]);require(a['current']==1 and b['current']==size//512-1 and a['alternate']==b['current'] and b['alternate']==1,'GPT header locations differ')
 require(a['count']==b['count']==128 and a['entry_bytes']==b['entry_bytes']==128 and a['entry_lba']==2 and b['entry_lba']==size//512-33,'Unexpected GPT array shape')
 entries=primary[1024:];require(len(entries)==16384 and entries==secondary[:16384] and zlib.crc32(entries)==a['entry_crc']==b['entry_crc'],'GPT entry arrays or CRC differ')
 require(a['disk_guid']==b['disk_guid'] and a['first']==b['first'] and a['last']==b['last'],'GPT metadata disagree')
 return {'primary':primary,'secondary':secondary,'header':a,'entries':[entries[i:i+128] for i in range(0,len(entries),128)]}
def occupied(e):return e[:16]!=b'\0'*16
def validate_existing(t):
 require([i+1 for i,e in enumerate(t['entries']) if occupied(e)]==[1,2,3,4],'Not exactly the four approved existing partitions')
 for e,shape,typ in zip(t['entries'],SHAPE,TYPES):
  start,end=struct.unpack_from('<QQ',e,32)
  require((start*512,(end-start+1)*512)==shape and str(uuid.UUID(bytes_le=e[:16]))==typ,'Existing partition geometry/type differs')
 require(START==(SHAPE[2][0]+SHAPE[2][1])//512 and (START+SECTORS)*512==SHAPE[3][0],'New Linux geometry is not exact free gap')
def append(path,primary_sha,secondary_sha,runner=subprocess.run):
 before=read_table(path);validate_existing(before)
 require(hashlib.sha256(before['primary']).hexdigest()==primary_sha and hashlib.sha256(before['secondary']).hexdigest()==secondary_sha,'Fresh GPT is not bound to approved snapshot')
 cmd=['sfdisk','--append','--wipe','never','--wipe-partitions','never',path]
 source=f'start={START}, size={SECTORS}, type={TYPE}, name="Manjaro"\n'
 result=runner(cmd,input=source,capture_output=True,text=True,timeout=30)
 require(result.returncode==0,'sfdisk append failed; inspect actual table, never blindly retry: '+result.stderr[-1200:])
 after=read_table(path)
 require(after['primary'][:512]==before['primary'][:512],'Protective MBR changed')
 require(after['header']['disk_guid']==before['header']['disk_guid'] and after['header']['first']==before['header']['first'] and after['header']['last']==before['header']['last'],'Disk GUID/usable bounds changed')
 require(after['entries'][:4]==before['entries'][:4] and after['entries'][5:]==before['entries'][5:],'Existing GPT entries changed')
 require([i+1 for i,e in enumerate(after['entries']) if occupied(e)]==[1,2,3,4,5],'Unexpected new partition slots')
 e=after['entries'][4];start,end=struct.unpack_from('<QQ',e,32)
 require(start==START and end-start+1==SECTORS and str(uuid.UUID(bytes_le=e[:16]))==TYPE,'Linux5 geometry/type differs')
 guid=str(uuid.UUID(bytes_le=e[16:32]));require(all(e[16:32]!=old[16:32] for old in before['entries'][:4]),'New GUID collides')
 return {'schema':'sp7-linux-partition5-created-v1','partition_number':5,'start_bytes':START*512,'size_bytes':SECTORS*512,'type_guid':TYPE,'partition_guid':guid,'old_entries_and_mbr_identical':True,'no_filesystem_format_performed':True,'primary_sha256':hashlib.sha256(after['primary']).hexdigest(),'secondary_sha256':hashlib.sha256(after['secondary']).hexdigest()}

def preserve_windows_protective_mbr(path,original_mbr,current_primary_sha,current_secondary_sha):
 """Preserve known Windows protective-sector convention without changing new GPT."""
 before=read_table(path);current=before['primary'][:512]
 require(hashlib.sha256(before['primary']).hexdigest()==current_primary_sha and hashlib.sha256(before['secondary']).hexdigest()==current_secondary_sha,'Current table binding differs')
 require(len(original_mbr)==512 and original_mbr[510:]==current[510:]==b'\x55\xaa','Protective MBR signature differs')
 require(original_mbr[450]==current[450]==0xee and struct.unpack_from('<I',original_mbr,454)[0]==struct.unpack_from('<I',current,454)[0]==1,'Protective type/start differs')
 require(struct.unpack_from('<I',original_mbr,458)[0]==0xffffffff and struct.unpack_from('<I',current,458)[0]==DISK_BYTES//512-1,'Not the observed Windows-vs-libfdisk length convention')
 diffs=[i for i,(a,b) in enumerate(zip(original_mbr,current)) if a!=b]
 require(diffs and set(diffs)<=set([451,452,453,458,459,460,461]),'Unexpected MBR difference outside protective CHS/length')
 require([i+1 for i,e in enumerate(before['entries']) if occupied(e)]==[1,2,3,4,5],'Expected exactly five partitions')
 for e,shape,typ in zip(before['entries'],SHAPE,TYPES):
  a,b=struct.unpack_from('<QQ',e,32);require((a*512,(b-a+1)*512)==shape and str(uuid.UUID(bytes_le=e[:16]))==typ,'Existing partition geometry/type differs')
 e=before['entries'][4];a,b=struct.unpack_from('<QQ',e,32);require(a==START and b-a+1==SECTORS and str(uuid.UUID(bytes_le=e[:16]))==TYPE,'Linux5 geometry/type differs')
 with open(path,'r+b',buffering=0) as f:
  require(f.write(original_mbr)==512,'Short protective sector write');os.fsync(f.fileno())
 after=read_table(path)
 require(after['primary'][:512]==original_mbr and after['primary'][512:]==before['primary'][512:] and after['secondary']==before['secondary'],'Post-preservation table mismatch')
 return {'schema':'sp7-protective-mbr-preserved-v1','bytes_written':512,'changed_offsets':diffs,'all_gpt_bytes_unchanged':True,'original_windows_mbr_restored':True,'primary_sha256':hashlib.sha256(after['primary']).hexdigest(),'secondary_sha256':hashlib.sha256(after['secondary']).hexdigest()}
