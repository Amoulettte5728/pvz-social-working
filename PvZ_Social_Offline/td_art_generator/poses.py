"""Compose battle-plant poses from the Social Edition sprite parts.

Each plant function returns {state: PIL.Image}. Every pose is drawn on the
same canvas (CW x CH) with the plant standing on the ground line GY, centred
on CX, so poses of one plant line up with each other in the SWF.
"""
import os, math
from PIL import Image

ROOT = os.environ.get('PVZ_SPRITES', '/home/claude/spr/social edition plants')
CW, CH, CX, GY = 140, 150, 70, 140
_cache = {}


def part(folder, pid):
    key = (folder, pid)
    if key not in _cache:
        d = os.path.join(ROOT, folder)
        f = None
        for ext in ('png', 'jpg'):
            p = os.path.join(d, f'pvzPlant[1]-{pid}.{ext}')
            if os.path.exists(p):
                f = p; break
        if f is None:
            raise FileNotFoundError(f'{folder} part {pid}')
        _cache[key] = Image.open(f).convert('RGBA')
    return _cache[key]


def canvas():
    return Image.new('RGBA', (CW, CH), (0, 0, 0, 0))


def put(cv, img, x, y, rot=0.0, s=1.0, sx=None, sy=None, anchor=(0.5, 0.5), alpha=1.0):
    """Paste img so that its anchor point (fraction of its size) lands on (x, y).
    rot in degrees (counter-clockwise), s uniform scale."""
    sx = s if sx is None else sx; sy = s if sy is None else sy
    im = img
    if sx != 1 or sy != 1:
        im = im.resize((max(1, round(im.width * sx)), max(1, round(im.height * sy))), Image.LANCZOS)
    ax, ay = im.width * anchor[0], im.height * anchor[1]
    if rot:
        # rotate around the anchor: pad so the anchor is the centre, then rotate
        w, h = im.size
        R = int(math.ceil(math.hypot(max(ax, w - ax), max(ay, h - ay)))) + 2
        pad = Image.new('RGBA', (2 * R, 2 * R), (0, 0, 0, 0))
        pad.paste(im, (int(round(R - ax)), int(round(R - ay))), im)
        im = pad.rotate(rot, resample=Image.BICUBIC)
        ax, ay = R, R
    if alpha < 1:
        a = im.getchannel('A').point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
    cv.alpha_composite(im, (int(round(x - ax)), int(round(y - ay)))) if (x - ax >= 0 and y - ay >= 0) else _paste_clip(cv, im, int(round(x - ax)), int(round(y - ay)))
    return cv


def _paste_clip(cv, im, x, y):
    tmp = Image.new('RGBA', cv.size, (0, 0, 0, 0)); tmp.paste(im, (x, y), im); cv.alpha_composite(tmp)


def trim_bottom_center(img):
    return img


# ---------------- shared rigs ----------------
def shooter(folder, head, snout, extra_back=None, extra_front=None, leaves=118, stem=119, fire=False,
            blink=None, head_s=1.0, snout_dx=0):
    cv = canvas()
    put(cv, part(folder, leaves), CX - 2, GY - 14)
    put(cv, part(folder, stem), CX - 2, GY - 38, s=1.25)
    hx, hy = CX - 6, GY - 72
    if fire:
        hx -= 4
    if extra_back:
        for pid, dx, dy, r, s in extra_back:
            put(cv, part(folder, pid), hx + dx, hy + dy, rot=r, s=s)
    sn = part(folder, snout)
    put(cv, sn, hx + 34 + snout_dx + (6 if fire else 0), hy + 4, sx=(1.25 if fire else 1.0), sy=(0.9 if fire else 1.0))
    put(cv, part(folder, head), hx, hy, s=head_s)
    if blink:
        put(cv, part(folder, blink), hx + 6, hy - 10)
    if extra_front:
        for pid, dx, dy, r, s in extra_front:
            put(cv, part(folder, pid), hx + dx, hy + dy, rot=r, s=s)
    return cv


def peashooter():
    return {'idle': shooter('peashooter', 122, 123), 'fire': shooter('peashooter', 122, 123, fire=True)}


