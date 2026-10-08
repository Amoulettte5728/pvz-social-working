"""Tiny SWF writer for placeholder art libraries (AS3, Flash 10).

Builds: DefineShape3 (solid RGBA fills + outline, circles via quadratic curves,
polygons), DefineSprite timelines, a DoABC2 tag declaring one empty
`public class <Name> extends flash.display.MovieClip` per exported sprite,
and a SymbolClass tag linking them.
"""
import struct, zlib, math


class Bits:
    def __init__(self):
        self.out = bytearray(); self.acc = 0; self.n = 0

    def u(self, v, nb):
        for i in range(nb - 1, -1, -1):
            self.acc = (self.acc << 1) | ((v >> i) & 1); self.n += 1
            if self.n == 8:
                self.out.append(self.acc); self.acc = 0; self.n = 0

    def s(self, v, nb):
        self.u(v & ((1 << nb) - 1), nb)

    def flush(self):
        if self.n:
            self.out.append(self.acc << (8 - self.n)); self.acc = 0; self.n = 0
        return bytes(self.out)


def sbits(*vals):
    m = 1
    for v in vals:
        v = int(v)
        n = (v.bit_length() + 1) if v >= 0 else ((~v).bit_length() + 1)
        m = max(m, n)
    return m


def ubits(*vals):
    return max([1] + [int(v).bit_length() for v in vals])


def rect(xmin, xmax, ymin, ymax):
    nb = sbits(xmin, xmax, ymin, ymax)
    b = Bits(); b.u(nb, 5)
    for v in (xmin, xmax, ymin, ymax):
        b.s(int(v), nb)
    return b.flush()


def matrix(tx=0, ty=0, sx=1.0, sy=1.0, rot=0.0):
    """Twips translate; scale/rotation in plain units / radians."""
    b = Bits()
    a = sx * math.cos(rot); d = sy * math.cos(rot)
    r0 = sx * math.sin(rot); r1 = -sy * math.sin(rot)
    if abs(a - 1) > 1e-6 or abs(d - 1) > 1e-6:
        A = int(round(a * 65536)); D = int(round(d * 65536))
        nb = sbits(A, D); b.u(1, 1); b.u(nb, 5); b.s(A, nb); b.s(D, nb)
    else:
        b.u(0, 1)
    if abs(r0) > 1e-6 or abs(r1) > 1e-6:
        R0 = int(round(r0 * 65536)); R1 = int(round(r1 * 65536))
        nb = sbits(R0, R1); b.u(1, 1); b.u(nb, 5); b.s(R0, nb); b.s(R1, nb)
    else:
        b.u(0, 1)
    tx = int(round(tx)); ty = int(round(ty))
    if tx == 0 and ty == 0:
        b.u(0, 5)
    else:
        nb = sbits(tx, ty); b.u(nb, 5); b.s(tx, nb); b.s(ty, nb)
    return b.flush()


def cxform_alpha(mr=1, mg=1, mb=1, ma=1, ar=0, ag=0, ab=0, aa=0):
    b = Bits()
    M = [int(round(v * 256)) for v in (mr, mg, mb, ma)]
    A = [int(v) for v in (ar, ag, ab, aa)]
    hasM = any(v != 256 for v in M); hasA = any(A)
    b.u(1 if hasA else 0, 1); b.u(1 if hasM else 0, 1)
    nb = sbits(*(([*M] if hasM else []) + ([*A] if hasA else []) + [0]))
    b.u(nb, 4)
    if hasM:
        for v in M: b.s(v, nb)
    if hasA:
        for v in A: b.s(v, nb)
    return b.flush()


def tag(code, body):
    if len(body) < 63 and code not in (20, 36, 21, 35, 90, 6):
        return struct.pack('<H', (code << 6) | len(body)) + body
    return struct.pack('<HI', (code << 6) | 63, len(body)) + body


