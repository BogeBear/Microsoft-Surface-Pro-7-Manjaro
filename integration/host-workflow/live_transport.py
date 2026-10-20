from pathlib import Path
import subprocess
W=Path(__file__).resolve().parent
BASE=['ssh','-F','/dev/null','-i','/home/sp7-user/.ssh/sp7_windows_20261017','-p','2222','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(W/'live-connection/known_hosts-live2'),'-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=4','user@192.0.2.10']
def run_python(source,timeout=60):
 return subprocess.run([*BASE,'sudo -n python3 -'],input=source,text=True,capture_output=True,timeout=timeout)
