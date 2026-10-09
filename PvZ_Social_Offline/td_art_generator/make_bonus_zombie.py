"""pvzBonusZombie_1_.swf from the home-made rabbit-imp SWFs (Zombie_bonus.swf /
Zombie_bonus_charred.swf). Frames were rendered on white and on black; exact
alpha is recovered from the difference, then each frame becomes a bitmap.
usage: make_bonus_zombie.py <white_dir> <black_dir> <charred_white> <charred_black> <out.swf>"""
import os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from swfw import *

WN, BN, WC, BC, OUT = sys.argv[1:6]
OFFSET = (-30, -71)      # rabbit's feet (50,130 in its stage) on the zombie's tile, like a normal zombie (feet ~20,59)


def unmatte(w, b):
    w = w.convert('RGB'); b = b.convert('RGB')
    out = Image.new('RGBA', w.size)
    wp, bp = w.load(), b.load(); op = out.load()
    for y in range(w.size[1]):
        for x in range(w.size[0]):
            wr, wg, wb = wp[x, y]; br, bg, bb = bp[x, y]
            a = 255 - ((wr - br) + (wg - bg) + (wb - bb)) / 3.0
            a = max(0, min(255, int(round(a))))
            if a == 0:
                op[x, y] = (0, 0, 0, 0)
            else:
                op[x, y] = tuple(min(255, int(round(c * 255.0 / a))) for c in (br, bg, bb)) + (a,)
    return out


defs = []; _n = [1]; _cache = {}
def cid():
    c = _n[0]; _n[0] += 1; return c


def shape_of(im):
    bb = im.getchannel('A').getbbox()
    if not bb:
        return None
    crop = im.crop(bb)
    key = hashlib.md5(crop.tobytes() + bytes(str(crop.size), 'ascii')).hexdigest()
    if key not in _cache:
        bid = cid(); defs.append(define_bits_lossless2(bid, crop))
        sid = cid(); defs.append(define_bitmap_shape(sid, bid, crop.width, crop.height))
        _cache[key] = (sid, bb[0], bb[1])
    return _cache[key]


dot_img = Image.new('RGBA', (1, 1), (0, 0, 0, 1))
dbid = cid(); defs.append(define_bits_lossless2(dbid, dot_img))
DOT = cid(); defs.append(define_bitmap_shape(DOT, dbid, 1, 1))


def frame_of(path_w, path_b):
    if not (os.path.exists(path_w) and os.path.exists(path_b)):
        return [(DOT, (1, 0, 0, 1, OFFSET[0], OFFSET[1]), 1.0)]
    im = unmatte(Image.open(path_w), Image.open(path_b))
    s = shape_of(im)
    if s is None:
        return [(DOT, (1, 0, 0, 1, OFFSET[0], OFFSET[1]), 1.0)]
    sid, x, y = s
    return [(sid, (1, 0, 0, 1, OFFSET[0] + x, OFFSET[1] + y), 1.0)]


src = {f: frame_of(f'{WN}/{f}.png', f'{BN}/{f}.png') for f in range(1, 192)}
body = []
for f in range(1, 276):
    if f <= 190:
        body.append(src[f])
    elif f < 231:
        body.append([(DOT, (1, 0, 0, 1, OFFSET[0], OFFSET[1]), 1.0)])
    else:                               # 231..275: leave = arrival (97 -> 2) played backwards
        k = 97 - int(round((f - 231) * (95.0 / 44.0)))
        body.append(src[max(2, min(97, k))])
dots = [[(DOT, (1, 0, 0, 1, OFFSET[0], OFFSET[1]), 1.0)] for _ in range(275)]
charred = [frame_of(f'{WC}/{f}.png', f'{BC}/{f}.png') for f in range(1, 37)]

exports = []
for name, frames in (('Zombie_Bonus', body), ('bonus_head', dots), ('bonus_other', dots), ('BonusZombie_Charred', charred)):
    c = cid(); defs.append(define_sprite_raw(c, frames)); exports.append((c, name))
data = build_swf(defs, exports)
open(OUT, 'wb').write(data)
print(OUT, len(data), 'bytes;', len(_cache), 'distinct frame bitmaps;', [(n, len(fr)) for n, fr in (('Zombie_Bonus', body), ('BonusZombie_Charred', charred))])
