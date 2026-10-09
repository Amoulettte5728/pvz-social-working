"""Build pvzTD_1_.swf: placeholder battle art for PvZ Social Offline.

Every exported clip matches a class name the battle engine asks for and has at
least as many frames as the engine plays (from PlantsConfig.PLANT_FRAME_LIST,
the plant classes' own frame constants, ZombiesConfig prop tables, LawnMower /
WaterLawnMower). Every frame draws something (BitmapUtil needs non-empty
bounds). Art is simple and replaceable: swap any clip for real art with the
same class name and at least the same frame count.
"""
import math, sys, json
import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('PVZ_SPRITES', os.path.join(HERE, 'plant_sprites'))
os.environ.setdefault('PVZ_PROJECTILES', os.path.join(HERE, 'projectiles'))
os.environ.setdefault('PVZ_ALMANAC_SWF', os.path.join(HERE, '..', 'almanac_1_.swf'))
os.environ.setdefault('PVZ_FLA', os.path.join(HERE, 'fla_extracted'))
if not os.path.isdir(os.environ['PVZ_FLA']):
    import glob, rawzip
    for _f in glob.glob(os.path.join(HERE, 'fla_sources', '*.fla')):
        rawzip.extract(_f, os.path.join(os.environ['PVZ_FLA'], os.path.splitext(os.path.basename(_f))[0]))
from swfw import *

OUT = sys.argv[1] if len(sys.argv) > 1 else 'pvzTD_1_.swf'
INK = (40, 30, 20, 255)

defs = []
_shape_cache = {}
_next = [1]


def cid():
    c = _next[0]; _next[0] += 1; return c


def shp(kind, *args, fill, line=INK, lw=1.5):
    key = (kind, args, fill, line, lw)
    if key in _shape_cache:
        return _shape_cache[key]
    if kind == 'e':
        path = ellipse(*args)
    elif kind == 'p':
        path = polygon(list(args[0]))
    elif kind == 'r':
        x, y, w, h = args; path = polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    c = cid()
    defs.append(define_shape3(c, path, fill, line, lw))
    _shape_cache[key] = c
    return c


def P(c, x=0, y=0, sx=1, sy=1, rot=0, cx=None):
    return (c, x, y, sx, sy, rot, cx)


def star(cx_, cy_, r1, r2, n=5, a0=-math.pi / 2):
    pts = []
    for i in range(2 * n):
        r = r1 if i % 2 == 0 else r2
        a = a0 + i * math.pi / n
        pts.append((round(cx_ + r * math.cos(a), 2), round(cy_ + r * math.sin(a), 2)))
    return tuple(pts)


# ---------------- palettes ----------------
GREEN = (95, 190, 60, 255); DGREEN = (50, 130, 40, 255); LGREEN = (150, 220, 90, 255)
YEL = (250, 215, 40, 255); ORANGE = (245, 140, 30, 255); BROWN = (150, 95, 45, 255)
DBROWN = (95, 60, 30, 255); RED = (215, 45, 40, 255); PURPLE = (150, 90, 190, 255)
LPURP = (200, 160, 230, 255); ICE = (150, 215, 245, 255); WHITE = (250, 250, 245, 255)
GREY = (150, 150, 155, 255); DGREY = (90, 90, 95, 255); BLACK = (20, 20, 20, 255)
PINK = (240, 150, 190, 255); TAN = (230, 200, 140, 255); BLUE = (70, 130, 220, 255)
TERRA = (190, 100, 60, 255); CREAM = (250, 240, 200, 255)

EYE_W = None


def eyes(x, y, gap=8, r=3.2, closed=False):
    if closed:
        c = shp('r', 0, 0, r * 2.2, 1.6, fill=BLACK, line=None)
        return [P(c, x - r * 1.1, y), P(c, x + gap - r * 1.1, y)]
    w = shp('e', 0, 0, r * 1.25, r * 1.4, fill=WHITE, line=INK, lw=0.8)
    k = shp('e', 0, 0, r * 0.6, r * 0.7, fill=BLACK, line=None)
    return [P(w, x, y), P(k, x + r * 0.35, y), P(w, x + gap, y), P(k, x + gap + r * 0.35, y)]


def cracks(x, y, level):
    c = shp('p', ((0, 0), (6, 5), (3, 9), (9, 15), (8, 16), (1, 10), (4, 6), (-1, 1)), fill=DBROWN, line=None)
    out = [P(c, x, y)]
    if level >= 2:
        out += [P(c, x + 14, y + 12, 1, 1, 1.2), P(c, x - 6, y + 20, 0.8, 0.8, -0.6)]
    return out


# ---------------- plant templates (return part lists for a state) ----------------
def t_shooter(head, st, kind='pea'):
    f = st['t']; bob = math.sin(f * 0.5) * 1.5
    lean = 0.0; snout = 1.0
    if st['mode'] == 'attack':
        ph = st['aphase']; lean = -0.12 * math.sin(ph * math.pi); snout = 1.0 + 0.35 * (1 if st['fire'] else 0)
    stem = shp('r', 0, 0, 5, 28, fill=DGREEN)
    leaf = shp('e', 0, 0, 12, 5, fill=DGREEN)
    hd = shp('e', 0, 0, 17, 15, fill=head)
    sn = shp('e', 0, 0, 8, 7, fill=head)
    hole = shp('e', 0, 0, 3.5, 4.5, fill=BLACK, line=None)
    parts = [P(stem, 30, 42), P(leaf, 22, 70, 1, 1, 0.3), P(leaf, 42, 70, 1, 1, -0.3)]
    hx, hy = 32 + lean * 20, 30 + bob
    if kind == 'repeater':
        parts.append(P(shp('e', 0, 0, 10, 5, fill=DGREEN), hx - 16, hy - 12, 1, 1, -0.6))
    if kind == 'gatling':
        parts.append(P(shp('e', 0, 0, 16, 8, fill=DGREY), hx, hy - 12))
    parts += [P(sn, hx + 16 + 3 * snout, hy + 1, snout, 1), P(hole, hx + 21 + 4 * snout, hy + 1), P(hd, hx, hy)]
    if kind == 'snow':
        parts.append(P(shp('p', ((0, 0), (5, -9), (9, 0), (13, -8), (16, 2)), fill=WHITE), hx - 14, hy - 10))
    if kind == 'gatling':
        parts.append(P(shp('r', 0, 0, 30, 5, fill=GREY), hx - 15, hy - 16))
    parts += eyes(hx - 2, hy - 5, 9, 3)
    return parts


def t_flower(st, petal=YEL, face=BROWN, twin=False, small=False):
    f = st['t']; sway = math.sin(f * 0.4) * 0.08
    stem = shp('r', 0, 0, 5, 30, fill=DGREEN); leaf = shp('e', 0, 0, 12, 5, fill=DGREEN)
    pe = shp('e', 0, 0, 7 if small else 9, 4.5 if small else 5, fill=petal)
    fc = shp('e', 0, 0, 10 if small else 12, 10 if small else 12, fill=face)
    parts = [P(stem, 30, 40), P(leaf, 20, 70, 1, 1, 0.3), P(leaf, 44, 70, 1, 1, -0.3)]
    heads = [(24, 28), (46, 24)] if twin else [(33, 28)]
    for (x, y) in heads:
        x += sway * 30
        R = 14 if small else 17
        for i in range(10):
            a = i * math.pi / 5 + f * 0.05
            parts.append(P(pe, x + R * math.cos(a), y + R * math.sin(a), 1, 1, a))
        parts.append(P(fc, x, y))
        parts += eyes(x - 5, y - 3, 8, 2.4)
        parts.append(P(shp('e', 0, 0, 4, 2, fill=DBROWN, line=None), x, y + 5))
    return parts


def t_nut(st, color=TAN, h=1.0, pumpkin=False):
    f = st['t']; bob = math.sin(f * 0.35) * 0.03
    body = shp('e', 0, 0, 26 if not pumpkin else 36, 30 * h if not pumpkin else 20, fill=color, lw=2)
    cy = 72 - 30 * h if not pumpkin else 58
    parts = [P(body, 34, cy, 1 + bob, 1 - bob)]
    if pumpkin:
        rib = shp('e', 0, 0, 10, 18, fill=None or (230, 120, 30, 255), line=INK, lw=1)
        parts += [P(rib, 20, cy), P(rib, 48, cy)]
    lvl = st.get('hurt', 0)
    parts += eyes(26, cy - 8 * h, 12, 4, closed=False)
    if lvl:
        parts += cracks(20, cy - 20 * h, lvl)
    return parts


