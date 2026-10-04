"""The city kit's detail layer (2026-09-30, the user's asset sheets in
ref/city_direction_2026-09-30/: "add more detail to the assets like in the
sheet"). A new module: `kit.py`'s primitives are shared with the village kit
and stay as they are; `citykit.house(rich=True)` calls in here.

What the sheet's houses have that the blockout lacked, each sized to read at
the kit render (760 px) and at the 8 deg game camera:
- roofs: tile courses (a lip every 0.36 m, so the slope and the verge read
  stepped), ridge caps, moss patches, dormers on the street slope
- stone: quoins at the corners, a relieving arch and jamb stones round the
  door, lintels with a keystone over the ground-floor windows
- timber: carved brackets under the jetty, St Andrew's crosses under the
  upper windows
- green: trailing plants under the window boxes, ivy up a corner

None of it casts a shadow: the SHADOW_ proxy stays the house's boxes, so the
cascades (the city's known GPU cost) do not grow with detail.
"""
import math
import random

from mathutils import Matrix, Vector

import kit as K

Z = Vector((0, 0, 1))
# a worn or replaced tile shows a neighbouring roof's colour
WORN = {"clay_tile": "shingle", "slate_blue": "slate", "slate": "slate_blue", "shingle": "clay_tile"}


def _m(basis, p):
    m = basis.to_4x4()
    m.translation = p
    return m


# ---------------------------------------------------------------------------
# roofs
# ---------------------------------------------------------------------------

def roof_dress(me, x0, x1, y0, y1, z_eave, pitch, cover, ridge_axis="x", rnd=None, dormers=(),
               dormer_mat="plaster", over_eave=0.60, over_gable=0.45, thick=0.18, step=0.36, moss=4):
    """Dress a `K.roof` built with the same arguments: tile courses on both
    slopes, ridge caps, moss, and dormers at (a along the ridge, slope side),
    side -1 the -b slope. Same frame trick as `K.roof` for a ridge along y
    (local a = world y, local b = -world x: side +1 is the -x slope)."""
    rnd = rnd or random.Random(7)
    if ridge_axis == "y":
        keep = me.xf
        me.xf = keep @ Matrix.Rotation(math.radians(90), 4, "Z")
        roof_dress(me, y0, y1, -x1, -x0, z_eave, pitch, cover, "x", rnd, dormers, dormer_mat,
                   over_eave, over_gable, thick, step, moss)
        me.xf = keep
        return
    a0, a1 = x0 - over_gable, x1 + over_gable
    half = (y1 - y0) / 2
    mid_b = (y0 + y1) / 2
    p = math.radians(pitch)
    ridge_z = z_eave + half * math.tan(p)
    slope = (half + over_eave) / math.cos(p)
    for side in (-1, 1):
        ang = p * side
        dn = Vector((0, side * math.cos(p), -math.sin(p)))
        nrm = Vector((0, side * math.sin(p), math.cos(p)))
        rot = Matrix.Rotation(-ang, 4, "X")

        def top(s, a):
            return Vector((a, mid_b, ridge_z)) + dn * s + nrm * thick
        # courses of individual tiles, staggered, each a little lifted or rolled,
        # and a few worn ones in a neighbouring colour (2026-09-30, the user's
        # brief: "individually readable uneven roof tiles")
        s, k = slope - 0.04, 0
        while s > 0.3:
            a = a0 + (0.2 if k % 2 else 0.0)
            while a < a1 - 0.08:
                ln = min(rnd.uniform(0.35, 0.8), a1 - a)
                lift = rnd.uniform(0.0, 0.035)
                mat = WORN.get(cover, cover) if rnd.random() < 0.07 else cover
                me.box(Matrix.Translation(top(s, a + ln / 2) + nrm * (0.025 + lift / 2)) @ rot
                       @ Matrix.Rotation(rnd.uniform(-0.04, 0.04), 4, "Y"), (ln - 0.045, 0.1, 0.065 + lift), mat)
                a += ln
            s -= step
            k += 1
        # moss where the rain runs off: small cushions in clusters on the lower
        # slope and along the eave (a flat patch read as a green sticker)
        for _ in range(moss):
            s0 = rnd.uniform(slope * 0.5, slope - 0.25)
            a_ = rnd.uniform(a0 + 0.6, a1 - 0.6)
            for _ in range(rnd.randint(4, 7)):
                s = min(slope - 0.1, s0 + rnd.uniform(-0.35, 0.35))
                a = a_ + rnd.uniform(-0.5, 0.5)
                z = rnd.uniform(0.04, 0.09)
                me.box(Matrix.Translation(top(s, a) + nrm * (0.05 + z / 2)) @ rot
                       @ Matrix.Rotation(rnd.uniform(0, math.pi), 4, "Z"),
                       (rnd.uniform(0.14, 0.34), rnd.uniform(0.12, 0.28), z), "moss")
    # ridge caps: a row of tiles set diamond-wise over the ridge beam
    n = max(2, int((a1 - a0 - 0.3) / 0.42))
    for i in range(n + 1):
        a = a0 + 0.15 + i * (a1 - a0 - 0.3) / n
        me.box(Matrix.Translation((a, mid_b, ridge_z + thick + 0.14)) @ Matrix.Rotation(math.radians(45), 4, "X"),
               (0.38, 0.24, 0.24), cover)
    for a, side in dormers:
        dormer(me, a, side, mid_b, ridge_z, p, slope, thick, cover, dormer_mat)