def repeater():
    back = [(118, -24, -22, 35, 0.55)]
    return {'idle': shooter('repeater', 122, 123, extra_back=back), 'fire': shooter('repeater', 122, 123, extra_back=back, fire=True)}


def snowpea():
    back = [(382, -30, -26, 20, 0.9), (383, -34, -2, 0, 0.8)]
    return {'idle': shooter('snow pea', 384, 385, extra_back=back), 'fire': shooter('snow pea', 384, 385, extra_back=back, fire=True)}


def gatling():
    def g(fire):
        cv = canvas()
        put(cv, part('gatling pea', 246), CX - 2, GY - 14)
        put(cv, part('gatling pea', 119), CX - 2, GY - 38, s=1.25)
        hx, hy = CX - 10 - (4 if fire else 0), GY - 72
        put(cv, part('gatling pea', 251), hx + 52 + (6 if fire else 0), hy + 6, s=1.0)
        put(cv, part('gatling pea', 250), hx + 34, hy + 5, s=0.8)
        put(cv, part('gatling pea', 249), hx, hy)
        put(cv, part('gatling pea', 253), hx - 4, hy - 22, s=0.8)
        return cv
    return {'idle': g(False), 'fire': g(True)}


def sunflower_rig(folder, face, petals, leaves, stem, glow=False):
    cv = canvas()
    put(cv, part(folder, leaves), CX, GY - 14)
    put(cv, part(folder, stem), CX, GY - 38, s=1.3)
    fx, fy = CX, GY - 78
    ps = [part(folder, p) for p in petals]
    n = len(ps)
    for i, p in enumerate(ps):
        a = 2 * math.pi * i / n
        put(cv, p, fx + 26 * math.cos(a), fy + 24 * math.sin(a), rot=-math.degrees(a) - 90, s=1.35)
    put(cv, part(folder, face), fx, fy, s=0.95)
    if glow:
        g = canvas(); put(g, part(folder, face), fx, fy, s=1.0)
    return cv


def sunflower():
    petals = list(range(62, 81))
    return {'idle': sunflower_rig('sunflower', 81, petals, 59, 60)}


def twinsun():
    cv = canvas()
    put(cv, part('twin sun flower', 156), CX, GY - 14)
    put(cv, part('twin sun flower', 155), CX - 12, GY - 44, rot=12)
    put(cv, part('twin sun flower', 155), CX + 12, GY - 44, rot=-12)
    for dx, dy in ((-24, -84), (24, -92)):
        put(cv, part('twin sun flower', 159), CX + dx, GY + dy, s=0.72)
        put(cv, part('twin sun flower', 160), CX + dx, GY + dy, s=0.62)
    return {'idle': cv}


def whole(folder, pid, s=1.0, dy=0, dx=0):
    cv = canvas(); im = part(folder, pid)
    put(cv, im, CX + dx, GY + dy, s=s, anchor=(0.5, 1.0)); return cv


def wallnut():
    return {'idle': whole('wall-nut', 51, 0.78), 'hurt1': whole('wall-nut', 52, 0.78), 'hurt2': whole('wall-nut', 53, 0.78)}


def tallnut():
    return {'idle': whole('tall-nut', 304, 0.82), 'hurt1': whole('tall-nut', 305, 0.82), 'hurt2': whole('tall-nut', 306, 0.83)}


def vinenut():
    return {'idle': whole('vine nut', 406, 0.4), 'hurt1': whole('vine nut', 410, 0.4), 'hurt2': whole('vine nut', 412, 0.4)}


def cherry():
    def c(swell):
        cv = canvas(); s = 1.0 + 0.25 * swell
        put(cv, part('cherry bomb', 19), CX + 2, GY - 58, s=0.9)
        put(cv, part('cherry bomb', 14), CX - 16, GY - 60, s=1.0, rot=-10)
        put(cv, part('cherry bomb', 29), CX - 20, GY - 30, s=0.75 * s)
        put(cv, part('cherry bomb', 30), CX + 20, GY - 26, s=0.75 * s)
        put(cv, part('cherry bomb', 17), CX - 20, GY - 36, s=0.9)
        put(cv, part('cherry bomb', 22), CX + 20, GY - 32, s=0.9)
        put(cv, part('cherry bomb', 27), CX - 6, GY - 76, s=0.9)
        return cv
    return {'idle': c(0), 'swell': c(1)}


