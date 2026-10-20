#!/bin/bash
set -euo pipefail
exec >/dev/ttyS0 2>&1
trap 'echo SP7_WIFI_TEST_FINISHED; sync; poweroff -f' EXIT
p=/run/live/medium/SP7-DUALBOOT
python3 - <<'PY'
from pathlib import Path
import hashlib
p=Path('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c')
assert p.read_bytes()[4] == 1
print('SP7_SECURE_BOOT_PASS',flush=True)
f=Path('/usr/lib/firmware/iwlwifi-Qu-c0-hr-b0-77.ucode')
assert hashlib.sha256(f.read_bytes()).hexdigest()=='5b3fba7570cff075b26131c606ac2848f4a7251abbcaf48df6cffbe43236e628'
assert f.stat().st_uid==0 and f.stat().st_mode & 0o777==0o644
print('SP7_FIRMWARE_OVERLAY_PASS',flush=True)
PY
systemctl is-active --quiet NetworkManager
echo SP7_NETWORKMANAGER_AUTO_START_PASS
set +e
bash "$p/enable-temporary-ssh.sh" >/run/helper-negative.txt 2>&1
rc=$?
set -e
[[ $rc != 0 && ! -e /run/sp7-dualboot-ssh ]]
grep -q 'only for the Surface Pro 7' /run/helper-negative.txt
echo SP7_HELPER_NON_SURFACE_GUARD_PASS
r=/run/sp7-sshd-offline-test
install -d -m 0755 "$r" /run/sshd
ssh-keygen -q -t ed25519 -N '' -f "$r/host_key"
cp "$p/bogebear.pub" "$r/authorized_keys"
python3 - <<'PY'
from pathlib import Path
lines=Path('/run/live/medium/SP7-DUALBOOT/enable-temporary-ssh.sh').read_text().splitlines()
a=lines.index('cat >"$r/sshd_config" <<EOF')+1
b=lines.index('EOF',a)
s='\n'.join(lines[a:b])+'\n'
s=s.replace('$r','/run/sp7-sshd-offline-test').replace('$addr','127.0.0.1').replace('$peer','192.0.2.10')
Path('/run/sp7-sshd-offline-test/sshd_config').write_text(s)
PY
/usr/sbin/sshd -t -f "$r/sshd_config"
/usr/sbin/sshd -T -f "$r/sshd_config" -C user=user,addr=192.0.2.10,host=bogebear | tr '[:upper:]' '[:lower:]' >"$r/effective.txt"
for rule in 'port 2222' 'passwordauthentication no' 'kbdinteractiveauthentication no' 'permitrootlogin no' 'authenticationmethods publickey' 'allowusers user@192.0.2.10' 'allowtcpforwarding no' 'allowstreamlocalforwarding no' 'allowagentforwarding no' 'permituserrc no'; do
 grep -Fxq "$rule" "$r/effective.txt"
done
echo SP7_SSH_CONFIG_RESTRICTIONS_PASS
/usr/sbin/sshd -f "$r/sshd_config" -E "$r/sshd.log"
ready=no
for attempt in {1..20}; do
 if [[ -s $r/sshd.pid ]]; then
  pid=$(cat "$r/sshd.pid")
  if [[ $pid =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null && [[ $(readlink -f "/proc/$pid/exe") == /usr/sbin/sshd ]]; then
   listener=$(ss -H -ltnp 'sport = :2222')
   if [[ $listener == *"127.0.0.1:2222"* && $listener == *"pid=$pid,"* ]]; then ready=yes; break; fi
  fi
 fi
 sleep 0.1
done
[[ $ready == yes ]]
echo SP7_SSH_LOOPBACK_STARTUP_CHECK_PASS
kill "$pid"
for attempt in {1..20}; do
 [[ -z $(ss -H -ltn 'sport = :2222') ]] && break
 sleep 0.1
done
[[ -z $(ss -H -ltn 'sport = :2222') ]]
echo SP7_SSH_LOOPBACK_STOP_PASS
echo SP7_WIFI_UPDATE_VM_COMPLETE
