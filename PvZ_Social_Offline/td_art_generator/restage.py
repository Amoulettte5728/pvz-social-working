import sys, zlib, struct
src, dst, bg = sys.argv[1], sys.argv[2], sys.argv[3]
xmin,xmax,ymin,ymax = [int(v) for v in sys.argv[4:8]]
d = open(src,'rb').read()
sig = d[:3]; ver = d[3]
if sig == b'CWS': body = zlib.decompress(d[8:])
elif sig == b'FWS': body = d[8:]
else: raise SystemExit('unsupported '+str(sig))
nbits = body[0] >> 3; rect_len = (5 + 4*nbits + 7)//8
rest = body[rect_len:]
vals=[v*20 for v in (xmin,xmax,ymin,ymax)]
nb=max(max(abs(v).bit_length() for v in vals)+1, 1)
bits='{:05b}'.format(nb)+''.join(format(v & ((1<<nb)-1), '0%db'%nb) for v in vals)
bits+= '0'*((8-len(bits)%8)%8)
rect=bytes(int(bits[i:i+8],2) for i in range(0,len(bits),8))
# rest: frame rate(2) frame count(2) then tags; replace SetBackgroundColor (code 9)
hdr = rest[:4]; tags = rest[4:]; out=b''; p=0
col = bytes.fromhex(bg)
while p < len(tags):
    tc, = struct.unpack_from('<H', tags, p); code = tc>>6; ln = tc&63; hl=2
    if ln == 63: ln, = struct.unpack_from('<I', tags, p+2); hl=6
    t = tags[p:p+hl+ln]
    if code == 9: t = struct.pack('<H', (9<<6)|3) + col
    out += t; p += hl+ln
body2 = rect + hdr + out
open(dst,'wb').write(b'FWS'+bytes([ver])+struct.pack('<I', len(body2)+8)+body2)
