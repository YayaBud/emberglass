"""
Emberglass detailed architecture primitives.

The forms the monument half of the library needs and the domestic driver does
not: round coursed towers, crenellated parapets, voussoired arches, spires and
conical caps, buttresses, tracery windows, windmill sails, striped awnings and
heraldic banners.

Same conventions as detail_primitives: front faces -Y, +Z up, one object per
component carrying its own material slots.
"""

import bpy
import bmesh
import random
from math import radians, cos, sin, tan, pi, atan2

import detail_primitives as dp
from detail_primitives import (_begin, _end, _box, _blob, _cyl, _quad,
                               _prism_beam, _peg, _nail_head, _moss_clump,
                               _moss_run, _lichen_patch, _weed_tuft,
                               ROOF_PALETTES)


def _stone_slots(mats, stone="limestone"):
    return dp._masonry_slots(mats, stone)


S_MORTAR, S_A, S_B, S_C, S_MOSS, S_LICHEN, S_WEED = range(7)


# =============================================================================
# Round coursed tower
# =============================================================================

def create_round_tower(name, radius=1.6, height=5.5, mats=None, seed=11,
                       course_h=0.30, batter=0.06, moss=True, weeds=True,
                       string_courses=(), arrow_slits=0, door=False,
                       stone="limestone"):
    """Round rubble tower laid block by block, with a slight batter.

    Every course is a ring of individually placed wedge blocks; the block count
    per ring drops as the tower tapers, so the bond never repeats vertically.
    """
    obj, mesh, bm = _begin(name, _stone_slots(mats, stone))
    rng = random.Random(seed)

    n_courses = max(4, int(height / course_h))
    ch = height / n_courses
    for i in range(n_courses):
        z0 = i * ch
        t = z0 / max(0.001, height)
        r = radius * (1.0 - batter * t)
        # Mortar core, set back so each block reads proud
        _cyl(bm, S_MORTAR, r - 0.10, ch + 0.01, (0, 0, z0 + ch * 0.5),
             segments=14)
        n_blocks = max(8, int(2 * pi * r / 0.46))
        phase = rng.uniform(0, 2 * pi)
        for k in range(n_blocks):
            a0 = phase + 2 * pi * k / n_blocks
            arc = (2 * pi / n_blocks) * rng.uniform(0.80, 0.97)
            bw = 2.0 * r * sin(arc * 0.5)
            th = rng.uniform(0.16, 0.24)
            bh = ch * rng.uniform(0.76, 0.96)
            zc = z0 + ch * 0.5 + (ch - bh) * rng.uniform(-0.35, 0.35)
            rr = r - th * 0.5 + 0.045
            _box(bm, rng.choice([S_A, S_A, S_B, S_B, S_C]),
                 size=(bw, th, bh),
                 loc=(cos(a0) * rr, sin(a0) * rr, zc),
                 rot=(rng.uniform(-0.02, 0.02), 0.0, a0 + pi * 0.5))
            if moss and rng.random() < (0.16 if t < 0.25 else 0.05):
                _moss_clump(bm, S_MOSS,
                            (cos(a0) * (r + 0.03), sin(a0) * (r + 0.03),
                             zc + bh * 0.45),
                            rng.uniform(0.06, 0.12), rng, squash=0.5)
            if rng.random() < 0.07:
                _lichen_patch(bm, S_LICHEN,
                              (cos(a0) * (r + 0.03), sin(a0) * (r + 0.03), zc),
                              rng.uniform(0.05, 0.10), 2, rng, plates=2)

    # Splayed plinth
    _cyl(bm, S_B, radius + 0.16, 0.22, (0, 0, 0.0), segments=16, base=True)
    n_p = max(10, int(2 * pi * radius / 0.42))
    for k in range(n_p):
        a0 = 2 * pi * k / n_p
        _box(bm, rng.choice([S_A, S_B, S_C]),
             size=(2 * pi * (radius + 0.1) / n_p * 0.9, 0.22, 0.30),
             loc=(cos(a0) * (radius + 0.06), sin(a0) * (radius + 0.06), 0.0),
             rot=(0, 0, a0 + pi * 0.5), base=True)

    # Projecting string courses
    for sz in string_courses:
        r = radius * (1.0 - batter * (sz / max(0.001, height)))
        n_s = max(12, int(2 * pi * r / 0.40))
        for k in range(n_s):
            a0 = 2 * pi * k / n_s
            _box(bm, rng.choice([S_A, S_C]),
                 size=(2 * pi * (r + 0.1) / n_s * 0.92, 0.20, 0.17),
                 loc=(cos(a0) * (r + 0.07), sin(a0) * (r + 0.07), sz),
                 rot=(0, 0, a0 + pi * 0.5), base=True)

    # Arrow slits, evenly spun up the shaft
    for i in range(arrow_slits):
        za = height * (0.28 + 0.52 * (i / max(1, arrow_slits - 1)))
        a0 = -pi * 0.5 + i * 0.9
        r = radius * (1.0 - batter * (za / height))
        _box(bm, S_MORTAR, size=(0.13, 0.30, 0.68),
             loc=(cos(a0) * (r - 0.02), sin(a0) * (r - 0.02), za),
             rot=(0, 0, a0 + pi * 0.5))
        for sgn in (-1, 1):
            _box(bm, S_C, size=(0.14, 0.24, 0.80),
                 loc=(cos(a0) * (r + 0.03) - sin(a0) * sgn * 0.20,
                      sin(a0) * (r + 0.03) + cos(a0) * sgn * 0.20, za),
                 rot=(0, 0, a0 + pi * 0.5))

    if moss:
        n_m = max(10, int(2 * pi * radius / 0.24))
        for k in range(n_m):
            if rng.random() < 0.35:
                continue
            a0 = 2 * pi * k / n_m
            _moss_clump(bm, S_MOSS,
                        (cos(a0) * (radius + 0.20), sin(a0) * (radius + 0.20),
                         0.05), rng.uniform(0.08, 0.15), rng)
    if weeds:
        for k in range(max(4, int(2 * pi * radius / 0.9))):
            a0 = rng.uniform(0, 2 * pi)
            _weed_tuft(bm, S_WEED,
                       (cos(a0) * (radius + 0.10), sin(a0) * (radius + 0.10),
                        rng.uniform(0.25, 0.7)),
                       rng.uniform(0.14, 0.26), rng, blades=rng.randint(5, 8))

    return _end(obj, mesh, bm, bevel=0.010, segments=2)


