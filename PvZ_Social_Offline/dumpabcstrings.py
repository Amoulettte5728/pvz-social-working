import sys,struct,zlib
sys.path.insert(0,'/mnt/data/_linkage_work/td_art_generator')
from swfsyms import tags
class R:
 def __init__(s,b):s.b=b;s.p=0
 def u8(s):v=s.b[s.p];s.p+=1;return v
 def u16(s):return s.u8()|s.u8()<<8
 def u30(s):
  v=0
  for i in range(5):
   b=s.u8();v|=(b&127)<<(7*i)
   if not b&128:return v
  return v
for f in sys.argv[1:]:
 v,t=tags(f)
 for c,b in t:
  if c not in (72,82):continue
  if c==82:
   # DoABC: flags 4, name null-terminated, then abc
   q=4
   while q<len(b) and b[q]:q+=1
   abc=b[q+1:]
  else: abc=b
  r=R(abc);r.u16();r.u16()
  ni=r.u30();[r.u30() for _ in range(max(0,ni-1))]
  nu=r.u30();[r.u30() for _ in range(max(0,nu-1))]
  nd=r.u30();r.p+=8*max(0,nd-1)
  ns=r.u30(); vals=[]
  for _ in range(max(0,ns-1)):
   n=r.u30(); vals.append(abc[r.p:r.p+n].decode('utf8','replace'));r.p+=n
  print('FILE',f,'STRINGS',len(vals))
  for x in vals:
   if any(k.lower() in x.lower() for k in ['CardSelector','SCard','seed','plant','card','modeId','tutorial','boost']): print(x)
