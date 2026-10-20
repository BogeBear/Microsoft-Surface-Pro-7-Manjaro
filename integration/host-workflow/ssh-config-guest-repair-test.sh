#!/bin/bash
set -euo pipefail
exec >/dev/ttyS0 2>&1
python3 - <<'END'
from pathlib import Path
lines=Path('/run/live/medium/SP7-DUALBOOT/enable-temporary-ssh.sh').read_text().splitlines()
start=lines.index('cat >"$r/sshd_config" <<EOF')+1
end=lines.index('EOF',start)
s=chr(10).join(lines[start:end])+chr(10)
s=s.replace('$r','/run/sp7-sshd-offline-test').replace('$addr','127.0.0.1').replace('$peer','192.0.2.10')
Path('/run/sp7-sshd-offline-test/sshd_config').write_text(s)
p=Path('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c')
print('SP7_LIVE_SECURE_BOOT='+str(p.read_bytes()[4]),flush=True)
END
r=/run/sp7-sshd-offline-test
/usr/sbin/sshd -t -f "$r/sshd_config"
/usr/sbin/sshd -T -f "$r/sshd_config" -C user=user,addr=192.0.2.10,host=bogebear >/run/sp7-sshd-effective.txt
for rule in 'port 2222' 'passwordauthentication no' 'kbdinteractiveauthentication no' 'permitrootlogin no' 'authenticationmethods publickey' 'allowusers user@192.0.2.10' 'allowtcpforwarding no' 'allowagentforwarding no'; do grep -Fxq "$rule" /run/sp7-sshd-effective.txt; done
[[ ! -e "$r/sshd.pid" && ! -e /run/sp7-dualboot-ssh ]]
echo SP7_TEMPORARY_SSH_CONFIG_VALID_NO_SERVER_STARTED
echo SP7_LIVE_READONLY_PROBE_COMPLETE
poweroff -f