# =============================================================================
# Crenellated parapet
# =============================================================================

def create_crenellation(name, width, depth, mats=None, seed=13, merlon=0.42,
                        gap=0.34, height=0.62, thick=0.30, round_plan=False,
                        radius=1.6, moss=True, cap=True, stone="limestone"):
    """Merlons and embrasures round a wall head, laid as individual stones."""
    obj, mesh, bm = _begin(name, _stone_slots(mats, stone))
    rng = random.Random(seed)

    if round_plan:
        n = max(8, int(2 * pi * radius / (merlon + gap)))
        for k in range(n):
            a0 = 2 * pi * k / n
            _box(bm, rng.choice([S_A, S_B, S_C]),
                 size=(merlon, thick, height * rng.uniform(0.92, 1.0)),
                 loc=(cos(a0) * radius, sin(a0) * radius, 0.0),
                 rot=(0, 0, a0 + pi * 0.5), base=True)
            if moss and rng.random() < 0.28:
                _moss_clump(bm, S_MOSS,
                            (cos(a0) * radius, sin(a0) * radius, height),
                            rng.uniform(0.05, 0.10), rng)
        if cap:
            n_c = max(12, int(2 * pi * radius / 0.36))
            for k in range(n_c):
                a0 = 2 * pi * k / n_c
                _box(bm, rng.choice([S_A, S_C]),
                     size=(2 * pi * radius / n_c * 0.94, thick + 0.16, 0.16),
                     loc=(cos(a0) * radius, sin(a0) * radius, -0.16),
                     rot=(0, 0, a0 + pi * 0.5), base=True)
        return _end(obj, mesh, bm, bevel=0.010, segments=2)

    hw, hd = width * 0.5, depth * 0.5
    for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
        run = hd if ax == 0 else hw
        n = max(2, int((run * 2) / (merlon + gap)))
        step = (run * 2) / n
        for i in range(n):
            c = -run + (i + 0.5) * step
            mh = height * rng.uniform(0.90, 1.0)
            if ax == 0:
                _box(bm, rng.choice([S_A, S_B, S_C]),
                     size=(thick, merlon, mh),
                     loc=(sgn * (hw - thick * 0.5 + 0.03), c, 0.0),
                     rot=(0, 0, rng.uniform(-0.01, 0.01)), base=True)
                mp = (sgn * (hw + 0.02), c, mh)
            else:
                _box(bm, rng.choice([S_A, S_B, S_C]),
                     size=(merlon, thick, mh),
                     loc=(c, sgn * (hd - thick * 0.5 + 0.03), 0.0),
                     rot=(0, 0, rng.uniform(-0.01, 0.01)), base=True)
                mp = (c, sgn * (hd + 0.02), mh)
            if moss and rng.random() < 0.26:
                _moss_clump(bm, S_MOSS, mp, rng.uniform(0.05, 0.11), rng)

    if cap:
        for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            run = hd if ax == 0 else hw
            n = max(3, int(run * 2 / 0.44))
            for i in range(n):
                c = -run + (i + 0.5) * (run * 2 / n)
                L = (run * 2 / n) - 0.03
                if ax == 0:
                    _box(bm, rng.choice([S_A, S_C]),
                         size=(thick + 0.20, L, 0.17),
                         loc=(sgn * (hw - thick * 0.5 + 0.03), c, -0.17),
                         base=True)
                else:
                    _box(bm, rng.choice([S_A, S_C]),
                         size=(L, thick + 0.20, 0.17),
                         loc=(c, sgn * (hd - thick * 0.5 + 0.03), -0.17),
                         base=True)
    return _end(obj, mesh, bm, bevel=0.010, segments=2)


