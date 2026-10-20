from pathlib import Path
import socket,json,time
s=Path('/mnt/sp7-backup/BACKUP/SP7-dualboot-preparation-history-20261019/synthetic-secureboot-clonezilla-live-v3-vm');a=json.loads((s/'launch.json').read_text());q=a[a.index('-qmp')+1].split(',')[0][5:];console='/tmp/sp7-public-live-v3-final-check.sock'
def reply(f):
 while True:
  x=json.loads(f.readline())
  if 'return' in x or 'error' in x:return x
with socket.socket(socket.AF_UNIX) as c:
 c.settimeout(3);c.connect(q);f=c.makefile('rwb',buffering=0);f.readline();f.write(b'{"execute":"qmp_capabilities"}\n');reply(f)
 x={'execute':'chardev-change','arguments':{'id':'serial0','backend':{'type':'socket','data':{'addr':{'type':'unix','data':{'path':console}},'server':True,'wait':False,'logfile':str(s/'serial.log'),'logappend':True}}}}
 f.write(json.dumps(x).encode()+b'\n');r=reply(f);(s/'console-change-receipt.json').write_text(json.dumps(r)+'\n');assert 'return' in r,r;f.close()
with socket.socket(socket.AF_UNIX) as c:
 c.settimeout(2);c.connect(console);c.sendall(b"printf '%s' 'IyEvYmluL2Jhc2gKc2V0IC1ldW8gcGlwZWZhaWwKZXhlYyA+L2Rldi90dHlTMCAyPiYxCnB5dGhvbjMgLSA8PCdFTkQnCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aApsaW5lcz1QYXRoKCcvcnVuL2xpdmUvbWVkaXVtL1NQNy1EVUFMQk9PVC9lbmFibGUtdGVtcG9yYXJ5LXNzaC5zaCcpLnJlYWRfdGV4dCgpLnNwbGl0bGluZXMoKQpzdGFydD1saW5lcy5pbmRleCgnY2F0ID4iJHIvc3NoZF9jb25maWciIDw8RU9GJykrMQplbmQ9bGluZXMuaW5kZXgoJ0VPRicsc3RhcnQpCnM9Y2hyKDEwKS5qb2luKGxpbmVzW3N0YXJ0OmVuZF0pK2NocigxMCkKcz1zLnJlcGxhY2UoJyRyJywnL3J1bi9zcDctc3NoZC1vZmZsaW5lLXRlc3QnKS5yZXBsYWNlKCckYWRkcicsJzEyNy4wLjAuMScpLnJlcGxhY2UoJyRwZWVyJywnMTkyLjE2OC4xLjEzNScpClBhdGgoJy9ydW4vc3A3LXNzaGQtb2ZmbGluZS10ZXN0L3NzaGRfY29uZmlnJykud3JpdGVfdGV4dChzKQpwPVBhdGgoJy9zeXMvZmlybXdhcmUvZWZpL2VmaXZhcnMvU2VjdXJlQm9vdC04YmU0ZGY2MS05M2NhLTExZDItYWEwZC0wMGUwOTgwMzJiOGMnKQpwcmludCgnU1A3X0xJVkVfU0VDVVJFX0JPT1Q9JytzdHIocC5yZWFkX2J5dGVzKClbNF0pLGZsdXNoPVRydWUpCkVORApyPS9ydW4vc3A3LXNzaGQtb2ZmbGluZS10ZXN0Ci91c3Ivc2Jpbi9zc2hkIC10IC1mICIkci9zc2hkX2NvbmZpZyIKL3Vzci9zYmluL3NzaGQgLVQgLWYgIiRyL3NzaGRfY29uZmlnIiAtQyB1c2VyPXVzZXIsYWRkcj0xOTIuMTY4LjEuMTM1LGhvc3Q9Ym9nZWJlYXIgPi9ydW4vc3A3LXNzaGQtZWZmZWN0aXZlLnR4dApmb3IgcnVsZSBpbiAncG9ydCAyMjIyJyAncGFzc3dvcmRhdXRoZW50aWNhdGlvbiBubycgJ2tiZGludGVyYWN0aXZlYXV0aGVudGljYXRpb24gbm8nICdwZXJtaXRyb290bG9naW4gbm8nICdhdXRoZW50aWNhdGlvbm1ldGhvZHMgcHVibGlja2V5JyAnYWxsb3d1c2VycyB1c2VyQDE5Mi4xNjguMS4xMzUnICdhbGxvd3RjcGZvcndhcmRpbmcgbm8nICdhbGxvd2FnZW50Zm9yd2FyZGluZyBubyc7IGRvIGdyZXAgLUZ4cSAiJHJ1bGUiIC9ydW4vc3A3LXNzaGQtZWZmZWN0aXZlLnR4dDsgZG9uZQpbWyAhIC1lICIkci9zc2hkLnBpZCIgJiYgISAtZSAvcnVuL3NwNy1kdWFsYm9vdC1zc2ggXV0KZWNobyBTUDdfVEVNUE9SQVJZX1NTSF9DT05GSUdfVkFMSURfTk9fU0VSVkVSX1NUQVJURUQKZWNobyBTUDdfTElWRV9SRUFET05MWV9QUk9CRV9DT01QTEVURQpwb3dlcm9mZiAtZgo=' | base64 -d | sudo bash\n");data=bytearray();end=time.monotonic()+20
 while time.monotonic()<end:
  try:b=c.recv(65536)
  except socket.timeout:continue
  if not b:break
  data+=b
  if b'SP7_LIVE_READONLY_PROBE_COMPLETE' in data:break
 (s/'console-repaired-ssh-config-final.txt').write_bytes(data);print(data.decode(errors='replace'))
p=Path(console)
if p.exists():p.unlink()
