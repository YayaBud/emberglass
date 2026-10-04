"""Pixel-art tree and bush sprites, generated: the world's vegetation.

    python D:/assests/scripts/forge/foliage/trees.py

Writes `game/assets/foliage/<name>.png` (RGBA) and `manifest.json` (size in
metres, the trunk's foot in pixels), and a sheet at `renders/foliage/`.

Drawn at the sprite's own density, 52 texels/m (hd2d audit Law 2), the way a
pixel artist builds a tree rather than the way a 3D package would:

* the canopy is a pile of leaf CLUMPS, each shaded as a sphere under the
  scene's key (upper left, the side sun of `Grade.TwilightKit`), painted back
  to front so near clumps overlap far ones;
* every clump throws a drop shadow down-right onto what is behind it -- that
  shadow, not the outline, is what gives a canopy its depth;
* clump edges are broken into leaf shapes, the lit side speckled with lighter
  leaves and the dark side with darker ones;
* a tapered bark trunk with branches forking up into the canopy, lit on the
  left, and a selective outline: each edge pixel takes the darkest step of its
  OWN ramp, never black, so the silhouette reads without looking inked.

Every opaque pixel is a ramp colour (the same CIELAB ramps as texgen).
numpy + PIL only.
"""
import json
import math
import zlib
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "tex"))
from texgen import ramp  # noqa: E402

TPM = 52.0
OUT = os.path.join(ROOT, "game", "assets", "foliage")
SHEETS = os.path.join(ROOT, "renders", "foliage")
LIGHT = np.array([-0.62, -0.62, 0.48])      # x right, y down, z toward the viewer
LIGHT = LIGHT / np.linalg.norm(LIGHT)