def potato():
    def p(armed, light):
        cv = canvas()
        if armed:
            put(cv, part('potato mine', 128), CX, GY, s=0.72, anchor=(0.5, 1.0))
            put(cv, part('potato mine', 129), CX, GY - 22, s=0.72)
            put(cv, part('potato mine', 136 if light else 134), CX, GY - 50, s=0.45)
        else:
            put(cv, part('potato mine', 126), CX, GY - 6, s=1.0)
            put(cv, part('potato mine', 127), CX + 12, GY - 4, s=0.8)
        return cv
    return {'buried': p(False, False), 'armed': p(True, False), 'blink': p(True, True)}


def chomper_rig(f, ids, pose, s=0.85, chew_ball=None):
    up, lo, lip, stem, l1, l2 = ids
    cv = canvas()
    put(cv, part(f, l1), CX - 20, GY - 10, rot=15)
    put(cv, part(f, l2), CX + 18, GY - 10, rot=-10)
    put(cv, part(f, stem), CX - 8, GY - 34, s=1.5, rot=-10)
    hx, hy = CX + 4, GY - 66
    if pose == 'chew':
        put(cv, part(f, chew_ball), hx, hy, s=1.25 * s / 0.85)
        return cv
    ux, uy, ur, lr = {'idle': (14, -20, -8, 0), 'open': (12, -32, 40, -20), 'shut': (8, -8, -26, 6)}[pose]
    put(cv, part(f, lo), hx, hy + 8, rot=lr, s=s)
    put(cv, part(f, lip), hx + 2, hy + 8, rot=lr, s=s)
    put(cv, part(f, up), hx + ux, hy + uy, rot=ur, s=s)
    return cv


def chomper():
    ids = (186, 181, 182, 171, 173, 183)
    return {p: chomper_rig('chomper', ids, p, chew_ball=189) for p in ('idle', 'open', 'shut', 'chew')}


def superchomper():
    ids = (342, 338, 339, 328, 330, 340)
    return {p: chomper_rig('super chomper', ids, p, s=0.72, chew_ball=347) for p in ('idle', 'open', 'shut', 'chew')}


def squash():
    return {'idle': whole('squash', 110, 0.78)}


def shroom(folder, body, cap, eye=None, s=1.0, cap_dy=-30, body_dy=0, cap_s=1.0, eye_pos=(0, -8), eye_gap=10, eye_s=1.0,
           sleep=False, face=None, sleepface=None):
    cv = canvas()
    put(cv, part(folder, body), CX, GY + body_dy, s=s, anchor=(0.5, 1.0))
    bh = part(folder, body).height * s
    put(cv, part(folder, cap), CX, GY - bh + cap_dy * s + body_dy, s=s * cap_s, anchor=(0.5, 0.5))
    if sleep and sleepface is not None:
        put(cv, part(folder, sleepface), CX, GY - bh * 0.45, s=s)
    elif face is not None:
        put(cv, part(folder, face), CX, GY - bh * 0.5, s=s)
    elif eye is not None and not sleep:
        e = part(folder, eye)
        for k in (-1, 1):
            put(cv, e, CX + eye_pos[0] + k * eye_gap * s, GY - bh * 0.55 + eye_pos[1] * s, s=s * eye_s)
    if sleep:
        a = cv.split()
        dark = Image.merge('RGBA', [c.point(lambda v: int(v * 0.72)) for c in a[:3]] + [a[3]])
        return dark
    return cv


def mk_shroom(**kw):
    return {'idle': shroom(**kw), 'sleep': shroom(sleep=True, **kw)}


def puff():
    return mk_shroom(folder='puff-shroom', body=45, cap=48, eye=47, s=0.62, cap_dy=-4, eye_gap=8, eye_s=0.9)


def sunshroom():
    return mk_shroom(folder='sun-shroom', body=42, cap=43, s=0.72, cap_dy=-10, sleepface=44)


def fume():
    return mk_shroom(folder='fume-shroom', body=299, cap=300, eye=302, s=0.8, cap_dy=-18, eye_gap=12)


