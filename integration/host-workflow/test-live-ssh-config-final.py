from pathlib import Path
import os,json,subprocess,time,selectors,base64,shutil
os.umask(0o077);w=Path(__file__).resolve().parent;s=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/synthetic-secureboot-clonezilla-ssh-final-v4-vm');s.mkdir(mode=0o700)
old=s.parent/'synthetic-secureboot-clonezilla-live-v3-vm';a=json.loads((old/'launch.json').read_text());disk=old/'public-live-gpt.raw';assert disk.is_file()
vars=s/'OVMF_VARS.fd';shutil.copyfile(old/'OVMF_VARS.fd',vars)
for i,v in enumerate(a):
 if v=='file:'+str(old/'serial.log'):raise AssertionError('Unexpected old serial backend')
 if v.startswith('if=pflash,format=raw,file='):a[i]='if=pflash,format=raw,file='+str(vars)
 if v.startswith('if=none,id=synthetic,format=raw,file='):a[i]=v+',readonly=on'
 if v=='-qmp':a[i+1]='unix:/tmp/sp7-ssh-v4-'+str(os.getpid())+'.sock,server=on,wait=off'
sock=Path(a[a.index('-qmp')+1].split(',')[0][5:]);(s/'launch.json').write_text(json.dumps(a,indent=2)+'\n')
b=base64.b64encode((w/'ssh-config-guest-final-test.sh').read_bytes()).decode();command="stty -echo; printf '%s' '"+b+"' | base64 -d | sudo bash\n";seen=bytearray();sent=False;start=time.monotonic()
with (s/'serial.log').open('xb') as out,(s/'qemu.log').open('xb') as err:
 p=subprocess.Popen(a,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err);sel=selectors.DefaultSelector();sel.register(p.stdout,selectors.EVENT_READ)
 try:
  while time.monotonic()-start<110:
   for key,ev in sel.select(.25):
    d=os.read(key.fileobj.fileno(),65536)
    if d:seen+=d;out.write(d);out.flush()
   if b'user@sp7-live:~$ ' in seen and not sent:
    sent=True;time.sleep(.5);p.stdin.write(command.encode());p.stdin.flush()
   if b'SP7_CONFIG_TEST_DONE' in seen or p.poll() is not None:break
 finally:
  sel.close()
  try:p.wait(timeout=8)
  except subprocess.TimeoutExpired:p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  if sock.exists():sock.unlink()
passed=all(x in seen for x in [b'SP7_LIVE_SECURE_BOOT=1',b'SP7_SSHD_SYNTAX_PASS',b'SP7_HELPER_NON_SURFACE_GUARD_PASS',b'SP7_TEMPORARY_SSH_CONFIG_VALID_NO_SERVER_STARTED'])
r={'schema':'sp7-live-usb-ssh-configuration-v1','passed':passed,'vm_off':p.poll() is not None,'qemu_exit':p.returncode,'seconds':time.monotonic()-start,'existing_public_fixture_read_only':True,'no_network_host_mounts_user_backup_host_keys_or_physical_passthrough':True,'test_host_key_generated_only_in_guest_ram':True,'ssh_server_not_started':True,'physical_sp7_connection_not_tested':True};(s/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');(w/'secureboot-live-candidate/ssh-configuration-vm-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));print('\n'.join(x for x in seen.decode(errors='replace').splitlines() if x.startswith(('SP7_','PASS:','FAIL:','port ','permitroot','allow','password','kbd','authentication'))));raise SystemExit(0 if passed else 1)
