"""Pixel-art tileable surfaces for the world: albedo, normal and ORM maps.

    python D:/assests/scripts/forge/tex/texgen.py            # self-check, write every surface + sheet
    python D:/assests/scripts/forge/tex/texgen.py cobble     # one surface

Density is the sprite's own, 52 texels/m (hd2d audit Law 2): the character is
96 px for 1.85 m, and a world drawn at the same texel size is what stops the
figure looking pasted on. Units are sized for that -- a brick is 16x6 texels
(0.31 x 0.12 m), a cobble ~13, a shingle 16x7 -- and rounded up from real size
where real size would fall under the ~6 px it takes to read as a shape.

Every surface is three per-texel layers built on a TORUS, so every tile wraps:

    ramp   which colour ramp the texel is painted from (stone, mortar, moss...)
    shade  index into that ramp; the ramp's middle step is the base colour
    height 0..1 relief, for the normal map and for cavity AO

The albedo is therefore palette-only by construction -- every texel is one of
the ramps' colours, the invariant the self-check asserts, the same discipline
`player_paint.py` holds for the character. Ramps are built in CIELAB with a
hue shift (darker steps cooler, lighter warmer), which is what pixel-art ramps
do and what a flat multiply of the base colour cannot.

What made the reference surfaces measure 2.9-7.6 L* gradient against our flat
1.7-2.0 (findings 2026-09-23) is structure: a dark gap between every unit, a
lit top-left rim and a shaded bottom-right one on each unit, and a tone that
differs unit to unit. Every recipe below is built from those three moves.

numpy + PIL only.
"""
import json
import os
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TEXELS_PER_M = 52.0
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "game", "assets", "tex")
SHEETS = os.path.join(ROOT, "renders", "tex")

# Provisional gates on the raw albedo, set above the render targets (L*
# gradient >= 3.0, std >= 16 on a 980-wide frame crop) because lighting, the
# 1280 -> 980 resample and DoF all soften a texture on its way to the screen.
# Phase 2 calibrates these against real renders.
GATE_GRAD = 4.5
GATE_STD = 16.0

# Calm ground (user, 2026-09-27, option A after four reference videos): the
# streets and the world's terrain are gated from ABOVE. The game frame's
# ground measured 3-19x the videos' detail (findings 2026-09-27), so for these
# surfaces the floor above is reversed; walls and roofs keep it. The gradient
# is judged per 52/m texel (x DENSITY): the frame sees metres, and an HD tile
# of the same stones measures half the gradient per texel. Calm means SPARSE
# features at a readable step (fewer blades, pebbles, cracks; bigger cobbles),
# not every feature faded -- faint everywhere reads as mush.
CALM = {"cobble", "flagstone", "dirt", "cobble_hd", "dirt_hd", "grass_hd", "paving_brick", "setts", "setts_lg", "limestone",
        # walls and roofs (2026-09-27, the pass after the ground): what the city and
        # village kits are built from; desert, snow and cloth keep the floor
        "planks", "timber", "ashlar", "ashlar_big", "fieldstone", "slate", "slate_blue", "moss", "brick", "plaster",
        "thatch", "clay_tile", "shingle", "bark"}
CALM_GRAD = 3.0
CALM_STD = 12.0
# Deep stones (user, 2026-09-27: "the ground is too flat ... look at the
# reference photos"): the streets' stones are separate raised units in a dark
# gap, as every reference draws them. The calm gate holds on the FACES only
# (the gap is structure, not noise), and the gap must sit STRUCT_GAP L* below.
STRUCT = {"cobble", "cobble_hd", "flagstone", "paving_brick", "setts", "setts_lg", "limestone",
          # masonry walls (2026-09-28): the same deep joints, calm faces
          "brick", "ashlar", "ashlar_big", "fieldstone"}
STRUCT_GAP = 22.0
# Normal-map strength per surface (default 2.2): under a low sun the ground's
# relief is shading noise on top of the albedo's -- except the domed stones.
NORMAL = {n: (1.8 if n in STRUCT else 1.0) for n in CALM}
# Warm stone (user, 2026-09-29: "it is all grey ... too brutalist"): each stone
# of these surfaces takes one of three face ramps -- the base and two hue-turned
# variants (degrees, same L* and chroma) -- so a wall reads as sorted natural
# stone, not poured concrete. Variety by variant, not by pixel noise. The
# variants are ramps 3 and 4 (after the recipe's own), picked per unit by an rng
# of their own, so the recipe's draws -- and every other surface -- are untouched.
HUE = {"ashlar": (-16, 14), "ashlar_big": (-16, 14), "flagstone": (-14, 12), "fieldstone": (-16, 14),
       "cobble": (-14, 12), "cobble_hd": (-14, 12), "setts_lg": (-14, 12), "limestone": (-10, 10)}
HUE_SHARE = (0.5, 0.25, 0.25)


# ---------------------------------------------------------------------------
# colour: sRGB <-> CIELAB, and hue-shifted ramps
# ---------------------------------------------------------------------------