def dormer(me, a, side, mid_b, ridge_z, p, slope, thick, cover, mat, w=1.3, h=1.15):
    """A gabled dormer at `a` along the ridge on the `side` slope (-1: -b): a
    box let into the roof, a lit window with frame and sill, its own little
    gable roof. Deep enough that its ridge dies into the main roof."""
    o = side                                              # outward along b, toward the eave
    hw = w / 2 + 0.15
    rise = hw
    d = max(1.7, (h + rise + 0.25) / math.tan(p))
    s_f = slope * 0.58                                    # its front, down the slope from the ridge
    b_f = mid_b + o * s_f * math.cos(p)
    z_s = ridge_z - s_f * math.sin(p) + thick / math.cos(p)
    z0, z1 = z_s - 0.35, z_s + h
    me.box(Matrix.Translation((a, b_f - o * d / 2, (z0 + z1) / 2)), (w, d, z1 - z0), mat)
    zc = z_s + h * 0.5
    me.box(Matrix.Translation((a, b_f + o * 0.01, zc)), (w * 0.5, 0.04, h * 0.62), "M_Window_Dim")
    for dx in (-1, 1):
        K.beam(me, (a + dx * w * 0.27, b_f + o * 0.04, zc - h * 0.33), (a + dx * w * 0.27, b_f + o * 0.04, zc + h * 0.33), 0.08, 0.08)
    K.beam(me, (a - w * 0.3, b_f + o * 0.04, zc + h * 0.34), (a + w * 0.3, b_f + o * 0.04, zc + h * 0.34), 0.09, 0.08)
    K.beam(me, (a, b_f + o * 0.03, zc - h * 0.3), (a, b_f + o * 0.03, zc + h * 0.3), 0.04, 0.03, mat="iron")
    me.box(Matrix.Translation((a, b_f + o * 0.08, zc - h * 0.34)), (w * 0.62, 0.16, 0.07), "planks")
    # its roof: two slabs at 45 deg, the ridge running back into the main roof
    for sa in (-1, 1):
        c = Vector((a + sa * hw / 2, b_f - o * (d / 2 - 0.12), z1 + rise / 2 + 0.04))
        me.box(Matrix.Translation(c) @ Matrix.Rotation(math.radians(45 * sa), 4, "Y"),
               (hw / math.cos(math.radians(45)), d + 0.24, 0.08), "planks", faces={"+z": cover})
    me.prism(Vector((a + o * w / 2, b_f, z1)), Vector((-o, 0, 0)), Z, [(0, 0), (w, 0), (w / 2, rise - 0.08)], 0.1, mat)
    for sa in (-1, 1):
        K.beam(me, (a + sa * hw, b_f + o * 0.14, z1 - 0.02), (a, b_f + o * 0.14, z1 + rise), 0.18, 0.06, up=(0, 1, 0))


# ---------------------------------------------------------------------------
# stone
# ---------------------------------------------------------------------------

def quoins(me, x0, x1, y0, y1, z0, z1, mat="ashlar", course=0.34, proud=0.04):
    """Dressed corner stones, long and short in turn, standing proud of both
    faces at all four corners of a storey."""
    for cx, sx in ((x0, 1), (x1, -1)):
        for cy, sy in ((y0, 1), (y1, -1)):
            k, z = 0, z0
            while z + course * 0.6 < z1:
                lx, ly = (0.62, 0.34) if k % 2 == 0 else (0.34, 0.62)
                hz = min(course, z1 - z) - 0.03
                me.box(Matrix.Translation((cx + sx * (lx / 2 - proud), cy + sy * (ly / 2 - proud), z + hz / 2 + 0.015)),
                       (lx, ly, hz), mat)
                z += course
                k += 1


