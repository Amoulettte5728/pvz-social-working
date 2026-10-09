"""pvzBonusZombie_1_.swf from the home-made rabbit-imp SWFs (Zombie_bonus.swf /
Zombie_bonus_charred.swf). Frames were rendered on white and on black; exact
alpha is recovered from the difference, then each frame becomes a bitmap.
usage: make_bonus_zombie.py <white_dir> <black_dir> <charred_white> <charred_black> <out.swf>"""
import os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from swfw import *

WN, BN, WC, BC, OUT = sys.argv[1:6]
OFFSET = (47, 50)        # rabbit feet (50,130 in its stage) at (97,180): the bonus zombie's hit box is x 80-115, y 80-180


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
charred = [frame_of(f'{WC}/{f}.png', f'{BC}/{f}.png') for f in range(1, 37)]

# BonusZombie plays: 1-97 enter, 98-170 shake (idle loop), 171-193 die,
# 194-230 charred, 231-275 leave. Your file: 1-79 arrive + laugh, 79-119 the
# sign-holding idle (frame 119 == frame 79, so 80-119 loops seamlessly),
# 120-166 the hand grabs him and pulls him away, 169-191 die.
# The idle loop must stop before 120, or the grab would play (and repeat)
# while he is still standing there.
IDLE = list(range(80, 120))            # 40 frames, seamless
def idle_at(i):                        # i = position in the idle cycle (float ok)
    return src[IDLE[int(i) % len(IDLE)]]
def stretch(seq, n):
    return [seq[min(len(seq) - 1, int(i * len(seq) / float(n)))] for i in range(n)]
leave = [src[f] for f in range(120, 167)]
die = [src[f] for f in range(169, 192)]        # 23 frames = body 171-193
body = []
for f in range(1, 276):
    if f <= 97:
        body.append(src[f])                     # 80-97 are already the start of the idle cycle
    elif f <= 170:
        # 73 body frames = exactly 2 idle cycles, starting where 97 left off
        # (user 98 = cycle index 18) and ending just before it, so the
        # 170 -> 98 wrap is seamless.
        body.append(idle_at(18 + (f - 98) * 2 * len(IDLE) / 73.0))
    elif f <= 193:
        body.append(die[f - 171])
    elif f <= 230:
        body.append(charred[min(f - 194, len(charred) - 1)])
    else:
        body.append(stretch(leave, 45)[f - 231])
dots = [[(DOT, (1, 0, 0, 1, OFFSET[0], OFFSET[1]), 1.0)] for _ in range(275)]

exports = []
for name, frames in (('Zombie_Bonus', body), ('bonus_head', dots), ('bonus_other', dots), ('BonusZombie_Charred', charred)):
    c = cid(); defs.append(define_sprite_raw(c, frames)); exports.append((c, name))
data = build_swf(defs, exports)
open(OUT, 'wb').write(data)
print(OUT, len(data), 'bytes;', len(_cache), 'distinct frame bitmaps;', [(n, len(fr)) for n, fr in (('Zombie_Bonus', body), ('BonusZombie_Charred', charred))])
