"""One normal loader attempt, using a dependency-free CSS support library.

Run only through ordinary interactive OS authorization. No force flags,
device-binding driver, capture, light control, installed files or new rights.
"""
import hashlib,json,os,pathlib,subprocess
P=pathlib.Path
assert os.geteuid()==0
assert os.uname().release=='7.2.11-arch1-1-surface'
assert P('/proc/sys/kernel/random/boot_id').read_text().strip()=='8255b1ce-aaa9-47e8-9a40-29469d1d0484'
cp=P('/srv/sp7-project/target/work/resume-state.json')
assert hashlib.sha256(cp.read_bytes()).hexdigest()=='cca14b8a31a5374882ac6fc56f973a067bf7aeb547145f394c451c82eee14c9a'
module=P('/usr/lib/modules/6.19.8-arch1-3-surface/updates/ipu4/intel-ipu4p-isys-csslib.ko')
assert not module.is_symlink() and module.stat().st_uid==0
expected='92fb37cba620ffa526d43c75b6bd5b3dab1582560057d1827f6c02d650ad9559'
assert hashlib.sha256(module.read_bytes()).hexdigest()==expected
name='intel_ipu4p_isys_csslib'
assert not (P('/sys/module')/name).exists()
def cmd(a):
 p=subprocess.run(a,text=True,capture_output=True,timeout=15)
 return dict(exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
assert cmd(['/usr/bin/modinfo','-F','depends',str(module)])['stdout'].strip()==''
vermagic=cmd(['/usr/bin/modinfo','-F','vermagic',str(module)])['stdout'].strip()
assert vermagic.startswith('6.19.8-arch1-3-surface ')
before=set(x.name for x in P('/sys/module').iterdir())
cursor=cmd(['/usr/bin/journalctl','-k','-b','-n','0','--show-cursor','--no-pager'])
assert cursor['exit']==0
cursor=cursor['stdout'].split('-- cursor: ')[-1].strip()
result={'kernel':os.uname().release,'module_sha256':expected,'module_vermagic':vermagic,
        'no_force_flags':True,'capture_or_lighting_requested':False}
result['normal_insmod']=cmd(['/usr/bin/insmod',str(module)])
loaded=(P('/sys/module')/name).exists()
result['loaded_after_attempt']=loaded
if loaded:
 result['remove_support_library']=cmd(['/usr/bin/rmmod',name])
result['support_library_absent_at_end']=not (P('/sys/module')/name).exists()
after=set(x.name for x in P('/sys/module').iterdir())
result['module_inventory_added']=sorted(after-before)
result['module_inventory_removed']=sorted(before-after)
j=cmd(['/usr/bin/journalctl','-k','-b','--after-cursor',cursor,'--no-pager','-o','cat'])
result['kernel_loader_messages']=[x for x in j['stdout'].splitlines() if any(s in x.lower() for s in ['ipu','version magic','module','symbol'])]
result['journal_exit']=j['exit']
print(json.dumps(result))
assert result['support_library_absent_at_end']
