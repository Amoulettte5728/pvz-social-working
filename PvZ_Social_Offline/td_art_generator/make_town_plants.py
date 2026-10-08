"""Garden-plot plant SWFs for the town (TownPlant_* classes).

The original Social Edition garden plot (Plant_SnowPeashooter.swf) is a small
crop field: frames 1-20 seedlings, 21-50 six young plants, 51-80 seven grown
plants (some mirrored). This script copies that exact layout from the Snow Pea
plot and fills it with the PvZ 1 FLA plants playing their idle animation, each
plant starting at a different idle frame so they do not sway in sync.

usage: make_town_plants.py <snowpea_plot.swf> <out_dir>
"""
import os, sys, math, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swfw import *
from swfsyms import tags
import fla_plants as FP

SNOW, OUT = sys.argv[1], sys.argv[2]

# ---------------------------------------------------------------- read the reference layout
def _bits(b, p, n): return ''.join(f'{x:08b}' for x in b[p:p + n])


def _matrix(b, p):
    bits = _bits(b, p, 40); q = [0]
    def rd(n, signed=True):
        v = int(bits[q[0]:q[0] + n], 2) if n else 0
        if signed and n and v >> (n - 1): v -= (1 << n)
        q[0] += n; return v
    a = d = 1.0; b_ = c = 0.0
    if rd(1, False):
        n = rd(5, False); a = rd(n) / 65536; d = rd(n) / 65536
    if rd(1, False):
        n = rd(5, False); b_ = rd(n) / 65536; c = rd(n) / 65536
    n = rd(5, False); tx = rd(n) / 20; ty = rd(n) / 20
    return (a, b_, c, d, tx, ty)


def reference_layout(path):
    v, t = tags(path)
    main = None
    for c, b in t:
        if c == 39 and struct.unpack_from('<H', b, 2)[0] > 10:
            main = b
    p = 4; frame = 1; display = {}; snap = {}
    while p < len(main):
        h = struct.unpack_from('<H', main, p)[0]; code = h >> 6; ln = h & 63; hp = 2
        if ln == 63: ln = struct.unpack_from('<I', main, p + 2)[0]; hp = 6
        body = main[p + hp:p + hp + ln]; p += hp + ln
        if code == 26:
            fl = body[0]; depth = struct.unpack_from('<H', body, 1)[0]; q = 3
            ent = dict(display.get(depth, {}))
            if fl & 2: ent['ch'] = struct.unpack_from('<H', body, q)[0]; q += 2
            if fl & 4: ent['M'] = _matrix(body, q)
            display[depth] = ent
        if code == 28: display.pop(struct.unpack_from('<H', body, 0)[0], None)
        if code == 1:
            if frame in (1, 21, 51): snap[frame] = [e for _, e in sorted(display.items())]
            frame += 1
        if code == 0: break
    def groups(items, size):
        out = []
        for i in range(0, len(items) - size + 1, size):
            g = items[i:i + size]
            a, b_, c, d, tx, ty = g[0]['M']
            out.append(dict(x=tx, y=ty, scale=math.hypot(a, b_), flip=a < 0))
        return out
    return groups(snap[1], 3), groups(snap[21], 4), groups(snap[51], 4)


SEEDLINGS, YOUNG, GROWN = reference_layout(SNOW)

# ---------------------------------------------------------------- plants
ALL_TARGETS = {
    # class name: (battle clip, total frames, stage ranges = conf_1_.xml <plantAnimator>, idle engine frames)
    'TownPlant_Peashooter': ('Plant_Peashooter', 80, ((1, 20), (21, 50), (51, 80)), (1, 25)),
    'TownPlant_Sunflower': ('Plant_Sunflower', 70, ((1, 20), (21, 45), (46, 70)), (1, 25)),
    'TownPlant_Repeater': ('Plant_Repeater', 80, ((1, 20), (21, 50), (51, 80)), (1, 25)),
    'TownPlant_CherryBomb': ('Plant_CherryBomb', 88, ((1, 20), (21, 54), (55, 88)), (1, 13)),
    'TownPlant_SunShroom': ('Plant_SunShroom', 70, ((1, 20), (21, 45), (46, 70)), (35, 46)),
    'TownPlant_Wallnut': ('Plant_Wallnut', 50, ((1, 20), (21, 35), (36, 50)), (1, 17)),
    'TownPlant_LilyPad': ('Plant_LilyPad', 80, ((1, 20), (21, 50), (51, 80)), (1, 1)),
    'TownPlant_PotatoMine': ('Plant_PotatoMine', 70, ((1, 20), (21, 45), (46, 70)), (22, 32)),
    'TownPlant_Squash': ('Plant_Squash', 80, ((1, 20), (21, 50), (51, 80)), (1, 19)),
    'TownPlant_Jalapeno': ('Plant_Jalapeno', 70, ((1, 20), (21, 45), (46, 70)), (1, 7)),
}
ONLY = sys.argv[3:]   # optional: class names to build
TARGETS = {k: v for k, v in ALL_TARGETS.items() if not ONLY or k in ONLY}
SIZE = {'young': 0.42, 'grown': 0.47}   # plant size relative to the battle art
SEED_SCALE = 0.62

