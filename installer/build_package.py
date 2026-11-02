#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Create an inactive workbench from an exact locally checked-out camera tree."""
import argparse,hashlib,json,os,stat
from pathlib import Path
import sp7_setup as s
CAMERA_MANIFEST_SHA256 = 'f29e1e39165b0c816bdf1c0cca8325400b2551b69733f48edb449136171d4db4'
CAMERA_COMMIT = '876b5b1dbb5125d5ff878ff5b2d2671b2716e8e8'

def build(source, output):
    source=Path(source).absolute();output=Path(output).absolute()
    for p in [source,*source.parents]:
        if p.is_symlink():raise ValueError('Source ancestor is a symlink')
    manifest=source/'SHA256SUMS';raw=manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=CAMERA_MANIFEST_SHA256:raise ValueError('Unexpected camera manifest')
    rows={};files={}
    for line in raw.decode().splitlines():
        h,n=line.split('  ',1);s.relative(n)
        if n in rows or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('Invalid checksum row')
        if not(n in ['README.md','LICENSE','.gitignore'] or n.startswith(('replacement/','LICENSES/'))):raise ValueError('Unexpected source scope')
        rows[n]=h
    if len(rows)>s.MAX_FILES:raise ValueError('Source file-count limit')
    total=0
    for n,h in rows.items():
        p=source/n
        for parent in p.parents:
            if parent==source:break
            if parent.is_symlink():raise ValueError('Source parent symlink')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or a.st_size>s.LIMIT:raise ValueError('Unsafe source file')
            chunks=[];size=0
            while size<=s.LIMIT:
                x=os.read(fd,min(65536,s.LIMIT+1-size))
                if not x:break
                chunks.append(x);size+=len(x)
            b=os.fstat(fd);data=b''.join(chunks)
            if any(getattr(a,k)!=getattr(b,k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink']):raise ValueError('Source changed')
            if len(data)!=a.st_size or hashlib.sha256(data).hexdigest()!=h:raise ValueError('Source checksum mismatch')
        finally:os.close(fd)
        total+=len(data)
        if total>s.LIMIT:raise ValueError('Source size limit')
        files['app/'+n]=(data,0o755 if n.endswith('.sh') else 0o644)
    files['app/SHA256SUMS']=(raw,0o644)
    files['app/tools/sp7_setup.py']=(Path(__file__).with_name('sp7_setup.py').read_bytes(),0o755)
    m=dict(format=1,version='0.2.0',profile='inactive-workbench',compatibility=dict(distribution='manjaro',arch='x86_64',product='Surface Pro 7',kernel=s.KERNEL,python_min=[3,11],glibc_min=[2,38]),activation=dict(camera=False,drivers=False,login=False,autostart=False),camera_source_commit=CAMERA_COMMIT,files={n:dict(sha256=s.digest(d),mode=mode) for n,(d,mode) in files.items()})
    files['manifest.json']=(s.encode(m),0o644);package=s.archive_bytes(files);s.load_package(package,s.digest(package))
    output.mkdir(parents=True,exist_ok=True)
    dest=output/'sp7-independent-workbench-0.2.0-x86_64.tar.gz'
    with dest.open('xb') as f:f.write(package);f.flush();os.fsync(f.fileno())
    checks=output/'SHA256SUMS'
    with checks.open('x') as f:f.write(s.digest(package)+'  '+dest.name+'\n');f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(package=str(dest),sha256=s.digest(package),files=len(files),activation='none'),indent=2))
    return m

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--camera-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if os.geteuid()==0:raise SystemExit('Build as an ordinary user')
    build(a.camera_source,a.output)