def _hex(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0


def _to_lab(rgb):
    rgb = np.asarray(rgb, dtype=np.float64)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def _from_lab(lab):
    lab = np.asarray(lab, dtype=np.float64)
    fy = (lab[..., 0] + 16) / 116
    fx = fy + lab[..., 1] / 500
    fz = fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    lin = np.clip(xyz @ m.T, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)


def ramp(base, steps=7, dl=11.0, shift=2.0):
    """`steps` colours around `base` (sRGB hex), middle = base. Each step
    down loses `dl` L* and shifts b* by -shift (cooler) and a* by +shift/3
    (a touch of violet in the darks); each step up the opposite. Returns
    uint8 [steps, 3]."""
    lab = _to_lab(_hex(base))
    mid = steps // 2
    out = []
    for k in range(steps):
        d = k - mid
        out.append(lab + np.array([dl * d, -shift * d / 3, shift * d]))
    return np.round(_from_lab(np.array(out)) * 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# toroidal primitives -- every one wraps, so every tile built from them does
# ---------------------------------------------------------------------------

def value_noise(h, w, cell, rng, octaves=1, cellx=None):
    """Smooth value noise in 0..1 on an h x w torus. `cell` (and `cellx`,
    for stretched grain) must divide h and w; each octave halves them."""
    assert h % cell == 0 and w % (cellx or cell) == 0, (h, w, cell, cellx)
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    c, cx = cell, (cellx or cell)
    for _ in range(octaves):
        gh, gw = h // c, w // cx
        grid = rng.random((gh, gw))
        ys, xs = np.arange(h) / c, np.arange(w) / cx
        y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
        fy, fx = ys - y0, xs - x0
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        y0, x0 = y0 % gh, x0 % gw
        y1, x1 = (y0 + 1) % gh, (x0 + 1) % gw
        a = grid[y0][:, x0] * (1 - fx) + grid[y0][:, x1] * fx
        b = grid[y1][:, x0] * (1 - fx) + grid[y1][:, x1] * fx
        out += amp * (a * (1 - fy[:, None]) + b * fy[:, None])
        total += amp
        amp *= 0.5
        c, cx = max(1, c // 2), max(1, cx // 2)
    return out / total


def clumps(h, w, cell, rng, density):
    """Blotches covering ~density of the tile: value noise, thresholded."""
    n = value_noise(h, w, cell, rng, 2)
    return n > np.quantile(n, 1 - density)


def voronoi(h, w, cell, rng, jitter=0.9, sx=1.0):
    """Jittered-grid Voronoi on the torus. One site per `cell` x `cell*sx`
    grid cell. Returns (id, edge): the nearest site's id and the distance
    from the cell edge (half the gap between nearest and second-nearest)."""
    cw = int(round(cell * sx))
    gh, gw = h // cell, w // cw
    sy = (np.arange(gh)[:, None] + 0.5 + (rng.random((gh, gw)) - 0.5) * jitter) * cell
    sxp = (np.arange(gw)[None, :] + 0.5 + (rng.random((gh, gw)) - 0.5) * jitter) * cw
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    ci, cj = (yy // cell).astype(int), (xx // cw).astype(int)
    d1 = np.full((h, w), 1e9)
    d2 = np.full((h, w), 1e9)
    ident = np.zeros((h, w), dtype=np.int64)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ni, nj = ci + di, cj + dj
            wi, wj = ni % gh, nj % gw
            py = sy[wi, wj] + (ni - wi) * cell
            px = sxp[wi, wj] + (nj - wj) * cw
            # anisotropic distance: stretched cells read as flat laid stone
            d = np.hypot((yy - py), (xx - px) / sx)
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            ident = np.where(closer, wi * gw + wj, ident)
            d1 = np.where(closer, d, d1)
    return ident, (d2 - d1) / 2


def bevel(inside, dist):
    """Shade offsets that make a unit read as raised under a top-left light:
    +1 on texels whose upper or left neighbour is outside the unit, -1 where
    the lower or right one is. `inside` is the unit mask; `dist` the texel's
    distance to the unit edge (texels deeper than 1.5 get no rim)."""
    up = np.roll(inside, 1, 0)
    left = np.roll(inside, 1, 1)
    down = np.roll(inside, -1, 0)
    right = np.roll(inside, -1, 1)
    off = np.zeros(inside.shape, dtype=np.int16)
    rim = inside & (dist < 1.5)
    off[rim & (~up | ~left)] += 1
    off[rim & (~down | ~right)] -= 1
    return off


def per_unit(ident, rng, choices, weights):
    """A random value per unit id, looked up per texel."""
    n = int(ident.max()) + 1
    table = rng.choice(choices, size=n, p=weights)
    return table[ident]


def cracks(h, w, rng, count, length):
    """Thin random-walk cracks on the torus: bool mask."""
    m = np.zeros((h, w), dtype=bool)
    for _ in range(count):
        y, x = rng.integers(0, h), rng.integers(0, w)
        dy, dx = rng.choice([-1, 0, 1]), rng.choice([-1, 1])
        for _ in range(length):
            m[y % h, x % w] = True
            if rng.random() < 0.35:
                dy = int(np.clip(dy + rng.choice([-1, 1]), -1, 1))
            y, x = y + dy, x + dx
    return m


# ---------------------------------------------------------------------------
# surfaces -- each returns (size, layers) where layers = dict(ramp, shade, height)
# ---------------------------------------------------------------------------

class Layers:
    def __init__(self, h, w, mid):
        self.ramp = np.zeros((h, w), dtype=np.int8)
        self.shade = np.full((h, w), mid, dtype=np.int16)
        self.height = np.ones((h, w))
        self.unit = None   # per-texel unit id, set by `_units` (for HUE)


def _units(L, inside, dist, ident, rng, tones=(-1, 0, 0, 1), rim=True, depth=1.0, dome=0.0, gap_shade=1):
    """The shared move: gaps to ramp 1 at its dark end, a tone per unit, a
    bevelled rim, height that rises off the gap over ~2 texels. `dome` > 0
    (texels): the height keeps rising to the unit's middle, a rounded top
    the sun shades one side of (user, 2026-09-27: "the ground is too flat")."""
    tone = per_unit(ident, rng, np.array(tones), None)
    L.unit = ident
    L.shade = L.shade + np.where(inside, tone, 0)
    if rim:
        L.shade = L.shade + bevel(inside, dist)
    # the top row of a unit catches the light: one more step
    top = inside & ~np.roll(inside, 1, 0)
    L.shade = L.shade + (top & (dist < 1.5))
    L.ramp = np.where(inside, L.ramp, 1).astype(np.int8)
    L.shade = np.where(inside, L.shade, gap_shade)
    if dome > 0:
        L.height = np.where(inside, 0.45 + 0.55 * np.sqrt(np.clip(dist / dome, 0, 1)), 0.0)
    else:
        L.height = np.where(inside, np.clip(0.35 + dist / 2.5, 0, 1) * depth + (1 - depth) * 0.5, 0.0)


def s_brick(rng, bw=16, bh=6, w=512, h=504, mortar=1, dome=0.0, gap_shade=1):
    assert w % bw == 0 and h % bh == 0 and (h // bh) % 2 == 0, (w, h, bw, bh)
    L = Layers(h, w, 3)
    yy, xx = np.mgrid[0:h, 0:w]
    row = yy // bh
    off = (row % 2) * (bw // 2)
    col = ((xx + off) // bw) % (w // bw)
    ly, lx = yy % bh, (xx + off) % bw
    inside = (ly >= mortar) & (lx >= mortar)
    ident = row * (w // bw) + col
    dist = np.minimum.reduce([ly - mortar + 0.5, lx - mortar + 0.5, bh - ly - 0.5, bw - lx - 0.5]).astype(float)
    # chipped corners: a few bricks lose a corner texel to the mortar
    chip = (per_unit(ident, rng, np.array([0, 1]), [0.8, 0.2]) == 1) & (ly == mortar) & (lx == mortar)
    inside &= ~chip
    _units(L, inside, dist, ident, rng, tones=(-1, 0, 0, 1, 1), dome=dome, gap_shade=gap_shade)
    L.shade[inside & clumps(h, w, 8, rng, 0.18)] -= 1
    return L


def s_cobble(rng, cell=13, w=520, h=520, gap=1.6, k=1, pits=0.04, dome=0.0, gap_shade=1):
    """`k` = texel density multiple: the same stones in metres, k x the texels."""
    cell, w, h, gap = cell * k, w * k, h * k, gap * k
    L = Layers(h, w, 3)
    ident, edge = voronoi(h, w, cell, rng, jitter=0.85)
    inside = edge > gap / 2
    _units(L, inside, (edge - gap / 2) / k, ident, rng, tones=(-1, -1, 0, 0, 1), dome=dome, gap_shade=gap_shade)
    L.shade[inside & (rng.random((h, w)) < pits)] -= 1
    # worn tops: the middle of each cobble is polished a step lighter
    L.shade[inside & (edge > 4.5 * k)] += 1
    if k > 1:
        # what the extra texels can carry: pits, and a darker lower lip
        L.shade[inside & (rng.random((h, w)) < pits * 1.25)] -= 1
        L.shade[inside & (edge < 1.2 * k) & np.roll(~inside, -2, 0)] -= 1
    return L


def s_fieldstone(rng, cell=22, w=528, h=528, gap=2.2, dome=0.0, gap_shade=1):
    L = Layers(h, w, 3)
    ident, edge = voronoi(h, w, cell, rng, jitter=0.95, sx=1.5)
    inside = edge > gap / 2
    _units(L, inside, edge - gap / 2, ident, rng, tones=(-2, -1, 0, 0, 1), dome=dome, gap_shade=gap_shade)
    L.shade[inside & clumps(h, w, 8, rng, 0.25)] -= 1
    L.shade[inside & (rng.random((h, w)) < 0.05)] += 1
    return L


def s_sandstone(rng, bw=40, bh=16, w=520, h=512):
    L = s_brick(rng, bw=bw, bh=bh, w=w, h=h, mortar=1)
    # strata: horizontal bands through each block
    yy = np.mgrid[0:h, 0:w][0]
    band = (np.sin(yy * 2 * np.pi / 8 + value_noise(h, w, 8, rng) * 4) > 0.55) & (L.ramp == 0)
    L.shade[band] -= 1
    return L


def s_plaster(rng, w=512, h=504):
    L = Layers(h, w, 3)
    # trowel strokes: horizontal-stretched noise, three tones
    strokes = value_noise(h, w, 8, rng, 2, cellx=64)
    blot = value_noise(h, w, 56, rng, 3, cellx=64)
    L.shade = L.shade + np.digitize(strokes * 0.6 + blot * 0.4, [0.36, 0.5, 0.64]) - 2
    L.shade[clumps(h, w, 8, rng, 0.08)] -= 1
    L.shade[rng.random((h, w)) < 0.05] += 1
    L.shade[rng.random((h, w)) < 0.03] -= 1
    c = cracks(h, w, rng, 28, 40)
    L.shade[c] = 0
    L.height = 0.8 - c * 0.5 + (strokes - 0.5) * 0.25
    # where the plaster has fallen away, brick shows through
    hole = clumps(h, w, 8, rng, 0.06)
    b = s_brick(rng, w=w, h=h, bw=16, bh=6)
    L.ramp[hole] = np.where(b.ramp[hole] == 0, 2, 1)
    L.shade[hole] = np.clip(b.shade[hole], 0, 4)
    L.height[hole] = b.height[hole] * 0.5
    # the plaster's broken edge: a lit rim just below each hole's top
    rim = np.roll(hole, 1, 0) & ~hole
    L.shade[rim] += 1
    return L


def s_planks(rng, pw=12, w=504, h=512, vertical=True):
    L = Layers(h, w, 3)
    yy, xx = np.mgrid[0:h, 0:w]
    a, b = (xx, yy) if vertical else (yy, xx)
    board = a // pw
    la = a % pw
    # butt joints: each board is cut into lengths at its own offsets
    cut_len = 128
    assert w % pw == 0 and h % cut_len == 0, (w, h, pw, cut_len)
    shift = per_unit(board, rng, np.arange(cut_len), None)
    seg = ((b + shift) // cut_len) % ((h if vertical else w) // cut_len)
    lb = (b + shift) % cut_len
    ident = board * 64 + seg
    inside = (la >= 1) & (lb >= 1)
    dist = np.minimum(np.minimum(la - 0.5, pw - la - 0.5), np.minimum(lb - 0.5, cut_len - lb - 0.5)).astype(float)
    _units(L, inside, dist, ident, rng, tones=(-1, 0, 0, 1))
    # grain: noise stretched hard along the board
    grain = value_noise(h, w, 8, rng, 2)
    # 1.7 rad/texel rounded to a whole number of periods across the tile
    k = round(1.7 * (w if vertical else h) / (2 * np.pi))
    streak = (np.abs(np.sin(a * 2 * np.pi * k / (w if vertical else h) + grain * 9)) < 0.22) & inside
    L.shade[streak] -= 1
    # knots and nails
    knot = inside & (per_unit(ident, rng, np.array([0, 1]), [0.7, 0.3]) == 1) & (np.abs(lb - 30) < 2) & (np.abs(la - pw // 2) < 2)
    L.shade[knot] = 0
    nail = inside & ((lb == 3) | (lb == cut_len - 4)) & (la == pw // 2)
    L.ramp[nail] = 2
    L.shade[nail] = 1
    L.height = np.where(inside, L.height - streak * 0.15, 0.0)
    return L


def s_timber(rng, w=128, h=512):
    """A beam face: grain along its length (v), for beams UV'd lengthwise."""
    L = Layers(h, w, 3)
    grain = value_noise(h, w, 64, rng, 2, cellx=2)
    L.shade = L.shade + np.digitize(grain, [0.3, 0.45, 0.62, 0.78]) - 2
    L.shade[clumps(h, w, 16, rng, 0.10)] -= 1
    c = cracks(h, w, rng, 10, 80)
    L.shade[c] = 0
    # checks: short dark splits along the grain
    split = value_noise(h, w, 32, rng, 1, cellx=1) > 0.86
    L.shade[split] = 1
    L.height = 0.5 + (grain - 0.5) * 0.6 - c * 0.4 - split * 0.3
    return L


def s_shingle(rng, sw=16, sh=7, w=512, h=504, round_=False):
    """Overlapping rows seen from outside: each row shows its lower part, the
    row above throws a shadow across its top, the bottom edge catches light,
    and a dark slot runs between neighbours. No horizontal mortar line --
    that is what made the first pass read as brick."""
    assert w % sw == 0 and h % sh == 0 and (h // sh) % 2 == 0, (w, h, sw, sh)
    L = Layers(h, w, 3)
    yy, xx = np.mgrid[0:h, 0:w]
    row = yy // sh
    off = (row % 2) * (sw // 2)
    col = ((xx + off) // sw) % (w // sw)
    ly, lx = yy % sh, (xx + off) % sw
    ident = row * (w // sw) + col
    inside = lx >= 1
    if round_:
        # rounded tips: the bottom corners belong to the row beneath
        cx = np.abs(lx - (sw - 1) / 2) / ((sw - 1) / 2)
        cut = (ly >= sh - 3) & (cx > np.sqrt(np.clip(1 - ((ly - (sh - 3)) / 3.0) ** 2, 0, 1)) * 0.95)
        inside &= ~cut
    tone = per_unit(ident, rng, np.array([-1, -1, 0, 0, 1]), None)
    L.shade = L.shade + np.where(inside, tone, 0)
    L.shade[inside & (ly == 0)] -= 2
    L.shade[inside & (ly == 1)] -= 1
    L.shade[inside & (ly == sh - 1)] += 1
    L.shade[inside & (lx == 1)] += 1
    L.shade[inside & (lx == sw - 1)] -= 1
    # weathering: a few missing or lifted tiles show the dark underlay
    gone = per_unit(ident, rng, np.array([0, 1]), [0.99, 0.01]) == 1
    L.ramp = np.where(inside, 0, 1).astype(np.int8)
    # slots between tiles are the underlay in shadow; a lost tile shows it lit
    L.shade = np.where(inside, L.shade, 0)
    L.ramp[gone] = 1
    L.shade[gone] = 2 + (ly[gone] > 1)
    inside &= ~gone
    L.shade[inside & (rng.random((h, w)) < 0.05)] -= 1
    L.height = np.where(inside, 0.25 + 0.75 * ly / (sh - 1), 0.0)
    return L


def s_thatch(rng, w=512, h=510, row=10, strand_w=1):
    """Bundled straw in overlapping courses. Strands are vertical and wavy;
    each course ends in ragged bundle tips with shadow under them."""
    assert h % row == 0, (h, row)
    L = Layers(h, w, 3)
    yy, xx = np.mgrid[0:h, 0:w]
    # strand_w texels per straw: wider straws are calmer (the calm set)
    strand = np.repeat(np.repeat(rng.random((1, w // strand_w)), strand_w, 1), h, 0)
    wav = value_noise(h, w, 10, rng, 2, cellx=4)
    L.shade = L.shade + np.digitize(strand * 0.7 + wav * 0.3, [0.3, 0.5, 0.72]) - 2
    ly = yy % row
    course = yy // row
    # bundles 4 texels wide, each with its own tip length
    bundle = ((xx + per_unit(course, rng, np.arange(4), None)) // 4) % (w // 4)
    tip = per_unit(course * (w // 4) + bundle, rng, np.array([0, 1, 2, 3]), None)
    below = ly >= row - tip
    L.ramp[below] = 1
    L.shade[below] = 1
    L.shade[(ly == row - tip - 1) & ~below] += 1          # sunlit ends
    L.shade[ly == 0] -= 1
    L.height = np.where(below, 0.1, 0.35 + 0.65 * ly / row)
    return L


def s_grass(rng, w=512, h=512, k=1, blades=0.16):
    w, h = w * k, h * k
    L = Layers(h, w, 2)
    n = value_noise(h, w, 64 * k, rng, 3)
    L.shade = L.shade + np.digitize(n, [0.4, 0.62]) - 1
    # dense tufts: blades 2-4 base texels tall (k x as many texels), one texel
    # wide -- so a denser tile gets finer blades, not fatter ones -- dark root,
    # lit tip, the tip leaning
    n_blades = int(w * h * blades / k)
    ys, xs = rng.integers(0, h, n_blades), rng.integers(0, w, n_blades)
    tall = rng.integers(2, 5, n_blades) * k
    lean = rng.choice([-1, 0, 1], n_blades)
    for t in range(4 * k):
        m = t < tall
        yy = (ys[m] - t) % h
        xx2 = (xs[m] + lean[m] * (t >= tall[m] - k)) % w
        L.shade[yy, xx2] = np.where(t < k, 1, np.where(t >= tall[m] - k, 5, 3 + ((t // k) % 2)))
    # bare patches: small and few -- at 32-texel blobs and 5% they read as the
    # same red spots every 9.8 m in the game frame (seen 2026-09-23)
    dirt = clumps(h, w, 16 * k, rng, 0.03)
    L.ramp[dirt] = 1
    L.shade[dirt] = 2 + (rng.random(dirt.sum()) < 0.3) - (rng.random(dirt.sum()) < 0.2)
    L.height = 0.5 + (L.shade - 3) * 0.1
    return L


def s_dirt(rng, w=512, h=512, k=1, speck=(0.18, 0.10, 0.06), pebbles=0.38, crack_n=20):
    w, h = w * k, h * k
    L = Layers(h, w, 3)
    n = value_noise(h, w, 32 * k, rng, 3)
    L.shade = L.shade + np.digitize(n, [0.3, 0.6]) - 1
    L.shade[clumps(h, w, 4 * k, rng, speck[0])] -= 1
    L.shade[rng.random((h, w)) < speck[1]] -= 1
    L.shade[rng.random((h, w)) < speck[2]] += 1
    # pebbles: tiny stones with a lit rim and a shadow under them
    ident, edge = voronoi(h, w, 8 * k, rng, jitter=1.0)
    peb = (edge > 1.6 * k) & (per_unit(ident, rng, np.array([0, 1]), [1 - pebbles, pebbles]) == 1)
    L.ramp[peb] = 2
    L.shade[peb] = 3 + bevel(peb, edge - 1.6 * k)[peb]
    shadow = np.roll(peb, -k, 0) & ~peb
    L.shade[shadow] = 0
    c = cracks(h, w, rng, crack_n * k, 24 * k)
    L.shade[c & ~peb] = 0
    L.height = 0.45 + (n - 0.5) * 0.3 + peb * 0.35 - c * 0.2
    return L


def s_sand(rng, w=512, h=512):
    L = Layers(h, w, 3)
    yy = np.mgrid[0:h, 0:w][0]
    warp = value_noise(h, w, 64, rng, 2)
    ph = yy * (2 * np.pi / 16) + warp * 9
    rip = np.sin(ph)
    L.shade = L.shade + np.digitize(rip, [-0.5, 0.5]) - 1
    # a lit crest and a thin shadow on each ripple's lee
    L.shade[np.cos(ph) > 0.93] += 2
    L.shade[np.cos(ph) < -0.93] -= 2
    grain = rng.random((h, w))
    L.shade[grain < 0.10] += 1
    L.shade[grain > 0.92] -= 1
    L.height = 0.5 + rip * 0.25
    return L


def s_sand_hd(rng, k=2):
    """Wind-rippled sand at the HD density: ripples every 0.3 m, wandering,
    a lit crest and a lee shadow, a scatter of darker grains and pebbles."""
    w = h = 512 * k
    L = Layers(h, w, 3)
    yy = np.mgrid[0:h, 0:w][0]
    warp = value_noise(h, w, 64 * k, rng, 2)
    ph = yy * (2 * np.pi / (16 * k)) + warp * 9
    rip = np.sin(ph)
    L.shade = L.shade + np.digitize(rip, [-0.6, 0.6]) - 1
    L.shade[np.cos(ph) > 0.95] += 1
    L.shade[np.cos(ph) < -0.95] -= 1
    grain = rng.random((h, w))
    L.shade[grain < 0.06] += 1
    L.shade[grain > 0.95] -= 1
    peb = clumps(h, w, 4 * k, rng, 0.006)
    L.ramp[peb] = 1
    L.shade[peb] = 2
    L.height = 0.5 + rip * 0.2
    return L


def s_cracked(rng, k=2):
    """Sun-cracked earth: plates of dried mud, each its own tone, dark cracks
    between, the plate edges curled up and catching the light."""
    w = h = 512 * k
    L = Layers(h, w, 3)
    ident, edge = voronoi(h, w, 32 * k, rng, jitter=0.9)
    inside = edge > 1.2 * k
    _units(L, inside, edge - 1.2 * k, ident, rng, tones=(-1, 0, 0, 1))
    L.shade[inside & clumps(h, w, 16 * k, rng, 0.2)] -= 1
    dust = clumps(h, w, 8 * k, rng, 0.08)
    L.ramp[dust & inside] = 2
    L.shade[dust & inside] = 3
    return L


def s_dune_rock(rng, k=2):
    """Desert rock face: horizontal strata bands of different hardness, the
    soft ones eroded darker, pits and a few cracks."""
    w = h = 512 * k
    L = Layers(h, w, 3)
    yy = np.mgrid[0:h, 0:w][0]
    warp = value_noise(h, w, 128 * k, rng, 2) * 20 * k
    band = ((yy + warp) // (18 * k)).astype(int)
    tone = rng.integers(-1, 2, band.max() + 2)
    L.shade = L.shade + tone[band]
    soft = (((yy + warp) % (18 * k)) < 3 * k)
    L.shade[soft] -= 2
    pits = clumps(h, w, 4 * k, rng, 0.03)
    L.shade[pits] -= 1
    L.shade[rng.random((h, w)) < 0.04] += 1
    L.height = 0.6 - soft * 0.3
    return L


def s_snow(rng, w=512, h=512):
    L = Layers(h, w, 4)
    n = value_noise(h, w, 64, rng, 4)
    yy = np.mgrid[0:h, 0:w][0]
    ph = yy * (2 * np.pi / 32) + value_noise(h, w, 64, rng, 2) * 10
    drift = np.sin(ph)
    L.shade = L.shade + np.digitize(n * 0.5 + (drift * 0.5 + 0.5) * 0.5, [0.3, 0.45, 0.62]) - 2
    L.shade[np.cos(ph) < -0.9] -= 2               # wind-drift shadow lines
    blue = clumps(h, w, 8, rng, 0.10)
    L.ramp[blue] = 1
    L.shade[blue] = 3 + (rng.random(blue.sum()) < 0.4)
    L.shade[rng.random((h, w)) < 0.025] = 6        # sparkle
    L.shade[rng.random((h, w)) < 0.02] -= 1
    L.height = 0.4 + n * 0.3 + drift * 0.15
    return L


def s_snow_soft(rng, w=512, h=512, k=1):
    """Fresh lying snow, as the snow-region reference paints it: soft lumps
    lit from the upper left (a bright rim, a cool blue shadow side), a few
    faint wind ripples, sparkle, and the odd pebble or dry grass tip poking
    through. No stripes: the old `snow` tile's drift bands read as a
    ploughed field at 8 deg."""
    w, h = w * k, h * k
    L = Layers(h, w, 3)
    lump = value_noise(h, w, 128 * k, rng, 3) * 0.75 + value_noise(h, w, 32 * k, rng, 2) * 0.25
    # mostly one bright tone; only the steeper lump sides step down (the
    # normal map does the rest of the relief in the game's light)
    sl = (lump - np.roll(np.roll(lump, 2 * k, 0), 2 * k, 1)) * 18
    L.shade = L.shade + 1 + np.digitize(sl, [-0.3, 0.3]) - 1
    rip = np.sin(np.mgrid[0:h, 0:w][0] * (2 * np.pi / (24 * k)) + value_noise(h, w, 128 * k, rng, 2) * 14)
    L.shade[(rip > 0.97) & (value_noise(h, w, 64 * k, rng, 1) > 0.6)] -= 1
    L.shade[rng.random((h, w)) < 0.012 / k] = 6          # sparkle
    stones = clumps(h, w, 4 * k, rng, 0.004)
    L.ramp[stones] = 1
    L.shade[stones] = 1 + (rng.random(stones.sum()) < 0.4)
    n_tip = int(w * h * 0.0015 / k)
    ys, xs = rng.integers(0, h, n_tip), rng.integers(0, w, n_tip)
    for t in range(3 * k):
        L.ramp[(ys - t) % h, xs] = 2
        L.shade[(ys - t) % h, xs] = 1 + (t >= 2 * k)
    L.height = 0.35 + lump * 0.5
    return L


def s_snow_packed(rng, w=512, h=512, k=1):
    """Trodden snow on the old trails: packed grey-blue, boot prints pressed in
    (dark floor, bright rim), grit and slush worked into it."""
    w, h = w * k, h * k
    L = Layers(h, w, 3)
    n = value_noise(h, w, 32 * k, rng, 3)
    L.shade = L.shade + np.digitize(n, [0.35, 0.65]) - 1
    yy, xx = np.mgrid[0:h, 0:w]
    height = 0.55 + n * 0.2
    for _ in range(int(90 * k * k)):
        cy, cx = rng.integers(0, h), rng.integers(0, w)
        a = rng.random() * np.pi
        dy = (yy - cy + h // 2) % h - h // 2
        dx = (xx - cx + w // 2) % w - w // 2
        u = (dx * np.cos(a) + dy * np.sin(a)) / (7 * k)
        v = (-dx * np.sin(a) + dy * np.cos(a)) / (3.5 * k)
        d = u * u + v * v
        L.shade[d < 1.0] -= 1
        L.shade[(d >= 1.0) & (d < 1.6)] += 1
        height = np.where(d < 1.0, height - 0.25, height)
    grit = clumps(h, w, 4 * k, rng, 0.012)
    L.ramp[grit] = 1
    L.shade[grit] = 2 + (rng.random(grit.sum()) < 0.3)
    L.shade[rng.random((h, w)) < 0.02] += 1
    L.height = np.clip(height, 0, 1)
    return L


def s_snowstone(rng, k=2):
    """The sheet's rocky-snow tile: mid blue-grey fieldstone, snow packed in
    the gaps and lying on each stone's upper edge."""
    w = h = 528 * k
    L = Layers(h, w, 3)
    ident, edge = voronoi(h, w, 22 * k, rng, jitter=0.95, sx=1.5)
    inside = edge > 2.2 * k / 2
    _units(L, inside, edge - 2.2 * k / 2, ident, rng, tones=(-2, -1, 0, 0, 1))
    L.shade[inside & clumps(h, w, 16 * k, rng, 0.25)] -= 1
    top = inside & ~np.roll(inside, 3 * k, 0)
    snow = (~inside & clumps(h, w, 16 * k, rng, 0.55)) | (top & clumps(h, w, 8 * k, rng, 0.6))
    L.ramp[snow] = 2
    L.shade[snow] = 4 + (rng.random(snow.sum()) < 0.3) - (rng.random(snow.sum()) < 0.2)
    L.height = np.where(snow, np.maximum(L.height, 0.55), L.height)
    return L


def s_ice_hd(rng, k=2):
    """Frozen puddle ice at the HD density: blue, white-cracked, frost streaks."""
    w = h = 512 * k
    L = Layers(h, w, 3)
    n = value_noise(h, w, 64 * k, rng, 3)
    L.shade = L.shade + np.digitize(n, [0.4, 0.7]) - 1
    ident, edge = voronoi(h, w, 32 * k, rng)
    crack = edge < 0.7 * k
    L.shade[crack] = 5
    streak = np.abs(np.sin(np.mgrid[0:h, 0:w][1] * 2 * np.pi * 16 / w + n * 6)) < 0.08
    L.shade[streak] += 1
    frost = clumps(h, w, 16 * k, rng, 0.08)
    L.ramp[frost] = 2
    L.shade[frost] = 5
    L.height = 0.8 - crack * 0.4
    return L


def s_ice(rng, w=512, h=512):
    L = Layers(h, w, 3)
    n = value_noise(h, w, 64, rng, 3)
    L.shade = L.shade + np.digitize(n, [0.4, 0.7]) - 1
    ident, edge = voronoi(h, w, 40, rng)
    crack = edge < 0.7
    L.shade[crack] = 5
    streak = np.abs(np.sin(np.mgrid[0:h, 0:w][1] * 2 * np.pi * 16 / w + n * 6)) < 0.08
    L.shade[streak] += 1
    L.height = 0.8 - crack * 0.4
    return L


def s_mud(rng, w=512, h=512):
    """Rainforest floor: dark wet soil, leaves, roots."""
    L = Layers(h, w, 2)
    n = value_noise(h, w, 32, rng, 3)
    L.shade = L.shade + np.digitize(n, [0.4, 0.7]) - 1
    # roots: dark wandering lines, then a dense leaf fall on top
    roots = cracks(h, w, rng, 40, 60)
    L.shade[roots] = 0
    L.shade[rng.random((h, w)) < 0.08] += 1
    wet = clumps(h, w, 16, rng, 0.08)
    L.shade[wet] = 4
    L = _leaves(L, rng, density=0.32, ramps=(1, 2))
    return L


def s_leaf_litter(rng, w=512, h=512):
    """Emberwood floor: autumn leaves over dark soil."""
    L = Layers(h, w, 2)
    n = value_noise(h, w, 32, rng, 2)
    L.shade = L.shade + np.digitize(n, [0.5]) - 1
    return _leaves(L, rng, density=0.35, ramps=(1, 2))


def _leaves(L, rng, density, ramps):
    h, w = L.shade.shape
    leaf = np.array([[0, 1, 1, 0], [1, 1, 1, 1], [1, 1, 1, 1], [0, 1, 1, 0], [0, 0, 1, 0]], bool)
    k = int(w * h * density / leaf.sum())
    for _ in range(k):
        y, x = rng.integers(0, h), rng.integers(0, w)
        r = int(rng.choice(ramps))
        tone = int(rng.integers(2, 5))
        lf = np.rot90(leaf, rng.integers(0, 4))
        ys = (y + np.nonzero(lf)[0]) % h
        xs = (x + np.nonzero(lf)[1]) % w
        L.ramp[ys, xs] = r
        L.shade[ys, xs] = tone
        L.shade[ys[:1], xs[:1]] = tone + 1
        L.height[ys, xs] = 0.8
    return L


def s_moss(rng, w=512, h=512):
    L = Layers(h, w, 3)
    n = value_noise(h, w, 16, rng, 3)
    L.shade = L.shade + np.digitize(n, [0.3, 0.5, 0.7]) - 2
    fuzz = rng.random((h, w))
    L.shade[fuzz < 0.14] += 1
    L.shade[fuzz > 0.88] -= 1
    L.shade[(fuzz > 0.5) & (fuzz < 0.53)] += 2
    L.height = 0.4 + n * 0.5
    return L


def s_slate(rng):
    return s_shingle(rng, sw=16, sh=8, w=512, h=512)


def s_fishscale(rng):
    return s_shingle(rng, sw=16, sh=8, w=512, h=512, round_=True)


def s_adobe(rng, w=512, h=504):
    L = s_plaster(rng, w, h)
    # faint mud-brick courses under the render
    yy = np.mgrid[0:h, 0:w][0]
    L.shade[(yy % 14 == 0) & (L.ramp == 0) & (value_noise(h, w, 56, rng, cellx=64) > 0.4)] -= 1
    straw = rng.random((h, w)) < 0.03
    L.ramp[straw] = 2
    L.shade[straw] = 4
    return L


def s_bark(rng, w=256, h=512):
    L = Layers(h, w, 3)
    ridge = value_noise(h, w, 16, rng, 2)
    xx = np.mgrid[0:h, 0:w][1]
    fur = np.abs(np.sin(xx * (2 * np.pi / 8) + ridge * 7))
    L.shade = L.shade + np.digitize(fur, [0.3, 0.8]) - 1
    L.shade[fur < 0.15] = 0
    L.height = fur
    return L


# --- Emberglass city ---------------------------------------------------------

def s_clay_tile(rng, sw=12, sh=8, w=504, h=512):
    """Barrel clay tiles: shingle rows, each tile shaded as a half-cylinder
    (lit left flank, dark right one) so the roof reads as ridged pantiles."""
    L = s_shingle(rng, sw=sw, sh=sh, w=w, h=h)
    yy, xx = np.mgrid[0:h, 0:w]
    lx = (xx + ((yy // sh) % 2) * (sw // 2)) % sw
    tile = L.ramp == 0
    L.shade[tile & ((lx == 2) | (lx == 3))] += 1
    L.shade[tile & (lx >= sw - 3)] -= 1
    L.height = np.where(tile, L.height * (0.6 + 0.4 * np.sin(np.pi * lx / sw)), L.height)
    return L


def s_ashlar(rng, mortar=1, dome=0.0, gap_shade=1, bw=26, bh=12):
    """Dressed wall stone: big squared blocks, thin joints, weathered patches."""
    L = s_brick(rng, bw=bw, bh=bh, w=520, h=504, mortar=mortar, dome=dome, gap_shade=gap_shade)
    stone = L.ramp == 0
    L.shade[stone & clumps(504, 520, 8, rng, 0.2)] -= 1
    L.shade[stone & (rng.random((504, 520)) < 0.05)] += 1
    L.shade[stone & cracks(504, 520, rng, 14, 18)] -= 1
    return L


def s_flagstone(rng, w=510, h=520, crack_n=18, pits=0.04, gap=0.8, dome=0.0, gap_shade=1):
    """Paving flags: large near-rectangular slabs, worn light in the middle."""
    L = Layers(h, w, 3)
    ident, edge = voronoi(h, w, 26, rng, jitter=0.55, sx=1.3)
    inside = edge > gap
    _units(L, inside, edge - gap, ident, rng, tones=(-1, -1, 0, 0, 1), dome=dome, gap_shade=gap_shade)
    L.shade[inside & (edge > 7)] += 1
    L.shade[inside & cracks(h, w, rng, crack_n, 22)] -= 2
    L.shade[inside & (rng.random((h, w)) < pits)] -= 1
    return L


def s_cloth(rng, w=520, h=512, stripe=26):
    """Woven canvas: fine weave, sagging folds; `stripe` > 0 alternates ramp 0
    and ramp 2 in vertical bands (the awning stripes)."""
    L = Layers(h, w, 3)
    yy, xx = np.mgrid[0:h, 0:w]
    folds = value_noise(h, w, 64, rng, 2, cellx=8)
    L.shade = L.shade + np.digitize(folds, [0.35, 0.5, 0.65]) - 2
    L.shade[(yy + xx) % 2 == 0] -= (rng.random((h, w)) < 0.25)[(yy + xx) % 2 == 0]
    if stripe:
        band = (xx // stripe) % 2 == 1
        L.ramp[band] = 2
        L.shade[(xx % stripe) == 0] -= 1
    L.height = 0.5 + (folds - 0.5) * 0.5
    return L


def s_stained_glass(rng, w=260, h=260):
    """Leaded glass: small cells of red, blue and gold between black leads."""
    L = Layers(h, w, 2)
    ident, edge = voronoi(h, w, 10, rng, jitter=0.9)
    lead = edge < 0.9
    colour = per_unit(ident, rng, np.array([0, 2, 3, 2]), None)
    L.ramp = np.where(lead, 1, colour).astype(np.int8)
    L.shade = np.where(lead, 1, 2 + (edge > 3) - (rng.random((h, w)) < 0.1))
    L.height = np.where(lead, 1.0, 0.4)
    return L


def s_crops(rng, w=512, h=512, row=16):
    """Field rows: planted ridges of grain between dark furrows."""
    L = Layers(h, w, 3)
    yy, xx = np.mgrid[0:h, 0:w]
    lx = xx % row
    furrow = (lx < 4) | (lx >= row - 2)
    blades = value_noise(h, w, 4, rng, 2, cellx=2)
    L.shade = L.shade + np.digitize(blades, [0.35, 0.55, 0.72]) - 2
    green = clumps(h, w, 32, rng, 0.25) & ~furrow
    L.ramp[green] = 2
    L.shade[~furrow & (lx == 4)] -= 1
    L.shade[~furrow & (lx == row - 3)] += 1
    L.ramp[furrow] = 1
    L.shade[furrow] = 1 + (rng.random((h, w)) < 0.3)[furrow]
    L.height = np.where(furrow, 0.1, 0.5 + blades * 0.5)
    return L


# Surfaces drawn at a multiple of 52 texels/m. The ground is seen at a grazing
# 8 deg and its foreground sits ~2x closer than the player, where a 52/m texel
# spans ~3 screen pixels (user, 2026-09-23: "the road looks low resolution").
# At 2x it spans 1-1.5. Everything else stays at the sprite's density.
DENSITY = {"cobble_hd": 2, "dirt_hd": 2, "grass_hd": 2, "snow_hd": 2, "snow_packed_hd": 2, "snowstone_hd": 2, "ice_hd": 2,
           "sand_hd": 2, "cracked_hd": 2, "dune_rock_hd": 2}

# name -> (recipe, ramps as (base hex, steps), roughness per ramp)
SURFACES = {
    # village / Greenwood
    "brick":       (lambda r: s_brick(r, bw=20, bh=8, w=520, h=512, dome=3.0, gap_shade=0),
                    [("#8a5a44", 7, 5), ("#3e3129", 5, 6), ("#6b6358", 5, 4)], [0.85, 0.98, 0.9]),
    # deep stones (STRUCT, 2026-09-27 "the ground is too flat"): 0.38 m domed
    # cobbles in a dark 5 cm gap; the faces stay calm
    "cobble":      (lambda r: s_cobble(r, cell=20, gap=2.6, pits=0.0, dome=6.0, gap_shade=0),
                    [("#89735f", 7, 6), ("#57483f", 5, 7), ("#6b6358", 5, 5)], [0.8, 0.98, 0.9]),
    "fieldstone":  (lambda r: s_fieldstone(r, gap=3.0, dome=6.0, gap_shade=0),
                    [("#947d69", 7, 6), ("#483b33", 5, 6), ("#5f6e3a", 5, 7)], [0.85, 0.98, 0.9]),
    "plaster":     (s_plaster,    [("#cfc3a8", 7, 7), ("#8f8574", 5, 7), ("#77706a", 5, 7)], [0.9, 0.9, 0.85]),
    "planks":      (s_planks,     [("#7a5a3c", 7, 5), ("#5a432e", 5, 5), ("#4a4a4e", 5, 5)], [0.8, 0.9, 0.5]),
    "timber":      (s_timber,     [("#5b3f2a", 7, 5), ("#2b2019", 5, 5), ("#2b2019", 5, 5)], [0.8, 0.9, 0.9]),
    "shingle":     (s_shingle,    [("#6e4a36", 7, 3), ("#3d2b21", 5, 3), ("#4a4038", 5, 3)], [0.85, 0.95, 0.9]),
    "slate":       (s_slate,      [("#625247", 7, 4), ("#493d37", 5, 4), ("#483d36", 5, 4)], [0.6, 0.95, 0.9]),
    # blue-grey slate at slate's L* (2026-09-30, the user's asset sheet: blue roofs among the red)
    "slate_blue":  (s_slate,      [("#4f5a6b", 7, 4), ("#3a4250", 5, 4), ("#39414e", 5, 4)], [0.6, 0.95, 0.9]),
    "fishscale":   (s_fishscale,  [("#4f6a6e", 7), ("#1a2324", 5), ("#3a4a4e", 5)], [0.6, 0.95, 0.9]),
    "thatch":      (lambda r: s_thatch(r, strand_w=4),     [("#a88a52", 7, 4), ("#7d673f", 5, 4), ("#3d3222", 5, 4)], [0.95, 0.95, 0.95]),
    "grass":       (s_grass,      [("#5c7a34", 7), ("#5a5236", 7), ("#5a5236", 5)], [0.95, 0.95, 0.95]),
    "dirt":        (lambda r: s_dirt(r, speck=(0.10, 0.05, 0.03), pebbles=0.25, crack_n=10),
                    [("#7a6046", 7, 6), ("#3a2c20", 5, 6), ("#8a8378", 5, 6)], [0.95, 0.95, 0.85]),
    "moss":        (s_moss,       [("#4f6b2e", 7, 4), ("#2f3f1c", 5, 4), ("#2f3f1c", 5, 4)], [0.9, 0.9, 0.9]),
    # Emberwood / Crags / Fen
    "leaf_litter": (s_leaf_litter, [("#3a2c20", 7), ("#b0602a", 7), ("#8a3a22", 7)], [0.95, 0.9, 0.9]),
    "bark":        (s_bark,       [("#5a4636", 7, 3), ("#2b2019", 5, 3), ("#2b2019", 5, 3)], [0.95, 0.95, 0.95]),
    "cobble_hd":   (lambda r: s_cobble(r, cell=20, gap=2.6, pits=0.0, k=2, dome=6.0, gap_shade=0),
                    [("#89735f", 7, 6), ("#57483f", 5, 7), ("#6b6358", 5, 5)], [0.8, 0.98, 0.9]),
    "dirt_hd":     (lambda r: s_dirt(r, k=2, speck=(0.06, 0.03, 0.02), pebbles=0.25, crack_n=10),
                    [("#7a6046", 7, 6), ("#3a2c20", 5, 6), ("#8a8378", 5, 6)], [0.95, 0.95, 0.85]),
    "grass_hd":    (lambda r: s_grass(r, k=2, blades=0.03),
                    [("#5c7a34", 7, 5), ("#5a5236", 7, 5), ("#5a5236", 5, 5)], [0.95, 0.95, 0.95]),
    # desert
    "sand_hd":     (lambda r: s_sand_hd(r, k=2),   [("#d2ad72", 7), ("#8a6a44", 5), ("#8a6a44", 5)], [0.95, 0.95, 0.95]),
    "cracked_hd":  (lambda r: s_cracked(r, k=2),   [("#b0885a", 7), ("#4a3424", 5), ("#c8a878", 5)], [0.95, 0.95, 0.95]),
    "dune_rock_hd": (lambda r: s_dune_rock(r, k=2), [("#b27a4c", 7), ("#5a3a26", 5), ("#5a3a26", 5)], [0.9, 0.95, 0.95]),
    "sand":        (s_sand,       [("#c9a46a", 7), ("#8a6a44", 5), ("#8a6a44", 5)], [0.95, 0.95, 0.95]),
    "sandstone":   (s_sandstone,  [("#c08a58", 7), ("#6a4a30", 5), ("#6a4a30", 5)], [0.9, 0.95, 0.9]),
    "adobe":       (s_adobe,      [("#b8875a", 7), ("#7a5638", 5), ("#d8c07a", 7)], [0.95, 0.95, 0.9]),
    # snow
    "snow":        (s_snow,       [("#dfe6ee", 7), ("#9eb4d2", 7), ("#9eb4d2", 5)], [0.6, 0.6, 0.6]),
    "snow_hd":     (lambda r: s_snow_soft(r, k=2),   [("#dde5ef", 7), ("#5f6168", 5), ("#8a7a58", 5)], [0.75, 0.9, 0.95]),
    "snow_packed_hd": (lambda r: s_snow_packed(r, k=2), [("#aab5c6", 7), ("#5a5048", 5), ("#8d99ab", 5)], [0.6, 0.9, 0.8]),
    "snowstone_hd": (lambda r: s_snowstone(r, k=2), [("#666b7c", 7), ("#23252c", 5), ("#dde5ef", 7)], [0.9, 0.95, 0.75]),
    "ice_hd":      (lambda r: s_ice_hd(r, k=2), [("#8fb6cc", 7), ("#2a4a60", 5), ("#e4eef6", 7)], [0.15, 0.4, 0.6]),
    "ice":         (s_ice,        [("#8fb6cc", 7), ("#2a4a60", 5), ("#2a4a60", 5)], [0.15, 0.4, 0.4]),
    # Emberglass city
    "clay_tile":   (s_clay_tile,  [("#a4533a", 7, 3), ("#733c2b", 5, 3), ("#5a4a3e", 5, 3)], [0.8, 0.95, 0.9]),
    "ashlar":      (lambda r: s_ashlar(r, mortar=2, dome=4.0, gap_shade=0),
                    [("#a0876e", 7, 4), ("#4e3f37", 5, 6), ("#5f6e3a", 5, 3)], [0.85, 0.98, 0.9]),
    # city walls, quays, retaining walls and towers (2026-09-30, "city life" plan, item 6): the
    # sheet's big blocks, ~1.0 x 0.40 m at 52 texels/m; `ashlar` is 0.50 x 0.23 (brick scale)
    # greyer than the houses' honey (the sheet's walls and towers are grey stone; both outside
    # reviews asked for grey stone against the warm fronts): the fortifications only
    "ashlar_big":  (lambda r: s_ashlar(r, mortar=2, dome=5.0, gap_shade=0, bw=52, bh=21),
                    [("#958a7e", 7, 4), ("#48403c", 5, 6), ("#5f6e3a", 5, 3)], [0.85, 0.98, 0.9]),
    "flagstone":   (lambda r: s_flagstone(r, crack_n=8, pits=0.02, gap=1.3, dome=8.0, gap_shade=0),
                    [("#97836c", 7, 6), ("#594b42", 5, 7), ("#5f6e3a", 5, 6)], [0.8, 0.98, 0.9]),
    # the plaza's rings (CitySite): brick pavers on a light mortar, calm; they read
    # by hue against the grey flags. Walls keep `brick`.
    "paving_brick": (lambda r: s_brick(r, bw=20, bh=8, w=520, h=512, dome=3.0, gap_shade=0),
                    [("#8a5a44", 7, 5), ("#4e3c33", 5, 7), ("#6b6358", 5, 5)], [0.85, 0.98, 0.9]),
    # the city's streets (2026-09-29, VISUAL_PRODUCTION_GUIDE): 0.30 x 0.15 m setts in
    # running bond, the courses along the road (CitySite gives the road UVs along its
    # axis). The cobble's stone, so only the pattern changes against the Voronoi cobbles
    "setts":       (lambda r: s_brick(r, bw=16, bh=8, w=512, h=512, mortar=2, dome=3.0, gap_shade=0),
                    [("#7d776c", 7, 6), ("#524c44", 5, 7), ("#6b6358", 5, 5)], [0.8, 0.98, 0.9]),
    # the next A/B (2026-09-29): 0.30 x 0.15 m measured busier than the Voronoi
    # cobbles in frame (twice the joint edge per square metre); these are 0.60 x
    # 0.30 m, about the cobbles' edge density, in straight courses
    "setts_lg":    (lambda r: s_brick(r, bw=32, bh=16, w=512, h=512, mortar=2, dome=4.0, gap_shade=0),
                    [("#8b725f", 7, 6), ("#57483f", 5, 7), ("#6b6358", 5, 5)], [0.8, 0.98, 0.9]),
    # monuments (2026-09-29, the grand fountain after the user's sheet): pale
    # limestone that reads lighter than the honey houses round it
    "limestone":   (lambda r: s_ashlar(r, mortar=2, dome=4.0, gap_shade=0),
                    [("#c5baab", 7, 4), ("#776b61", 5, 6), ("#5f6e3a", 5, 3)], [0.85, 0.98, 0.9]),
    "cloth_red":   (s_cloth,      [("#9a3b30", 7), ("#2a1a18", 5), ("#d8c8a0", 7)], [0.95, 0.95, 0.95]),
    "cloth_blue":  (s_cloth,      [("#3a5a8a", 7), ("#1a2030", 5), ("#d8c8a0", 7)], [0.95, 0.95, 0.95]),
    "cloth_cream": (lambda r: s_cloth(r, stripe=0), [("#cdbf98", 7), ("#3a3226", 5), ("#cdbf98", 7)], [0.95, 0.95, 0.95]),
    "stained_glass": (s_stained_glass, [("#9a2a2a", 5), ("#141414", 5), ("#2a4a9a", 5), ("#c09a2a", 5)],
                      [0.2, 0.9, 0.2, 0.2]),
    "crops":       (s_crops,      [("#b8983c", 7), ("#4a3624", 5), ("#6a7a30", 7)], [0.95, 0.95, 0.95]),
    # rainforest
    "jungle_floor": (s_mud,       [("#3a2e22", 5), ("#3f6a2a", 7), ("#6a5a2a", 7)], [0.45, 0.6, 0.6]),
}


# ---------------------------------------------------------------------------
# bake: layers -> albedo, normal, ORM
# ---------------------------------------------------------------------------

def bake(name):
    recipe, ramp_defs, rough = SURFACES[name]
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    L = recipe(rng)
    ramps = [ramp(*d) for d in ramp_defs]   # (base hex, steps[, L* per step])
    if name in HUE and L.unit is not None:
        rough = list(rough)
        base = ramp_defs[0]
        lab = _to_lab(_hex(base[0]))
        for deg in HUE[name]:
            a = np.radians(deg)
            turned = np.array([lab[0], lab[1] * np.cos(a) - lab[2] * np.sin(a), lab[1] * np.sin(a) + lab[2] * np.cos(a)])
            rgb = np.clip(_from_lab(turned), 0, 1)
            hexed = "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in rgb)
            ramps.append(ramp(hexed, *base[1:]))
            rough.append(rough[0])
        hrng = np.random.default_rng(zlib.crc32((name + "#hue").encode()))
        n_units = int(L.unit.max()) + 1
        pick = hrng.choice(np.array([0, len(ramp_defs), len(ramp_defs) + 1]), size=n_units, p=HUE_SHARE)
        face = L.ramp == 0
        L.ramp = np.where(face, pick[L.unit], L.ramp).astype(np.int8)
    h, w = L.shade.shape
    albedo = np.zeros((h, w, 3), dtype=np.uint8)
    rough_map = np.zeros((h, w))
    for i, r in enumerate(ramps):
        m = L.ramp == i
        albedo[m] = r[np.clip(L.shade[m], 0, len(r) - 1)]
        rough_map[m] = rough[i]
    # normal from height, central differences on the torus (OpenGL/Godot: +Y up)
    hgt = L.height.astype(np.float64)
    dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5
    dy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5
    strength = NORMAL.get(name, 2.2)
    n = np.stack([-dx * strength, dy * strength, np.ones_like(hgt)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    normal = np.round((n * 0.5 + 0.5) * 255).astype(np.uint8)
    # cavity AO: how far below its neighbourhood each texel sits
    blur = hgt.copy()
    for _ in range(3):
        blur = (blur + np.roll(blur, 1, 0) + np.roll(blur, -1, 0) + np.roll(blur, 1, 1) + np.roll(blur, -1, 1)) / 5
    ao = np.clip(1.0 - np.maximum(blur - hgt, 0) * 1.6, 0.35, 1.0)
    orm = np.round(np.stack([ao, rough_map, np.zeros_like(ao)], -1) * 255).astype(np.uint8)
    return albedo, normal, orm, ramps


# ---------------------------------------------------------------------------
# measurement -- the same L* statistics the reference crops were scored with
# ---------------------------------------------------------------------------

def lstats(rgb):
    lab = _to_lab(rgb.astype(np.float64) / 255.0)
    Lc = lab[..., 0]
    g = (np.abs(np.diff(Lc, axis=1)).mean() + np.abs(np.diff(Lc, axis=0)).mean()) / 2
    # A seam is judged against the worst boundary INSIDE the tile, row by row
    # and column by column: a structured tile legitimately starts on a unit
    # edge, and an edge is supposed to differ. A broken wrap shows up as an
    # edge harsher than any the pattern makes on its own.
    rows = np.abs(np.diff(Lc, axis=0)).mean(1)
    cols = np.abs(np.diff(Lc, axis=1)).mean(0)
    seam = max(np.abs(Lc[0, :] - Lc[-1, :]).mean() / (rows.max() + 1e-6),
               np.abs(Lc[:, 0] - Lc[:, -1]).mean() / (cols.max() + 1e-6))
    return float(Lc.std()), float(g), float(seam)


def check(name, albedo, ramps):
    allowed = {tuple(c) for r in ramps for c in r}
    flat = albedo.reshape(-1, 3)
    uniq = {tuple(c) for c in np.unique(flat, axis=0)}
    bad = uniq - allowed
    std, grad, seam = lstats(albedo)
    ok_pal = not bad
    ok_seam = seam <= 1.05   # no harsher than the harshest interior boundary
    gap = None
    if name in STRUCT:
        lab = _to_lab(albedo.astype(np.float64) / 255.0)[..., 0]
        faces = [ramps[0]] + (ramps[-len(HUE[name]):] if name in HUE else [])
        face = np.isin(albedo.reshape(-1, 3).view([("", albedo.dtype)] * 3).ravel(),
                       np.array([tuple(c) for r in faces for c in r], dtype=[("", albedo.dtype)] * 3)).reshape(albedo.shape[:2])
        fx = face[:, 1:] & face[:, :-1]
        fy = face[1:, :] & face[:-1, :]
        fgrad = (np.abs(np.diff(lab, axis=1))[fx].mean() + np.abs(np.diff(lab, axis=0))[fy].mean()) / 2
        std, grad = float(lab[face].std()), float(fgrad)
        gap = float(lab[face].mean() - lab[~face].mean())
        ok_gate = grad * DENSITY.get(name, 1) <= CALM_GRAD and std <= CALM_STD and gap >= STRUCT_GAP
    elif name in CALM:
        ok_gate = grad * DENSITY.get(name, 1) <= CALM_GRAD and std <= CALM_STD
    else:
        ok_gate = grad >= GATE_GRAD and std >= GATE_STD
    return dict(name=name, std=std, grad=grad, seam=seam, palette=ok_pal, seamless=ok_seam,
                gate=ok_gate, colours=len(uniq), gap=gap)


def write(name, albedo, normal, orm):
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(albedo).save(os.path.join(OUT, f"{name}_albedo.png"))
    Image.fromarray(normal).save(os.path.join(OUT, f"{name}_normal.png"))
    Image.fromarray(orm).save(os.path.join(OUT, f"{name}_orm.png"))


def sheet(results, maps):
    os.makedirs(SHEETS, exist_ok=True)
    tile = 256
    cols = 6
    rows = (len(maps) + cols - 1) // cols
    img = Image.new("RGB", (cols * tile, rows * (tile + 34)), (18, 18, 22))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        f = ImageFont.load_default()
    for i, (name, alb) in enumerate(maps):
        r = results[name]
        x, y = (i % cols) * tile, (i // cols) * (tile + 34)
        # a 128-texel corner at 2x: the texels as they read at zoom x2
        crop = Image.fromarray(alb[:128, :128]).resize((tile, tile), Image.NEAREST)
        img.paste(crop, (x, y + 34))
        mark = "ok" if r["gate"] and r["palette"] and r["seamless"] else "MISS"
        d.text((x + 4, y + 2), f"{name}  {mark}", fill=(240, 220, 160), font=f)
        d.text((x + 4, y + 17), f"L*std {r['std']:.1f}  grad {r['grad']:.2f}  {r['colours']} col",
               fill=(210, 210, 210), font=f)
    img.save(os.path.join(SHEETS, "surfaces.png"))


def main(argv):
    names = [a for a in argv if not a.startswith("-")] or list(SURFACES)
    results, maps, manifest = {}, [], {}
    for name in names:
        a1, n1, o1, ramps = bake(name)
        a2, _, _, _ = bake(name)
        assert np.array_equal(a1, a2), f"{name}: not deterministic"
        r = check(name, a1, ramps)
        results[name] = r
        maps.append((name, a1))
        write(name, a1, n1, o1)
        h, w = a1.shape[:2]
        tpm = TEXELS_PER_M * DENSITY.get(name, 1)
        manifest[name] = dict(px=[w, h], texels_per_m=tpm, metres=[round(w / tpm, 4), round(h / tpm, 4)])
        print(f"{name:<13} {w}x{h}  L*std {r['std']:5.1f}  grad {r['grad']:5.2f}  seam {r['seam']:5.2f}  "
              f"colours {r['colours']:3d}  palette {'ok' if r['palette'] else 'FAIL'}  "
              f"seamless {'ok' if r['seamless'] else 'FAIL'}  gate {'ok' if r['gate'] else 'MISS'}"
              + (f"  (faces; gap {r['gap']:.1f} L* down)" if r["gap"] is not None else ""))
    # merged, not replaced: a one-surface run used to write a manifest holding
    # only that surface, and TexLib.Repeat then failed for every other one
    path = os.path.join(OUT, "manifest.json")
    if os.path.exists(path):
        with open(path) as fh:
            manifest = {**json.load(fh)["surfaces"], **manifest}
    with open(path, "w") as fh:
        json.dump(dict(texels_per_m=TEXELS_PER_M, surfaces=manifest), fh, indent=1)
    sheet(results, maps)
    fails = [n for n, r in results.items() if not (r["palette"] and r["seamless"])]
    miss = [n for n, r in results.items() if not r["gate"]]
    print(f"texgen: {len(results)} surfaces, invariant fails {fails or 'none'}, gate misses {miss or 'none'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
