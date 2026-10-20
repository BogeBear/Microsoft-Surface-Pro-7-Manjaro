from pathlib import Path
import json,hashlib,datetime
w=Path(__file__).resolve().parent;c=w/'readable-grub-candidate';b=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/readable-grub-20261019')
menu=(c/'grub-built-in.cfg').read_bytes();h=hashlib.sha256(menu).hexdigest();v=json.loads((c/'built-in-vm-receipt.json').read_text());p=json.loads((c/'physical-verification.json').read_text());assert v['passed'] and v['vm_off'] and v['menu_sha256']==p['menu_sha256']==h
r={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'installed':True,'menu_sha256':h,'file':'EFI/SP7Manjaro/grub.cfg','preferred_graphics_mode':'800x600','fallback_graphics_modes':['1024x768','auto'],'font':'signed GRUB built-in fallback font; external fonts not deployed','menu_choices':['Windows 11','Manjaro - kontrollstart (textlage)','Manjaro - skrivbord'],'control_entry_preserved_without_graphical_startup':True,'all_os_entry_commands_unchanged':True,'windows_default':True,'timeout_seconds':12,'secure_boot_kept_enabled':True,'bitlocker_protection_on':True,'only_own_grub_cfg_modified':True,'no_font_theme_or_other_asset_installed':True,'original_menu_backup':'grub.cfg.before','local_graphical_vm_passed_and_off':True,'physical_surface_visual_confirmation_pending':True,'no_restart_or_camera_use_performed':True,'test_findings':['External PF2 font loading rejected by Secure Boot; candidate not installed.','all_video module is not embedded; omitted to avoid loading old external modules.','Custom theme trial did not reach its menu; rejected and not installed.','Final simple gfxterm candidate rendered at 800x600 with signed built-in modules, no reported startup errors. Built-in fallback font has limited decorative glyphs; OS option text readable.']}
(c/'READABILITY-INSTALLED.json').write_text(json.dumps(r,indent=2)+'\n');(b/'READABILITY-INSTALLED.json').write_text(json.dumps(r,indent=2)+'\n');(b/'grub.cfg.installed').write_bytes(menu);(b/'vm-verified.json').write_text(json.dumps(v,indent=2)+'\n')
p=w/'CURRENT-WORK.json';j=json.loads(p.read_text());j.update(updated_utc=r['host_utc'],active_grub_menu_sha256=h,active_grub_menu_path=r['file'],grub_readability='readable-grub-candidate/READABILITY-INSTALLED.json',grub_readability_visual_confirmation_pending=True,user_action_requested='When SP7 is cool by user assessment, restart and choose Manjaro - skrivbord; larger GRUB appearance can be checked on the way.',physical_phase='dualboot_functional_readable_grub_installed_awaiting_manjaro_for_ir_revalidation',pending=['User next restart: verify larger GRUB appearance and boot Manjaro for IR continuation','Read fresh installed Manjaro checkpoint, loaded module/helper versions and full camera idle state before preparing next IR trial']);p.write_text(json.dumps(j,indent=2,ensure_ascii=False)+'\n')
m={}
for f in b.iterdir():
 if f.is_file() and f.name!='SHA256.json':m[f.name]={'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
(b/'SHA256.json').write_text(json.dumps(m,indent=2)+'\n')
with (w.parent.parent/'AGENTS.md').open('a') as f:f.write('''
GRUB LÄSBARHETSÄNDRING installerad2026-10-19 på användarorder, fortfarandeWindows:
EndastEFI/SP7Manjaro/grub.cfg ändrad,1373bytes, nySHA7504aeadd0fe26e022e97e3f922b7bac4c46d8250a354591158d2f3fec7715f1.
800x600 första grafikläge,1024x768/auto reserv, gfxterm med signerade inbyggda
moduler/font. Alla OSentry-kommandon identiska med fysiskt fungerandeversionen.
Windowsdefault12sek kvar. Kontrollstarten finns KVAR; bara kortad rubrik till
Manjaro - kontrollstart (textlage), fortfarande systemd.unit=multi-user.target.
Manjaro - skrivbord kvar. Ingen font/themeasset faktiskt installerad påSP7.
SecureBoottrue/BitLockerOn efterwrite. Alla andra läsbaraEFIfiler oförändrade;
BCD/BCD.LOG fortsattWinlåsta fördirektråhash, aldrigskrivmål. Windowsdata/
firmware/partitioner/PAM/KWallet oförändrade. Ingenomstart ellerkamerastart.
Originalmeny+slutkvittens iBACKUP/SP7-dualboot-live-20261019/readable-grub-20261019.

Lokaltgrafikprov SecureBootVMoff: final enkelgfxterm renderade800x600 utan
uppstartsfel; fysiskaSurfacebilden återstår. Inbyggdfont har begränsade dekorativa
ram-/pilsymboler, textvalen är läsbara. Tidigare32pxexternPF2 avvisades av
SecureBoot föreinstallation, all_video utelämnad dåexternmodul saknas, separat
customthemeförsök nåddeintemeny och är EJ installerat. Kör inte dessa felande
kandidater skarpt. Slutfil grub-built-in.cfg och READABILITY-INSTALLED.json i
work/sp7-dualboot-20261019/readable-grub-candidate; built-in-vm-receipt.json PASS.
Användaren har informerats att kontrollstarten bara fått kortare namn.
Nästa användarsteg: närsval enligtmanuellregel, väljManjaro-skrivbord och
meddela närLinuxärigång; därefterfärskcheckpoint/drivrutiner/fullidle införIR.
''')
print('Readable menu installed, rollback original preserved in BACKUP. No SP7 restart.')
