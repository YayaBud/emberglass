"""The Emberglass city kit's new assets (2026-09-30, the user's "proposed new
assets" sheet, ref/city_direction_2026-09-30/assets_proposed.webp): the
buildings, house variants, water pieces, props and ships the kit lacked.

Built from the same parts as `citykit.py` / `cityprops.py` (house(), the
detail layer, the helpers) so they carry the same look; `build_city.py` lists
them next to the originals. Conventions as the kit: front -Y, ground z = 0.
Placing them in the city is a later step (implementation_plan.md Phase 4).
"""
import math
import random

from mathutils import Matrix, Vector

import citykit as C
import cityprops as P

K, T, DT = C.K, C.T, C.DT
X, Y, Z = C.X, C.Y, C.Z
GT = C.GROUND_TOP


def _fence(me, a, b, h=1.1, step=2.0):
    """A post-and-rail fence from a to b."""
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    n = max(1, int(L / step))
    for k in range(n + 1):
        p = a + (b - a) * (k / n)
        K.beam(me, p, p + Z * h, 0.12, 0.12)
    for zz in (h * 0.45, h * 0.9):
        K.beam(me, a + Z * zz, b + Z * zz, 0.08, 0.1)


def _wheel(me, xc, yc, zc, r, axis="x", n=16, w=0.7):
    """A water wheel turning about x (or y): two rims, spokes, paddles."""
    def pt(a, off):
        c, s = r * math.cos(a), r * math.sin(a)
        return Vector((xc + off, yc + c, zc + s)) if axis == "x" else Vector((xc + c, yc + off, zc + s))
    for off in (-w / 2, w / 2):
        for k in range(n):
            a0, a1 = k * math.tau / n, (k + 1) * math.tau / n
            K.beam(me, pt(a0, off), pt(a1, off), 0.1, 0.12)
        for k in range(0, n, 2):
            c = Vector((xc + off, yc, zc)) if axis == "x" else Vector((xc, yc + off, zc))
            K.beam(me, c, pt(k * math.tau / n, off), 0.08, 0.08)
    for k in range(n):
        a = (k + 0.5) * math.tau / n
        p = pt(a, 0)
        if axis == "x":
            me.box(T(p.x, p.y, p.z, rx=math.degrees(a)), (w + 0.1, 0.06, 0.55), "planks")
        else:
            me.box(T(p.x, p.y, p.z, ry=-math.degrees(a)), (0.55, w + 0.1, 0.06), "planks")
    C.rod(me, (xc - 0.6, yc, zc) if axis == "x" else (xc, yc - 0.6, zc),
          (xc + 0.6, yc, zc) if axis == "x" else (xc, yc + 0.6, zc), 0.14, "iron", n=6)


def _bartizan(me, x, y, z0, z1, r=0.9, cover="slate"):
    C.cyl(me, x, y, z0, z1, r, "ashlar", n=10, r1=r)
    C.cyl(me, x, y, z0 - 0.8, z0, r * 0.4, "ashlar", n=10, r1=r)
    C.pyramid(me, x, y, z1, r + 0.25, r * 2.6, cover, n=10)


# =============================================================================
# buildings
# =============================================================================

def inn():
    """A coaching inn: three storeys, stone below, jettied timber above, a
    long balcony, a grand sign with a key, a table set, a trough, barrels."""
    me, sh = C._pair("inn")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 11.0, 8.0, 3, ground="fieldstone", cover="clay_tile", pitch=50, ridge="x",
                                          jet=0.35, door=4.6, door_w=1.6, chimneys=((-4.2, 1.8), (4.0, 1.8)), sh=sh,
                                          extras=False)
    rnd = random.Random(501)
    DT.grand_sign(me, (x0 + 0.4, y0 - 0.35, GT + 1.95), (0, -1, 0), reach=2.1, board=(1.5, 1.05), emblem="key")
    DT.balcony(me, (x0, y0 - 0.35, 0), (1, 0, 0), 2.0, 9.0, GT, rnd=rnd)
    for x in (-1.35, 1.15):
        C.wall_lantern(me, x, y0, 2.4)
    DT.pots(me, rnd, ((-1.6, y0 - 0.55, 0.0), (1.4, y0 - 0.55, 0.0)))
    DT.table_set(me, (3.2, y0 - 1.35, 0), (1, 0, 0), rnd)
    me.box(T(-3.6, y0 - 1.0, 0.3), (1.6, 0.6, 0.6), "ashlar")
    me.box(T(-3.6, y0 - 1.0, 0.57), (1.4, 0.45, 0.04), "water")
    for y in (y0 + 0.7, y0 + 1.4):
        C._barrel(me, x1 + 0.5, y)
    C.banner(me, x1 - 0.4, y0 - 0.37, ze - 0.3, 2.6)
    DT.ivy(me, rnd, Vector((x1 - 0.5, y0, 0.45)), (1, 0, 0), 2.3)
    return me, sh


def apothecary():
    """A narrow shop with a blue awning, herbs drying under it, jars on a
    table, a mortar-and-pestle sign."""
    me, sh = C._pair("apothecary")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 5.2, 6.6, 2, ground="brick", cover="slate_blue", pitch=54, ridge="y",
                                          jet=0.35, door=0.5, shop=True, chimneys=((1.6, 1.8),), sh=sh,
                                          awning=("cloth_blue", "cloth_cream"), extras=False)
    rnd = random.Random(502)
    for k in range(6):
        x = -0.35 + k * 0.4
        me.box(T(x, y0 - 0.9, 2.62), (0.02, 0.02, 0.3), "iron")
        me.box(T(x, y0 - 0.9, 2.35, rz=k * 30), (0.14, 0.14, 0.3), ("moss", "crops", "thatch")[k % 3])
    me.box(T(0.8, y0 - 0.85, 0.78), (1.8, 0.6, 0.06), "planks")
    for dx in (-0.8, 0.8):
        me.box(T(0.8 + dx, y0 - 0.85, 0.38), (0.07, 0.5, 0.76), "timber")
    for k in range(7):
        C.cyl(me, 0.05 + k * 0.25, y0 - 0.85 + rnd.uniform(-0.12, 0.12), 0.81, 0.81 + rnd.uniform(0.14, 0.26), 0.07,
              ("glass", "clay_tile", "glass", "cloth_cream")[k % 4], n=6)
    DT.grand_sign(me, (x0 + 0.3, y0 - 0.35, GT + 1.8), (0, -1, 0), reach=1.6, board=(1.1, 0.8), emblem="mortar")
    DT.pots(me, rnd, ((x0 + 0.35, y0 - 0.55, 0.0),))
    C.wall_lantern(me, -1.4, y0, 2.4)
    DT.ivy(me, rnd, Vector((x1 - 0.4, y0, 0.45)), (1, 0, 0), 2.2)
    return me, sh


