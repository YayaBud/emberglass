"""The Emberglass city kit: every building and structure on the master city
plan (implementation_plan.md), built in the kit's look.

New code. It builds on the kit's parts (`scripts/forge/kit/kit.py`: Mesh,
wall, opening, gable, roof, chimney, plinth, beam) so every surface is named
after a `texgen.py` surface, UV'd at 52 texels/m, one material slot per
surface. The old city scripts (`scripts/city/`) are reference only and are
not imported.

Conventions (as the kit): front is -Y, ground z = 0, plinths run to -0.5.
Every building is finished on all four sides -- the city's streets are
radial under a locked camera yaw, so half of them are seen from the back.
Each asset returns (visual Mesh, shadow Mesh); `build_city.py` adds the
collision hull, exports and renders.
"""
import math
import os
import random
import sys

from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "kit"))
import kit as K  # noqa: E402
import detail as DT  # noqa: E402  (2026-09-30: the detail layer, house(rich=True))

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
T = K.T

# Chimney tops of the asset being built. build_city clears it per asset and
# writes it to the manifest ("smoke"), so the game can put smoke on them.
SMOKE = []
# The front wall of each storey house() builds: (storey, floor z, wall y,
# x0, x1). build_city writes it to the manifest ("front") so the game hangs
# balconies and signs ON the wall, jetties included, not on the eave box.
FRONT = []
K.FLAT.update({"water": (0.16, 0.32, 0.42), "foam": (0.85, 0.9, 0.92),
               "royal": (0.10, 0.17, 0.42),   # the king's solid blue (cloth_blue is striped)
               # painted shutters, doors and canopies (2026-09-30, "city life" plan, item 4): the
               # views measured 98-99.8 % warm pixels, the sheet 32-95; flat, so no stripes
               "paint_teal": (0.24, 0.47, 0.50), "paint_green": (0.30, 0.44, 0.27),
               "paint_blue": (0.25, 0.35, 0.58), "paint_oxblood": (0.50, 0.18, 0.15)})
# The detail layer (detail.py) is on for the whole kit since 2026-09-30 ("go"):
# house() defaults to rich, `roof()` and `pyramid()` tile what they build.
RICH = True
STONE = ("fieldstone", "brick", "ashlar")


# ---------------------------------------------------------------------------
# shapes the kit does not have
# ---------------------------------------------------------------------------

def cyl(me, cx, cy, z0, z1, r, mat, n=12, r1=None, top=None, rot=0.0):
    """Vertical n-sided prism, tapering from r to r1."""
    r1 = r if r1 is None else r1
    ang = [math.radians(rot) + k * math.tau / n for k in range(n)]
    lo = [Vector((cx + r * math.cos(a), cy + r * math.sin(a), z0)) for a in ang]
    hi = [Vector((cx + r1 * math.cos(a), cy + r1 * math.sin(a), z1)) for a in ang]
    c = Vector((cx, cy, (z0 + z1) / 2))
    for k in range(n):
        j = (k + 1) % n
        me.face([lo[k], lo[j], hi[j], hi[k]], mat, c)
    me.face(lo, mat, c)
    me.face(hi, top or mat, c)


def rod(me, a, b, r, mat, n=8, r1=None):
    """A round bar from a to b (any direction), capped."""
    a, b = Vector(a), Vector(b)
    t = (b - a).normalized()
    s = t.cross(Z if abs(t.z) < 0.9 else X).normalized()
    u = t.cross(s)
    r1 = r if r1 is None else r1
    ra = [a + (s * math.cos(k * math.tau / n) + u * math.sin(k * math.tau / n)) * r for k in range(n)]
    rb = [b + (s * math.cos(k * math.tau / n) + u * math.sin(k * math.tau / n)) * r1 for k in range(n)]
    c = (a + b) / 2
    for k in range(n):
        j = (k + 1) % n
        me.face([ra[k], ra[j], rb[j], rb[k]], mat, c, axis=t)
    me.face(ra, mat, c)
    me.face(rb, mat, c)


def pyramid(me, cx, cy, z0, r, h, mat, n=4, rot=45.0):
    """Pointed roof / spire / cone: n sides, base radius r, height h."""
    ring = [Vector((cx + r * math.cos(math.radians(rot) + k * math.tau / n),
                    cy + r * math.sin(math.radians(rot) + k * math.tau / n), z0)) for k in range(n)]
    apex = Vector((cx, cy, z0 + h))
    c = Vector((cx, cy, z0 + h * 0.3))
    for k in range(n):
        me.face([ring[k], ring[(k + 1) % n], apex], mat, c)
    me.face(ring, "planks", c)
    if RICH and mat in ("slate", "slate_blue", "shingle", "clay_tile") and h > 1.5 and r > 0.8:
        DT.cone_courses(me, cx, cy, z0, r, h, n, rot, mat)


def roof(me, x0, x1, y0, y1, z_eave, pitch, cover, over_eave=0.60, over_gable=0.45, thick=0.18, ridge_axis="x"):
    """`K.roof`, then (RICH) the detail layer's tiles, ridge caps and moss --
    for the roofs the landmarks build themselves; house() dresses its own."""
    z = K.roof(me, x0, x1, y0, y1, z_eave, pitch, cover, over_eave=over_eave, over_gable=over_gable, thick=thick,
               ridge_axis=ridge_axis)
    if RICH:
        DT.roof_dress(me, x0, x1, y0, y1, z_eave, pitch, cover, ridge_axis=ridge_axis,
                      rnd=random.Random(int((x1 - x0) * 97 + (y1 - y0) * 13 + z_eave * 7)),
                      over_eave=over_eave, over_gable=over_gable, thick=thick, moss=2)
    return z


def hip(me, x0, x1, y0, y1, z, pitch, cover, over=0.4):
    """Hipped roof as one convex solid: fascia band, two slopes, two hips."""
    a0, a1, b0, b1 = x0 - over, x1 + over, y0 - over, y1 + over
    tp = math.tan(math.radians(pitch))
    half = min(a1 - a0, b1 - b0) / 2
    top = z + half * tp
    cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
    if a1 - a0 >= b1 - b0:
        r0, r1 = Vector((a0 + half, cy, top)), Vector((a1 - half, cy, top))
    else:
        r0, r1 = Vector((cx, b0 + half, top)), Vector((cx, b1 - half, top))
    lo = [Vector((a0, b0, z - 0.22)), Vector((a1, b0, z - 0.22)), Vector((a1, b1, z - 0.22)), Vector((a0, b1, z - 0.22))]
    hi = [p + Z * 0.22 for p in lo]
    c = Vector((cx, cy, z))
    for k in range(4):
        j = (k + 1) % 4
        me.face([lo[k], lo[j], hi[j], hi[k]], "timber", c)
    me.face(lo, "planks", c)
    if (r1 - r0).length < 1e-3:
        for k in range(4):
            me.face([hi[k], hi[(k + 1) % 4], r0], cover, c)
    elif a1 - a0 >= b1 - b0:
        me.face([hi[0], hi[1], r1, r0], cover, c)
        me.face([hi[2], hi[3], r0, r1], cover, c)
        me.face([hi[1], hi[2], r1], cover, c)
        me.face([hi[3], hi[0], r0], cover, c)
    else:
        me.face([hi[1], hi[2], r1, r0], cover, c)
        me.face([hi[3], hi[0], r0, r1], cover, c)
        me.face([hi[0], hi[1], r0], cover, c)
        me.face([hi[2], hi[3], r1], cover, c)
    K.beam(me, r0 + Z * 0.08, r1 + Z * 0.08 + (X * 0.01 if (r1 - r0).length < 1e-3 else Vector()), 0.2, 0.2)
    return top


def merlons(me, a, b, z, mat="ashlar", h=0.85, w=0.8, gap=0.6, t=0.5):
    """Crenellations from (x, y) a to b on a parapet top at z."""
    a, b = Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0))
    d = b - a
    L = d.length
    n = max(1, int((L + gap) / (w + gap)))
    step = (L - n * w) / max(n - 1, 1) + w if n > 1 else 0
    rz = math.degrees(math.atan2(d.y, d.x))
    for k in range(n):
        p = a + d.normalized() * (w / 2 + k * step if n > 1 else L / 2)
        me.box(T(p.x, p.y, z + h / 2, rz=rz), (w, t, h), mat)


def merlon_ring(me, cx, cy, r, z, n, mat="ashlar", h=0.8, w=0.8):
    for k in range(n):
        a = k * 360.0 / n
        me.box(T(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)), z + h / 2, rz=a),
               (0.45, w, h), mat)


def slit(me, x, y, z, rz, h=1.0):
    """An arrow slit on a face whose outward normal is at `rz` degrees."""
    me.box(T(x, y, z, rz=rz), (0.08, 0.16, h), "glass")
    me.box(T(x, y, z + h / 2 + 0.08, rz=rz), (0.1, 0.4, 0.14), "ashlar")


def slits_ring(me, cx, cy, r, z, n, off=0.0):
    for k in range(n):
        a = off + k * 360.0 / n
        slit(me, cx + (r + 0.02) * math.cos(math.radians(a)), cy + (r + 0.02) * math.sin(math.radians(a)), z, a)


def lancet(me, o, along, u0, u1, z0, z1, wall_mat, glass="stained_glass"):
    """Fill a wall hole (kind 'hole') with a pointed-arch window: recessed
    glass, the arch's shoulders in the wall stone, a sill."""
    along = Vector(along).normalized()
    out = along.cross(Z).normalized()
    w = u1 - u0
    mid = o + along * ((u0 + u1) / 2)
    basis = K.Matrix((along, -out, Z)).transposed().to_4x4()
    m = basis.copy()
    m.translation = mid + Z * ((z0 + z1) / 2) - out * 0.2
    me.box(m, (w, 0.04, z1 - z0), glass)
    r = w * 0.75
    p = o + along * u0 + Z * (z1 - r)
    me.prism(p, along, Z, [(0, 0), (0, r), (w / 2, r)], K.WALL_T, wall_mat)
    me.prism(p, along, Z, [(w / 2, r), (w, r), (w, 0)], K.WALL_T, wall_mat)
    m = basis.copy()
    m.translation = mid + Z * (z0 - 0.05) + out * 0.06
    me.box(m, (w + 0.2, 0.22, 0.1), "ashlar")


def disc(me, centre, normal_rz, r, mat, n=12, depth=0.06):
    """A flat round plate standing on a wall face (rose window, clock, shield):
    in the vertical plane facing the direction `normal_rz` degrees."""
    a = math.radians(normal_rz)
    nrm = Vector((math.cos(a), math.sin(a), 0))
    u = Z.cross(nrm).normalized()
    o = Vector(centre) + nrm * (depth / 2)
    poly = [(r * math.cos(k * math.tau / n), r * math.sin(k * math.tau / n)) for k in range(n)]
    me.prism(o, u, Z, poly, depth, mat)


def arch_fill(me, xa, xb, y0, y1, z_spring, rise, z_top, mat="ashlar", n=10, ring="ashlar"):
    """Masonry over a segmental arch from xa to xb (springing at z_spring,
    `rise` high) up to z_top, y0..y1 thick, with a voussoir ring proud on
    both faces. The arch's underside is the soffit."""
    s, cx = (xb - xa) / 2, (xa + xb) / 2
    R = (s * s + rise * rise) / (2 * rise)
    zc = z_spring + rise - R
    th = math.asin(min(1.0, s / R))
    pts = [(cx + R * math.sin(-th + 2 * th * k / n), zc + R * math.cos(-th + 2 * th * k / n)) for k in range(n + 1)]
    for (xa_, za), (xb_, zb) in zip(pts, pts[1:]):
        me.prism(Vector((0, y0, 0)), X, Z, [(xa_, za), (xb_, zb), (xb_, z_top), (xa_, z_top)], y1 - y0, mat)
        mx, mz = (xa_ + xb_) / 2, (za + zb) / 2
        rad = Vector((mx - cx, 0, mz - zc)).normalized()
        a = math.atan2(zb - za, xb_ - xa_)
        seg = math.hypot(xb_ - xa_, zb - za)
        for yy in (y0 - 0.05, y1 + 0.05):
            me.box(T(mx + rad.x * 0.25, yy, mz + rad.z * 0.25, ry=-math.degrees(a)), (seg * 1.04, 0.12, 0.5), ring)
    return pts