def t_shroom(st, cap=PURPLE, big=1.0, spots=True):
    f = st['t']; sleeping = st['mode'] == 'sleep'
    sq = math.sin(f * (0.25 if sleeping else 0.5)) * (0.04 if sleeping else 0.06)
    if st['mode'] == 'attack' and st['fire']:
        sq = 0.15
    stem = shp('e', 0, 0, 9 * big, 11 * big, fill=CREAM)
    cp = shp('e', 0, 0, 20 * big, 13 * big, fill=cap)
    spot = shp('e', 0, 0, 3.5 * big, 3 * big, fill=WHITE, line=None)
    base = 72
    parts = [P(stem, 34, base - 10 * big, 1 - sq, 1 + sq), P(cp, 34, base - 24 * big - sq * 10, 1 + sq, 1 - sq)]
    if spots:
        parts += [P(spot, 26, base - 28 * big), P(spot, 40, base - 30 * big), P(spot, 34, base - 22 * big)]
    parts += eyes(29, base - 10 * big, 9, 2.5 * big, closed=sleeping)
    if sleeping:
        tint = (0.6, 0.6, 0.75, 1, 0, 0, 0, 0)
        parts = [p[:6] + (tint,) for p in parts]
    return parts


def t_bomb(st, color=RED, pair=False, big=1.0, shape='round'):
    f = st['t']; boom = st['mode'] == 'attack'
    s = 1.0 + (0.4 * st['aphase'] if boom else 0.03 * math.sin(f * 0.6))
    if shape == 'long':
        b = shp('e', 0, 0, 10, 26, fill=color)
        parts = [P(b, 34, 44, s, s, 0.15)]
        parts += eyes(29, 36, 8, 2.6)
        parts.append(P(shp('p', ((0, 0), (6, -10), (10, 0)), fill=DGREEN), 34, 20))
        return parts
    b = shp('e', 0, 0, 13 * big, 13 * big, fill=color)
    parts = []
    if pair:
        parts += [P(b, 24, 54, s, s), P(b, 46, 58, s, s)]
        stem = shp('p', ((0, 0), (2, 0), (12, -26), (10, -26)), fill=DGREEN, line=None)
        parts += [P(stem, 24, 44), P(stem, 36, 48, -1, 1)]
        parts += eyes(19, 50, 8, 2.5) + eyes(41, 54, 8, 2.5)
    else:
        parts += [P(b, 34, 72 - 13 * big, s, s)]
        parts += eyes(28, 66 - 13 * big, 10, 3)
    return parts


def t_pult(st, ammo=GREEN, pot=TERRA):
    f = st['t']; arm = -0.2 + 0.05 * math.sin(f * 0.4)
    if st['mode'] == 'attack':
        arm = -0.2 - 1.2 * math.sin(st['aphase'] * math.pi)
    body = shp('e', 0, 0, 20, 14, fill=DGREEN)
    stick = shp('r', 0, -3, 30, 6, fill=DBROWN)
    am = shp('e', 0, 0, 9, 8, fill=ammo)
    parts = [P(body, 34, 60), P(stick, 34, 48, 1, 1, math.pi + arm)]
    ax = 34 + 30 * math.cos(math.pi + arm); ay = 48 + 30 * math.sin(math.pi + arm)
    parts.append(P(am, ax, ay))
    parts += eyes(34, 57, 9, 3)
    return parts


def t_chomper(st, color=PURPLE, armored=False):
    f = st['t']; m = st['mode']
    jaw = 0.35 + 0.1 * math.sin(f * 0.4)
    if m == 'attack':
        jaw = 0.9 * math.sin(st['aphase'] * math.pi)
    if m == 'chew':
        jaw = 0.12 + 0.1 * math.sin(f * 1.2)
    stem = shp('r', 0, 0, 5, 34, fill=DGREEN); leaf = shp('e', 0, 0, 14, 5, fill=DGREEN)
    top = shp('p', ((0, 0), (40, 0), (34, -18), (8, -22)), fill=color)
    bot = shp('p', ((0, 0), (40, 0), (32, 14), (6, 12)), fill=color)
    teeth = shp('p', ((0, 0), (4, 5), (8, 0), (12, 5), (16, 0), (20, 5), (24, 0)), fill=WHITE, line=None)
    parts = [P(stem, 26, 40), P(leaf, 18, 72, 1, 1, 0.2), P(leaf, 40, 72, 1, 1, -0.2)]
    parts += [P(bot, 14, 40, 1, 1, jaw * 0.4), P(top, 14, 40, 1, 1, -jaw * 0.6), P(teeth, 26, 40, 1, 1, -jaw * 0.6)]
    if armored:
        parts.append(P(shp('r', 0, 0, 26, 5, fill=GREY), 18, 22, 1, 1, -jaw * 0.6))
    if m == 'chew':
        parts[3] = P(shp('e', 0, 0, 22, 16, fill=color), 30, 38)
    return parts


def t_generic(st, body, extra=lambda st: []):
    f = st['t']; bob = math.sin(f * 0.5) * 1.2
    return [(p[0], p[1], p[2] + bob, p[3], p[4], p[5], p[6]) for p in body(st)] + extra(st)


def lily(st):
    return [P(shp('e', 0, 0, 30, 10, fill=GREEN), 34, 66), P(shp('p', ((0, 0), (12, -6), (12, 6)), fill=(70, 150, 90, 255), line=None), 40, 66)]


def spikeweed(st):
    k = 1 + (0.25 if st['mode'] == 'attack' and st['fire'] else 0)
    sp = shp('p', ((0, 0), (5, -12), (10, 0)), fill=GREY)
    return [P(shp('e', 0, 0, 30, 6, fill=DGREEN), 34, 68)] + [P(sp, 8 + 11 * i, 66, 1, k) for i in range(5)]


def pot(st):
    return [P(shp('p', ((0, 0), (40, 0), (34, 26), (6, 26)), fill=TERRA), 14, 46), P(shp('r', 0, 0, 44, 6, fill=(170, 85, 50, 255)), 12, 42)]


def gravebuster(st):
    return [P(shp('e', 0, 0, 22, 12, fill=GREEN), 34, 62), P(shp('p', ((0, 0), (10, -20), (20, 0)), fill=DGREEN), 12, 60), P(shp('p', ((0, 0), (10, -20), (20, 0)), fill=DGREEN), 36, 60)] + eyes(28, 60, 10, 3)


def tanglekelp(st):
    w = math.sin(st['t'] * 0.5) * 0.15
    k = shp('e', 0, 0, 6, 26, fill=(40, 120, 70, 255))
    return [P(k, 26, 46, 1, 1, w), P(k, 42, 46, 1, 1, -w), P(shp('e', 0, 0, 16, 12, fill=(60, 150, 80, 255)), 34, 58)] + eyes(28, 55, 10, 3)


def torchwood(st, fire=ORANGE):
    fl = 1 + 0.15 * math.sin(st['t'] * 1.1)
    return [P(shp('r', 0, 0, 30, 40, fill=BROWN, lw=2), 19, 32), P(shp('p', ((0, 0), (8, -18), (14, -6), (20, -22), (28, 0)), fill=fire), 20, 32, 1, fl)] + eyes(25, 46, 12, 3.5)


def cactus(st):
    tall = 1.0
    if st['t'] >= 20:
        tall = 1.5
    body = shp('e', 0, 0, 11, 26, fill=GREEN)
    arm = shp('e', 0, 0, 6, 12, fill=GREEN)
    sp = shp('p', ((0, 0), (3, -4), (6, 0)), fill=WHITE, line=None)
    y0 = 72 - 26 * tall
    return [P(arm, 20, y0 + 20, 1, tall), P(arm, 48, y0 + 16, 1, tall), P(body, 34, y0, 1, tall), P(sp, 30, y0 - 26 * tall)] + eyes(29, y0 - 6, 9, 2.8)


def cattail(st):
    return [P(shp('e', 0, 0, 22, 8, fill=GREEN), 34, 66), P(shp('e', 0, 0, 14, 12, fill=PINK), 34, 52), P(shp('e', 0, 0, 3, 14, fill=BROWN), 48, 30, 1, 1, 0.5)] + eyes(29, 50, 9, 2.6)