# =============================================================================
# Voussoired arch and portal
# =============================================================================

def create_arch_portal(name, width=3.2, height=3.4, depth=1.4, mats=None,
                       seed=17, gate=True, portcullis=True, keystone=True,
                       stone="limestone"):
    """Semicircular arch of individual voussoirs over a gated opening."""
    obj, mesh, bm = _begin(name, _stone_slots(mats, stone) + [
        mats["M_Iron_Aged"], mats["M_Wood_Planks"], mats["M_Roof_Void"]])
    P_IRON, P_WOOD, P_DARK = 7, 8, 9
    rng = random.Random(seed)
    r = width * 0.5
    spring = height - r

    # Dark void behind the opening
    _box(bm, P_DARK, size=(width - 0.06, depth * 0.5, spring),
         loc=(0, depth * 0.1, spring * 0.5), base=False)
    _cyl(bm, P_DARK, r - 0.04, depth * 0.5, (0, depth * 0.1, spring),
         rot=(pi / 2, 0, 0), segments=16)

    # Jambs, laid as alternating long-and-short quoins
    n_j = max(4, int(spring / 0.34))
    for sgn in (-1, 1):
        for i in range(n_j):
            z0 = i * (spring / n_j)
            long_ = (i % 2 == 0)
            jw = 0.52 if long_ else 0.36
            _box(bm, rng.choice([S_A, S_B, S_C]),
                 size=(jw, depth, (spring / n_j) - 0.035),
                 loc=(sgn * (r + jw * 0.5 - 0.02), 0, z0), base=True)

    # Voussoirs
    n_v = max(9, int(pi * r / 0.34))
    if n_v % 2 == 0:
        n_v += 1
    for i in range(n_v):
        a0 = pi * (i + 0.5) / n_v
        vr = r + 0.30
        mid = (n_v // 2)
        mi = S_C if (keystone and i == mid) else rng.choice([S_A, S_B, S_C])
        vw = (pi * vr / n_v) * rng.uniform(0.92, 1.0)
        extra = 0.14 if (keystone and i == mid) else 0.0
        _box(bm, mi, size=(vw, depth, 0.62 + extra),
             loc=(-cos(a0) * vr, 0, spring + sin(a0) * vr),
             rot=(0, a0 - pi * 0.5, 0))
        if rng.random() < 0.20:
            _moss_clump(bm, S_MOSS,
                        (-cos(a0) * (vr + 0.30), -depth * 0.5,
                         spring + sin(a0) * (vr + 0.30)),
                        rng.uniform(0.05, 0.10), rng)

    if portcullis:
        for i in range(5):
            x = -r * 0.78 + i * (r * 1.56 / 4.0)
            _box(bm, P_IRON, size=(0.07, 0.07, spring + r * 0.55),
                 loc=(x, -depth * 0.32, (spring + r * 0.55) * 0.5), base=False)
        for j in range(3):
            _box(bm, P_IRON, size=(width * 0.82, 0.06, 0.07),
                 loc=(0, -depth * 0.32, 0.5 + j * (spring * 0.42)))
        for i in range(5):
            x = -r * 0.78 + i * (r * 1.56 / 4.0)
            _box(bm, P_IRON, size=(0.09, 0.09, 0.20),
                 loc=(x, -depth * 0.32, 0.10))

    if gate:
        for sgn in (-1, 1):
            for i in range(4):
                bw = (r - 0.1) / 4.0
                x = sgn * (0.06 + (i + 0.5) * bw)
                _prism_beam(bm, P_WOOD, spring * 0.95, bw - 0.02, 0.10,
                            loc=(x, depth * 0.30, 0.0), chamfer=0.010, rings=3,
                            bow=0.006, rng=rng, chips=1, chip_mat=P_WOOD,
                            base=True)
            for z in (spring * 0.22, spring * 0.72):
                _box(bm, P_IRON, size=(r - 0.08, 0.05, 0.14),
                     loc=(sgn * (r * 0.5), depth * 0.24, z))
                for k in range(3):
                    _nail_head(bm, P_IRON,
                               (sgn * (0.2 + k * (r - 0.3) / 2.0),
                                depth * 0.19, z), rot=(pi / 2, 0, 0),
                               radius=0.022)
    return _end(obj, mesh, bm, bevel=0.010, segments=2)


def create_arch_window(name, width=0.80, height=1.80, mats=None, seed=19,
                       stained=True, tracery=True, depth=0.34, gothic=False,
                       stone="limestone"):
    """Arched light with voussoir head, tracery bars and coloured glass."""
    slots = _stone_slots(mats, stone) + [
        mats["M_Iron_Aged"], mats["M_Window_Warm"], mats["M_Stained_Glass"],
        mats["M_Window_Dim"]]
    obj, mesh, bm = _begin(name, slots)
    W_IRON, W_GLOW, W_STAIN, W_DIM = 7, 8, 9, 10
    rng = random.Random(seed)
    r = width * 0.5
    spring = height - r

    glass_mat = W_STAIN if stained else W_GLOW
    _box(bm, glass_mat, size=(width - 0.10, 0.04, spring),
         loc=(0, -depth * 0.18, spring * 0.5), base=False)
    _cyl(bm, glass_mat, r - 0.05, 0.04, (0, -depth * 0.18, spring),
         rot=(pi / 2, 0, 0), segments=14)
    if rng.random() < 0.6:
        _box(bm, W_DIM, size=(width * 0.38, 0.045, spring * 0.42),
             loc=(rng.uniform(-0.1, 0.1), -depth * 0.19, spring * 0.45))

    for sgn in (-1, 1):
        n_j = max(3, int(spring / 0.32))
        for i in range(n_j):
            _box(bm, rng.choice([S_A, S_B, S_C]),
                 size=(0.20, depth, (spring / n_j) - 0.03),
                 loc=(sgn * (r + 0.07), 0, i * (spring / n_j)), base=True)

    n_v = max(7, int(pi * r / 0.24))
    for i in range(n_v):
        a0 = pi * (i + 0.5) / n_v
        vr = r + 0.11
        h_ = 1.0
        if gothic:
            # Pinch the head toward a point
            h_ = 1.0 + 0.35 * abs(cos(a0))
        _box(bm, rng.choice([S_A, S_B, S_C]),
             size=((pi * vr / n_v) * 0.96, depth, 0.24 * h_),
             loc=(-cos(a0) * vr, 0, spring + sin(a0) * vr * (1.20 if gothic else 1.0)),
             rot=(0, a0 - pi * 0.5, 0))

    if tracery:
        _box(bm, W_IRON, size=(0.05, depth * 0.5, height * 0.86),
             loc=(0, -depth * 0.26, height * 0.44))
        for j in range(3):
            _box(bm, W_IRON, size=(width - 0.12, depth * 0.4, 0.042),
                 loc=(0, -depth * 0.26, spring * (0.26 + j * 0.32)))
        _cyl(bm, W_IRON, r * 0.46, depth * 0.34, (0, -depth * 0.26, spring + r * 0.30),
             rot=(pi / 2, 0, 0), segments=12)

    # Sill with drip and moss
    _box(bm, S_C, size=(width + 0.34, depth + 0.16, 0.11),
         loc=(0, -0.05, -0.03), rot=(-0.05, 0, 0))
    for sgn in (-1, 1):
        _moss_clump(bm, S_MOSS, (sgn * (width * 0.5 + 0.10), -depth * 0.5, 0.0),
                    rng.uniform(0.04, 0.07), rng)
    return _end(obj, mesh, bm, bevel=0.009, segments=2)


# =============================================================================
# Spires, conical caps, buttresses
# =============================================================================

def create_conical_roof(name, radius=1.8, height=2.4, mats=None, seed=23,
                        palette="slate", rows=None, finial=True, flare=0.12):
    """Cone clad in individually laid tiles, course by course."""
    a, b, c, aged = ROOF_PALETTES.get(palette, ROOF_PALETTES["slate"])
    obj, mesh, bm = _begin(name, [mats["M_Timber_Aged"], mats[a], mats[b],
                                  mats[c], mats[aged], mats["M_Moss"],
                                  mats["M_Iron_Aged"]])
    C_TIM, C_A, C_B, C_C, C_AGED, C_MOSS, C_IRON = range(7)
    rng = random.Random(seed)

    slope = (radius ** 2 + height ** 2) ** 0.5
    phi = atan2(height, radius)          # slope angle from horizontal
    rows = rows or max(4, int(slope / 0.24))
    _cyl(bm, C_TIM, radius * 0.98, height, (0, 0, 0), segments=16,
         radius2=0.02, base=True)

    # Rx(phi - pi) then Rz(a + pi/2) lays a tile's local +Y down the cone and
    # its local +Z along the (inverted, symmetric) surface normal.
    tilt = phi - pi
    nx, nz = cos(phi), sin(phi)
    for r_i in range(rows):
        t0 = r_i / rows
        rr = radius * (1.0 - t0) + (flare if r_i == 0 else 0.0)
        zz = height * t0
        n = max(6, int(2 * pi * max(0.05, rr) / 0.26))
        phase = rng.uniform(0, 2 * pi) if r_i % 2 else 0.0
        for k in range(n):
            a0 = phase + 2 * pi * k / n
            tw = (2 * pi * max(0.05, rr) / n) * 0.96
            mi = C_AGED if rng.random() < 0.13 else rng.choice([C_A, C_A, C_B, C_C])
            _box(bm, mi, size=(tw, (slope / rows) * 1.55, 0.05),
                 loc=(cos(a0) * (rr + nx * 0.035),
                      sin(a0) * (rr + nx * 0.035),
                      zz + (height / rows) * 0.5 + nz * 0.035),
                 rot=(tilt, 0.0, a0 + pi * 0.5))
        if r_i < 2:
            for _ in range(max(1, int(n * 0.16))):
                a0 = rng.uniform(0, 2 * pi)
                _moss_clump(bm, C_MOSS,
                            (cos(a0) * (rr + 0.06), sin(a0) * (rr + 0.06),
                             zz + 0.05), rng.uniform(0.05, 0.10), rng)

    if finial:
        _cyl(bm, C_IRON, 0.05, 0.42, (0, 0, height - 0.04), segments=8,
             base=True)
        _blob(bm, C_IRON, (0, 0, height + 0.40), (0.10, 0.10, 0.12))
        _box(bm, C_IRON, size=(0.30, 0.03, 0.22), loc=(0, 0, height + 0.62))
    return _end(obj, mesh, bm, bevel=0.006, segments=1, angle=42.0)


def create_spire(name, base=1.5, height=4.2, mats=None, seed=29,
                 palette="slate", sides=8, finial=True, lucarnes=2):
    """Broach spire: an octagonal pyramid clad in courses, with dormer lucarnes."""
    a, b, c, aged = ROOF_PALETTES.get(palette, ROOF_PALETTES["slate"])
    obj, mesh, bm = _begin(name, [mats["M_Timber_Aged"], mats[a], mats[b],
                                  mats[c], mats[aged], mats["M_Moss"],
                                  mats["M_Iron_Aged"], mats["M_Gold_Brass"]])
    P_TIM, P_A, P_B, P_C, P_AGED, P_MOSS, P_IRON, P_GOLD = range(8)
    rng = random.Random(seed)

    _cyl(bm, P_TIM, base * 0.99, height, (0, 0, 0), segments=sides,
         radius2=0.03, base=True)

    rows = max(6, int(height / 0.30))
    phi = atan2(height, base)
    slope = (base ** 2 + height ** 2) ** 0.5
    tilt = phi - pi
    nx, nz = cos(phi), sin(phi)
    for r_i in range(rows):
        t0 = r_i / rows
        rr = base * (1.0 - t0)
        zz = height * t0
        n = max(sides, int(2 * pi * max(0.05, rr) / 0.28))
        phase = rng.uniform(0, 2 * pi) if r_i % 2 else 0.0
        for k in range(n):
            a0 = phase + 2 * pi * k / n
            tw = (2 * pi * max(0.05, rr) / n) * 0.95
            mi = P_AGED if rng.random() < 0.11 else rng.choice([P_A, P_A, P_B, P_C])
            _box(bm, mi, size=(tw, (slope / rows) * 1.5, 0.048),
                 loc=(cos(a0) * (rr + nx * 0.03), sin(a0) * (rr + nx * 0.03),
                      zz + (height / rows) * 0.5 + nz * 0.03),
                 rot=(tilt, 0.0, a0 + pi * 0.5))

    for i in range(lucarnes):
        a0 = -pi * 0.5 + i * pi * 0.5
        zz = height * 0.22
        rr = base * 0.80
        _box(bm, P_A, size=(0.34, 0.30, 0.44),
             loc=(cos(a0) * rr, sin(a0) * rr, zz), rot=(0, 0, a0 + pi * 0.5))
        _box(bm, P_TIM, size=(0.18, 0.10, 0.26),
             loc=(cos(a0) * (rr + 0.14), sin(a0) * (rr + 0.14), zz),
             rot=(0, 0, a0 + pi * 0.5))

    if finial:
        _cyl(bm, P_IRON, 0.055, 0.70, (0, 0, height - 0.05), segments=8,
             base=True)
        _blob(bm, P_GOLD, (0, 0, height + 0.68), (0.13, 0.13, 0.15), subdiv=1)
        _box(bm, P_IRON, size=(0.05, 0.05, 0.40), loc=(0, 0, height + 0.96))
        _box(bm, P_IRON, size=(0.34, 0.03, 0.03), loc=(0, 0, height + 1.10))
        _box(bm, P_IRON, size=(0.03, 0.34, 0.03), loc=(0, 0, height + 1.10))
    return _end(obj, mesh, bm, bevel=0.006, segments=1, angle=42.0)


def create_buttress(name, height=3.0, mats=None, seed=31, width=0.55,
                    projection=0.80, stages=2, weathering=True,
                    stone="limestone"):
    """Stepped buttress in coursed stone with sloped weatherings."""
    obj, mesh, bm = _begin(name, _stone_slots(mats, stone))
    rng = random.Random(seed)

    for s in range(stages):
        z0 = height * (s / stages)
        z1 = height * ((s + 1) / stages)
        proj = projection * (1.0 - s * 0.38)
        n = max(2, int((z1 - z0) / 0.30))
        for i in range(n):
            zz = z0 + i * ((z1 - z0) / n)
            bh = ((z1 - z0) / n) - 0.035
            _box(bm, rng.choice([S_A, S_B, S_C]),
                 size=(width, proj, bh),
                 loc=(0, -proj * 0.5, zz),
                 rot=(0, 0, rng.uniform(-0.008, 0.008)), base=True)
        if weathering:
            _box(bm, S_C, size=(width + 0.10, proj * 0.75, 0.16),
                 loc=(0, -proj * 0.62, z1 - 0.05), rot=(-0.55, 0, 0))
    _box(bm, S_C, size=(width + 0.18, projection + 0.16, 0.16),
         loc=(0, -(projection + 0.16) * 0.5 + 0.08, 0.0), base=True)
    for _ in range(3):
        _weed_tuft(bm, S_WEED,
                   (rng.uniform(-width * 0.4, width * 0.4),
                    -projection * rng.uniform(0.2, 0.9), 0.14),
                   rng.uniform(0.10, 0.20), rng)
    _moss_run(bm, S_MOSS, (-width * 0.5, -projection, 0.03),
              (width * 0.5, -projection, 0.03), 4, 0.07, rng, skip=0.4)
    return _end(obj, mesh, bm, bevel=0.010, segments=2)


# =============================================================================
# Windmill sails, awnings, banners
# =============================================================================

def create_windmill_sails(name, mats=None, seed=37, length=3.4, blades=4):
    """Lattice sails on a hub, each blade with individual slats."""
    obj, mesh, bm = _begin(name, [mats["M_Timber_Aged"], mats["M_Iron_Aged"],
                                  mats["M_Canvas_Sail"], mats["M_Timber_Chip"]])
    W_TIM, W_IRON, W_SAIL, W_CHIP = range(4)
    rng = random.Random(seed)

    _cyl(bm, W_IRON, 0.20, 0.34, (0, 0, 0), rot=(pi / 2, 0, 0), segments=12)
    _cyl(bm, W_IRON, 0.10, 0.52, (0, 0, 0), rot=(pi / 2, 0, 0), segments=10)

    for b in range(blades):
        ang = 2 * pi * b / blades + 0.22
        # _prism_beam runs along local +Z; Ry(ang) swings it in the XZ plane,
        # so u is the whip direction and p is perpendicular to it in-plane.
        ux, uz = sin(ang), cos(ang)
        px, pz = cos(ang), -sin(ang)
        _prism_beam(bm, W_TIM, length, 0.085, 0.085,
                    loc=(0, -0.12, 0), rot=(0, ang, 0), chamfer=0.010, rings=4,
                    bow=0.02, rng=rng, chips=2, chip_mat=W_CHIP, base=True)
        n_slat = 9
        for i in range(n_slat):
            t = (i + 0.7) / (n_slat + 0.7)
            r = length * t
            sw = 0.60 * (1.0 - t * 0.22)
            cxp = ux * r + px * sw * 0.5
            czp = uz * r + pz * sw * 0.5
            _box(bm, W_SAIL if i % 3 else W_TIM,
                 size=(0.05, 0.07, sw),
                 loc=(cxp, -0.17, czp), rot=(0, ang + pi * 0.5, 0))
            _box(bm, W_TIM, size=(0.04, 0.06, sw * 0.98),
                 loc=(cxp, -0.10, czp), rot=(0, ang + pi * 0.5, 0))
        # Outer rail tying the slat ends, parallel to the whip
        _box(bm, W_TIM, size=(0.05, 0.05, length * 0.80),
             loc=(ux * length * 0.55 + px * 0.55, -0.17,
                  uz * length * 0.55 + pz * 0.55),
             rot=(0, ang, 0))
    return _end(obj, mesh, bm, bevel=0.006, segments=1, angle=42.0)


def create_striped_awning(name, width=2.4, depth=1.5, mats=None, seed=41,
                          colour="red", posts=True, height=2.2, valance=True):
    """Canvas awning with individual stripe panels, sag, posts and a valance."""
    stripe = mats["M_Awning_Red"] if colour == "red" else mats["M_Awning_Blue"]
    obj, mesh, bm = _begin(name, [mats["M_Timber_Aged"], stripe,
                                  mats["M_Linen"], mats["M_Iron_Aged"],
                                  mats["M_Timber_Chip"]])
    A_TIM, A_STRIPE, A_LINEN, A_IRON, A_CHIP = range(5)
    rng = random.Random(seed)
    hw = width * 0.5
    drop = 0.42

    n = max(5, int(width / 0.24))
    sw = width / n
    for i in range(n):
        x = -hw + (i + 0.5) * sw
        mi = A_STRIPE if i % 2 == 0 else A_LINEN
        sag = 0.07 * sin(pi * (i + 0.5) / n)
        _box(bm, mi, size=(sw - 0.006, depth * 1.02, 0.035),
             loc=(x, -depth * 0.5, height - drop * 0.5 - sag),
             rot=(atan2(drop, depth), 0, 0))
        if valance:
            _box(bm, mi, size=(sw - 0.006, 0.03, 0.22),
                 loc=(x, -depth - 0.02, height - drop - 0.11 - sag))

    _prism_beam(bm, A_TIM, width + 0.12, 0.07, 0.09,
                loc=(-(width + 0.12) * 0.5, 0.02, height), rot=(0, pi / 2, 0),
                chamfer=0.010, rings=3, rng=rng, chips=2, chip_mat=A_CHIP,
                base=True)
    _prism_beam(bm, A_TIM, width + 0.06, 0.06, 0.07,
                loc=(-(width + 0.06) * 0.5, -depth, height - drop),
                rot=(0, pi / 2, 0), chamfer=0.008, rings=3, rng=rng,
                base=True)
    if posts:
        for sgn in (-1, 1):
            _prism_beam(bm, A_TIM, height - drop, 0.085, 0.085,
                        loc=(sgn * (hw - 0.05), -depth, 0.0), chamfer=0.010,
                        rings=4, bow=0.008, rng=rng, chips=2, chip_mat=A_CHIP,
                        base=True)
            _box(bm, A_IRON, size=(0.05, 0.16, 0.05),
                 loc=(sgn * (hw - 0.05), -depth + 0.10, height - drop - 0.10),
                 rot=(0.7, 0, 0))
    else:
        for sgn in (-1, 1):
            _box(bm, A_IRON, size=(0.035, depth * 0.9, 0.035),
                 loc=(sgn * (hw - 0.08), -depth * 0.45, height - drop * 0.3),
                 rot=(-0.5, 0, 0))
    return _end(obj, mesh, bm, bevel=0.006, segments=1, angle=42.0)


def create_banner(name, width=0.70, height=1.90, mats=None, seed=43,
                  colour="red", emblem=True, pole=True, swallowtail=True):
    """Hanging heraldic banner with a sagging cloth, fringe and charge."""
    cloth = {"red": "M_Guild_Red", "blue": "M_Guild_Blue",
             "cream": "M_Wool_Cream"}.get(colour, "M_Guild_Red")
    obj, mesh, bm = _begin(name, [mats["M_Timber_Aged"], mats[cloth],
                                  mats["M_Gold_Brass"], mats["M_Iron_Aged"]])
    B_TIM, B_CLOTH, B_GOLD, B_IRON = range(4)
    rng = random.Random(seed)

    if pole:
        _box(bm, B_IRON, size=(0.05, 0.26, 0.05), loc=(0, -0.13, height + 0.06))
        _cyl(bm, B_IRON, 0.05, width + 0.18, (0, -0.24, height + 0.04),
             rot=(0, pi / 2, 0), segments=8)
        for sgn in (-1, 1):
            _blob(bm, B_GOLD, (sgn * (width * 0.5 + 0.09), -0.24, height + 0.04),
                  (0.055, 0.055, 0.055))

    rows = max(7, int(height / 0.22))
    for j in range(rows):
        t = (j + 0.5) / rows
        z = height * (1.0 - t)
        if swallowtail and t > 0.78:
            w = width * max(0.30, 1.0 - 0.60 * (t - 0.78) / 0.22)
        else:
            w = width
        sag = 0.035 * sin(pi * t)
        _box(bm, B_CLOTH, size=(w, 0.022, (height / rows) * 1.10),
             loc=(0, -0.235 - sag, z),
             rot=(0, 0, rng.uniform(-0.006, 0.006)))
    if swallowtail:
        for sgn in (-1, 1):
            _box(bm, B_CLOTH, size=(width * 0.30, 0.022, 0.30),
                 loc=(sgn * width * 0.32, -0.245, height * 0.10))
    if emblem:
        _blob(bm, B_GOLD, (0, -0.262, height * 0.58),
              (width * 0.26, 0.012, width * 0.26), subdiv=1)
        _box(bm, B_GOLD, size=(width * 0.44, 0.010, 0.045),
             loc=(0, -0.262, height * 0.34))
    return _end(obj, mesh, bm, bevel=0.005, segments=1, angle=45.0)


# =============================================================================
# Lighthouse lamp room
# =============================================================================

def create_lighthouse_lamp(name, radius=1.30, height=1.95, mats=None, seed=53,
                           gallery=2.05, rail_h=0.86, posts=8,
                           stone="granite"):
    """Corbelled gallery, glazed lamp room and the light burning inside it.

    Local origin sits on the top course of the shaft: the corbels hang below
    z=0, the deck is laid at z=0, and the roof plate finishes at
    height + 0.58, which is where a conical roof goes.
    """
    # Window_Dim, not Window_Warm: at 1.45 emission under the Standard view
    # transform the panes clip to flat white and swallow the mullions and the
    # reflector. The flame is the only thing here allowed to blow out.
    slots = _stone_slots(mats, stone) + [
        mats["M_Iron_Aged"], mats["M_Window_Dim"],
        mats["M_Lantern_Flame"], mats["M_Timber_Aged"]]
    S_IRON, S_GLASS, S_FLAME, S_TIMBER = 7, 8, 9, 10
    obj, mesh, bm = _begin(name, slots)
    rng = random.Random(seed)

    # Corbels carrying the gallery, two courses, laid one stone at a time
    n_cb = max(12, int(2 * pi * gallery / 0.42))
    for k in range(n_cb):
        a0 = 2 * pi * k / n_cb
        for dr, dz in ((0.16, -0.46), (0.40, -0.26)):
            rr = gallery - 0.52 + dr
            _box(bm, rng.choice([S_A, S_B, S_C]),
                 size=(2 * pi * rr / n_cb * 0.88, 0.36, 0.21),
                 loc=(cos(a0) * rr, sin(a0) * rr, dz),
                 rot=(rng.uniform(-0.015, 0.015), 0.0, a0 + pi * 0.5))

    # Gallery deck - mortar bed, then flags in wedges so the joints read
    _cyl(bm, S_MORTAR, gallery - 0.08, 0.15, (0, 0, 0.075), segments=18)
    n_fl = max(14, int(2 * pi * gallery / 0.55))
    for k in range(n_fl):
        a0 = 2 * pi * k / n_fl + rng.uniform(-0.025, 0.025)
        rr = gallery * 0.60
        _box(bm, rng.choice([S_A, S_B, S_C]),
             size=(2 * pi * rr / n_fl * 0.93, gallery * 0.76,
                   rng.uniform(0.15, 0.18)),
             loc=(cos(a0) * rr, sin(a0) * rr, 0.08),
             rot=(0, 0, a0 + pi * 0.5), base=True)

    # Iron railing - posts lean a little, nothing here is plumb
    n_rp = max(10, int(2 * pi * gallery / 0.56))
    for k in range(n_rp):
        a0 = 2 * pi * k / n_rp
        rr = gallery - 0.17
        tilt = rng.uniform(-0.035, 0.035)
        _box(bm, S_IRON, size=(0.055, 0.055, rail_h),
             loc=(cos(a0) * rr, sin(a0) * rr, 0.22),
             rot=(tilt, tilt, a0), base=True)
    for zr in (rail_h * 0.54, rail_h * 0.97):
        n_rs = max(18, int(2 * pi * gallery / 0.28))
        for k in range(n_rs):
            a0 = 2 * pi * k / n_rs
            rr = gallery - 0.17
            _box(bm, S_IRON,
                 size=(2 * pi * rr / n_rs * 1.04, 0.042, 0.048),
                 loc=(cos(a0) * rr, sin(a0) * rr, 0.22 + zr),
                 rot=(0, 0, a0 + pi * 0.5))

    # Stone sill ring the lamp room stands on
    n_s = max(10, int(2 * pi * radius / 0.46))
    for k in range(n_s):
        a0 = 2 * pi * k / n_s
        _box(bm, rng.choice([S_A, S_B]),
             size=(2 * pi * radius / n_s * 0.92, 0.32, 0.22),
             loc=(cos(a0) * radius, sin(a0) * radius, 0.22),
             rot=(0, 0, a0 + pi * 0.5), base=True)

    # Mullions and glazed bays
    zb = 0.44
    for k in range(posts):
        a0 = 2 * pi * k / posts
        _box(bm, S_IRON, size=(0.085, 0.115, height),
             loc=(cos(a0) * radius, sin(a0) * radius, zb),
             rot=(0, 0, a0 + pi * 0.5), base=True)
    for k in range(posts):
        a0 = 2 * pi * (k + 0.5) / posts
        bw = 2.0 * radius * sin(pi / posts) * 0.94
        _box(bm, S_GLASS, size=(bw, 0.05, height * 0.88),
             loc=(cos(a0) * radius, sin(a0) * radius, zb + 0.04),
             rot=(0, 0, a0 + pi * 0.5), base=True)
        _box(bm, S_IRON, size=(bw, 0.07, 0.05),
             loc=(cos(a0) * radius, sin(a0) * radius,
                  zb + height * rng.uniform(0.42, 0.52)),
             rot=(0, 0, a0 + pi * 0.5))

    # The light: burner pan, a reflector built plate by plate, and the flame
    zf = zb + height * 0.40
    _cyl(bm, S_IRON, radius * 0.60, 0.11, (0, 0, zb + 0.16), segments=12)
    for k in range(7):
        a0 = pi * 0.30 + k * 0.29
        _box(bm, S_IRON, size=(0.26, 0.045, 0.66),
             loc=(cos(a0) * radius * 0.54, sin(a0) * radius * 0.54, zf),
             rot=(0, 0, a0 + pi * 0.5))
    _blob(bm, S_FLAME, (0, 0, zf),
          (radius * 0.24, radius * 0.24, radius * 0.40), subdiv=1)

    # Roof plate the cone lands on
    _cyl(bm, S_TIMBER, radius + 0.13, 0.12, (0, 0, zb + height + 0.06),
         segments=14)

    # Salt and lichen on the shaded flanks (-X / +Y), never all the way round
    for _ in range(max(8, n_cb // 2)):
        a0 = rng.uniform(pi * 0.40, pi * 1.40)
        _lichen_patch(bm, S_LICHEN,
                      (cos(a0) * (gallery - 0.03), sin(a0) * (gallery - 0.03),
                       rng.uniform(-0.44, 0.16)),
                      rng.uniform(0.06, 0.13), 2, rng, plates=2)
    for _ in range(6):
        a0 = rng.uniform(pi * 0.45, pi * 1.35)
        _moss_clump(bm, S_MOSS,
                    (cos(a0) * (gallery - 0.10), sin(a0) * (gallery - 0.10),
                     0.17), rng.uniform(0.05, 0.10), rng, squash=0.5)

    return _end(obj, mesh, bm, bevel=0.010, segments=2)