def cathedral():
    """The cathedral: a long ashlar nave with seven stained bays between
    buttresses and flying buttresses, twin west towers with tiled spires, a
    rose window over a great door, an apse, a flèche on the ridge."""
    me, sh = C._pair("cathedral")
    W, D, zt = 12.0, 26.0, 12.0
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    rnd = random.Random(503)
    K.plinth(me, x0, x1, y0, y1, mat="ashlar")
    bays = [(1.6 + k * 3.4, 3.2 + k * 3.4, 2.0, 9.2, "hole") for k in range(7)]
    for o, al in ((Vector((x1, y0, 0)), Y), (Vector((x0, y1, 0)), -Y)):
        K.wall(me, o, al, D, 0.5, zt, bays, "ashlar", frame=False)
        for u0, u1, v0, v1, _ in bays:
            C.lancet(me, o, al, u0, u1, 0.5 + v0, 0.5 + v1, "ashlar")
        out = al.cross(Z)
        for u in [0.6] + [4.1 + 3.4 * k for k in range(6)] + [D - 0.6]:
            p = o + al * u + out * 0.9
            me.box(T(p.x, p.y, 4.2), (0.9, 0.9, 8.4), "ashlar")
            C.pyramid(me, p.x, p.y, 8.4, 0.5, 2.2, "ashlar", n=4)
            K.beam(me, p + Z * 7.6, o + al * u + Z * (zt - 1.4), 0.4, 0.5, mat="ashlar")
    K.wall(me, Vector((x0, y0, 0)), X, W, 0.5, zt, [(W / 2 - 1.5, W / 2 + 1.5, 0.0, 5.2, "door")], "ashlar", frame=False)
    K.wall(me, Vector((x1, y1, 0)), -X, W, 0.5, zt, [], "ashlar", frame=False)
    rise = W / 2 * math.tan(math.radians(58))
    K.gable(me, Vector((x0, y0, 0)), X, W, zt, rise, "ashlar", frame=False)
    K.gable(me, Vector((x1, y1, 0)), -X, W, zt, rise, "ashlar", frame=False)
    C.disc(me, (0, y0 - 0.03, zt - 2.6), -90, 2.3, "ashlar", n=20)
    C.disc(me, (0, y0 - 0.07, zt - 2.6), -90, 1.95, "stained_glass", n=20)
    DT.surrounds(me, x0, y0, 0.5, [(W / 2 - 1.5, W / 2 + 1.5, 0.0, 5.2, "door")])
    ridge = C.roof(me, x0, x1, y0, y1, zt, 58, "slate", over_eave=0.4, ridge_axis="y")
    C.pyramid(me, 0, 0, ridge + 0.2, 0.9, 5.5, "slate", n=8, rot=22.5)
    # apse: half an octagon under a half cone
    poly = [(5.4 * math.cos(math.pi * k / 4), 5.4 * math.sin(math.pi * k / 4)) for k in range(5)]
    me.prism(Vector((0, y1 - 0.2, zt - 1.2)), X, Y, poly, zt - 0.7, "ashlar")
    ring = [Vector((5.9 * math.cos(math.pi * k / 4), y1 - 0.2 + 5.9 * math.sin(math.pi * k / 4), zt - 1.3)) for k in range(5)]
    apex = Vector((0, y1 - 0.2, zt + 3.4))
    for k in range(4):
        me.face([ring[k], ring[k + 1], apex], "slate", Vector((0, y1 + 1.0, zt)))
    for k in range(1, 4):
        a = math.pi * k / 4
        me.box(T(5.42 * math.cos(a), y1 - 0.2 + 5.42 * math.sin(a), 5.6, rz=math.degrees(a)), (0.05, 1.0, 5.0), "stained_glass")
    # twin west towers
    th = 21.0
    for cx in (x0 + 0.5, x1 - 0.5):
        tx0, tx1, ty0, ty1 = cx - 2.5, cx + 2.5, y0 - 4.6, y0 + 0.4
        K.plinth(me, tx0, tx1, ty0, ty1, mat="ashlar")
        me.box(T(cx, (ty0 + ty1) / 2, th / 2 + 0.25), (5.0, 5.0, th - 0.5), "ashlar")
        DT.stone_face(me, rnd, (tx0, ty0, 0), (1, 0, 0), 5.0, 0.5, th - 4.5, blocks=10, streaks=3,
                      ivy_h=0.25 if cx < 0 else 0)
        # the tower is solid: its windows stand proud of the face (a lancet expects a hole)
        me.box(T(cx, ty0 - 0.03, 10.0), (1.1, 0.08, 3.6), "stained_glass")
        me.box(T(cx, ty0 - 0.06, 11.9), (1.4, 0.1, 0.25), "ashlar")
        for dx in (-0.62, 0.62):
            me.box(T(cx + dx, ty0 - 0.06, 10.0), (0.16, 0.1, 3.8), "ashlar")
        for fx, fy, sx_, sy_ in ((cx, ty0 - 0.03, 1.8, 0.08), (tx1 + 0.03, (ty0 + ty1) / 2, 0.08, 1.8),
                                 (tx0 - 0.03, (ty0 + ty1) / 2, 0.08, 1.8)):
            me.box(T(fx, fy, th - 2.2), (sx_, sy_, 3.0), "glass")
        me.box(T(cx, (ty0 + ty1) / 2, th + 0.1), (5.4, 5.4, 0.3), "ashlar")
        for sx in (-1, 1):
            for sy in (-1, 1):
                C.pyramid(me, cx + sx * 2.45, (ty0 + ty1) / 2 + sy * 2.45, th + 0.25, 0.35, 2.0, "ashlar")
        C.pyramid(me, cx, (ty0 + ty1) / 2, th + 0.25, 3.3, 12.0, "slate", n=8, rot=22.5)
        C.rod(me, (cx, (ty0 + ty1) / 2, th + 12.2), (cx, (ty0 + ty1) / 2, th + 13.6), 0.05, "iron", n=4)
        K.proxy_box(sh, tx0, tx1, ty0, ty1, -0.5, th)
        C.pyramid(sh, cx, (ty0 + ty1) / 2, th, 3.2, 12.0, "SHADOW")
    for x in (-2.1, 2.1):
        C.wall_lantern(me, x, y0, 3.2)
    C.banner(me, -2.6, y0 - 0.05, zt - 1.0, 4.5, mat="cloth_blue")
    C.banner(me, 2.6, y0 - 0.05, zt - 1.0, 4.5, mat="cloth_blue")
    K.proxy_box(sh, x0, x1, y0, y1, -0.5, zt)
    K.proxy_roof(sh, x0, x1, y0, y1, zt, ridge, ridge_axis="y")
    return me, sh


def granary():
    """A timber granary raised on staddle stones against rats, a ladder to
    its door, sacks at the foot."""
    me, sh = C._pair("granary")
    for x in (-2.4, 0.0, 2.4):
        for y in (-1.8, 0.0, 1.8):
            C.cyl(me, x, y, 0.0, 0.85, 0.18, "fieldstone", n=8, r1=0.12)
            C.cyl(me, x, y, 0.85, 1.0, 0.42, "fieldstone", n=10)
    lift = 1.4
    me.xf = Matrix.Translation((0, 0, lift))
    sh.xf = Matrix.Translation((0, 0, lift))
    ridge, (x0, x1, y0, y1), ze = C.house(me, 6.0, 4.6, 1, ground="planks", cover="shingle", pitch=48, ridge="x",
                                          door=2.4, door_w=1.2, sh=sh, extras=False, dormers=())
    me.xf = Matrix.Identity(4)
    sh.xf = Matrix.Identity(4)
    for x in (-0.55, 0.55):
        K.beam(me, (x, y0 - 1.3, 0.0), (x, y0 - 0.15, lift + 0.5), 0.08, 0.08)
    for k in range(1, 6):
        t = k / 6
        K.beam(me, (-0.55, y0 - 1.3 + 1.15 * t, (lift + 0.5) * t), (0.55, y0 - 1.3 + 1.15 * t, (lift + 0.5) * t), 0.05, 0.05)
    for k, (x, y) in enumerate(((1.6, y0 - 0.9), (2.1, y0 - 0.6), (1.85, y0 - 1.4))):
        C._sack(me, x, y, rz=k * 30)
    return me, sh


def market_hall():
    """The market hall: an open stone arcade below, a timber hall above on
    it, a clay roof with a bell cupola, banners and lanterns on the piers."""
    me, sh = C._pair("market_hall")
    W, D, zf = 12.0, 7.0, 3.6
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    K.plinth(me, x0, x1, y0, y1, mat="ashlar")
    xs = [x0 + 0.4 + i * (W - 0.8) / 4 for i in range(5)]
    for x in xs:
        for y in (y0 + 0.4, y1 - 0.4):
            me.cbox(T(x, y, (0.5 + zf) / 2), (0.7, 0.7, zf - 0.5), "ashlar", 0.05)
    for i in range(4):
        xa, xb = xs[i] + 0.35, xs[i + 1] - 0.35
        for ya, yb in ((y0 + 0.05, y0 + 0.75), (y1 - 0.75, y1 - 0.05)):
            C.arch_fill(me, xa, xb, ya, yb, zf - 1.6, 1.0, zf, n=8)
    for x in (x0 + 0.4, x1 - 0.4):
        me.box(T(x, 0, zf - 0.3), (0.7, D - 1.5, 0.6), "ashlar")
    me.box(T(0, 0, zf + 0.12), (W + 0.3, D + 0.3, 0.25), "planks", axis=(1, 0, 0))
    C.storey(me, (x0, x1, y0, y1), zf + 0.25, zf + 2.8, "plaster", True, (), spacing=1.8, rails=(0.65,), rich=True)
    ze = zf + 2.8
    rise = D / 2 * math.tan(math.radians(45))
    K.gable(me, Vector((x1, y0, 0)), (0, 1, 0), D, ze, rise, "plaster", frame=True, window=(0.6, 0.7))
    K.gable(me, Vector((x0, y1, 0)), (0, -1, 0), D, ze, rise, "plaster", frame=True)
    ridge = C.roof(me, x0, x1, y0, y1, ze, 45, "clay_tile", ridge_axis="x")
    me.box(T(0, 0, ridge + 0.75), (1.4, 1.4, 1.5), "planks")
    for dx in (-0.6, 0.6):
        for dy in (-0.6, 0.6):
            K.beam(me, (dx, dy, ridge), (dx, dy, ridge + 1.5))
    C.cyl(me, 0, 0, ridge + 0.6, ridge + 1.2, 0.35, "iron", n=8, r1=0.22)
    C.pyramid(me, 0, 0, ridge + 1.5, 1.25, 1.8, "slate_blue", n=4)
    rnd = random.Random(505)
    for i in range(4):
        DT.hanging_lantern(me, ((xs[i] + xs[i + 1]) / 2, y0 + 0.4, zf - 0.6), drop=0.3)
    for x in (xs[1], xs[3]):
        C.banner(me, x, y0 + 0.02, zf - 0.2, 2.2, mat="cloth_blue")
    for k, x in enumerate((-3.2, -1.2, 1.4, 3.3)):
        C._crate(me, x, 0.8, 0.5, 0.6, k * 11)
        C._sack(me, x + 0.5, -0.4, 0.5, rz=k * 25)
    K.proxy_box(sh, x0, x1, y0, y1, zf, ze)
    K.proxy_roof(sh, x0, x1, y0, y1, ze, ridge, ridge_axis="x")
    return me, sh


def library():
    """A stone library: two ashlar storeys with tall windows, a blue slate
    roof, a round stair turret at the corner, steps to the door, a book sign."""
    me, sh = C._pair("library")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 10.0, 8.0, 2, ground="ashlar", upper="ashlar", cover="slate_blue", pitch=52,
                                          ridge="x", door=4.3, door_w=1.4, spacing=1.7, chimneys=((-3.8, 2.2),), sh=sh,
                                          extras=False)
    rnd = random.Random(506)
    C.cyl(me, x1 - 0.2, y0 + 0.2, -0.3, ze + 1.4, 1.35, "ashlar", n=12)
    for z in (2.2, 4.6):
        C.slit(me, x1 - 0.2, y0 + 0.2 - 1.36, z, -90)
    C.pyramid(me, x1 - 0.2, y0 + 0.2, ze + 1.4, 1.7, 3.4, "slate_blue", n=12)
    for k in range(3):
        me.box(T(-0.3 + 0.0, y0 - 0.35 - k * 0.35, 0.4 - k * 0.14), (2.4 + k * 0.4, 0.4, 0.14), "ashlar")
    DT.grand_sign(me, (x0 + 0.4, y0, GT + 0.9), (0, -1, 0), reach=1.5, board=(1.0, 0.75), emblem="book")
    for x in (-1.6, 1.0):
        C.banner(me, x, y0 - 0.03, ze - 0.4, 2.8, mat="cloth_blue")
    C.wall_lantern(me, 1.5, y0, 2.4)
    DT.pots(me, rnd, ((-1.3, y0 - 1.2, 0.0), (0.7, y0 - 1.2, 0.0)))
    DT.ivy(me, rnd, Vector((x0 + 0.5, y0, 0.45)), (1, 0, 0), 3.2)
    K.proxy_box(sh, x1 - 1.4, x1 + 1.0, y0 - 1.0, y0 + 1.4, -0.5, ze + 1.4)
    return me, sh