def _auto(L, fixed, spacing, w, v0, v1, kind, margin=0.5):
    """Windows spread evenly along a wall of length L, skipping any that
    would touch a fixed opening."""
    ops = list(fixed)
    n = int((L - 2 * margin + spacing - w) // spacing)
    if n > 0:
        start = (L - (n * spacing - (spacing - w))) / 2
        for i in range(n):
            u0 = start + i * spacing
            u1 = u0 + w
            if all(u1 + 0.3 < f[0] or u0 - 0.3 > f[1] for f in fixed):
                ops.append((u0, u1, v0, v1, kind))
    return sorted(ops)


KINDS = ("window", "window", "window_dim", "window_dim")


def storey(me, box, z0, z1, infill, frame, front=(), spacing=2.0, ww=0.9, rails=(), kinds=KINDS,
           sides=(1, 1, 1, 1), sill=0.8, wh=None, front_only=False, rich=False):
    """Four walls of one storey round `box` (x0, x1, y0, y1), windows spread
    along each; `front` holds the -Y wall's fixed openings (doors, shop)."""
    x0, x1, y0, y1 = box
    W, D = x1 - x0, y1 - y0
    wh = wh or min(1.3, z1 - z0 - sill - 0.4)
    walls = [((x0, y0), (1, 0, 0), W), ((x1, y0), (0, 1, 0), D), ((x1, y1), (-1, 0, 0), W), ((x0, y1), (0, -1, 0), D)]
    for i, ((ox, oy), al, L) in enumerate(walls):
        if not sides[i]:
            continue
        fixed = list(front) if i == 0 else []
        ops = fixed if (front_only and i == 0) else _auto(L, fixed, spacing, ww, sill, sill + wh, kinds[i])
        br = []
        if frame and ops:
            if ops[0][0] > 1.0:
                br.append((K.BEAM, ops[0][0] - K.BEAM, True))
            if L - ops[-1][1] > 1.0:
                br.append((ops[-1][1] + K.BEAM, L - K.BEAM, False))
        K.wall(me, Vector((ox, oy, 0)), al, L, z0, z1, ops, infill, frame=frame, braces=br,
               rails=rails if frame else ())
        if rich and frame:
            DT.sill_crosses(me, Vector((ox, oy, 0)), al, ops, z0, sill, length=L, z1=z1)
        if rich:
            wr = random.Random(int(ox * 777 + oy * 13 + z0 * 51 + i))
            DT.window_dress(me, wr, Vector((ox, oy, 0)), al, ops, z0)
            if infill in ("fieldstone", "brick"):
                DT.wall_patches(me, wr, Vector((ox, oy, 0)), al, L, z0, z1, ops)
        # window boxes under about a third of the windows (2026-09-29): colour
        # on the fronts, seeded by the wall so a rebuild is the same house
        rnd = random.Random(int(ox * 1000 + oy * 37 + z0 * 101 + i))
        alv = Vector(al).normalized()
        out = alv.cross(Vector((0, 0, 1))).normalized()
        for u0, u1, v0, v1, kind in ops:
            if kind.startswith("window") and rnd.random() < (0.6 if rich else 0.36):
                c = Vector((ox, oy, 0)) + alv * ((u0 + u1) / 2) + out * 0.15 + Vector((0, 0, z0 + v0 - 0.12))
                K.window_box(me, c, al, (u1 - u0) + 0.2, rnd)
                if rich:
                    DT.trailing(me, c, al, (u1 - u0) + 0.2, rnd)


# Octopath proportions (user, 2026-09-24): an ordinary building's storey is
# 2.3 m, its door 2.0 m (1.08x the 1.85 m figure; an Octopath II town frame
# measures ~1.1x), its roof 10 degrees flatter than drawn, and it has at most
# 3 floors. Before this the city stood 6-10 character heights tall against
# Octopath's ~3.4, so one townhouse filled the frame. Landmarks pass tall=True
# and keep what they were built with.
FH = 2.3
DOOR_H = 2.0
MAX_FLOORS = 3
FLATTER = 10.0
GROUND_TOP = 0.5 + FH + 0.3   # plinth + ground storey: where the first floor starts


def house(me, W, D, floors, ground="fieldstone", upper="plaster", cover="slate", pitch=50, ridge="x",
          jet=0.0, fh=2.7, door=None, door_w=1.0, shop=False, spacing=2.0, chimneys=(), sh=None,
          upper_front=(), roof=True, gable_win=True, front=None, tall=False, rich=RICH, dormers=None, awning=("cloth_blue", "cloth_cream"), extras=True):
    """The common town building: plinth, `floors` storeys (the ground one in
    `ground`, the rest in `upper`, timber-framed when plaster), each upper
    floor jettied `jet` over the street, gables, roof, chimneys. Returns
    (ridge z, top box, eave z). Unless `tall`, the storey, floor count and
    pitch given are overridden by the proportions above. `rich` adds the
    detail layer (`detail.py`): quoins, stone surrounds, jetty brackets,
    crosses, trailing plants, tile courses, ridge caps, moss and `dormers`
    ((a along the ridge, slope side), see `detail.roof_dress`)."""
    if not tall:
        fh, floors, pitch = FH, min(floors, MAX_FLOORS), pitch - FLATTER
    door_h, clear = (2.3, 0.4) if tall else (DOOR_H, 0.3)
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    K.plinth(me, x0, x1, y0, y1)
    z, by0 = 0.5, y0
    for f in range(floors):
        z1 = z + fh + (0.3 if f == 0 else 0.0)
        mat = ground if f == 0 else upper
        fr = mat == "plaster"
        if f == 0:
            if front is not None:
                fx = list(front)
            else:
                du = door if door is not None else max(0.6, W * 0.22)
                fx = [(du, du + door_w, 0.0, min(door_h, z1 - z - clear), "door")]
                if shop and W - (du + door_w) > 2.9:
                    fx.append((du + door_w + 0.5, min(du + door_w + 2.9, W - 0.5), 0.8, 2.2, "window_bare" if rich else "window"))
        else:
            fx = list(upper_front)
        storey(me, (x0, x1, by0, y1), z, z1, mat, fr, fx, spacing=spacing, rails=(0.65,) if fr else (), rich=rich)
        if rich and mat in STONE:
            DT.quoins(me, x0, x1, by0, y1, z, z1)
        if f == 0:
            gfx = fx
            if rich:
                DT.surrounds(me, x0, by0, z, fx, awning=awning, stone=mat in STONE)
        FRONT.append((f, z, by0, x0, x1))
        if sh is not None:
            K.proxy_box(sh, x0, x1, by0, y1, -0.5 if f == 0 else z, z1)
        if jet and f < floors - 1:
            if rich:
                DT.jetty_brackets(me, x0, x1, by0, z1, jet)
            n = max(2, int(W / 0.6))
            for i in range(n + 1):
                x = x0 + 0.2 + i * (W - 0.4) / n
                K.beam(me, (x, by0 + 0.3, z1 - 0.1), (x, by0 - jet - 0.12, z1 - 0.1), 0.16, 0.14)
            by0 -= jet
        z = z1
    top = upper if floors > 1 else ground
    fr = top == "plaster"
    tp = math.tan(math.radians(pitch))
    if ridge == "x":
        rise = (y1 - by0) / 2 * tp
        K.gable(me, Vector((x1, by0, 0)), (0, 1, 0), y1 - by0, z, rise, top, frame=fr,
                window=(0.6, 0.7) if gable_win else None)
        K.gable(me, Vector((x0, y1, 0)), (0, -1, 0), y1 - by0, z, rise, top, frame=fr)
    else:
        rise = W / 2 * tp
        K.gable(me, Vector((x0, by0, 0)), (1, 0, 0), W, z, rise, top, frame=fr,
                window=(0.7, 0.9) if gable_win else None)
        K.gable(me, Vector((x1, y1, 0)), (-1, 0, 0), W, z, rise, top, frame=fr)
    ridge_z = z + rise
    if roof:
        ridge_z = K.roof(me, x0, x1, by0, y1, z, pitch, cover, ridge_axis=ridge)
        if rich:
            if dormers is None:
                # one dormer per ~4 m of the slope the street sees (-y for a ridge
                # along x, -x for one along y), none on thatch, none by a chimney
                dormers = []
                span = (x1 - x0) if ridge == "x" else (y1 - by0)
                n = 0 if cover == "thatch" or span < 4.5 else 1 if span < 7.5 else 2 if span < 12 else 3
                ctr = 0.0 if ridge == "x" else (by0 + y1) / 2
                side = -1 if ridge == "x" else 1
                for k in range(n):
                    a = ctr + span * (k + 1) / (n + 1) - span / 2
                    near = [c for c in chimneys if abs((c[0] if ridge == "x" else c[1]) - a) < 1.4
                            and ((c[1] < (by0 + y1) / 2) if ridge == "x" else (c[0] < 0))]
                    if not near:
                        dormers.append((a, side))
            DT.roof_dress(me, x0, x1, by0, y1, z, pitch, cover, ridge_axis=ridge,
                          rnd=random.Random(int(W * 100 + D * 7)), dormers=dormers, dormer_mat=top)
        if sh is not None:
            K.proxy_roof(sh, x0, x1, by0, y1, z, ridge_z, ridge_axis=ridge)
    crnd = random.Random(int(W * 31 + D * 17))
    for cx, cy in chimneys:
        K.chimney(me, cx, cy, ridge_z + 0.8, w=0.8, d=0.8, mat="brick" if ground == "brick" else "fieldstone")
        if rich:
            DT.chimney_extra(me, crnd, cx, cy, ridge_z + 0.8)
        SMOKE.append((cx, cy, ridge_z + 0.8 + 0.45))
    if rich:
        DT.foundation(me, crnd, x0, x1, y0, y1,
                      skip=[(x0 + o[0], x0 + o[1]) for o in gfx if o[4] == "door"])
    if rich and extras:
        # what every house front gets by chance: ivy at a corner, a pot by the
        # door, a lantern beside it (the prototypes place their own: extras=False)
        ern = random.Random(int(W * 53 + D * 29 + floors * 7))
        if ern.random() < 0.55:
            DT.ivy(me, ern, Vector((x0 + 0.45 if ern.random() < 0.5 else x1 - 0.45, y0, 0.45)), (1, 0, 0),
                   2.8 if tall else 2.2)
        door_ = next((o for o in gfx if o[4] == "door"), None)
        if door_ is not None:
            du0, du1 = x0 + door_[0], x0 + door_[1]
            if ern.random() < 0.5 and du1 + 0.45 < x1 - 0.2:
                DT.pots(me, ern, ((du1 + 0.4, y0 - 0.55, 0.0),))
            if ern.random() < 0.5 and du0 - 0.35 > x0 + 0.3:
                wall_lantern(me, du0 - 0.35, y0, 2.35)
    return ridge_z, (x0, x1, by0, y1), z


def wall_lantern(me, x, y, z, rz=-90.0):
    """An iron bracket lantern on a wall facing `rz` (default -Y)."""
    a = math.radians(rz)
    o = Vector((math.cos(a), math.sin(a), 0))
    p = Vector((x, y, z))
    K.beam(me, p, p + o * 0.5, 0.05, 0.05, mat="iron")
    lamp = p + o * 0.5 - Z * 0.32
    me.box(T(lamp.x, lamp.y, lamp.z + 0.24), (0.3, 0.3, 0.05), "iron")
    pyramid(me, lamp.x, lamp.y, lamp.z + 0.26, 0.22, 0.18, "iron")
    me.box(T(lamp.x, lamp.y, lamp.z), (0.2, 0.2, 0.36), "M_Lamp")
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        me.box(T(lamp.x + dx * 0.11, lamp.y + dy * 0.11, lamp.z), (0.03, 0.03, 0.4), "iron")
    me.box(T(lamp.x, lamp.y, lamp.z - 0.2), (0.26, 0.26, 0.04), "iron")


def banner(me, x, y, z_top, length, mat="cloth_red", w=0.9, rz=-90.0):
    """A long hanging banner on a rod, swallow-tailed, facing `rz`."""
    a = math.radians(rz)
    o = Vector((math.cos(a), math.sin(a), 0))
    u = Z.cross(o).normalized()
    p = Vector((x, y, z_top)) + o * 0.08
    K.beam(me, p - u * (w / 2 + 0.12), p + u * (w / 2 + 0.12), 0.05, 0.05, mat="iron")
    poly = [(-w / 2, 0), (w / 2, 0), (w / 2, -length), (0, -length + 0.35), (-w / 2, -length)]
    me.prism(p + o * 0.03, u, Z, poly[:3] + [poly[3]], 0.03, mat)
    me.prism(p + o * 0.03, u, Z, [poly[0], poly[3], poly[4]], 0.03, mat)


def hanging_sign(me, x, y, z, rz=-90.0, mat="cloth_red"):
    """A painted board on an iron arm, standing out from a wall facing `rz`."""
    a = math.radians(rz)
    o = Vector((math.cos(a), math.sin(a), 0))
    p = Vector((x, y, z))
    K.beam(me, p, p + o * 1.1, 0.06, 0.06, mat="iron")
    K.beam(me, p - Z * 0.5, p + o * 0.55, 0.04, 0.04, mat="iron")
    c = p + o * 0.65 - Z * 0.42
    me.box(T(c.x, c.y, c.z, rz=rz), (0.8, 0.06, 0.6), "planks")
    me.box(T(c.x, c.y, c.z, rz=rz), (0.4, 0.09, 0.3), mat)


def rubble(me, rnd, cx, cy, r, n, mat="fieldstone"):
    for _ in range(n):
        s = rnd.uniform(0.25, 0.55)
        me.box(T(cx + rnd.uniform(-r, r), cy + rnd.uniform(-r, r), s * 0.35, rz=rnd.uniform(0, 90)),
               (s, s * 0.8, s * 0.7), mat)


# ---------------------------------------------------------------------------
# buildings
# ---------------------------------------------------------------------------

def _barrel(me, x, y, z=0.0):
    rod(me, (x, y, z), (x, y, z + 0.9), 0.3, "planks", n=10, r1=0.3)
    for zz in (0.15, 0.75):
        cyl(me, x, y, z + zz, z + zz + 0.06, 0.315, "iron", n=10)


def _crate(me, x, y, z, s, rz=0.0):
    me.box(T(x, y, z + s / 2, rz=rz), (s, s, s), "planks")
    for d in (-1, 1):
        me.box(T(x, y, z + s / 2, rz=rz) @ T(d * s * 0.36, -s / 2 - 0.01, 0), (0.07, 0.03, s * 0.96), "timber")


def _sack(me, x, y, z=0.0, rz=0.0):
    me.box(T(x, y, z + 0.27, rz=rz), (0.44, 0.34, 0.54), "cloth_cream")
    me.box(T(x, y, z + 0.58, rz=rz), (0.2, 0.16, 0.1), "cloth_cream")
    me.box(T(x, y, z + 0.52, rz=rz), (0.24, 0.2, 0.04), "timber")


def _pair(name):
    return K.Mesh(name), K.Mesh("SHADOW_" + name)


def guildhouse():
    """Market Square: three storeys, ashlar ground floor with a wide door,
    jettied timber floors above, gable to the square with a clock, a bell
    turret on the ridge, red banners."""
    me, sh = _pair("guildhouse")
    ridge, (x0, x1, y0, y1), ze = house(me, 9.0, 8.0, 3, ground="ashlar", cover="slate", pitch=56, ridge="y",
                                        jet=0.35, fh=2.9, door=3.8, door_w=1.4, spacing=2.1,
                                        chimneys=((2.8, 2.2),), sh=sh, tall=True)
    disc(me, (0, y0 - 0.02, ze + 1.9), -90, 0.6, "flagstone")
    disc(me, (0, y0 - 0.06, ze + 1.9), -90, 0.48, "plaster")
    K.beam(me, (0, y0 - 0.1, ze + 1.9), (0, y0 - 0.1, ze + 2.25), 0.05, 0.03, mat="iron")
    K.beam(me, (0, y0 - 0.1, ze + 1.9), (0.28, y0 - 0.1, ze + 1.9), 0.05, 0.03, mat="iron")
    me.box(T(0, 1.2, ridge + 0.6), (1.7, 1.7, 2.4), "plaster")
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        K.beam(me, (dx * 0.8, 1.2 + dy * 0.8, ridge - 0.6), (dx * 0.8, 1.2 + dy * 0.8, ridge + 1.8))
    me.box(T(0, 1.2, ridge + 1.1), (1.74, 1.74, 0.9), "glass")
    pyramid(me, 0, 1.2, ridge + 1.8, 1.5, 2.6, "slate")
    rod(me, (0, 1.2, ridge + 4.3), (0, 1.2, ridge + 5.1), 0.04, "iron", n=4)
    for x in (-3.3, 3.3):
        banner(me, x, y0 - 0.02, ze - 0.4, 3.2)
    wall_lantern(me, -1.2, y0, 2.6)
    wall_lantern(me, 1.6, y0, 2.6)
    me.box(T(0, y0 - 0.9, -0.05), (3.4, 1.0, 0.3), "ashlar")
    return me, sh


def tavern():
    """Two storeys and an attic, fieldstone below, jettied timber above, a
    balcony along the front, a sign on an arm, barrels by the door."""
    me, sh = _pair("tavern")
    ridge, (x0, x1, y0, y1), ze = house(me, 9.4, 7.0, 2, ground="fieldstone", cover="clay_tile", pitch=48,
                                        ridge="x", jet=0.4, fh=2.9, door=2.2, door_w=1.3, spacing=2.0,
                                        chimneys=((-3.4, 1.0), (3.2, 1.0)), sh=sh,
                                        rich=True, dormers=((-1.6, -1), (2.0, -1)), extras=False)
    rnd = random.Random(410)
    DT.ivy(me, rnd, Vector((4.1, y0, 0.45)), (1, 0, 0), 2.5)
    # the hero pass (2026-09-30): banners at the corner, pots at the door, a bench,
    # a planted strip, crates by the barrels
    banner(me, x1 - 0.45, y0 - 0.02, ze - 0.3, 2.6)
    banner(me, x0 + 0.45, y0 - 0.02, ze - 0.3, 2.6)
    DT.pots(me, rnd, ((-2.85, y0 - 0.6, 0.0), (-0.85, y0 - 0.6, 0.0)))
    DT.flower_strip(me, rnd, (2.0, y0 - 0.6, 0), (4.5, y0 - 0.6, 0))
    _crate(me, 1.75, y0 - 0.75, 0.0, 0.6, 8)
    _crate(me, 1.75, y0 - 0.75, 0.6, 0.46, 35)
    DT.table_set(me, (-3.7, y0 - 1.25, 0), (1, 0, 0), rnd)
    # the front balcony dressed: boxes on its rail, lanterns hung under it
    for x in (-1.1, 0.9, 2.8):
        c = Vector((x, y0 - 1.17, GROUND_TOP + 0.9))
        K.window_box(me, c, (1, 0, 0), 1.0, rnd)
        DT.trailing(me, c, (1, 0, 0), 1.0, rnd)
    for x in (-1.95, 3.55):
        DT.hanging_lantern(me, (x, y0 - 1.05, GROUND_TOP - 0.05), drop=0.25)
    # an attic balcony on the street-side gable, with its own window
    zg = ze + 1.05
    me.box(T(x0 - 0.03, 0, zg), (0.04, 0.8, 0.95), "M_Window_Dim")
    for dy in (-0.45, 0.45):
        K.beam(me, (x0 - 0.08, dy, zg - 0.5), (x0 - 0.08, dy, zg + 0.5), 0.1, 0.1)
    K.beam(me, (x0 - 0.08, -0.5, zg + 0.52), (x0 - 0.08, 0.5, zg + 0.52), 0.12, 0.1)
    DT.balcony(me, (x0, 0.75, 0), (0, -1, 0), 0.0, 1.5, zg - 0.55, depth=0.55, rnd=rnd)
    # street-side: a keg on a trestle, sacks, a chalk board
    for dx in (-0.35, 0.35):
        K.beam(me, (2.6 + dx, y0 - 1.55, 0.0), (2.6 + dx, y0 - 1.3, 0.62), 0.07, 0.07, up=(1, 0, 0))
        K.beam(me, (2.6 + dx, y0 - 1.05, 0.0), (2.6 + dx, y0 - 1.3, 0.62), 0.07, 0.07, up=(1, 0, 0))
    rod(me, (2.15, y0 - 1.3, 0.9), (3.05, y0 - 1.3, 0.9), 0.3, "planks", n=10, r1=0.3)
    for xx in (2.3, 2.9):
        me.box(T(xx, y0 - 1.3, 0.9), (0.06, 0.64, 0.64), "iron")
    me.box(T(2.02, y0 - 1.3, 0.82), (0.12, 0.05, 0.05), "iron")
    for k in range(2):
        _sack(me, 1.95 + k * 0.1, y0 - 1.6 - k * 0.45, rz=k * 30)
    for s_ in (-1, 1):
        me.box(T(-0.9, y0 - 1.45 + s_ * 0.16, 0.45, rx=s_ * 12), (0.6, 0.04, 0.9), "planks")
    me.box(T(-0.9, y0 - 1.64, 0.5, rx=-12), (0.5, 0.02, 0.6), "iron")
    for k in range(3):
        me.box(T(-0.9 + (k - 1) * 0.12, y0 - 1.66, 0.62 - k * 0.12, rx=-12), (0.3 - k * 0.06, 0.01, 0.03), "cloth_cream")
    zf = GROUND_TOP
    me.box(T(0.8, y0 - 0.55, zf + 0.05), (5.6, 1.1, 0.14), "planks", axis=(1, 0, 0))
    for x in (-1.8, 0.8, 3.4):
        K.beam(me, (x, y0 + 0.05, zf - 0.9), (x, y0 - 1.0, zf), 0.14, 0.14, up=(1, 0, 0))
    for k in range(13):
        x = -1.95 + k * 0.46
        K.beam(me, (x, y0 - 1.05, zf + 0.12), (x, y0 - 1.05, zf + 1.0), 0.06, 0.06)
    K.beam(me, (-2.0, y0 - 1.05, zf + 1.02), (3.6, y0 - 1.05, zf + 1.02), 0.1, 0.1)
    for x in (-2.0, 3.6):
        K.beam(me, (x, y0 - 1.05, zf + 1.0), (x, y0 + 0.2, zf + 1.0), 0.1, 0.1)
    DT.grand_sign(me, (x0 + 0.4, y0 - 0.4, GROUND_TOP + 1.95), (0, -1, 0), reach=2.1, board=(1.55, 1.1))
    wall_lantern(me, -2.9, y0, 2.4)
    wall_lantern(me, -0.7, y0, 2.4)
    for i, (x, y) in enumerate(((0.4, y0 - 0.6), (1.1, y0 - 0.55), (0.75, y0 - 1.2))):
        rod(me, (x, y, 0), (x, y, 0.9), 0.3, "planks", n=10, r1=0.3)
        for zz in (0.15, 0.75):
            cyl(me, x, y, zz, zz + 0.06, 0.315, "iron", n=10)
    return me, sh


def shop():
    """A narrow shopfront: brick ground floor with a wide window and awning,
    jettied timber floor, slate gable to the street, a sign."""
    me, sh = _pair("shop")
    # 2026-09-30, the hero pass: a blue striped awning over the window, the produce
    # under it, a dormer, ivy, pots and a lantern (detail.py, rich=True)
    ridge, (x0, x1, y0, y1), ze = house(me, 5.8, 6.6, 2, ground="brick", cover="clay_tile", pitch=54, ridge="y",
                                        jet=0.4, fh=2.8, door=0.4, shop=True, chimneys=((1.8, 1.8),), sh=sh,
                                        rich=True, dormers=((0.3, 1),), extras=False)
    rnd = random.Random(437)
    hanging_sign(me, x0 + 0.2, y0, GROUND_TOP - 0.5, mat="cloth_blue")
    wall_lantern(me, -1.25, y0, 2.4)
    for i, x in enumerate((-0.65, 0.15, 0.95)):
        me.box(T(x, y0 - 0.75, 0.25 + (i % 2) * 0.05, rz=i * 7), (0.6, 0.55, 0.5 + (i % 2) * 0.1), "planks")
        me.box(T(x, y0 - 0.75, 0.55 + (i % 2) * 0.1, rz=i * 7), (0.52, 0.47, 0.08), ("crops", "moss", "clay_tile")[i])
        for _ in range(4):
            me.box(T(x + rnd.uniform(-0.18, 0.18), y0 - 0.75 + rnd.uniform(-0.15, 0.15), 0.64 + (i % 2) * 0.1),
                   (0.12, 0.12, 0.1), ("cloth_red", "crops", "moss")[i])
    for k in range(2):
        me.box(T(1.85 + k * 0.1, y0 - 0.6 - k * 0.45, 0.3, rz=k * 25), (0.5, 0.4, 0.6), "cloth_cream")
    DT.pots(me, rnd, ((-2.8, y0 - 0.55, 0.0),))
    _barrel(me, x1 + 0.55, y0 + 0.6)
    _sack(me, x1 + 0.6, y0 + 1.3, rz=30)
    DT.ivy(me, rnd, Vector((2.35, y0, 0.45)), (1, 0, 0), 2.4)
    return me, sh


def tenement():
    """Storeys stacked over the lane (three, the city's cap), each jettied
    out over the last: fieldstone ground floor, timber floors, two chimneys."""
    me, sh = _pair("tenement")
    ridge, (x0, x1, y0, y1), ze = house(me, 6.6, 6.2, 4, ground="fieldstone", cover="clay_tile", pitch=55, ridge="x",
                                        jet=0.3, fh=2.6, door=0.7, spacing=1.9,
                                        chimneys=((-2.3, 1.1), (2.3, 1.1)), sh=sh)
    for z, yy in ((GROUND_TOP + 0.55, y0 + 0.6), (GROUND_TOP + FH + 0.55, y0 + 0.3)):
        K.flower_box(me, 1.0, yy - 0.2, z, 1.0)
    wall_lantern(me, -1.4, -3.1, 2.5)
    return me, sh


def blacksmith():
    """A fieldstone smithy with an open forge shed on its east side: brick
    hearth glowing, a tall chimney, anvil, quench trough, tool rack."""
    me, sh = _pair("blacksmith")
    ridge, (x0, x1, y0, y1), ze = house(me, 7.0, 6.0, 1, ground="fieldstone", cover="shingle", pitch=45,
                                        ridge="x", fh=3.0, door=1.0, door_w=1.2, sh=sh)
    # the shed: posts, a lean-to roof off the gable wall
    for y in (y0 + 0.2, y1 - 0.2):
        K.beam(me, (6.2, y, -0.1), (6.2, y, 2.7))
    K.beam(me, (6.2, y0 + 0.1, 2.75), (6.2, y1 - 0.1, 2.75), 0.2, 0.2)
    ang = math.degrees(math.atan2(0.9, 3.2))
    me.box(T(4.95, 0, 3.25, ry=ang), (3.4, 6.8, 0.12), "planks", faces={"+z": "shingle"})
    me.box(T(4.8, 0, -0.05), (3.0, 6.0, 0.2), "flagstone")
    # hearth, coals, hood, chimney
    me.box(T(4.6, 1.3, 0.5), (1.6, 1.4, 1.0), "brick")
    me.box(T(4.6, 1.3, 1.02), (1.2, 1.0, 0.06), "M_Lamp")
    me.box(T(4.6, 1.3, 2.2), (1.2, 1.0, 0.9), "brick")
    me.box(T(4.6, 1.3, 5.0), (0.8, 0.8, 4.6), "brick")
    me.box(T(4.6, 1.3, 7.35), (0.95, 0.95, 0.12), "slate")
    SMOKE.append((4.6, 1.3, 7.45))
    # anvil on a stump, quench trough, rack
    cyl(me, 5.0, -1.2, 0.0, 0.55, 0.32, "bark", n=8, top="timber")
    me.box(T(5.0, -1.2, 0.68), (0.25, 0.2, 0.26), "iron")
    me.box(T(5.0, -1.2, 0.86), (0.7, 0.24, 0.14), "iron")
    me.box(T(5.42, -1.2, 0.86), (0.22, 0.12, 0.08), "iron")
    me.box(T(6.6, 1.0, 0.3), (0.6, 1.4, 0.6), "planks")
    me.box(T(6.6, 1.0, 0.57), (0.46, 1.26, 0.04), "water")
    me.box(T(3.62, -1.4, 1.6), (0.08, 1.6, 1.0), "planks")
    for k in range(4):
        K.beam(me, (3.7, -2.0 + k * 0.38, 2.0), (3.7, -2.0 + k * 0.38, 1.25), 0.04, 0.04, mat="iron")
    return me, sh


def warehouse():
    """Three storeys of storage: brick ground floor with wide doors, plank
    upper floors with stacked loading doors under a hoist beam."""
    me, sh = _pair("warehouse")
    ridge, (x0, x1, y0, y1), ze = house(me, 8.0, 10.0, 3, ground="brick", upper="planks", cover="clay_tile",
                                        pitch=50, ridge="y", fh=2.8, door=2.8, door_w=2.4, spacing=2.2,
                                        upper_front=[(3.3, 4.7, 0.0, 2.1, "door")], chimneys=(), sh=sh)
    K.beam(me, (0, y0 + 0.5, ze + 2.6), (0, y0 - 1.5, ze + 2.6), 0.22, 0.22)
    K.beam(me, (0, y0 - 0.02, ze + 1.6), (0, y0 - 1.0, ze + 2.55), 0.14, 0.14, up=(1, 0, 0))
    K.beam(me, (0, y0 - 1.35, ze + 2.45), (0, y0 - 1.35, ze - 1.4), 0.03, 0.03, mat="thatch")
    me.box(T(0, y0 - 1.35, ze + 2.4), (0.1, 0.3, 0.3), "timber")
    me.box(T(0, y0 - 1.35, ze - 1.5), (0.06, 0.18, 0.22), "iron")
    for x in (x0 - 0.3, x1 + 0.3):
        for k in range(2):
            me.box(T(x, -2 + k * 2.6, 0.35), (0.6, 0.6, 0.7), "planks")
    return me, sh


def stables():
    """A long timber-framed stable: four stall doors, thatched roof, hay
    bales and a water trough."""
    me, sh = _pair("stables")
    doors = [(u, u + 1.3, 0.0, 2.2, "door") for u in (0.9, 3.9, 6.9, 9.9)]
    ridge, (x0, x1, y0, y1), ze = house(me, 12.2, 6.0, 1, ground="plaster", cover="thatch", pitch=46, ridge="x",
                                        fh=3.0, front=doors, spacing=2.4, sh=sh)
    for x, y, rz in ((7.1, -1.0, 10), (7.2, 0.3, -5), (7.15, -0.35, 80)):
        me.box(T(x, y, 0.3 if rz < 50 else 0.85, rz=rz), (0.9, 0.5, 0.55), "thatch")
    me.box(T(0, y0 - 1.2, 0.3), (2.4, 0.6, 0.6), "planks")
    me.box(T(0, y0 - 1.2, 0.57), (2.24, 0.46, 0.04), "water")
    return me, sh


def barracks():
    """The citadel's barracks: long two-storey block, three chimneys,
    painted shields along the front, a weapon rack."""
    me, sh = _pair("barracks")
    ridge, (x0, x1, y0, y1), ze = house(me, 16.0, 7.0, 2, ground="fieldstone", cover="slate", pitch=50,
                                        ridge="x", fh=2.9, door=7.4, door_w=1.3, spacing=2.3,
                                        chimneys=((-5.2, 1.2), (0, 1.2), (5.2, 1.2)), sh=sh)
    for i, x in enumerate((-5.0, 0.0, 5.0)):
        disc(me, (x, y0 - 0.01, ze - 0.7), -90, 0.5, ("cloth_red", "cloth_blue", "cloth_red")[i], n=10)
        disc(me, (x, y0 - 0.06, ze - 0.7), -90, 0.12, "iron", n=6)
    banner(me, 2.6, y0, ze - 0.1, 2.4, mat="cloth_blue")
    me.box(T(-3.0, y0 - 0.6, 0.9), (2.2, 0.12, 0.1), "timber")
    me.box(T(-3.0, y0 - 0.6, 0.3), (2.2, 0.12, 0.1), "timber")
    for k in range(6):
        x = -3.9 + k * 0.36
        K.beam(me, (x, y0 - 0.55, 0.05), (x, y0 - 0.45, 2.1), 0.04, 0.04, mat="timber")
        pyramid(me, x, y0 - 0.45, 2.1, 0.05, 0.25, "iron")
    return me, sh


def cottage_tile():
    """A plastered, timber-framed cottage under red clay tiles, a porch roof
    over the door, flower boxes."""
    me, sh = _pair("cottage_tile")
    ridge, (x0, x1, y0, y1), ze = house(me, 6.6, 5.2, 1, ground="plaster", cover="clay_tile", pitch=46,
                                        ridge="x", fh=2.6, door=2.8, chimneys=((2.4, 0.9),), sh=sh)
    me.box(T(-0.02, y0 - 0.55, 3.05, rx=-20), (1.8, 1.2, 0.08), "planks", faces={"+z": "clay_tile"})
    for x in (-0.8, 0.8):
        K.beam(me, (x, y0 - 0.02, 2.2), (x, y0 - 0.9, 2.85), 0.1, 0.1, up=(1, 0, 0))
    K.flower_box(me, -2.0, y0 - 0.2, 1.22, 1.0)
    K.flower_box(me, 2.0, y0 - 0.2, 1.22, 1.0)
    return me, sh


def cottage_l():
    """An L-plan cottage: two shingled wings meeting at a corner."""
    me, sh = _pair("cottage_l")
    house(me, 6.4, 5.0, 1, ground="plaster", cover="shingle", pitch=47, ridge="x", fh=2.6, door=1.2,
          chimneys=((-2.6, 0.8),), sh=sh)
    me.xf = T(1.9, 3.6, 0, rz=90)
    sh.xf = me.xf
    house(me, 5.0, 4.4, 1, ground="plaster", cover="shingle", pitch=47, ridge="x", fh=2.6, door=1.8, sh=sh)
    me.xf = K.Matrix.Identity(4)
    sh.xf = me.xf
    return me, sh


def townhouse_narrow():
    """A slot of a house: 4 m wide, three storeys, steep slate gable."""
    me, sh = _pair("townhouse_narrow")
    house(me, 4.0, 7.5, 3, ground="brick", cover="clay_tile", pitch=60, ridge="y", jet=0.35, fh=2.6, door=0.5,
          spacing=1.7, chimneys=((1.2, 2.6),), sh=sh)
    return me, sh


def townhouse_std():
    """The city's plain townhouse, in place of the village kit's (11.2 m, six
    character heights): two storeys, brick ground floor with a door and a shop
    window, jettied timber floor with flower boxes, slate gable to the street,
    a chimney. 5.2 x 7 m, the village one's footprint."""
    me, sh = _pair("townhouse_std")
    # 2026-09-30, the user's asset sheet: rubble stone below with dressed quoins and
    # an arched door, blue slate, dormers both sides, ivy (detail.py, rich=True)
    house(me, 5.2, 7.0, 2, ground="fieldstone", cover="slate_blue", pitch=52, ridge="y", jet=0.4, door=0.8, shop=True,
          chimneys=((1.7, 1.6),), sh=sh, rich=True, dormers=((0.4, 1), (0.4, -1)), awning=("cloth_red", "cloth_cream"), extras=False)
    rnd = random.Random(583)
    x0, x1, y0, y1 = -2.6, 2.6, -3.5, 3.5
    DT.ivy(me, rnd, Vector((2.2, y0, 0.45)), (1, 0, 0), 2.3)
    DT.ivy(me, rnd, Vector((x0, 0.9, 0.45)), (0, -1, 0), 2.6)
    # the hero pass (2026-09-30, the user's brief): a balcony on the side, a lantern
    # at the door, a sign on the side, pots, a planted strip, barrels and crates
    DT.balcony(me, (x0, y1, 0), (0, -1, 0), 2.4, 4.4, GROUND_TOP, rnd=rnd)
    wall_lantern(me, -2.1, y0, 2.4)
    hanging_sign(me, x0, y0 + 1.3, GROUND_TOP - 0.5, rz=180.0, mat="cloth_blue")
    DT.pots(me, rnd, ((-0.5, y0 - 0.6, 0.0), (-2.15, y0 - 0.6, 0.0)))
    DT.flower_strip(me, rnd, (x0 - 0.6, y0 + 0.4, 0), (x0 - 0.6, y0 + 2.4, 0))
    for x, y in ((x0 - 0.7, y1 - 1.1), (x0 - 0.75, y1 - 1.8)):
        _barrel(me, x, y)
    _crate(me, x0 - 0.8, y1 - 0.4, 0.0, 0.62, 12)
    _crate(me, x0 - 0.8, y1 - 0.4, 0.62, 0.48, 40)
    DT.picket(me, (x0 - 0.9, y0 + 0.3, 0), (x0 - 0.9, y0 + 2.5, 0))
    for k, (dx, dy) in enumerate(((-1.25, y1 - 0.35), (-1.3, y1 - 0.95))):
        _sack(me, x0 + dx, dy, rz=20 + k * 35)
    for x in (-1.2, 1.4):
        K.flower_box(me, x, -3.5 - 0.4 - 0.2, GROUND_TOP + 0.55, 1.1)
    return me, sh


def townhouse_corner():
    """A corner house with an oriel turret on the street corner."""
    me, sh = _pair("townhouse_corner")
    ridge, (x0, x1, y0, y1), ze = house(me, 6.4, 6.4, 3, ground="brick", cover="clay_tile", pitch=50,
                                        ridge="x", fh=2.7, door=1.0, shop=True, chimneys=((-2.2, 1.2),), sh=sh)
    cx, cy = x1 + 0.1, y0 - 0.1
    zc = GROUND_TOP + 0.4   # the oriel starts just over the ground floor
    cyl(me, cx, cy, zc - 1.2, zc, 0.35, "ashlar", n=8, r1=1.05)
    cyl(me, cx, cy, zc, ze + 0.5, 1.05, "plaster", n=8)
    for k in range(8):
        a = k * 45 + 22.5
        if 90 < a < 180:
            continue
        for zz in (GROUND_TOP + 1.35, GROUND_TOP + FH + 1.35):
            me.box(T(cx + 1.06 * math.cos(math.radians(a)), cy + 1.06 * math.sin(math.radians(a)), zz, rz=a),
                   (0.04, 0.45, 1.0), "M_Window_Dim")
    pyramid(me, cx, cy, ze + 0.5, 1.35, 3.2, "clay_tile", n=8, rot=22.5)
    rod(me, (cx, cy, ze + 3.6), (cx, cy, ze + 4.3), 0.04, "iron", n=4)
    return me, sh


def townhouse_stall():
    """A townhouse with a market stall built out in front of it."""
    me, sh = _pair("townhouse_stall")
    ridge, (x0, x1, y0, y1), ze = house(me, 5.4, 7.0, 2, ground="brick", cover="shingle", pitch=52, ridge="y",
                                        jet=0.4, fh=2.8, door=0.4, chimneys=((1.5, 2.0),), sh=sh)
    y = y0 - 1.6
    me.box(T(0.9, y + 0.3, 0.5), (3.0, 0.7, 1.0), "planks")
    for x in (-0.6, 2.4):
        K.beam(me, (x, y, -0.1), (x, y, 2.3))
        K.beam(me, (x, y0 - 0.05, 2.9), (x, y, 2.3), 0.1, 0.1)
    ang = math.degrees(math.atan2(0.6, 1.6))
    me.box(T(0.9, (y + y0) / 2, 2.62, rx=-ang), (3.4, 1.8, 0.05), "cloth_red")
    for i, x in enumerate((-0.2, 0.6, 1.4, 2.1)):
        me.box(T(x, y + 0.3, 1.08), (0.6, 0.5, 0.16), "planks")
        me.box(T(x, y + 0.3, 1.18), (0.52, 0.42, 0.06), ("clay_tile", "moss", "crops", "cloth_red")[i])
    return me, sh


def townhouse_damaged():
    """A townhouse half unroofed: rafters bare over the back half, a window
    boarded, rubble and a fallen beam in front."""
    me, sh = _pair("townhouse_damaged")
    rnd = random.Random(7)
    ridge, (x0, x1, y0, y1), ze = house(me, 5.4, 7.0, 2, ground="brick", cover="slate", pitch=52, ridge="y",
                                        jet=0.4, fh=2.8, door=0.4, roof=False, sh=sh)
    ym = (y0 + y1) / 2
    ridge = roof(me, x0, x1, y0, ym, ze, 52 - FLATTER, "slate", ridge_axis="y")
    rise = (x1 - x0) / 2 * math.tan(math.radians(52 - FLATTER))
    for k in range(6):
        y = ym + 0.3 + k * 0.6
        for s in (-1, 1):
            K.beam(me, (s * (x1 + 0.2), y, ze - 0.15), (0, y, ze + rise), 0.12, 0.1, up=(0, 1, 0))
    K.beam(me, (0, ym, ze + rise + 0.1), (0, y1 + 0.2, ze + rise + 0.1), 0.2, 0.2)
    for k in range(3):
        K.beam(me, (x0 + 0.4, ym - 0.2 + k * 0.5, ze + 0.4), (x0 + 1.9, ym + k * 0.5, ze + 1.9), 0.25, 0.04,
               mat="slate", up=(0, 1, 0))
    for s in (-1, 1):
        zb = GROUND_TOP + 1.3   # across the upper floor's boarded window
        K.beam(me, (-0.9, y0 - 0.45, zb + s * 0.5), (0.9, y0 - 0.45, zb - s * 0.5), 0.2, 0.04, mat="planks")
    K.beam(me, (1.4, y0 - 2.4, 0.1), (3.2, y0 - 0.6, 0.35), 0.2, 0.2)
    rubble(me, rnd, 1.6, y0 - 1.5, 1.2, 9, "brick")
    rubble(me, rnd, 0.6, y0 - 1.0, 0.6, 5, "slate")
    return me, sh


def townhouse_ruin():
    """A burnt-out townhouse: ragged brick walls, one chimney stack still
    standing, charred beams, rubble and moss. No roof."""
    me, sh = _pair("townhouse_ruin")
    rnd = random.Random(11)
    W, D = 5.4, 7.0
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    K.plinth(me, x0, x1, y0, y1)
    runs = [((x0, y0), X, W), ((x1, y0), Y, D), ((x1, y1), -X, W), ((x0, y1), -Y, D)]
    for (ox, oy), al, L in runs:
        out = al.cross(Z)
        u = 0.0
        while u < L - 0.01:
            w = min(rnd.uniform(0.45, 0.8), L - u)
            gap = (al.x > 0.5 and 0.5 < u < 1.5) or (0.35 < (u / L) < 0.5 and rnd.random() < 0.5)
            top = 0.5 + (0.3 if gap else rnd.uniform(1.4, 4.6))
            c = Vector((ox, oy, 0)) + al * (u + w / 2) - out * 0.15
            me.box(T(c.x, c.y, (0.5 + top) / 2, rz=math.degrees(math.atan2(al.y, al.x))), (w - 0.02, 0.3, top - 0.5),
                   "brick", faces={"+z": "moss"} if rnd.random() < 0.3 else None)
            u += w
    me.box(T(x1 - 1.0, y1 - 0.2, 4.3), (0.9, 0.7, 7.6), "brick")
    for a, b in (((x0 + 0.5, y0 + 1.5, 0.5), (x1 - 0.8, y0 + 2.5, 3.2)), ((x0 + 1.0, y1 - 1.0, 0.6), (x0 + 2.8, y0 + 2.0, 2.4))):
        K.beam(me, a, b, 0.22, 0.2)
    rubble(me, rnd, 0, 0, 2.0, 14, "brick")
    rubble(me, rnd, 0.5, y0 - 1.2, 1.0, 6, "brick")
    me.box(T(-0.8, 0.8, 0.52), (2.0, 1.6, 0.06), "moss")
    return me, sh


def church():
    """The Old City's church: an ashlar nave with pointed stained-glass
    windows between buttresses, a slate roof, a round apse, a rose window,
    and a bell tower with a tall spire over the door."""
    me, sh = _pair("church")
    W, D, zt = 9.0, 16.0, 8.5
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    K.plinth(me, x0, x1, y0, y1, mat="ashlar")
    lan = [(u, u + 1.2, 1.6, 5.8, "hole") for u in (2.6, 5.9, 9.2, 12.5)]
    for o, al in ((Vector((x1, y0, 0)), Y), (Vector((x0, y1, 0)), -Y)):
        K.wall(me, o, al, D, 0.5, zt, lan, "ashlar", frame=False)
        for u0, u1, v0, v1, _ in lan:
            lancet(me, o, al, u0, u1, 0.5 + v0, 0.5 + v1, "ashlar")
        out = al.cross(Z)
        for u in (0.2, 3.4 + 0.6, 6.7 + 0.6, 10.0 + 0.6, 13.3 + 0.6, D - 0.2):
            p = o + al * u + out * 0.35
            me.box(T(p.x, p.y, 2.6), (0.7, 0.7, 5.2) if abs(al.y) < 0.5 else (0.7, 0.7, 5.2), "ashlar")
            q = o + al * u + out * 0.2
            me.box(T(q.x, q.y, 5.9), (0.45, 0.45, 1.4), "ashlar")
    K.wall(me, Vector((x0, y0, 0)), X, W, 0.5, zt, [], "ashlar", frame=False)
    K.wall(me, Vector((x1, y1, 0)), -X, W, 0.5, zt, [], "ashlar", frame=False)
    rise = W / 2 * math.tan(math.radians(56))
    K.gable(me, Vector((x0, y0, 0)), X, W, zt, rise, "ashlar", frame=False)
    K.gable(me, Vector((x1, y1, 0)), -X, W, zt, rise, "ashlar", frame=False)
    disc(me, (0, y0 - 0.03, zt + 1.4), -90, 1.25, "ashlar", n=16)
    disc(me, (0, y0 - 0.07, zt + 1.4), -90, 1.0, "stained_glass", n=16)
    ridge = roof(me, x0, x1, y0, y1, zt, 56, "slate", over_eave=0.4, ridge_axis="y")
    # apse: half an octagon, with a half-cone roof
    poly = [(4.2 * math.cos(math.pi * k / 4), 4.2 * math.sin(math.pi * k / 4)) for k in range(5)]
    me.prism(Vector((0, y1 - 0.2, zt - 1.0)), X, Y, poly, zt - 0.5, "ashlar")
    ring = [Vector((4.6 * math.cos(math.pi * k / 4), y1 - 0.2 + 4.6 * math.sin(math.pi * k / 4), zt - 1.1)) for k in range(5)]
    apex = Vector((0, y1 - 0.2, zt + 2.8))
    for k in range(4):
        me.face([ring[k], ring[k + 1], apex], "slate", Vector((0, y1 + 1.0, zt)))
    for k in range(1, 4):
        a = math.pi * k / 4
        me.box(T(4.22 * math.cos(a), y1 - 0.2 + 4.22 * math.sin(a), 4.2, rz=math.degrees(a)), (0.05, 0.7, 3.2),
               "stained_glass")
    # tower over the door
    tx0, tx1, ty0, ty1, th = -2.4, 2.4, y0 - 4.4, y0 + 0.2, 17.0
    K.plinth(me, tx0, tx1, ty0, ty1, mat="ashlar")
    K.wall(me, Vector((tx0, ty0, 0)), X, 4.8, 0.5, 6.0, [(1.7, 3.1, 0.0, 3.5, "door")], "ashlar", frame=False)
    K.wall(me, Vector((tx0, ty0, 0)), X, 4.8, 6.0, th, [(1.8, 3.0, 0.7, 4.3, "hole")], "ashlar", frame=False)
    lancet(me, Vector((tx0, ty0, 0)), X, 1.8, 3.0, 6.7, 10.3, "ashlar")
    K.wall(me, Vector((tx1, ty0, 0)), Y, 4.6, 0.5, th, [(2.0, 2.6, 8.0, 10.0, "hole")], "ashlar", frame=False)
    K.wall(me, Vector((tx0, ty1, 0)), -Y, 4.6, 0.5, th, [(2.0, 2.6, 8.0, 10.0, "hole")], "ashlar", frame=False)
    for yy in (ty0 + 0.4, ty0 + 4.2):
        for s in (-1, 1):
            me.box(T(s * 2.55, yy, 5.0), (0.5, 0.5, 10.0), "ashlar")
    # belfry: four arched openings with the bell inside
    bz0, bz1 = th, th + 4.0
    me.box(T(0, (ty0 + ty1) / 2, bz0 + 0.1), (5.1, 4.9, 0.3), "ashlar")
    for o, al, L in ((Vector((tx0, ty0, 0)), X, 4.8), (Vector((tx1, ty0, 0)), Y, 4.6),
                     (Vector((tx1, ty1, 0)), -X, 4.8), (Vector((tx0, ty1, 0)), -Y, 4.6)):
        K.wall(me, o, al, L, bz0 + 0.2, bz1, [(1.3, L - 1.3, 0.3, 3.2, "hole")], "ashlar", frame=False)
        lancet(me, o, al, 1.3, L - 1.3, bz0 + 0.5, bz0 + 3.4, "ashlar", glass="glass")
    tcy = (ty0 + ty1) / 2
    cyl(me, 0, tcy, bz0 + 1.2, bz0 + 2.4, 0.75, "iron", n=10, r1=0.45)
    me.box(T(0, tcy, bz1 + 0.15), (5.3, 5.1, 0.3), "ashlar")
    for sx in (-1, 1):
        for sy in (-1, 1):
            pyramid(me, sx * 2.35, tcy + sy * 2.25, bz1 + 0.3, 0.35, 1.8, "ashlar")
    pyramid(me, 0, tcy, bz1 + 0.3, 3.1, 11.0, "slate", n=8, rot=22.5)
    rod(me, (0, tcy, bz1 + 11.2), (0, tcy, bz1 + 12.6), 0.05, "iron", n=4)
    me.box(T(0, tcy, bz1 + 12.2), (0.7, 0.07, 0.07), "iron")
    wall_lantern(me, -1.4, ty0, 2.8)
    wall_lantern(me, 1.4, ty0, 2.8)
    K.proxy_box(sh, x0, x1, y0, y1, -0.5, zt)
    K.proxy_roof(sh, x0, x1, y0, y1, zt, ridge, ridge_axis="y")
    K.proxy_box(sh, tx0, tx1, ty0, ty1, -0.5, bz1)
    pyramid(sh, 0, tcy, bz1, 3.0, 11.0, "SHADOW")
    return me, sh


def chapel():
    """A small ashlar chapel: pointed windows, a bell-cote on the gable,
    a rose window, slate roof."""
    me, sh = _pair("chapel")
    W, D, zt = 6.2, 10.0, 5.8
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    K.plinth(me, x0, x1, y0, y1, mat="ashlar")
    lan = [(u, u + 1.0, 1.2, 4.2, "hole") for u in (2.2, 6.8)]
    for o, al in ((Vector((x1, y0, 0)), Y), (Vector((x0, y1, 0)), -Y)):
        K.wall(me, o, al, D, 0.5, zt, lan, "ashlar", frame=False)
        for u0, u1, v0, v1, _ in lan:
            lancet(me, o, al, u0, u1, 0.5 + v0, 0.5 + v1, "ashlar")
    K.wall(me, Vector((x0, y0, 0)), X, W, 0.5, zt, [(2.5, 3.7, 0.0, 2.8, "door")], "ashlar", frame=False)
    K.wall(me, Vector((x1, y1, 0)), -X, W, 0.5, zt, [(2.6, 3.6, 1.5, 4.3, "hole")], "ashlar", frame=False)
    lancet(me, Vector((x1, y1, 0)), -X, 2.6, 3.6, 2.0, 4.8, "ashlar")
    rise = W / 2 * math.tan(math.radians(55))
    K.gable(me, Vector((x0, y0, 0)), X, W, zt, rise, "ashlar", frame=False)
    K.gable(me, Vector((x1, y1, 0)), -X, W, zt, rise, "ashlar", frame=False)
    disc(me, (0, y0 - 0.03, zt + 1.2), -90, 0.75, "ashlar", n=12)
    disc(me, (0, y0 - 0.07, zt + 1.2), -90, 0.58, "stained_glass", n=12)
    ridge = roof(me, x0, x1, y0, y1, zt, 55, "slate", ridge_axis="y")
    for x in (-0.55, 0.55):
        me.box(T(x, y0 + 0.1, ridge + 0.9), (0.3, 0.45, 1.8), "ashlar")
    cyl(me, 0, y0 + 0.1, ridge + 0.6, ridge + 1.3, 0.3, "iron", n=8, r1=0.18)
    me.box(T(0, y0 + 0.1, ridge + 1.9), (1.5, 0.6, 0.2), "ashlar")
    pyramid(me, 0, y0 + 0.1, ridge + 2.0, 0.6, 0.9, "slate")
    wall_lantern(me, 1.1, y0, 2.4)
    K.proxy_box(sh, x0, x1, y0, y1, -0.5, zt)
    K.proxy_roof(sh, x0, x1, y0, y1, zt, ridge, ridge_axis="y")
    return me, sh


def manor_a():
    """A noble town manor: symmetrical, ashlar ground floor and quoins,
    plastered upper floors, a columned porch with a pediment, hipped slate
    roof with dormers, two chimneys."""
    me, sh = _pair("manor_a")
    W, D = 14.0, 10.0
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    K.plinth(me, x0, x1, y0, y1, z_top=0.9, mat="ashlar")
    tall = dict(spacing=2.4, ww=1.0, sill=0.7, wh=1.7)
    storey(me, (x0, x1, y0, y1), 0.9, 4.2, "ashlar", False, [(6.3, 7.7, 0.0, 2.7, "door")], **tall)
    storey(me, (x0, x1, y0, y1), 4.2, 7.4, "plaster", False, **tall)
    storey(me, (x0, x1, y0, y1), 7.4, 10.2, "plaster", False, spacing=2.4, ww=0.9, sill=0.7, wh=1.3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            me.box(T(sx * (W / 2 + 0.02), sy * (D / 2 + 0.02), 5.3), (0.7, 0.7, 9.8), "ashlar")
    me.box(T(0, y0 - 0.02, 4.25), (W + 0.3, D + 0.3, 0.25), "ashlar")
    me.box(T(0, 0, 10.25), (W + 0.4, D + 0.4, 0.3), "ashlar")
    top = hip(me, x0, x1, y0, y1, 10.4, 40, "slate", over=0.55)
    for x in (-4.5, 0.0, 4.5):
        me.box(T(x, y0 + 1.6, 11.6), (1.2, 1.6, 1.6), "plaster")
        me.box(T(x, y0 + 0.82, 11.5), (0.7, 0.04, 0.9), "M_Window_Dim")
        roof(me, x - 0.6, x + 0.6, y0 + 0.8, y0 + 2.4, 12.4, 50, "slate", over_eave=0.15, over_gable=0.1,
               thick=0.1, ridge_axis="y")
    for x in (-5.4, 5.4):
        K.chimney(me, x, 1.0, top + 0.6, w=1.0, d=1.0, mat="ashlar", top="brick")
        SMOKE.append((x, 1.0, top + 0.6 + 0.45))
    # porch: two columns, pediment, steps
    py = y0 - 1.8
    for x in (-1.4, 1.4):
        cyl(me, x, py + 0.3, 0.9, 4.0, 0.25, "ashlar", n=10)
        me.box(T(x, py + 0.3, 0.95), (0.7, 0.7, 0.2), "ashlar")
        me.box(T(x, py + 0.3, 4.05), (0.7, 0.7, 0.2), "ashlar")
    me.box(T(0, py + 0.9, 4.3), (3.8, 2.2, 0.4), "ashlar")
    me.prism(Vector((-1.9, py - 0.2, 4.5)), X, Z, [(0, 0), (3.8, 0), (1.9, 1.2)], -2.2, "ashlar")
    for k in range(3):
        me.box(T(0, py - 0.5 + k * 0.45 + 0.2, 0.15 + k * 0.25), (4.2 - k * 0.3, 1.6 - k * 0.45, 0.3 + k * 0.5 + 0.2),
               "ashlar", faces={"+z": "flagstone"})
    for x in (-3.0, 3.0):
        wall_lantern(me, x, y0, 2.9)
    K.proxy_box(sh, x0, x1, y0, y1, -0.5, 10.4)
    pyramid(sh, 0, 0, 10.4, W * 0.72, top - 10.4, "SHADOW")
    return me, sh


def manor_b():
    """A half-timbered noble house: brick below, jettied timber floors, a
    round corner tower with a conical slate roof, two gables to the street."""
    me, sh = _pair("manor_b")
    ridge, (x0, x1, y0, y1), ze = house(me, 11.0, 8.0, 3, ground="brick", cover="slate", pitch=55, ridge="x",
                                        jet=0.35, fh=2.8, door=5.0, door_w=1.3, spacing=2.1,
                                        chimneys=((-3.6, 1.2), (3.6, 1.2)), sh=sh)
    me.xf = T(-2.6, y0 + 1.2, 0)
    K.gable(me, Vector((-1.8, -1.25, 0)), X, 3.6, ze, 3.6 / 2 * math.tan(math.radians(58 - FLATTER)), "plaster")
    storey(me, (-1.8, 1.8, -1.25, 1.0), ze - FH, ze, "plaster", True, spacing=1.6, rails=(0.65,),
           sides=(1, 1, 0, 1))
    roof(me, -1.8, 1.8, -1.25, 2.2, ze, 58 - FLATTER, "slate", ridge_axis="y")
    me.xf = K.Matrix.Identity(4)
    cx, cy = x1 + 0.6, y0 + 0.6
    cyl(me, cx, cy, -0.5, ze + 1.2, 1.9, "ashlar", n=12)
    slits_ring(me, cx, cy, 1.9, 4.5, 3, off=-110)
    for zz in (6.0, 8.8):
        for a in (-100, -40, 20):
            me.box(T(cx + 1.93 * math.cos(math.radians(a)), cy + 1.93 * math.sin(math.radians(a)), zz, rz=a),
                   (0.05, 0.6, 1.1), "M_Window_Dim")
    cyl(me, cx, cy, ze + 1.2, ze + 1.5, 2.2, "ashlar", n=12)
    pyramid(me, cx, cy, ze + 1.5, 2.45, 5.2, "slate", n=12)
    rod(me, (cx, cy, ze + 6.6), (cx, cy, ze + 7.6), 0.04, "iron", n=4)
    K.proxy_box(sh, cx - 1.9, cx + 1.9, cy - 1.9, cy + 1.9, -0.5, ze + 1.5)
    return me, sh


def keep():
    """The citadel's keep: a 16 m ashlar tower-house, 20 m to the parapet,
    corbelled round turrets with conical roofs at its corners, a hipped
    roof inside the crenellations, an entrance stair up to a raised door,
    red banners."""
    me, sh = _pair("keep")
    S, zt = 16.0, 20.5
    h = S / 2
    me.box(T(0, 0, 0.5), (S + 1.4, S + 1.4, 2.0), "fieldstone")
    for (ox, oy), al in (((-h, -h), X), ((h, -h), Y), ((h, h), -X), ((-h, h), -Y)):
        # kit.wall cuts one opening per column, so each row of windows is its own band
        low = [(u, u + 1.0, 6.5, 8.1, "window") for u in (3.0, 7.5, 12.0)]
        if al.x > 0.5:
            low = [op for op in low if not 6 < op[0] < 9] + [(7.0, 8.6, 1.5, 4.1, "door")]
        K.wall(me, Vector((ox, oy, 0)), al, S, 1.5, 11.0, sorted(low), "ashlar", frame=False)
        K.wall(me, Vector((ox, oy, 0)), al, S, 11.0, zt, [(u, u + 1.0, 2.0, 3.6, "window") for u in (3.0, 7.5, 12.0)],
               "ashlar", frame=False)
        out = al.cross(Z)
        for u in (0.9, h, S - 0.9):
            p = Vector((ox, oy, 0)) + al * u + out * 0.3
            me.box(T(p.x, p.y, 6.0), (0.9 if abs(al.x) > 0.5 else 0.6, 0.6 if abs(al.x) > 0.5 else 0.9, 11.0), "ashlar")
        for u in (2.0, 5.2, 10.8, 14.0):
            p = Vector((ox, oy, 0)) + al * u + out * 0.02
            slit(me, p.x, p.y, 4.5, math.degrees(math.atan2(out.y, out.x)))
    me.box(T(0, 0, zt + 0.15), (S + 0.8, S + 0.8, 0.3), "ashlar")
    for a, b in (((-h, -h - 0.25), (h, -h - 0.25)), ((h + 0.25, -h), (h + 0.25, h)),
                 ((h, h + 0.25), (-h, h + 0.25)), ((-h - 0.25, h), (-h - 0.25, -h))):
        merlons(me, a, b, zt + 0.3, w=1.0, gap=0.7)
    top = hip(me, -h + 1.4, h - 1.4, -h + 1.4, h - 1.4, zt, 42, "slate", over=0.2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * h, sy * h
            cyl(me, cx, cy, 13.0, 15.0, 1.0, "ashlar", n=10, r1=2.2)
            cyl(me, cx, cy, 15.0, zt + 4.0, 2.2, "ashlar", n=12)
            slits_ring(me, cx, cy, 2.2, zt + 1.0, 4, off=45)
            cyl(me, cx, cy, zt + 4.0, zt + 4.3, 2.5, "ashlar", n=12)
            pyramid(me, cx, cy, zt + 4.3, 2.75, 6.5, "slate", n=12)
            rod(me, (cx, cy, zt + 10.6), (cx, cy, zt + 12.2), 0.05, "iron", n=4)
    for x in (-4.0, 4.0):
        banner(me, x, -h - 0.02, 17.5, 5.5, w=1.3)
    # entrance stair up to the door at z 4.5
    for k in range(12):
        me.box(T(-7.2 + k * 0.5, -h - 1.2, (1.5 + (k + 1) * 0.25) / 2), (0.52, 2.0, 1.5 + (k + 1) * 0.25 + 0.5),
               "ashlar", faces={"+z": "flagstone"})
    me.box(T(-0.6, -h - 1.2, 2.25), (2.2, 2.0, 4.0), "ashlar", faces={"+z": "flagstone"})
    wall_lantern(me, -1.6, -h, 5.6)
    wall_lantern(me, 1.3, -h, 5.6)
    K.proxy_box(sh, -h, h, -h, h, -0.5, zt + 1.2)
    pyramid(sh, 0, 0, zt, S * 0.62, top - zt, "SHADOW")
    return me, sh


def lighthouse():
    """Harbour lighthouse: a tapering ashlar tower banded in white plaster
    on a rock base, a gallery with a railing, a lit lantern room."""
    me, sh = _pair("lighthouse")
    rnd = random.Random(5)
    for k in range(10):
        a = k * math.tau / 10
        r = rnd.uniform(3.6, 4.6)
        s = rnd.uniform(1.6, 2.6)
        me.box(T(r * math.cos(a), r * math.sin(a), 0.2, rz=math.degrees(a)), (s, s * 0.9, 2.2), "fieldstone")
    cyl(me, 0, 0, -1.0, 1.5, 4.2, "fieldstone", n=12, top="flagstone")
    H, r0, r1 = 20.0, 3.0, 2.1
    rr = lambda z: r0 + (r1 - r0) * (z - 1.5) / (H - 1.5)
    cyl(me, 0, 0, 1.5, H, r0, "ashlar", n=14, r1=r1)
    for zb in (6.0, 11.5, 16.0):
        cyl(me, 0, 0, zb, zb + 1.4, rr(zb) + 0.04, "plaster", n=14, r1=rr(zb + 1.4) + 0.04)
    for k, zz in enumerate((3.6, 8.6, 13.4, 17.6)):
        a = -90 + (k % 2) * 60 - 30
        me.box(T((rr(zz) + 0.02) * math.cos(math.radians(a)), (rr(zz) + 0.02) * math.sin(math.radians(a)), zz, rz=a),
               (0.06, 0.5, 0.9), "M_Window_Dim")
    me.box(T(0, -r0 - 0.02, 2.6), (1.0, 0.1, 2.1), "planks")
    for k in range(10):
        a = k * 36
        me.box(T(2.25 * math.cos(math.radians(a)), 2.25 * math.sin(math.radians(a)), H - 0.3, rz=a), (0.9, 0.3, 0.5),
               "ashlar")
    cyl(me, 0, 0, H, H + 0.3, 3.1, "flagstone", n=14)
    for k in range(16):
        a = k * math.tau / 16
        rod(me, (3.0 * math.cos(a), 3.0 * math.sin(a), H + 0.3), (3.0 * math.cos(a), 3.0 * math.sin(a), H + 1.3),
            0.04, "iron", n=4)
    for k in range(16):
        a, b = k * math.tau / 16, (k + 1) * math.tau / 16
        K.beam(me, (3.0 * math.cos(a), 3.0 * math.sin(a), H + 1.3), (3.0 * math.cos(b), 3.0 * math.sin(b), H + 1.3),
               0.06, 0.06, mat="iron")
    cyl(me, 0, 0, H + 0.3, H + 0.9, 1.6, "ashlar", n=8)
    cyl(me, 0, 0, H + 0.9, H + 3.1, 1.45, "M_Lamp", n=8)
    for k in range(8):
        a = k * 45 + 22.5
        me.box(T(1.47 * math.cos(math.radians(a)), 1.47 * math.sin(math.radians(a)), H + 2.0, rz=a),
               (0.08, 0.12, 2.2), "iron")
    pyramid(me, 0, 0, H + 3.1, 1.95, 1.8, "iron", n=8, rot=22.5)
    rod(me, (0, 0, H + 4.9), (0, 0, H + 5.6), 0.06, "iron", n=4)
    cyl(me, 0, 0, H + 5.6, H + 5.9, 0.2, "iron", n=6)
    # the keeper's cottage against it
    me.xf = T(4.2, 1.6, 1.5, rz=90)
    sh.xf = me.xf
    house(me, 4.0, 3.4, 1, ground="plaster", cover="slate", pitch=48, ridge="x", fh=2.4, door=1.4,
          chimneys=((1.2, 0.6),), sh=sh)
    me.xf = K.Matrix.Identity(4)
    sh.xf = me.xf
    cyl(sh, 0, 0, -1.0, H + 3.0, 2.8, "SHADOW", n=8)
    return me, sh


def windmill():
    """A whitewashed tower mill: tapering octagonal body on a stone plinth,
    a shingled cap, four lattice sails (their own object, SAILS_windmill,
    so the game can turn them), a door and small windows."""
    me, sh = _pair("windmill")
    cyl(me, 0, 0, -0.5, 1.4, 3.6, "fieldstone", n=8, rot=22.5)
    cyl(me, 0, 0, 1.4, 10.5, 3.2, "plaster", n=8, r1=2.3, rot=22.5)
    for zz in (4.0, 7.5):
        rr = 3.2 + (2.3 - 3.2) * (zz - 1.4) / 9.1
        for a in (-90, 0, 180):
            ap = a + 0.0
            me.box(T((rr * 0.93) * math.cos(math.radians(ap)), (rr * 0.93) * math.sin(math.radians(ap)), zz, rz=ap),
                   (0.12, 0.6, 0.8), "M_Window_Dim")
    me.box(T(0, -3.25, 2.5), (1.1, 0.4, 2.2), "planks")
    me.box(T(0, -3.3, 3.75), (1.4, 0.5, 0.2), "timber")
    cyl(me, 0, 0, 5.2, 5.4, 3.9, "planks", n=8, rot=22.5)
    for k in range(8):
        a = math.radians(22.5 + k * 45)
        K.beam(me, (2.9 * math.cos(a), 2.9 * math.sin(a), 4.0), (3.8 * math.cos(a), 3.8 * math.sin(a), 5.2), 0.12, 0.12)
    cyl(me, 0, 0, 10.5, 11.0, 2.6, "timber", n=10)
    pyramid(me, 0, 0, 11.0, 2.7, 2.6, "shingle", n=10)
    rod(me, (0, -1.5, 11.2), (0, -3.6, 11.1), 0.3, "timber")
    sails = K.Mesh("SAILS_windmill")
    hub = Vector((0, -3.7, 11.1))
    rod(sails, hub + Y * 0.3, hub - Y * 0.3, 0.45, "timber", n=8)
    for k in range(4):
        a = math.radians(45 + k * 90)
        d = Vector((math.cos(a), 0, math.sin(a)))
        side = Vector((-d.z, 0, d.x))
        K.beam(sails, hub, hub + d * 8.4, 0.24, 0.24, up=(0, 1, 0))
        for j in range(8):
            p = hub + d * (1.8 + j * 0.85)
            K.beam(sails, p, p + side * 1.7, 0.07, 0.07, up=(0, 1, 0))
        K.beam(sails, hub + d * 1.8 + side * 1.7, hub + d * 8.2 + side * 1.7, 0.09, 0.09, up=(0, 1, 0))
        c = hub + d * 5.0 + side * 0.9 - Y * 0.08
        sails.box(K.Matrix.Translation(c) @ K.Matrix.Rotation(-a, 4, "Y"), (6.2, 0.03, 1.6), "cloth_cream")
    K.proxy_box(sh, -3.0, 3.0, -3.0, 3.0, -0.5, 13.5)
    return me, sh, sails


def barn():
    """A big plank barn, gable end to the yard with tall double doors, a
    hay loft door above, a shingle roof."""
    me, sh = _pair("barn")
    ridge, (x0, x1, y0, y1), ze = house(me, 8.6, 12.0, 1, ground="planks", cover="shingle", pitch=50, ridge="y", dormers=(),
                                        fh=4.2, front=[(2.6, 6.0, 0.0, 3.6, "door")], spacing=2.8, sh=sh,
                                        gable_win=False)
    me.box(T(0, y0 - 0.1, ze + 1.6), (1.4, 0.12, 1.4), "planks")
    K.beam(me, (0, y0 + 0.3, ze + 3.0), (0, y0 - 1.1, ze + 3.0), 0.2, 0.2)
    for s in (-1, 1):
        K.beam(me, (s * 1.7, y0 - 0.04, 0.6), (s * 0.05, y0 - 0.04, 3.9), 0.12, 0.1, mat="timber")
    for x, y in ((-5.4, -2.0), (-5.5, 0.4), (-5.3, 2.8)):
        cyl(me, x, y, 0.0, 1.2, 0.7, "thatch", n=10)
    return me, sh


def watchtower():
    """A stone watchtower with a timber lookout under a pyramid roof."""
    me, sh = _pair("watchtower")
    S = 4.4
    me.box(T(0, 0, 4.25), (S, S, 9.5), "fieldstone")
    me.box(T(0, 0, 0.3), (S + 0.6, S + 0.6, 1.6), "fieldstone")
    me.box(T(0, -S / 2 - 0.01, 1.6), (1.0, 0.08, 2.0), "planks")
    for zz in (4.0, 7.0):
        for rz, (x, y) in ((-90, (0, -S / 2)), (0, (S / 2, 0)), (180, (-S / 2, 0))):
            slit(me, x, y, zz, rz)
    me.box(T(0, 0, 9.1), (S + 1.2, S + 1.2, 0.2), "planks")
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.beam(me, (sx * (S / 2 + 0.4), sy * (S / 2 + 0.4), 9.2), (sx * (S / 2 + 0.4), sy * (S / 2 + 0.4), 11.8))
            K.beam(me, (sx * S / 2, sy * S / 2, 7.6), (sx * (S / 2 + 0.4), sy * (S / 2 + 0.4), 9.0), 0.14, 0.14)
    for zz in (9.7, 10.3):
        for a, b in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            K.beam(me, (a[0] * (S / 2 + 0.4), a[1] * (S / 2 + 0.4), zz), (b[0] * (S / 2 + 0.4), b[1] * (S / 2 + 0.4), zz),
                   0.1, 0.1)
    cyl(me, 0, 0, 9.2, 10.0, 0.4, "iron", n=8, r1=0.5)
    me.box(T(0, 0, 10.05), (0.7, 0.7, 0.1), "M_Lamp")
    pyramid(me, 0, 0, 11.8, (S / 2 + 1.1) * 1.414, 3.4, "shingle")
    K.proxy_box(sh, -S / 2, S / 2, -S / 2, S / 2, -0.5, 11.8)
    return me, sh


def tower_round():
    """A round wall tower: ashlar drum, string course, arrow slits in three
    rows, a corbelled parapet under a conical slate roof, doors to the wall
    walk on both flanks (+-X)."""
    me, sh = _pair("tower_round")
    r = 3.2
    cyl(me, 0, 0, -0.5, 1.5, r + 0.5, "ashlar_big", n=14, r1=r)
    cyl(me, 0, 0, 1.5, 13.0, r, "ashlar_big", n=14)
    cyl(me, 0, 0, 8.8, 9.1, r + 0.12, "ashlar_big", n=14)
    for zz, off in ((3.5, -90), (6.5, -60), (11.0, -90)):
        slits_ring(me, 0, 0, r, zz, 4, off=off)
    for s in (-1, 1):
        me.box(T(s * (r - 0.05), 0, 10.3), (0.2, 1.0, 2.0), "planks")
    for k in range(14):
        a = k * 360 / 14
        me.box(T((r + 0.15) * math.cos(math.radians(a)), (r + 0.15) * math.sin(math.radians(a)), 12.8, rz=a),
               (0.35, 0.5, 0.45), "ashlar_big")
    cyl(me, 0, 0, 13.0, 14.0, r + 0.35, "ashlar_big", n=14)
    pyramid(me, 0, 0, 14.0, r + 0.75, 6.0, "slate", n=14)
    rod(me, (0, 0, 20.0), (0, 0, 21.5), 0.05, "iron", n=4)
    me.box(T(0.45, 0, 21.2), (0.8, 0.03, 0.5), "cloth_red")
    cyl(sh, 0, 0, -0.5, 14.0, r, "SHADOW", n=8)
    pyramid(sh, 0, 0, 14.0, r + 0.7, 6.0, "SHADOW", n=8)
    return me, sh


def tower_square():
    """A square wall tower: battered base, machicolations, crenellated
    parapet, a flag."""
    me, sh = _pair("tower_square")
    S = 6.0
    me.box(T(0, 0, 0.5), (S + 1.0, S + 1.0, 2.0), "ashlar_big")
    me.box(T(0, 0, 6.5), (S, S, 11.0), "ashlar_big", faces={"+z": "flagstone"})
    for zz in (4.0, 8.0):
        for rz, (x, y) in ((-90, (0, -S / 2)), (0, (S / 2, 0)), (180, (-S / 2, 0)), (90, (0, S / 2))):
            slit(me, x, y, zz, rz)
    for i in range(4):
        rz = i * 90
        a = math.radians(rz)
        o, u = Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))
        for k in range(7):
            p = o * (S / 2 + 0.2) + u * (-S / 2 + 0.45 + k * (S - 0.9) / 6)
            me.box(T(p.x, p.y, 11.6, rz=rz), (0.4, 0.35, 0.5), "ashlar_big")
        p = o * (S / 2 + 0.25)
        me.box(T(p.x, p.y, 12.4, rz=rz), (0.5, S + 1.0, 1.0), "ashlar_big")
        a0 = o * (S / 2 + 0.25) - u * (S / 2 + 0.5)
        a1 = o * (S / 2 + 0.25) + u * (S / 2 + 0.5)
        merlons(me, (a0.x, a0.y), (a1.x, a1.y), 12.9, w=0.8, gap=0.6)
    rod(me, (1.8, 1.8, 12.0), (1.8, 1.8, 17.0), 0.06, "iron", n=4)
    me.box(T(1.8 + 0.9, 1.8, 16.4), (1.7, 0.03, 1.0), "cloth_red")
    K.proxy_box(sh, -S / 2, S / 2, -S / 2, S / 2, -0.5, 13.4)
    return me, sh


def gatehouse():
    """A city gate: two round towers with conical roofs flank an arched
    passage under a crenellated gate block; portcullis half raised, the
    doors open inward, banners, lanterns."""
    me, sh = _pair("gatehouse")
    gx, gy, gz = 3.3, 3.2, 10.0
    me.box(T(-2.55, 0, 4.75), (1.5, 2 * gy, 10.5), "ashlar_big")
    me.box(T(2.55, 0, 4.75), (1.5, 2 * gy, 10.5), "ashlar_big")
    arch_fill(me, -1.8, 1.8, -gy, gy, 3.8, 1.8, gz, n=8)
    me.box(T(0, 0, -0.05), (3.6, 2 * gy, 0.3), "cobble")
    me.box(T(0, 0, gz + 0.15), (2 * gx + 0.4, 2 * gy + 0.4, 0.3), "ashlar_big", faces={"+z": "flagstone"})
    for yy in (-gy - 0.2, gy + 0.2):
        merlons(me, (-gx, yy), (gx, yy), gz + 0.3)
    for k in range(6):
        me.box(T(-2.8 + k * 1.12, -gy - 0.2, gz - 0.35), (0.35, 0.4, 0.5), "ashlar_big")
    for k in range(9):
        K.beam(me, (-1.6 + k * 0.4, -1.4, 2.6), (-1.6 + k * 0.4, -1.4, 5.4), 0.08, 0.08, mat="iron")
        pyramid(me, -1.6 + k * 0.4, -1.4, 2.4, 0.06, 0.25, "iron")
    for zz in (2.9, 3.6, 4.3, 5.0):
        K.beam(me, (-1.7, -1.4, zz), (1.7, -1.4, zz), 0.06, 0.06, mat="iron")
    for s in (-1, 1):
        me.box(T(s * 1.72, 0.6, 1.8, rz=s * 80), (1.7, 0.12, 3.5), "planks", axis=(0, 0, 1))
    for s in (-1, 1):
        cx = s * 5.6
        cyl(me, cx, 0.3, -0.5, 1.5, 3.4, "ashlar_big", n=14, r1=3.0)
        cyl(me, cx, 0.3, 1.5, 13.0, 3.0, "ashlar_big", n=14)
        slits_ring(me, cx, 0.3, 3.0, 5.0, 3, off=-90 - 45 * s)
        slits_ring(me, cx, 0.3, 3.0, 9.0, 3, off=-90 + 30 * s)
        cyl(me, cx, 0.3, 13.0, 14.0, 3.35, "ashlar_big", n=14)
        pyramid(me, cx, 0.3, 14.0, 3.75, 6.2, "slate", n=14)
        rod(me, (cx, 0.3, 20.2), (cx, 0.3, 21.8), 0.05, "iron", n=4)
        me.box(T(cx + 0.45, 0.3, 21.5), (0.8, 0.03, 0.5), "cloth_red")
        banner(me, s * 2.55, -gy - 0.02, 8.6, 3.6)
        wall_lantern(me, s * 2.2, -gy, 3.6)
    K.proxy_box(sh, -gx, gx, -gy, gy, -0.5, gz + 1.0)
    for s in (-1, 1):
        cyl(sh, s * 5.6, 0.3, -0.5, 14.0, 3.0, "SHADOW", n=8)
        pyramid(sh, s * 5.6, 0.3, 14.0, 3.7, 6.2, "SHADOW", n=8)
    return me, sh


def water_gate():
    """The south water gate: an arch over the harbour channel carrying a
    crenellated gallery, a portcullis hanging over the water, a turret on
    each pier."""
    me, sh = _pair("water_gate")
    span, pw, dy, zt = 11.0, 3.2, 3.0, 9.0
    for s in (-1, 1):
        cx = s * (span / 2 + pw / 2)
        me.box(T(cx, 0, (zt - 2.5) / 2), (pw, 2 * dy, zt + 2.5), "ashlar_big")
        me.prism(Vector((cx - pw / 2, -dy, -2.5)), X, Z, [(0, 0), (pw, 0), (pw, 4.0), (0, 4.0)], -0.01, "ashlar_big")
        cyl(me, cx, 0, zt, zt + 5.0, 2.0, "ashlar_big", n=12)
        cyl(me, cx, 0, zt + 5.0, zt + 5.6, 2.25, "ashlar_big", n=12)
        pyramid(me, cx, 0, zt + 5.6, 2.5, 4.5, "slate", n=12)
        slits_ring(me, cx, 0, 2.0, zt + 2.5, 3, off=-90)
        me.box(T(cx, -dy - 0.02, 1.0), (pw + 0.1, 0.1, 1.6), "moss")
    arch_fill(me, -span / 2, span / 2, -dy, dy, 1.5, 4.8, zt, n=12)
    me.box(T(0, 0, zt + 0.15), (span + 2 * pw, 2 * dy + 0.3, 0.3), "ashlar_big", faces={"+z": "flagstone"})
    for yy in (-dy - 0.1, dy + 0.1):
        merlons(me, (-span / 2 - pw, yy), (span / 2 + pw, yy), zt + 0.3)
    for k in range(20):
        x = -4.75 + k * 0.5
        K.beam(me, (x, -1.0, 2.4), (x, -1.0, 6.0), 0.1, 0.1, mat="iron")
        pyramid(me, x, -1.0, 2.1, 0.08, 0.35, "iron")
    for zz in (2.8, 3.6, 4.4, 5.2):
        K.beam(me, (-4.9, -1.0, zz), (4.9, -1.0, zz), 0.08, 0.08, mat="iron")
    for s in (-1, 1):
        banner(me, s * 3.0, -dy - 0.02, zt - 0.4, 2.8, mat="cloth_blue")
    K.proxy_box(sh, -span / 2 - pw, span / 2 + pw, -dy, dy, 5.5, zt + 1.0)
    return me, sh


# ---------------------------------------------------------------------------
# fortification, ground and water
# ---------------------------------------------------------------------------

def wall_run():
    """8 m of curtain wall, outer face -Y: battered base, 9 m of ashlar,
    arrow slits, a wall-walk with a crenellated outer parapet and a low
    inner one. Tiles end to end along x."""
    me, sh = _pair("wall_run")
    L, t, H = 8.0, 2.6, 9.0
    me.box(T(0, 0, 0.5), (L, t + 0.8, 3.0), "ashlar_big")
    me.box(T(0, 0, H / 2), (L, t, H + 1.0), "ashlar_big", faces={"+z": "flagstone"})
    me.box(T(0, -t / 2 + 0.2, H + 0.45), (L, 0.4, 0.9), "ashlar_big")
    merlons(me, (-L / 2, -t / 2 + 0.2), (L / 2, -t / 2 + 0.2), H + 0.9, w=0.9, gap=0.65, t=0.4)
    me.box(T(0, t / 2 - 0.15, H + 0.25), (L, 0.3, 0.5), "ashlar_big")
    for x in (-2.5, 2.5):
        slit(me, x, -t / 2, 5.0, -90)
    for k in range(6):
        me.box(T(-3.35 + k * 1.34, -t / 2 - 0.12, H - 0.2), (0.3, 0.3, 0.4), "ashlar_big")
    me.box(T(-1.0, -t / 2 - 0.02, 2.0), (1.2, 0.05, 3.0), "moss")
    DT.stone_face(me, random.Random(1308), (-L / 2, -t / 2, 0), (1, 0, 0), L, 2.0, H - 0.4)
    K.proxy_box(sh, -L / 2, L / 2, -t / 2, t / 2, -0.5, H + 1.7)
    return me, sh


def wall_corner():
    """A square bastion where the wall turns: a step taller than the wall,
    crenellated on all sides, a lantern on the walk."""
    me, sh = _pair("wall_corner")
    S, H = 5.0, 10.5
    me.box(T(0, 0, 0.5), (S + 0.8, S + 0.8, 3.0), "ashlar_big")
    me.box(T(0, 0, H / 2), (S, S, H + 1.0), "ashlar_big", faces={"+z": "flagstone"})
    c = S / 2 + 0.1
    for a, b in (((-c, -c), (c, -c)), ((c, -c), (c, c)), ((c, c), (-c, c)), ((-c, c), (-c, -c))):
        merlons(me, a, b, H, w=0.8, gap=0.6, t=0.4)
    for rz, (x, y) in ((-90, (0, -S / 2)), (0, (S / 2, 0))):
        slit(me, x, y, 6.0, rz)
    rod(me, (1.5, 1.5, H), (1.5, 1.5, H + 2.2), 0.06, "iron", n=4)
    me.box(T(1.5, 1.5, H + 2.3), (0.3, 0.3, 0.4), "M_Lamp")
    wr = random.Random(1328)
    DT.stone_face(me, wr, (-S / 2, -S / 2, 0), (1, 0, 0), S, 2.0, H - 0.3, blocks=10)
    DT.stone_face(me, wr, (S / 2, -S / 2, 0), (0, 1, 0), S, 2.0, H - 0.3, blocks=10, ivy_h=0)
    K.proxy_box(sh, -S / 2, S / 2, -S / 2, S / 2, -0.5, H + 0.8)
    return me, sh


def retaining_tall(h):
    """A terrace retaining wall `h` high, 6 m long, face -Y: ashlar with
    stepped buttresses, a flagstone cap, drain spouts and moss streaks."""
    def make():
        me, sh = _pair(f"retaining_{int(h)}")
        L, t = 6.0, 1.2
        me.box(T(0, 0, (h - 0.5) / 2), (L, t, h + 0.5), "ashlar_big")
        me.box(T(0, -0.1, h + 0.1), (L, t + 0.3, 0.2), "flagstone")
        for x in (-L / 2 + 0.4, L / 2 - 0.4):
            me.box(T(x, -t / 2 - 0.35, h * 0.3), (0.8, 0.7, h * 0.6 + 0.5), "ashlar_big")
            me.box(T(x, -t / 2 - 0.2, h * 0.7), (0.7, 0.4, h * 0.4), "ashlar_big")
        for x in (-1.0, 1.4):
            me.box(T(x, -t / 2 - 0.2, h * 0.35), (0.2, 0.4, 0.2), "iron")
            me.box(T(x, -t / 2 - 0.01, h * 0.18), (0.35, 0.03, h * 0.34), "moss")
        me.box(T(0, -t / 2 - 0.01, h - 0.4), (L - 1.6, 0.03, 0.5), "moss")
        DT.stone_face(me, random.Random(int(h * 100)), (-L / 2 + 0.85, -t / 2, 0), (1, 0, 0), L - 1.7, 0.3, h - 0.2,
                      blocks=int(h * 1.5), ivy_h=0.6)
        K.proxy_box(sh, -L / 2, L / 2, -t / 2, t / 2, -0.5, h + 0.2)
        return me, sh
    make.__name__ = f"retaining_{int(h)}"
    return make


def grand_stair():
    """The stair up to a higher terrace: 5 m wide, 20 steps with a landing,
    balustraded both sides, rising toward +Y."""
    me, sh = _pair("grand_stair")
    W, rise, tread = 5.0, 0.3, 0.45
    y, z = 0.0, 0.0
    for k in range(20):
        if k == 10:
            me.box(T(0, y + 1.25, (z - 0.5) / 2), (W, 2.5, z + 0.5), "ashlar", faces={"+z": "flagstone"})
            for s in (-1, 1):
                me.box(T(s * (W / 2 + 0.2), y + 1.25, (z + 0.9 - 0.5) / 2), (0.4, 2.5, z + 1.4), "ashlar")
                cyl(me, s * (W / 2 + 0.2), y + 1.25, z + 0.9, z + 1.2, 0.3, "ashlar", n=8)
            y += 2.5
        z += rise
        me.box(T(0, y + tread / 2, (z - 0.5) / 2), (W, tread, z + 0.5), "ashlar", faces={"+z": "flagstone"})
        for s in (-1, 1):
            me.box(T(s * (W / 2 + 0.2), y + tread / 2, (z + 0.9 - 0.5) / 2), (0.4, tread, z + 1.4), "ashlar",
                   faces={"+z": "flagstone"})
        y += tread
    for s in (-1, 1):
        cyl(me, s * (W / 2 + 0.2), 0.2, 0.0, 1.3, 0.32, "ashlar", n=8)
        pyramid(me, s * (W / 2 + 0.2), 0.2, 1.3, 0.35, 0.5, "ashlar", n=8)
    K.proxy_box(sh, -W / 2 - 0.4, W / 2 + 0.4, 0, y, -0.5, z)
    return me, sh


def ramp():
    """A cobbled cart ramp rising 3 m over 12 m toward +Y, curbed."""
    me, sh = _pair("ramp")
    W, L, H = 3.6, 12.0, 3.0
    me.prism(Vector((W / 2, 0, 0)), Y, Z, [(0, -0.5), (L, -0.5), (L, H), (0, 0)], W, "ashlar")
    ang = math.degrees(math.atan2(H, L))
    me.box(T(0, L / 2, H / 2 + 0.06, rx=ang), (W - 0.1, math.hypot(L, H), 0.1), "cobble")
    for s in (-1, 1):
        me.prism(Vector((s * (W / 2 + 0.2) + 0.2, 0, 0)), Y, Z, [(0, 0), (L, H), (L, H + 0.5), (0, 0.5)], 0.4, "ashlar")
    K.proxy_box(sh, -W / 2, W / 2, 0, L, -0.5, H / 2)
    return me, sh


def _bridge(name, spans, span_w, rise, width, deck):
    me, sh = _pair(name)
    pier = 2.2
    total = spans * span_w + (spans - 1) * pier
    x = -total / 2
    y0, y1 = -width / 2, width / 2
    for i in range(spans):
        arch_fill(me, x, x + span_w, y0, y1, deck - 0.6 - rise, rise, deck - 0.35, n=10)
        x += span_w
        if i < spans - 1:
            me.box(T(x + pier / 2, 0, (deck - 0.35 - 3.0) / 2), (pier, width, deck - 0.35 + 3.0), "ashlar")
            for s in (-1, 1):
                me.prism(Vector((x, s * width / 2, -3.0)), X, Y, [(0, 0), (pier, 0), (pier / 2, s * 1.4)],
                         -(deck - 0.6 - rise + 3.0 + 1.0), "ashlar")
            x += pier
    for s in (-1, 1):
        me.box(T(s * (total / 2 + 1.5), 0, (deck - 0.35 - 3.0) / 2), (3.0, width + 0.6, deck - 0.35 + 3.0), "ashlar")
    L = total + 6.0
    me.box(T(0, 0, deck - 0.2), (L, width, 0.3), "ashlar", faces={"+z": "cobble"})
    for s in (-1, 1):
        me.box(T(0, s * (width / 2 - 0.18), deck + 0.45), (L, 0.36, 1.0), "ashlar")
        me.box(T(0, s * (width / 2 - 0.18), deck + 1.0), (L, 0.5, 0.12), "flagstone")
    # the detail rollout (2026-09-30): caps along the parapets, vines trailing over
    # the side, moss on the caps, a lantern on each abutment
    rnd = random.Random(len(name) * 31 + spans)
    for s in (-1, 1):
        nc = int(L / 3.0)
        for k in range(nc + 1):
            x = -L / 2 + 0.3 + k * (L - 0.6) / nc
            me.box(T(x, s * (width / 2 - 0.18), deck + 1.16), (0.6, 0.62, 0.22), "ashlar")
            if rnd.random() < 0.35:
                me.box(T(x, s * (width / 2 - 0.18), deck + 1.3, rz=rnd.uniform(0, 90)), (0.36, 0.3, 0.07), "moss")
        for _ in range(int(L / 2.5)):
            x = rnd.uniform(-L / 2 + 1, L / 2 - 1)
            ln = rnd.uniform(0.8, 2.6)
            DT.hanging_vine(me, rnd, (x, s * (width / 2), deck + 0.95), (0, s, 0), ln)
        for e in (-1, 1):
            x = e * (total / 2 + 1.5)
            rod(me, (x, s * (width / 2 - 0.18), deck + 1.27), (x, s * (width / 2 - 0.18), deck + 2.5), 0.07, "iron", n=6)
            me.box(T(x, s * (width / 2 - 0.18), deck + 2.7), (0.26, 0.26, 0.36), "M_Lamp")
            me.box(T(x, s * (width / 2 - 0.18), deck + 2.92), (0.34, 0.34, 0.06), "iron")
    K.proxy_box(sh, -L / 2, L / 2, y0, y1, deck - 1.2, deck + 1.0)
    return me, sh


def bridge_arch():
    """A single stone arch over the river: 14 m span, 4.5 m wide."""
    return _bridge("bridge_arch", 1, 14.0, 4.2, 4.5, 5.2)


def bridge_long():
    """The long west bridge: three arches with cutwater piers."""
    return _bridge("bridge_long", 3, 9.0, 3.4, 5.0, 4.6)


def quay_wall():
    """8 m of harbour quay, water side -Y: an ashlar face down past the
    waterline with a moss band, a flagstone top, coping, mooring rings,
    two bollards and water stairs."""
    me, sh = _pair("quay_wall")
    me.box(T(0, 0, 0.0), (8.0, 4.0, 5.0), "ashlar_big", faces={"+z": "flagstone"})
    me.box(T(0, -2.05, 2.4), (8.0, 0.3, 0.25), "ashlar_big")
    me.box(T(0, -2.02, 0.1), (8.0, 0.05, 0.8), "moss")
    for x in (-2.5, 1.0):
        for k in range(6):
            a, b = k * math.tau / 6, (k + 1) * math.tau / 6
            K.beam(me, (x + 0.2 * math.cos(a), -2.12, 1.6 + 0.2 * math.sin(a)),
                   (x + 0.2 * math.cos(b), -2.12, 1.6 + 0.2 * math.sin(b)), 0.05, 0.05, mat="iron")
    for x in (-3.2, 0.0):
        cyl(me, x, -1.4, 2.5, 3.2, 0.25, "iron", n=8, r1=0.2)
        cyl(me, x, -1.4, 3.2, 3.35, 0.32, "iron", n=8)
    for k in range(7):
        me.box(T(2.6 + k * 0.2, -2.6, 2.3 - k * 0.35), (0.5, 1.0, 0.35), "ashlar_big", faces={"+z": "flagstone"})
    rnd = random.Random(1320)
    DT.stone_face(me, rnd, (-4.0, -2.0, 0), (1, 0, 0), 5.6, 0.2, 2.3, course=0.7, blocks=8, streaks=3, ivy_h=0)
    _barrel(me, -1.4, 0.6, 2.5)
    _barrel(me, -0.8, 1.1, 2.5)
    _crate(me, 1.6, 0.9, 2.5, 0.7, 10)
    _crate(me, 1.6, 0.9, 3.2, 0.5, 35)
    _sack(me, 2.4, 0.5, 2.5, rz=20)
    for k in range(12):
        a, b = k * math.tau / 12, (k + 1) * math.tau / 12
        K.beam(me, (-2.8 + 0.35 * math.cos(a), 0.9 + 0.35 * math.sin(a), 2.56), (-2.8 + 0.35 * math.cos(b), 0.9 + 0.35 * math.sin(b), 2.56),
               0.08, 0.08, mat="thatch")
    rod(me, (3.6, 1.6, 2.5), (3.6, 1.6, 4.9), 0.08, "timber", n=6)
    wall_lantern(me, 3.6, 1.6, 4.8, rz=-90)
    K.proxy_box(sh, -4, 4, -2, 2, -2.5, 2.5)
    return me, sh


def pier():
    """A wooden jetty 12 m out over the water (-Y): plank deck on log piles
    with cross bracing, bollards, a ladder and a lamp at the end."""
    me, sh = _pair("pier")
    Lp, W, dz = 12.0, 3.0, 1.2
    me.box(T(0, -Lp / 2, dz), (W, Lp, 0.16), "planks", axis=(1, 0, 0))
    for s in (-1, 1):
        K.beam(me, (s * (W / 2 - 0.1), 0, dz - 0.18), (s * (W / 2 - 0.1), -Lp, dz - 0.18), 0.2, 0.22)
    for k in range(7):
        y = -0.3 - k * (Lp - 0.6) / 6
        for s in (-1, 1):
            rod(me, (s * (W / 2 - 0.05), y, -2.5), (s * (W / 2 - 0.05), y, dz + (0.5 if k == 6 else 0.0)), 0.16, "bark", n=8)
        if k % 2 == 0:
            K.beam(me, (-W / 2, y, -1.0), (W / 2, y, dz - 0.3), 0.1, 0.1)
    for s in (-1, 1):
        cyl(me, s * 1.0, -Lp + 0.4, dz + 0.08, dz + 0.6, 0.16, "iron", n=8)
    for k in range(6):
        K.beam(me, (-0.3, -Lp - 0.08, dz - 0.3 * k), (0.3, -Lp - 0.08, dz - 0.3 * k), 0.05, 0.05)
    for s in (-1, 1):
        K.beam(me, (s * 0.3, -Lp - 0.08, dz + 0.1), (s * 0.3, -Lp - 0.08, -1.0), 0.07, 0.07)
    rod(me, (W / 2 - 0.2, -Lp + 1.2, dz), (W / 2 - 0.2, -Lp + 1.2, dz + 2.6), 0.08, "timber", n=6)
    # the detail rollout (2026-09-30): weed on the piles, cargo, nets hung to dry
    for k in range(7):
        y = -0.3 - k * (Lp - 0.6) / 6
        for s in (-1, 1):
            cyl(me, s * (W / 2 - 0.05), y, -0.15, 0.3, 0.19, "moss", n=8)
    _crate(me, -0.7, -2.5, dz + 0.08, 0.6, 12)
    _barrel(me, -0.9, -3.4, dz + 0.08)
    _sack(me, 0.6, -2.3, dz + 0.08, rz=30)
    for k in range(3):
        me.box(T(-W / 2 - 0.02, -5.5 - k * 1.3, dz - 0.35), (0.04, 1.1, 0.75), "bark")
        me.box(T(-W / 2 - 0.05, -5.5 - k * 1.3, dz - 0.72), (0.08, 0.12, 0.12), "cloth_red")
    wall_lantern(me, W / 2 - 0.2, -Lp + 1.2, dz + 2.5, rz=180)
    K.proxy_box(sh, -W / 2, W / 2, -Lp, 0, dz - 0.3, dz + 0.1)
    return me, sh


def harbour_arm():
    """12 m of breakwater: a rubble base sloping into the sea, a flagstone
    walk on top, a crenellated parapet on the sea side (-Y)."""
    me, sh = _pair("harbour_arm")
    rnd = random.Random(3)
    me.prism(Vector((6.0, 0, 0)), Y, Z, [(-4.5, -2.5), (4.5, -2.5), (2.0, 2.0), (-2.0, 2.0)], 12.0, "fieldstone",
             back="fieldstone")
    me.box(T(0, 0, 2.1), (12.0, 4.2, 0.2), "flagstone")
    me.box(T(0, -1.9, 2.75), (12.0, 0.45, 1.1), "ashlar_big")
    merlons(me, (-6.0, -1.9), (6.0, -1.9), 3.3, w=0.9, gap=0.7, t=0.45)
    for _ in range(14):
        s = rnd.uniform(0.7, 1.3)
        x = rnd.uniform(-5.5, 5.5)
        me.box(T(x, -3.6 - rnd.uniform(0, 0.8), -0.2 + rnd.uniform(0, 0.3), rz=rnd.uniform(0, 60)), (s, s * 0.9, s * 0.8),
               "fieldstone")
    for _ in range(18):                                  # weed at the waterline (2026-09-30)
        s_ = rnd.uniform(0.4, 0.9)
        me.box(T(rnd.uniform(-5.8, 5.8), -3.3 - rnd.uniform(0, 1.0), 0.15, rz=rnd.uniform(0, 90)), (s_, s_ * 0.8, 0.12), "moss")
    rod(me, (5.2, 0.8, 2.2), (5.2, 0.8, 5.0), 0.1, "timber", n=6)
    me.box(T(5.2, 0.8, 5.25), (0.4, 0.4, 0.5), "M_Lamp")
    me.box(T(5.2, 0.8, 5.55), (0.5, 0.5, 0.08), "iron")
    for k in range(12):
        a, b = k * math.tau / 12, (k + 1) * math.tau / 12
        K.beam(me, (-3.5 + 0.35 * math.cos(a), 1.0 + 0.35 * math.sin(a), 2.26), (-3.5 + 0.35 * math.cos(b), 1.0 + 0.35 * math.sin(b), 2.26),
               0.08, 0.08, mat="thatch")
    K.proxy_box(sh, -6, 6, -4.5, 4.5, -2.5, 2.2)
    return me, sh


def chain_boom():
    """The chain across the harbour mouth: two banded stone posts and a
    sagging iron chain of alternating links between them."""
    me, sh = _pair("chain_boom")
    span = 12.0
    for s in (-1, 1):
        cyl(me, s * span / 2, 0, -0.5, 2.6, 0.55, "ashlar", n=10)
        cyl(me, s * span / 2, 0, 1.8, 2.0, 0.6, "iron", n=10)
        cyl(me, s * span / 2, 0, 2.6, 2.9, 0.65, "ashlar", n=10)
        cyl(me, s * span / 2, 0, -0.2, 0.5, 0.58, "moss", n=10)
        rod(me, (s * span / 2, 0, 2.9), (s * span / 2, 0, 3.9), 0.06, "iron", n=6)
        me.box(T(s * span / 2, 0, 4.1), (0.26, 0.26, 0.34), "M_Lamp")
        me.box(T(s * span / 2, 0, 4.31), (0.34, 0.34, 0.06), "iron")
    n = 36
    for k in range(n):
        x = -span / 2 + 0.6 + k * (span - 1.2) / (n - 1)
        z = 2.3 - 1.4 * (1 - (2 * x / span) ** 2)
        if k % 2:
            me.box(T(x, 0, z), (0.36, 0.06, 0.2), "iron")
        else:
            me.box(T(x, 0, z), (0.36, 0.2, 0.06), "iron")
    K.proxy_box(sh, -span / 2 - 0.5, span / 2 + 0.5, -0.5, 0.5, -0.5, 2.9)
    return me, sh


def waterfall():
    """A 10 m waterfall: a rock lip, the falling sheet bowing out as it
    drops, rock walls either side, foam where it lands. The water is its own
    surface (`water`, `foam`) for the game's water shader."""
    me, sh = _pair("waterfall")
    rnd = random.Random(9)
    Hh, Ww = 10.0, 6.0
    for s in (-1, 1):
        for k in range(7):
            z = -0.5 + k * 1.6
            w = rnd.uniform(2.0, 3.0)
            me.box(T(s * (Ww / 2 + w / 2 - 0.2), rnd.uniform(-0.4, 0.4), z + 0.9, rz=rnd.uniform(-8, 8)),
                   (w, rnd.uniform(3.0, 4.2), 1.8), "fieldstone", faces={"+z": "moss"} if k == 6 else None)
    for k in range(5):
        x = -Ww / 2 + 0.6 + k * (Ww - 1.2) / 4
        me.box(T(x, 0.9 + rnd.uniform(0, 0.4), Hh - 0.3), (1.5, 2.4, 0.9), "fieldstone", faces={"+z": "moss"})
    me.box(T(0, 1.5, Hh - 0.05), (Ww, 2.0, 0.1), "water")
    prev = None
    for k in range(9):
        t = k / 8
        p = (-0.3 - 1.6 * t * t, Hh - 0.2 - Hh * t)
        if prev:
            dy, dz = p[0] - prev[0], p[1] - prev[1]
            ln = math.hypot(dy, dz)
            me.box(T(0, (p[0] + prev[0]) / 2, (p[1] + prev[1]) / 2, rx=math.degrees(math.atan2(dz, dy))),
                   (Ww - 0.4, ln + 0.05, 0.12), "water")
        prev = p
    for _ in range(12):
        s = rnd.uniform(0.6, 1.4)
        me.box(T(rnd.uniform(-2.6, 2.6), -2.0 - rnd.uniform(0, 1.5), 0.1 + rnd.uniform(0, 0.4), rz=rnd.uniform(0, 90)),
               (s, s, s * 0.5), "foam")
    me.box(T(0, -3.0, -0.05), (Ww + 2, 4.0, 0.1), "water")
    # the detail rollout (2026-09-30): ferns along the rock tops, spray at the foot,
    # rocks standing in the pool
    for s in (-1, 1):
        for k in range(7):
            z = -0.5 + k * 1.6 + 1.8
            for _ in range(3):
                me.box(T(s * rnd.uniform(Ww / 2 + 0.2, Ww / 2 + 2.2), rnd.uniform(-1.2, 1.0), z + 0.08, rz=rnd.uniform(0, 90)),
                       (rnd.uniform(0.3, 0.6), 0.25, 0.22), "moss")
    for _ in range(10):
        sz = rnd.uniform(0.3, 0.8)
        me.box(T(rnd.uniform(-2.4, 2.4), -1.2 - rnd.uniform(0, 1.0), 0.4 + rnd.uniform(0, 1.2), rz=rnd.uniform(0, 90)),
               (sz, sz, sz * 0.7), "foam")
    for _ in range(5):
        sz = rnd.uniform(0.5, 1.0)
        me.box(T(rnd.uniform(-3.5, 3.5), -3.5 - rnd.uniform(0, 1.2), 0.1, rz=rnd.uniform(0, 90)), (sz, sz * 0.8, sz * 0.6),
               "fieldstone", faces={"+z": "moss"})
    K.proxy_box(sh, -Ww / 2 - 2.5, Ww / 2 + 2.5, -1.5, 2.0, -0.5, Hh)
    return me, sh


BUILDINGS = [guildhouse, tavern, shop, church, tenement, blacksmith, warehouse, stables, gatehouse, tower_round,
             tower_square, watchtower, lighthouse, water_gate, manor_a, manor_b, chapel, keep, barracks, windmill, barn]
VARIANTS = [townhouse_std, townhouse_narrow, townhouse_corner, townhouse_stall, townhouse_damaged, townhouse_ruin, cottage_tile,
            cottage_l]
STRUCTURES = [wall_run, wall_corner, retaining_tall(6), retaining_tall(12), grand_stair, ramp, bridge_arch,
              bridge_long, quay_wall, pier, harbour_arm, chain_boom, waterfall]