def blover(st):
    lf = shp('e', 0, 0, 10, 9, fill=GREEN)
    spin = st['t'] * (0.6 if st['t'] > 32 else 0.1)
    parts = [P(shp('r', 0, 0, 4, 26, fill=DGREEN), 32, 44)]
    for i in range(4):
        a = spin + i * math.pi / 2
        parts.append(P(lf, 34 + 11 * math.cos(a), 36 + 11 * math.sin(a)))
    return parts + eyes(30, 34, 8, 2.2)


def starfruit(st):
    return [P(shp('p', star(34, 50, 24, 11), fill=YEL), 0, 0)] + eyes(28, 46, 10, 2.8)


def marigold(st):
    return t_flower(st, petal=(250, 250, 250, 255), face=ORANGE, small=True)


def coffee(st):
    s = 1 + (0.2 * st['aphase'] if st['mode'] == 'attack' else 0)
    return [P(shp('e', 0, 0, 12, 16, fill=DBROWN), 34, 56, s, s), P(shp('r', 0, 0, 2, 20, fill=BROWN, line=None), 33, 46)] + eyes(28, 52, 9, 2.5)


def magnet(st):
    parts = t_shroom(st, cap=(200, 50, 60, 255), spots=False)
    mag = shp('p', ((0, 0), (8, 0), (8, 14), (18, 14), (18, 0), (26, 0), (26, 22), (0, 22)), fill=GREY)
    return parts + [P(mag, 21, 26)]


def fume(st, cap=PURPLE):
    parts = t_shroom(st, cap=cap, big=1.2)
    parts.append(P(shp('e', 0, 0, 7, 6, fill=cap), 60, 48))
    return parts


def gloom(st):
    parts = t_shroom(st, cap=(110, 60, 140, 255), big=1.25)
    return parts + [P(shp('e', 0, 0, 5, 5, fill=(90, 40, 120, 255)), x, 48) for x in (6, 62)]


def squash(st):
    y = 0
    if st['mode'] == 'attack':
        ph = st['aphase']; y = -40 * math.sin(ph * math.pi * 0.8)
    return [P(shp('e', 0, 0, 22, 20, fill=(120, 170, 60, 255), lw=2), 34, 52 + y)] + eyes(24, 46 + y, 14, 3.5)


