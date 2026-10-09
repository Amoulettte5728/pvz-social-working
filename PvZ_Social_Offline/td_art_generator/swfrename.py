"""Rename exported symbol classes in a SWF (SymbolClass tag + same-length
strings in DoABC). usage: swfrename.py in.swf out.swf old=new [old=new ...]"""
import sys, zlib, struct
src, dst = sys.argv[1], sys.argv[2]
ren = dict(a.split('=', 1) for a in sys.argv[3:])
d = open(src, 'rb').read()
sig, ver = d[:3], d[3]
body = zlib.decompress(d[8:]) if sig == b'CWS' else d[8:]
nb = body[0] >> 3; rl = (5 + 4 * nb + 7) // 8
out = bytearray(body[:rl + 4]); p = rl + 4
def tag(code, b):
    if len(b) < 63 and code not in (6, 21, 35, 20, 36, 90):
        return struct.pack('<H', (code << 6) | len(b)) + b
    return struct.pack('<HI', (code << 6) | 63, len(b)) + b
done = []
while p < len(body):
    h, = struct.unpack_from('<H', body, p); p += 2
    code, ln = h >> 6, h & 63
    long_ = ln == 63
    if long_:
        ln, = struct.unpack_from('<I', body, p); p += 4
    b = body[p:p + ln]; p += ln
    if code == 76:
        n, = struct.unpack_from('<H', b); q = 2; nb_ = bytearray(struct.pack('<H', n))
        for _ in range(n):
            cid, = struct.unpack_from('<H', b, q); q += 2
            e = b.index(b'\0', q); name = b[q:e].decode('utf-8'); q = e + 1
            if name in ren:
                done.append((name, ren[name])); name = ren[name]
            nb_ += struct.pack('<H', cid) + name.encode('utf-8') + b'\0'
        b = bytes(nb_)
    elif code in (72, 82):
        bb = bytearray(b)
        for o, nw in ren.items():
            if len(o) != len(nw):
                continue
            ob = bytes([len(o)]) + o.encode(); nwb = bytes([len(nw)]) + nw.encode()
            bb = bytearray(bytes(bb).replace(ob, nwb))
        b = bytes(bb)
    out += (struct.pack('<HI', (code << 6) | 63, len(b)) + b) if (long_ or len(b) >= 63) else struct.pack('<H', (code << 6) | len(b)) + b
    if code == 0:
        break
comp = zlib.compress(bytes(out), 9)
open(dst, 'wb').write(b'CWS' + bytes([ver]) + struct.pack('<I', len(out) + 8) + comp)
print(dst, 'renamed', done)
