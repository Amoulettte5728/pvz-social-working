import sys
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from abccheck import R, tags
# operand formats: list of 'u30','u8','s24','sw' (lookupswitch)
OPS={}
def op(codes,fmt):
    for c in codes: OPS[c]=fmt
op([0x01,0x02,0x03,0x07,0x09,0x1C,0x1D,0x1E,0x1F,0x20,0x21,0x23,0x26,0x27,0x28,0x29,0x2A,0x2B,0x30,0x35,0x36,0x37,0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,0x47,0x48,0x50,0x51,0x52,0x57,0x64,0x70,0x71,0x72,0x73,0x74,0x75,0x76,0x77,0x78,0x81,0x82,0x83,0x84,0x85,0x87,0x88,0x89,0x8A,0x8B,0x8C,0x90,0x91,0x93,0x95,0x96,0x97,0xA0,0xA1,0xA2,0xA3,0xA4,0xA5,0xA6,0xA7,0xA8,0xA9,0xAA,0xAB,0xAC,0xAD,0xAE,0xAF,0xB0,0xB1,0xB3,0xB4,0xC0,0xC1,0xC4,0xC5,0xC6,0xC7,0xD0,0xD1,0xD2,0xD3,0xD4,0xD5,0xD6,0xD7,0xF3],[])
op([0x04,0x05,0x06,0x08,0x2C,0x2D,0x2E,0x2F,0x31,0x40,0x41,0x42,0x49,0x53,0x55,0x56,0x58,0x59,0x5A,0x5D,0x5E,0x5F,0x60,0x61,0x62,0x63,0x66,0x68,0x6A,0x6C,0x6D,0x6E,0x6F,0x80,0x86,0x92,0x94,0xB2,0xC2,0xC3,0xF0,0xF1,0x25],['u30'])
op([0x43,0x44,0x45,0x46,0x4A,0x4C,0x4E,0x4F],['u30','u30'])
op([0x32],['u30','u30'])
op([0x0C,0x0D,0x0E,0x0F,0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19,0x1A],['s24'])
op([0x24,0x65],['u8'])
op([0xEF],['u8','u30','u8','u30'])
op([0x1B],['sw'])
def walk(abc,name):
    r=R(abc); r.u16(); r.u16()
    ni=r.u30(); [r.u30() for _ in range(max(0,ni-1))]
    nu=r.u30(); [r.u30() for _ in range(max(0,nu-1))]
    nd=r.u30(); [r.skip(8) for _ in range(max(0,nd-1))]
    ns=r.u30(); [r.skip(r.u30()) for _ in range(max(0,ns-1))]
    nn=r.u30(); [ (r.u8(),r.u30()) for _ in range(max(0,nn-1))]
    nss=r.u30(); [[r.u30() for _ in range(r.u30())] for _ in range(max(0,nss-1))]
    nm=r.u30()
    for _ in range(max(0,nm-1)):
        k=r.u8()
        if k in (7,0xD,9,0xE): r.u30(); r.u30()
        elif k in (0xF,0x10,0x1B,0x1C): r.u30()
        elif k==0x1D: r.u30(); [r.u30() for _ in range(r.u30())]
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
            else: r.u30(); r.u30()
            if kb&0x40: [r.u30() for _ in range(r.u30())]
    C=r.u30()
    for _ in range(C):
        r.u30(); r.u30(); fl=r.u8()
        if fl&0x08: r.u30()
        [r.u30() for _ in range(r.u30())]; r.u30(); traits()
    for _ in range(C): r.u30(); traits()
    for _ in range(r.u30()): r.u30(); traits()
    bad=0
    for bi in range(r.u30()):
        m=r.u30(); ms=r.u30(); lc=r.u30(); isd=r.u30(); msd=r.u30(); cl=r.u30()
        code=abc[r.p:r.p+cl]; r.skip(cl)
        c=R(code)
        try:
            while c.p<len(code):
                at=c.p; o=c.u8()
                if o not in OPS: raise ValueError(f'unknown opcode 0x{o:02X} at {at}')
                for f in OPS[o]:
                    if f=='u30': c.u30()
                    elif f=='u8': c.u8()
                    elif f=='s24': c.s24()
                    elif f=='sw':
                        c.s24(); n=c.u30(); [c.s24() for _ in range(n+1)]
                if c.p>len(code): raise EOFError('operand past end')
        except Exception as e:
            bad+=1
            if bad<=5: print(f'  {name}: method {m} body {bi}: {e!r} (code_len {cl}, maxstack {ms}, locals {lc}, scope {isd}-{msd})')
        for _ in range(r.u30()): r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
        traits()
    print(f'{name}: bodies with problems = {bad}')
for f in sys.argv[1:]:
    v,t=tags(f)
    for cde,b in t:
        if cde==82: walk(b[b.index(b'\0',4)+1:], f.split('/')[-1])
        if cde==72: walk(b, f.split('/')[-1])
