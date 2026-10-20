"""Boot verified PUBLIC Clonezilla live files only; no user data or real disk."""
import pathlib,subprocess,json,os,shutil,zipfile,time,socket,hashlib
VM_SCRIPT='#!/bin/bash\nset -euo pipefail\nexec >/dev/ttyS0 2>&1\necho SP7_PUBLIC_LIVE_USERSPACE_READY\nuname -r\nmokutil --sb-state\ncat /sys/kernel/security/lockdown\np=/run/live/medium/SP7-DUALBOOT\nbash -n "$p/enable-temporary-ssh.sh"\nset +e\nsudo bash "$p/enable-temporary-ssh.sh" >/run/sp7-helper-negative.txt 2>&1\nrc=$?\nset -e\ncat /run/sp7-helper-negative.txt\n[[ $rc != 0 && ! -e /run/sp7-dualboot-ssh ]]\ngrep -q \'only for the Surface Pro 7\' /run/sp7-helper-negative.txt\necho SP7_HELPER_NON_SURFACE_GUARD_PASS\nr=/run/sp7-sshd-offline-test\ninstall -d -m 0755 "$r" /run/sshd\nssh-keygen -q -t ed25519 -N \'\' -f "$r/host_key"\ncp "$p/bogebear.pub" "$r/authorized_keys"\npython3 - <<\'END\'\nfrom pathlib import Path\ns=Path(\'/run/live/medium/SP7-DUALBOOT/enable-temporary-ssh.sh\').read_text()\ns=s.split(\'cat >"$r/sshd_config" <<EOF\\n\',1)[1].split(\'\\nEOF\\n\',1)[0]\ns=s.replace(\'$r\',\'/run/sp7-sshd-offline-test\').replace(\'$addr\',\'127.0.0.1\').replace(\'$peer\',\'192.0.2.10\')\nPath(\'/run/sp7-sshd-offline-test/sshd_config\').write_text(s+\'\\n\')\np=Path(\'/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c\')\nprint(\'SP7_LIVE_SECURE_BOOT=\'+str(p.read_bytes()[4]),flush=True)\nEND\n/usr/sbin/sshd -t -f "$r/sshd_config"\n/usr/sbin/sshd -T -f "$r/sshd_config" -C user=user,addr=192.0.2.10,host=bogebear >/run/sp7-sshd-effective.txt\nfor rule in \'port 2222\' \'passwordauthentication no\' \'kbdinteractiveauthentication no\' \'permitrootlogin no\' \'authenticationmethods publickey\' \'allowusers user@192.0.2.10\' \'allowtcpforwarding no\' \'allowagentforwarding no\'; do grep -Fxq "$rule" /run/sp7-sshd-effective.txt; done\n[[ ! -e "$r/sshd.pid" ]]\necho SP7_TEMPORARY_SSH_CONFIG_VALID_NO_SERVER_STARTED\necho SP7_LIVE_READONLY_PROBE_COMPLETE\nsync\npoweroff -f\n'
os.umask(0o077);w=pathlib.Path(__file__).resolve().parent;s=pathlib.Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/synthetic-secureboot-clonezilla-live-v2-vm');s.mkdir(mode=0o700)
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

# Exact public USB helper/config inputs. No backups or private keys in guest.
cmd([str(mt/'mmd'),'-i',str(efi),'::/SP7-DUALBOOT'],'mkdir-public-tools')
for n in ['MEDIA-ID.txt','enable-temporary-ssh.sh','bogebear.pub']:cp(w/'usb-overlay/SP7-DUALBOOT'/n,'SP7-DUALBOOT/'+n,'copy-public-'+n)
script=s/'sp7-vm-check.sh';script.write_text(VM_SCRIPT);cp(script,'sp7-vm-check.sh','copy-vm-only-probe')
cfg=s/'grub.cfg';actual=(w/'usb-overlay/EFI/Boot/grub.cfg').read_text();cfg.write_text('serial --unit=0 --speed=115200\nterminal_output serial\n'+actual.replace('nomodeset nosplash','nomodeset nosplash console=ttyS0,115200'))
cp(cfg,'EFI/BOOT/grub.cfg','copy-cfg')
(s/'menu-diagnostic-augmentation.json').write_text(json.dumps({'original_usb_menu_sha256':hashlib.sha256(actual.encode()).hexdigest(),'only_added_serial_console_for_observation':True})+'\n')
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
(s/'launch.json').write_text(json.dumps(a,indent=2)+'\n');start=time.monotonic();passed=False;console_sent=False;console_client=None;console=None
def qreply(f):
 while True:
  x=json.loads(f.readline())
  if 'return' in x or 'error' in x:return x
with (s/'qemu.log').open('xb') as log:
 p=subprocess.Popen(a,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
 try:
  while time.monotonic()-start<170:
   b=serial.read_bytes() if serial.exists() else b''
   if b'SP7_LIVE_SECURE_BOOT=1' in b and b'SP7_LIVE_READONLY_PROBE_COMPLETE' in b:passed=True;break
   if b'user@sp7-live:' in b and not console_sent:
    console_sent=True
    console='/tmp/sp7-live-v2-console-'+str(os.getpid())+'.sock'
    with socket.socket(socket.AF_UNIX) as c:
     c.settimeout(3);c.connect(str(sock));f=c.makefile('rwb',buffering=0);f.readline();f.write(b'{"execute":"qmp_capabilities"}\n');qreply(f)
     change={'execute':'chardev-change','arguments':{'id':'serial0','backend':{'type':'socket','data':{'addr':{'type':'unix','data':{'path':console}},'server':True,'wait':False,'logfile':str(serial),'logappend':True}}}}
     f.write(json.dumps(change).encode()+b'\n');assert 'return' in qreply(f)
    console_client=socket.socket(socket.AF_UNIX);console_client.settimeout(2);console_client.connect(console);console_client.sendall(b'\nsudo bash /run/live/medium/sp7-vm-check.sh\n')
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
  if console_client:console_client.close()
  if console and pathlib.Path(console).exists():pathlib.Path(console).unlink()
r={'schema':'sp7-vendor-signed-clonezilla-live-v1','passed':passed,'temporary_ssh_configuration_test':True,'network_server_started_in_vm':False,'vm_off':p.poll() is not None,'qemu_exit':p.returncode,'seconds':time.monotonic()-start,'no_network_host_mounts_user_backup_private_keys_or_passthrough':True,'physical_sp7_boot_tested':False,'no_extra_mok_keys_in_test':True};(s/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');(w/'secureboot-live-candidate/live-v2-vm-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True);raise SystemExit(0 if passed else 1)