class Canvas:
    """Per pixel: which ramp, which step, and whether anything is there."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.ramp = np.full((h, w), -1, dtype=np.int16)
        self.shade = np.zeros((h, w), dtype=np.int16)

    def put(self, mask, ramp_id, shade):
        self.ramp[mask] = ramp_id
        self.shade[mask] = shade[mask] if isinstance(shade, np.ndarray) else shade


def _value_noise(h, w, cell, rng):
    gh, gw = h // cell + 2, w // cell + 2
    g = rng.random((gh, gw))
    ys, xs = np.arange(h) / cell, np.arange(w) / cell
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0] * (1 - fx) + g[y0][:, x0 + 1] * fx
    b = g[y0 + 1][:, x0] * (1 - fx) + g[y0 + 1][:, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def trunk(cv, rng, x0, y_base, y_top, w_base, w_top, bark_id, branches=(), lean=0.0):
    """Tapered trunk from (x0, y_base) up to y_top, lit on its left, with
    vertical bark streaks; `branches` are (y_start_frac, dx, dy, width)."""
    h, w = cv.h, cv.w
    yy, xx = np.mgrid[0:h, 0:w]
    t = np.clip((y_base - yy) / max(y_base - y_top, 1), 0, 1)
    cx = x0 + lean * (y_base - yy) + np.sin(t * 3.1) * 3
    half = (w_base + (w_top - w_base) * t) / 2
    # root flare at the base
    half = half + np.clip(1 - (y_base - yy) / 14, 0, 1) ** 2 * w_base * 0.45
    inside = (yy <= y_base) & (yy >= y_top) & (np.abs(xx - cx) <= half)
    u = (xx - cx) / np.maximum(half, 1)          # -1 left edge .. +1 right edge
    shade = np.clip(np.round(3.4 - u * 1.9), 0, 6).astype(np.int16)
    streak = (_value_noise(h, w, 3, rng) > 0.62) & inside
    shade = shade - streak
    cv.put(inside, bark_id, shade)
    for (fy, dx, dy, bw) in branches:
        yb = y_base - (y_base - y_top) * fy
        xb = x0 + lean * (y_base - yb)
        n = int(max(abs(dx), abs(dy)))
        for i in range(n):
            s = i / max(n - 1, 1)
            px = xb + dx * s + math.sin(s * 5) * 1.5
            py = yb + dy * s
            r = bw * (1 - 0.6 * s) / 2
            m = (xx - px) ** 2 + (yy - py) ** 2 <= r * r
            su = np.clip((xx - px) / max(r, 1), -1, 1)
            cv.put(m, bark_id, np.clip(np.round(3.2 - su * 1.6), 0, 6).astype(np.int16))




def _fan(rng, size, kind):
    """A leaf spray as the references draw one: a FAN of 3-5 pointed leaves
    from a common stem, each leaf lit on its upper-left side and shaded on
    the other. Returns (mask, offset) -- offset is -1 on a leaf's shaded
    side, +1 on its lit side, 0 along its midrib. `kind` 'needle' makes long
    thin leaves drooping outward (conifers)."""
    S = int(size * 1.6) + 4
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    ox, oy = S / 2, 2.0
    tilt = rng.uniform(-25, 25)
    if kind == "needle":
        n, L, wid, spread = int(rng.integers(4, 6)), size * 0.95, 1.1, 130
    else:
        n, L, wid, spread = int(rng.integers(3, 6)), size * 0.75, 1.9, 110
    mask = np.zeros((S, S), dtype=bool)
    off = np.zeros((S, S), dtype=np.int16)
    for i in range(n):
        a = math.radians(90 + tilt + (i / max(n - 1, 1) - 0.5) * spread)   # 90 = straight down
        dx, dy = math.cos(a), math.sin(a)
        ln = L * rng.uniform(0.75, 1.05)
        # distance along and across this leaf's axis
        along = (xx - ox) * dx + (yy - oy) * dy
        across = -(xx - ox) * dy + (yy - oy) * dx
        t = along / ln
        # a teardrop: widest a third of the way out, pointed at the tip
        halfw = wid * np.clip(np.sin(np.clip(t, 0, 1) * math.pi) ** 0.7 * (1.25 - 0.5 * t), 0, None)
        leaf = (t >= 0) & (t <= 1) & (np.abs(across) <= halfw + 0.35)
        # which side of the midrib faces the key (upper left)
        side = np.sign(across) * np.sign(-dy * LIGHT[0] + dx * LIGHT[1] + 1e-9)
        o = np.where(np.abs(across) < 0.6, 0, np.where(side < 0, 1, -1))
        off[leaf] = o[leaf]
        mask |= leaf
    return mask, off


def _spray(cv, rng, px, py, w, h, kind, ramp_id, base):
    """Paint one spray whose stem sits at (px + w/2, py): a fan of leaves,
    the fan's top edge one step brighter still, then clipped to the canvas."""
    kind = "needle" if kind == "chevron" else "leaf"
    m, off = _fan(rng, max(w, h), kind)
    S = m.shape[0]
    x0, y0 = int(px + w / 2 - S / 2), int(py - 2)
    H, W = cv.h, cv.w
    xs0, ys0 = max(0, -x0), max(0, -y0)
    xs1, ys1 = min(S, W - x0), min(S, H - y0)
    if xs1 <= xs0 or ys1 <= ys0:
        return
    m = m[ys0:ys1, xs0:xs1]
    off = off[ys0:ys1, xs0:xs1]
    top = m & ~np.pad(m, ((1, 0), (0, 0)))[:-1]
    s = base + off + top.astype(np.int16)
    region = (slice(y0 + ys0, y0 + ys1), slice(x0 + xs0, x0 + xs1))
    cv.ramp[region][m] = ramp_id
    cv.shade[region][m] = np.clip(s, 0, 6)[m]


def _sprays_over(cv, rng, cx, cy, rx, ry, sw, kind, leaf_id, lam_of, protrude=0.12, gap=0.06, bottom_dark=True):
    """Lay leaf sprays over the ellipse (cx, cy, rx, ry), top row to bottom
    row, each lower spray over the one above. `lam_of(x, y)` gives the light
    at a spray's centre. Edge sprays may sit past the rim by `protrude`, so
    the silhouette is made of sprays, not of an ellipse."""
    sh = max(5, int(round(sw * (0.72 if kind == "scallop" else 1.1))))
    step_x, step_y = sw * 0.6, sh * 0.52
    rows = int((2 * ry * (1 + protrude)) / step_y) + 2
    for r in range(rows):
        y = cy - ry * (1 + protrude) + r * step_y
        cols = int((2 * rx * (1 + protrude)) / step_x) + 2
        for c in range(cols):
            x = cx - rx * (1 + protrude) + c * step_x + (step_x / 2 if r % 2 else 0) + rng.uniform(-2, 2)
            yj = y + rng.uniform(-2, 2)
            gx, gy = (x - cx) / rx, (yj - cy) / ry
            d2 = gx * gx + gy * gy
            if d2 > (1 + protrude * rng.uniform(0, 1)) ** 2:
                continue
            if d2 > 0.3 and rng.random() < gap:
                continue
            b = lam_of(x, yj)
            if bottom_dark and gy > 0.45:
                b -= 1
            w_ = int(sw * rng.uniform(0.7, 1.35))
            h_ = int(sh * rng.uniform(0.8, 1.2))
            _spray(cv, rng, x - w_ / 2, yj - h_ / 2, w_, h_, kind, leaf_id, int(np.clip(b, 0, 4)))