def scaredy():
    return mk_shroom(folder='scaredy-shroom', body=288, cap=293, eye=291, s=0.9, cap_dy=-8, eye_gap=6, eye_pos=(0, -30))


def seashroom():
    def s(sleep):
        cv = canvas()
        put(cv, part('sea-shroom', 141), CX, GY - 6, s=0.9)
        put(cv, part('sea-shroom', 142), CX, GY - 22, s=0.9)
        put(cv, part('sea-shroom', 144), CX, GY - 42, s=0.9)
        if not sleep:
            for k in (-1, 1):
                put(cv, part('sea-shroom', 146), CX + k * 8, GY - 24, s=0.9)
        if sleep:
            a = cv.split(); cv = Image.merge('RGBA', [c.point(lambda v: int(v * 0.72)) for c in a[:3]] + [a[3]])
        return cv
    return {'idle': s(False), 'sleep': s(True)}


def magnet():
    def m(sleep, used=False):
        cv = canvas()
        put(cv, part('magnet shroom', 307), CX, GY - 14, s=1.3)
        put(cv, part('magnet shroom', 308), CX, GY - 34, s=1.15)
        put(cv, part('magnet shroom', 316 if used else 309), CX, GY - 66, s=0.5)
        return shroom_dark(cv) if sleep else cv
    return {'idle': m(False), 'sleep': m(True), 'used': m(False, True)}


def gloom():
    return {'idle': whole('gloom-shroom', 12, 1.05, dy=-2), 'sleep': shroom_dark(whole('gloom-shroom', 13, 1.05, dy=-2)),
            'fire': whole('gloom-shroom', 12, 1.15, dy=-2)}


def shroom_dark(cv):
    a = cv.split(); return Image.merge('RGBA', [c.point(lambda v: int(v * 0.72)) for c in a[:3]] + [a[3]])


def icyfume():
    def f(sleep):
        cv = canvas()
        put(cv, part('icy fume shroom', 276), CX, GY, s=0.33, anchor=(0.5, 1.0))
        put(cv, part('icy fume shroom', 278), CX + 4, GY - 62, s=0.3)
        put(cv, part('icy fume shroom', 281 if sleep else 277), CX + 6, GY - 22, s=0.33)
        return shroom_dark(cv) if sleep else cv
    return {'idle': f(False), 'sleep': f(True)}


def fireshroom():
    def f(sleep):
        cv = canvas()
        put(cv, part('fire shroom', 420), CX, GY, s=0.4, anchor=(0.5, 1.0))
        put(cv, part('fire shroom', 421), CX, GY - 58, s=0.36)
        put(cv, part('fire shroom', 423 if sleep else 422), CX, GY - 32, s=0.38)
        return shroom_dark(cv) if sleep else cv
    return {'idle': f(False), 'sleep': f(True)}


def torch(folder, body, flames, s=1.0, bs=1.0, face=None):
    out = {}
    for i, fl in enumerate(flames):
        cv = canvas()
        put(cv, part(folder, body), CX, GY, s=bs, anchor=(0.5, 1.0))
        bh = part(folder, body).height * bs
        put(cv, part(folder, fl), CX, GY - bh + 4, s=s, anchor=(0.5, 0.85))
        out[f'flame{i}'] = cv
    out['idle'] = out['flame0']
    return out


def torchwood():
    return torch('torchwood', 258, [257, 260, 261], s=0.9, bs=0.8)


def flamewood():
    return torch('flamewood', 416, [415, 418, 419], s=0.9, bs=0.4)


def jalapeno():
    def j(sw):
        cv = canvas(); put(cv, part('jalapeno', 263), CX, GY, sx=0.85 * (1 + 0.2 * sw), sy=0.85 * (1 - 0.1 * sw), anchor=(0.5, 1.0))
        put(cv, part('jalapeno', 262), CX + 6, GY - 72, s=0.9)
        return cv
    return {'idle': j(0), 'swell': j(1)}