# ---------- shapes ----------
class Path:
    """A closed outline in pixel units: list of ('L',x,y) / ('Q',cx,cy,x,y), start point."""
    def __init__(self, sx, sy):
        self.start = (sx, sy); self.segs = []

    def L(self, x, y):
        self.segs.append(('L', x, y)); return self

    def Q(self, cx, cy, x, y):
        self.segs.append(('Q', cx, cy, x, y)); return self


def ellipse(cx, cy, rx, ry, n=8):
    p = Path(cx + rx, cy)
    k = 1 / math.cos(math.pi / n)
    for i in range(1, n + 1):
        a0 = 2 * math.pi * (i - 1) / n; a1 = 2 * math.pi * i / n; am = (a0 + a1) / 2
        p.Q(cx + rx * k * math.cos(am), cy + ry * k * math.sin(am), cx + rx * math.cos(a1), cy + ry * math.sin(a1))
    return p


def polygon(pts):
    p = Path(*pts[0])
    for x, y in pts[1:]:
        p.L(x, y)
    p.L(*pts[0])
    return p


def define_shape3(cid, path, fill, line=(0, 0, 0, 255), lw=1.5):
    """One closed path, one solid RGBA fill, optional outline (line=None for none)."""
    T = lambda v: int(round(v * 20))
    xs = [path.start[0]] + [s[-2] for s in path.segs] + [s[1] for s in path.segs if s[0] == 'Q']
    ys = [path.start[1]] + [s[-1] for s in path.segs] + [s[2] for s in path.segs if s[0] == 'Q']
    pad = lw if line else 0
    bounds = rect(T(min(xs) - pad), T(max(xs) + pad), T(min(ys) - pad), T(max(ys) + pad))
    body = struct.pack('<H', cid) + bounds
    body += bytes([1, 0x00]) + bytes(fill)                         # fill styles
    if line:
        body += bytes([1]) + struct.pack('<H', T(lw)) + bytes(line)  # line styles
    else:
        body += bytes([0])
    b = Bits(); nfb = 1; nlb = 1 if line else 0
    b.u(nfb, 4); b.u(nlb, 4)
    # style change: moveTo + fillStyle1 (+ lineStyle)
    sx, sy = T(path.start[0]), T(path.start[1])
    b.u(0, 1); b.u(0, 1); b.u(1 if line else 0, 1); b.u(1, 1); b.u(0, 1); b.u(1, 1)
    nb = sbits(sx, sy); b.u(nb, 5); b.s(sx, nb); b.s(sy, nb)
    b.u(1, nfb)
    if line:
        b.u(1, nlb)
    cx, cy = sx, sy
    for s in path.segs:
        if s[0] == 'L':
            x, y = T(s[1]), T(s[2]); dx, dy = x - cx, y - cy
            if dx == 0 and dy == 0:
                continue
            nb = sbits(dx, dy); b.u(1, 1); b.u(1, 1); b.u(max(nb, 2) - 2, 4); nb = max(nb, 2)
            if dx != 0 and dy != 0:
                b.u(1, 1); b.s(dx, nb); b.s(dy, nb)
            elif dx == 0:
                b.u(0, 1); b.u(1, 1); b.s(dy, nb)
            else:
                b.u(0, 1); b.u(0, 1); b.s(dx, nb)
            cx, cy = x, y
        else:
            qx, qy, x, y = T(s[1]), T(s[2]), T(s[3]), T(s[4])
            c1x, c1y, a1x, a1y = qx - cx, qy - cy, x - qx, y - qy
            nb = max(sbits(c1x, c1y, a1x, a1y), 2)
            b.u(1, 1); b.u(0, 1); b.u(nb - 2, 4)
            for v in (c1x, c1y, a1x, a1y):
                b.s(v, nb)
            cx, cy = x, y
    b.u(0, 1); b.u(0, 5)  # end shape
    body += b.flush()
    return tag(32, body)


