"""User-authorized full shutdown, after fresh independent thermal/identity checks."""
from pathlib import Path
import base64, datetime, gzip, json, subprocess, sys, time
from windows_transport import command, run

w = Path(__file__).resolve().parent
series = json.loads((w/'preboot-temperature-series.json').read_text())
if not series.get('complete') or time.time()-series['started_epoch'] >= 120:
    subprocess.run([sys.executable, str(w/'collect-preboot-temperatures.py')], check=True)
    series = json.loads((w/'preboot-temperature-series.json').read_text())
assert series['complete'] and time.time()-series['started_epoch'] < 180
boot = series['metadata']['BootUtc']
reader = (w/'Read-HWiNFO-Temperatures.ps1').read_text()
source = r"""
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ne 'BOGEBEARSP7'){throw 'Unexpected computer'}
$boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
if($boot -ne '__BOOT__'){throw 'Windows boot changed'}
$ac=@(Get-CimInstance -Namespace root\WMI BatteryStatus|ForEach-Object {$_.PowerOnline})
if($ac.Count -lt 1 -or @($ac|Where-Object {$_ -ne $true}).Count){throw 'External power not confirmed'}
if(@(Get-Disk|Where-Object {$_.BusType -eq 'USB' -and $_.FriendlyName -eq 'Verbatim STORE N GO' -and $_.Size -eq 31042043904}).Count -ne 1){throw 'USB disk binding failed'}
if(@(Get-CimInstance Win32_DiskDrive|Where-Object {$_.InterfaceType -eq 'USB' -and $_.PNPDeviceID -like '*\072128E995155590&0'}).Count -ne 1){throw 'USB PnP binding failed'}
if(@(Get-CimInstance Win32_LogicalDisk|Where-Object {$_.DriveType -eq 2 -and $_.VolumeSerialNumber -eq 'C48CB988' -and $_.FileSystem -eq 'FAT32'}).Count -ne 1){throw 'USB filesystem binding failed'}
$t=(& { __READER__ })|ConvertFrom-Json
if($t.CompletePackageAndFourCores -ne $true -or $t.StrictlyBelow60 -ne $true -or $t.PollUnixSeconds -le __LASTPOLL__){throw 'Final fresh temperature guard blocked shutdown'}
[pscustomobject]@{Schema='sp7-full-shutdown-final-guard-v1';BootUtc=$boot;GuardPassed=$true;Temperature=$t;Action='shutdown.exe /s /t 0';InternalPartitionsChanged=$false}|ConvertTo-Json -Depth 7 -Compress
[Console]::Out.Flush()
& shutdown.exe /s /t 0
if($LASTEXITCODE -ne 0){throw 'Windows rejected shutdown request'}
Write-Output 'SP7_FULL_SHUTDOWN_REQUEST_ACCEPTED'
""".replace('__BOOT__',boot).replace('__READER__',reader).replace('__LASTPOLL__',str(series['samples'][-1]['PollUnixSeconds']))
time.sleep(2.3)
ps="$s=[Console]::In.ReadToEnd(); & ([scriptblock]::Create($s))"
assert len(command(ps)[-1]) < 7800
r=subprocess.run(command(ps),input=source,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'physical_power_off_observed':False}
(w/'full-shutdown-request.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(r.stdout,flush=True)
if r.returncode: print(r.stderr,flush=True)
assert '"GuardPassed":true' in r.stdout, 'No successful final guard receipt; do not claim shutdown'
print('Final guard passed. Shutdown request sent; physical off still needs observation.',flush=True)