def town_hall():
    """The town hall: three tall storeys, ashlar below and timber above, a
    clock turret on the ridge, a balcony over the door, blue banners."""
    me, sh = C._pair("town_hall")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 12.0, 9.0, 3, ground="ashlar", upper="plaster", cover="slate", pitch=50,
                                          ridge="x", jet=0.3, door=5.2, door_w=1.6, chimneys=((-4.8, 2.6), (4.8, 2.6)),
                                          sh=sh, tall=True, extras=False)
    rnd = random.Random(507)
    zb = 0.5 + 2.7 + 0.3
    DT.balcony(me, (x0, y0 - 0.3, 0), (1, 0, 0), 4.4, 7.6, zb, rnd=rnd)
    cy = (y0 - 0.6 + y1) / 2
    me.box(T(0, cy, ridge + 1.0), (2.2, 2.2, 2.6), "plaster")
    for dx in (-1.05, 1.05):
        for dy in (-1.05, 1.05):
            K.beam(me, (dx, cy + dy, ridge - 0.3), (dx, cy + dy, ridge + 2.3))
    C.disc(me, (0, cy - 1.12, ridge + 1.2), -90, 0.7, "ashlar", n=16)
    C.disc(me, (0, cy - 1.16, ridge + 1.2), -90, 0.56, "cloth_cream", n=16)
    K.beam(me, (0, cy - 1.2, ridge + 1.2), (0, cy - 1.2, ridge + 1.6), 0.05, 0.03, mat="iron")
    K.beam(me, (0, cy - 1.2, ridge + 1.2), (0.3, cy - 1.2, ridge + 1.2), 0.05, 0.03, mat="iron")
    C.pyramid(me, 0, cy, ridge + 2.3, 1.7, 3.6, "slate_blue", n=8, rot=22.5)
    C.rod(me, (0, cy, ridge + 5.9), (0, cy, ridge + 7.2), 0.04, "iron", n=4)
    me.box(T(0.5, cy, ridge + 6.9), (0.9, 0.03, 0.5), "cloth_blue")
    for x in (-4.5, -2.3, 2.3, 4.5):
        C.banner(me, x, y0 - 0.33, ze - 0.4, 3.0, mat="cloth_blue")
    for k in range(3):
        me.box(T(0.6, y0 - 0.4 - k * 0.35, 0.4 - k * 0.14), (2.6 + k * 0.4, 0.4, 0.14), "ashlar")
    for x in (-0.3, 1.5):
        C.wall_lantern(me, x, y0, 2.6)
    DT.pots(me, rnd, ((-0.8, y0 - 1.3, 0.0), (2.0, y0 - 1.3, 0.0)))
    return me, sh


def mansion():
    """A merchant prince's mansion: three storeys, brick and timber, two
    round corner turrets, a columned porch, hedges and pots."""
    me, sh = C._pair("mansion")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 14.0, 10.0, 3, ground="brick", upper="plaster", cover="slate", pitch=52,
                                          ridge="x", door=6.3, door_w=1.4, spacing=2.2,
                                          chimneys=((-5.5, 2.8), (5.5, 2.8)), sh=sh, extras=False)
    rnd = random.Random(508)
    for x in (x0, x1):
        C.cyl(me, x, y0, -0.3, ze + 0.6, 1.5, "brick", n=12)
        C.cyl(me, x, y0, ze + 0.6, ze + 0.9, 1.65, "ashlar", n=12)
        for z in (2.2, 4.6, 7.0):
            me.box(T(x, y0 - 1.5, z), (0.7, 0.1, 1.0), "M_Window_Dim")
        C.pyramid(me, x, y0, ze + 0.9, 1.9, 4.4, "slate", n=12)
    for x in (-1.6, 1.6):
        for y in (y0 - 2.2, y0 - 0.3):
            C.cyl(me, x, y, 0.0, 3.0, 0.2, "ashlar", n=8)
    C.roof(me, -1.9, 1.9, y0 - 2.6, y0 + 0.1, 3.0, 32, "slate", over_eave=0.2, over_gable=0.15, thick=0.12, ridge_axis="y")
    for s in (-1, 1):
        me.box(T(s * 4.6, y0 - 1.3, 0.6), (4.0, 0.9, 1.2), "moss")
    DT.pots(me, rnd, ((-2.3, y0 - 2.4, 0.0), (2.3, y0 - 2.4, 0.0)))
    C.wall_lantern(me, -1.0, y0, 2.4)
    C.wall_lantern(me, 1.0, y0, 2.4)
    DT.ivy(me, rnd, Vector((x0 + 1.9, y0, 0.45)), (1, 0, 0), 3.4)
    for x in (x0, x1):
        K.proxy_box(sh, x - 1.5, x + 1.5, y0 - 1.5, y0 + 1.5, -0.5, ze + 0.9)
    return me, sh


def small_keep():
    """A small keep: an 8 m square ashlar tower of 14 m, corner bartizans with
    slate cones, crenellations, slits, an arched door, a blue banner."""
    me, sh = C._pair("small_keep")
    S, H = 8.0, 14.0
    rnd = random.Random(509)
    K.plinth(me, -S / 2, S / 2, -S / 2, S / 2, mat="ashlar")
    me.box(T(0, 0, H / 2 + 0.25), (S, S, H - 0.5), "ashlar", faces={"+z": "flagstone"})
    DT.stone_face(me, rnd, (-S / 2, -S / 2, 0), (1, 0, 0), S, 0.5, H, blocks=14)
    DT.stone_face(me, rnd, (-S / 2, S / 2, 0), (0, -1, 0), S, 0.5, H, blocks=10, ivy_h=0)
    c = S / 2 + 0.1
    for a, b in (((-c, -c), (c, -c)), ((c, -c), (c, c)), ((c, c), (-c, c)), ((-c, c), (-c, -c))):
        C.merlons(me, a, b, H, w=0.8, gap=0.6, t=0.4)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bartizan(me, sx * S / 2, sy * S / 2, H - 2.6, H + 0.9)
    for x, z in ((-2.0, 6.0), (2.0, 6.0), (0.0, 10.0)):
        C.slit(me, x, -S / 2, z, -90)
    for x in (-1.8, 1.8):
        me.box(T(x, -S / 2 - 0.03, 9.4), (0.8, 0.06, 1.2), "M_Window_Dim")
    me.box(T(0, -S / 2 + 0.05, 1.7), (1.6, 0.1, 2.4), "planks")
    DT.surrounds(me, -S / 2, -S / 2, 0.5, [(S / 2 - 0.8, S / 2 + 0.8, 0.0, 2.3, "door")])
    for k in range(3):
        me.box(T(0, -S / 2 - 0.4 - k * 0.35, 0.4 - k * 0.14), (2.2 + k * 0.4, 0.4, 0.14), "ashlar")
    C.banner(me, 2.6, -S / 2 - 0.02, H - 1.0, 4.2, mat="cloth_blue")
    C.rod(me, (0, 0, H), (0, 0, H + 4.0), 0.06, "timber", n=6)
    me.box(T(0.6, 0, H + 3.6), (1.2, 0.03, 0.7), "cloth_blue")
    C.wall_lantern(me, -1.4, -S / 2, 2.6)
    K.proxy_box(sh, -S / 2, S / 2, -S / 2, S / 2, -0.5, H + 0.8)
    return me, sh


def mill_house():
    """A water mill: stone and timber, a big undershot wheel on its flank, a
    flume feeding it, sacks of flour at the door."""
    me, sh = C._pair("mill_house")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 7.0, 6.0, 2, ground="fieldstone", cover="shingle", pitch=48, ridge="x",
                                          door=1.2, chimneys=((2.4, 1.4),), sh=sh, extras=False)
    rnd = random.Random(510)
    xw = x0 - 0.8
    _wheel(me, xw, 0.0, 2.4, 2.3, axis="x")
    me.box(T(xw, -3.3, 4.85), (1.0, 3.6, 0.1), "planks", axis=(0, 1, 0))
    for s in (-1, 1):
        me.box(T(xw + s * 0.5, -3.3, 5.05), (0.08, 3.6, 0.4), "planks", axis=(0, 1, 0))
    me.box(T(xw, -3.3, 5.0), (0.84, 3.5, 0.05), "water")
    for y in (-4.8, -2.2):
        K.beam(me, (xw, y, 0.0), (xw, y, 4.8), 0.16, 0.16)
    me.box(T(xw, 0.0, 0.0), (2.2, 5.5, 0.1), "water")
    for k, (x, y) in enumerate(((x0 + 1.5, y0 - 0.8), (x0 + 2.1, y0 - 0.7), (x0 + 1.8, y0 - 1.3))):
        C._sack(me, x, y, rz=k * 40)
    DT.ivy(me, rnd, Vector((x1 - 0.5, y0, 0.45)), (1, 0, 0), 2.2)
    C.wall_lantern(me, x0 + 0.8, y0, 2.4)
    return me, sh


