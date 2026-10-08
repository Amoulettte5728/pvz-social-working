"""Extract a zip by walking local file headers (ignores a broken central directory)."""
import struct, zlib, os, sys

def extract(path, out):
    d = open(path, 'rb').read(); p = 0; n = 0
    while True:
        i = d.find(b'PK\x03\x04', p)
        if i < 0: break
        ver, flag, meth, t, dt, crc, csz, usz, nl, xl = struct.unpack_from('<HHHHHIIIHH', d, i + 4)
        name = d[i + 30:i + 30 + nl].decode('utf-8', 'replace')
        s = i + 30 + nl + xl
        if meth == 8:
            do = zlib.decompressobj(-15)
            data = do.decompress(d[s:s + csz] if csz and not (flag & 8) else d[s:])
            used = (csz if csz and not (flag & 8) else len(d[s:]) - len(do.unused_data))
        elif meth == 0:
            data = d[s:s + csz]; used = csz
        else:
            print('skip method', meth, name); p = s; continue
        p = max(s + used, i + 4)
        if name.endswith('/'):
            continue
        fp = os.path.join(out, name)
        os.makedirs(os.path.dirname(fp) or out, exist_ok=True)
        open(fp, 'wb').write(data); n += 1
    return n

if __name__ == '__main__':
    print(extract(sys.argv[1], sys.argv[2]), 'files')