defs = []; _next = [1]; _shapes = {}


def cid():
    c = _next[0]; _next[0] += 1; return c


def shape_for(key, im):
    if key not in _shapes:
        bid = cid(); defs.append(define_bits_lossless2(bid, im))
        sid = cid(); defs.append(define_bitmap_shape(sid, bid, im.width, im.height))
        _shapes[key] = sid
    return _shapes[key]


def base_point(frame):
    """Bottom-centre of the plant's visible pixels (where it stands)."""
    xs = []; ys = []
    for key, im, M, a in frame:
        bb = im.getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox()
        if not bb: continue
        a_, b_, c_, d_, tx, ty = M
        for x, y in ((bb[0], bb[1]), (bb[2], bb[1]), (bb[0], bb[3]), (bb[2], bb[3])):
            xs.append(a_ * x + c_ * y + tx); ys.append(b_ * x + d_ * y + ty)
    return ((min(xs) + max(xs)) / 2.0, max(ys))


def place(frame, inst_x, inst_y, s, flip, base):
    sx = -s if flip else s
    T = (sx, 0, 0, s, inst_x - sx * base[0], inst_y - s * base[1])
    out = []
    for key, im, M, a in frame:
        out.append((shape_for(key, im), FP.mul(T, M), a))
    return out


sprout_doc = FP.doc('PeaShooterSingle')
sprout = sprout_doc.image('anim_sprout.png')
sprout_sid = shape_for(('sprout',), sprout)

exports = []
for cls, (battle, total, stages, idle_rng) in TARGETS.items():
    spec = FP.SPECS[battle]
    import json as _json
    _rows = _json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plant_rows.json')))
    allf = FP.build(battle, idle_rng[1], _rows)        # engine frames 1..end (rows give hurt/state info)
    idle = allf[idle_rng[0] - 1:idle_rng[1]]          # the idle animation used in the garden
    base = base_point(idle[0])
    frames = []
    for f in range(1, total + 1):
        parts = []
        if f <= stages[0][1]:
            for i, g in enumerate(SEEDLINGS):
                bob = 1.0 + 0.04 * math.sin((f + i * 3) * 2 * math.pi / 20.0)
                s = SEED_SCALE * g['scale']
                sx = -s if g['flip'] else s
                parts.append((sprout_sid, (sx, 0, 0, s * bob, g['x'] - sx * sprout.width / 2.0,
                                           g['y'] - s * bob * sprout.height), 1.0))
        else:
            layout, size = (YOUNG, SIZE['young']) if f <= stages[1][1] else (GROWN, SIZE['grown'])
            # draw back-to-front by y so nearer plants overlap farther ones
            for i, g in sorted(enumerate(layout), key=lambda e: e[1]['y']):
                fr = idle[(f * 1 + i * 7) % len(idle)]
                parts += place(fr, g['x'], g['y'], size * g['scale'] / 0.906, g['flip'], base)
        frames.append(parts)
    c = cid(); defs.append(define_sprite_raw(c, frames)); exports.append((c, cls))

    os.makedirs(OUT, exist_ok=True)
    fname = 'Plant_' + cls[len('TownPlant_'):] + '.swf'
    data = build_swf(defs, [exports[-1]])
    open(os.path.join(OUT, fname), 'wb').write(data)
    print(fname, cls, total, 'frames,', len(data), 'bytes')
    defs.clear(); _shapes.clear(); exports.clear(); _next[0] = 1
    sprout_sid = shape_for(('sprout',), sprout)