def _lam(gx, gy):
    gz = math.sqrt(max(0.05, 1 - min(gx * gx + gy * gy, 1)))
    return gx * LIGHT[0] + gy * LIGHT[1] + gz * LIGHT[2]


def canopy(cv, rng, cx, cy, rx, ry, n, r_lo, r_hi, leaf_id, rim_jag=0.35, spread_up=0.0, kind="scallop"):
    """A canopy the way the references build one: 5-8 big foliage masses,
    each a lump lit on its own upper left, painted back to front with the
    darkest greens showing between them; every mass is covered in leaf
    sprays whose tone mixes the mass's light with the whole tree's. `n` = the
    number of masses (0 = random 5-8); r_lo/r_hi = spray width range."""
    H, W = cv.h, cv.w
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    k = n or int(rng.integers(5, 9))
    masses = []
    for i in range(k):
        a = rng.uniform(0, 2 * math.pi)
        d = math.sqrt(rng.uniform(0.1, 1)) * 0.6
        mx = cx + math.cos(a) * rx * d
        my = cy + math.sin(a) * ry * d * 0.85 - spread_up * rng.uniform(0, 1)
        mrx, mry = rx * rng.uniform(0.40, 0.56), ry * rng.uniform(0.42, 0.6)
        masses.append((my + mry * 0.6, mx, my, mrx, mry))
    # one mass always crowns the top, so the silhouette is not flat
    masses.append((cy - ry * 0.55 + ry * 0.3, cx + rng.uniform(-rx, rx) * 0.2, cy - ry * 0.55, rx * 0.45, ry * 0.42))
    masses.sort()
    # the dark heart first: every mass's core in the darkest greens
    for _, mx, my, mrx, mry in masses:
        core = ((xx - mx) / (mrx * 0.9)) ** 2 + ((yy - my) / (mry * 0.9)) ** 2 <= 1
        cv.put(core, leaf_id, 1)
        cv.shade[core & (rng.random((H, W)) < 0.25)] = 0
    sw = int(round((r_lo + r_hi) / 2))
    for _, mx, my, mrx, mry in masses:
        def lam_of(x, y, mx=mx, my=my, mrx=mrx, mry=mry):
            loc = _lam((x - mx) / mrx, (y - my) / mry)
            glo = _lam((x - cx) / (rx * 1.2), (y - cy) / (ry * 1.25))
            return round(1.6 + (0.5 * loc + 0.5 * glo) * 3.2)
        _sprays_over(cv, rng, mx, my, mrx, mry, sw, kind, leaf_id, lam_of)
    return None


def outline(cv, ramps):
    """Selective outline: silhouette pixels one step darker than their own
    ramp's darkest-but-one, so the edge reads without a black ink line."""
    solid = cv.ramp >= 0
    edge = solid & ~(np.roll(solid, 1, 0) & np.roll(solid, -1, 0) & np.roll(solid, 1, 1) & np.roll(solid, -1, 1))
    cv.shade[edge] = np.minimum(cv.shade[edge], 1)
    cv.shade[edge & (cv.shade > 0)] -= 1


def render(cv, ramps):
    out = np.zeros((cv.h, cv.w, 4), dtype=np.uint8)
    for i, r in enumerate(ramps):
        m = cv.ramp == i
        out[m, :3] = r[np.clip(cv.shade[m], 0, len(r) - 1)]
        out[m, 3] = 255
    return out


# ---------------------------------------------------------------------------
# species
# ---------------------------------------------------------------------------

OAK = [("#5d4630", 7), ("#4e7a2e", 7)]
BIRCH = [("#d8d2c4", 7), ("#7a9a38", 7)]
PINE = [("#4d3a2a", 7), ("#2f5a3a", 7)]
BUSH = [("#4d3a2a", 7), ("#467034", 7)]