# ---------- sprites ----------
def place2(depth, cid=None, mtx=None, cx=None, move=False):
    flags = 0
    if move: flags |= 0x01
    if cid is not None: flags |= 0x02
    if mtx is not None: flags |= 0x04
    if cx is not None: flags |= 0x08
    body = bytes([flags]) + struct.pack('<H', depth)
    if cid is not None: body += struct.pack('<H', cid)
    if mtx is not None: body += mtx
    if cx is not None: body += cx
    return tag(26, body)


def remove2(depth):
    return tag(28, struct.pack('<H', depth))


def define_sprite(cid, frames):
    """frames: list of frames; each frame is a list of (partCid, tx_px, ty_px, sx, sy, rot, cxform|None).
    Depth = index in list. Parts are re-placed every frame (replace/move)."""
    body = struct.pack('<HH', cid, len(frames))
    prev = {}
    for fr in frames:
        cur = {}
        for d, part in enumerate(fr, start=1):
            pc, x, y, sx, sy, rot, cxf = part
            m = matrix(x * 20, y * 20, sx, sy, rot)
            cxb = cxform_alpha(*cxf) if cxf else None
            key = (pc, m, cxb)
            if d in prev and prev[d] == key:
                cur[d] = key; continue
            if d in prev and prev[d][0] == pc:
                body += place2(d, None, m, cxb if cxb is not None else cxform_alpha(), move=True)
            elif d in prev:
                body += place2(d, pc, m, cxb if cxb is not None else None, move=True)
            else:
                body += place2(d, pc, m, cxb)
            cur[d] = key
        for d in prev:
            if d not in cur:
                body += remove2(d)
        prev = cur
        body += tag(1, b'')
    body += tag(0, b'')
    return tag(39, body)


# ---------- ABC ----------
def u30(v):
    out = bytearray()
    while True:
        b = v & 0x7F; v >>= 7
        if v: out.append(b | 0x80)
        else:
            out.append(b); return bytes(out)