def surrounds(me, x0, y0, z, openings, mat="ashlar", awning=("cloth_blue", "cloth_cream"), stone=True):
    """Stone round the front's ground-floor openings (front wall along +x from
    (x0, y0), out = -y): a relieving arch and jamb stones for a door, a
    lintel with a keystone over a window."""
    yf = y0 - 0.03
    for u0, u1, v0, v1, kind in openings:
        cx, w = x0 + (u0 + u1) / 2, u1 - u0
        # two doors in three painted (2026-09-30): a leaf over the planks, two iron straps; the
        # colour by a hash of the door's place, so no rng stream moves
        hh = (math.sin(x0 * 12.9898 + cx * 78.233 + y0 * 3.7) * 43758.5453) % 1.0
        if kind == "door" and hh < 0.66:
            me.box(K.T(cx, yf - 0.02, z + (v0 + v1) / 2 - 0.02), (w - 0.1, 0.03, v1 - v0 - 0.08), PAINT[int(hh * 60) % len(PAINT)])
            for dz in (0.3, v1 - v0 - 0.45):
                me.box(K.T(cx, yf - 0.045, z + v0 + dz), (w - 0.16, 0.02, 0.06), "iron")
        if kind == "door" and stone:
            r = w / 2 + 0.16
            n = 9
            for i in range(n):
                t = math.pi * (i + 0.5) / n
                me.box(K.T(cx + r * math.cos(t), yf, z + v1 + 0.05 + r * 0.55 * math.sin(t), ry=math.degrees(math.pi / 2 - t)),
                       (0.2 if i != n // 2 else 0.26, 0.12, 0.34), mat)
            k, zz = 0, z + v0
            while zz < z + v1 - 0.2:
                ext = 0.4 if k % 2 == 0 else 0.26
                for side, ue in ((-1, u0), (1, u1)):
                    me.box(K.T(x0 + ue + side * (ext / 2 - 0.02), yf, zz + 0.16), (ext, 0.12, 0.3), mat)
                zz += 0.34
                k += 1
        elif kind == "window_bare":                         # a shop window: a striped cloth awning
            cloth_awning(me, Vector((x0, y0, 0)), (1, 0, 0), u0, u1, z + v1 + 0.5, awning)
        elif kind.startswith("window") and w <= 1.4 and stone:
            me.box(K.T(cx, yf - 0.01, z + v1 + 0.12), (w + 0.34, 0.12, 0.22), mat)
            me.box(K.T(cx, yf - 0.03, z + v1 + 0.16), (0.2, 0.14, 0.32), mat)


# ---------------------------------------------------------------------------
# timber
# ---------------------------------------------------------------------------

def jetty_brackets(me, x0, x1, y_wall, z_floor, jet, every=1.2):
    """Carved brackets under a jetty: a brace from the wall below up to the
    overhanging joist, with a rounded boss at its foot."""
    n = max(2, int((x1 - x0 - 0.4) / every))
    for i in range(n + 1):
        x = x0 + 0.2 + i * (x1 - x0 - 0.4) / n
        K.beam(me, (x, y_wall - 0.05, z_floor - 0.85), (x, y_wall - jet * 0.85, z_floor - 0.2), 0.13, 0.11, up=(1, 0, 0))
        me.box(K.T(x, y_wall - 0.08, z_floor - 0.9), (0.18, 0.12, 0.16), "timber")


def sill_crosses(me, o, along, ops, z0, sill, length=None, z1=None):
    """St Andrew's crosses in the panel under each window of a framed wall;
    with `length` and `z1`, knee braces in the top corners and the plate's
    end standing past the corner (the joints read)."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    fo = Vector(o) + out * K.PROUD - out * (K.BEAM / 2)
    if length is not None and z1 is not None:
        for u, d in ((K.BEAM, 1), (length - K.BEAM, -1)):
            K.beam(me, fo + along * u + Z * (z1 - 0.75), fo + along * (u + d * 0.55) + Z * (z1 - K.BEAM), 0.12, 0.11, up=out)
            for q in (fo + along * u + Z * (z1 - 0.72), fo + along * (u + d * 0.5) + Z * (z1 - K.BEAM)):
                me.box(_m(Matrix((along, -out, Z)).transposed(), q + out * 0.07), (0.05, 0.03, 0.05), "planks")
        K.beam(me, fo - along * 0.16 + Z * (z1 - K.BEAM / 2), fo + along * 0.05 + Z * (z1 - K.BEAM / 2), 0.2, 0.2)
    for u0, u1, v0, v1, kind in ops:
        if not kind.startswith("window") or u1 - u0 > 1.4:
            continue
        lo, hi = z0 + 0.12, z0 + v0 - 0.06
        if hi - lo < 0.3:
            continue
        for a, b in (((u0, lo), (u1, hi)), ((u0, hi), (u1, lo))):
            K.beam(me, fo + along * a[0] + Z * a[1], fo + along * b[0] + Z * b[1], 0.11, 0.1, up=out)


# ---------------------------------------------------------------------------
# green
# ---------------------------------------------------------------------------

def trailing(me, c, along, w, rnd):
    """Plants trailing over the front of a window box centred at `c`."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    for _ in range(rnd.randint(3, 5)):
        u = rnd.uniform(-w / 2 + 0.1, w / 2 - 0.1)
        ln = rnd.uniform(0.25, 0.6)
        me.box(_m(basis, c + along * u + out * 0.12 + Z * (0.05 - ln / 2)), (0.09, 0.05, ln), "moss")
        me.box(_m(basis, c + along * u + out * 0.14 + Z * (0.02 - ln)) @ Matrix.Rotation(math.radians(45), 4, "Y"),
               (0.15, 0.08, 0.15), "moss")


def ivy(me, rnd, base, along, height, spread=0.9, clumps=None):
    """Ivy climbing a wall from `base` (a point on the outer face): leaf
    clumps on a wandering stem that fans out as it rises."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    n = clumps or int(height / 0.14)
    u = 0.0
    for i in range(n):
        f = i / max(n - 1, 1)
        u = max(-spread, min(spread, u + rnd.uniform(-0.18, 0.18)))
        zz = f * height
        for _ in range(1 + int(f * 2)):
            du = u + rnd.uniform(-0.35, 0.35) * (0.4 + f)
            s = rnd.uniform(0.18, 0.34)
            me.box(_m(basis, Vector(base) + along * du + out * 0.05 + Z * zz)
                   @ Matrix.Rotation(rnd.uniform(0, math.pi), 4, "Y"), (s, 0.07, s * 0.8), "moss")


# ---------------------------------------------------------------------------
# chimneys, footings, balconies, awnings, pots (2026-09-30, the user's brief:
# "varied chimneys ... stone foundation blocks ... balconies and awnings ...
# flower boxes and small gardens")
# ---------------------------------------------------------------------------

def chimney_extra(me, rnd, x, y, z_top, w=0.8):
    """Vary a `K.chimney`: stone bands round the stack, a third pot in
    terracotta at its own height, moss on the cap."""
    for zb in (z_top - 0.95, z_top - 0.4)[: rnd.randint(1, 2)]:
        me.box(K.T(x, y, zb), (w + 0.08, w + 0.08, 0.1), "ashlar")
    h = 0.3 + rnd.uniform(0.0, 0.14)
    me.box(K.T(x + rnd.choice((-0.2, 0.2)), y + 0.2, z_top + 0.11 + h / 2), (0.16, 0.16, h), "clay_tile")
    me.box(K.T(x - 0.2, y - 0.25, z_top + 0.13, rz=rnd.uniform(0, 90)), (0.2, 0.14, 0.06), "moss")


def foundation(me, rnd, x0, x1, y0, y1, skip=(), grow=0.16):
    """Big stones round the plinth: lengths 0.45-1.0 m, their tops uneven,
    each a little proud. `skip` holds x spans on the front (-y) to leave clear
    (door steps)."""
    sides = (((x0 - grow, y0 - grow), (1, 0), x1 - x0 + 2 * grow), ((x1 + grow, y0 - grow), (0, 1), y1 - y0 + 2 * grow),
             ((x1 + grow, y1 + grow), (-1, 0), x1 - x0 + 2 * grow), ((x0 - grow, y1 + grow), (0, -1), y1 - y0 + 2 * grow))
    for i, ((ox, oy), (ax, ay), L) in enumerate(sides):
        along = Vector((ax, ay, 0))
        out = along.cross(Z).normalized()
        basis = Matrix((along, -out, Z)).transposed()
        u = 0.0
        while u < L - 0.1:
            ln = min(rnd.uniform(0.45, 1.0), L - u)
            x = ox + ax * (u + ln / 2)
            if i == 0 and any(a - 0.3 < x < b + 0.3 for a, b in skip):
                u += ln
                continue
            h = rnd.uniform(0.5, 0.64)
            c = Vector((ox, oy, 0)) + along * (u + ln / 2) + out * rnd.uniform(0.02, 0.06) + Z * (h / 2 - 0.12)
            me.box(_m(basis, c), (ln - 0.04, 0.2, h), "ashlar" if rnd.random() < 0.2 else "fieldstone")
            if rnd.random() < 0.25:
                me.box(_m(basis, c + Z * (h / 2 + 0.02) - out * 0.02), (rnd.uniform(0.15, 0.35), 0.14, 0.05), "moss")
            u += ln


def balcony(me, o, along, u0, u1, z, depth=0.8, rnd=None):
    """A timber balcony on a wall (outer face from `o` along `along`) at floor
    height `z`: plank floor on brackets, balusters, a rail with a flower box."""
    rnd = rnd or random.Random(3)
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    o = Vector(o)
    mid = o + along * ((u0 + u1) / 2)
    w = u1 - u0
    me.box(_m(basis, mid + out * (depth / 2) + Z * (z + 0.05)), (w, depth, 0.1), "planks", axis=(1, 0, 0))
    for u in (u0 + 0.15, (u0 + u1) / 2, u1 - 0.15):
        p = o + along * u
        K.beam(me, p + Z * (z - 0.7), p + out * (depth - 0.1) + Z * z, 0.1, 0.1, up=along)
    n = max(3, int(w / 0.2))
    for i in range(n + 1):
        p = o + along * (u0 + 0.05 + i * (w - 0.1) / n) + out * (depth - 0.05)
        K.beam(me, p + Z * (z + 0.1), p + Z * (z + 0.9), 0.05, 0.05)
    for u in (u0 + 0.05, u1 - 0.05):
        p = o + along * u
        K.beam(me, p + Z * (z + 0.95), p + out * (depth - 0.05) + Z * (z + 0.95), 0.08, 0.08)
    K.beam(me, o + along * u0 + out * (depth - 0.05) + Z * (z + 0.95), o + along * u1 + out * (depth - 0.05) + Z * (z + 0.95),
           0.09, 0.08)
    c = mid + out * (depth + 0.1) + Z * (z + 0.82)
    K.window_box(me, c, along, min(w - 0.3, 1.4), rnd)
    trailing(me, c, along, min(w - 0.3, 1.4), rnd)


def cloth_awning(me, o, along, u0, u1, z, cols=("cloth_blue", "cloth_cream"), depth=1.2, drop=0.45):
    """A striped cloth awning over (u0, u1) of a wall at height `z`: the
    canopy in alternating stripes, a scalloped valance, two iron stays."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    o = Vector(o)
    w = u1 - u0 + 0.3
    n = max(4, int(w / 0.34))
    sw = w / n
    ang = math.atan2(drop, depth)
    ln = math.hypot(drop, depth)
    basis = Matrix((along, -out, Z)).transposed().to_4x4() @ Matrix.Rotation(ang, 4, "X")
    for i in range(n):
        u = u0 - 0.15 + (i + 0.5) * sw
        m = basis.copy()
        m.translation = o + along * u + out * (depth / 2) + Z * (z - drop / 2)
        me.box(m, (sw + 0.005, ln, 0.04), cols[i % 2])
        tip = o + along * u + out * (depth + 0.01) + Z * (z - drop - 0.01)
        me.prism(tip - along * (sw / 2), along, Z, [(0, 0), (sw, 0), (sw / 2, -0.22)], 0.03, cols[i % 2])
    for u in (u0 - 0.1, u1 + 0.1):
        K.beam(me, o + along * u + Z * (z - drop - 0.7), o + along * u + out * (depth - 0.05) + Z * (z - drop), 0.04, 0.04,
               mat="iron")


def pots(me, rnd, pts):
    """Terracotta pots with a bloom cluster each, at `pts` (x, y, z)."""
    for x, y, z in pts:
        s = rnd.uniform(0.28, 0.42)
        me.box(K.T(x, y, z + s / 2, rz=rnd.uniform(0, 90)), (s, s, s), "clay_tile")
        me.box(K.T(x, y, z + s + 0.08, rz=rnd.uniform(0, 90)), (s * 1.1, s * 1.1, 0.18), "moss")
        for _ in range(3):
            me.box(K.T(x + rnd.uniform(-s / 3, s / 3), y + rnd.uniform(-s / 3, s / 3), z + s + 0.2, rz=45),
                   (0.1, 0.1, 0.08), rnd.choice(("cloth_red", "crops", "cloth_blue", "cloth_cream")))


def flower_strip(me, rnd, a, b, w=0.5):
    """A narrow planted bed from a to b (points on the ground): a plank
    kerb, soil, green clumps and blooms."""
    a, b = Vector(a), Vector(b)
    along = (b - a).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    L = (b - a).length
    mid = (a + b) / 2
    me.box(_m(basis, mid + Z * 0.08), (L, w, 0.16), "planks", axis=(1, 0, 0))
    me.box(_m(basis, mid + Z * 0.17), (L - 0.08, w - 0.08, 0.04), "moss")
    for i in range(int(L / 0.22)):
        p = a + along * (0.12 + i * 0.22) + out * rnd.uniform(-w / 4, w / 4)
        me.box(_m(basis, p + Z * 0.26) @ Matrix.Rotation(rnd.uniform(0, 1.5), 4, "Z"), (0.2, 0.18, 0.16), "moss")
        if rnd.random() < 0.6:
            me.box(_m(basis, p + Z * 0.36), (0.09, 0.09, 0.08), rnd.choice(("cloth_red", "crops", "cloth_cream", "cloth_blue")))


# ---------------------------------------------------------------------------
# the final polish (2026-09-30, the user: "missing secondary details ... varied
# shutters/windows ... lantern brackets ... small gardens ... subtle material and
# weathering variation ... make the tavern noticeably more distinctive")
# ---------------------------------------------------------------------------

# flat paints (2026-09-30, "city life" plan, item 4): the cloths were striped fabric on a
# shutter, and warm; the views measured 98-99.8 % warm pixels
PAINT = ("paint_teal", "paint_green", "paint_blue", "paint_oxblood", "paint_teal", "paint_green")


def window_dress(me, rnd, o, along, ops, z0):
    """Vary the windows of one wall: some shutters painted (a panel and two
    battens over the kit's plank shutters), some windows under a little
    shingled hood on brackets, the rest left bare wood."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    for u0, u1, v0, v1, kind in ops:
        w = u1 - u0
        if not kind.startswith("window") or w > 1.4:
            continue
        mid = Vector(o) + along * ((u0 + u1) / 2)
        h = v1 - v0
        r = rnd.random()
        if r < 0.55:
            paint = rnd.choice(PAINT)
            for side in (-1, 1):
                c = mid + along * (side * (w / 2 + w / 4 + 0.04)) + Z * (z0 + (v0 + v1) / 2)
                me.box(_m(basis, c + out * 0.065), (w / 2 - 0.05, 0.02, h - 0.12), paint)
                for dz in (-h * 0.3, h * 0.3):
                    me.box(_m(basis, c + out * 0.085 + Z * dz), (w / 2 - 0.02, 0.025, 0.07), "planks")
        elif r < 0.75:
            m = basis.to_4x4() @ Matrix.Rotation(math.radians(-32), 4, "X")
            m.translation = mid + Z * (z0 + v1 + 0.2) + out * 0.24
            me.box(m, (w + 0.36, 0.5, 0.05), "planks", faces={"+z": "shingle"})
            for side in (-1, 1):
                p = mid + along * (side * (w / 2 + 0.1))
                K.beam(me, p + Z * (z0 + v1 - 0.05) + out * 0.02, p + Z * (z0 + v1 + 0.12) + out * 0.4, 0.06, 0.06)


def wall_patches(me, rnd, o, along, L, z0, z1, ops, n=7):
    """Repaired stones: a few dressed blocks proud of a rubble wall, kept clear
    of the openings -- the wall has been mended, not built yesterday."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    for _ in range(n * 3):
        if n <= 0:
            break
        u, v = rnd.uniform(0.7, L - 0.7), rnd.uniform(0.15, z1 - z0 - 0.3)
        if any(a - 0.35 < u < b + 0.35 and c - 0.3 < v < d + 0.3 for a, b, c, d, _k in ops):
            continue
        me.box(_m(basis, Vector(o) + along * u + Z * (z0 + v) + out * 0.02),
               (rnd.uniform(0.3, 0.55), 0.06, rnd.uniform(0.2, 0.3)), rnd.choice(("ashlar", "ashlar", "limestone")))
        n -= 1


def picket(me, a, b, h=0.55, gap=0.19):
    """A low picket fence from a to b round a bed: posts and two rails."""
    a, b = Vector(a), Vector(b)
    along = (b - a).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    L = (b - a).length
    for i in range(int(L / gap) + 1):
        me.box(_m(basis, a + along * (i * gap) + Z * (h / 2)), (0.05, 0.03, h), "planks")
    for zz in (h * 0.3, h * 0.78):
        me.box(_m(basis, (a + b) / 2 + Z * zz - out * 0.03), (L, 0.03, 0.05), "planks", axis=(1, 0, 0))


def hanging_lantern(me, p, drop=0.45):
    """A lantern hung on a short chain below point `p` (under a beam)."""
    p = Vector(p)
    me.box(K.T(p.x, p.y, p.z - drop / 2), (0.03, 0.03, drop), "iron")
    c = p - Z * (drop + 0.2)
    me.box(K.T(c.x, c.y, c.z + 0.22), (0.26, 0.26, 0.05), "iron")
    me.box(K.T(c.x, c.y, c.z), (0.18, 0.18, 0.34), "M_Lamp")
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        me.box(K.T(c.x + dx * 0.1, c.y + dy * 0.1, c.z), (0.03, 0.03, 0.38), "iron")
    me.box(K.T(c.x, c.y, c.z - 0.19), (0.22, 0.22, 0.04), "iron")


def grand_sign(me, p, out_dir, reach=1.7, board=(1.3, 0.9), emblem="tankard"):
    """A tavern's hanging sign: an iron arm with a strut and a scroll, a
    framed board on two chains, and a carved emblem on both faces. `p` is the
    arm's root on the wall; the board hangs in the plane of the arm."""
    p, o = Vector(p), Vector(out_dir).normalized()
    side = o.cross(Z).normalized()
    K.beam(me, p, p + o * reach, 0.08, 0.08, mat="iron")
    K.beam(me, p - Z * 0.8, p + o * (reach * 0.6), 0.06, 0.06, mat="iron")
    for k in range(5):                                   # the scroll over the arm
        t = k / 4 * math.pi
        q = p + o * (0.35 + 0.22 * math.cos(t)) + Z * (0.18 + 0.2 * math.sin(t))
        me.box(K.T(q.x, q.y, q.z), (0.05, 0.05, 0.05), "iron")
    bw, bh = board
    top = p + o * (reach - bw / 2 - 0.1) - Z * 0.35
    basis = Matrix((o, side, Z)).transposed()
    for d in (-1, 1):
        me.box(_m(basis, top + o * (d * bw * 0.4) + Z * 0.17), (0.03, 0.03, 0.34), "iron")
    c = top - Z * (bh / 2)
    me.box(_m(basis, c), (bw, 0.07, bh), "planks")
    for dz in (-1, 1):
        me.box(_m(basis, c + Z * (dz * (bh / 2 - 0.03))), (bw + 0.06, 0.1, 0.07), "timber")
    for dx in (-1, 1):
        me.box(_m(basis, c + o * (dx * (bw / 2 - 0.03))), (0.07, 0.1, bh + 0.06), "timber")
    for s in (-1, 1):                                     # a painted panel on both faces
        me.box(_m(basis, c + side * (s * 0.04)), (bw - 0.16, 0.02, bh - 0.16), "cloth_blue")
    hanging_lantern(me, p + o * (reach - 0.02), drop=0.2)   # lit at dusk: the sign reads from afar
    for s in (-1, 1):                                     # the other trades' emblems (2026-09-30)
        f = c + side * (s * 0.06)
        if emblem == "key":
            for dx, dz, w, h in ((-0.3, 0.0, 0.08, 0.3), (-0.12, 0.0, 0.08, 0.3), (-0.21, 0.14, 0.26, 0.07), (-0.21, -0.14, 0.26, 0.07),
                                 (0.1, 0.0, 0.46, 0.07), (0.28, -0.1, 0.07, 0.18), (0.18, -0.1, 0.07, 0.14)):
                me.box(_m(basis, f + o * dx + Z * dz), (w, 0.04, h), "crops")
        elif emblem == "mortar":
            me.box(_m(basis, f + Z * -0.15), (0.44, 0.04, 0.2), "crops")
            me.box(_m(basis, f + Z * -0.27), (0.26, 0.04, 0.06), "crops")
            me.box(_m(basis, f + o * 0.08 + Z * 0.08) @ Matrix.Rotation(math.radians(30), 4, "Y"), (0.07, 0.045, 0.44), "cloth_cream")
        elif emblem == "book":
            for d, rot in ((-1, 12), (1, -12)):
                me.box(_m(basis, f + o * (d * 0.17)) @ Matrix.Rotation(math.radians(rot), 4, "Y"), (0.32, 0.04, 0.4), "cloth_cream")
            me.box(_m(basis, f + Z * -0.21), (0.7, 0.045, 0.05), "cloth_red")
        elif emblem == "anchor":
            me.box(_m(basis, f), (0.06, 0.04, 0.6), "crops")
            me.box(_m(basis, f + Z * 0.18), (0.36, 0.04, 0.06), "crops")
            for d in (-1, 1):
                me.box(_m(basis, f + o * (d * 0.16) + Z * -0.24) @ Matrix.Rotation(math.radians(d * 40), 4, "Y"), (0.3, 0.04, 0.06), "crops")
        elif emblem == "wheat":
            for d in (-1, 0, 1):
                me.box(_m(basis, f + o * (d * 0.12) + Z * -0.08) @ Matrix.Rotation(math.radians(d * 12), 4, "Y"), (0.03, 0.04, 0.5), "crops")
                me.box(_m(basis, f + o * (d * 0.16) + Z * 0.2), (0.08, 0.045, 0.2), "crops")
    if emblem == "tankard":
        for s in (-1, 1):
            f = c + side * (s * 0.06)
            me.box(_m(basis, f + Z * -0.04), (0.34, 0.04, 0.42), "crops")          # the mug
            me.box(_m(basis, f + o * 0.24 + Z * -0.02), (0.12, 0.04, 0.26), "crops")  # its handle
            me.box(_m(basis, f + Z * 0.21), (0.4, 0.045, 0.1), "cloth_cream")        # the foam


def table_set(me, c, along, rnd):
    """A trestle table and two benches set out on the street, tankards on top."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    c = Vector(c)
    me.box(_m(basis, c + Z * 0.74), (1.5, 0.7, 0.06), "planks", axis=(1, 0, 0))
    for d in (-1, 1):
        me.box(_m(basis, c + along * (d * 0.6) + Z * 0.36), (0.08, 0.55, 0.72), "timber")
    for s in (-1, 1):
        b = c + out * (s * 0.62)
        me.box(_m(basis, b + Z * 0.44), (1.5, 0.28, 0.05), "planks", axis=(1, 0, 0))
        for d in (-1, 1):
            me.box(_m(basis, b + along * (d * 0.6) + Z * 0.21), (0.07, 0.22, 0.42), "timber")
    for i in range(3):
        me.box(_m(basis, c + along * rnd.uniform(-0.6, 0.6) + out * rnd.uniform(-0.2, 0.2) + Z * 0.85),
               (0.1, 0.1, 0.16), rnd.choice(("clay_tile", "crops", "planks")))


# ---------------------------------------------------------------------------
# the rollout to the whole kit (2026-09-30, "go"): cone roofs and big stone faces
# ---------------------------------------------------------------------------

def cone_courses(me, cx, cy, z0, r, h, n, rot, mat, step=0.42, rnd=None):
    """Tile courses on a `pyramid` cone: a lip along every edge of rings
    climbing to the apex, a few worn tiles. Towers and turrets read tiled like
    the gable roofs."""
    rnd = rnd or random.Random(int(r * 100 + h * 10 + n))
    apex = Vector((cx, cy, z0 + h))
    slant = math.hypot(h, r)
    t = 0.04
    while t < 0.88:
        ring = [Vector((cx + r * (1 - t) * math.cos(math.radians(rot) + k * math.tau / n),
                        cy + r * (1 - t) * math.sin(math.radians(rot) + k * math.tau / n), z0 + h * t)) for k in range(n)]
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            e = b - a
            if e.length < 0.15:
                continue
            x = e.normalized()
            nrm = x.cross(apex - a).normalized()
            c = (a + b) / 2
            if nrm.dot(c - Vector((cx, cy, c.z))) < 0:
                nrm = -nrm
            y = nrm.cross(x).normalized()
            m = Matrix((x, y, nrm)).transposed().to_4x4()
            m.translation = c + nrm * 0.03
            me.box(m, (e.length * 1.02, 0.1, 0.05), WORN.get(mat, mat) if rnd.random() < 0.07 else mat)
        t += step / slant


def stone_face(me, rnd, o, along, L, z0, z1, course=0.8, blocks=16, streaks=4, ivy_h=0.55):
    """A big masonry face made to read as large blocks, not brick-scale
    texture: bed joints standing proud every `course`, single proud blocks in
    ashlar / limestone / fieldstone, moss streaks down from the top, and an
    ivy curtain climbing from the foot."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    basis = Matrix((along, -out, Z)).transposed()
    o = Vector(o)
    z = z0 + course
    while z < z1 - 0.2:
        u = 0.0
        while u < L - 0.05:
            ln = min(rnd.uniform(1.2, 3.2), L - u)
            me.box(_m(basis, o + along * (u + ln / 2) + Z * z + out * 0.015), (ln - 0.06, 0.04, 0.06), "ashlar")
            u += ln
        z += course
    rows = max(1, int((z1 - z0) / course))
    for _ in range(blocks):
        u = rnd.uniform(0.5, L - 0.5)
        zc = z0 + course * (rnd.randint(0, rows - 1) + 0.5)
        me.box(_m(basis, o + along * u + Z * zc + out * 0.02), (rnd.uniform(0.7, 1.5), 0.05, course - 0.12),
               rnd.choice(("ashlar", "limestone", "fieldstone")))
    for _ in range(streaks):
        u = rnd.uniform(0.3, L - 0.3)
        ln = rnd.uniform(0.6, 2.2)
        me.box(_m(basis, o + along * u + Z * (z1 - ln / 2) + out * 0.025), (rnd.uniform(0.12, 0.3), 0.03, ln), "moss")
    if ivy_h:
        ivy(me, rnd, o + along * rnd.uniform(L * 0.2, L * 0.8) + Z * z0, along, (z1 - z0) * ivy_h, spread=1.3)


def hanging_vine(me, rnd, top, out, length):
    """A vine hanging down a face from `top`: leaf clumps down a swaying stem,
    thinning toward its tip (a flat strip read as a green slab in game)."""
    top, out = Vector(top), Vector(out).normalized()
    side = out.cross(Z).normalized()
    n = max(3, int(length / 0.16))
    u = 0.0
    for i in range(n):
        u += rnd.uniform(-0.06, 0.06)
        p = top - Z * (i * length / n) + side * u + out * 0.05
        sz = rnd.uniform(0.14, 0.24) * (1.0 - 0.45 * i / n)
        me.box(K.T(p.x, p.y, p.z, rz=rnd.uniform(0, 90)), (sz, sz * 0.6, sz * 0.9), "moss")
