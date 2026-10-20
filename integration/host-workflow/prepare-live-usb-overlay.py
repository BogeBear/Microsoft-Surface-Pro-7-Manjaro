"""Prepare public-only, inactive additive USB payload. Does not write USB."""
from pathlib import Path
import shutil,zipfile,json,hashlib,subprocess
w=Path(__file__).resolve().parent;o=w/'usb-overlay';o.mkdir(exist_ok=False)
for d in ['EFI/Boot','live','SP7-DUALBOOT/certificates']:(o/d).mkdir(parents=True)
for src,dst in [('shimx64.efi','bootx64.efi'),('debian-grub-2.14-4.efi','grubx64.efi'),('mmx64.efi','mmx64.efi')]:shutil.copyfile(w/'secureboot-candidate'/src,o/'EFI/Boot'/dst)
shutil.copyfile(w/'secureboot-candidate/surface.cer',o/'SP7-DUALBOOT/certificates/surface.cer')
with zipfile.ZipFile('/mnt/sp7-backup/BACKUP/rescue-media-20261014/clonezilla-live-3.3.3-37-amd64.zip') as z:
 for n in ['vmlinuz','initrd.img','filesystem.squashfs','Clonezilla-Live-Version']:
  with z.open('live/'+n) as src,(o/'live'/n).open('xb') as dst:shutil.copyfileobj(src,dst)
