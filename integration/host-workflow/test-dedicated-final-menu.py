from pathlib import Path
import subprocess,json,os,shutil,time,socket,hashlib
w=Path(__file__).resolve().parent;s=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/dedicated-grub-menu-final-vm');s.mkdir(mode=0o700)
def cmd(a,n,input=None,env=None):
 r=subprocess.run(a,input=input,capture_output=True,timeout=90,env=env);(s/(n+'.log')).write_bytes(r.stdout+r.stderr);assert r.returncode==0,(n,r.stderr[-500:])
root=s/'synthetic-root';(root/'@/boot/grub').mkdir(parents=True)
actual=(w/'dualboot-config-candidate/sp7-dualboot.cfg').read_text();(root/'@/boot/grub/sp7-dualboot.cfg').write_text(actual+'\necho SP7_DEDICATED_MENU_PARSED\necho SP7_MENU_DEFAULT=$default\necho SP7_MENU_TIMEOUT=$timeout\necho SP7_MENU_ROOT=$root\nhalt\n')
efi=s/'efi.raw';fs=s/'linux.raw';disk=s/'synthetic-gpt.raw'
for p,n in [(efi,64*1024**2),(fs,512*1024**2),(disk,1024**3)]:
 with p.open('xb') as f:f.truncate(n)
cmd(['mkfs.fat','-F','32','-i','9E390F59',str(efi)],'mkfat');mt=w/'portable-tools/mtools/usr/bin'
cmd([str(mt/'mmd'),'-i',str(efi),'::/EFI','::/EFI/SP7Manjaro'],'mkdir')
for src,name in [('shimx64.efi','shimx64.efi'),('debian-grub-2.14-4.efi','grubx64.efi'),('mmx64.efi','mmx64.efi')]:cmd([str(mt/'mcopy'),'-i',str(efi),str(w/'secureboot-candidate'/src),'::/EFI/SP7Manjaro/'+name],'copy-'+name)
cfg=s/'grub.cfg';cfg.write_text('serial --unit=0 --speed=115200\nterminal_output serial\necho SP7_DEDICATED_EFI_DIRECTORY_LOADED\n'+(w/'dualboot-config-candidate/efi-grub.cfg').read_text());cmd([str(mt/'mcopy'),'-i',str(efi),str(cfg),'::/EFI/SP7Manjaro/grub.cfg'],'copy-config')
cmd(['mkfs.btrfs','-f','-U','b7e9ce03-4b90-4c6a-8091-643c8c5879e5','-r',str(root),str(fs)],'mkbtrfs')
table=b'label:gpt\nunit:sectors\n\nstart=2048,size=131072,type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B\nstart=133120,size=32768,type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE\nstart=165888,size=131072,type=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7\nstart=296960,size=65536,type=DE94BBA4-06D1-4D40-A16A-BFD50179D6AC\nstart=524288,size=1048576,type=0FC63DAF-8483-4772-8E79-3D69D8477DE4\n'
cmd(['sfdisk','--no-reread',str(disk)],'gpt',table)
with disk.open('r+b') as d:
 for f,off in [(efi,1048576),(fs,268435456)]:
  d.seek(off)
  with f.open('rb') as src:
   while b:=src.read(1024**2):
    if b.strip(b'\0'):d.write(b)
    else:d.seek(len(b),1)
variables=s/'OVMF_VARS.fd';env=dict(os.environ);env['PYTHONPATH']=str(w/'portable-tools/virt-firmware/usr/lib/python3.14/site-packages')
cmd(['python',str(w/'portable-tools/virt-firmware/usr/bin/virt-fw-vars'),'-i','/usr/share/edk2/x64/OVMF_VARS.4m.fd','-o',str(variables),'--enroll-microsoft','--microsoft-db','all','--set-json',str(w/'secureboot-candidate/sp7-public-policy/dbx-vm-public-only.json'),'--sb','--append-boot-filepath','\\EFI\\SP7Manjaro\\shimx64.efi'],'vars',env=env)
serial=s/'serial.log';sock=Path('/tmp/sp7-dedicated-final-menu.sock')
a=['qemu-system-x86_64','-machine','q35,smm=on','-global','driver=cfi.pflash01,property=secure,value=on','-accel','kvm','-cpu','host','-smp','1','-m','512','-nodefaults','-device','VGA','-display','none','-monitor','none','-serial','file:'+str(serial),'-qmp','unix:'+str(sock)+',server=on,wait=off','-nic','none','-drive','if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.secboot.4m.fd','-drive','if=pflash,format=raw,file='+str(variables),'-drive','if=none,id=publicOnly,format=raw,file='+str(disk),'-device','nvme,serial=SYNTHETIC_MENU_ONLY,drive=publicOnly','-no-reboot'];(s/'launch.json').write_text(json.dumps(a,indent=2)+'\n');start=time.monotonic();seen=b''
with (s/'qemu.log').open('xb') as log:
 p=subprocess.Popen(a,stdout=log,stderr=log,stdin=subprocess.DEVNULL)
 try:
  while time.monotonic()-start<45:
   seen=serial.read_bytes() if serial.exists() else b''
   if b'SP7_DEDICATED_MENU_PARSED' in seen or p.poll() is not None:break
   time.sleep(.25)
 finally:
  if p.poll() is None:p.terminate()
  try:p.wait(timeout=6)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  if sock.exists():sock.unlink()
passed=all(v in seen for v in [b'SP7_DEDICATED_EFI_DIRECTORY_LOADED',b'SP7_DEDICATED_MENU_PARSED',b'SP7_MENU_DEFAULT=0',b'SP7_MENU_TIMEOUT=12',b'SP7_MENU_ROOT=hd0,gpt5'])
r={'schema':'sp7-dedicated-signed-grub-menu-vm-v1','passed':passed,'vm_off':p.poll() is not None,'seconds':time.monotonic()-start,'menu_sha256':hashlib.sha256(actual.encode()).hexdigest(),'no_fallback_efi_or_competing_config_used':True,'secure_boot_enabled_in_firmware':True,'no_network_hostmounts_userbackup_credentials_or_physical_passthrough':True,'physical_os_startup_not_tested':True};(s/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');(w/'secureboot-live-candidate/dedicated-final-menu-vm-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));print(seen.decode(errors='replace')[-1800:]);raise SystemExit(0 if passed else 1)
