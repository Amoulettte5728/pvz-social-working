import sys,struct
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
  raise ValueError('u30')
 def bytes(s,n):v=s.b[s.p:s.p+n];s.p+=n;return v
 def skip(s,n):s.p+=n

def parse(abc):
 r=R(abc); r.u16();r.u16()
 ints=[0]; n=r.u30(); ints += [r.u30() for _ in range(max(0,n-1))]
 uints=[0]; n=r.u30(); uints += [r.u30() for _ in range(max(0,n-1))]
 dbl=[0.0]; n=r.u30(); r.skip(8*max(0,n-1))
 strs=['']; n=r.u30()
 for _ in range(max(0,n-1)):
  ln=r.u30(); strs.append(r.bytes(ln).decode('utf8','replace'))
 ns=['']; n=r.u30();
 for _ in range(max(0,n-1)):
  kind=r.u8(); idx=r.u30(); ns.append((kind,idx))
 nss=[[]]; n=r.u30()
 for _ in range(max(0,n-1)): nss.append([r.u30() for __ in range(r.u30())])
 mn=[None]; n=r.u30()
 for _ in range(max(0,n-1)):
  k=r.u8()
  if k in (0x07,0x0D): mn.append((k,r.u30(),r.u30()))
  elif k in (0x0F,0x10): mn.append((k,r.u30()))
  elif k in (0x11,0x12): mn.append((k,))
  elif k in (0x09,0x0E): mn.append((k,r.u30(),r.u30()))
  elif k in (0x1B,0x1C): mn.append((k,r.u30()))
  elif k==0x1D: mn.append((k,r.u30(),[r.u30() for __ in range(r.u30())]))
  else: raise ValueError('mn kind '+hex(k))
 def qname(i):
  if not i or i>=len(mn): return ''
  x=mn[i]
  if x[0] in (7,13):
   nsid, sid=x[1],x[2]
   return strs[sid]
  return ''
 methods=[]; n=r.u30()
 for _ in range(n):
  param_count=r.u30(); ret=r.u30(); params=[r.u30() for __ in range(param_count)]; name=r.u30(); flags=r.u8(); opts=[]
  if flags&8:
   opts=[(r.u30(),r.u8()) for __ in range(r.u30())]
  if flags&0x80: param_names=[r.u30() for __ in range(param_count)]
  else:param_names=[]
  methods.append({'name':strs[name] if name<len(strs) else '', 'ret':ret,'params':params,'flags':flags})
 # metadata
 n=r.u30()
 for _ in range(n):
  r.u30(); cnt=r.u30(); r.skip(8*cnt)
 instances=[]; classes=[]
 n=r.u30()
 for _ in range(n):
  name=r.u30(); supern=r.u30(); flags=r.u8(); protected= r.u30() if flags&8 else 0
  interfaces=[r.u30() for __ in range(r.u30())]
  init=r.u30(); traits=parse_traits(r,strs,mn)
  instances.append({'name':qname(name),'init':init,'traits':traits})
 for _ in range(n):
  init=r.u30(); traits=parse_traits(r,strs,mn); classes.append({'init':init,'traits':traits})
 scripts=[]; n=r.u30()
 for _ in range(n): init=r.u30(); traits=parse_traits(r,strs,mn); scripts.append({'init':init,'traits':traits})
 bodies=[]; n=r.u30()
 for _ in range(n):
  mi=r.u30(); maxstack=r.u30(); local=r.u30(); init_scope=r.u30(); max_scope=r.u30(); ln=r.u30(); code=r.bytes(ln)
  ex=[]
  for __ in range(r.u30()): ex.append((r.u30(),r.u30(),r.u30(),r.u30(),r.u30()))
  traits=parse_traits(r,strs,mn)
  bodies.append((mi,code))
 return strs,mn,methods,instances,classes,bodies

def parse_traits(r,strs,mn):
 out=[]
 def q(i):
  if not i:return ''
  x=mn[i]
  return strs[x[2]] if x and x[0] in (7,13) else ''
 for _ in range(r.u30()):
  namei=r.u30(); kind=r.u8(); k=kind&15; attrs=kind&0xf0; val=None
  if k in (0,6): slot=r.u30(); typ=r.u30(); vi=r.u30(); val=(slot,typ,vi); r.u8() if vi else None
  elif k in (1,2,3,4,5): val=(r.u30(),r.u30())
  else: raise ValueError('trait kind')
  if attrs&0x40:
   for __ in range(r.u30()):r.u30()
  out.append((q(namei),k,val))
 return out

def getabc(f):
 v,t=tags(f)
 for c,b in t:
  if c==72:return b
  if c==82:
   q=4
   while q<len(b) and b[q]:q+=1
   return b[q+1:]
if __name__ == "__main__":
 for f in sys.argv[1:]:
  strs,mn,methods,inst,classes,bodies=parse(getabc(f))
  targets=[]
  for ci,x in enumerate(inst):
   if any(k in x['name'] for k in ['CardSelector','SCardListTopPanel','CardVO','PlantVO','CardsManager','PlantsFactory','Boost']):
    targets.append((ci,x['name'],x['traits']))
  print('TARGETS',targets[:30])
  for i,m in enumerate(methods):
   if any(k.lower() in m['name'].lower() for k in ['moveShow','initCard','getCard','setCard','selectCard','getPlantCardImg','getCardVO','setCardVO','getCardsVOData','show']):
    print('METHOD',i,m)