pub=Path('/home/sp7-user/.ssh/sp7_windows_20261017.pub').read_text();assert pub.startswith('ssh-ed25519 ') and 'PRIVATE' not in pub
(o/'SP7-DUALBOOT/bogebear.pub').write_text(pub)
(o/'SP7-DUALBOOT/MEDIA-ID.txt').write_text('SP7 additive signed live environment 20261019; no automated partition/restore actions.\n')
(o/'EFI/Boot/grub.cfg').write_text('''set default=0
set timeout=20
menuentry 'SP7 Linux live - ingen automatisk aterstallning' {
 search --set=root -f /SP7-DUALBOOT/MEDIA-ID.txt
 linux /live/vmlinuz boot=live union=overlay username=user config components hostname=sp7-live noswap noeject noprompt locales=en_US.UTF-8 keyboard-layouts=se ocs_live_run="bash" ocs_live_batch=no nomodeset nosplash
 initrd /live/initrd.img
}
menuentry 'Windows Surface recovery - befintliga filer pa USB' {
 search --set=root -f /SP7-DUALBOOT/MEDIA-ID.txt
 chainloader /EFI/Microsoft/Boot/bootmgfw.efi
}
menuentry 'Windows 11 - intern disk' {
 search --no-floppy --fs-uuid --set=root 9E39-0F59
 chainloader /EFI/Microsoft/Boot/bootmgfw.efi
}
menuentry 'MOK Manager - manuell registrering av offentligt certifikat' {
 search --set=root -f /SP7-DUALBOOT/MEDIA-ID.txt
 chainloader /EFI/Boot/mmx64.efi
}
''')
(o/'SP7-DUALBOOT/enable-temporary-ssh.sh').write_text('''#!/bin/bash
# Human-triggered only. No partition, filesystem, firmware, camera or IR operations.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo from the live environment.'; exit 1; }
grep -qw 'boot=live' /proc/cmdline || { echo 'STOP: not a live boot.'; exit 1; }
[[ $(findmnt -n -o FSTYPE /) == overlay ]] || { echo 'STOP: root is not a volatile live overlay.'; exit 1; }
[[ $(cat /sys/class/dmi/id/product_name) == 'Surface Pro 7' ]] || { echo 'STOP: this helper is only for the Surface Pro 7.'; exit 1; }
medium=$(dirname -- "$(readlink -f -- "$0")")
[[ -f "$medium/MEDIA-ID.txt" && -f "$medium/bogebear.pub" ]] || exit 1
# The known local host only; not a public internet listener or password login.
peer=192.0.2.10
addr=$(ip -j -4 route get "$peer" | python3 -c 'import sys,json,ipaddress;x=json.load(sys.stdin);a=x[0].get("prefsrc","");ipaddress.IPv4Address(a);print(a)')
[[ $addr == 192.168.1.* ]] || { echo 'STOP: expected the existing private LAN.'; exit 1; }
r=/run/sp7-dualboot-ssh
[[ ! -e $r ]] || { echo 'STOP: temporary server directory already exists.'; exit 1; }
install -d -m 0755 "$r"
install -m 0644 "$medium/bogebear.pub" "$r/authorized_keys"
ssh-keygen -q -t ed25519 -N '' -f "$r/host_key"
install -d -m 0755 /run/sshd
cat >"$r/sshd_config" <<EOF
Port 2222
ListenAddress $addr
HostKey $r/host_key
PidFile $r/sshd.pid
AuthorizedKeysFile $r/authorized_keys
AllowUsers user@$peer
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AuthenticationMethods publickey
UsePAM yes
StrictModes yes
AllowAgentForwarding no
AllowTcpForwarding no
X11Forwarding no
PermitTunnel no
Subsystem sftp internal-sftp
LogLevel INFO
EOF
/usr/sbin/sshd -t -f "$r/sshd_config"
/usr/sbin/sshd -f "$r/sshd_config" -E "$r/sshd.log"
printf '\\nTemporary project SSH: user@%s port 2222\\n' "$addr"
ssh-keygen -lf "$r/host_key.pub"
echo 'Host key above is PUBLIC. Send its fingerprint for verification.'
echo 'No internal partition has been mounted or changed by this helper.'
echo 'All temporary server state is in RAM and disappears on shutdown.'
''')
(o/'SP7-DUALBOOT/LAS-MIG.txt').write_text('''SP7 dualboot - stegvis live-start, ingen automatisk installation

Secure Boot ska vara fortsatt aktiverat (Microsoft och Third Party).
USB-menyn erbjuder Linux live, befintlig Windows-aterstallning och intern Windows.
Ingen partitionering, aterstallning, kamerastart eller certifikatregistrering
utforas automatiskt. USB innehaller bara offentligt certifikat och SSH-publiknyckel.

Efter Linuxstart: valj skal/kommandotolk om Clonezilla visar en meny.
Anslut befintligt wifi med nmtui. Skriv aldrig wifi- eller BitLockerlosenord i chatten.
Om wifi inte visas: stanna och rapportera; andra drivrutinsandringar gor vi efter status.
Nar natverket fungerar kan anvandaren sjalv starta projektets tillfalliga SSH:
 sudo bash /run/live/medium/SP7-DUALBOOT/enable-temporary-ssh.sh
Om mediet sitter under /lib/live/mount/medium: anvand den sokvagen istallet.
Hjalparen kraver faktisk Surface Pro 7, live-boot och RAM-overlay. Den skapar
bara serverfiler i /run, anvander publiknyckel och tillater bara development-host
pa 192.0.2.10. Den ger inga nya permanenta sudo- eller autostartregler.
Visa dess publika hostkey-fingeravtryck sa att anslutningen kan verifieras.
Aktivera inte andra SSH-servrar som reservvag.

Fysisk krympning/aterstallning kraver separat genomgang av den exakta diskplanen.
Anvand INTE originalbackupens hel-disk-GPT/partition-prefix: de skulle skriva over Windows.
USB:s ursprungliga EFI-filer ar hashverifierat bevarade i anvandarens BACKUP-mapp.
Windows/EFI/MSR/WinRE pa SP7 har inte andrats av denna USB-forberedelse.

Signerad start av Surface-karnan kraver senare fysisk registrering av surface.cer.
Ingen registrering gors automatiskt. Backupens karnmodulpolicy ar oforandrad:
Secure Boot i firmware innebar inte att den karnan blockerar osignerade moduler.
Detta paket pastar inte verifierad biometri, PAD eller fysisk IR-funktion.
''')
subprocess.run(['bash','-n',str(o/'SP7-DUALBOOT/enable-temporary-ssh.sh')],check=True)
manifest=[]
for p in sorted(o.rglob('*')):
 if p.is_file():manifest.append({'path':str(p.relative_to(o)),'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()})
(w/'usb-overlay-manifest.json').write_text(json.dumps({'schema':'sp7-additive-live-usb-overlay-v1','inactive_until_copied':True,'usb_serial':'072128E995155590','usb_uuid':'C48C-B988','private_key_included':False,'writes_partitions_or_internal_disks':False,'windows_recovery_files_preserved':True,'original_efi_backup':'/mnt/sp7-backup/BACKUP/SP7-USB-before-dualboot-20261019','files':manifest},indent=2)+'\n');print('Prepared',len(manifest),'files;',sum(x['bytes'] for x in manifest),'bytes; USB unchanged')
