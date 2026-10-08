"""Battle clips from the PvZ 1 FLAs (PopCap reanim sources).

For each engine class name, SPECS gives the FLA folder (extracted with
rawzip.py) and a mapping from engine frame numbers (1-based, the numbers in
PlantsConfig.PLANT_FRAME_LIST) to what should be drawn:

  ('f', n)            draw FLA main-timeline frame n (0-based), all tracks
  ('a', body, head)   draw body frame + head frame attached at the stem locator
                      (head shifted by stem(body) - stem(body_start), like PvZ)

build(name, nframes) returns a list of frames, each a list of
(image_key, PIL image, (a,b,c,d,tx,ty), alpha), in FLA stage coordinates.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xflrender import Doc, layer_matrix, mul
from PIL import Image

FLA_ROOT = os.environ.get('PVZ_FLA', '/home/claude/xfl')
SOCIAL = os.environ.get('PVZ_SPRITES', '/home/claude/spr/social edition plants')
_docs = {}


def doc(name):
    if name not in _docs:
        _docs[name] = Doc(os.path.join(FLA_ROOT, name))
    return _docs[name]


def inv(m):
    a, b, c, d, tx, ty = m; det = a * d - b * c
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * tx + ic * ty), -(ib * tx + id_ * ty))


SKIP_ALWAYS = {'_guide', 'guide', 'Guide'}


def _skip(extra=()):
    ex = set(extra)
    return lambda n: n in SKIP_ALWAYS or n in ex or n.lower().endswith('guide')


def retime(i, n_in, a, b):
    """Map index i in [0, n_in) onto FLA frames a..b inclusive."""
    if n_in <= 1:
        return a
    return a + int(round(i * (b - a) / float(n_in - 1)))


def loop(i, a, b):
    return a + i % (b - a + 1)


# ---------------------------------------------------------------- specs
def offset(off):
    return lambda f, n: ('f', f - 1 + off)


def shooter(idle_full=None, body=(4, 28), head_idle=(29, 53), head_shoot=(54, 78), idle_len=25, stem='anim_stem'):
    def m(f, n):
        if f <= idle_len:
            if idle_full:
                return ('f', idle_full[0] + (f - 1) % (idle_full[1] - idle_full[0] + 1))
            return ('a', loop(f - 1, *body), loop(f - 1, *head_idle))
        k = f - idle_len - 1; na = n - idle_len
        return ('a', loop(k, *body), retime(k, na, *head_shoot))
    m.stem = stem; m.body_start = body[0]
    return m


def segments(segs, default=None):
    """segs: list of (engine_from, engine_to, fla_from, fla_to, mode) mode 'stretch'|'loop'."""
    def m(f, n):
        for a, b, fa, fb, mode in segs:
            if a <= f <= b:
                k = f - a
                return ('f', retime(k, b - a + 1, fa, fb) if mode == 'stretch' else loop(k, fa, fb))
        return ('f', default if default is not None else segs[0][2])
    return m


SPECS = {
    'Plant_Peashooter': dict(fla='PeaShooterSingle', map=shooter(idle_full=(79, 103))),
    'Plant_Snowpea': dict(fla='SnowPea', map=shooter(idle_full=(79, 103))),
    'Plant_Repeater': dict(fla='PeaShooter', map=shooter(idle_full=(79, 103))),
    'Plant_GatlingPea': dict(fla='GatlingPea', map=shooter(head_shoot=(54, 92))),
    'Plant_Sunflower': dict(fla='SunFlower', map=offset(4)),
    'Plant_TwinSunflower': dict(fla='TwinSunflower', map=offset(9)),
    'Plant_Wallnut': dict(fla='Wallnut', map=lambda f, n: ('f', (f - 1) % 17),
                          hurt={'Wallnut_body.png': ('social', 'wall-nut', 52, 53)}),
    'Plant_Tallnut': dict(fla='Tallnut', map=lambda f, n: ('f', 20 + (f - 1) % 17),
                          hurt={'Tallnut_body.png': ('fla', 'Tallnut_cracked1.png', 'Tallnut_cracked2.png')}),
    'Plant_Pumpkin': dict(fla='Pumpkin', map=lambda f, n: ('f', (f - 1) % 21), layers_skip=('Pumpkin_back',),
                          hurt={'Pumpkin_front.png': ('fla', 'pumpkin_damage1.png', 'Pumpkin_damage3.png')}),
    'Plant_Pumpkin_back': dict(fla='Pumpkin', map=lambda f, n: ('f', (f - 1) % 21), layers_skip=('Pumpkin_front',)),
    'Plant_CherryBomb': dict(fla='CherryBomb', map=segments([(1, 13, 14, 26, 'loop'), (14, 27, 0, 13, 'stretch')])),
    'Plant_PotatoMine': dict(fla='PotatoMine', map=segments([(1, 21, 0, 19, 'stretch'), (22, 32, 20, 30, 'loop')])),
    'Plant_Chomper': dict(fla='Chomper', map=offset(0)),
    'Plant_Squash': dict(fla='Squash', map=segments([(1, 19, 5, 23, 'loop'), (20, 45, 24, 49, 'stretch'),
                                                     (46, 82, 50, 72, 'stretch')])),
    'Plant_PuffShroom': dict(fla='PuffShroom', map=offset(4)),
    'Plant_SunShroom': dict(fla='SunShroom', map=offset(5)),
    'Plant_FumeShroom': dict(fla='FumeShroom', map=offset(4)),
    'Plant_ScaredyShroom': dict(fla='ScaredyShroom', map=offset(5)),
    'Plant_SeaShroom': dict(fla='SeaShroom', map=offset(4)),
    'Plant_MagnetShroom': dict(fla='Magnetshroom', map=offset(4)),
    'Plant_GloomShroom': dict(fla='GloomShroom', map=offset(5)),
    'Plant_Torchwood': dict(fla='Torchwood', map=offset(4)),
    'Plant_Jalapeno': dict(fla='Jalapeno', map=offset(5)),
    'Plant_CoffeeBean': dict(fla='Coffeebean', map=offset(0)),
    'Plant_GraveBuster': dict(fla='Gravebuster', map=offset(0)),
    'Plant_LilyPad': dict(fla='LilyPad', map=lambda f, n: ('f', 0)),
    'Plant_Pot': dict(fla='Pot', map=offset(0)),
    'Plant_Blover': dict(fla='Blover', map=offset(0)),
    'Plant_Cactus': dict(fla='Cactus', map=offset(0)),
    'Plant_Cattail': dict(fla='Cattail', map=offset(0)),
    'Plant_Cabbagepult': dict(fla='Cabbagepult', map=offset(5)),
    'Plant_MelonPult': dict(fla='Melonpult', map=offset(5)),
    'Plant_WinterMelon': dict(fla='WinterMelon', map=offset(5)),
    'Plant_Tanglekelp': dict(fla='Tanglekelp', map=offset(4)),
    'Plant_MariGold': dict(fla='Marigold', map=lambda f, n: ('f', loop(f - 1, 5, 29))),
}

OTHER = {
    'portal': dict(fla='Portal_Circle', map=lambda f, n: ('f', (f - 1) % 61), frames=61, shift=(-49.1, -98.7)),
    'Bullet_FirePea': dict(fla='FirePea', map=lambda f, n: ('f', (f - 1) % 25), frames=25, shift=(-25.8, -24.9)),
    'Bullet_SuperFirePea': dict(fla='FirePea', map=lambda f, n: ('f', (f - 1) % 25), frames=25, shift=(-25.8, -24.9), hue=0.55),
    'Puff': dict(fla='Puff', map=lambda f, n: ('f', 6 + min(f - 1, 8)), frames=9, shift=(-87.5, -92.7)),
    'Bullet_Sun': dict(fla='Sun', map=lambda f, n: ('f', f - 1), frames=13),
    'LawnMower': dict(fla='LawnMower', map=lambda f, n: ('f', min(f - 1, 33)), frames=34),
    'PoolCleaner': dict(fla='PoolCleaner', map=lambda f, n: ('f', min(f - 1, 81)), frames=83),
}

# layers that only mark animation ranges / attach points, never drawn
MARKER_PREFIX = ('anim_idle', 'anim_shooting', 'anim_head_idle', 'anim_full_idle', 'anim_stem')


def _placements(d, frame, skip_layers):
    sk = _skip(skip_layers)
    return d.placements(frame, skip=sk)


def _social(folder, pid):
    for ext in ('png', 'jpg'):
        p = os.path.join(SOCIAL, folder, f'pvzPlant[1]-{pid}.{ext}')
        if os.path.exists(p):
            return Image.open(p).convert('RGBA')
    return None


_hue_cache = {}


def _hue(im, shift):
    """Rotate the hue of an RGBA image by `shift` (0..1), keeping alpha."""
    k = (id(im), shift)
    if k not in _hue_cache:
        a = im.getchannel('A')
        h, s, v = im.convert('RGB').convert('HSV').split()
        h = h.point(lambda x: (x + int(shift * 255)) % 256)
        out = Image.merge('HSV', (h, s, v)).convert('RGB').convert('RGBA'); out.putalpha(a)
        _hue_cache[k] = out
    return _hue_cache[k]


def build(name, nframes, rows=None):
    spec = SPECS.get(name) or OTHER.get(name)
    d = doc(spec['fla'])
    mapping = spec['map']
    skip_layers = spec.get('layers_skip', ())
    hurt = spec.get('hurt', {})
    hurt_imgs = {}
    for src, h in hurt.items():
        if h[0] == 'social':
            hurt_imgs[src] = (_social(h[1], h[2]), _social(h[1], h[3]))
        else:
            hurt_imgs[src] = (d.image(h[1]), d.image(h[2]))
    row = rows.get(name) if rows else None
    out = []
    for f in range(1, nframes + 1):
        what = mapping(f, nframes)
        if what[0] == 'f':
            pl = _placements(d, what[1], skip_layers)
        else:
            _, fb, fh = what
            body = _placements(d, fb, skip_layers)
            head = _placements(d, fh, skip_layers)
            stem_now = layer_matrix(d, fb, mapping.stem)
            stem_ref = layer_matrix(d, mapping.body_start, mapping.stem)
            if stem_now and stem_ref:
                shift = mul(stem_now, inv(stem_ref))
                head = [(im, mul(shift, M), a, ln) for im, M, a, ln in head]
            pl = body + head
        level = 0
        if row and row[5] and row[5] <= f <= row[6]:
            level = 1
        if row and row[7] and row[7] <= f <= row[8]:
            level = 2
        frame = []
        for im, M, a, ln in pl:
            if a <= 0.01:
                continue
            key = (spec['fla'], id(im))
            if spec.get('hue') is not None:
                im = _hue(im, spec['hue']); key = (spec['fla'], 'hue', spec['hue'], id(im))
            if level and hurt_imgs:
                for src, pair in hurt_imgs.items():
                    if im is d.image(src) and pair[level - 1] is not None:
                        im = pair[level - 1]; key = (spec['fla'], 'hurt', src, level)
            frame.append((key, im, M, a))
        out.append(frame)
    return out
