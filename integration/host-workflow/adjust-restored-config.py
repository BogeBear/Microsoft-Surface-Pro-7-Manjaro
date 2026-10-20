from pathlib import Path
import json,base64,hashlib,datetime
from live_transport import run_python
w=Path(__file__).resolve().parent
inv=json.loads((w/'restored-actual-inventory.json').read_text())
backup=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-live-20261019/restored-config-before-adjustment')
changes={}
checkpoint=next(k for k in inv['selected_files'] if k.endswith('/resume-state.json'))
for rel in ['@/etc/fstab',checkpoint]:
 m=inv['selected_files'][rel];old=base64.b64decode(m['base64']);assert hashlib.sha256((backup/rel).read_bytes()).hexdigest()==m['sha256']
 if rel.endswith('/fstab'):
  assert old.count(b'UUID=340E-0667')==1
  new=old.replace(b'UUID=340E-0667',b'UUID=9E39-0F59')
 else:
  j=json.loads(old);j.update(active=False,phase='dualboot_restored_awaiting_fresh_revalidation',hardware_tests_blocked_until_recovery=True,reviewed_presence_plan=None,heartbeat_status='disabled_pending_fresh_revalidation',user_presence='unknown_after_restore',camera_status_not_revalidated_after_login_reboot=True,next_step='Verify actual installed boot, Secure Boot, signed kernel, module/helper bindings and full camera idle state before any new sensor trial. Restore-era receipts and plans are historical, not fresh authorization.')
  if isinstance(j.get('pending_reboot'),dict):j['pending_reboot'].update(requested=False,retired_reason='Historical request retired on dualboot restoration; no automatic reboot permitted by this restored record.')
  j['dualboot_restore']={'host_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_checkpoint_sha256':m['sha256'],'previous_boot_id_is_historical':True,'physical_boot_not_yet_verified':True,'camera_auto_enablement_removed':True,'no_ir_started':True}
  new=(json.dumps(j,indent=2,ensure_ascii=False)+'\n').encode()
 changes[rel]={'before_sha256':m['sha256'],'data':base64.b64encode(new).decode(),'after_sha256':hashlib.sha256(new).hexdigest(),'uid':m['uid'],'gid':m['gid'],'mode':m['mode']}
menu=(w/'dualboot-config-candidate/sp7-dualboot.cfg').read_bytes();assert hashlib.sha256(menu).hexdigest()=='914eae107c4473fa3f00d2e49fb00f729dba890e509a33ab811dc0f18c644578'
links=[x for x in inv['enablement_links'] if 'sp7-camera' in x['path']];assert len(links)==2
payload={'changes':changes,'links':links,'menu':base64.b64encode(menu).decode(),'kernel':inv['kernel_files']['@/boot/vmlinuz-linux-surface']['sha256']}
(w/'config-adjustment-payload.json').write_text(json.dumps(payload,indent=2)+'\n')
(backup/'removed-enablement-links.json').write_text(json.dumps(links,indent=2)+'\n')
source=r'''import pathlib,json,subprocess,hashlib,base64,os
P=pathlib.Path
D=PAYLOAD
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='2f3101c2-bfa7-4518-8b0d-168f5a51b057'
assert json.loads(P('/run/sp7-dualboot-restore/status.json').read_text())['phase']=='restore_complete_unmounted'
assert subprocess.check_output(['blkid','-s','UUID','-o','value','/dev/nvme0n1p5'],text=True).strip()=='b7e9ce03-4b90-4c6a-8091-643c8c5879e5'
assert not subprocess.run(['findmnt','-rn','-S','/dev/nvme0n1p5'],capture_output=True,text=True).stdout.strip()
root=P('/run/sp7-config-adjust');root.mkdir(mode=0o700,exist_ok=True)
subprocess.run(['mount','-t','btrfs','-o','rw,subvolid=5','/dev/nvme0n1p5',str(root)],check=True)
r={'schema':'sp7-restored-config-adjustment-v1','changes':{},'removed_links':[],'complete':False};originals={};removed=[];created=[]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def atomic(p,b,uid,gid,mode):
 assert not p.is_symlink();q=p.with_name(p.name+'.dualboot-new');assert not q.exists() and not q.is_symlink()
 with q.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 os.chown(q,uid,gid);os.chmod(q,mode);os.replace(q,p)
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
try:
 for rel,m in D['changes'].items():
  p=root/rel;assert p.is_file() and not p.is_symlink() and sha(p)==m['before_sha256'],rel
  st=p.stat();assert (st.st_uid,st.st_gid,st.st_mode&0o777)==(m['uid'],m['gid'],m['mode']);originals[rel]=p.read_bytes()
 for x in D['links']:
  p=root/x['path'];assert p.is_symlink() and os.readlink(p)==x['target']
 kernel=root/'@/boot/vmlinuz-linux-surface';assert sha(kernel)==D['kernel']
 oldgrub=root/'@/boot/grub/grub.cfg';oldhash=sha(oldgrub)
 menu=root/'@/boot/grub/sp7-dualboot.cfg';assert not menu.exists() and not menu.is_symlink()
 P('/run/sp7-config-adjust-before.json').write_text(json.dumps({'originals':{k:base64.b64encode(v).decode() for k,v in originals.items()},'links':D['links']}))
 for rel,m in D['changes'].items():
  atomic(root/rel,base64.b64decode(m['data']),m['uid'],m['gid'],m['mode']);assert sha(root/rel)==m['after_sha256'];r['changes'][rel]={'before':m['before_sha256'],'after':sha(root/rel)}
 atomic(menu,base64.b64decode(D['menu']),0,0,0o644);created.append(menu)
 for x in D['links']:
  (root/x['path']).unlink();removed.append(x);r['removed_links'].append(x)
 assert sha(oldgrub)==oldhash
 assert all(not (root/x['path']).is_symlink() for x in removed)
 r.update(complete=True,old_root_grub_sha256_unchanged=oldhash,menu_sha256=sha(menu),kernel_sha256_unchanged=sha(kernel),fstab_efi_uuid='9E39-0F59',no_pam_or_wallet_changes=True,no_camera_or_ir_started=True)
except BaseException as e:
 r['error']=str(e);errors=[]
 for rel,b in originals.items():
  try:m=D['changes'][rel];atomic(root/rel,b,m['uid'],m['gid'],m['mode'])
  except BaseException as z:errors.append(str(z))
 for p in created:
  try:p.unlink()
  except BaseException as z:errors.append(str(z))
 for x in removed:
  try:(root/x['path']).symlink_to(x['target'])
  except BaseException as z:errors.append(str(z))
 r['rollback_errors']=errors
finally:
 subprocess.run(['sync','-f',str(root)],check=False)
 q=subprocess.run(['umount',str(root)],capture_output=True,text=True);r['unmount_exit']=q.returncode;r['unmount_stderr']=q.stderr
 P('/run/sp7-config-adjust-result.json').write_text(json.dumps(r))
print(json.dumps(r));raise SystemExit(0 if r['complete'] and r['unmount_exit']==0 else 1)
'''.replace('PAYLOAD',repr(payload))
(w/'config-adjustment-reviewed-remote.py').write_text(source)
if __name__=='__main__':
 import sys
 if '--apply' not in sys.argv:print('Prepared only; --apply is required.');raise SystemExit(0)
 assert not (w/'physical-config-adjustment.json').exists(),'Existing result; inspect, do not rerun blindly'
 r=run_python(source,timeout=90);(w/'physical-config-adjustment.json').write_text(json.dumps({'ssh_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr},indent=2)+'\n');print(r.stdout);assert r.returncode==0,r.stderr
