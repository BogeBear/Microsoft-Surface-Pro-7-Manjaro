from pathlib import Path
import socket,json,time
s=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/synthetic-secureboot-clonezilla-live-v2-vm');a=json.loads((s/'launch.json').read_text());q=a[a.index('-qmp')+1].split(',')[0][5:];console='/tmp/sp7-public-live-v2-console-check.sock'
def reply(f):
 while True:
  x=json.loads(f.readline())
  if 'return' in x or 'error' in x:return x
with socket.socket(socket.AF_UNIX) as c:
 c.settimeout(3);c.connect(q);f=c.makefile('rwb',buffering=0);f.readline();f.write(b'{"execute":"qmp_capabilities"}\n');reply(f)
 x={'execute':'chardev-change','arguments':{'id':'serial0','backend':{'type':'socket','data':{'addr':{'type':'unix','data':{'path':console}},'server':True,'wait':False,'logfile':str(s/'serial.log'),'logappend':True}}}}
 f.write(json.dumps(x).encode()+b'\n');r=reply(f);(s/'console-change-receipt.json').write_text(json.dumps(r)+'\n');assert 'return' in r,r
with socket.socket(socket.AF_UNIX) as c:
 c.settimeout(2);c.connect(console);c.sendall(b'\nsudo bash /run/live/medium/sp7-vm-check.sh\n');data=bytearray();end=time.monotonic()+20
 while time.monotonic()<end:
  try:b=c.recv(65536)
  except socket.timeout:continue
  if not b:break
  data+=b
  if b'SP7_LIVE_READONLY_PROBE_COMPLETE' in data:break
 (s/'console-final.txt').write_bytes(data);print(data.decode(errors='replace'))
p=Path(console)
if p.exists():p.unlink()