def stable_yard():
    """A long stable with half doors, a fenced yard before it, a hay stack
    and a trough."""
    me, sh = C._pair("stable_yard")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 12.0, 5.5, 1, ground="plaster", cover="shingle", pitch=45, ridge="x",
                                          door=1.0, door_w=1.8, spacing=2.4, sh=sh, extras=False)
    rnd = random.Random(511)
    for k in range(4):
        x = x0 + 3.6 + k * 2.2
        me.box(T(x, y0 - 0.05, 1.2), (1.4, 0.08, 1.4), "planks")
        me.box(T(x, y0 - 0.09, 1.2), (1.3, 0.04, 0.08), "timber")
    yf = y0 - 3.4
    _fence(me, (x0, yf, 0), (-1.0, yf, 0))
    _fence(me, (1.0, yf, 0), (x1, yf, 0))
    for x in (x0, x1):
        _fence(me, (x, y0 - 0.4, 0), (x, yf, 0))
    C.cyl(me, x0 + 1.4, yf + 1.4, 0.0, 1.0, 0.9, "thatch", n=10, r1=0.95)
    C.cyl(me, x0 + 1.4, yf + 1.4, 1.0, 1.9, 0.95, "thatch", n=10, r1=0.3)
    me.box(T(x1 - 1.8, yf + 0.9, 0.3), (1.6, 0.6, 0.6), "planks")
    me.box(T(x1 - 1.8, yf + 0.9, 0.57), (1.4, 0.45, 0.04), "water")
    for k in range(6):
        me.box(T(rnd.uniform(x0 + 1, x1 - 1), rnd.uniform(yf + 0.4, y0 - 0.8), 0.05, rz=rnd.uniform(0, 90)), (0.6, 0.35, 0.1), "thatch")
    C.wall_lantern(me, x0 + 2.4, y0, 2.3)
    return me, sh


def dockhouse():
    """A dock warehouse: stone below, planks above, a wide loading door, a
    hoist beam out of the gable with a crate on its rope, cargo at the door."""
    me, sh = C._pair("dockhouse")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 9.0, 7.0, 2, ground="fieldstone", upper="planks", cover="clay_tile", pitch=50,
                                          ridge="y", door=1.0, door_w=2.2, chimneys=((3.0, 2.0),), sh=sh, extras=False)
    rnd = random.Random(512)
    K.beam(me, (0, y0 + 0.5, ze + 1.9), (0, y0 - 1.8, ze + 1.9), 0.24, 0.24)
    C.rod(me, (-0.12, y0 - 1.55, ze + 1.7), (0.12, y0 - 1.55, ze + 1.7), 0.16, "timber", n=8)
    K.beam(me, (0, y0 - 1.55, ze + 1.6), (0, y0 - 1.55, 3.2), 0.03, 0.03, mat="thatch")
    C._crate(me, 0, y0 - 1.55, 2.5, 0.7, 15)
    me.box(T(0, y0 - 0.05, ze + 0.7), (1.4, 0.08, 1.4), "planks")
    for k in range(3):
        C._crate(me, x0 + 3.9 + k * 0.7, y0 - 0.8, 0.0, 0.65, k * 13)
    C._crate(me, x0 + 4.3, y0 - 0.8, 0.65, 0.5, 30)
    for y in (y0 - 0.6, y0 - 1.3):
        C._barrel(me, x1 - 0.6, y)
    C._sack(me, x1 - 1.4, y0 - 0.8, rz=20)
    C.wall_lantern(me, x0 + 0.6, y0, 2.4)
    return me, sh


def fisher_house():
    """A fisher's cottage: plaster and thatch, nets drying on poles, a rack of
    fish, barrels, oars leaning by the door."""
    me, sh = C._pair("fisher_house")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 6.0, 5.0, 1, ground="plaster", cover="thatch", pitch=46, ridge="x",
                                          door=1.2, chimneys=((2.2, 1.2),), sh=sh, extras=False)
    rnd = random.Random(513)
    for x in (x0 - 1.2, x0 - 1.2 + 3.2):
        C.rod(me, (x, y0 - 2.2, 0.0), (x, y0 - 2.2, 2.4), 0.07, "timber", n=6)
    K.beam(me, (x0 - 1.2, y0 - 2.2, 2.3), (x0 + 2.0, y0 - 2.2, 2.3), 0.04, 0.04, mat="thatch")
    me.box(T(x0 + 0.4, y0 - 2.2, 1.6), (3.0, 0.04, 1.3), "bark")
    for k in range(5):
        me.box(T(x0 - 0.8 + k * 0.7, y0 - 2.24, 0.95), (0.12, 0.08, 0.12), "cloth_red")
    for x in (x1 + 0.5, x1 + 2.1):
        K.beam(me, (x, y0 + 0.4, 0.0), (x, y0 + 0.4, 1.8), 0.1, 0.1)
    K.beam(me, (x1 + 0.5, y0 + 0.4, 1.7), (x1 + 2.1, y0 + 0.4, 1.7), 0.08, 0.08)
    for k in range(6):
        me.box(T(x1 + 0.7 + k * 0.25, y0 + 0.4, 1.35), (0.06, 0.12, 0.55), ("ice", "cloth_cream")[k % 2])
    C._barrel(me, x0 + 0.5, y0 - 0.7)
    for k in range(2):
        K.beam(me, (x0 + 2.4 + k * 0.25, y0 - 0.5, 0.0), (x0 + 2.2 + k * 0.25, y0 - 0.1, 2.6), 0.05, 0.05)
    DT.flower_strip(me, rnd, (x0 + 3.3, y0 - 0.55, 0), (x1 - 0.3, y0 - 0.55, 0))
    return me, sh


# =============================================================================
# house variants
# =============================================================================

def townhouse_arched():
    """A stone townhouse whose door is a wide arch (a passage to the yard)."""
    me, sh = C._pair("townhouse_arched")
    C.house(me, 5.6, 7.0, 3, ground="ashlar", cover="clay_tile", pitch=54, ridge="y", jet=0.3, door=1.5, door_w=2.4,
            chimneys=((1.8, 1.8),), sh=sh)
    return me, sh


def townhouse_wooden():
    """A plank-built townhouse under shingle."""
    me, sh = C._pair("townhouse_wooden")
    C.house(me, 5.4, 6.8, 2, ground="planks", upper="planks", cover="shingle", pitch=50, ridge="y", door=0.7,
            chimneys=((1.7, 1.6),), sh=sh)
    return me, sh


def townhouse_stone():
    """An all-ashlar townhouse under blue slate."""
    me, sh = C._pair("townhouse_stone")
    C.house(me, 5.6, 7.0, 2, ground="ashlar", upper="ashlar", cover="slate_blue", pitch=52, ridge="y", door=0.8,
            chimneys=((1.8, 1.6),), sh=sh)
    return me, sh


def cottage_thatch():
    """A thatched cottage with a picket-fenced flower garden."""
    me, sh = C._pair("cottage_thatch")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 6.4, 5.0, 1, ground="plaster", cover="thatch", pitch=48, ridge="x",
                                          door=2.4, chimneys=((2.3, 1.2),), sh=sh)
    rnd = random.Random(521)
    DT.flower_strip(me, rnd, (x0 + 0.2, y0 - 0.9, 0), (x0 + 2.1, y0 - 0.9, 0), w=0.8)
    DT.picket(me, (x0 + 0.1, y0 - 1.5, 0), (x0 + 2.2, y0 - 1.5, 0))
    return me, sh


def merchant_house():
    """A wide merchant's house: three storeys, a shop with a red awning, a sign."""
    me, sh = C._pair("merchant_house")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 7.6, 7.0, 3, ground="brick", cover="clay_tile", pitch=52, ridge="x", jet=0.35,
                                          door=0.8, shop=True, awning=("cloth_red", "cloth_cream"), chimneys=((-2.8, 1.8),),
                                          sh=sh)
    C.hanging_sign(me, x1 - 0.3, y0, GT - 0.5, mat="cloth_red")
    return me, sh


def alley_house():
    """A narrow three-storey house for the old alleys."""
    me, sh = C._pair("alley_house")
    C.house(me, 3.6, 7.0, 3, ground="fieldstone", cover="slate", pitch=58, ridge="y", jet=0.3, door=0.6,
            chimneys=((1.0, 2.0),), sh=sh)
    return me, sh


def city_house():
    """A solid city house: ashlar below, timber above, blue slate."""
    me, sh = C._pair("city_house")
    C.house(me, 6.2, 7.2, 3, ground="ashlar", cover="slate_blue", pitch=52, ridge="x", jet=0.3, door=2.4,
            chimneys=((2.4, 2.0),), sh=sh)
    return me, sh


def river_house():
    """A house on the water: a plank deck on posts behind it, a mooring post."""
    me, sh = C._pair("river_house")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 6.0, 6.0, 2, ground="fieldstone", cover="shingle", pitch=50, ridge="x",
                                          jet=0.4, door=2.0, chimneys=((-2.2, 1.6),), sh=sh)
    me.box(T(0, y1 + 1.2, 0.45), (5.6, 2.4, 0.12), "planks", axis=(1, 0, 0))
    for x in (-2.6, 0.0, 2.6):
        C.rod(me, (x, y1 + 2.3, -1.5), (x, y1 + 2.3, 0.45), 0.12, "bark", n=6)
        C.cyl(me, x, y1 + 2.3, -0.2, 0.15, 0.15, "moss", n=6)
    for x in (-2.7, 2.7):
        K.beam(me, (x, y1, 1.4), (x, y1 + 2.35, 1.4), 0.06, 0.06)
    K.beam(me, (-2.7, y1 + 2.35, 1.4), (2.7, y1 + 2.35, 1.4), 0.06, 0.06)
    return me, sh


def tower_house():
    """A four-storey tower house: narrow, steep, a bartizan at its corner."""
    me, sh = C._pair("tower_house")
    ridge, (x0, x1, y0, y1), ze = C.house(me, 4.6, 4.8, 4, ground="fieldstone", upper="plaster", cover="slate", pitch=62,
                                          ridge="y", door=1.6, fh=2.5, chimneys=((1.4, 1.4),), sh=sh, tall=True)
    _bartizan(me, x0, y0, ze - 1.6, ze + 0.6, r=0.7)
    return me, sh


