"""Explicit public-only fixture: original stock module vs project vs unsigned."""
from pathlib import Path
import hashlib,json,shutil,subprocess,stat,gzip,os
w=Path(__file__).resolve().parent;b=w/'secureboot-probe-initramfs';r=b/'root-v7'
shutil.copytree(b/'root-v6',r,symlinks=True)
src=Path('/mnt/sp7-backup/BACKUP/SP7-camera-20261014/tree/usr/lib/modules/6.19.8-arch1-3-surface/kernel/drivers/net/dummy.ko.zst')
with (r/'tests/dummy-stock.ko').open('xb') as f:subprocess.run(['zstd','-dc',str(src)],stdout=f,check=True)
s=(r/'init').read_text();s=s.replace('insmod /tests/dummy-unsigned.ko', '''echo SP7_CMDLINE=$(cat /proc/cmdline)
echo SP7_EFFECTIVE_CAPS
cat /proc/self/status | grep -E '^Cap(Eff|Bnd):'
echo SP7_PUBLIC_MOK_VARIABLES_BEGIN
for f in /sys/firmware/efi/efivars/MokListRT-* /sys/firmware/efi/efivars/MokListTrustedRT-* /sys/firmware/efi/efivars/MokSBStateRT-*; do
 if [ -f "$f" ]; then echo "$f"; od -An -tx1 -N8 "$f"; fi
done
echo SP7_PUBLIC_MOK_VARIABLES_END
insmod /tests/dummy-stock.ko
t=$?
echo SP7_STOCK_SIGNED_MODULE_RC=$t
if [ "$t" = 0 ]; then rmmod dummy; fi
insmod /tests/dummy-unsigned.ko''')
s=s.replace('cat /proc/keys','cat /proc/keys | grep -E "keyring|asymmetric"');(r/'init').write_text(s)
files=[r,*sorted(r.rglob('*'))];out=bytearray();manifest=[]
for ino,p in enumerate(files,1):
 rel='.' if p==r else p.relative_to(r).as_posix();st=p.lstat();data=os.readlink(p).encode() if p.is_symlink() else p.read_bytes() if p.is_file() else b''
 name=rel.encode()+b'\0';fields=[ino,st.st_mode,0,0,2 if p.is_dir() else 1,0,len(data),0,0,0,0,len(name),0];header=b'070701'+b''.join(f'{n:08x}'.encode() for n in fields);out+=header+name;out+=b'\0'*(-len(out)%4);out+=data;out+=b'\0'*(-len(out)%4);manifest.append({'path':rel,'mode':oct(st.st_mode),'sha256':hashlib.sha256(data).hexdigest()})
name=b'TRAILER!!!\0';fields=[0,0,0,0,1,0,0,0,0,0,0,len(name),0];out+=b'070701'+b''.join(f'{n:08x}'.encode() for n in fields)+name;out+=b'\0'*(-len(out)%512)
f=b/'initramfs-v7.cpio.gz';f.write_bytes(gzip.compress(bytes(out),mtime=0));(b/'v7-receipt.json').write_text(json.dumps({'purpose':'stock positive control, MOK visibility, enforced lockdown; no private keys','sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'manifest':manifest},indent=2)+'\n')
p=w/'test-secureboot-kernel-modules-v6.py';s=p.read_text().replace('v6','v7').replace(",'--set-true','MokListTrusted'",'');(w/'test-secureboot-kernel-modules-v7.py').write_text(s)
