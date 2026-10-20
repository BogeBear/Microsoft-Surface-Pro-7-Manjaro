"""Boot verified PUBLIC Clonezilla live files only; no user data or real disk."""
import pathlib,subprocess,json,os,shutil,zipfile,time,socket,hashlib
os.umask(0o077);w=pathlib.Path(__file__).resolve().parent;s=pathlib.Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/synthetic-secureboot-clonezilla-live-v1-vm');s.mkdir(mode=0o700)
def cmd(a,n,input=None):
 r=subprocess.run(a,input=input,capture_output=True,timeout=180);(s/(n+'.log')).write_bytes(r.stdout+r.stderr);assert r.returncode==0,(n,r.returncode,r.stderr[-600:])
efi=s/'public-live-fat.raw';disk=s/'public-live-gpt.raw'
for p,n in [(efi,1024**3),(disk,1100*1024**2)]:
 with p.open('xb') as f:f.truncate(n)
cmd(['mkfs.fat','-F','32','-n','SP7_VM_ONLY',str(efi)],'mkfat');mt=w/'portable-tools/mtools/usr/bin'
def cp(src,dst,n):cmd([str(mt/'mcopy'),'-i',str(efi),str(src),'::/'+dst],n)
cmd([str(mt/'mmd'),'-i',str(efi),'::/EFI','::/EFI/BOOT','::/live'],'mkdir')
for src,dst in [('shimx64.efi','BOOTX64.EFI'),('debian-grub-2.14-4.efi','grubx64.efi'),('mmx64.efi','mmx64.efi')]:cp(w/'secureboot-candidate'/src,'EFI/BOOT/'+dst,'copy-'+src)
with zipfile.ZipFile('/mnt/sp7-backup/BACKUP/rescue-media-20261014/clonezilla-live-3.3.3-37-amd64.zip') as z:
 for n in ['vmlinuz','initrd.img','filesystem.squashfs']:
  f=s/n
  with z.open('live/'+n) as src,f.open('xb') as dst:shutil.copyfileobj(src,dst)
  cp(f,'live/'+n,'copy-'+n)
script=s/'sp7-vm-check.sh';script.write_text('''#!/bin/bash
exec >/dev/ttyS0 2>&1
echo SP7_PUBLIC_LIVE_USERSPACE_READY
uname -r
mokutil --sb-state
cat /sys/kernel/security/lockdown
lsblk -bdno NAME,SIZE,MODEL
partclone.restore --version
python3 - <<'END'
from pathlib import Path
import struct
p=Path('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c')
print('SP7_LIVE_SECURE_BOOT='+str(p.read_bytes()[4]),flush=True)
END
echo SP7_LIVE_READONLY_PROBE_COMPLETE
sync
poweroff -f
''');cp(script,'sp7-vm-check.sh','copy-vm-only-probe')
cfg=s/'grub.cfg';cfg.write_text('''serial --unit=0 --speed=115200
terminal_output serial
echo SP7_LIVE_VENDOR_GRUB_LOADED
search --set=root -f /sp7-vm-check.sh
linux /live/vmlinuz boot=live union=overlay username=user config components hostname=sp7-vm-only noswap noeject noprompt locales=en_US.UTF-8 keyboard-layouts=us ocs_live_run="bash /lib/live/mount/medium/sp7-vm-check.sh" ocs_live_batch=yes console=ttyS0,115200 loglevel=4 nosplash nomodeset
initrd /live/initrd.img
boot
''');cp(cfg,'EFI/BOOT/grub.cfg','copy-cfg')
cmd(['sfdisk','--no-reread',str(disk)],'gpt',b'label: gpt\nunit: sectors\n\nstart=2048,size=2097152,type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B\n')
with disk.open('r+b') as d,efi.open('rb') as f:
 d.seek(1048576)
 while b:=f.read(1024**2):
  if b.strip(b'\0'):d.write(b)
  else:d.seek(len(b),1)
v=s/'OVMF_VARS.fd';env=dict(os.environ);env['PYTHONPATH']=str(w/'portable-tools/virt-firmware/usr/lib/python3.14/site-packages')
r=subprocess.run(['python',str(w/'portable-tools/virt-firmware/usr/bin/virt-fw-vars'),'-i','/usr/share/edk2/x64/OVMF_VARS.4m.fd','-o',str(v),'--set-json',str(w/'secureboot-candidate/sp7-public-policy/dbx-vm-public-only.json'),'--enroll-microsoft','--microsoft-db','all','--sb','--output-json',str(s/'vars-before.json')],capture_output=True,env=env);(s/'vars-build.log').write_bytes(r.stdout+r.stderr);assert r.returncode==0
serial=s/'serial.log';sock=pathlib.Path('/tmp/sp7-live-vm-'+str(os.getpid())+'.sock')
a=['qemu-system-x86_64','-machine','q35,smm=on','-global','driver=cfi.pflash01,property=secure,value=on','-accel','kvm','-cpu','host','-smp','2','-m','3072','-nodefaults','-device','VGA','-display','none','-monitor','none','-serial','file:'+str(serial),'-qmp','unix:'+str(sock)+',server=on,wait=off','-nic','none','-drive','if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.secboot.4m.fd','-drive','if=pflash,format=raw,file='+str(v),'-drive','if=none,id=synthetic,format=raw,file='+str(disk),'-device','nvme,serial=SYNTHETIC_SP7_ONLY,drive=synthetic','-no-reboot']
(s/'launch.json').write_text(json.dumps(a,indent=2)+'\n');start=time.monotonic();passed=False
with (s/'qemu.log').open('xb') as log:
 p=subprocess.Popen(a,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
 try:
  while time.monotonic()-start<170:
   b=serial.read_bytes() if serial.exists() else b''
   if b'SP7_LIVE_SECURE_BOOT=1' in b and b'SP7_LIVE_READONLY_PROBE_COMPLETE' in b:passed=True;break
   if p.poll() is not None:break
   time.sleep(.5)
 finally:
  if p.poll() is None:
   try:
    with socket.socket(socket.AF_UNIX) as c:
     c.settimeout(3);c.connect(str(sock));c.recv(65536);c.sendall(b'{"execute":"qmp_capabilities"}\n');c.recv(65536);c.sendall(b'{"execute":"quit"}\n')
   except OSError:p.terminate()
  try:p.wait(timeout=8)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  if sock.exists():sock.unlink()
r={'schema':'sp7-vendor-signed-clonezilla-live-v1','passed':passed,'vm_off':p.poll() is not None,'qemu_exit':p.returncode,'seconds':time.monotonic()-start,'no_network_host_mounts_user_backup_private_keys_or_passthrough':True,'physical_sp7_boot_tested':False,'no_extra_mok_keys_in_test':True};(s/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');(w/'secureboot-live-candidate/live-vm-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True);raise SystemExit(0 if passed else 1)