# =============================================================================
# walls and water
# =============================================================================

def bridge_covered():
    """A covered timber footbridge: stone abutments, a plank deck, framed
    sides with crosses, a shingle roof, a lantern at each end."""
    me, sh = C._pair("bridge_covered")
    L, W, dz = 14.0, 3.6, 3.0
    for s in (-1, 1):
        me.box(T(s * (L / 2 - 1.0), 0, (dz - 1.0) / 2), (2.0, W + 0.8, dz + 1.0), "ashlar")
    me.box(T(0, 0, dz), (L, W, 0.25), "planks", axis=(1, 0, 0))
    for s in (-1, 1):
        K.beam(me, (-L / 2 + 2, s * (W / 2 - 0.1), dz - 0.3), (L / 2 - 2, s * (W / 2 - 0.1), dz - 0.3), 0.3, 0.3)
        K.beam(me, (-L / 2 + 2, s * (W / 2 - 0.1), dz - 0.4), (0, s * (W / 2 - 0.1), dz - 1.6), 0.2, 0.2)
        K.beam(me, (L / 2 - 2, s * (W / 2 - 0.1), dz - 0.4), (0, s * (W / 2 - 0.1), dz - 1.6), 0.2, 0.2)
        xs = [-L / 2 + 0.2 + k * (L - 0.4) / 7 for k in range(8)]
        for x in xs:
            K.beam(me, (x, s * (W / 2 - 0.1), dz), (x, s * (W / 2 - 0.1), dz + 2.6))
        for zz in (dz + 1.0, dz + 2.55):
            K.beam(me, (-L / 2, s * (W / 2 - 0.1), zz), (L / 2, s * (W / 2 - 0.1), zz))
        for a, b in zip(xs, xs[1:]):
            K.beam(me, (a, s * (W / 2 - 0.1), dz + 0.1), (b, s * (W / 2 - 0.1), dz + 0.95), 0.1, 0.1, up=(0, 1, 0))
            K.beam(me, (a, s * (W / 2 - 0.1), dz + 0.95), (b, s * (W / 2 - 0.1), dz + 0.1), 0.1, 0.1, up=(0, 1, 0))
    ridge = C.roof(me, -L / 2, L / 2, -W / 2, W / 2, dz + 2.7, 40, "shingle", over_eave=0.4, over_gable=0.3, ridge_axis="x")
    for x in (-L / 2 - 0.3, L / 2 + 0.3):
        C.wall_lantern(me, x, -W / 2 + 0.2, dz + 2.2, rz=180 if x < 0 else 0)
    rnd = random.Random(531)
    for _ in range(4):
        DT.hanging_vine(me, rnd, (rnd.uniform(-5, 5), -W / 2 - 0.05, dz), (0, -1, 0), rnd.uniform(0.6, 1.4))
    K.proxy_box(sh, -L / 2, L / 2, -W / 2, W / 2, dz - 0.3, dz + 2.7)
    K.proxy_roof(sh, -L / 2, L / 2, -W / 2, W / 2, dz + 2.7, ridge, ridge_axis="x")
    return me, sh


def dock_platform():
    """An 8 x 6 m plank dock on piles: bollards, cargo, a ladder, a lamp."""
    me, sh = C._pair("dock_platform")
    Lx, Ly, dz = 8.0, 6.0, 1.2
    me.box(T(0, -Ly / 2, dz), (Lx, Ly, 0.16), "planks", axis=(1, 0, 0))
    for x in (-Lx / 2 + 0.2, 0.0, Lx / 2 - 0.2):
        for y in (-0.2, -Ly / 2, -Ly + 0.2):
            C.rod(me, (x, y, -2.5), (x, y, dz), 0.16, "bark", n=8)
            C.cyl(me, x, y, -0.15, 0.3, 0.19, "moss", n=8)
    for x in (-Lx / 2 + 0.6, Lx / 2 - 0.6):
        C.cyl(me, x, -Ly + 0.4, dz + 0.08, dz + 0.6, 0.16, "iron", n=8)
    C._crate(me, -1.8, -2.0, dz + 0.08, 0.7, 10)
    C._crate(me, -1.1, -2.1, dz + 0.08, 0.6, -6)
    C._crate(me, -1.5, -2.0, dz + 0.78, 0.5, 20)
    C._barrel(me, 1.6, -1.8, dz + 0.08)
    C._barrel(me, 2.2, -2.3, dz + 0.08)
    C._sack(me, 0.4, -3.6, dz + 0.08, rz=30)
    for k in range(6):
        K.beam(me, (-0.3, -Ly - 0.08, dz - 0.3 * k), (0.3, -Ly - 0.08, dz - 0.3 * k), 0.05, 0.05)
    C.rod(me, (Lx / 2 - 0.3, -0.5, dz), (Lx / 2 - 0.3, -0.5, dz + 2.8), 0.08, "timber", n=6)
    C.wall_lantern(me, Lx / 2 - 0.3, -0.5, dz + 2.7, rz=180)
    K.proxy_box(sh, -Lx / 2, Lx / 2, -Ly, 0, dz - 0.3, dz + 0.1)
    return me, sh


def sluice_gate():
    """A stone sluice: channel walls, a timber frame, a plank gate half raised
    on a windlass, water through it."""
    me, sh = C._pair("sluice_gate")
    for s in (-1, 1):
        me.box(T(s * 2.2, 0, 1.0), (1.4, 6.0, 3.0), "ashlar", faces={"+z": "flagstone"})
    me.box(T(0, 0, -0.35), (3.0, 6.0, 0.1), "water")
    for s in (-1, 1):
        K.beam(me, (s * 1.45, 0, 2.5), (s * 1.45, 0, 5.2), 0.24, 0.24)
    K.beam(me, (-1.7, 0, 5.1), (1.7, 0, 5.1), 0.26, 0.26)
    me.box(T(0, 0, 1.8), (2.7, 0.18, 2.2), "planks")
    for zz in (1.0, 2.6):
        me.box(T(0, -0.1, zz), (2.7, 0.06, 0.14), "iron")
    C.rod(me, (-1.3, 0, 4.5), (1.3, 0, 4.5), 0.14, "timber", n=8)
    for k in range(6):
        a = k * math.tau / 6
        K.beam(me, (1.5, 0, 4.5), (1.5, 0.55 * math.cos(a), 4.5 + 0.55 * math.sin(a)), 0.05, 0.05)
    K.beam(me, (0, 0, 4.4), (0, 0, 2.9), 0.03, 0.03, mat="iron")
    rnd = random.Random(533)
    for s in (-1, 1):
        for _ in range(4):
            me.box(T(s * 1.52, rnd.uniform(-2.8, 2.8), rnd.uniform(-0.1, 0.4)), (0.04, rnd.uniform(0.4, 1.0), 0.3), "moss")
    K.proxy_box(sh, -2.9, 2.9, -3.0, 3.0, -0.5, 2.5)
    return me, sh


def riverbank():
    """8 m of river bank: an earth and stone slope into the water, boulders
    at the edge, reeds and flowers."""
    me, sh = C._pair("riverbank")
    rnd = random.Random(534)
    me.prism(Vector((4.0, 0, 0)), Y, Z, [(-3.0, -0.4), (1.0, -0.4), (1.0, 1.5)], 8.0, "dirt", back="fieldstone")
    me.box(T(0, -3.0, -0.3), (8.0, 2.0, 0.1), "water")
    for _ in range(12):
        s_ = rnd.uniform(0.4, 0.9)
        me.box(T(rnd.uniform(-3.8, 3.8), rnd.uniform(-2.9, -2.2), rnd.uniform(-0.3, 0.0), rz=rnd.uniform(0, 90)),
               (s_, s_ * 0.8, s_ * 0.6), "fieldstone", faces={"+z": "moss"} if rnd.random() < 0.4 else None)
    for _ in range(14):
        cx, cy = rnd.uniform(-3.7, 3.7), rnd.uniform(-2.4, -1.6)
        for _ in range(5):
            h = rnd.uniform(0.7, 1.4)
            me.box(T(cx + rnd.uniform(-0.2, 0.2), cy + rnd.uniform(-0.2, 0.2), h / 2 - 0.2, rx=rnd.uniform(-8, 8)),
                   (0.04, 0.04, h), rnd.choice(("moss", "thatch")))
    for _ in range(8):
        x, y = rnd.uniform(-3.6, 3.6), rnd.uniform(-2.0, 0.8)
        z = -0.4 + (y + 3.0) * 0.475                      # on the slope
        me.box(T(x, y, z + 0.05, rz=rnd.uniform(0, 90)), (0.3, 0.3, 0.15), "moss")
        me.box(T(x, y, z + 0.16), (0.09, 0.09, 0.07), rnd.choice(("cloth_red", "crops", "cloth_cream")))
    return me, sh


