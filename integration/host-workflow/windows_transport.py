from pathlib import Path
import base64,subprocess
ROOT=Path('/srv/sp7-project/host')
KNOWN=ROOT/'work/sp7-windows-check-20261017/connection/known_hosts'
OPTIONS=['-F','/dev/null','-i','/home/sp7-user/.ssh/sp7_windows_20261017','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','PasswordAuthentication=no','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(KNOWN),'-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=4']
TARGET='bjorn@192.0.2.10'
def command(source):return ['ssh',*OPTIONS,TARGET,'powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(source.encode('utf-16le')).decode()]
def run(source,timeout=60):return subprocess.run(command(source),stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
