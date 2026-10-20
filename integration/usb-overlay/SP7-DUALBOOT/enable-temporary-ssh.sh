#!/bin/bash
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
printf '\nTemporary project SSH: user@%s port 2222\n' "$addr"
ssh-keygen -lf "$r/host_key.pub"
echo 'Host key above is PUBLIC. Send its fingerprint for verification.'
echo 'No internal partition has been mounted or changed by this helper.'
echo 'All temporary server state is in RAM and disappears on shutdown.'