def abc_for_classes(names, base_pkg="flash.display", base_name="MovieClip"):
    """One AS3 class `public class <Name> extends flash.display.MovieClip` per name.

    Layout copies what Flash's own compiler emits (checked against a
    Flash-built Plant_Peashooter.swf that the Adobe player loads): one script
    per class, a protected namespace per class (instance flag 0x08), and a
    script initialiser that pushes the full base-class scope chain
    (Object .. MovieClip) before `newclass`, with matching scope depths.
    """
    chain = [("", "Object"), ("flash.events", "EventDispatcher"), ("flash.display", "DisplayObject"),
             ("flash.display", "InteractiveObject"), ("flash.display", "DisplayObjectContainer"),
             ("flash.display", "Sprite"), ("flash.display", "MovieClip")]
    strings = ["", "flash.display", "flash.events"] + [c for _, c in chain] + list(names)
    S = {}
    for st in strings:
        if st not in S:
            S[st] = len(S) + 1
    out = bytearray(struct.pack('<HH', 16, 46))
    out += u30(0) + u30(0) + u30(0)
    out += u30(len(S) + 1)
    for st in S:
        e = st.encode('utf-8'); out += u30(len(e)) + e
    # namespaces: 1 pkg "", 2 pkg flash.display, 3 pkg flash.events, 4.. protected ns per class
    NS = {"": 1, "flash.display": 2, "flash.events": 3}
    out += u30(4 + len(names))
    out += bytes([0x16]) + u30(S[""]) + bytes([0x16]) + u30(S["flash.display"]) + bytes([0x16]) + u30(S["flash.events"])
    for n in names:
        out += bytes([0x18]) + u30(S[n])
    out += u30(0)  # ns sets
    # multinames: 1..7 = base chain (Object .. MovieClip), 8.. = classes
    MN = {}
    out += u30(1 + len(chain) + len(names))
    for i, (pkg, cname) in enumerate(chain):
        out += bytes([0x07]) + u30(NS[pkg]) + u30(S[cname]); MN[cname] = i + 1
    for i, n in enumerate(names):
        out += bytes([0x07]) + u30(1) + u30(S[n])
    CM = lambda i: 1 + len(chain) + i
    N = len(names)
    # methods per class i: cinit 3i, iinit 3i+1, script init 3i+2
    out += u30(3 * N)
    for _ in range(3 * N):
        out += u30(0) + u30(0) + u30(0) + bytes([0])
    out += u30(0)  # metadata
    out += u30(N)
    for i in range(N):
        out += u30(CM(i)) + u30(MN["MovieClip"]) + bytes([0x08]) + u30(4 + i) + u30(0) + u30(3 * i + 1) + u30(0)
    for i in range(N):
        out += u30(3 * i) + u30(0)
    out += u30(N)
    for i in range(N):
        out += u30(3 * i + 2) + u30(1) + u30(CM(i)) + bytes([0x04]) + u30(1) + u30(i)
    out += u30(3 * N)
    cinit = bytes([0xD0, 0x30, 0x47])
    iinit = bytes([0xD0, 0x30, 0xD0, 0x49]) + u30(0) + bytes([0x47])
    for i in range(N):
        code = bytearray([0xD0, 0x30, 0x65, 0x00])
        for _, cname in chain:
            code += bytes([0x60]) + u30(MN[cname]) + bytes([0x30])
        code += bytes([0x60]) + u30(MN["MovieClip"]) + bytes([0x58]) + u30(i)
        code += bytes([0x1D]) * len(chain)
        code += bytes([0x68]) + u30(CM(i)) + bytes([0x47])
        d = len(chain) + 2  # 9: global + 7 bases + class scope
        out += u30(3 * i) + u30(1) + u30(1) + u30(d) + u30(d + 1) + u30(len(cinit)) + cinit + u30(0) + u30(0)
        out += u30(3 * i + 1) + u30(1) + u30(1) + u30(d + 1) + u30(d + 2) + u30(len(iinit)) + iinit + u30(0) + u30(0)
        out += u30(3 * i + 2) + u30(2) + u30(1) + u30(1) + u30(d) + u30(len(code)) + bytes(code) + u30(0) + u30(0)
    return bytes(out)


def doabc(abc, name=""):
    return tag(82, struct.pack('<I', 1) + name.encode() + b'\0' + abc)


def symbol_class(pairs):
    body = struct.pack('<H', len(pairs))
    for cid, n in pairs:
        body += struct.pack('<H', cid) + n.encode('utf-8') + b'\0'
    return tag(76, body)


def build_swf(define_tags, exports, w=760, h=600, fps=30, compress=True, bitmap_exports=()):
    """exports: list of (spriteCid, className); bitmap_exports: (bitmapCid, className) for BitmapData classes."""
    names = [n for _, n in exports]
    tags = tag(69, struct.pack('<I', 0x08))            # FileAttributes: AS3 (must be first)
    tags += tag(9, bytes([0xFF, 0xFF, 0xFF]))          # background
    tags += b''.join(define_tags)
    tags += doabc(abc_for_classes(names))
    if bitmap_exports:
        tags += doabc(abc_for_bitmapdata_classes([n for _, n in bitmap_exports]))
    tags += symbol_class(list(exports) + list(bitmap_exports))
    tags += tag(1, b'') + tag(0, b'')
    hdr = rect(0, w * 20, 0, h * 20) + struct.pack('<HH', fps << 8, 1)
    body = hdr + tags
    ln = 8 + len(body)
    if compress:
        return b'CWS' + bytes([10]) + struct.pack('<I', ln) + zlib.compress(body, 9)
    return b'FWS' + bytes([10]) + struct.pack('<I', ln) + body


