"""Strict ABC walker: parses every structure per the AVM2 spec and reports
where parsing goes out of bounds or leaves trailing bytes."""
import sys, struct, zlib
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swfsyms import tags
class R:
    def __init__(s,b): s.b=b; s.p=0
    def u8(s):
        if s.p>=len(s.b): raise EOFError(f'u8 at {s.p}')
        v=s.b[s.p]; s.p+=1; return v
    def u16(s): return s.u8()|(s.u8()<<8)
    def s24(s):
        v=s.u8()|(s.u8()<<8)|(s.u8()<<16); return v-(1<<24) if v&0x800000 else v
    def u30(s):
        v=0
        for i in range(5):
            b=s.u8(); v|=(b&0x7f)<<(7*i)
            if not b&0x80: break
        return v
    def d(s): s.p+=8
    def skip(s,n):
        if s.p+n>len(s.b): raise EOFError(f'skip {n} at {s.p}')
        s.p+=n
def parse(abc):
    r=R(abc); r.u16(); r.u16()
    ni=r.u30(); [r.u30() for _ in range(max(0,ni-1))]
    nu=r.u30(); [r.u30() for _ in range(max(0,nu-1))]
    nd=r.u30(); [r.skip(8) for _ in range(max(0,nd-1))]
    ns=r.u30()
    for _ in range(max(0,ns-1)): r.skip(r.u30())
    nn=r.u30()
    for _ in range(max(0,nn-1)): r.u8(); r.u30()
    nss=r.u30()
    for _ in range(max(0,nss-1)): [r.u30() for _ in range(r.u30())]
    nm=r.u30()
    for _ in range(max(0,nm-1)):
        k=r.u8()
        if k in (7,0xD): r.u30(); r.u30()
        elif k in (0xF,0x10): r.u30()
        elif k in (0x11,0x12): pass
        elif k in (9,0xE): r.u30(); r.u30()
        elif k in (0x1B,0x1C): r.u30()
        elif k==0x1D: r.u30(); [r.u30() for _ in range(r.u30())]
        else: raise ValueError(f'bad multiname kind {k}')
    M=r.u30()
    for _ in range(M):
        pc=r.u30(); r.u30(); [r.u30() for _ in range(pc)]; r.u30(); fl=r.u8()
        if fl&0x08:
            for _ in range(r.u30()): r.u30(); r.u8()
        if fl&0x80: [r.u30() for _ in range(pc)]
    for _ in range(r.u30()):
        r.u30(); n=r.u30(); [r.u30() for _ in range(2*n)]
    def traits():
        for _ in range(r.u30()):
            r.u30(); kb=r.u8(); k=kb&0xF
            if k in (0,6): r.u30(); r.u30(); vi=r.u30(); (r.u8() if vi else None)
            elif k in (1,2,3,4,5): r.u30(); r.u30()
            else: raise ValueError(f'bad trait kind {k}')
            if kb&0x40: [r.u30() for _ in range(r.u30())]
    C=r.u30()
    for _ in range(C):
        r.u30(); r.u30(); fl=r.u8()
        if fl&0x08: r.u30()
        [r.u30() for _ in range(r.u30())]; r.u30(); traits()
    for _ in range(C): r.u30(); traits()
    for _ in range(r.u30()): r.u30(); traits()
    nb=r.u30()
    for _ in range(nb):
        m=r.u30(); r.u30(); r.u30(); r.u30(); r.u30(); cl=r.u30(); r.skip(cl)
        for _ in range(r.u30()): r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
        traits()
    return dict(methods=M,bodies=nb,classes=C,end=r.p,len=len(abc))
for f in sys.argv[1:]:
    v,t=tags(f)
    for c,b in t:
        if c in (72,82):
            abc=b if c==72 else b[4+b.index(b'\0',4)+1-4:] if False else b[b.index(b'\0',4)+1:]
            try:
                info=parse(abc); ok=info['end']==info['len']
                print(f"{f.split('/')[-1]}: {'OK' if ok else 'TRAILING'} {info}")
            except Exception as e:
                print(f"{f.split('/')[-1]}: FAIL {e!r}")