def potato(st):
    armed = st['t'] >= 22
    parts = [P(shp('e', 0, 0, 22, 14 if armed else 7, fill=BROWN), 34, 64 if armed else 70)]
    if armed:
        parts += [P(shp('r', 0, 0, 2, 12, fill=GREY, line=None), 33, 40), P(shp('e', 0, 0, 3.5, 3.5, fill=RED if (st['t'] // 3) % 2 else (120, 20, 20, 255), line=None), 34, 40)]
        parts += eyes(26, 60, 12, 3)
    return parts


def sea(st):
    parts = t_shroom(st, cap=(60, 170, 150, 255), big=0.85)
    return parts + [P(shp('e', 0, 0, 20, 4, fill=(100, 170, 220, 255), line=None), 34, 72)]


def grave_or(st, fn):
    return fn(st)


PLANTS = {
    'Plant_Peashooter': lambda st: t_shooter(GREEN, st),
    'Plant_Snowpea': lambda st: t_shooter(ICE, st, 'snow'),
    'Plant_Repeater': lambda st: t_shooter(GREEN, st, 'repeater'),
    'Plant_GatlingPea': lambda st: t_shooter(GREEN, st, 'gatling'),
    'Plant_Sunflower': lambda st: t_flower(st),
    'Plant_TwinSunflower': lambda st: t_flower(st, twin=True, small=True),
    'Plant_MariGold': marigold,
    'Plant_Wallnut': lambda st: t_nut(st),
    'Plant_Tallnut': lambda st: t_nut(st, color=(215, 180, 120, 255), h=1.6),
    'Plant_VinyGrowthNut': lambda st: t_nut(st, color=(170, 200, 110, 255)),
    'Plant_Pumpkin': lambda st: t_nut(st, color=ORANGE, pumpkin=True),
    'Plant_Pumpkin_back': lambda st: [P(shp('e', 0, 0, 36, 18, fill=(200, 110, 25, 255)), 34, 52)],
    'Plant_Qiake': lambda st: t_nut(st, color=(170, 140, 220, 255), pumpkin=True),
    'Plant_Qiake_back': lambda st: [P(shp('e', 0, 0, 36, 18, fill=(130, 100, 180, 255)), 34, 52)],
    'Plant_QK': lambda st: t_nut(st, color=(170, 140, 220, 255), pumpkin=True),
    'Plant_CherryBomb': lambda st: t_bomb(st, pair=True),
    'Plant_Jalapeno': lambda st: t_bomb(st, color=RED, shape='long'),
    'Plant_PickleBomb': lambda st: t_bomb(st, color=(100, 160, 50, 255), shape='long'),
    'Plant_PotatoMine': potato,
    'Plant_Squash': squash,
    'Plant_Chomper': lambda st: t_chomper(st),
    'Plant_ReinforcedChomper': lambda st: t_chomper(st, color=(120, 60, 150, 255), armored=True),
    'Plant_PuffShroom': lambda st: t_shroom(st, cap=PURPLE, big=0.7),
    'Plant_ScaredyShroom': lambda st: t_shroom(st, cap=LPURP, big=0.9),
    'Plant_SunShroom': lambda st: t_shroom(st, cap=YEL, big=0.6 if st['t'] < 23 else 0.9),
    'Plant_FumeShroom': fume,
    'Plant_IceFumeShroom': lambda st: fume(st, cap=ICE),
    'Plant_FireShroom': lambda st: fume(st, cap=ORANGE),
    'Plant_GloomShroom': gloom,
    'Plant_SeaShroom': sea,
    'Plant_MagnetShroom': magnet,
    'Plant_CoffeeBean': coffee,
    'Plant_LilyPad': lambda st: lily(st),
    'Plant_Spikeweed': spikeweed,
    'Plant_Pot': pot,
    'Plant_GraveBuster': gravebuster,
    'Plant_Tanglekelp': tanglekelp,
    'Plant_Torchwood': torchwood,
    'Plant_FireTorchWood': lambda st: torchwood(st, fire=(80, 170, 255, 255)),
    'Plant_Cactus': cactus,
    'Plant_Cattail': cattail,
    'Plant_Blover': blover,
    'Plant_StarFruit': starfruit,
    'Plant_Cabbagepult': lambda st: t_pult(st, ammo=LGREEN),
    'Plant_MelonPult': lambda st: t_pult(st, ammo=(60, 160, 70, 255)),
    'Plant_WinterMelon': lambda st: t_pult(st, ammo=ICE),
}

# frame table rows from PlantsConfig.PLANT_FRAME_LIST (by resource name)
ROWS = json.load(open(os.path.join(HERE, 'plant_rows.json')))
EXTRA_MAX = {'Plant_Cactus': 95, 'Plant_Chomper': 94, 'Plant_ReinforcedChomper': 94, 'Plant_MagnetShroom': 127,
             'Plant_PotatoMine': 32, 'Plant_ScaredyShroom': 81, 'Plant_Squash': 82, 'Plant_Blover': 62,
             'Plant_Pumpkin_back': 64, 'Plant_Qiake_back': 64, 'Plant_QK': 22}


def flat(row):
    out = []
    for v in row:
        out += v if isinstance(v, list) else [v]
    return out


def plant_state(name, f):
    row = ROWS.get(name)
    st = {'t': f, 'mode': 'idle', 'aphase': 0.0, 'fire': False, 'hurt': 0}
    if not row:
        return st
    rng = lambda a, b: a and b and a <= f <= b
    if rng(row[2], row[3]):
        st['mode'] = 'attack'; st['aphase'] = (f - row[2]) / max(1, row[3] - row[2])
        st['fire'] = any(abs(f - x) <= 2 for x in row[4])
    if rng(row[5], row[6]): st['hurt'] = 1
    if rng(row[7], row[8]): st['hurt'] = 2
    if rng(row[9], row[10]): st['mode'] = 'sleep'
    if name in ('Plant_Chomper', 'Plant_ReinforcedChomper') and f > 50:
        st['mode'] = 'chew'
    return st



# ---------------- bitmap plants (Social Edition sprite parts) ----------------
import poses as _poses
K = 0.85                 # canvas -> clip scale
ANCHOR = (34, 76)        # where the pose's ground centre lands in the clip
_bm_cache = {}


def pose_shape(name, state, img):
    key = (name, state)
    if key in _bm_cache:
        return _bm_cache[key]
    bb = img.getbbox() or (0, 0, 2, 2)
    x0, y0 = max(0, bb[0] - 1), max(0, bb[1] - 1)
    crop = img.crop((x0, y0, min(img.width, bb[2] + 1), min(img.height, bb[3] + 1)))
    bid = cid(); defs.append(define_bits_lossless2(bid, crop))
    sid = cid(); defs.append(define_bitmap_shape(sid, bid, crop.width, crop.height))
    _bm_cache[key] = (sid, x0, y0)
    _sid_size[sid] = (crop.width, crop.height)
    _sid_img[sid] = crop
    return _bm_cache[key]


def place_pose(name, state, img, sx=1.0, sy=1.0, rot=0.0, dx=0.0, dy=0.0, pivot=None, cx=None):
    sid, x0, y0 = pose_shape(name, state, img)
    px, py = pivot or (_poses.CX, _poses.GY)
    a, b = K * sx * math.cos(rot), K * sx * math.sin(rot)
    c, d = -K * sy * math.sin(rot), K * sy * math.cos(rot)
    vx, vy = x0 - px, y0 - py
    tx = ANCHOR[0] + dx + a * vx + c * vy + (px - _poses.CX) * K
    ty = ANCHOR[1] + dy + b * vx + d * vy + (py - _poses.GY) * K
    return P(sid, tx, ty, K * sx, K * sy, rot, cx)


def pick(d, *names):
    for n in names:
        if n in d:
            return n
    return 'idle'


def bitmap_frame(name, d, st, n):
    f = st['t']; m = st['mode']
    bob = math.sin(f * 2 * math.pi / 24.0)
    sx, sy, rot, dx, dy = 1.0 + 0.012 * bob, 1.0 - 0.02 * bob, 0.0, 0.0, 0.0
    state = 'idle'
    if st.get('hurt') == 1: state = pick(d, 'hurt1')
    if st.get('hurt') == 2: state = pick(d, 'hurt2')
    if m == 'sleep':
        state = pick(d, 'sleep'); sx, sy = 1.0 + 0.02 * bob, 1.0 - 0.03 * bob
    if m == 'attack':
        ph = st['aphase']
        if 'fire' in d and st['fire']:
            state = 'fire'
        if 'throw' in d:
            state = 'throw' if 0.35 < ph < 0.75 else 'idle'
        if 'swell' in d:
            state = 'swell'; k = 1 + 0.35 * ph; sx, sy = k, k
        if 'open' in d:
            state = 'open' if ph < 0.45 else 'shut'
        if 'grab0' in d:
            state = f'grab{min(8, int(ph * 9))}'
        if 'used' in d:
            state = 'used'
        if 'f0' in d and 'f11' in d:
            state = f'f{min(11, int(ph * 12))}'
        if name == 'Plant_Squash':
            dy = -40 * math.sin(min(1.0, ph * 1.25) * math.pi); sx, sy = 1.0, 1.0
        rot = -0.06 * math.sin(ph * math.pi) if 'fire' in d else 0.0
    if m == 'chew' and 'chew' in d:
        state = 'chew'; sx, sy = 1.0 + 0.05 * math.sin(f * 1.3), 1.0 - 0.05 * math.sin(f * 1.3)
    if 'flame0' in d and m != 'attack':
        state = f'flame{(f // 3) % 3}'
    if name == 'Plant_PotatoMine':
        state = 'buried' if f < 22 else ('blink' if (f // 4) % 2 else 'armed')
    if name == 'Plant_Blover':
        state = 'spin' if f >= 33 else 'idle'
        if f >= 33: rot = 0.0
    if name == 'Plant_Cactus' and f >= 20:
        state = 'tall'
    if name == 'Plant_SunShroom' and f < 23:
        sx *= 0.72; sy *= 0.72
    if name in ('Plant_Pumpkin_back', 'Plant_Qiake_back'):
        state = 'back'; sx, sy = 1.0, 1.0
    return [place_pose(name, state, d[state], sx, sy, rot, dx, dy)]


BITMAP_SRC = dict(_poses.PLANTS)
BITMAP_SRC['Plant_Pumpkin_back'] = _poses.PLANTS['Plant_Pumpkin']
BITMAP_SRC['Plant_Qiake_back'] = _poses.PLANTS['Plant_Qiake']
BITMAP_SRC['Plant_QK'] = _poses.PLANTS['Plant_Qiake']
_pose_sets = {}
for _n, _fn in BITMAP_SRC.items():
    try:
        _pose_sets[_n] = _fn()
    except Exception as _e:
        print('pose error', _n, _e)


# ---------------- FLA plants (PvZ 1 reanim sources) ----------------
try:
    import fla_plants as _fla
except Exception as _e:
    _fla = None; print('FLA converter unavailable:', _e)
_fla_shapes = {}
SHIFTS = {}
FLA_POS = (0.0, 0.0)     # FLA stage coordinates are used as clip coordinates


def fla_shape(key, im):
    if key not in _fla_shapes:
        bid = cid(); defs.append(define_bits_lossless2(bid, im))
        sid = cid(); defs.append(define_bitmap_shape(sid, bid, im.width, im.height))
        _fla_shapes[key] = sid
    return _fla_shapes[key]


_abox = {}


def _alpha_box(im):
    k = id(im)
    if k not in _abox:
        _abox[k] = im.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox() or (0, 0, 0, 0)
    return _abox[k]


def fla_bbox(frame):
    xs = []; ys = []
    for key, im, M, a in frame:
        x0, y0, x1, y1 = _alpha_box(im)
        if x1 <= x0 or a < 0.2:
            continue
        a_, b_, c_, d_, tx, ty = M
        for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            xs.append(a_ * x + c_ * y + tx); ys.append(b_ * x + d_ * y + ty)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)


def fla_frames(name, n):
    frames = _fla.build(name, n, ROWS)
    if name in ('LawnMower', 'PoolCleaner'):
        k = MOWER_SCALE
        frames = [[(key, im, tuple(v * k for v in M), a) for key, im, M, a in fr] for fr in frames]
    src = SHIFT_FROM.get(name)
    if src and use_fla(src):
        rf = _fla.build(src, idle_index(src, 999) + 1, ROWS); ref = rf[idle_index(src, len(rf))]
        dx, dy = plant_shift(src, fla_bbox(ref), [(im, M) for key, im, M, a in ref if a >= 0.2])
    else:
        _ref = frames[idle_index(name, len(frames))]
        dx, dy = plant_shift(name, fla_bbox(_ref), [(im, M) for key, im, M, a in _ref if a >= 0.2]) if name.startswith('Plant_') or name in ('LawnMower', 'PoolCleaner') else (0.0, 0.0)
    if name in _fla.OTHER and _fla.OTHER[name].get('shift'):
        dx, dy = _fla.OTHER[name]['shift']
        if name.startswith('Bullet_'):
            bdx, bdy = bullet_shift(name); dx += bdx; dy += bdy
    SHIFTS[name] = (round(dx, 1), round(dy, 1))
    out = []
    for fr in frames:
        parts = []
        for key, im, M, a in fr:
            a_, b_, c_, d_, tx, ty = M
            parts.append((fla_shape(key, im), (a_, b_, c_, d_, tx + FLA_POS[0] + dx, ty + FLA_POS[1] + dy), a))
        if not parts:   # never leave a frame empty (BitmapUtil needs bounds)
            parts.append((fla_shape(('blank',), _blank_img()), (1, 0, 0, 1, 0, 0), 1.0))
        out.append(parts)
    return out


def _blank_img():
    from PIL import Image as _I
    im = _I.new('RGBA', (2, 2), (0, 0, 0, 0)); im.putpixel((0, 0), (0, 0, 0, 8)); return im


def add_fla_clip(name, n):
    c = cid()
    defs.append(define_sprite_raw(c, fla_frames(name, n)))
    exports.append((c, name))


def use_fla(name):
    return _fla is not None and (name in _fla.SPECS or name in _fla.OTHER)


# ---------------- placement normalisation ----------------
# The battle puts a plant clip's origin at (cell corner + PLANT_OFFSET_XY_LIST[plant][0:2]);
# cells are 75 x 95. Every plant is shifted so its first frame is centred in the cell and
# its base sits BASE_Y px below the cell top. Mowers are centred on their clip origin
# (the game places the mower origin at row top + 55, collision box +-30).
try:
    OFFS = json.load(open(os.path.join(HERE, 'plant_offsets.json'))) if 'HERE' in globals() else json.load(open('/home/claude/plant_offsets.json'))
except Exception:
    OFFS = {}
CELL_CX, BASE_Y = 30.5, 67.0
MOWER_CENTER = (14.0, -22.0)
MOWER_SCALE = 0.8
SHIFT_FROM = {'Plant_Pumpkin_back': 'Plant_Pumpkin', 'Plant_Qiake_back': 'Plant_Qiake'}
NO_SHIFT = {'Plant_QK'}
_sid_size = {}
_sid_img = {}


def _corners(M, w, h):
    a, b, c, d, tx, ty = M
    return [(a * x + c * y + tx, b * x + d * y + ty) for x, y in ((0, 0), (w, 0), (0, h), (w, h))]


def bbox_of(items):
    xs = []; ys = []
    for M, w, h in items:
        for x, y in _corners(M, w, h):
            xs.append(x); ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)


def idle_index(name, n):
    row = ROWS.get(name)
    i = (row[0] - 1) if row and row[0] else 0
    return max(0, min(n - 1, i))


BASE_Y_SPECIAL = {'Plant_CoffeeBean': 51.0}


def render_items(items):
    """items: (PIL image, (a,b,c,d,tx,ty)) -> (RGBA image, x0, y0) covering them all."""
    from PIL import Image as _I
    bb = bbox_of([(M, im.width, im.height) for im, M in items])
    x0, y0 = int(math.floor(bb[0])) - 1, int(math.floor(bb[1])) - 1
    W, H = int(math.ceil(bb[2])) - x0 + 2, int(math.ceil(bb[3])) - y0 + 2
    cv = _I.new('RGBA', (max(1, W), max(1, H)), (0, 0, 0, 0))
    for im, M in items:
        a, b, c, d, tx, ty = M
        tx -= x0; ty -= y0
        det = a * d - b * c
        if abs(det) < 1e-9:
            continue
        ia, ib, ic, id_ = d / det, -c / det, -b / det, a / det
        cv.alpha_composite(im.transform(cv.size, _I.AFFINE, (ia, ib, -(ia * tx + ib * ty), ic, id_, -(ic * tx + id_ * ty)), resample=_I.BILINEAR))
    return cv, x0, y0


def base_center_x(items):
    """x centre of the bottom quarter of the visible pixels (leaves / stem / base)."""
    cv, x0, y0 = render_items(items)
    alpha = cv.getchannel('A').point(lambda v: 255 if v > 40 else 0)
    bb = alpha.getbbox()
    if not bb:
        return None, None
    top = bb[3] - max(3, (bb[3] - bb[1]) // 4)
    band = alpha.crop((0, top, cv.width, bb[3])).getbbox()
    cx = (band[0] + band[2]) / 2.0 if band else (bb[0] + bb[2]) / 2.0
    return x0 + cx, y0 + bb[3]


def plant_shift(name, bb, items=None):
    if name in NO_SHIFT:
        return 0.0, 0.0
    if name in ('LawnMower', 'PoolCleaner'):
        return MOWER_CENTER[0] - (bb[0] + bb[2]) / 2, MOWER_CENTER[1] - (bb[1] + bb[3]) / 2
    ox, oy = (OFFS.get(name) or [0, 0])[:2]
    cx, bottom = (None, None)
    if items:
        cx, bottom = base_center_x(items)
    if cx is None:
        cx, bottom = (bb[0] + bb[2]) / 2, bb[3]
    return CELL_CX - ox - cx, BASE_Y_SPECIAL.get(name, BASE_Y) - oy - bottom


def pose_bbox(parts):
    items = []
    for p in parts:
        sid, x, y, sx, sy, rot = p[:6]
        if sid in _sid_size:
            w, h = _sid_size[sid]
            items.append(((sx * math.cos(rot), sx * math.sin(rot), -sy * math.sin(rot), sy * math.cos(rot), x, y), w, h))
    return bbox_of(items)

exports = []


def add_clip(name, frames):
    c = cid()
    defs.append(define_sprite(c, frames))
    exports.append((c, name))


report = {}
for name, fn in PLANTS.items():
    row = ROWS.get(name)
    n = max([1] + (flat(row) if row else []) + [EXTRA_MAX.get(name, 0)])
    if name.endswith('_back'):
        n = EXTRA_MAX[name]
    n = max(n, 1)
    if use_fla(name):
        add_fla_clip(name, n); report[name] = n; continue
    if name in _pose_sets:
        frames = [bitmap_frame(name, _pose_sets[name], plant_state(name, f), n) for f in range(1, n + 1)]
        src = SHIFT_FROM.get(name, name)
        i0 = idle_index(src, n)
        ref = frames[i0] if src == name else bitmap_frame(src, _pose_sets[src], plant_state(src, i0 + 1), n)
        _items = []
        for p in ref:
            sid_, x_, y_, sx_, sy_, rot_ = p[:6]
            if sid_ in _sid_img:
                _items.append((_sid_img[sid_], (sx_ * math.cos(rot_), sx_ * math.sin(rot_), -sy_ * math.sin(rot_), sy_ * math.cos(rot_), x_, y_)))
        dx, dy = plant_shift(src, pose_bbox(ref), _items)
        SHIFTS[name] = (round(dx, 1), round(dy, 1))
        frames = [[(p[0], p[1] + dx, p[2] + dy) + tuple(p[3:]) for p in fr] for fr in frames]
    else:
        frames = [fn(plant_state(name, f)) for f in range(1, n + 1)]
    add_clip(name, frames); report[name] = n

# ---------------- bullets ----------------
def spin_frames(parts_fn, n):
    return [parts_fn(i) for i in range(n)]


def ball(color, r=8):
    return lambda i: [P(shp('e', 0, 0, r, r, fill=color), r + 1, r + 1), P(shp('e', 0, 0, r * 0.35, r * 0.3, fill=WHITE, line=None), r * 0.7, r * 0.6)]


BULLETS = {
    'Bullet_Pea': (ball(GREEN), 4), 'Bullet_Snowpea': (ball(ICE), 4),
    'Bullet_PuffShm': (ball(LPURP, 6), 4),
    'Bullet_FumeShm': (lambda i: [P(shp('e', 0, 0, 26, 12, fill=(190, 150, 220, 200), line=None), 30 + 4 * i, 14, 1 + 0.1 * i, 1)], 4),
    'Bullet_IceFumeShm': (lambda i: [P(shp('e', 0, 0, 26, 12, fill=(170, 225, 250, 200), line=None), 30 + 4 * i, 14, 1 + 0.1 * i, 1)], 4),
    'Bullet_GloomShroom': (lambda i: [P(shp('e', 0, 0, 40, 40, fill=(120, 80, 150, 150), line=None), 45, 45, 0.6 + 0.1 * i, 0.6 + 0.1 * i)], 6),
    'Bullet_Cabbage': (lambda i: [P(shp('e', 0, 0, 12, 10, fill=LGREEN), 13, 11, 1, 1, i * 0.8)], 4),
    'Bullet_Melon': (lambda i: [P(shp('e', 0, 0, 16, 13, fill=(60, 160, 70, 255)), 17, 14, 1, 1, i * 0.8)], 4),
    'Bullet_WinterMelon': (lambda i: [P(shp('e', 0, 0, 16, 13, fill=ICE), 17, 14, 1, 1, i * 0.8)], 4),
    'Bullet_FirePea': (lambda i: [P(shp('p', ((0, 0), (14, -8), (10, 0), (16, 6), (0, 8)), fill=ORANGE, line=None), 0, 9, 1, 1 + 0.1 * (i % 2)), P(shp('e', 0, 0, 8, 8, fill=YEL), 18, 9)], 4),
    'Bullet_SuperFirePea': (lambda i: [P(shp('p', ((0, 0), (20, -12), (14, 0), (22, 9), (0, 12)), fill=RED, line=None), 0, 13, 1, 1 + 0.1 * (i % 2)), P(shp('e', 0, 0, 11, 11, fill=ORANGE), 26, 13)], 4),
    'Bullet_Cactus': (lambda i: [P(shp('p', ((0, 0), (22, 3), (0, 6)), fill=WHITE), 0, 0)], 1),
    'Bullet_Star': (lambda i: [P(shp('p', star(12, 12, 11, 5), fill=YEL), 0, 0, 1, 1, 0)], 1),
    'Bullet_Track': (lambda i: [P(shp('e', 0, 0, 9, 9, fill=(250, 200, 60, 255)), 10, 10)], 1),
    'CharmBullet': (ball(PINK, 7), 4),
    'Bullet_Sun': (lambda i: [P(shp('e', 0, 0, 34, 34, fill=(255, 240, 120, 110), line=None), 36, 36, 1 + 0.05 * math.sin(i), 1 + 0.05 * math.sin(i)),
                             P(shp('p', star(36, 36, 32, 18, n=8), fill=(255, 220, 40, 255), line=None), 0, 0),
                             P(shp('e', 0, 0, 16, 16, fill=(255, 245, 150, 255), line=(230, 170, 20, 255)), 36, 36)], 12),
}
# ---- official projectiles (PNG) and FLA fire peas ----
PROJ_DIR = os.environ.get('PVZ_PROJECTILES', '/home/claude/proj/Projectiles') if 'os' in globals() else '/home/claude/proj/Projectiles'
PNG_BULLETS = {   # class: (file, frames, spin)
    'Bullet_Pea': ('ProjectilePea.png', 1, False),
    'Bullet_Snowpea': ('ProjectileSnowPea.png', 1, False),
    'Bullet_Cactus': ('ProjectileCactus.png', 1, False),
    'Bullet_Track': ('ProjectileCactus.png', 1, False),
    'Bullet_Cabbage': ('Cabbagepult_cabbage.png', 12, True),
    'Bullet_Melon': ('Melonpult_melon.png', 12, True),
    'Bullet_WinterMelon': ('WinterMelon_projectile.png', 12, True),
    'Bullet_Star': ('Projectile_star.png', 8, True),
}
_png_shape = {}


def png_bullet_frames(fname, n, spin):
    from PIL import Image as _I
    import os as _os
    p = _os.path.join(PROJ_DIR, fname)
    if not _os.path.exists(p):
        return None
    if fname not in _png_shape:
        im = _I.open(p).convert('RGBA')
        bid = cid(); defs.append(define_bits_lossless2(bid, im))
        sid = cid(); defs.append(define_bitmap_shape(sid, bid, im.width, im.height))
        _png_shape[fname] = (sid, im.width, im.height)
    sid, w, h = _png_shape[fname]
    frames = []
    for i in range(n):
        a = (2 * math.pi * i / n) if spin else 0.0
        c, s_ = math.cos(a), math.sin(a)
        cx, cy = w / 2.0, h / 2.0          # rotate about the image centre, centre stays at (w/2, h/2)
        tx = cx - (c * cx - s_ * cy); ty = cy - (s_ * cx + c * cy)
        frames.append([(sid, (c, s_, -s_, c, tx, ty), 1.0)])
    return frames


def cloud_image(rgb, w=96, h=44, blobs=14, seed=3, t=0.0):
    """Soft billowing cloud: overlapping blurred puffs, denser at the core."""
    from PIL import Image as _I, ImageDraw as _D, ImageFilter as _F
    import random as _r
    rnd = _r.Random(seed)
    im = _I.new('RGBA', (w, h), rgb + (0,))
    a = _I.new('L', (w, h), 0); d = _D.Draw(a)
    for i in range(blobs):
        cx = rnd.uniform(0.18, 0.82) * w + t * 6 * (rnd.random() - 0.3)
        cy = rnd.uniform(0.35, 0.65) * h
        r = rnd.uniform(0.16, 0.30) * h * (1.0 + 0.35 * t)
        d.ellipse([cx - r * 1.4, cy - r, cx + r * 1.4, cy + r], fill=int(120 + 80 * rnd.random()))
    a = a.filter(_F.GaussianBlur(4))
    im.putalpha(a.point(lambda v: int(min(255, v * 1.6) * (1.0 - 0.45 * t))))
    # lighter highlights
    hl = _I.new('RGBA', (w, h), tuple(min(255, c + 70) for c in rgb) + (0,))
    ha = a.point(lambda v: int(max(0, v - 150) * 1.2 * (1.0 - 0.55 * t)))
    hl.putalpha(ha)
    im.alpha_composite(hl)
    return im


CLOUD_BULLETS = {'Bullet_FumeShm': (150, 95, 195), 'Bullet_IceFumeShm': (120, 200, 245)}


def add_cloud_bullet(name, n=6):
    frames = []
    for i in range(n):
        im = cloud_image(CLOUD_BULLETS[name], t=i / float(n - 1))
        bid = cid(); defs.append(define_bits_lossless2(bid, im))
        sid = cid(); defs.append(define_bitmap_shape(sid, bid, im.width, im.height))
        bdx, bdy = bullet_shift(name); SHIFTS[name] = (bdx, bdy)
        frames.append([(sid, (1, 0, 0, 1, 0 + bdx, -8 + bdy), 1.0)])
    c = cid(); defs.append(define_sprite_raw(c, frames)); exports.append((c, name))
    return n


# Projectiles are launched from a fixed point relative to the plant's position,
# so when a plant's art is re-centred (SHIFTS) the projectile art must move by the
# same amount, otherwise it leaves from the old spot (below / ahead of the snout).
BULLET_OWNER = {
    'Bullet_Pea': 'Plant_Peashooter', 'Bullet_Snowpea': 'Plant_Snowpea',
    'Bullet_FirePea': 'Plant_Peashooter', 'Bullet_SuperFirePea': 'Plant_Peashooter',
    'Bullet_Cabbage': 'Plant_Cabbagepult', 'Bullet_Melon': 'Plant_MelonPult',
    'Bullet_WinterMelon': 'Plant_WinterMelon', 'Bullet_Cactus': 'Plant_Cactus',
    'Bullet_Track': 'Plant_Cattail', 'Bullet_Star': 'Plant_StarFruit',
    'Bullet_PuffShm': 'Plant_PuffShroom', 'Bullet_FumeShm': 'Plant_FumeShroom',
    'Bullet_IceFumeShm': 'Plant_IceFumeShroom', 'Bullet_GloomShroom': 'Plant_GloomShroom',
}


BULLET_EXTRA = {   # fine-tuning on top of the owner's shift (pea centre at snout height)
    'Bullet_Pea': (0.0, -8.0), 'Bullet_Snowpea': (0.0, -8.0),
    'Bullet_FirePea': (0.0, -8.0), 'Bullet_SuperFirePea': (0.0, -8.0),
}


def bullet_shift(name):
    o = BULLET_OWNER.get(name)
    dx, dy = tuple(SHIFTS.get(o, (0.0, 0.0))) if o else (0.0, 0.0)
    ex, ey = BULLET_EXTRA.get(name, (0.0, 0.0))
    return dx + ex, dy + ey


def add_png_bullet(name):
    fname, n, spin = PNG_BULLETS[name]
    fr = png_bullet_frames(fname, n, spin)
    if fr is None:
        return None
    bdx, bdy = bullet_shift(name); SHIFTS[name] = (bdx, bdy)
    fr = [[(sid, (a, b, c, d, tx + bdx, ty + bdy), al) for sid, (a, b, c, d, tx, ty), al in f] for f in fr]
    c = cid(); defs.append(define_sprite_raw(c, fr)); exports.append((c, name))
    return n


for name, (fn, n) in BULLETS.items():
    if name in CLOUD_BULLETS:
        report[name] = add_cloud_bullet(name); continue
    if name in PNG_BULLETS:
        got = add_png_bullet(name)
        if got:
            report[name] = got; continue
    if use_fla(name):
        n = _fla.OTHER[name].get('frames', n); add_fla_clip(name, n); report[name] = n; continue
    bdx, bdy = bullet_shift(name)
    frs = [[(p[0], p[1] + bdx, p[2] + bdy) + tuple(p[3:]) for p in fr] for fr in spin_frames(fn, n)]
    if bdx or bdy:
        SHIFTS[name] = (bdx, bdy)
    add_clip(name, frs); report[name] = n

# ---------------- scene objects ----------------
def mower(i, water=False):
    body = shp('r', 0, 0, 44, 20, fill=(210, 40, 40, 255) if not water else (60, 140, 210, 255), lw=2)
    wheel = shp('e', 0, 0, 7, 7, fill=BLACK)
    handle = shp('r', 0, 0, 3, 26, fill=DGREY)
    shake = (i % 2) * 1.0
    parts = [P(handle, 4, 18, 1, 1, -0.6), P(body, 10, 34 + shake), P(wheel, 16, 56, 1, 1, i), P(wheel, 46, 56, 1, 1, i)]
    if water and i >= 11:
        parts.append(P(shp('e', 0, 0, 30, 5, fill=(120, 180, 240, 200), line=None), 32, 60))
    return parts


if use_fla('LawnMower'):
    add_fla_clip('LawnMower', 34)
else:
    add_clip('LawnMower', [mower(i) for i in range(34)])
report['LawnMower'] = 34
if use_fla('PoolCleaner'):
    add_fla_clip('PoolCleaner', 83)
else:
    add_clip('PoolCleaner', [mower(i, True) for i in range(83)])
report['PoolCleaner'] = 83

# zombie armour props: name+state (1 full, 2 broken, 3 destroyed)
PROPS = {'Prop_Cone': (ORANGE, 'cone', 292), 'Prop_Bucket': (GREY, 'bucket', 292), 'Prop_Paper': (CREAM, 'paper', 292),
         'Prop_Flag': (RED, 'flag', 292), 'Prop_Door': (DGREY, 'door', 292), 'Prop_Football': (RED, 'helmet', 292),
         'Prop_BlackFootball': (BLACK, 'helmet', 292), 'Prop_Box': (PURPLE, 'box', 292)}


def prop_parts(color, kind, state):
    dmg = [P(shp('p', ((0, 0), (5, 6), (2, 10), (7, 14)), fill=None or DBROWN, line=None), 10 + 6 * k, 8 + 4 * k) for k in range(state - 1)]
    if kind == 'cone':
        base = [P(shp('p', ((14, 0), (28, 34), (0, 34)), fill=color, lw=1.5), 0, 0), P(shp('r', 0, 0, 22, 4, fill=WHITE, line=None), 3, 18)]
    elif kind == 'bucket':
        base = [P(shp('p', ((3, 0), (29, 0), (32, 26), (0, 26)), fill=color, lw=1.5), 0, 0)]
    elif kind == 'paper':
        base = [P(shp('r', 0, 0, 30, 36, fill=color), 0, 0), P(shp('r', 0, 0, 22, 3, fill=GREY, line=None), 4, 8), P(shp('r', 0, 0, 22, 3, fill=GREY, line=None), 4, 16)]
    elif kind == 'flag':
        base = [P(shp('r', 0, 0, 3, 50, fill=BROWN), 0, 0), P(shp('r', 0, 0, 28, 18, fill=color), 3, 2)]
    elif kind == 'door':
        base = [P(shp('r', 0, 0, 30, 56, fill=color, lw=2), 0, 0), P(shp('e', 0, 0, 3, 3, fill=YEL), 24, 30)]
    elif kind == 'helmet':
        base = [P(shp('e', 0, 0, 18, 14, fill=color, lw=2), 18, 14), P(shp('r', 0, 0, 20, 3, fill=WHITE, line=None), 8, 16)]
    else:
        base = [P(shp('r', 0, 0, 30, 26, fill=color, lw=2), 0, 0)]
    return base + dmg


# ---- flag zombie flag: pole + flag held by Zombie.fla's Zombie_flaghand track ----
FLAG_GRIP = (4.2, 104.4)      # pole image point held in the fist (bottom end; pole runs (27,36) top -> (3,108) bottom)
FLAG_TOP = (24.6, 43.2)       # cloth hangs 10% down from the pole tip (27,36) toward the bottom (3,108)
FLAG_SCALE = 1.25              # pole length (was 1.45; shorter)
FLAG_CLOTH_SCALE = 0.6         # cloth size (smaller than the original 1:1 art)
FLAG_CLOTH_ANCHOR = (14.0, 3.0) # top-left corner of the cloth (its left edge runs parallel to the pole)


def flag_prop_frames(state):
    """Pole + cloth held in the GAME's flag-zombie fist.

    The prop is added at the zombie's origin, on top of the body clip
    Zombie_Flag (pvzNormalZombie_1_.swf). That body is drawn differently from
    Zombie.fla (arm stretched forward, fist in front at shoulder height), so
    the fist position per body frame was measured from the game clip itself
    (flag_fist.json, clip coordinates; 250 body frames, the prop has 292)."""
    if _fla is None:
        return None
    try:
        d = _fla.doc('Zombie')
    except Exception:
        return None
    pole = d.image('Zombie_flagpole'); hand = d.image('Zombie_flaghand.png')
    cloth = d.image({1: 'Zombie_flag1.png', 2: 'Zombie_flag2', 3: 'Zombie_flag3'}[state])
    if pole is None or hand is None or cloth is None:
        return None
    import os as _os, json as _js
    _here = _os.path.dirname(_os.path.abspath(__file__))
    fist = {int(k): v for k, v in _js.load(open(_os.path.join(_here, 'flag_fist.json'))).items()}
    sp = fla_shape(('flagpole',), pole); sh = fla_shape(('flaghand',), hand); sc = fla_shape(('flagcloth', state), cloth)
    k = FLAG_SCALE
    frames = []; last = fist[min(fist)]
    for f in range(1, 293):
        fx, fy = fist.get(f, last); last = (fx, fy)
        mul_ = _fla.mul
        # pole: grip point onto the fist, uniform scale k, no rotation (leans back as drawn)
        Mpole = (k, 0, 0, k, fx - k * FLAG_GRIP[0], fy - k * FLAG_GRIP[1])
        wave = 0.06 * math.sin(f * 2 * math.pi / 18.0)
        c, s_ = math.cos(wave), math.sin(wave)
        tx_, ty_ = Mpole[0] * FLAG_TOP[0] + Mpole[4], Mpole[3] * FLAG_TOP[1] + Mpole[5]   # pole top in clip coords
        cs = FLAG_CLOTH_SCALE
        Mcl = mul_((1, 0, 0, 1, tx_, ty_), mul_((c, s_, -s_, c, 0, 0),
                   (cs, 0, 0, cs, -cs * FLAG_CLOTH_ANCHOR[0], -cs * FLAG_CLOTH_ANCHOR[1])))
        hk = 0.8
        Mhand = (hk, 0, 0, hk, fx - hk * hand.width / 2.0, fy - hk * hand.height / 2.0)
        frames.append([(sp, Mpole, 1.0), (sc, Mcl, 1.0), (sh, Mhand, 1.0)])
    return frames


# ---- cone / bucket: your sprites placed on the GAME's head clip (general_head) ----
# cone_bucket_map.json: per zombie frame (1..292) the matrix of the cone/bucket image
# in zombie coordinates = Zombie.fla's head->cone/bucket relationship, scaled (x1.16)
# and moved onto the game head (measured from pvzNormalZombie general_head).
def headgear_prop_frames(kind, state):
    import os as _os, json as _js
    from PIL import Image as _I
    here = _os.path.dirname(_os.path.abspath(__file__))
    mp_path = _os.path.join(here, 'cone_bucket_map.json')
    img_path = _os.path.join(here, 'cone_bucket', f'Zombie_{kind}{state}.png')
    if not (_os.path.exists(mp_path) and _os.path.exists(img_path)):
        return None
    mp = _js.load(open(mp_path))[kind]
    im = _I.open(img_path).convert('RGBA')
    sid = fla_shape(('headgear', kind, state), im)
    return [[(sid, tuple(mp[str(f)]), 1.0)] for f in range(1, 293)]


for pname, (color, kind, n) in PROPS.items():
    if pname in ('Prop_Cone', 'Prop_Bucket'):
        kind = 'cone' if pname == 'Prop_Cone' else 'bucket'
        built = [headgear_prop_frames(kind, st_) for st_ in (1, 2, 3)]
        if all(b is not None for b in built):
            for st_, fr_ in zip((1, 2, 3), built):
                c_ = cid(); defs.append(define_sprite_raw(c_, fr_)); exports.append((c_, f'{pname}{st_}')); report[f'{pname}{st_}'] = 292
            continue
    if pname == 'Prop_Flag':
        ok = True
        for st_ in (1, 2, 3):
            fr_ = flag_prop_frames(st_)
            if fr_ is None:
                ok = False; break
            c_ = cid(); defs.append(define_sprite_raw(c_, fr_)); exports.append((c_, f'Prop_Flag{st_}')); report[f'Prop_Flag{st_}'] = 292
        if ok:
            continue
    for s in (1, 2, 3):
        parts = prop_parts(color, kind, s)
        add_clip(f'{pname}{s}', [parts] * n); report[f'{pname}{s}'] = n
add_clip('Prop_Paper_ForDrop', [prop_parts(CREAM, 'paper', 1)] * 12); report['Prop_Paper_ForDrop'] = 12
add_clip('Prop_Door_ForDrop', [prop_parts(DGREY, 'door', 1)] * 12); report['Prop_Door_ForDrop'] = 12


# ---------------- effects ----------------
def burst(color, n=8, r=20, blobs=6, color2=None):
    frames = []
    for i in range(n):
        k = (i + 1) / n
        a = 1 - 0.8 * k
        c = shp('e', 0, 0, r, r, fill=color, line=None)
        parts = [P(c, r * 2, r * 2, 0.4 + 0.8 * k, 0.4 + 0.8 * k, 0, (1, 1, 1, a, 0, 0, 0, 0))]
        d = shp('e', 0, 0, r * 0.25, r * 0.25, fill=color2 or color, line=None)
        for j in range(blobs):
            ang = j * 2 * math.pi / blobs
            parts.append(P(d, r * 2 + math.cos(ang) * r * 1.4 * k, r * 2 + math.sin(ang) * r * 1.4 * k, 1, 1, 0, (1, 1, 1, a, 0, 0, 0, 0)))
        frames.append(parts)
    return frames


def flame_row(n=14, w=90, color=ORANGE):
    fl = shp('p', ((0, 0), (8, -26), (14, -10), (20, -34), (28, 0)), fill=color, line=None)
    fl2 = shp('p', ((0, 0), (6, -14), (12, 0)), fill=YEL, line=None)
    return [[P(fl, 4 + 26 * j, 40, 1, 0.6 + 0.4 * abs(math.sin(i * 0.7 + j)), 0, (1, 1, 1, 1 - i / (n * 1.3), 0, 0, 0, 0)) for j in range(w // 26)]
            + [P(fl2, 12 + 26 * j, 40) for j in range(w // 26)] for i in range(n)]


def zzz(n=24):
    z = shp('p', ((0, 0), (10, 0), (10, 2), (3, 10), (10, 10), (10, 12), (0, 12), (0, 10), (7, 2), (0, 2)), fill=(180, 200, 255, 255), line=(60, 70, 140, 255), lw=0.8)
    return [[P(z, 4 + i * 0.5, 30 - i, 0.6 + i * 0.02, 0.6 + i * 0.02, 0, (1, 1, 1, 1 - i / (n * 1.2), 0, 0, 0, 0))] for i in range(n)]


def hammer(n=10):
    head = shp('r', 0, 0, 30, 16, fill=DGREY, lw=2); stick = shp('r', 0, 0, 5, 34, fill=BROWN)
    return [[P(stick, 40, 20, 1, 1, -0.9 + 0.12 * i), P(head, 26, 10, 1, 1, -0.9 + 0.12 * i)] for i in range(n)]


EFFECTS = {}
for k in (1, 2, 3):
    EFFECTS[f'pea_bullet_effect{k}'] = burst(GREEN, 6, 10)
    EFFECTS[f'snow_pea_bullet_effect{k}'] = burst(ICE, 6, 10)
    EFFECTS[f'melon_bullet_effect_{k}'] = burst((60, 160, 70, 255), 8, 18)
    EFFECTS[f'winter_melon_bullet_effect_{k}'] = burst(ICE, 8, 18, color2=WHITE)
    EFFECTS[f'Dirt{k}'] = burst(BROWN, 10, 14, color2=DBROWN)
for k in (1, 2):
    EFFECTS[f'Dirt_Roll_{k}'] = burst(BROWN, 10, 16, color2=DBROWN)
EFFECTS.update({
    'puff_bullet_effect': burst(LPURP, 6, 8), 'fire_pea_bullet_effect': burst(ORANGE, 6, 12, color2=YEL),
    'Cherry_Bomb_Effect': burst(ORANGE, 16, 90, 10, color2=RED), 'potato_explode': burst(TAN, 14, 50, 8, color2=BROWN),
    'jack_explode': burst(ORANGE, 14, 70, 8, color2=RED), 'Tomb_Explode': burst(GREY, 12, 30, 8, color2=DGREY),
    'Fire': flame_row(), 'FireShroomEffect': flame_row(12, 80, RED), 'Puff': burst(WHITE, 10, 14),
    'SleepEffect': zzz(), 'nut_effect': burst(TAN, 8, 12, color2=BROWN), 'splash_zombie_water': burst((110, 170, 230, 255), 10, 24, color2=WHITE),
    'steam': burst(WHITE, 12, 18), 'water_particle': burst((110, 170, 230, 255), 8, 8),
    'vase_break': burst((180, 120, 80, 255), 10, 22, color2=DBROWN), 'vase_break2': burst((180, 120, 80, 255), 10, 22, color2=DBROWN),
    'GargantuarDownEffectMc': burst(TAN, 12, 50, 8), 'ImgZombieDownEffectMc': burst(TAN, 10, 24, 6),
    'Hammer': hammer(),
    'portal': [[P(shp('e', 0, 0, 30, 40, fill=(90, 40, 150, 255), line=(200, 150, 255, 255), lw=3), 34, 44, 1, 1, i * 0.4),
                P(shp('e', 0, 0, 16, 24, fill=(40, 10, 80, 255), line=None), 34, 44, 1, 1, -i * 0.4)] for i in range(12)],
    'tanglekelp_arm': [[P(shp('e', 0, 0, 6, 30, fill=(40, 120, 70, 255)), 20 + 8 * j, 40 - i * 2, 1, 1, 0.2 * math.sin(i + j)) for j in range(3)] for i in range(12)],
    'bonus_mask': [[P(shp('r', 0, 0, 100, 140, fill=BLACK, line=None), 0, 0)]],
    'vaseMc': [[P(shp('e', 0, 0, 24, 30, fill=(180, 120, 80, 255), lw=2), 30, 40), P(shp('r', 0, 0, 20, 8, fill=(150, 95, 60, 255)), 20, 8)]],
})
for name, frames in EFFECTS.items():
    if use_fla(name):
        n_ = _fla.OTHER[name].get('frames', len(frames)); add_fla_clip(name, n_); report[name] = n_; continue
    add_clip(name, frames); report[name] = len(frames)

# rakeMc: engine calls getMovieClilp and plays it as a normal timeline
add_clip('rakeMc', [[P(shp('r', 0, 0, 4, 60, fill=BROWN), 30, 10 + (0 if i < 6 else -20), 1, 1, 0 if i < 6 else -0.5),
                     P(shp('r', 0, 0, 30, 6, fill=DGREY), 17, 66 + (0 if i < 6 else -20))] for i in range(12)]); report['rakeMc'] = 12

# ---- BitmapData symbols the battle UI looks up with ResourceCache.getBitmap() ----
# "Locked" (padlock on seed cards the player has not unlocked) only exists in
# almanac_1_.swf, which the battle never loads; SCard then stays half-built and
# the seed-selection screen fails. Copy the original bitmap in under that name.
bitmap_exports = []
try:
    import struct as _st, os as _os2
    from swfsyms import tags as _tags, syms as _syms
    _alm = _os2.environ.get('PVZ_ALMANAC_SWF', '/home/claude/w2/almanac_1_.swf')
    if not _os2.path.exists(_alm):
        _alm = _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), '..', 'almanac_1_.swf')
    _names = dict(_syms(_alm)); _v, _t = _tags(_alm)
    _lid = [c for c, n in _names.items() if n == 'Locked'][0]
    for _code, _body in _t:
        if _code in (20, 36) and _st.unpack_from('<H', _body)[0] == _lid:
            _nid = cid()
            defs.append(_st.pack('<HI', (_code << 6) | 63, len(_body)) + _st.pack('<H', _nid) + _body[2:])
            bitmap_exports.append((_nid, 'Locked'))
            break
except Exception as _e:
    print('Locked bitmap not added:', _e)

data = build_swf(defs, exports, bitmap_exports=bitmap_exports)
open(OUT, 'wb').write(data)
json.dump(report, open(OUT + '.frames.json', 'w'), indent=0)
print(len(exports), 'clips,', len(data), 'bytes ->', OUT)
json.dump(SHIFTS, open(OUT + '.shifts.json', 'w'), indent=0)
