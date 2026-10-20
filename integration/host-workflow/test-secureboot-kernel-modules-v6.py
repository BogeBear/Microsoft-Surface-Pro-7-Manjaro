"""Secret-free synthetic GPT test, no host mounts, networking or passthrough."""
import hashlib,json,os,pathlib,shutil,socket,subprocess,time
os.umask(0o077)
w=pathlib.Path(__file__).resolve().parent
s=pathlib.Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/synthetic-secureboot-kernel-module-v6-vm');s.mkdir(mode=0o700)
root=s/'root';(root/'@/boot/grub').mkdir(parents=True)
(root/'@/boot/grub/grub.cfg').write_text('serial --unit=0 --speed=115200\nterminal_output serial\necho SP7_SYNTHETIC_UUID_CONFIG_LOADED\necho SP7_ROOT=$root\necho SP7_PREFIX=$prefix\nlinux /@/boot/vmlinuz-linux-surface console=ttyS0,115200 earlyprintk=serial,ttyS0,115200 panic=1 lockdown=integrity\ninitrd /@/boot/initramfs-probe.img\nboot\n')
shutil.copyfile('/mnt/sp7-backup/BACKUP/SP7-camera-20261014/tree/boot/vmlinuz-linux-surface',root/'@/boot/vmlinuz-linux-surface')
shutil.copyfile(w/'secureboot-probe-initramfs/initramfs-v6.cpio.gz',root/'@/boot/initramfs-probe.img')
def cmd(args,name,input=None):
 r=subprocess.run(args,input=input,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180);(s/(name+'.log')).write_bytes(r.stdout);assert r.returncode==0,(name,r.returncode,r.stdout[-600:])
efi=s/'efi.raw';btrfs=s/'linux.raw';disk=s/'gpt-five-partitions.raw'
for p,size in [(efi,64*1024**2),(btrfs,512*1024**2),(disk,1024**3)]:
 with p.open('xb') as f:f.truncate(size)
cmd(['/usr/bin/mkfs.fat','-F','32',str(efi)],'mkfat')
mtools=w/'portable-tools/mtools/usr/bin'
cmd([str(mtools/'mmd'),'-i',str(efi),'::/EFI','::/EFI/BOOT'],'mkdir-efi')
cmd([str(mtools/'mcopy'),'-i',str(efi),str(w/'secureboot-candidate/shimx64.efi'),'::/EFI/BOOT/BOOTX64.EFI'],'copy-efi')
cmd([str(mtools/'mcopy'),'-i',str(efi),str(w/'secureboot-candidate/debian-grub-2.14-4.efi'),'::/EFI/BOOT/grubx64.efi'],'copy-signed-grub')
cmd([str(mtools/'mcopy'),'-i',str(efi),str(w/'secureboot-candidate/mmx64.efi'),'::/EFI/BOOT/mmx64.efi'],'copy-mok-manager')
# Bootstrap locations are deliberately distinguishable in the synthetic fixture.
cmd([str(mtools/'mmd'),'-i',str(efi),'::/boot','::/boot/grub','::/EFI/debian','::/.disk'],'bootstrap-directories')
info=s/'live-info.txt';info.write_text('SP7 synthetic UEFI routing test only\n')
cmd([str(mtools/'mcopy'),'-i',str(efi),str(info),'::/.disk/info'],'live-marker')
for index,dest in enumerate(['::/boot/grub/grub.cfg','::/EFI/BOOT/grub.cfg','::/EFI/debian/grub.cfg','::/grub.cfg']):
 bootstrap=s/('bootstrap-'+str(index)+'.cfg');bootstrap.write_text('serial --unit=0 --speed=115200\nterminal_output serial\necho SP7_BOOTSTRAP_PATH='+dest+'\n'+(w/'secureboot-candidate/embedded.cfg').read_text())
 cmd([str(mtools/'mcopy'),'-i',str(efi),str(bootstrap),dest],'copy-bootstrap-'+str(index))
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
vars=s/'OVMF_VARS.fd'
varenv=dict(os.environ);varenv['PYTHONPATH']=str(w/'portable-tools/virt-firmware/usr/lib/python3.14/site-packages')
varcmd=['/usr/bin/python',str(w/'portable-tools/virt-firmware/usr/bin/virt-fw-vars'),'-i','/usr/share/edk2/x64/OVMF_VARS.4m.fd','-o',str(vars),'--enroll-microsoft','--microsoft-db','all','--set-json',str(w/'secureboot-candidate/sp7-public-policy/dbx-vm-public-only.json'),'--sb','--set-true','MokListTrusted','--add-mok','605dab50-e046-4300-abb6-3dd810dd8b23',str(w/'secureboot-candidate/project.der'),'--add-mok','605dab50-e046-4300-abb6-3dd810dd8b23',str(w/'secureboot-candidate/surface.cer'),'--output-json',str(s/'vars-before.json')]
v=subprocess.run(varcmd,env=varenv,capture_output=True);(s/'vars-build.log').write_bytes(v.stdout+v.stderr);assert v.returncode==0

sock=pathlib.Path('/tmp/sp7-uuid-test-'+str(os.getpid())+'.sock');serial=s/'serial.log'
args=['/usr/bin/qemu-system-x86_64','-machine','q35,smm=on','-global','driver=cfi.pflash01,property=secure,value=on','-accel','kvm','-cpu','host','-smp','1','-m','2048','-nodefaults','-device','VGA','-display','none','-monitor','none','-serial','file:'+str(serial),'-qmp','unix:'+str(sock)+',server=on,wait=off','-nic','none','-drive','if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.secboot.4m.fd','-drive','if=pflash,format=raw,file='+str(vars),'-drive','if=none,id=synthetic,format=raw,file='+str(disk),'-device','nvme,serial=SYNTHETIC_SP7_ONLY,drive=synthetic','-no-reboot']
(s/'launch.json').write_text(json.dumps(args,indent=2)+'\n')
start=time.monotonic();passed=False
with (s/'qemu.log').open('xb') as log:
 proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
 try:
  while time.monotonic()-start<70:
   content=serial.read_bytes() if serial.exists() else b''
   if b'SP7_SECURE_KERNEL_AND_MODULE_PROOF_PASS' in content and b'SP7_GUEST_SECURE_BOOT=1' in content:passed=True;break
   if b'SP7_SECURE_KERNEL_AND_MODULE_PROOF_FAIL' in content:break
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
report={'schema':'synthetic-secureboot-surface-kernel-module-enforcement-v1','passed':passed,'qemu_exit':proc.returncode,'vm_off':proc.poll() is not None,'seconds':time.monotonic()-start,'boot_efi_sha256':hashlib.sha256((w/'secureboot-candidate/debian-grub-2.14-4.efi').read_bytes()).hexdigest(),'network':False,'host_mounts':False,'physical_passthrough':False,'user_backup_or_credentials_in_vm':False,'synthetic_filesystem_only':True,'secure_boot_firmware_template_enabled':True,'secure_boot_guest_observation_pending':True,'negative_signature_control_pending':True,'physical_sp7_boot_tested':False}
(s/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');(w/'secureboot-candidate/synthetic-kernel-module-test.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
raise SystemExit(0 if passed else 1)