def oak(rng, height_m=7.2, width_m=6.4):
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    trunk(cv, rng, W / 2, base, H * 0.42, 30, 14, 0,
          branches=[(0.55, -W * 0.22, -H * 0.2, 12), (0.62, W * 0.2, -H * 0.24, 11), (0.8, -W * 0.05, -H * 0.3, 9)],
          lean=rng.uniform(-0.05, 0.05))
    canopy(cv, rng, W / 2, H * 0.37, W * 0.40, H * 0.28, 0, 13, 19, 1)
    outline(cv, None)
    return cv, OAK, base


def birch(rng, height_m=7.6, width_m=4.2):
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    trunk(cv, rng, W / 2, base, H * 0.25, 16, 8, 0,
          branches=[(0.5, -W * 0.18, -H * 0.12, 6), (0.62, W * 0.18, -H * 0.16, 6)],
          lean=rng.uniform(-0.06, 0.06))
    # birch bark: dark lenticels across the white
    yy, xx = np.mgrid[0:H, 0:W]
    marks = (cv.ramp == 0) & ((yy + (xx * 0.3).astype(int)) % 17 < 2) & (rng.random((H, W)) < 0.7)
    cv.shade[marks] = 0
    canopy(cv, rng, W / 2, H * 0.30, W * 0.36, H * 0.25, 0, 11, 14, 1, spread_up=10)
    outline(cv, None)
    return cv, BIRCH, base


def pine(rng, height_m=8.4, width_m=4.4):
    """A conifer of drooping tiers: each tier a skirt of needle sprays, dark
    underneath, the lower tiers laid over the upper ones; lit from the left."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    trunk(cv, rng, W / 2, base, H * 0.15, 16, 7, 0)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    top, bottom = H * 0.02, H * 0.84
    tiers = int(rng.integers(7, 10))
    for i in range(tiers):
        f = (i + 1) / tiers
        hem = top + (bottom - top) * f
        apex = top + (bottom - top) * max(0, f - 1.9 / tiers)
        half = W * 0.47 * f ** 0.85 * rng.uniform(0.9, 1.05)
        # the skirt's dark body, visible between sprays and under the hem
        t = np.clip((yy - apex) / max(hem - apex, 1), 0, 1)
        body = (yy >= apex) & (yy <= hem) & (np.abs(xx - W / 2) <= half * t ** 0.9)
        cv.put(body, 1, 1)
        cv.shade[body & (yy > hem - 6)] = 0

        def lam_of(x, y, apex=apex, hem=hem, half=half):
            gx = (x - W / 2) / max(half, 1)
            gy = (y - (apex + hem) / 2) / max((hem - apex) / 2, 1)
            return round(2.0 + (-gx * 0.7 - gy * 0.35 + 0.35) * 2.2)
        sw = 13
        sh = 13
        y = apex
        while y < hem - sh * 0.4:
            tt = np.clip((y - apex) / max(hem - apex, 1), 0, 1)
            hw = half * tt ** 0.9
            n = max(1, int(2 * hw / (sw * 0.62)))
            for j in range(n):
                x = W / 2 - hw + (j + 0.5) * (2 * hw / n) + rng.uniform(-2, 2)
                b = lam_of(x, y) - (1 if tt > 0.75 else 0)
                w_ = int(sw * rng.uniform(0.8, 1.2))
                _spray(cv, rng, x - w_ / 2, y + rng.uniform(-2, 2), w_, int(sh * rng.uniform(0.85, 1.2)),
                       "chevron", 1, int(np.clip(b, 0, 4)))
            y += sh * 0.48
    outline(cv, None)
    return cv, PINE, base


def bush(rng, height_m=1.5, width_m=2.4):
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    canopy(cv, rng, W / 2, H * 0.56, W * 0.42, H * 0.36, 3, 10, 13, 1)
    outline(cv, None)
    return cv, BUSH, base


VINE_OAK = [("#5d4630", 7), ("#3f6b2e", 7), ("#6f9a3a", 7)]
FERN = [("#4d3a2a", 7), ("#4f8a34", 7)]
LOG = [("#5a4430", 7), ("#5d8a32", 7), ("#b89262", 7)]


def ivy(cv, rng, ivy_id, on=0):
    """Ivy up whatever ramp `on` holds (a trunk), in spiralling bands; each
    leaf keeps the host's shade, so it is lit on the same side."""
    H, W = cv.h, cv.w
    yy, xx = np.mgrid[0:H, 0:W]
    # stripes warped by noise and broken into patches: straight bands read as a barber pole
    warp = (_value_noise(H, W, 7, rng) * 22).astype(int)
    band = ((yy + (xx * 1.4).astype(int) + warp) % 19 < 6) & (_value_noise(H, W, 5, rng) > 0.45)
    leaf = (cv.ramp == on) & band & (rng.random((H, W)) < 0.75)
    cv.put(leaf, ivy_id, np.clip(cv.shade + 1, 1, 5))


