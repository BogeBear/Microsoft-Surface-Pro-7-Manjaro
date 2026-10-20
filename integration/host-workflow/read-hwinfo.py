from pathlib import Path
import base64,gzip,json,sys
from windows_transport import run
w=Path(__file__).resolve().parent;s=(w/'Read-HWiNFO-Temperatures.ps1').read_bytes()
b=base64.b64encode(gzip.compress(s,mtime=0)).decode()
p="$b=[Convert]::FromBase64String('"+b+"');$m=New-Object IO.MemoryStream(,$b);$g=New-Object IO.Compression.GZipStream($m,[IO.Compression.CompressionMode]::Decompress);$r=New-Object IO.StreamReader($g,[Text.Encoding]::UTF8);try{Invoke-Expression $r.ReadToEnd()}finally{$r.Dispose();$g.Dispose();$m.Dispose()}"
r=run(p);name=sys.argv[1] if len(sys.argv)>1 else 'hwinfo-temperature-01';(w/(name+'.json')).write_text(r.stdout);(w/(name+'.stderr.txt')).write_text(r.stderr);print(r.stdout if r.returncode==0 else r.stderr);raise SystemExit(r.returncode)
