#!/usr/bin/env python3
"""Compile syntax / parse shell scripts, never run an integration action."""
import ast,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];bad=[];count=0
for p in sorted((root/'integration').rglob('*')):
 if p.suffix=='.py':
  try:ast.parse(p.read_text(),filename=str(p.relative_to(root)));count+=1
  except SyntaxError as e:bad.append(str(e))
 elif p.suffix=='.sh':
  r=subprocess.run(['bash','-n',str(p)],capture_output=True,text=True);count+=1
  if r.returncode:bad.append(r.stderr)
print('Syntax-checked files:',count)
for error in bad:print(error)
raise SystemExit(bool(bad))