# ---------- bitmaps ----------
def define_bits_lossless2(cid, img):
    """PIL RGBA image -> DefineBitsLossless2 (format 5: premultiplied ARGB, zlib)."""
    img = img.convert('RGBA')
    w, h = img.size
    raw = bytearray()
    px = img.tobytes()
    for i in range(0, len(px), 4):
        r, g, b, a = px[i], px[i + 1], px[i + 2], px[i + 3]
        if a < 255:
            r = r * a // 255; g = g * a // 255; b = b * a // 255
        raw += bytes((a, r, g, b))
    body = struct.pack('<HBHH', cid, 5, w, h) + zlib.compress(bytes(raw), 9)
    return struct.pack('<HI', (36 << 6) | 63, len(body)) + body


def define_bitmap_shape(cid, bitmap_id, w, h, smooth=True):
    """Rectangle w x h px filled with the bitmap (clipped), origin top-left."""
    T = lambda v: int(round(v * 20))
    body = struct.pack('<H', cid) + rect(0, T(w), 0, T(h))
    # fill style: 0x41 clipped bitmap (smoothed) / 0x43 clipped non-smoothed
    body += bytes([1, 0x41 if smooth else 0x43]) + struct.pack('<H', bitmap_id) + matrix(0, 0, 20.0, 20.0)
    body += bytes([0])  # no line styles
    b = Bits(); b.u(1, 4); b.u(0, 4)
    b.u(0, 1); b.u(0, 1); b.u(0, 1); b.u(1, 1); b.u(0, 1); b.u(1, 1)  # moveTo + fillStyle1
    b.u(1, 5); b.s(0, 1); b.s(0, 1)
    b.u(1, 1)
    for dx, dy in ((T(w), 0), (0, T(h)), (-T(w), 0), (0, -T(h))):
        nb = max(sbits(dx, dy), 2)
        b.u(1, 1); b.u(1, 1); b.u(nb - 2, 4)
        if dx == 0:
            b.u(0, 1); b.u(1, 1); b.s(dy, nb)
        else:
            b.u(0, 1); b.u(0, 1); b.s(dx, nb)
    b.u(0, 1); b.u(0, 5)
    body += b.flush()
    return tag(32, body)


def matrix_raw(a, b, c, d, tx, ty):
    """SWF MATRIX from a full 2x3 affine (px translation). x' = a*x + c*y + tx ; y' = b*x + d*y + ty."""
    bb = Bits()
    if abs(a - 1) > 1e-6 or abs(d - 1) > 1e-6:
        A = int(round(a * 65536)); D = int(round(d * 65536))
        nb = sbits(A, D); bb.u(1, 1); bb.u(nb, 5); bb.s(A, nb); bb.s(D, nb)
    else:
        bb.u(0, 1)
    if abs(b) > 1e-6 or abs(c) > 1e-6:
        B = int(round(b * 65536)); C = int(round(c * 65536))
        nb = sbits(B, C); bb.u(1, 1); bb.u(nb, 5); bb.s(B, nb); bb.s(C, nb)
    else:
        bb.u(0, 1)
    TX = int(round(tx * 20)); TY = int(round(ty * 20))
    if TX == 0 and TY == 0:
        bb.u(0, 5)
    else:
        nb = sbits(TX, TY); bb.u(nb, 5); bb.s(TX, nb); bb.s(TY, nb)
    return bb.flush()


def define_sprite_raw(cid, frames):
    """frames: list of frames; each frame is a list of (shapeCid, (a,b,c,d,tx,ty), alpha).
    Depth = index in the list."""
    body = struct.pack('<HH', cid, len(frames))
    prev = {}
    for fr in frames:
        cur = {}
        for dpt, (pc, m, al) in enumerate(fr, start=1):
            mb = matrix_raw(*m)
            cxb = cxform_alpha(1, 1, 1, max(0.0, min(1.0, al))) if al < 0.999 else cxform_alpha()
            key = (pc, mb, cxb)
            cur[dpt] = key
            if prev.get(dpt) == key:
                continue
            if dpt in prev and prev[dpt][0] == pc:
                body += place2(dpt, None, mb, cxb, move=True)
            elif dpt in prev:
                body += place2(dpt, pc, mb, cxb, move=True)
            else:
                body += place2(dpt, pc, mb, cxb)
        for dpt in prev:
            if dpt not in cur:
                body += remove2(dpt)
        prev = cur
        body += tag(1, b'')
    body += tag(0, b'')
    return tag(39, body)