def stone_stairs():
    """A straight flight of 12 steps, 3 m wide and 3 m high, between coped
    side walls, moss in the corners, a lantern at the top."""
    me, sh = C._pair("stone_stairs")
    Wd, n, rise, tread = 3.0, 12, 0.25, 0.36
    for k in range(n):
        me.box(T(0, k * tread, (k + 1) * rise / 2), (Wd, tread + 0.02, (k + 1) * rise), "ashlar", faces={"+z": "flagstone"})
    Lw = n * tread
    for s in (-1, 1):
        me.prism(Vector((s * (Wd / 2 + 0.25), -0.2, 0)), Y, Z, [(0, 0), (Lw + 0.2, 0), (Lw + 0.2, n * rise + 0.9), (0, 0.9)],
                 0.5, "ashlar")
        for k in range(n):
            me.box(T(s * (Wd / 2 + 0.25), k * tread, (k + 1) * rise + 0.95), (0.62, tread + 0.02, 0.1), "flagstone")
    rnd = random.Random(535)
    for k in range(0, n, 2):
        s = rnd.choice((-1, 1))
        me.box(T(s * (Wd / 2 - 0.15), k * tread, (k + 1) * rise + 0.03), (0.25, 0.25, 0.06), "moss")
    C.rod(me, (Wd / 2 + 0.25, Lw - 0.2, n * rise + 1.0), (Wd / 2 + 0.25, Lw - 0.2, n * rise + 2.4), 0.06, "iron", n=6)
    me.box(T(Wd / 2 + 0.25, Lw - 0.2, n * rise + 2.6), (0.26, 0.26, 0.34), "M_Lamp")
    me.box(T(Wd / 2 + 0.25, Lw - 0.2, n * rise + 2.8), (0.34, 0.34, 0.06), "iron")
    K.proxy_box(sh, -Wd / 2 - 0.5, Wd / 2 + 0.5, -0.2, Lw, -0.5, n * rise)
    return me, sh


def archway():
    """A free-standing street arch: two piers, a round arch with a keystone,
    a crenellated top, lanterns, a banner, ivy."""
    me, sh = C._pair("archway")
    rnd = random.Random(536)
    for s in (-1, 1):
        me.cbox(T(s * 3.0, 0, 2.5), (1.4, 1.6, 5.5), "ashlar", 0.05)
    C.arch_fill(me, -2.3, 2.3, -0.8, 0.8, 3.6, 2.0, 6.4, n=12)
    me.box(T(0, 0, 6.6), (7.6, 1.8, 0.4), "ashlar")
    C.merlons(me, (-3.7, -0.7), (3.7, -0.7), 6.8, w=0.7, gap=0.55, t=0.4)
    me.box(T(0, -0.85, 5.55), (0.5, 0.15, 0.7), "limestone")
    for s in (-1, 1):
        C.wall_lantern(me, s * 3.0, -0.8, 3.2)
    C.banner(me, 0.0, -0.9, 6.2, 1.6, mat="cloth_blue")
    DT.ivy(me, rnd, Vector((-3.4, -0.8, 0.0)), (1, 0, 0), 4.5, spread=0.6)
    K.proxy_box(sh, -3.7, 3.7, -0.8, 0.8, 3.6, 6.8)
    return me, sh


# =============================================================================
# props
# =============================================================================

def stall_c():
    """A tent stall: a pitched canopy in red and cream stripes over a counter
    of baskets."""
    me = K.Mesh("stall_c")
    me.box(T(0, 0, 0.45), (2.4, 0.9, 0.9), "planks")
    for x in (-1.2, 1.2):
        for y in (-0.6, 0.6):
            K.beam(me, (x, y, 0), (x, y, 2.0))
        K.beam(me, (x, 0, 0), (x, 0, 2.7))
    K.beam(me, (-1.3, 0, 2.7), (1.3, 0, 2.7), 0.08, 0.08)
    ang = math.degrees(math.atan2(0.7, 0.9))
    for k in range(7):
        x = -1.3 + (k + 0.5) * 2.6 / 7
        for s in (-1, 1):
            # green and cream (2026-09-30, "city life" plan: stall_a is red, stall_b blue)
            me.box(T(x, s * 0.5, 2.35, rx=s * ang), (2.6 / 7 + 0.005, 1.15, 0.04), ("paint_green", "cloth_cream")[k % 2])
    rnd = random.Random(541)
    for k, x in enumerate((-0.8, 0.0, 0.8)):
        C.cyl(me, x, -0.1, 0.9, 1.15, 0.28, "thatch", n=8, r1=0.32)
        for _ in range(5):
            me.box(T(x + rnd.uniform(-0.15, 0.15), -0.1 + rnd.uniform(-0.15, 0.15), 1.2), (0.12, 0.12, 0.1),
                   ("cloth_red", "crops", "moss")[k])
    return me, None


def large_stall():
    """A covered market stall 4 m wide: six posts, a shingle roof, two
    counters, goods, a lantern."""
    me = K.Mesh("large_stall")
    for x in (-2.0, 0.0, 2.0):
        for y in (-0.9, 0.9):
            K.beam(me, (x, y, 0), (x, y, 2.4), 0.14, 0.14)
    C.roof(me, -2.1, 2.1, -1.0, 1.0, 2.4, 35, "shingle", over_eave=0.35, over_gable=0.2, thick=0.1, ridge_axis="x")
    for x in (-1.0, 1.0):
        me.box(T(x, -0.4, 0.45), (1.8, 0.8, 0.9), "planks")
    rnd = random.Random(542)
    for k in range(6):
        P.crate(me, -1.6 + k * 0.62, -0.4, 0.9, 0.45, rz=rnd.uniform(-8, 8), top=("clay_tile", "moss", "crops")[k % 3])
    for k in range(4):
        P.sack(me, -1.5 + k * 1.0, 0.55, 0.0, 0.9, rz=k * 20)
    me.box(T(0.0, -0.9, 2.15), (0.02, 0.02, 0.2), "iron")
    me.box(T(0.0, -0.9, 1.92), (0.16, 0.16, 0.26), "M_Lamp")
    return me, K.Mesh("SHADOW_large_stall")


def crate_pile():
    me = K.Mesh("crate_pile")
    for k, (x, y, z, s) in enumerate(((0, 0, 0, 0.7), (0.72, 0.05, 0, 0.7), (1.44, 0, 0, 0.66), (0.35, 0.02, 0.7, 0.66),
                                      (1.07, 0.04, 0.7, 0.62), (0.7, 0.03, 1.36, 0.58))):
        P.crate(me, x, y, z, s, rz=(k * 7) % 15 - 7, top="moss" if k == 5 else None)
    return me, None


def barrel_stack():
    me = K.Mesh("barrel_stack")
    for k in range(3):
        P.barrel(me, -0.7 + k * 0.7, 0, 0.0, lying=True)
    for k in range(2):
        P.barrel(me, -0.35 + k * 0.7, 0, 0.58, lying=True)
    P.barrel(me, 0.0, 0, 1.16, lying=True)
    for y in (-0.5, 0.5):
        K.beam(me, (-1.1, y, 0.05), (1.1, y, 0.05), 0.1, 0.1)
    return me, None


def fountain_small():
    """A small round fountain: a basin, a column, a bowl, water."""
    me = K.Mesh("fountain_small")
    C.cyl(me, 0, 0, 0.0, 0.7, 1.5, "ashlar", n=16)
    C.cyl(me, 0, 0, 0.55, 0.62, 1.35, "water", n=16)
    C.cyl(me, 0, 0, 0.6, 1.9, 0.22, "limestone", n=10)
    C.cyl(me, 0, 0, 1.9, 2.2, 0.35, "limestone", n=12, r1=0.7)
    C.cyl(me, 0, 0, 2.12, 2.18, 0.62, "water", n=12)
    C.cyl(me, 0, 0, 2.2, 2.7, 0.08, "limestone", n=8)
    for k in range(8):                                   # jets arcing from the bowl into the basin
        a = k * math.tau / 8
        prev = None
        for j in range(7):
            t = j / 6
            r, z = 0.66 + 0.5 * t, 2.1 - 1.45 * t * t
            p = Vector((r * math.cos(a), r * math.sin(a), z))
            if prev is not None:
                K.beam(me, prev, p, 0.07, 0.05, mat="water")
            prev = p
    rnd = random.Random(545)
    for _ in range(8):
        a = rnd.uniform(0, math.tau)
        me.box(T(1.45 * math.cos(a), 1.45 * math.sin(a), 0.72, rz=math.degrees(a)), (0.25, 0.18, 0.05), "moss")
    return me, None


def tree_planter():
    """A square stone planter with a young tree in bloom-edged soil."""
    me = K.Mesh("tree_planter")
    rnd = random.Random(546)
    me.box(T(0, 0, 0.3), (1.4, 1.4, 0.6), "ashlar", faces={"+z": "dirt"})
    C.cyl(me, 0, 0, 0.6, 2.2, 0.1, "bark", n=6, r1=0.07)
    for (x, y, z, r) in ((0, 0, 2.6, 0.9), (0.4, 0.2, 2.3, 0.6), (-0.35, -0.25, 2.35, 0.6)):
        P._canopy(me, rnd, x, y, z, r)
    for _ in range(8):
        x, y = rnd.uniform(-0.55, 0.55), rnd.uniform(-0.55, 0.55)
        me.box(T(x, y, 0.66), (0.16, 0.16, 0.1), "moss")
        me.box(T(x, y, 0.74), (0.07, 0.07, 0.06), rnd.choice(("cloth_red", "crops", "cloth_cream")))
    return me, None


def laundry_line():
    """Washing hung between two posts: shirts, sheets and cloths."""
    me = K.Mesh("laundry_line")
    for x in (-2.2, 2.2):
        K.beam(me, (x, 0, 0), (x, 0, 2.3), 0.1, 0.1)
    K.beam(me, (-2.2, 0, 2.2), (2.2, 0, 2.05), 0.02, 0.02, mat="thatch")
    cols = ("cloth_cream", "cloth_blue", "cloth_red", "cloth_cream", "cloth_blue", "cloth_cream")
    for k, c in enumerate(cols):
        x = -1.8 + k * 0.72
        h = (0.9, 0.55, 0.7, 1.1, 0.5, 0.8)[k]
        me.box(T(x, 0, 2.12 - h / 2 - 0.02 * k / 6), (0.55 if h > 0.6 else 0.4, 0.03, h), c)
    return me, None