def pickle():
    def j(sw):
        cv = canvas(); put(cv, part('pickled pepper', 197), CX, GY, sx=0.85 * (1 + 0.2 * sw), sy=0.85 * (1 - 0.1 * sw), anchor=(0.5, 1.0))
        put(cv, part('pickled pepper', 198), CX + 4, GY - 72, s=0.9)
        put(cv, part('pickled pepper', 200), CX - 4, GY - 48, s=0.7)
        return cv
    return {'idle': j(0), 'swell': j(1)}


def coffee():
    out = {}
    f0 = part('coffee bean', 222); bb = f0.getbbox(); sc = 0.62
    for i, pid in enumerate(range(222, 234)):
        cv = canvas(); im = part('coffee bean', pid)
        put(cv, im, CX, GY - bb[3] * sc + 2, s=sc, anchor=(0.5, 0.0))
        out[f'f{i}'] = cv
    out['idle'] = out['f0']
    return out


def pumpkin():
    return {'idle': whole('pumkin', 205, 0.72, dy=-2), 'hurt1': whole('pumkin', 206, 0.72, dy=-2),
            'hurt2': whole('pumkin', 207, 0.72, dy=-2), 'back': whole('pumkin', 204, 0.72, dy=-14)}


def qiake():
    return {'idle': whole('clam chuck', 402, 0.95, dy=-2), 'hurt1': whole('clam chuck', 403, 0.95, dy=-2),
            'hurt2': whole('clam chuck', 404, 0.95, dy=-2), 'back': whole('clam chuck', 400, 0.95, dy=-14)}


def gravebuster():
    cv = canvas()
    put(cv, part('grave buster', 37), CX, GY - 20, s=1.0)
    put(cv, part('grave buster', 38), CX, GY - 34, s=0.95)
    return {'idle': cv}


def lilypad():
    return {'idle': whole('lily pad', 138, 0.7, dy=8)}


def pot():
    cv = canvas(); put(cv, part('flower pot', 275), CX, GY, s=0.72, anchor=(0.5, 1.0)); return {'idle': cv}


def spikeweed():
    cv = canvas(); put(cv, part('spikeweed', 282), CX, GY, s=0.8, anchor=(0.5, 1.0))
    up = canvas(); put(up, part('spikeweed', 282), CX, GY, sx=0.8, sy=1.0, anchor=(0.5, 1.0))
    return {'idle': cv, 'fire': up}


def blover():
    def b(spin):
        cv = canvas()
        put(cv, part('blover', 191), CX, GY - 12, s=1.2)
        put(cv, part('blover', 196 if spin else 195), CX, GY - 44, s=1.05)
        return cv
    return {'idle': b(False), 'spin': b(True)}


def cactus():
    def c(tall):
        cv = canvas()
        body = part('cactus', 86)
        put(cv, body, CX, GY, sx=0.95, sy=0.95 * (1.45 if tall else 1.0), anchor=(0.5, 1.0))
        put(cv, part('cactus', 88), CX - 26, GY - 40, s=0.8, rot=10)
        put(cv, part('cactus', 88), CX + 26, GY - 36, s=0.8, rot=-10)
        return cv
    return {'idle': c(False), 'tall': c(True)}


def cattail():
    cv = canvas()
    put(cv, part('lily pad', 138), CX, GY - 2, s=0.7, anchor=(0.5, 1.0))
    put(cv, part('cattail', 214), CX, GY - 34, s=0.95)
    put(cv, part('cattail', 216), CX + 4, GY - 44, s=0.8)
    put(cv, part('cattail', 211), CX + 30, GY - 70, s=0.8, rot=-30)
    return {'idle': cv}


def pult(folder, basket_back, basket_front, ammo, leaves, ammo_s=1.0):
    def p(arm):
        cv = canvas()
        put(cv, part(folder, leaves), CX + 4, GY - 12)
        ang = -20 + 70 * arm
        bx = CX - 22 - 10 * math.cos(math.radians(ang)); by = GY - 60 - 26 * math.sin(math.radians(ang))
        put(cv, part(folder, basket_back), bx, by, s=0.62)
        if arm < 0.7:
            put(cv, part(folder, ammo), bx, by - 8, s=0.6 * ammo_s)
        put(cv, part(folder, basket_front), bx, by + 6, s=0.62)
        return cv
    return {'idle': p(0.0), 'throw': p(1.0)}


