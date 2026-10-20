from pathlib import Path
import os,json,subprocess,time,selectors,base64,shutil
os.umask(0o077);w=Path(__file__).resolve().parent;s=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/partition5-transaction-vm')
a=json.loads((s/'launch-mbr.json').read_text());sock=Path('/tmp/sp7-mbr-test.sock')
b=base64.b64encode((w/'partition5-mbr-guest-test.sh').read_bytes()).decode();command='stty -echo; umask 077\n'+''.join("printf '%s' '"+b[i:i+1000]+"' >>/tmp/partition5-test.b64\n" for i in range(0,len(b),1000))+"base64 -d /tmp/partition5-test.b64 | sudo bash\n";seen=bytearray();sent=False;start=time.monotonic()
with (s/'serial-mbr.log').open('xb') as out,(s/'qemu-mbr.log').open('xb') as err:
 p=subprocess.Popen(a,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err);sel=selectors.DefaultSelector();sel.register(p.stdout,selectors.EVENT_READ)
 try:
  while time.monotonic()-start<110:
   for key,ev in sel.select(.25):
    d=os.read(key.fileobj.fileno(),65536)
    if d:seen+=d;out.write(d);out.flush()
   if b'user@sp7-live:~$ ' in seen and not sent:
    sent=True;time.sleep(.5);p.stdin.write(command.encode());p.stdin.flush()
   if b'SP7_PARTITION5_TEST_DONE' in seen or p.poll() is not None:break
 finally:
  sel.close()
  try:p.wait(timeout=8)
  except subprocess.TimeoutExpired:p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  if sock.exists():sock.unlink()
passed=b'SP7_WINDOWS_MBR_PRESERVATION_ALL_PASS' in seen
r={'schema':'sp7-partition5-transaction-vm-v1','passed':passed,'vm_off':p.poll() is not None,'qemu_exit':p.returncode,'seconds':time.monotonic()-start,'existing_public_fixture_read_only':True,'no_network_host_mounts_user_backup_host_keys_or_physical_passthrough':True,'test_host_key_generated_only_in_guest_ram':True,'synthetic_empty_gpt_only_no_user_data':True,'physical_sp7_connection_not_tested':True};(s/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');(w/'secureboot-live-candidate/protective-mbr-vm-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));print('\n'.join(x for x in seen.decode(errors='replace').splitlines() if x.startswith(('SP7_','PASS:','FAIL:','port ','permitroot','allow','password','kbd','authentication'))));raise SystemExit(0 if passed else 1)
