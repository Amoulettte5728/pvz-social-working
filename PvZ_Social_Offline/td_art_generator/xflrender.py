"""Render PopCap reanim-style FLA (XFL) timelines.

Loads DOMDocument.xml + LIBRARY/*.xml + bin/*.dat of an extracted FLA and
returns, for any main-timeline frame, the list of bitmap placements
(image, 2x3 matrix) in drawing order. Supports keyframes, classic motion
tweens (decomposed scale/rotation/skew interpolation), nested graphic
symbols (loop / play once / single frame) and alpha colour transforms.
"""
import os, re, math
import xml.etree.ElementTree as ET
from PIL import Image
from xfldat import load_dat

NS = '{http://ns.adobe.com/xfl/2008/}'


def _m(el):
    """Matrix element -> (a, b, c, d, tx, ty)."""
    if el is None:
        return (1, 0, 0, 1, 0, 0)
    m = el.find(NS + 'Matrix')
    if m is None:
        return (1, 0, 0, 1, 0, 0)
    g = lambda k, dflt: float(m.get(k, dflt))
    return (g('a', 1), g('b', 0), g('c', 0), g('d', 1), g('tx', 0), g('ty', 0))


def mul(m1, m2):
    """m1 * m2 (apply m2 first, then m1)."""
    a1, b1, c1, d1, x1, y1 = m1; a2, b2, c2, d2, x2, y2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * x2 + c1 * y2 + x1, b1 * x2 + d1 * y2 + y1)


def decompose(m):
    a, b, c, d, tx, ty = m
    sx = math.hypot(a, b); sy = math.hypot(c, d)
    rx = math.atan2(b, a); ry = math.atan2(-c, d)   # rotation of x axis / y axis
    return sx, sy, rx, ry, tx, ty


def compose(sx, sy, rx, ry, tx, ty):
    return (sx * math.cos(rx), sx * math.sin(rx), -sy * math.sin(ry), sy * math.cos(ry), tx, ty)


def lerp_angle(a0, a1, t):
    d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    return a0 + d * t


def tween(m0, m1, t, ease=0):
    if ease:
        # Flash ease -100..100: approximate with quadratic in/out
        e = ease / 100.0
        t = t + e * t * (1 - t) if e > 0 else t - (-e) * t * (1 - t)
    s0 = decompose(m0); s1 = decompose(m1)
    return compose(s0[0] + (s1[0] - s0[0]) * t, s0[1] + (s1[1] - s0[1]) * t,
                   lerp_angle(s0[2], s1[2], t), lerp_angle(s0[3], s1[3], t),
                   s0[4] + (s1[4] - s0[4]) * t, s0[5] + (s1[5] - s0[5]) * t)