def laundry_span():
    """Washing strung across a street between two poles 7.6 m apart, 4.2 m up
    (the target sheet's Old City: laundry across the lanes). Overhead, like the
    bunting: the span runs along x, so it is placed facing along the road."""
    me = K.Mesh("laundry_span")
    half = 3.8
    for s_ in (-1, 1):
        C.rod(me, (s_ * half, 0, 0), (s_ * half, 0, 4.6), 0.07, "timber", n=6)
        K.beam(me, (s_ * half, 0, 4.4), (s_ * (half - 0.4), 0, 4.4), 0.05, 0.05)
    n = 12
    pts = [Vector((-half + 2 * half * i / n, 0, 4.35 - 0.5 * (1 - (2 * i / n - 1) ** 2))) for i in range(n + 1)]
    for a, b in zip(pts, pts[1:]):
        C.rod(me, a, b, 0.015, "thatch", n=4)
    rnd = random.Random(557)
    cols = ("cloth_cream", "cloth_blue", "cloth_red", "cloth_cream", "cloth_cream")
    for i in range(1, n, 1):
        if rnd.random() < 0.25:
            continue
        h = rnd.uniform(0.45, 1.0)
        w = rnd.uniform(0.35, 0.6)
        me.box(T(pts[i].x, 0, pts[i].z - h / 2 - 0.02), (w, 0.03, h), rnd.choice(cols))
    return me, None


def forge():
    """An open forge: a stone hearth with coals, a hood and chimney, bellows,
    an anvil on its stump, tools on a rack."""
    me = K.Mesh("forge")
    me.box(T(0, 0, 0.45), (1.8, 1.4, 0.9), "fieldstone", faces={"+z": "ashlar"})
    me.box(T(0, 0.1, 0.94), (1.0, 0.8, 0.1), "M_Lamp")
    for s in (-1, 1):
        K.beam(me, (s * 0.85, 0.6, 0.9), (s * 0.85, 0.6, 2.2), 0.12, 0.12)
    C.pyramid(me, 0, 0.3, 2.0, 1.1, 1.0, "brick", n=4)
    me.cbox(T(0, 0.3, 3.4), (0.6, 0.6, 1.6), "brick", 0.04)
    me.box(T(1.25, 0.3, 0.7), (0.6, 0.9, 0.35), "planks")
    me.box(T(1.25, 0.3, 0.9), (0.55, 0.85, 0.06), "cloth_red")
    C.cyl(me, -0.1, -1.4, 0, 0.55, 0.32, "bark", n=8, top="timber")
    me.box(T(-0.1, -1.4, 0.68), (0.25, 0.2, 0.26), "iron")
    me.box(T(-0.1, -1.4, 0.86), (0.7, 0.24, 0.14), "iron")
    for k in range(4):
        K.beam(me, (-1.3, -0.5 + k * 0.25, 0.1), (-1.3, -0.5 + k * 0.25, 1.4), 0.03, 0.03, mat="iron")
    K.beam(me, (-1.3, -0.65, 1.3), (-1.3, 0.35, 1.3), 0.06, 0.06)
    return me, K.Mesh("SHADOW_forge")


def statue_saint():
    """A robed figure in pale stone on a plinth, a book held to the chest."""
    me = K.Mesh("statue_saint")
    me.box(T(0, 0, 0.6), (1.4, 1.4, 1.2), "ashlar", faces={"+z": "flagstone"})
    # smooth plaster, not limestone: its block lines made the robe read as a tower
    C.cyl(me, 0, 0, 1.2, 2.9, 0.5, "plaster", n=10, r1=0.3)
    C.cyl(me, 0, 0, 2.75, 3.0, 0.42, "plaster", n=10, r1=0.36)
    C.cyl(me, 0, 0, 3.0, 3.35, 0.19, "plaster", n=10, r1=0.17)
    C.cyl(me, 0, -0.03, 3.3, 3.6, 0.25, "plaster", n=10, r1=0.08)
    me.box(T(0, -0.36, 2.4), (0.34, 0.1, 0.42), "cloth_cream")
    for s in (-1, 1):
        K.beam(me, (s * 0.32, -0.05, 2.8), (s * 0.12, -0.36, 2.35), 0.1, 0.1, mat="plaster")
    rnd = random.Random(549)
    DT.flower_strip(me, rnd, (-0.9, -0.95, 0), (0.9, -0.95, 0), w=0.4)
    for _ in range(4):
        me.box(T(rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 1.23, rz=rnd.uniform(0, 90)), (0.22, 0.18, 0.05), "moss")
    return me, K.Mesh("SHADOW_statue_saint")


def monument():
    """An obelisk on a stepped base, a plaque, flowers laid at its foot."""
    me = K.Mesh("monument")
    for k, s in enumerate((2.4, 1.9, 1.4)):
        me.box(T(0, 0, 0.2 + k * 0.4), (s, s, 0.4), "ashlar")
    C.cyl(me, 0, 0, 1.2, 5.2, 0.55, "limestone", n=4, r1=0.3, rot=45)
    C.pyramid(me, 0, 0, 5.2, 0.42, 0.5, "limestone", n=4)
    me.box(T(0, -0.52, 1.8), (0.5, 0.04, 0.4), "crops")
    rnd = random.Random(550)
    DT.pots(me, rnd, ((-0.8, -1.45, 0.0), (0.8, -1.45, 0.0)))
    for _ in range(6):
        me.box(T(rnd.uniform(-0.5, 0.5), -1.05, 0.44, rz=rnd.uniform(0, 90)), (0.12, 0.12, 0.08),
               rnd.choice(("cloth_red", "crops", "cloth_cream")))
    return me, K.Mesh("SHADOW_monument")


def table_set():
    me = K.Mesh("table_set")
    DT.table_set(me, (0, 0, 0), (1, 0, 0), random.Random(551))
    return me, None


def training_dummy():
    """A straw man on a post: sack body, crossbar arms, a leather target."""
    me = K.Mesh("training_dummy")
    K.beam(me, (0, 0, 0), (0, 0, 2.0), 0.12, 0.12)
    C.cyl(me, 0, 0, 0.9, 1.7, 0.28, "cloth_cream", n=8, r1=0.24)
    K.beam(me, (-0.6, 0, 1.5), (0.6, 0, 1.5), 0.08, 0.08)
    C.cyl(me, 0, 0, 1.7, 2.05, 0.16, "cloth_cream", n=8, r1=0.12)
    me.box(T(0, -0.27, 1.3), (0.26, 0.04, 0.26), "cloth_red")
    for s in (-1, 1):
        me.box(T(s * 0.62, 0, 1.5), (0.12, 0.12, 0.22), "thatch")
    for dx in (-0.35, 0.35):
        K.beam(me, (0, 0, 0.4), (dx, 0.3, 0.0), 0.06, 0.06)
    return me, None


def drying_rack():
    """A rack of herbs and hides drying in the sun."""
    me = K.Mesh("drying_rack")
    for x in (-1.2, 1.2):
        K.beam(me, (x, -0.4, 0), (x, 0, 1.9), 0.08, 0.08)
        K.beam(me, (x, 0.4, 0), (x, 0, 1.9), 0.08, 0.08)
    for zz in (1.1, 1.8):
        K.beam(me, (-1.3, 0, zz), (1.3, 0, zz), 0.05, 0.05)
    rnd = random.Random(553)
    for k in range(7):
        x = -1.0 + k * 0.33
        me.box(T(x, 0, 1.55), (0.14, 0.14, 0.4), rnd.choice(("moss", "crops", "thatch")))
    me.box(T(-0.4, 0, 0.75), (0.8, 0.04, 0.65), "planks")
    me.box(T(0.5, 0, 0.8), (0.7, 0.04, 0.55), "cloth_cream")
    return me, None


def bunting_pennant():
    """A short run of blue, cream and gold pennants between two poles."""
    me = K.Mesh("bunting_pennant")
    half = 3.0
    for s in (-1, 1):
        C.rod(me, (s * half, 0, 0), (s * half, 0, 4.6), 0.06, "timber", n=6)
    n = 10
    pts = [Vector((-half + 2 * half * i / n, 0, 4.45 - 0.6 * (1 - (2 * i / n - 1) ** 2))) for i in range(n + 1)]
    for a, b in zip(pts, pts[1:]):
        C.rod(me, a, b, 0.015, "timber", n=4)
    for i in range(1, n):
        me.prism(pts[i] + Vector((0, 0.01, 0)), X, Z, [(-0.18, 0), (0.18, 0), (0, -0.4)], 0.02,
                 ("cloth_blue", "cloth_cream", "crops")[i % 3])
    return me, None


def pergola():
    """A timber pergola: four posts, beams and rafters, vines over the top."""
    me = K.Mesh("pergola")
    for x in (-1.5, 1.5):
        for y in (-1.2, 1.2):
            K.beam(me, (x, y, 0), (x, y, 2.5), 0.14, 0.14)
    for y in (-1.2, 1.2):
        K.beam(me, (-1.8, y, 2.5), (1.8, y, 2.5), 0.12, 0.16)
    for k in range(7):
        x = -1.5 + k * 0.5
        K.beam(me, (x, -1.5, 2.65), (x, 1.5, 2.65), 0.08, 0.12)
    rnd = random.Random(555)
    for _ in range(26):
        me.box(T(rnd.uniform(-1.6, 1.6), rnd.uniform(-1.4, 1.4), 2.78, rz=rnd.uniform(0, 90)), (0.35, 0.3, 0.14), "moss")
    for x, y in ((-1.5, -1.2), (1.5, 1.2)):
        DT.ivy(me, rnd, Vector((x, y - 0.1, 0.0)), (1, 0, 0), 2.4, spread=0.25)
    for _ in range(6):
        me.box(T(rnd.uniform(-1.4, 1.4), rnd.uniform(-1.3, 1.3), 2.86), (0.09, 0.09, 0.06), rnd.choice(("cloth_red", "cloth_cream")))
    return me, None


