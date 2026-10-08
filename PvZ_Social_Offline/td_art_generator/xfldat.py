"""Decode XFL bin/*.dat bitmaps (Flash lossless 0x0503 or embedded JPEG) to PIL images."""
import struct, zlib, io
from PIL import Image

def load_dat(path):
    d = open(path, 'rb').read()
    if d[:2] == b'\xff\xd8':
        return Image.open(io.BytesIO(d)).convert('RGBA')
    if d[:2] != b'\x03\x05':
        raise ValueError(f'unknown .dat header {d[:4].hex()} in {path}')
    rowbytes, w, h = struct.unpack_from('<HHH', d, 2)
    p = 8 + 16
    has_alpha, compressed = d[p], d[p + 1]; p += 2
    if compressed:
        buf = bytearray()
        while p + 2 <= len(d):
            n = struct.unpack_from('<H', d, p)[0]; p += 2
            if n == 0: break
            buf += d[p:p + n]; p += n
        raw = zlib.decompress(bytes(buf))
    else:
        raw = d[p:]
    im = Image.new('RGBA', (w, h))
    px = bytearray(w * h * 4)
    for y in range(h):
        row = raw[y * rowbytes:y * rowbytes + w * 4]
        for x in range(w):
            a, r, g, b = row[x * 4:x * 4 + 4]
            if not has_alpha: a = 255
            if 0 < a < 255:
                r = min(255, r * 255 // a); g = min(255, g * 255 // a); b = min(255, b * 255 // a)
            o = (y * w + x) * 4; px[o:o + 4] = bytes((r, g, b, a))
    im.frombytes(bytes(px))
    return im
