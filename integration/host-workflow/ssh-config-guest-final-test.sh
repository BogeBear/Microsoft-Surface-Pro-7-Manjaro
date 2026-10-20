#!/bin/bash
set -euo pipefail
exec >/dev/ttyS0 2>&1
p=/run/live/medium/SP7-DUALBOOT
set +e
bash "$p/enable-temporary-ssh.sh" >/run/helper-negative.txt 2>&1
code=$?
set -e
[[ $code != 0 && ! -e /run/sp7-dualboot-ssh ]]
grep -q 'only for the Surface Pro 7' /run/helper-negative.txt
echo SP7_HELPER_NON_SURFACE_GUARD_PASS
r=/run/sp7-sshd-offline-test
install -d -m 0755 "$r" /run/sshd
ssh-keygen -q -t ed25519 -N '' -f "$r/host_key"
cp "$p/bogebear.pub" "$r/authorized_keys"
python3 - <<'END'
from pathlib import Path
lines=Path('/run/live/medium/SP7-DUALBOOT/enable-temporary-ssh.sh').read_text().splitlines()
a=lines.index('cat >"$r/sshd_config" <<EOF')+1
b=lines.index('EOF',a)
s=chr(10).join(lines[a:b])+chr(10)
s=s.replace('$r','/run/sp7-sshd-offline-test').replace('$addr','127.0.0.1').replace('$peer','192.0.2.10')
Path('/run/sp7-sshd-offline-test/sshd_config').write_text(s)
p=Path('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c')
print('SP7_LIVE_SECURE_BOOT='+str(p.read_bytes()[4]),flush=True)
END
/usr/sbin/sshd -t -f "$r/sshd_config"
echo SP7_SSHD_SYNTAX_PASS
/usr/sbin/sshd -T -f "$r/sshd_config" -C user=user,addr=192.0.2.10,host=bogebear >"$r/effective.txt"
fail=0
for rule in 'port 2222' 'passwordauthentication no' 'kbdinteractiveauthentication no' 'permitrootlogin no' 'authenticationmethods publickey' 'allowusers user@192.0.2.10' 'allowtcpforwarding no' 'allowagentforwarding no'; do
 if grep -Fxq "$rule" "$r/effective.txt"; then echo "PASS: $rule"; else echo "FAIL: $rule"; fail=1; fi
done
grep -E '^(port|passwordauthentication|kbdinteractiveauthentication|permitrootlogin|authenticationmethods|allowusers|allowtcpforwarding|allowagentforwarding)' "$r/effective.txt"
[[ ! -e "$r/sshd.pid" && ! -e /run/sp7-dualboot-ssh ]]
if [[ $fail == 0 ]]; then echo SP7_TEMPORARY_SSH_CONFIG_VALID_NO_SERVER_STARTED; fi
echo SP7_CONFIG_TEST_DONE
sync
poweroff -f
