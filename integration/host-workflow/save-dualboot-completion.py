from pathlib import Path
import json,hashlib,datetime
w=Path(__file__).resolve().parent;b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/completion');b.mkdir(mode=0o700,parents=True,exist_ok=True)
names=['DUALBOOT-COMPLETE.json','windows-after-grub-boot-audit.json','windows-after-grub-boot-details.json','windows-current-bitlocker-events.json','installed-first-boot-verification.json','desktop-user-confirmed.json'];m={}
for n in names:
 d=(w/n).read_bytes();(b/n).write_bytes(d);assert (b/n).read_bytes()==d;m[n]={'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}
p=w/'CURRENT-WORK.json';j=json.loads(p.read_text());j['completion_backup_saved']=str(b);j['completion_backup_saved_host_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();p.write_text(json.dumps(j,indent=2,ensure_ascii=False)+'\n');d=p.read_bytes();(b/p.name).write_bytes(d);m[p.name]={'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()};(b/'SHA256.json').write_text(json.dumps(m,indent=2)+'\n')
a=w.parent.parent/'AGENTS.md';marker='DUALBOOT FUNKTIONELLT VERIFIERAD2026-10-19 efter användarens verkliga startprov:'
if marker not in a.read_text():
 with a.open('a') as f:f.write('''
DUALBOOT FUNKTIONELLT VERIFIERAD2026-10-19 efter användarens verkliga startprov:
Windows startar nu även från korrigeradeGRUBmenyn, SSHpå; användaren rapporterar
BitLockeråterställning, nyPIN och återaktiveradansiktsinloggning. ReadonlySSHaudit
Windowsboot02:44:36.500UTC: SecureBoottrue, BitLocker100procent FullyEncrypted/
ProtectionOn, TPMpresent/ready/enabled/activated/owned, ingenTPMrestartpending.
Disk/CHealthy, CNOTDirty och cirka63GiBfritt. Alla fempartitionersGUID/offset/
storlek matchar exaktgodkändplan. Inga problem blandanslutnaPnPenheter;
IntelAVStreamkamera, Helloenhet ochwifiOK. SSH/WbioSrvc/Winmgmtrunning.
IngenCBSRebootPending. BCDbootmgr/current/firmware läsbara; signeradManjaro
startpost fortfarande först. AktivEFIgrub.cfg SHAa6d646f016c845c1e0827bc6b291c0267a7b8b909710941c8f124ead4c114917.

Två verkligaSystemfel vidboot+1.6s: BitLocker-Driver24641, record6909/6910:
'Oväntat fel ... när BitLocker-volymens huvudnyckel hämtades under omstarten.'
Dessa är förenliga med användarens rapporterade återställning, men exaktorsak
bevisas inte avtexten. Aktuellstatus är fullt skyddad; inga andraSystemcritical/
errorhändelser sedanboot i fullständigloggläsning. Ingen extraomstart behövs
nu; observera omnyckelfrågan återkommer vidnästa vanligaWindowsstart.
PIN/ansiktsautentisering har INTE testats fjärrvägen; endast användarens
återaktivering plusenhets-/tjänststatus. Inga kameror/biometriska bilder/
nycklar fångade och inga Windowsändringar elleromstarter gjorda i slutkontrollen.
Manjaro hade fysiskGUIstart innanWindowsmenyfixen; Linuxentrys i senasteEFI
menyn är identiska. Detta är dualbootslutkvitto, INTE IR-funktionsverifiering.
IRnästa steg kräver färskManjarocheckpoint/modul-/hjälparbindning och fullidle.
Kör inte om återställning, GPTappend eller gamlaGRUB-install. NuvarandeSP7OS
ärWindows och förblirigång. DUALBOOT-COMPLETE.json och Windowsaudit iwork;
slutkvitton ochSHA256 äveni användarens BACKUP/SP7-dualboot-live-20261019/completion.
Tidigarepartition-/Windows-/Manjarobackuper, frystaoriginal och lokaltestVMoff bevarade.
''')
print('Completion receipts written and readback-verified in BACKUP. No SP7 modification or restart.')