def abc_for_bitmapdata_classes(names):
    """`public class <Name> extends flash.display.BitmapData { function <Name>(w, h) { super(w, h); } }`
    One script per class, protected namespace, base-class scope chain - the
    layout Flash's own compiler emits for linked bitmap symbols."""
    strings = ["", "flash.display", "Object", "BitmapData"] + list(names)
    S = {}
    for st in strings:
        if st not in S:
            S[st] = len(S) + 1
    out = bytearray(struct.pack('<HH', 16, 46))
    out += u30(0) + u30(0) + u30(0)
    out += u30(len(S) + 1)
    for st in S:
        e = st.encode('utf-8'); out += u30(len(e)) + e
    out += u30(3 + len(names))
    out += bytes([0x16]) + u30(S[""]) + bytes([0x16]) + u30(S["flash.display"])
    for n in names:
        out += bytes([0x18]) + u30(S[n])
    out += u30(0)
    out += u30(3 + len(names))
    out += bytes([0x07]) + u30(1) + u30(S["Object"])          # 1 Object
    out += bytes([0x07]) + u30(2) + u30(S["BitmapData"])      # 2 flash.display.BitmapData
    for n in names:
        out += bytes([0x07]) + u30(1) + u30(S[n])
    CM = lambda i: 3 + i
    N = len(names)
    out += u30(3 * N)
    for i in range(N):
        out += u30(0) + u30(0) + u30(0) + bytes([0])               # cinit
        out += u30(2) + u30(0) + u30(0) + u30(0) + u30(0) + bytes([0])  # iinit(w, h)
        out += u30(0) + u30(0) + u30(0) + bytes([0])               # script init
    out += u30(0)
    out += u30(N)
    for i in range(N):
        out += u30(CM(i)) + u30(2) + bytes([0x08]) + u30(3 + i) + u30(0) + u30(3 * i + 1) + u30(0)
    for i in range(N):
        out += u30(3 * i) + u30(0)
    out += u30(N)
    for i in range(N):
        out += u30(3 * i + 2) + u30(1) + u30(CM(i)) + bytes([0x04]) + u30(1) + u30(i)
    out += u30(3 * N)
    cinit = bytes([0xD0, 0x30, 0x47])
    iinit = bytes([0xD0, 0x30, 0xD0, 0xD1, 0xD2, 0x49]) + u30(2) + bytes([0x47])
    for i in range(N):
        code = bytearray([0xD0, 0x30, 0x65, 0x00])
        code += bytes([0x60]) + u30(1) + bytes([0x30]) + bytes([0x60]) + u30(2) + bytes([0x30])
        code += bytes([0x60]) + u30(2) + bytes([0x58]) + u30(i) + bytes([0x1D, 0x1D])
        code += bytes([0x68]) + u30(CM(i)) + bytes([0x47])
        d = 4   # global + Object + BitmapData + class
        out += u30(3 * i) + u30(1) + u30(1) + u30(d) + u30(d + 1) + u30(len(cinit)) + cinit + u30(0) + u30(0)
        out += u30(3 * i + 1) + u30(3) + u30(3) + u30(d + 1) + u30(d + 2) + u30(len(iinit)) + iinit + u30(0) + u30(0)
        out += u30(3 * i + 2) + u30(2) + u30(1) + u30(1) + u30(d) + u30(len(code)) + bytes(code) + u30(0) + u30(0)   # global + Object + BitmapData pushed
    return bytes(out)