def mooring_post():
    """A timber mooring post with a rope wrapped round it and an iron ring."""
    me = K.Mesh("mooring_post")
    C.cyl(me, 0, 0, 0, 1.2, 0.2, "bark", n=8, r1=0.18)
    C.cyl(me, 0, 0, 1.2, 1.28, 0.22, "iron", n=8)
    for k in range(10):
        a = k * math.tau / 10
        me.box(T(0.21 * math.cos(a), 0.21 * math.sin(a), 0.75 + k * 0.012, rz=math.degrees(a)), (0.06, 0.1, 0.06), "thatch")
    K.beam(me, (0.2, 0, 0.75), (1.4, -0.6, 0.02), 0.04, 0.04, mat="thatch")
    for k in range(8):
        a, b = k * math.tau / 8, (k + 1) * math.tau / 8
        K.beam(me, (0, -0.2 - 0.12 + 0.12 * math.cos(a), 0.5 + 0.12 * math.sin(a)),
               (0, -0.2 - 0.12 + 0.12 * math.cos(b), 0.5 + 0.12 * math.sin(b)), 0.025, 0.025, mat="iron")
    return me, None


def fishing_nets():
    """Nets hung to dry on a frame of poles, with floats."""
    me = K.Mesh("fishing_nets")
    for x in (-1.6, 0.0, 1.6):
        K.beam(me, (x, 0, 0), (x, 0, 2.2), 0.08, 0.08)
    K.beam(me, (-1.7, 0, 2.15), (1.7, 0, 2.15), 0.05, 0.05)
    for k, x in enumerate((-0.8, 0.8)):
        me.box(T(x, 0, 1.5), (1.4, 0.04, 1.2), "bark")
        for j in range(4):
            me.box(T(x - 0.55 + j * 0.37, -0.04, 0.88), (0.12, 0.08, 0.12), ("cloth_red", "cloth_cream")[j % 2])
    me.box(T(0.4, -0.5, 0.1), (1.2, 0.8, 0.2), "bark")
    return me, None


def harbour_hut():
    """A small harbour hut: planks, a shingle roof, a door, a lit window,
    barrels and a net."""
    me, sh = C._pair("harbour_hut")
    C.house(me, 4.0, 3.4, 1, ground="planks", cover="shingle", pitch=40, ridge="x", door=0.6, sh=sh, dormers=(),
            extras=False)
    C._barrel(me, 1.4, -2.3)
    me.box(T(-1.2, -2.2, 0.1), (1.0, 0.7, 0.2), "bark")
    C.wall_lantern(me, -0.2, -1.7, 2.3)
    return me, sh


def shed():
    """A lean-to shed: a mono-pitch plank roof on posts, tools and a barrow."""
    me = K.Mesh("shed")
    for x in (-1.5, 1.5):
        K.beam(me, (x, -1.0, 0), (x, -1.0, 2.0), 0.12, 0.12)
        K.beam(me, (x, 1.0, 0), (x, 1.0, 2.6), 0.12, 0.12)
    me.box(T(0, 1.0, 1.3), (3.0, 0.08, 2.6), "planks", axis=(0, 0, 1))
    for s in (-1, 1):
        me.box(T(s * 1.5, 0.3, 1.1), (0.08, 1.4, 2.2), "planks", axis=(0, 0, 1))
    ang = math.degrees(math.atan2(0.6, 2.0))
    me.box(T(0, 0, 2.4, rx=ang), (3.4, 2.6, 0.08), "planks", faces={"+z": "shingle"})
    for k in range(3):
        K.beam(me, (-1.0 + k * 0.4, 0.9, 0.0), (-1.0 + k * 0.4, 0.8, 1.6), 0.04, 0.04)
    me.box(T(0.8, 0.2, 0.35), (0.7, 0.5, 0.3), "planks")
    C.rod(me, (0.8, -0.2, 0.15), (0.8, -0.35, 0.15), 0.15, "iron", n=8)
    P.sack(me, 0.3, 0.4, 0.0, 0.8)
    return me, None


# =============================================================================
# ships
# =============================================================================

def ship_cargo():
    """A cargo cog: one mast with a big square sail, a raised stern castle,
    cargo lashed on deck."""
    me = K.Mesh("ship_cargo")
    L, B = 14.0, 5.0
    top, hw = P.hull(me, L, B, -1.6, 1.2, rise=1.2)
    me.box(T(-5.0, 0, top(-5.0) + 0.8), (3.4, 3.8, 1.6), "planks", axis=(1, 0, 0))
    me.box(T(-5.1, 0, top(-5.0) + 1.65), (3.7, 4.1, 0.14), "timber")
    for k in range(2):
        me.box(T(-6.72, -0.8 + k * 1.6, top(-5.0) + 0.9), (0.04, 0.5, 0.45), "M_Window_Dim")
    z0 = top(0.5) - 0.3
    C.rod(me, (0.5, 0, z0), (0.5, 0, z0 + 11.0), 0.2, "timber", n=8, r1=0.13)
    P.sail(me, 0.5, z0 + 6.0, 6.0, 5.2, mat="cloth_cream")
    me.box(T(0.9, 0.0, z0 + 6.0), (0.06, 1.2, 1.2), "cloth_red")
    for s in (-1, 1):
        for k in range(3):
            K.beam(me, (0.5 - 0.6 + k * 0.6, s * hw(0.5) * 0.98, top(0.5)), (0.5, s * 0.2, z0 + 8.5), 0.03, 0.03, mat="thatch")
    C.rod(me, (6.5, 0, top(6.5)), (9.5, 0, top(6.5) + 1.8), 0.12, "timber", n=6)
    P._ship_dress(me, top, hw, L, random.Random(561), cargo=((-2.2, 0.8), (-1.6, -0.9), (2.4, 0.7), (3.0, -0.6)),
                  stern=-6.8, flag="cloth_red")
    sh = K.Mesh("SHADOW_ship_cargo")
    K.proxy_box(sh, -7, 7, -2.5, 2.5, -1.2, 3.0)
    return me, sh


def sailboat():
    """A small sailboat with a triangular sail, a tiller, a coil of rope."""
    me = K.Mesh("sailboat")
    top, hw = P.hull(me, 6.0, 2.0, -0.6, 0.5, rise=0.4, n=8)
    z0 = top(0.6) - 0.2
    C.rod(me, (0.6, 0, z0), (0.6, 0, z0 + 5.5), 0.07, "timber", n=6)
    K.beam(me, (0.6, 0, z0 + 0.9), (-2.4, 0, z0 + 1.0), 0.06, 0.06)
    me.prism(Vector((0.6, 0.02, z0 + 1.0)), -X, Z, [(0, 0), (3.0, 0), (0, 4.4)], 0.03, "cloth_cream")
    me.prism(Vector((0.62, 0.02, z0 + 1.0)), X, Z, [(0, 0), (2.2, 0), (0, 3.6)], 0.03, "cloth_red")
    K.beam(me, (-2.8, 0, top(-2.8) + 0.2), (-2.1, 0, top(-2.8) + 0.5), 0.05, 0.05)
    for k in range(10):
        a, b = k * math.tau / 10, (k + 1) * math.tau / 10
        K.beam(me, (-1.0 + 0.22 * math.cos(a), 0.3 + 0.22 * math.sin(a), top(-1.0) - 0.1),
               (-1.0 + 0.22 * math.cos(b), 0.3 + 0.22 * math.sin(b), top(-1.0) - 0.1), 0.06, 0.06, mat="thatch")
    return me, None


def dock_barge():
    """A flat river barge: a plank deck with cargo, a steering oar, poles."""
    me = K.Mesh("dock_barge")
    me.box(T(0, 0, 0.0), (10.0, 3.8, 0.8), "planks", axis=(1, 0, 0))
    for s in (-1, 1):
        me.box(T(s * 5.1, 0, 0.1), (0.4, 3.6, 0.6), "planks")
        K.beam(me, (-5, s * 1.9, 0.45), (5, s * 1.9, 0.45), 0.14, 0.14)
    rnd = random.Random(563)
    for k in range(4):
        P.crate(me, -2.5 + k * 0.75, 0.6, 0.4, 0.7, rz=rnd.uniform(-8, 8))
    for k in range(3):
        P.barrel(me, 1.2 + k * 0.75, -0.7, 0.4)
    for k in range(3):
        P.sack(me, -2.0 + k * 0.6, -0.9, 0.4, 0.9, rz=k * 25)
    K.beam(me, (4.6, 0, 0.9), (6.4, 0, -0.2), 0.08, 0.08)
    me.box(T(6.3, 0, -0.15), (0.6, 0.06, 0.4), "planks")
    for s in (-1, 1):
        K.beam(me, (-4.2, s * 1.6, 0.4), (-1.0, s * 1.7, 1.2), 0.05, 0.05)
    return me, None


BUILDINGS = [inn, apothecary, cathedral, granary, market_hall, library, town_hall, mansion, small_keep, mill_house,
             stable_yard, dockhouse, fisher_house]
VARIANTS = [townhouse_arched, townhouse_wooden, townhouse_stone, cottage_thatch, merchant_house, alley_house, city_house,
            river_house, tower_house]
STRUCTURES = [C.retaining_tall(4), C.retaining_tall(8), bridge_covered, dock_platform, sluice_gate, riverbank,
              stone_stairs, archway]
PROPS = [stall_c, large_stall, crate_pile, barrel_stack, fountain_small, tree_planter, laundry_line, forge, statue_saint,
         monument, table_set, training_dummy, drying_rack, bunting_pennant, pergola, mooring_post, fishing_nets,
         harbour_hut, shed, laundry_span]
SHIPS = [ship_cargo, sailboat, dock_barge]
