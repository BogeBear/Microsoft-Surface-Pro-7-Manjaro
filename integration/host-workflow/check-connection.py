import json
from pathlib import Path
from windows_transport import run
code=r'''$ErrorActionPreference='Stop';[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false);if($env:COMPUTERNAME -ne 'BOGEBEARSP7'){throw 'Wrong computer'};[pscustomobject]@{Computer=$env:COMPUTERNAME;Profile=$env:USERPROFILE;SecureBoot=(Confirm-SecureBootUEFI);CFree=(Get-Volume -DriveLetter C).SizeRemaining;Administrator=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);Boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime;PendingCBS=(Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending')}|ConvertTo-Json -Compress'''
r=run(code);print(r.stdout,r.stderr);r.check_returncode();Path('work/sp7-dualboot-20261019/connection-restored.json').write_text(json.dumps(json.loads(r.stdout.lstrip('\ufeff')),indent=2)+'\n')
