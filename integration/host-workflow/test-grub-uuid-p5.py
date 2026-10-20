"""Secret-free synthetic GPT test, no host mounts, networking or passthrough."""
import hashlib,json,os,pathlib,shutil,socket,subprocess,time
os.umask(0o077)
w=pathlib.Path(__file__).resolve().parent
s=pathlib.Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/synthetic-uuid-vm');s.mkdir(mode=0o700)
root=s/'root';(root/'@/boot/grub').mkdir(parents=True)
(root/'@/boot/grub/grub.cfg').write_text('serial --unit=0 --speed=115200\nterminal_output serial\necho SP7_SYNTHETIC_UUID_CONFIG_LOADED\necho SP7_ROOT=$root\necho SP7_PREFIX=$prefix\nhalt\n')
def cmd(args,name,input=None):
 r=subprocess.run(args,input=input,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180);(s/(name+'.log')).write_bytes(r.stdout);assert r.returncode==0,(name,r.returncode,r.stdout[-600:])
efi=s/'efi.raw';btrfs=s/'linux.raw';disk=s/'gpt-five-partitions.raw'
for p,size in [(efi,64*1024**2),(btrfs,512*1024**2),(disk,1024**3)]:
 with p.open('xb') as f:f.truncate(size)
cmd(['/usr/bin/mkfs.fat','-F','32',str(efi)],'mkfat')
mtools=w/'portable-tools/mtools/usr/bin'
cmd([str(mtools/'mmd'),'-i',str(efi),'::/EFI','::/EFI/BOOT'],'mkdir-efi')
cmd([str(mtools/'mcopy'),'-i',str(efi),str(w/'boot-candidate/grubx64.efi'),'::/EFI/BOOT/BOOTX64.EFI'],'copy-efi')
cmd(['/usr/bin/mkfs.btrfs','-f','-U','b7e9ce03-4b90-4c6a-8091-643c8c5879e5','-r',str(root),str(btrfs)],'mkbtrfs')
table=b"label: gpt\nunit: sectors\n\nstart=2048,size=131072,type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B\nstart=133120,size=32768,type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE\nstart=165888,size=131072,type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7\nstart=296960,size=65536,type=DE94BBA4-06D1-4D40-A16A-BFD50179D6AC\nstart=524288,size=1048576,type=0FC63DAF-8483-4772-8E79-3D69D8477DE4\n"
cmd(['/usr/bin/sfdisk','--no-reread',str(disk)],'sfdisk',table)
with disk.open('r+b') as dst:
 for p,offset in [(efi,1048576),(btrfs,268435456)]:
  dst.seek(offset)
  with p.open('rb') as source:
   # Avoid allocating zeros in the combined image.
   while block:=source.read(1024**2):
    if block.strip(b'\0'):dst.write(block)
    else:dst.seek(len(block),1)
vars=s/'OVMF_VARS.fd';shutil.copyfile('/usr/share/edk2/x64/OVMF_VARS.4m.fd',vars)
sock=pathlib.Path('/tmp/sp7-uuid-test-'+str(os.getpid())+'.sock');serial=s/'serial.log'
args=['/usr/bin/qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','host','-smp','1','-m','512','-nodefaults','-device','VGA','-display','none','-monitor','none','-serial','file:'+str(serial),'-qmp','unix:'+str(sock)+',server=on,wait=off','-nic','none','-drive','if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd','-drive','if=pflash,format=raw,file='+str(vars),'-drive','if=none,id=synthetic,format=raw,file='+str(disk),'-device','nvme,serial=SYNTHETIC_SP7_ONLY,drive=synthetic','-no-reboot']
(s/'launch.json').write_text(json.dumps(args,indent=2)+'\n')
start=time.monotonic();passed=False
with (s/'qemu.log').open('xb') as log:
 proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
 try:
  while time.monotonic()-start<70:
   content=serial.read_bytes() if serial.exists() else b''
   if b'SP7_SYNTHETIC_UUID_CONFIG_LOADED' in content and b'SP7_ROOT=hd0,gpt5' in content:passed=True;break
   if proc.poll() is not None:break
   time.sleep(.25)
 finally:
  if proc.poll() is None:
   try:
    with socket.socket(socket.AF_UNIX) as c:
     c.settimeout(3);c.connect(str(sock));c.recv(65536);c.sendall(b'{"execute":"qmp_capabilities"}\n');c.recv(65536);c.sendall(b'{"execute":"quit"}\n')
   except OSError:proc.terminate()
  try:proc.wait(timeout=8)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 if sock.exists():sock.unlink()
report={'schema':'synthetic-grub-uuid-gpt5-test-v1','passed':passed,'qemu_exit':proc.returncode,'vm_off':proc.poll() is not None,'seconds':time.monotonic()-start,'boot_efi_sha256':hashlib.sha256((w/'boot-candidate/grubx64.efi').read_bytes()).hexdigest(),'network':False,'host_mounts':False,'physical_passthrough':False,'user_backup_or_credentials_in_vm':False,'synthetic_filesystem_only':True,'secure_boot_tested':False,'physical_sp7_boot_tested':False}
(s/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');(w/'boot-candidate/synthetic-test.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
raise SystemExit(0 if passed else 1)