def hanging_vines(cv, rng, leaf_id, vine_id, n, max_len):
    """Strands hanging from the canopy's underside: a 1 px stem swaying a
    little, a leaf pair every 4 px, the leaf's left pixel lit. Drawn after
    the outline, or the outline would eat a 1 px strand whole."""
    H, W = cv.h, cv.w
    cols = np.nonzero((cv.ramp == leaf_id).any(axis=0))[0]
    cols = cols[(cols > cols.min() + 8) & (cols < cols.max() - 8)]
    for _ in range(n):
        x = int(rng.choice(cols))
        y0 = int(np.nonzero(cv.ramp[:, x] == leaf_id)[0].max()) - int(rng.integers(2, 10))
        L = int(max_len * rng.uniform(0.3, 1.0))
        ph, fq = rng.uniform(0, 6.28), rng.uniform(0.05, 0.12)
        for i in range(L):
            px, py = int(round(x + math.sin((y0 + i) * fq + ph) * 1.5)), y0 + i
            if not (1 <= px < W - 2 and 0 <= py < H - 1):
                break
            cv.ramp[py, px], cv.shade[py, px] = vine_id, 1
            if i % 4 == 0 and i < L - 2:
                s = 1 if (i // 4) % 2 else -1
                for dx, dy, sh in ((s, 0, 4 if s < 0 else 2), (2 * s, 1, 3 if s < 0 else 1), (s, 1, 2)):
                    if 0 <= px + dx < W and py + dy < H:
                        cv.ramp[py + dy, px + dx], cv.shade[py + dy, px + dx] = vine_id, sh


def vine_oak(rng, height_m=7.8, width_m=6.8):
    """An old oak gone over to ivy, strung with hanging vines."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    trunk(cv, rng, W / 2, base, H * 0.42, 36, 16, 0,
          branches=[(0.55, -W * 0.24, -H * 0.18, 13), (0.6, W * 0.22, -H * 0.22, 12), (0.82, W * 0.04, -H * 0.3, 9)],
          lean=rng.uniform(-0.05, 0.05))
    canopy(cv, rng, W / 2, H * 0.36, W * 0.42, H * 0.28, 0, 13, 19, 1)
    ivy(cv, rng, 2)
    outline(cv, None)
    hanging_vines(cv, rng, 1, 2, 30, H * 0.42)
    return cv, VINE_OAK, base


def fern(rng, height_m=1.3, width_m=2.1):
    """Fronds arching out from one crown, back ones first and darker; each
    frond a midrib with leaflets tapering to the tip, upper side lit."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    fronds = sorted(rng.uniform(-1, 1, int(rng.integers(9, 13))), key=abs, reverse=True)
    for f in fronds:
        th = f * 1.2                                   # radians from vertical
        L = H * rng.uniform(0.9, 1.1) * (1 - 0.15 * abs(f))
        curl = np.sign(f) * rng.uniform(0.6, 1.1)       # arches outward and down
        back = -1 if abs(f) > 0.6 else 0
        x, y = W / 2 + rng.uniform(-3, 3), float(base)
        n = int(L)
        for i in range(n):
            t = i / n
            a = th + curl * t * t
            dx, dy = math.sin(a), -math.cos(a)
            x, y = x + dx, y + dy
            # leaflets on every other step, so they read apart, not as one blade
            lw = 10 * (1 - t) ** 0.8 * min(1, t * 6) if i % 2 == 0 else 0
            for side in (1, -1):
                nx, ny = -dy * side + dx * 0.9, dx * side + dy * 0.9
                nn = math.hypot(nx, ny)
                up = ny < 0
                for k in range(int(lw)):
                    qx, qy = int(round(x + nx / nn * k)), int(round(y + ny / nn * k))
                    if 0 <= qx < W and 0 <= qy <= base:
                        cv.ramp[qy, qx] = 1
                        cv.shade[qy, qx] = int(np.clip((4 if up else 2) + back - (k > lw * 0.7), 0, 6))
            qx, qy = int(round(x)), int(round(y))
            if 0 <= qx < W and 0 <= qy <= base:
                cv.ramp[qy, qx], cv.shade[qy, qx] = 1, 3 + back
    outline(cv, None)
    return cv, FERN, base


def log(rng, length_m=3.0, dia_m=0.7):
    """A fallen trunk lying across the view: lit along its top, bark
    streaked lengthways, moss on the crown, the sawn end showing rings."""
    W, H = int((length_m + 0.3) * TPM), int((dia_m + 0.35) * TPM)
    cv = Canvas(W, H)
    base = H - 2
    r = dia_m * TPM / 2
    cy = base - r
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    x0, x1 = 8, W - 8 - r * 0.45
    wob = (_value_noise(H, W, 9, rng) - 0.5) * 3
    v = (yy - cy) / r
    body = (xx >= x0 + np.abs(v) * 4) & (xx <= x1) & (np.abs(v) <= 1 + wob / r)
    streak = (_value_noise(H, W // 6 + 1, 2, rng).repeat(6, axis=1)[:, :W] > 0.6)
    shade = np.clip(np.round(3.3 - v * 2.0) - streak, 0, 6).astype(np.int16)
    cv.put(body, 0, shade)
    moss = body & (v < -0.35 + wob * 0.1) & (_value_noise(H, W, 5, rng) > 0.4)
    cv.put(moss, 1, np.clip(np.round(4.2 + v * 1.5), 2, 5).astype(np.int16))
    d = np.sqrt(((xx - x1) / (r * 0.45)) ** 2 + ((yy - cy) / r) ** 2)
    cv.put(d <= 1, 2, np.where((d * 4.5).astype(int) % 2 == 0, 4, 3).astype(np.int16))
    for _ in range(3):   # shelf fungus on the flank
        fx, fy = rng.uniform(x0 + 20, x1 - 30), cy + r * rng.uniform(0.0, 0.5)
        m = (((xx - fx) / 7) ** 2 + ((yy - fy) / 3) ** 2 <= 1) & (yy <= fy + 1)
        cv.put(m, 2, np.where(yy < fy - 1, 5, 3).astype(np.int16))
    outline(cv, None)
    return cv, LOG, base


REED = [("#6a8a3a", 7), ("#5a3a24", 7)]


def reed(rng, height_m=1.7, width_m=1.1):
    """A clump of reeds: thin blades leaning out from one root, lit on the
    left, a few with a cattail head."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    for _ in range(int(rng.integers(14, 22))):
        lean = rng.uniform(-0.35, 0.35)
        L = H * rng.uniform(0.45, 0.95)
        x0 = W / 2 + rng.uniform(-6, 6)
        bend = rng.uniform(-0.15, 0.15)
        n = int(L)
        for i in range(n):
            t = i / n
            x = x0 + (lean + bend * t) * L * t
            y = base - i
            w = 2 if t < 0.6 else 1
            for dx in range(w):
                px = int(round(x)) + dx
                if 0 <= px < W and 0 <= y < H:
                    cv.ramp[y, px] = 0
                    cv.shade[y, px] = (4 if dx == 0 else 2) - (1 if t < 0.2 else 0)
        if rng.random() < 0.35:
            hx, hy = x0 + (lean + bend * 0.85) * L * 0.85, base - int(L * 0.85)
            for yy in range(int(hy) - 5, int(hy) + 5):
                for xx in range(int(round(hx)) - 1, int(round(hx)) + 2):
                    if 0 <= xx < W and 0 <= yy < H:
                        cv.ramp[yy, xx] = 1
                        cv.shade[yy, xx] = 4 if xx < hx else 2
    outline(cv, None)
    return cv, REED, base


# ---------------------------------------------------------------------------
# the four new regions (implementation_plan B1, 2026-09-28)
# ---------------------------------------------------------------------------

AUTUMN_LEAVES = ["#b8622c", "#c98f2e", "#a8452c"]   # orange, gold, rust


def autumn_oak(rng, height_m=7.0, width_m=6.4):
    """The Emberwood's oak: the oak's shape, its leaves turned."""
    cv, _, base = oak(rng, height_m, width_m)
    return cv, [("#5d4630", 7), (AUTUMN_LEAVES[int(rng.integers(0, 3))], 7)], base


def autumn_birch(rng, height_m=7.4, width_m=4.2):
    cv, _, base = birch(rng, height_m, width_m)
    return cv, [("#d8d2c4", 7), ("#d2a634", 7)], base


def snag(rng, height_m=6.0, width_m=3.8):
    """A dead standing tree (the Fen's drowned woods): a bare trunk, a few broken
    limbs, grey-green lichen in patches."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    trunk(cv, rng, W / 2, base, H * 0.1, 24, 6, 0,
          branches=[(0.42, -W * 0.3, -H * 0.16, 7), (0.55, W * 0.3, -H * 0.2, 6),
                    (0.7, -W * 0.2, -H * 0.14, 5), (0.82, W * 0.16, -H * 0.1, 4)],
          lean=rng.uniform(-0.08, 0.08))
    lichen = (cv.ramp == 0) & (_value_noise(H, W, 4, rng) > 0.68)
    cv.put(lichen, 1, np.clip(cv.shade + 1, 1, 5))
    outline(cv, None)
    return cv, [("#6b5f52", 7), ("#7d8a5a", 7)], base


def willow(rng, height_m=7.0, width_m=7.2):
    """A weeping willow: a broad low crown and a curtain of hanging strands."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    trunk(cv, rng, W / 2, base, H * 0.45, 34, 16, 0,
          branches=[(0.6, -W * 0.25, -H * 0.15, 12), (0.65, W * 0.25, -H * 0.17, 12)],
          lean=rng.uniform(-0.06, 0.06))
    canopy(cv, rng, W / 2, H * 0.33, W * 0.44, H * 0.22, 0, 11, 15, 1)
    outline(cv, None)
    hanging_vines(cv, rng, 1, 1, 110, H * 0.58)
    return cv, [("#5a4a3a", 7), ("#6e8f3c", 7)], base


FLOWER = ["#c8342c", "#4a64c8", "#e0b62c", "#e8e2d8", "#b04a9a"]   # poppy, cornflower, buttercup, daisy, campion


def flowers(rng, height_m=0.7, width_m=1.3):
    """A wildflower drift: a low leafy mound strewn with 2x2 blossoms of one colour."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    canopy(cv, rng, W / 2, H * 0.62, W * 0.44, H * 0.3, 3, 7, 9, 0)
    for _ in range(int(W * H / 55)):
        x, y = int(rng.integers(2, W - 3)), int(rng.integers(2, int(H * 0.72)))
        if cv.ramp[y, x] >= 0:
            cv.ramp[y:y + 2, x:x + 2] = 1
            cv.shade[y:y + 2, x:x + 2] = np.array([[5, 4], [4, 2]])
    outline(cv, None)
    return cv, [("#4c7a30", 7), (FLOWER[int(rng.integers(0, len(FLOWER)))], 7)], base


def mushroom(rng, height_m=0.55, width_m=0.8):
    """A clump of red-capped toadstools, white-spotted, pale stems lit on the left."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    for _ in range(int(rng.integers(3, 6))):
        cx = rng.uniform(W * 0.22, W * 0.78)
        f = rng.uniform(0.35, 1.0)
        top = base - f * (H - 12)
        r = rng.uniform(5, 9) * (0.6 + 0.4 * f)
        stem = (np.abs(xx - cx) <= 2) & (yy <= base) & (yy >= top)
        cv.put(stem, 0, np.where(xx < cx, 5, 3).astype(np.int16))
        cap = (((xx - cx) / r) ** 2 + ((yy - top) / (r * 0.6)) ** 2 <= 1) & (yy <= top + 1)
        cv.put(cap, 1, np.clip(np.round(4 - (xx - cx) / r * 1.5 + (yy - top) / r * 2), 1, 5).astype(np.int16))
        cv.put(cap & (rng.random((H, W)) < 0.12), 0, 6)
    outline(cv, None)
    return cv, [("#e2dccb", 7), ("#b8302a", 7)], base


def wheat(rng, height_m=1.2, width_m=1.2):
    """A clump of ripe grain: golden stalks leaning out, most carrying a head."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    for _ in range(int(rng.integers(16, 24))):
        lean = rng.uniform(-0.25, 0.25)
        L = H * rng.uniform(0.6, 0.96)
        x0 = W / 2 + rng.uniform(-8, 8)
        x = x0
        for i in range(int(L)):
            t = i / L
            x = x0 + lean * L * t * t
            px, y = int(round(x)), base - i
            if 0 <= px < W and 0 <= y < H:
                cv.ramp[y, px], cv.shade[y, px] = 0, 3 - (1 if t < 0.25 else 0)
        if rng.random() < 0.8:
            hx, hy = int(round(x)), int(base - L)
            for k in range(7):
                for dx in (0, 1):
                    if 0 <= hx + dx < W and 0 <= hy + k < H:
                        cv.ramp[hy + k, hx + dx], cv.shade[hy + k, hx + dx] = 1, 5 if dx == 0 else 3
    outline(cv, None)
    return cv, [("#9a8a3a", 7), ("#d8b24a", 7)], base


def heather(rng, height_m=0.8, width_m=1.6):
    """Heather on the Crags: a low dark mound, its top half speckled purple."""
    W, H = int(width_m * TPM), int(height_m * TPM)
    cv = Canvas(W, H)
    base = H - 2
    canopy(cv, rng, W / 2, H * 0.6, W * 0.44, H * 0.34, 3, 7, 10, 0)
    yy = np.mgrid[0:H, 0:W][0]
    bloom = (cv.ramp == 0) & (yy < H * 0.62) & (rng.random((H, W)) < 0.4)
    cv.put(bloom, 1, np.clip(cv.shade + 1, 1, 5))
    outline(cv, None)
    return cv, [("#3e5a34", 7), ("#9a5a9a", 7)], base


SPECIES = {"oak": oak, "birch": birch, "pine": pine, "bush": bush,
           "vine_oak": vine_oak, "fern": fern, "log": log, "reed": reed,
           "autumn_oak": autumn_oak, "autumn_birch": autumn_birch, "snag": snag, "willow": willow,
           "flowers": flowers, "mushroom": mushroom, "wheat": wheat, "heather": heather}
VARIANTS = {"oak": 3, "birch": 2, "pine": 2, "bush": 3, "vine_oak": 2, "fern": 3, "log": 2, "reed": 3,
            "autumn_oak": 3, "autumn_birch": 2, "snag": 2, "willow": 2,
            "flowers": 5, "mushroom": 2, "wheat": 2, "heather": 2}


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SHEETS, exist_ok=True)
    manifest, tiles = {}, []
    for sp, fn in SPECIES.items():
        for v in range(VARIANTS[sp]):
            name = f"{sp}_{v}"
            rng = np.random.default_rng(zlib.crc32(name.encode()))
            cv, ramp_defs, foot = fn(rng)
            ramps = [ramp(b, n) for b, n in ramp_defs]
            rgba = render(cv, ramps)
            # palette-only check
            allowed = {tuple(c) for r in ramps for c in r}
            op = rgba[..., 3] == 255
            bad = {tuple(c) for c in rgba[op][:, :3]} - allowed
            assert not bad, f"{name}: off-palette pixels"
            Image.fromarray(rgba).save(os.path.join(OUT, name + ".png"))
            manifest[name] = dict(px=[cv.w, cv.h], metres=[round(cv.w / TPM, 3), round(cv.h / TPM, 3)],
                                  foot_px=int(cv.h - 1 - foot))
            tiles.append((name, rgba))
            print(f"foliage: {name:<8} {cv.w}x{cv.h} px  {cv.w / TPM:.1f} x {cv.h / TPM:.1f} m  opaque {op.mean() * 100:.0f}%")
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(dict(texels_per_m=TPM, sprites=manifest), f, indent=1)
    # sheet: every sprite on a mid-grey ground, 1:1
    W = sum(t[1].shape[1] for t in tiles) + 10 * (len(tiles) + 1)
    H = max(t[1].shape[0] for t in tiles) + 40
    sheet = Image.new("RGB", (W, H), (96, 104, 88))
    x = 10
    d = ImageDraw.Draw(sheet)
    for name, rgba in tiles:
        im = Image.fromarray(rgba)
        sheet.paste(im, (x, H - 10 - im.height), im)
        d.text((x, 4), name, fill=(255, 255, 255))
        x += im.width + 10
    sheet.save(os.path.join(SHEETS, "trees.png"))
    print("foliage: sheet", os.path.join(SHEETS, "trees.png"))


if __name__ == "__main__":
    main()