class Doc:
    def __init__(self, root):
        self.root = root
        self.dom = ET.parse(os.path.join(root, 'DOMDocument.xml')).getroot()
        self.bitmaps = {}
        for bi in self.dom.iter(NS + 'DOMBitmapItem'):
            self.bitmaps[bi.get('name')] = bi.get('bitmapDataHRef')
        self._img = {}
        self._sym = {}
        self.width = float(self.dom.get('width', 550)); self.height = float(self.dom.get('height', 400))
        self.main = self.dom.find(f'{NS}timelines/{NS}DOMTimeline')

    def image(self, name):
        if name not in self._img:
            href = self.bitmaps.get(name)
            self._img[name] = load_dat(os.path.join(self.root, 'bin', href)) if href else None
        return self._img[name]

    def symbol(self, name):
        if name not in self._sym:
            p = os.path.join(self.root, 'LIBRARY', name + '.xml')
            if not os.path.exists(p):
                self._sym[name] = None
            else:
                r = ET.parse(p).getroot()
                self._sym[name] = r.find(f'{NS}timeline/{NS}DOMTimeline')
        return self._sym[name]

    # ------------------------------------------------------------
    def layers(self, timeline):
        return [l for l in timeline.find(NS + 'layers')] if timeline is not None else []

    def timeline_length(self, timeline):
        n = 0
        for l in self.layers(timeline):
            fr = l.find(NS + 'frames')
            if fr is None: continue
            for f in fr:
                n = max(n, int(f.get('index', 0)) + int(f.get('duration', 1)))
        return n

    def layer_frames(self, layer):
        fr = layer.find(NS + 'frames')
        return list(fr) if fr is not None else []

    def labels(self):
        """Frame labels on the main timeline: {name: (start, end)} using the anim_* label layers
        (layer name is the animation name; the non-empty span is the range)."""
        out = {}
        for l in self.layers(self.main):
            fs = self.layer_frames(l)
            for f in fs:
                nm = f.get('name')
                if nm:
                    out[nm] = (int(f.get('index', 0)), int(f.get('index', 0)) + int(f.get('duration', 1)) - 1)
        return out

    def placements(self, frame, timeline=None, parent=(1, 0, 0, 1, 0, 0), alpha=1.0, skip=None, depth=0):
        """List of (PIL image, matrix, alpha) for `frame` (0-based) of timeline, back to front."""
        timeline = self.main if timeline is None else timeline
        out = []
        lays = self.layers(timeline)
        for l in reversed(lays):                     # XFL lists top layer first
            if l.get('layerType') in ('guide', 'folder', 'mask') or l.get('visible') == 'false':
                continue
            if skip and depth == 0 and skip(l.get('name', '')):
                continue
            fs = self.layer_frames(l)
            cur = None
            for i, f in enumerate(fs):
                s = int(f.get('index', 0)); dur = int(f.get('duration', 1))
                if s <= frame < s + dur:
                    cur = (i, f, s, dur); break
            if cur is None:
                continue
            i, f, s, dur = cur
            els = f.find(NS + 'elements')
            if els is None:
                continue
            nxt = fs[i + 1] if i + 1 < len(fs) else None
            t = (frame - s) / float(dur) if dur else 0.0
            for k, el in enumerate(list(els)):
                tag = el.tag.replace(NS, '')
                m = _m(el.find(NS + 'matrix'))
                a = alpha
                cxf = el.find(f'{NS}color/{NS}Color')
                if cxf is not None and cxf.get('alphaMultiplier') is not None:
                    a *= float(cxf.get('alphaMultiplier'))
                if f.get('tweenType') == 'motion' and nxt is not None:
                    nels = nxt.find(NS + 'elements')
                    if nels is not None and len(list(nels)) > k and list(nels)[k].get('libraryItemName') == el.get('libraryItemName'):
                        n_el = list(nels)[k]
                        m = tween(m, _m(n_el.find(NS + 'matrix')), t, int(f.get('acceleration', 0) or 0))
                        ncx = n_el.find(f'{NS}color/{NS}Color')
                        a0 = float(cxf.get('alphaMultiplier', 1)) if cxf is not None else 1.0
                        a1 = float(ncx.get('alphaMultiplier', 1)) if ncx is not None else 1.0
                        a = alpha * (a0 + (a1 - a0) * t)
                M = mul(parent, m)
                if tag == 'DOMBitmapInstance':
                    im = self.image(el.get('libraryItemName'))
                    if im is not None:
                        out.append((im, M, a, l.get('name', '')))
                elif tag == 'DOMSymbolInstance':
                    sym = self.symbol(el.get('libraryItemName'))
                    if sym is None:
                        continue
                    n = max(1, self.timeline_length(sym))
                    ff = int(el.get('firstFrame', 0))
                    loop = el.get('loop', 'loop')
                    local = frame - s
                    if loop == 'single frame':
                        sf = ff
                    elif loop == 'play once':
                        sf = min(n - 1, ff + local)
                    else:
                        sf = (ff + local) % n
                    for p in self.placements(sf, sym, M, a, None, depth + 1):
                        out.append(p[:3] + (l.get('name', ''),))
        return out

    def render(self, frame, size=None, origin=(0, 0), scale=1.0, skip=None):
        W, H = size or (int(self.width), int(self.height))
        cv = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        for im, M, a, _ in self.placements(frame, skip=skip):
            a_, b_, c_, d_, tx, ty = M
            a_, b_, c_, d_ = a_ * scale, b_ * scale, c_ * scale, d_ * scale
            tx = tx * scale + origin[0]; ty = ty * scale + origin[1]
            det = a_ * d_ - b_ * c_
            if abs(det) < 1e-9:
                continue
            # PIL affine takes the inverse mapping (output -> input)
            ia, ib, ic, id_ = d_ / det, -c_ / det, -b_ / det, a_ / det
            itx = -(ia * tx + ib * ty); ity = -(ic * tx + id_ * ty)
            src = im
            if a < 1:
                src = im.copy(); src.putalpha(im.getchannel('A').point(lambda v: int(v * max(0, a))))
            layer = src.transform((W, H), Image.AFFINE, (ia, ib, itx, ic, id_, ity), resample=Image.BICUBIC)
            cv.alpha_composite(layer)
        return cv


def layer_matrix(doc, frame, layer_name, timeline=None):
    """Matrix of the first element on a named layer at a frame (tweened), or None."""
    timeline = doc.main if timeline is None else timeline
    for l in doc.layers(timeline):
        if l.get('name') != layer_name:
            continue
        fs = doc.layer_frames(l)
        for i, f in enumerate(fs):
            s = int(f.get('index', 0)); dur = int(f.get('duration', 1))
            if s <= frame < s + dur:
                els = f.find(NS + 'elements')
                if els is None or not len(list(els)):
                    return None
                el = list(els)[0]; m = _m(el.find(NS + 'matrix'))
                nxt = fs[i + 1] if i + 1 < len(fs) else None
                if f.get('tweenType') == 'motion' and nxt is not None:
                    nels = nxt.find(NS + 'elements')
                    if nels is not None and len(list(nels)):
                        m = tween(m, _m(list(nels)[0].find(NS + 'matrix')), (frame - s) / float(dur), int(f.get('acceleration', 0) or 0))
                return m
    return None