def pult_rig(f, body, leaves, bback, ammo, bfront, arm, body_s=0.9, ammo_s=0.72, arm_ids=None):
    cv = canvas()
    put(cv, part(f, leaves), CX + 2, GY - 12, s=0.9)
    put(cv, part(f, body), CX + 8, GY - 40, s=body_s)
    ang = math.radians(200 - 150 * arm)          # basket swings from back (left) over the head
    bx = CX + 6 + 40 * math.cos(ang); by = GY - 50 - 40 * abs(math.sin(ang))
    if arm_ids:
        for i in range(4):
            t = (i + 0.5) / 4
            put(cv, part(f, arm_ids[i % 2]), CX + 6 + (bx - CX - 6) * t, GY - 50 + (by - GY + 50) * t, s=0.7,
                rot=-math.degrees(math.atan2(by - (GY - 50), bx - (CX + 6))))
    put(cv, part(f, bback), bx, by, s=0.6)
    if arm < 0.7:
        put(cv, part(f, ammo), bx, by - 10, s=ammo_s)
    put(cv, part(f, bfront), bx, by + 6, s=0.6)
    return cv


def pult_cabbage(arm):
    return pult_rig('cabbage-pult', 244, 234, 236, 237, 238, arm, body_s=0.85, ammo_s=0.9, arm_ids=(242, 241))


def melon():
    def p(arm, winter=False):
        if winter:
            return pult_rig('winter melon', 376, 378, 372, 373, 374, arm, arm_ids=(379, 380))
        return pult_rig('melon-pult', 103, 105, 99, 100, 101, arm, arm_ids=(106, 107))
    return p


def melonpult():
    p = melon(); return {'idle': p(0.0), 'throw': p(1.0)}


def wintermelon():
    p = melon(); return {'idle': p(0.0, True), 'throw': p(1.0, True)}


def tanglekelp():
    out = {'idle': whole('tangle kelp', 357, 0.62, dy=8)}
    for i, pid in enumerate(range(348, 357)):
        out[f'grab{i}'] = whole('tangle kelp', pid, 0.9, dy=8)
    return out


def starfruit():
    return {'idle': whole('future star', 388, 0.9)}


PLANTS = {
    'Plant_Peashooter': peashooter, 'Plant_Repeater': repeater, 'Plant_Snowpea': snowpea, 'Plant_GatlingPea': gatling,
    'Plant_Sunflower': sunflower, 'Plant_TwinSunflower': twinsun, 'Plant_Wallnut': wallnut, 'Plant_Tallnut': tallnut,
    'Plant_VinyGrowthNut': vinenut, 'Plant_CherryBomb': cherry, 'Plant_PotatoMine': potato, 'Plant_Chomper': chomper,
    'Plant_ReinforcedChomper': superchomper, 'Plant_Squash': squash, 'Plant_PuffShroom': puff,
    'Plant_SunShroom': sunshroom, 'Plant_FumeShroom': fume, 'Plant_ScaredyShroom': scaredy, 'Plant_SeaShroom': seashroom,
    'Plant_MagnetShroom': magnet, 'Plant_GloomShroom': gloom, 'Plant_IceFumeShroom': icyfume,
    'Plant_FireShroom': fireshroom, 'Plant_Torchwood': torchwood, 'Plant_FireTorchWood': flamewood,
    'Plant_Jalapeno': jalapeno, 'Plant_PickleBomb': pickle, 'Plant_CoffeeBean': coffee, 'Plant_Pumpkin': pumpkin,
    'Plant_Qiake': qiake, 'Plant_GraveBuster': gravebuster, 'Plant_LilyPad': lilypad, 'Plant_Pot': pot,
    'Plant_Spikeweed': spikeweed, 'Plant_Blover': blover, 'Plant_Cactus': cactus, 'Plant_Cattail': cattail,
    'Plant_Cabbagepult': lambda: {'idle': pult_cabbage(0), 'throw': pult_cabbage(1)},
    'Plant_MelonPult': melonpult, 'Plant_WinterMelon': wintermelon, 'Plant_Tanglekelp': tanglekelp,
    'Plant_StarFruit': starfruit,
}
