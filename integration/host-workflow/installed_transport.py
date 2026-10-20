from pathlib import Path
import subprocess
W=Path(__file__).resolve().parent
BASE=['ssh','-F','/dev/null','-i','/home/sp7-user/Documents/Codex/2026-09-30/ok/work/sp7_transfer_key','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','StrictHostKeyChecking=yes','-o','HostKeyAlgorithms=ssh-ed25519','-o','UserKnownHostsFile='+str(W/'live-connection/known_hosts-restored-manjaro'),'-o','ConnectTimeout=8','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','sp7-user@192.0.2.10']
def run_python(source,timeout=60):
 return subprocess.run([*BASE,'python3 -'],input=source,text=True,capture_output=True,timeout=timeout)
