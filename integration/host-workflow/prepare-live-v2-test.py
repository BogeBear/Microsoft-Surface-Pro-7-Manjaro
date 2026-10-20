"""New USB configuration / temporary SSH configuration test; public-only VM."""
from pathlib import Path
w=Path(__file__).resolve().parent
s=(w/'test-secureboot-live.py').read_text().replace('clonezilla-live-v1-vm','clonezilla-live-v2-vm').replace("w/'secureboot-live-candidate/live-vm-receipt.json'","w/'secureboot-live-candidate/live-v2-vm-receipt.json'")
a=s.index("script=s/'sp7-vm-check.sh'");b=s.index("cmd(['sfdisk'",a)
block='''\n# Exact public USB helper/config inputs. No backups or private keys in guest.\ncmd([str(mt/'mmd'),'-i',str(efi),'::/SP7-DUALBOOT'],'mkdir-public-tools')\nfor n in ['MEDIA-ID.txt','enable-temporary-ssh.sh','bogebear.pub']:cp(w/'usb-overlay/SP7-DUALBOOT'/n,'SP7-DUALBOOT/'+n,'copy-public-'+n)\nscript=s/'sp7-vm-check.sh';script.write_text(VM_SCRIPT);cp(script,'sp7-vm-check.sh','copy-vm-only-probe')\ncfg=s/'grub.cfg';actual=(w/'usb-overlay/EFI/Boot/grub.cfg').read_text();cfg.write_text('serial --unit=0 --speed=115200\\nterminal_output serial\\n'+actual.replace('nomodeset nosplash','nomodeset nosplash console=ttyS0,115200'))\ncp(cfg,'EFI/BOOT/grub.cfg','copy-cfg')\n(s/'menu-diagnostic-augmentation.json').write_text(json.dumps({'original_usb_menu_sha256':hashlib.sha256(actual.encode()).hexdigest(),'only_added_serial_console_for_observation':True})+'\\n')\n'''
vm='''#!/bin/bash
set -euo pipefail
exec >/dev/ttyS0 2>&1
echo SP7_PUBLIC_LIVE_USERSPACE_READY
uname -r
mokutil --sb-state
cat /sys/kernel/security/lockdown
p=/run/live/medium/SP7-DUALBOOT
bash -n "$p/enable-temporary-ssh.sh"
set +e
sudo bash "$p/enable-temporary-ssh.sh" >/run/sp7-helper-negative.txt 2>&1
rc=$?
set -e
cat /run/sp7-helper-negative.txt
[[ $rc != 0 && ! -e /run/sp7-dualboot-ssh ]]
grep -q 'only for the Surface Pro 7' /run/sp7-helper-negative.txt
echo SP7_HELPER_NON_SURFACE_GUARD_PASS
r=/run/sp7-sshd-offline-test
install -d -m 0755 "$r" /run/sshd
ssh-keygen -q -t ed25519 -N '' -f "$r/host_key"
cp "$p/bogebear.pub" "$r/authorized_keys"
python3 - <<'END'
from pathlib import Path
s=Path('/run/live/medium/SP7-DUALBOOT/enable-temporary-ssh.sh').read_text()
s=s.split('cat >"$r/sshd_config" <<EOF\\n',1)[1].split('\\nEOF\\n',1)[0]
s=s.replace('$r','/run/sp7-sshd-offline-test').replace('$addr','127.0.0.1').replace('$peer','192.0.2.10')
Path('/run/sp7-sshd-offline-test/sshd_config').write_text(s+'\\n')
p=Path('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c')
print('SP7_LIVE_SECURE_BOOT='+str(p.read_bytes()[4]),flush=True)
END
/usr/sbin/sshd -t -f "$r/sshd_config"
/usr/sbin/sshd -T -f "$r/sshd_config" -C user=user,addr=192.0.2.10,host=bogebear >/run/sp7-sshd-effective.txt
for rule in 'port 2222' 'passwordauthentication no' 'kbdinteractiveauthentication no' 'permitrootlogin no' 'authenticationmethods publickey' 'allowusers user@192.0.2.10' 'allowtcpforwarding no' 'allowagentforwarding no'; do grep -Fxq "$rule" /run/sp7-sshd-effective.txt; done
[[ ! -e "$r/sshd.pid" ]]
echo SP7_TEMPORARY_SSH_CONFIG_VALID_NO_SERVER_STARTED
echo SP7_LIVE_READONLY_PROBE_COMPLETE
sync
poweroff -f
'''
s=s[:a]+block+s[b:]
s=s.replace("os.umask(0o077);w=",'VM_SCRIPT='+repr(vm)+"\nos.umask(0o077);w=")
# The real USB payload does not contain this test-only automatic terminal controller.
a=s.index('   if p.poll() is not None:break')
s=s[:a]+'''   if b'user@sp7-live:' in b and not console_sent:
    console_sent=True
    console='/tmp/sp7-live-v2-console-'+str(os.getpid())+'.sock'
    with socket.socket(socket.AF_UNIX) as c:
     c.settimeout(3);c.connect(str(sock));f=c.makefile('rwb',buffering=0);f.readline();f.write(b'{"execute":"qmp_capabilities"}\\n');qreply(f)
     change={'execute':'chardev-change','arguments':{'id':'serial0','backend':{'type':'socket','data':{'addr':{'type':'unix','data':{'path':console}},'server':True,'wait':False,'logfile':str(serial),'logappend':True}}}}
     f.write(json.dumps(change).encode()+b'\\n');assert 'return' in qreply(f)
    console_client=socket.socket(socket.AF_UNIX);console_client.settimeout(2);console_client.connect(console);console_client.sendall(b'\\nsudo bash /run/live/medium/sp7-vm-check.sh\\n')
'''+s[a:]
s=s.replace("start=time.monotonic();passed=False",'''start=time.monotonic();passed=False;console_sent=False;console_client=None;console=None
def qreply(f):
 while True:
  x=json.loads(f.readline())
  if 'return' in x or 'error' in x:return x''')
s=s.replace("  if sock.exists():sock.unlink()", "  if sock.exists():sock.unlink()\n  if console_client:console_client.close()\n  if console and pathlib.Path(console).exists():pathlib.Path(console).unlink()")
s=s.replace("'passed':passed,", "'passed':passed,'temporary_ssh_configuration_test':True,'network_server_started_in_vm':False,")
(w/'test-secureboot-live-v2.py').write_text(s)
