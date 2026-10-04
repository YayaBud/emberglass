"""The Emberglass city's props and ships, and the snow / desert kit pieces
the city reuses (snow and sand faces dropped, their materials renamed to
the world's texgen surfaces).

Same conventions as citykit.py: kit Mesh, texgen surface names, front -Y,
ground z = 0. Each function returns (visual Mesh, shadow Mesh or None --
small props cast no shadow, memory.md "Adding assets").
"""
import math
import os
import random
import sys

from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from citykit import K, T, X, Y, Z, cyl, rod, pyramid, merlons, disc, wall_lantern, banner, hanging_sign  # noqa
import detail as DT  # noqa: E402  (2026-09-30: the detail rollout)

sys.path.insert(0, os.path.join(HERE, "..", "snowkit"))
sys.path.insert(0, os.path.join(HERE, "..", "desertkit"))


def _m(name):
    return K.Mesh(name)


def barrel(me, x, y, z=0.0, s=1.0, mat="planks", lying=False):
    prof = [(0.26, 0.0), (0.31, 0.22), (0.33, 0.45), (0.31, 0.68), (0.26, 0.9)]
    for (r0, z0), (r1, z1) in zip(prof, prof[1:]):
        if lying:
            rod(me, (x, y + z0 * s - 0.45 * s, z + 0.33 * s), (x, y + z1 * s - 0.45 * s, z + 0.33 * s), r0 * s, mat,
                n=10, r1=r1 * s)
        else:
            cyl(me, x, y, z + z0 * s, z + z1 * s, r0 * s, mat, n=10, r1=r1 * s, top="timber")
    if not lying:
        for zz in (0.12, 0.76):
            cyl(me, x, y, z + zz * s, z + (zz + 0.05) * s, 0.325 * s, "iron", n=10)


def crate(me, x, y, z, s, rz=0.0, top=None):
    me.box(T(x, y, z + s / 2, rz=rz), (s, s, s), "planks")
    for dz in (0.04, s - 0.04):
        me.box(T(x, y, z + dz, rz=rz), (s + 0.02, s + 0.02, 0.06), "timber")
    # a diagonal batten on two faces (2026-09-30, the detail rollout)
    me.box(T(x, y, z + s / 2, rz=rz) @ T(0, -s / 2 - 0.015, 0, ry=45), (s * 1.25, 0.03, 0.07), "timber")
    me.box(T(x, y, z + s / 2, rz=rz) @ T(-s / 2 - 0.015, 0, 0, rz=90, ry=-45), (s * 1.25, 0.03, 0.07), "timber")
    if top:
        me.box(T(x, y, z + s + 0.03, rz=rz), (s - 0.08, s - 0.08, 0.1), top)


def sack(me, x, y, z, s=1.0, rz=0.0, mat="cloth_cream"):
    me.box(T(x, y, z + 0.22 * s, rz=rz), (0.5 * s, 0.36 * s, 0.44 * s), mat)
    me.box(T(x, y, z + 0.5 * s, rz=rz), (0.3 * s, 0.22 * s, 0.14 * s), mat)
    me.box(T(x, y, z + 0.6 * s, rz=rz), (0.1 * s, 0.1 * s, 0.08 * s), "thatch")


# ---------------------------------------------------------------- market
def market_stall_a():
    """Counter and shelf under a red striped canopy, crates of produce."""
    me = _m("market_stall_a")
    me.box(T(0, 0, 0.45), (2.6, 0.9, 0.9), "planks")
    me.box(T(0, -0.05, 0.93), (2.8, 1.1, 0.06), "timber")
    for x in (-1.3, 1.3):
        for y in (-0.55, 0.9):
            K.beam(me, (x, y, 0), (x, y, 2.2 if y < 0 else 2.7))
    ang = math.degrees(math.atan2(0.5, 1.6))
    for k in range(8):                                   # striped canopy (2026-09-30)
        me.box(T(-1.5 + (k + 0.5) * 0.375, 0.15, 2.5, rx=-ang), (0.38, 1.8, 0.05), ("cloth_red", "cloth_cream")[k % 2])
    for x in range(7):
        me.box(T(-1.35 + x * 0.45, -0.72, 2.12), (0.22, 0.03, 0.2), ("cloth_red", "cloth_cream")[x % 2])
    for k, x in enumerate((-0.9, -0.3, 0.4)):            # strings of garlic, herbs, onions
        for j in range(4):
            me.box(T(x, -0.6, 2.0 - j * 0.14, rz=j * 30), (0.1, 0.1, 0.1), ("cloth_cream", "moss", "clay_tile")[k])
    me.box(T(1.1, -0.6, 2.05), (0.02, 0.02, 0.2), "iron")
    me.box(T(1.1, -0.6, 1.82), (0.16, 0.16, 0.26), "M_Lamp")
    for i, (x, top) in enumerate(((-0.85, "clay_tile"), (-0.1, "moss"), (0.65, "crops"))):
        crate(me, x, -0.05, 0.96, 0.5, rz=(i - 1) * 6, top=top)
    me.box(T(0, 0.75, 1.5), (2.4, 0.4, 0.05), "planks")
    for x in (-0.8, 0.0, 0.8):
        cyl(me, x, 0.75, 1.53, 1.8, 0.14, "clay_tile", n=8, r1=0.1)
    return me, None


def market_stall_b():
    """Two-tier stall under a blue striped canopy: pots, cloth bolts, sacks."""
    me = _m("market_stall_b")
    me.box(T(0, 0, 0.4), (2.4, 1.0, 0.8), "planks")
    me.box(T(0, 0.35, 1.05), (2.4, 0.45, 0.5), "planks")
    for x in (-1.2, 1.2):
        for y in (-0.6, 0.6):
            K.beam(me, (x, y, 0), (x, y, 2.4))
    me.prism(Vector((1.35, -0.8, 2.4)), Y, Z, [(0, 0), (1.6, 0), (0.8, 0.6)], 2.7, "cloth_blue")
    for i, x in enumerate((-0.8, -0.3, 0.2, 0.7)):
        rod(me, (x - 0.18, -0.2, 0.9), (x + 0.18, -0.2, 0.9), 0.1, ("cloth_red", "cloth_cream", "cloth_blue", "cloth_red")[i], n=8)
    for x in (-0.7, 0.1, 0.8):
        cyl(me, x, 0.35, 1.3, 1.6, 0.15, "clay_tile", n=8, r1=0.11)
    sack(me, 1.5, -0.3, 0.0)
    sack(me, 1.55, 0.25, 0.0, 0.9, rz=20)
    for k in range(8):                                   # valance and hanging cloth (2026-09-30)
        me.prism(Vector((-1.35 + k * 0.34, -0.82, 2.42)), X, Z, [(0, 0), (0.34, 0), (0.17, -0.22)], 0.03,
                 ("cloth_blue", "cloth_cream")[k % 2])
    for k, x in enumerate((-0.95, 0.95)):
        me.box(T(x, -0.62, 1.9), (0.5, 0.03, 0.9), ("cloth_red", "cloth_cream")[k])
    me.box(T(0.0, -0.7, 2.25), (0.02, 0.02, 0.2), "iron")
    me.box(T(0.0, -0.7, 2.02), (0.16, 0.16, 0.26), "M_Lamp")
    return me, None


def awning():
    """A striped cloth awning for a shopfront: two brackets and a slope."""
    me = _m("awning")
    ang = math.degrees(math.atan2(0.6, 1.4))
    for k in range(8):                                   # stripes (2026-09-30)
        me.box(T(-1.4 + (k + 0.5) * 0.35, -0.7, 2.55, rx=-ang), (0.355, 1.55, 0.04), ("cloth_blue", "cloth_cream")[k % 2])
    for x in (-1.3, 1.3):
        K.beam(me, (x, 0, 2.85), (x, -1.35, 2.3), 0.06, 0.06, mat="iron")
        K.beam(me, (x, 0, 2.0), (x, -1.0, 2.4), 0.05, 0.05, mat="iron")
    for k in range(9):
        me.box(T(-1.4 + k * 0.35, -1.36, 2.18), (0.18, 0.03, 0.18), ("cloth_blue", "cloth_cream")[k % 2])
    return me, None


def sacks():
    me = _m("sacks")
    for x, y, z, rz in ((0, 0, 0, 0), (0.45, 0.1, 0, 25), (-0.4, 0.15, 0, -15), (0.1, 0.35, 0, 70), (0.2, 0.1, 0.5, 40)):
        sack(me, x, y, z, rz=rz)
    return me, None


def goods_crates():
    me = _m("goods_crates")
    crate(me, 0, 0, 0, 0.6, top="clay_tile")
    crate(me, 0.65, 0.05, 0, 0.55, rz=8, top="moss")
    crate(me, 0.3, 0.02, 0.6, 0.5, rz=-10)
    crate(me, -0.6, 0.1, 0, 0.5, rz=-5, top="crops")
    barrel(me, 1.3, 0.3, s=0.9)
    return me, None


def fountain():
    """The Grand Market Fountain (user, 2026-09-29, after the reference sheet
    "Emberglass Grand Market Fountain"): ~14 m across and ~8.5 m to the star.
    Three octagonal steps, a coped basin of blue water, an octagonal pedestal
    hung with four blue banners, a crowned king in pale stone with a blue cape
    and a gold staff whose star glows, four lions spouting into the basin,
    eight corner lanterns (real lights) and flower beds between them."""
    me = _m("fountain")
    rnd = random.Random(1717)
    oct_ = dict(n=8, rot=22.5)
    # the steps: three tiers, honey ashlar faces, flagstone treads
    for r, z0, z1 in ((7.0, -0.2, 0.18), (6.55, 0.18, 0.36), (6.1, 0.36, 0.54)):
        cyl(me, 0, 0, z0, z1, r, "limestone", top="flagstone", **oct_)
    # the basin wall with its coping, and the water
    rb = 5.6
    side = 2 * rb * math.tan(math.radians(22.5))
    for k in range(8):
        a = k * 45 + 22.5
        c = Vector((rb * math.cos(math.radians(a)), rb * math.sin(math.radians(a)), 0))
        me.box(T(c.x, c.y, 0.9, rz=a), (0.5, side + 0.22, 0.72), "limestone")
        me.box(T(c.x, c.y, 1.3, rz=a), (0.66, side + 0.36, 0.12), "flagstone")
    cyl(me, 0, 0, 0.54, 1.05, rb - 0.25, "water", **oct_)
    # the pedestal: an octagonal tower, a moulded cap, banners on four faces
    cyl(me, 0, 0, 1.05, 3.6, 1.9, "limestone", **oct_)
    cyl(me, 0, 0, 1.05, 1.35, 2.15, "limestone", top="flagstone", **oct_)
    cyl(me, 0, 0, 3.6, 3.85, 2.2, "limestone", top="flagstone", **oct_)
    for k in range(4):
        a = k * 90.0
        o = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        banner(me, o.x * 1.78, o.y * 1.78, 3.45, 1.9, mat="cloth_blue", w=0.85, rz=a)
        me.box(T(o.x * 1.9, o.y * 1.9, 2.75, rz=a + 90), (0.22, 0.05, 0.22), "crops")    # a gold emblem
    # ivy on the pedestal
    for k in range(10):
        a = rnd.uniform(0, math.tau)
        z = rnd.uniform(1.4, 3.3)
        me.box(T(1.95 * math.cos(a), 1.95 * math.sin(a), z, rz=math.degrees(a)), (0.12, rnd.uniform(0.3, 0.6), rnd.uniform(0.3, 0.8)), "moss")
    # the king (2026-09-30, user: "it is the main statue of the whole game, it looks
    # weak"): a sculpted figure 2.5x life size -- armoured, crowned, a tall gold staff
    # raised in the right hand with the lit star, a heater shield on the left arm, a
    # sword at the hip, a wide blue cape in folds with a gold hem -- on a taller
    # tiered plinth with a gold band. Built at life size under a scale in `me.xf`.
    stone, gold = "cloth_cream", "crops"
    cyl(me, 0, 0, 3.85, 4.05, 1.2, "limestone", top="flagstone", **oct_)
    cyl(me, 0, 0, 4.05, 4.6, 0.98, "limestone", **oct_)
    cyl(me, 0, 0, 4.28, 4.36, 1.0, gold, **oct_)
    cyl(me, 0, 0, 4.6, 4.72, 1.08, "limestone", top="flagstone", **oct_)
    me.box(T(0, 1.0, 4.45), (0.9, 0.06, 0.22), gold)                                        # the name plate
    # turned to +Y: the market's view (tour 00, the locked camera) looks at the
    # fountain from that side, and saw only the cape (2026-09-30)
    me.xf = Matrix.Translation((0, 0, 4.72)) @ Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Scale(2.5, 4)
    for x, y in ((-0.12, -0.05), (0.14, 0.08)):                                             # stance, sabatons
        me.box(T(x, y - 0.06, 0.04), (0.11, 0.27, 0.08), stone)
        rod(me, (x, y, 0.08), (x * 0.75, y * 0.5, 0.86), 0.07, stone, n=8, r1=0.085)
        cyl(me, x * 0.87, y * 0.75 - 0.03, 0.44, 0.52, 0.085, stone, n=8)                     # knee cop
    cyl(me, 0, 0, 0.72, 1.02, 0.27, stone, n=12, r1=0.19)                                   # armoured skirt
    me.box(T(0, -0.215, 0.8), (0.2, 0.03, 0.5), "royal")                               # tabard
    me.box(T(0, -0.235, 0.9, ry=45), (0.08, 0.02, 0.08), gold)
    cyl(me, 0, 0, 1.0, 1.44, 0.19, stone, n=12, r1=0.25)                                    # breastplate
    me.box(T(0, -0.225, 1.22), (0.04, 0.05, 0.36), stone)
    cyl(me, 0, 0, 1.0, 1.06, 0.205, gold, n=12)                                             # belt
    cyl(me, 0, 0, 1.38, 1.47, 0.24, stone, n=12, r1=0.19)                                   # mantle collar
    for sx in (-1, 1):                                                                      # pauldrons
        cyl(me, sx * 0.26, 0, 1.3, 1.44, 0.08, stone, n=8, r1=0.14)
        cyl(me, sx * 0.26, 0, 1.44, 1.52, 0.14, stone, n=8, r1=0.05)
    cyl(me, 0, 0, 1.46, 1.52, 0.07, stone, n=8)                                             # neck
    cyl(me, 0, 0, 1.52, 1.64, 0.09, stone, n=10, r1=0.115)                                  # head
    cyl(me, 0, 0, 1.64, 1.75, 0.115, stone, n=10, r1=0.095)
    me.box(T(0, -0.085, 1.56), (0.15, 0.08, 0.13), stone)                                   # beard
    me.box(T(0, -0.11, 1.48, rx=-20), (0.09, 0.06, 0.1), stone)
    me.box(T(0, -0.12, 1.65), (0.03, 0.04, 0.05), stone)                                    # nose
    cyl(me, 0, 0, 1.72, 1.81, 0.12, gold, n=10)                                             # crown
    for k in range(6):
        a = math.radians(k * 60 + 30)
        me.box(T(0.112 * math.cos(a), 0.112 * math.sin(a), 1.87, rz=k * 60 + 30), (0.04, 0.03, 0.14), gold)
    for k, c in enumerate(("cloth_red", "royal", "cloth_red")):
        a = math.radians(-90 + (k - 1) * 30)
        me.box(T(0.114 * math.cos(a), 0.114 * math.sin(a), 1.765, rz=k * 30), (0.03, 0.02, 0.03), c)
    # right arm raised on the staff; the staff and its star
    rod(me, (0.3, 0, 1.4), (0.42, -0.06, 1.24), 0.065, stone, n=8)
    rod(me, (0.42, -0.06, 1.24), (0.45, -0.15, 1.55), 0.055, stone, n=8)
    me.box(T(0.45, -0.15, 1.58), (0.09, 0.09, 0.11), stone)
    rod(me, (0.45, -0.15, 0.0), (0.45, -0.15, 2.5), 0.022, gold, n=6)
    for zz in (0.9, 1.9, 2.4):
        cyl(me, 0.45, -0.15, zz, zz + 0.04, 0.035, gold, n=6)
    me.box(T(0.45, -0.15, 2.62, ry=45), (0.12, 0.12, 0.12), "M_Lamp")
    for dx, dz in ((0.13, 0), (-0.13, 0), (0, 0.13), (0, -0.13)):
        me.box(T(0.45 + dx, -0.15, 2.62 + dz), (0.1 if dx else 0.025, 0.025, 0.1 if dz else 0.025), gold)
    # left arm on a heater shield: blue face, gold rim and a gold lozenge
    rod(me, (-0.3, 0, 1.4), (-0.38, -0.03, 1.15), 0.065, stone, n=8)
    rod(me, (-0.38, -0.03, 1.15), (-0.34, -0.2, 1.02), 0.055, stone, n=8)
    heater = [(-0.2, 0.25), (0.2, 0.25), (0.2, -0.04), (0.0, -0.32), (-0.2, -0.04)]
    me.prism(Vector((-0.36, -0.25, 0.98)), X, Z, [(u * 1.12, v * 1.1) for u, v in heater], 0.03, gold)
    me.prism(Vector((-0.36, -0.28, 0.98)), X, Z, heater, 0.04, "royal")
    me.box(T(-0.36, -0.3, 1.02, ry=45), (0.1, 0.02, 0.1), gold)
    # a sword at the right hip
    rod(me, (0.2, 0.08, 0.98), (0.3, 0.22, 0.32), 0.028, "timber", n=6)
    me.box(T(0.19, 0.06, 1.02, rx=20), (0.16, 0.03, 0.03), gold)
    # the cape: one solid tapered sheet from the shoulders to the plinth (separate
    # strips read as a cage in game), three fold ridges on it, a gold hem
    v = Vector((0, -0.12, 1.4)).normalized()
    # (clear of the torso: at y 0.16-0.28 its top half sat inside the breastplate,
    # which showed through pale)
    me.prism(Vector((0, 0.39, 0.04)), X, v, [(-0.4, 0), (0.4, 0), (0.29, 1.41), (-0.29, 1.41)], 0.05, "royal")
    for xf_ in (-0.2, 0.0, 0.2):
        K.beam(me, (xf_ * 0.75, 0.3, 1.38), (xf_ * 1.2, 0.45, 0.1), 0.06, 0.05, mat="royal", up=(0, 1, 0))
    K.beam(me, (-0.42, 0.42, 0.06), (0.42, 0.42, 0.06), 0.07, 0.06, mat=gold)
    for sx in (-1, 1):                                                                      # gold trim
        cyl(me, sx * 0.26, 0, 1.3, 1.34, 0.085, gold, n=8)
    me.box(T(0, -0.25, 1.22), (0.025, 0.03, 0.34), gold)
    me.xf = Matrix.Identity(4)
    # four fire braziers on the pedestal cap: the game hangs a light on each, so the
    # king is lit from below at dusk instead of standing as a dark shape on the sky
    for k in range(4):
        a = math.radians(45 + k * 90)
        bx, by = 1.75 * math.cos(a), 1.75 * math.sin(a)
        rod(me, (bx, by, 3.85), (bx, by, 4.55), 0.05, "iron", n=6)
        cyl(me, bx, by, 4.55, 4.8, 0.12, "iron", n=8, r1=0.26)
        me.box(T(bx, by, 4.82), (0.26, 0.26, 0.14), "M_Lamp")
    # four lions at the diagonals, facing out, spouting into the basin
    for k in range(4):
        a = math.radians(45 + k * 90)
        o = Vector((math.cos(a), math.sin(a), 0))
        deg = math.degrees(a)
        base = o * 2.55
        me.box(T(base.x, base.y, 1.2, rz=deg), (1.0, 0.9, 0.6), "limestone")                  # plinth in the water
        body = o * 2.5
        me.box(T(body.x, body.y, 1.85, rz=deg), (1.1, 0.7, 0.7), stone)
        head = o * 3.0
        cyl(me, head.x, head.y, 1.95, 2.75, 0.44, stone, n=8)                               # mane
        me.box(T(head.x + o.x * 0.3, head.y + o.y * 0.3, 2.3, rz=deg), (0.34, 0.42, 0.4), stone)   # muzzle
        paw = o * 3.05
        me.box(T(paw.x, paw.y, 1.62, rz=deg), (0.4, 0.62, 0.24), stone)
        mouth = head + o * 0.5
        rod(me, (mouth.x, mouth.y, 2.2), (mouth.x + o.x * 0.9, mouth.y + o.y * 0.9, 1.05), 0.08, "water", n=6)
    # eight lanterns on the top step's corners, flower beds between them
    for k in range(8):
        a = math.radians(22.5 + k * 45)
        c = Vector((6.3 * math.cos(a), 6.3 * math.sin(a), 0))
        rod(me, (c.x, c.y, 0.54), (c.x, c.y, 2.3), 0.06, "iron", n=6)
        me.box(T(c.x, c.y, 2.3), (0.3, 0.3, 0.05), "iron")
        me.box(T(c.x, c.y, 2.5), (0.22, 0.22, 0.36), "M_Lamp")
        pyramid(me, c.x, c.y, 2.68, 0.22, 0.2, "iron")
        b = math.radians(k * 45)
        bc = Vector((6.25 * math.cos(b), 6.25 * math.sin(b), 0.64))
        K.window_box(me, bc, (-math.sin(b), math.cos(b), 0), 1.5, rnd)
    return me, None


def planter():
    me = _m("planter")
    me.box(T(0, 0, 0.35), (1.2, 1.2, 0.7), "ashlar", faces={"+z": "dirt"})
    rod(me, (0, 0, 0.7), (0, 0, 1.6), 0.07, "bark", n=6)
    for k, (x, y, z, s) in enumerate(((0, 0, 1.9, 0.75), (0.25, 0.1, 1.7, 0.55), (-0.2, -0.15, 1.75, 0.5))):
        me.box(T(x, y, z, rz=k * 25), (s, s, s * 0.8), "moss")
    rnd = random.Random(209)                             # blooms round the foot (2026-09-30)
    for _ in range(10):
        x, y = rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5)
        me.box(T(x, y, 0.78, rz=rnd.uniform(0, 90)), (0.2, 0.2, 0.14), "moss")
        me.box(T(x, y, 0.88), (0.09, 0.09, 0.07), rnd.choice(("cloth_red", "crops", "cloth_cream", "cloth_blue")))
    return me, None


def notice_board():
    me = _m("notice_board")
    for x in (-0.8, 0.8):
        K.beam(me, (x, 0, -0.2), (x, 0, 2.2))
    me.box(T(0, -0.05, 1.45), (1.7, 0.08, 1.1), "planks")
    me.box(T(0, 0.1, 2.3, rx=-25), (2.0, 0.5, 0.05), "planks", faces={"+z": "shingle"})
    me.box(T(0, -0.1, 2.3, rx=25), (2.0, 0.5, 0.05), "planks", faces={"+z": "shingle"})
    rnd = random.Random(2)
    for _ in range(6):
        me.box(T(rnd.uniform(-0.6, 0.6), -0.1, rnd.uniform(1.1, 1.8), ry=rnd.uniform(-8, 8)),
               (rnd.uniform(0.2, 0.35), 0.01, rnd.uniform(0.25, 0.4)), "cloth_cream")
    return me, None


# ---------------------------------------------------------------- street
def street_lamp():
    me = _m("street_lamp")
    cyl(me, 0, 0, 0.0, 0.5, 0.3, "ashlar", n=8, r1=0.22)
    rod(me, (0, 0, 0.5), (0, 0, 3.2), 0.07, "iron", n=6)
    for zz in (1.0, 2.6):
        cyl(me, 0, 0, zz, zz + 0.06, 0.1, "iron", n=6)
    me.box(T(0, 0, 3.25), (0.36, 0.36, 0.06), "iron")
    me.box(T(0, 0, 3.55), (0.28, 0.28, 0.5), "M_Lamp")
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        me.box(T(dx * 0.16, dy * 0.16, 3.55), (0.04, 0.04, 0.55), "iron")
    me.box(T(0, 0, 3.84), (0.44, 0.44, 0.06), "iron")
    pyramid(me, 0, 0, 3.86, 0.3, 0.3, "iron")
    rod(me, (0, 0, 4.16), (0, 0, 4.35), 0.03, "iron", n=4)
    # a bracket with a hanging flower basket (2026-09-30)
    K.beam(me, (0, 0, 2.75), (0.75, 0, 2.75), 0.04, 0.04, mat="iron")
    K.beam(me, (0, 0, 2.35), (0.45, 0, 2.75), 0.03, 0.03, mat="iron")
    me.box(T(0.7, 0, 2.55), (0.02, 0.02, 0.35), "iron")
    cyl(me, 0.7, 0, 2.05, 2.35, 0.14, "planks", n=8, r1=0.24)
    rnd = random.Random(233)
    for _ in range(6):
        a = rnd.uniform(0, math.tau)
        me.box(T(0.7 + 0.18 * math.cos(a), 0.18 * math.sin(a), 2.38, rz=rnd.uniform(0, 90)), (0.16, 0.16, 0.12), "moss")
        me.box(T(0.7 + 0.2 * math.cos(a), 0.2 * math.sin(a), 2.46), (0.08, 0.08, 0.06), rnd.choice(("cloth_red", "crops", "cloth_cream")))
    for _ in range(3):
        a = rnd.uniform(0, math.tau)
        me.box(T(0.7 + 0.24 * math.cos(a), 0.24 * math.sin(a), 2.0), (0.06, 0.06, 0.45), "moss")
    return me, None


def wall_lantern_p():
    me = _m("wall_lantern")
    me.box(T(0, 0.04, 2.4), (0.2, 0.08, 0.5), "iron")
    wall_lantern(me, 0, 0, 2.5)
    return me, None


def hanging_lantern():
    me = _m("hanging_lantern")
    for k in range(6):
        me.box(T(0, 0, 3.0 - k * 0.12, rz=k * 90), (0.03, 0.08, 0.12), "iron")
    me.box(T(0, 0, 2.2), (0.24, 0.24, 0.34), "M_Lamp")
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        me.box(T(dx * 0.13, dy * 0.13, 2.2), (0.035, 0.035, 0.4), "iron")
    pyramid(me, 0, 0, 2.38, 0.24, 0.22, "iron")
    me.box(T(0, 0, 2.0), (0.28, 0.28, 0.04), "iron")
    return me, None


def hanging_sign_p():
    me = _m("hanging_sign")
    me.box(T(0, 0.05, 3.0), (0.2, 0.1, 0.6), "iron")
    hanging_sign(me, 0, 0, 3.1, mat="cloth_red")
    return me, None


def banner_p():
    # blue with a gold emblem (2026-09-30, the user's direction sheet: the city's
    # colour against the orange dusk; the fountain's banners are the same)
    me = _m("banner")
    banner(me, 0, 0, 5.0, 3.6, mat="cloth_blue")
    me.box(T(0, -0.14, 3.7, ry=45), (0.34, 0.04, 0.34), "crops")
    me.box(T(0, 0.08, 5.0), (1.3, 0.12, 0.12), "ashlar")
    return me, None


def _bunting(name, half):
    """Pennants on a sagging line across a street, between two poles `2*half` m
    apart (2026-09-30, the direction sheet: "this dense"). The span runs along x,
    so the prop is placed facing along the road."""
    me = _m(name)
    for sx in (-1, 1):
        rod(me, (sx * half, 0, 0), (sx * half, 0, 5.3), 0.07, "timber", n=6)
        cyl(me, sx * half, 0, 5.3, 5.4, 0.1, "iron", n=6)
    sag, n = 0.8, int(half * 2 / 0.6)
    pts = [Vector((-half + 2 * half * i / n, 0, 5.1 - sag * (1 - (2 * i / n - 1) ** 2))) for i in range(n + 1)]
    for a, b in zip(pts, pts[1:]):
        rod(me, a, b, 0.015, "timber", n=4)
    cols = ("cloth_red", "cloth_cream", "cloth_blue", "cloth_red", "crops")
    for i in range(1, n):
        me.prism(pts[i] + Vector((0, 0.01, 0)), X, Z, [(-0.2, 0), (0.2, 0), (0, -0.45)], 0.02, cols[i % len(cols)])
    return me, None


def bunting_s():
    return _bunting("bunting_s", 4.2)


def bunting_m():
    return _bunting("bunting_m", 6.3)


def flag():
    me = _m("flag")
    cyl(me, 0, 0, 0, 0.3, 0.3, "ashlar", n=8)
    rod(me, (0, 0, 0.3), (0, 0, 6.0), 0.06, "timber", n=6)
    cyl(me, 0, 0, 6.0, 6.15, 0.09, "iron", n=6)
    for k in range(4):
        x0 = 0.08 + k * 0.45
        me.box(T(x0 + 0.22, 0.12 * math.sin(k * 1.4), 5.4, rz=20 * math.cos(k * 1.4)), (0.47, 0.03, 1.0),
               "cloth_red" if k % 2 == 0 else "cloth_red")
    return me, None


def balcony():
    """A timber balcony for an upper floor: slab on brackets, balusters."""
    me = _m("balcony")
    me.box(T(0, -0.55, 0.0), (2.4, 1.1, 0.12), "planks", axis=(1, 0, 0))
    for x in (-1.0, 1.0):
        K.beam(me, (x, 0, -0.9), (x, -1.0, -0.06), 0.12, 0.12, up=(1, 0, 0))
    for k in range(11):
        x = -1.15 + k * 0.23
        K.beam(me, (x, -1.05, 0.06), (x, -1.05, 0.95), 0.05, 0.05)
    for x in (-1.15, 1.15):
        K.beam(me, (x, -1.05, 0.06), (x, 0, 0.06), 0.06, 0.06)
        K.beam(me, (x, -1.05, 1.0), (x, 0, 1.0), 0.09, 0.09)
    K.beam(me, (-1.2, -1.05, 1.0), (1.2, -1.05, 1.0), 0.09, 0.09)
    me.box(T(0.6, -1.12, 0.6), (0.8, 0.26, 0.2), "planks")
    me.box(T(0.6, -1.12, 0.72), (0.74, 0.2, 0.08), "moss")
    return me, None


def clothesline():
    me = _m("clothesline")
    for x in (-2.0, 2.0):
        K.beam(me, (x, 0, -0.2), (x, 0, 2.4), 0.12, 0.12)
    K.beam(me, (-2.0, 0, 2.3), (2.0, 0, 2.3), 0.025, 0.025, mat="thatch")
    for i, (x, w, h, mat) in enumerate(((-1.4, 0.6, 0.8, "cloth_cream"), (-0.6, 0.7, 0.6, "cloth_blue"),
                                        (0.2, 0.5, 0.9, "cloth_cream"), (0.9, 0.8, 0.5, "cloth_red"))):
        me.box(T(x, 0, 2.3 - h / 2, rz=(i % 2) * 4), (w, 0.02, h), mat)
    return me, None


def ladder():
    me = _m("ladder")
    lean = math.radians(15)
    for x in (-0.25, 0.25):
        K.beam(me, (x, -0.8, 0), (x, 0, 3.2), 0.07, 0.07)
    for k in range(9):
        t = (k + 0.7) / 10
        K.beam(me, (-0.25, -0.8 + 0.8 * t, 3.2 * t), (0.25, -0.8 + 0.8 * t, 3.2 * t), 0.04, 0.04)
    return me, None


def railing():
    me = _m("railing")
    for k in range(7):
        K.beam(me, (-1.5 + k * 0.5, 0, -0.1), (-1.5 + k * 0.5, 0, 1.0), 0.1, 0.1)
    for zz in (0.45, 0.98):
        K.beam(me, (-1.55, 0, zz), (1.55, 0, zz), 0.1, 0.08)
    return me, None


def post_chain():
    me = _m("post_chain")
    for x in (-1.5, 1.5):
        cyl(me, x, 0, 0, 0.8, 0.14, "ashlar", n=8)
        pyramid(me, x, 0, 0.8, 0.16, 0.15, "ashlar", n=8)
    for k in range(13):
        x = -1.35 + k * 0.225
        z = 0.65 - 0.25 * (1 - (x / 1.4) ** 2)
        me.box(T(x, 0, z), (0.14, 0.03 if k % 2 else 0.1, 0.1 if k % 2 else 0.03), "iron")
    return me, None


# ---------------------------------------------------------------- craft
def anvil():
    me = _m("anvil")
    cyl(me, 0, 0, 0, 0.55, 0.32, "bark", n=8, top="timber")
    me.box(T(0, 0, 0.68), (0.25, 0.2, 0.26), "iron")
    me.box(T(0, 0, 0.86), (0.7, 0.24, 0.14), "iron")
    me.box(T(0.42, 0, 0.87), (0.22, 0.12, 0.08), "iron")
    K.beam(me, (-0.1, -0.05, 0.95), (0.25, -0.25, 0.97), 0.04, 0.04, mat="timber")
    me.box(T(0.28, -0.27, 0.97), (0.1, 0.08, 0.08), "iron")
    for dy in (-0.03, 0.03):                             # tongs and a quench bucket (2026-09-30)
        K.beam(me, (-0.3, dy, 0.94), (0.05, dy * 3, 0.95), 0.025, 0.025, mat="iron")
    cyl(me, 0.6, 0.35, 0.0, 0.45, 0.2, "planks", n=8, r1=0.22)
    cyl(me, 0.6, 0.35, 0.38, 0.42, 0.19, "water", n=8)
    cyl(me, 0.6, 0.35, 0.3, 0.34, 0.225, "iron", n=8)
    return me, None


def grindstone():
    me = _m("grindstone")
    for x in (-0.3, 0.3):
        K.beam(me, (x, -0.35, 0), (x, 0, 0.8), 0.08, 0.08)
        K.beam(me, (x, 0.35, 0), (x, 0, 0.8), 0.08, 0.08)
    K.beam(me, (-0.3, -0.25, 0.35), (-0.3, 0.25, 0.35), 0.06, 0.06)
    K.beam(me, (0.3, -0.25, 0.35), (0.3, 0.25, 0.35), 0.06, 0.06)
    rod(me, (-0.1, 0, 0.8), (0.1, 0, 0.8), 0.42, "fieldstone", n=14)
    rod(me, (-0.45, 0, 0.8), (0.45, 0, 0.8), 0.03, "iron", n=4)
    K.beam(me, (0.45, 0, 0.8), (0.45, 0, 0.55), 0.04, 0.04, mat="iron")
    K.beam(me, (0.45, 0, 0.55), (0.62, 0, 0.55), 0.05, 0.05, mat="timber")
    return me, None


def trough():
    me = _m("trough")
    me.box(T(0, 0, 0.3), (1.8, 0.7, 0.6), "ashlar")
    me.box(T(0, 0, 0.57), (1.6, 0.5, 0.04), "water")
    rnd = random.Random(381)                             # moss and a bucket (2026-09-30)
    for _ in range(5):
        me.box(T(rnd.choice((-0.82, 0.82)) * rnd.uniform(0.3, 1.0), rnd.choice((-0.3, 0.3)), 0.62, rz=rnd.uniform(0, 90)),
               (0.25, 0.15, 0.06), "moss")
    cyl(me, 1.15, 0.2, 0.0, 0.4, 0.17, "planks", n=8, r1=0.19)
    cyl(me, 1.15, 0.2, 0.28, 0.31, 0.2, "iron", n=8)
    return me, None


def wagon():
    """A covered cargo wagon: four wheels, plank bed, canvas on hoops."""
    me = _m("wagon")
    me.box(T(0, 0, 0.85), (3.0, 1.5, 0.12), "planks", axis=(1, 0, 0))
    for y in (-0.72, 0.72):
        me.box(T(0, y, 1.1), (3.0, 0.06, 0.4), "planks", axis=(1, 0, 0))
    for x in (-1.5, 1.5):
        me.box(T(x, 0, 1.1), (0.06, 1.5, 0.4), "planks")
    for x in (-1.0, 1.0):
        for y in (-0.85, 0.85):
            rod(me, (x, y - 0.05, 0.55), (x, y + 0.05, 0.55), 0.55, "planks", n=12)
            rod(me, (x, y - 0.07, 0.55), (x, y + 0.07, 0.55), 0.12, "iron", n=6)
    poly = [(0.85 * math.cos(math.pi * k / 6), 0.85 * math.sin(math.pi * k / 6) * 1.1) for k in range(7)]
    me.prism(Vector((1.4, 0, 1.3)), Y, Z, poly, 2.6, "cloth_cream")
    K.beam(me, (1.5, 0, 0.8), (2.9, 0, 0.6), 0.08, 0.08)
    sack(me, -1.75, 0.0, 0.9, 0.9)
    crate(me, -1.2, 0.35, 0.91, 0.5, rz=6)                # cargo and a lantern (2026-09-30)
    barrel(me, -1.25, -0.35, 0.91, s=0.7)
    K.beam(me, (1.45, 0, 2.2), (1.85, 0, 2.2), 0.04, 0.04, mat="iron")
    me.box(T(1.85, 0, 1.98), (0.16, 0.16, 0.26), "M_Lamp")
    me.box(T(1.85, 0, 2.13), (0.2, 0.2, 0.04), "iron")
    return me, K.Mesh("SHADOW_wagon")


def hay_stack():
    me = _m("hay_stack")
    cyl(me, 0, 0, 0, 1.2, 1.3, "thatch", n=10, r1=1.4)
    cyl(me, 0, 0, 1.2, 2.2, 1.4, "thatch", n=10, r1=0.9)
    pyramid(me, 0, 0, 2.2, 0.95, 0.9, "thatch", n=10)
    rod(me, (0, 0, 2.8), (0, 0, 3.4), 0.05, "timber", n=4)
    K.beam(me, (1.2, -0.9, 0.0), (1.1, -0.6, 1.9), 0.05, 0.05, mat="timber")   # pitchfork, loose hay (2026-09-30)
    for dx in (-0.08, 0.0, 0.08):
        K.beam(me, (1.1 + dx, -0.6, 1.9), (1.1 + dx, -0.55, 2.25), 0.025, 0.025, mat="iron")
    rnd = random.Random(407)
    for _ in range(8):
        a = rnd.uniform(0, math.tau)
        me.box(T(1.6 * math.cos(a), 1.6 * math.sin(a), 0.08, rz=rnd.uniform(0, 90)), (0.5, 0.3, 0.14), "thatch")
    return me, None


# ---------------------------------------------------------------- harbour
def crane():
    """A harbour post crane: stone base, post, braced jib, rope and hook."""
    me = _m("crane")
    me.box(T(0, 0, 0.4), (1.6, 1.6, 0.8), "ashlar")
    K.beam(me, (0, 0, 0.8), (0, 0, 6.5), 0.4, 0.4)
    K.beam(me, (0, 0.3, 6.2), (0, -4.2, 5.6), 0.3, 0.3)
    K.beam(me, (0, 0, 3.8), (0, -2.4, 5.9), 0.2, 0.2)
    K.beam(me, (0, 0.2, 6.4), (0, 1.5, 1.2), 0.08, 0.08, mat="thatch")
    rod(me, (-0.15, -4.0, 5.45), (0.15, -4.0, 5.45), 0.2, "timber", n=8)
    K.beam(me, (0, -4.0, 5.3), (0, -4.0, 2.6), 0.03, 0.03, mat="thatch")
    me.box(T(0, -4.0, 2.5), (0.1, 0.2, 0.25), "iron")
    for s in (-1, 1):
        K.beam(me, (s * 0.8, 0, 0.8), (0, 0, 2.6), 0.15, 0.15, up=(0, 1, 0))
    crate(me, 0.6, -4.0, 1.5, 0.7)
    barrel(me, 1.2, 0.6, 0.0)                            # at its foot (2026-09-30)
    barrel(me, 1.3, -0.1, 0.0, s=0.9)
    for k in range(12):
        a, b = k * math.tau / 12, (k + 1) * math.tau / 12
        K.beam(me, (-1.3 + 0.4 * math.cos(a), 0.4 * math.sin(a), 0.06), (-1.3 + 0.4 * math.cos(b), 0.4 * math.sin(b), 0.06),
               0.1, 0.1, mat="thatch")
    return me, K.Mesh("SHADOW_crane")


def bollard():
    me = _m("bollard")
    cyl(me, 0, 0, 0, 0.6, 0.22, "iron", n=8, r1=0.18)
    cyl(me, 0, 0, 0.6, 0.72, 0.28, "iron", n=8)
    for k in range(10):
        a = k * math.tau / 10
        me.box(T(0.3 * math.cos(a), 0.3 * math.sin(a), 0.4, rz=math.degrees(a)), (0.08, 0.12, 0.08), "thatch")
    return me, None


def fish_barrels():
    me = _m("fish_barrels")
    for x, y, s in ((0, 0, 1.0), (0.7, 0.1, 0.9), (0.3, 0.65, 0.95)):
        barrel(me, x, y, s=s)
        rnd = random.Random(int(x * 10))
        for _ in range(5):
            me.box(T(x + rnd.uniform(-0.15, 0.15), y + rnd.uniform(-0.15, 0.15), 0.9 * s + 0.04, rz=rnd.uniform(0, 180)),
                   (0.32, 0.08, 0.06), "ice")
    cyl(me, -0.7, 0.3, 0.0, 0.35, 0.28, "thatch", n=8, r1=0.34)        # a fish basket (2026-09-30)
    for k in range(4):
        me.box(T(-0.7 + (k - 1.5) * 0.12, 0.3, 0.38, rz=k * 40), (0.3, 0.07, 0.05), "ice")
    return me, None


def net_stack():
    me = _m("net_stack")
    rnd = random.Random(4)
    for k in range(5):
        me.box(T(rnd.uniform(-0.3, 0.3), rnd.uniform(-0.2, 0.2), 0.12 + k * 0.14, rz=rnd.uniform(0, 90)),
               (1.4 - k * 0.15, 0.9 - k * 0.1, 0.18), "bark")
    for _ in range(6):
        me.box(T(rnd.uniform(-0.6, 0.6), rnd.uniform(-0.4, 0.4), rnd.uniform(0.2, 0.7)), (0.14, 0.14, 0.14), "cloth_red")
    return me, None


def rope_coil():
    me = _m("rope_coil")
    for layer in range(3):
        r = 0.45 - layer * 0.05
        for k in range(12):
            a, b = k * math.tau / 12, (k + 1) * math.tau / 12
            K.beam(me, (r * math.cos(a), r * math.sin(a), 0.06 + layer * 0.1),
                   (r * math.cos(b), r * math.sin(b), 0.06 + layer * 0.1), 0.1, 0.1, mat="thatch")
    return me, None


# ---------------------------------------------------------------- noble / citadel
def statue_knight():
    """A knight in stone on a plinth: helm, shield, sword point-down."""
    me = _m("statue_knight")
    me.box(T(0, 0, 0.6), (1.4, 1.4, 1.2), "ashlar", faces={"+z": "flagstone"})
    me.box(T(0, 0, 1.28), (1.2, 1.2, 0.16), "ashlar")
    for x in (-0.18, 0.18):
        me.box(T(x, 0, 1.85), (0.26, 0.3, 1.0), "ashlar")
    me.box(T(0, 0, 2.75), (0.7, 0.42, 0.9), "ashlar")
    me.box(T(0, 0, 3.05), (0.9, 0.46, 0.2), "ashlar")
    cyl(me, 0, 0, 3.2, 3.6, 0.2, "ashlar", n=8)
    pyramid(me, 0, 0, 3.6, 0.2, 0.25, "ashlar", n=8)
    me.box(T(0, -0.2, 3.42), (0.26, 0.04, 0.05), "glass")
    disc(me, (-0.5, -0.1, 2.6), -90, 0.35, "ashlar", n=8, depth=0.12)
    K.beam(me, (0.45, -0.25, 1.4), (0.45, -0.25, 2.9), 0.1, 0.04, mat="ashlar")
    me.box(T(0.45, -0.25, 2.55), (0.4, 0.08, 0.08), "ashlar")
    for x in (-0.35, 0.35):
        me.box(T(x, -0.1, 2.5), (0.18, 0.2, 0.7), "ashlar")
    rnd = random.Random(478)                             # weathered, planted (2026-09-30)
    DT.ivy(me, rnd, Vector((0.35, -0.7, 0.0)), (1, 0, 0), 1.1, spread=0.4)
    for _ in range(6):
        me.box(T(rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 1.37, rz=rnd.uniform(0, 90)), (0.25, 0.2, 0.05), "moss")
    DT.flower_strip(me, rnd, (-0.9, -0.95, 0), (0.9, -0.95, 0), w=0.4)
    return me, K.Mesh("SHADOW_statue_knight")


def hedge():
    """3 m of clipped boxwood hedge."""
    me = _m("hedge")
    rnd = random.Random(6)
    me.box(T(0, 0, 0.5), (3.0, 0.8, 1.0), "moss")
    for k in range(6):
        me.box(T(-1.2 + k * 0.5, rnd.uniform(-0.05, 0.05), 1.0 + rnd.uniform(-0.03, 0.05)),
               (0.62, 0.84, 0.2 + rnd.uniform(0, 0.08)), "moss")
    return me, None


def iron_fence():
    me = _m("iron_fence")
    me.box(T(0, 0, 0.25), (3.0, 0.4, 0.5), "ashlar", faces={"+z": "flagstone"})
    for k in range(13):
        x = -1.44 + k * 0.24
        rod(me, (x, 0, 0.5), (x, 0, 1.6), 0.02, "iron", n=4)
        pyramid(me, x, 0, 1.6, 0.05, 0.14, "iron")
    for zz in (0.7, 1.45):
        K.beam(me, (-1.5, 0, zz), (1.5, 0, zz), 0.04, 0.04, mat="iron")
    return me, None


def gate_small():
    me = _m("gate_small")
    for x in (-1.3, 1.3):
        me.box(T(x, 0, 1.1), (0.5, 0.5, 2.2), "ashlar")
        me.box(T(x, 0, 2.25), (0.62, 0.62, 0.1), "flagstone")
        cyl(me, x, 0, 2.3, 2.6, 0.2, "ashlar", n=8)
    for s in (-1, 1):
        x0 = s * 0.03
        for k in range(6):
            x = x0 + s * (0.07 + k * 0.18)
            rod(me, (x, 0, 0.05), (x, 0, 1.9 - 0.15 * abs(k - 2.5) / 2.5), 0.02, "iron", n=4)
        for zz in (0.2, 1.1, 1.7):
            K.beam(me, (x0, 0, zz), (x0 + s * 1.05, 0, zz), 0.04, 0.04, mat="iron")
    return me, None


def weapon_rack():
    me = _m("weapon_rack")
    for x in (-0.9, 0.9):
        K.beam(me, (x, 0, 0), (x, 0, 1.5), 0.1, 0.1)
    for zz in (0.3, 1.2):
        K.beam(me, (-0.95, 0, zz), (0.95, 0, zz), 0.08, 0.08)
    for k in range(5):
        x = -0.7 + k * 0.35
        K.beam(me, (x, -0.05, 0.1), (x, 0.05, 2.1), 0.04, 0.04)
        pyramid(me, x, 0.05, 2.1, 0.05, 0.22, "iron")
    for x, mat in ((-0.5, "cloth_red"), (0.45, "cloth_blue")):
        disc(me, (x, -0.2, 0.7), -90, 0.3, mat, n=10, depth=0.05)
        disc(me, (x, -0.24, 0.7), -90, 0.08, "iron", n=6, depth=0.04)
    return me, None


def chest():
    me = _m("chest")
    me.box(T(0, 0, 0.25), (0.9, 0.55, 0.5), "planks")
    me.box(T(0, 0, 0.56), (0.92, 0.57, 0.14), "planks")
    for x in (-0.3, 0.3):
        me.box(T(x, 0, 0.32), (0.06, 0.58, 0.66), "iron")
    me.box(T(0, -0.29, 0.44), (0.1, 0.03, 0.12), "iron")
    for x in (-0.44, 0.44):                              # corner irons, handles (2026-09-30)
        for y in (-0.27, 0.27):
            me.box(T(x, y, 0.32), (0.05, 0.05, 0.64), "iron")
        me.box(T(x + (0.03 if x > 0 else -0.03), 0, 0.42), (0.03, 0.22, 0.05), "thatch")
    return me, None


def training_target():
    me = _m("training_target")
    K.beam(me, (0, 0, -0.2), (0, 0, 1.9), 0.12, 0.12)
    K.beam(me, (-0.7, 0, 1.5), (0.7, 0, 1.5), 0.08, 0.08)
    me.box(T(0, 0, 1.25), (0.5, 0.35, 0.8), "thatch")
    me.box(T(0, 0, 1.85), (0.3, 0.3, 0.3), "cloth_cream")
    for x in (-0.6, 0.6):
        me.box(T(x, 0, 1.5), (0.25, 0.22, 0.22), "thatch")
    x = 1.6
    for s in (-1, 1):
        K.beam(me, (x + s * 0.3, 0.3, 0), (x, 0, 1.4), 0.07, 0.07)
    disc(me, (x, -0.05, 1.2), -90, 0.6, "thatch", n=12, depth=0.2)
    disc(me, (x, -0.17, 1.2), -90, 0.38, "cloth_red", n=12, depth=0.04)
    disc(me, (x, -0.2, 1.2), -90, 0.18, "cloth_cream", n=10, depth=0.04)
    return me, None


# ---------------------------------------------------------------- farm
def crop_field():
    """An 8 x 8 m patch of field: soil and planted ridges."""
    me = _m("crop_field")
    me.box(T(0, 0, -0.1), (8.0, 8.0, 0.2), "dirt")
    for k in range(16):
        x = -3.75 + k * 0.5
        me.box(T(x, 0, 0.12), (0.32, 7.8, 0.25), "crops", faces={"+z": "crops"})
    return me, None


def scarecrow():
    me = _m("scarecrow")
    K.beam(me, (0, 0, -0.2), (0, 0, 2.2), 0.1, 0.1)
    K.beam(me, (-0.8, 0, 1.6), (0.8, 0, 1.6), 0.08, 0.08)
    me.box(T(0, 0, 1.3), (0.6, 0.3, 0.8), "cloth_blue")
    for x in (-0.55, 0.55):
        me.box(T(x, 0, 1.55), (0.45, 0.2, 0.2), "cloth_blue")
        me.box(T(x * 1.5, 0, 1.55), (0.15, 0.1, 0.25), "thatch")
    me.box(T(0, 0, 0.8), (0.3, 0.1, 0.3), "thatch")
    me.box(T(0, 0, 1.95), (0.34, 0.3, 0.34), "cloth_cream")
    cyl(me, 0, 0, 2.12, 2.16, 0.4, "thatch", n=10)
    pyramid(me, 0, 0, 2.16, 0.2, 0.3, "thatch", n=8)
    return me, None


# ---------------------------------------------------------------- ships
def hull(me, L, B, keel, sheer, rise=1.2, n=12):
    """A round medieval hull: sections along x, full amidships, fine at the
    ends, sheer rising fore and aft. Returns the deck height function."""
    half = L / 2

    def hw(x):
        t = abs(x) / half
        return B / 2 * max(0.02, 1 - t ** (2.4 if x > 0 else 3.0))

    def top(x):
        return sheer + rise * (abs(x) / half) ** 2

    def bot(x):
        return keel * (1 - (abs(x) / half) ** 4)

    xs = [-half + L * k / n for k in range(n + 1)]
    ring = []
    for x in xs:
        pts = []
        for j in range(6):
            ph = math.pi / 2 * j / 5
            y = hw(x) * math.sin(ph) ** 0.6
            z = bot(x) + (top(x) - bot(x)) * (1 - math.cos(ph))
            pts.append((y, z))
        ring.append(pts)
    for i in range(n):
        x0, x1 = xs[i], xs[i + 1]
        c = Vector(((x0 + x1) / 2, 0, (bot((x0 + x1) / 2) + top((x0 + x1) / 2)) / 2))
        for j in range(5):
            for s in (-1, 1):
                a0, a1 = ring[i][j], ring[i][j + 1]
                b0, b1 = ring[i + 1][j], ring[i + 1][j + 1]
                me.face([Vector((x0, s * a0[0], a0[1])), Vector((x1, s * b0[0], b0[1])),
                         Vector((x1, s * b1[0], b1[1])), Vector((x0, s * a1[0], a1[1]))],
                        "planks" if j < 4 else "timber", c, axis=(1, 0, 0))
        d0, d1 = top(x0) - 0.35, top(x1) - 0.35
        w0, w1 = hw(x0) * 0.96, hw(x1) * 0.96
        me.face([Vector((x0, -w0, d0)), Vector((x1, -w1, d1)), Vector((x1, w1, d1)), Vector((x0, w0, d0))], "planks",
                Vector(((x0 + x1) / 2, 0, d0 - 1)), axis=(1, 0, 0))
        me.face([Vector((x0, -w0 * 0.3, bot(x0) + 0.05)), Vector((x1, -w1 * 0.3, bot(x1) + 0.05)),
                 Vector((x1, w1 * 0.3, bot(x1) + 0.05)), Vector((x0, w0 * 0.3, bot(x0) + 0.05))], "planks",
                Vector(((x0 + x1) / 2, 0, 5)))
    for s in (-1, 1):
        for i in range(n):
            x0, x1 = xs[i], xs[i + 1]
            K.beam(me, (x0, s * hw(x0), top(x0) + 0.05), (x1, s * hw(x1), top(x1) + 0.05), 0.14, 0.12)
    return top, hw


def sail(me, x, zc, w, h, bow=0.35, mat="cloth_cream"):
    """A square sail on a yard, bellied forward (+x) in three panels."""
    for k, (dz, dx) in enumerate(((h / 3, bow * 0.6), (0, bow), (-h / 3, bow * 0.6))):
        me.box(T(x + dx, 0, zc + dz), (0.05, w * (1 - 0.06 * abs(k - 1)), h / 3 + 0.02), mat)
    rod(me, (x, -w / 2 - 0.4, zc + h / 2 + 0.1), (x, w / 2 + 0.4, zc + h / 2 + 0.1), 0.09, "timber", n=6)


def ship_merchant():
    """A two-masted merchant carrack: raised fore and after castles, square
    sails, bowsprit, shrouds, a pennant."""
    me = _m("ship_merchant")
    L, B = 20.0, 6.0
    top, hw = hull(me, L, B, -2.0, 1.6, rise=1.6)
    me.box(T(-7.2, 0, top(-7.2) + 0.9), (4.2, 4.2, 1.9), "planks", axis=(1, 0, 0))
    me.box(T(-7.4, 0, top(-7.2) + 1.9), (4.6, 4.6, 0.16), "timber")
    for s in (-1, 1):
        for k in range(8):
            K.beam(me, (-9.2 + k * 0.55, s * 2.2, top(-7.2) + 1.95), (-9.2 + k * 0.55, s * 2.2, top(-7.2) + 2.6), 0.06, 0.06)
        K.beam(me, (-9.3, s * 2.2, top(-7.2) + 2.62), (-5.2, s * 2.2, top(-7.2) + 2.62), 0.1, 0.1)
    for k in range(3):
        me.box(T(-9.36, -1.2 + k * 1.2, top(-7.2) + 0.9), (0.04, 0.6, 0.5), "M_Window_Dim")
    me.box(T(7.0, 0, top(7.0) + 0.6), (3.2, 3.2, 1.2), "planks", axis=(1, 0, 0))
    me.box(T(7.0, 0, top(7.0) + 1.25), (3.5, 3.4, 0.12), "timber")
    rod(me, (9.5, 0, top(9.5)), (13.5, 0, top(9.5) + 2.6), 0.14, "timber", n=6)
    me.box(T(-10.1, 0, -0.3), (0.3, 0.12, 3.4), "timber")
    for x, h, w in ((1.5, 15.0, 7.5), (6.2, 11.0, 5.5)):
        z0 = top(x) - 0.4
        rod(me, (x, 0, z0), (x, 0, z0 + h), 0.22, "timber", n=8, r1=0.14)
        cyl(me, x, 0, z0 + h * 0.72, z0 + h * 0.72 + 0.5, 0.7, "planks", n=8)
        sail(me, x, z0 + h * 0.45, w, h * 0.42)
        sail(me, x, z0 + h * 0.83, w * 0.7, h * 0.18)
        for s in (-1, 1):
            for k in range(3):
                K.beam(me, (x - 0.6 + k * 0.6, s * hw(x) * 0.98, top(x)), (x, s * 0.2, z0 + h * 0.7), 0.03, 0.03,
                       mat="thatch")
        K.beam(me, (x, 0, z0 + h), (x + 4.5 if x < 5 else 12.8, 0, top(x) + (0.5 if x < 5 else 2.5)), 0.03, 0.03,
               mat="thatch")
    me.box(T(1.5 + 0.9, 0, top(1.5) + 15.2), (1.8, 0.03, 0.4), "cloth_red")
    _ship_dress(me, top, hw, L, random.Random(663), cargo=((-2.5, 0.8), (-1.8, -0.9), (3.0, 0.6), (3.6, -0.7)),
                stern=-9.8, flag="cloth_blue")
    sh = K.Mesh("SHADOW_ship_merchant")
    K.proxy_box(sh, -10, 10, -3, 3, -1.5, 3.5)
    K.proxy_box(sh, -1.0, 7.0, -0.2, 0.2, 3, 16)
    return me, sh


def ship_fishing():
    """A small fishing cog: one mast, a patched sail, nets and a cabin."""
    me = _m("ship_fishing")
    L, B = 9.0, 3.0
    top, hw = hull(me, L, B, -1.0, 0.8, rise=0.6, n=10)
    me.box(T(-2.6, 0, top(-2.6) + 0.55), (1.8, 1.8, 1.2), "planks", axis=(1, 0, 0))
    K.roof(me, -3.5, -1.7, -0.9, 0.9, top(-2.6) + 1.15, 30, "shingle", over_eave=0.15, over_gable=0.1, thick=0.08)
    z0 = top(0.8) - 0.3
    rod(me, (0.8, 0, z0), (0.8, 0, z0 + 7.0), 0.12, "timber", n=6, r1=0.08)
    sail(me, 0.8, z0 + 3.6, 3.4, 3.8, mat="cloth_cream")
    me.box(T(1.1, 0.2, z0 + 3.2), (0.06, 0.8, 0.8), "cloth_red")
    for s in (-1, 1):
        K.beam(me, (0.8, s * hw(0.8), top(0.8)), (0.8, s * 0.1, z0 + 6.5), 0.03, 0.03, mat="thatch")
    for k in range(3):
        me.box(T(2.6 + k * 0.3, 0.2 * k - 0.2, top(2.6) - 0.2 + k * 0.08, rz=k * 30), (0.9, 0.7, 0.2), "bark")
    me.box(T(-4.6, 0, -0.2), (0.2, 0.08, 1.8), "timber")
    _ship_dress(me, top, hw, L, random.Random(700), cargo=((-0.6, 0.4),), stern=-4.2, flag="cloth_red")
    for k in range(3):                                   # nets over the side, floats
        me.box(T(1.8 + k * 0.7, -hw(1.8) - 0.03, top(1.8) - 0.4), (0.6, 0.04, 0.7), "bark")
        me.box(T(1.8 + k * 0.7, -hw(1.8) - 0.06, top(1.8) - 0.8), (0.12, 0.08, 0.12), "cloth_red")
    sh = K.Mesh("SHADOW_ship_fishing")
    K.proxy_box(sh, -4.5, 4.5, -1.5, 1.5, -0.6, 1.8)
    return me, sh


# ---------------------------------------------------------------- reused kits
SNOW_TO_CITY = {"wood": "planks", "bark": "bark", "logend": "timber", "iron": "iron", "stone": "fieldstone",
                "glass": "M_Lamp", "slate": "slate", "sandstone": "ashlar", "clay": "clay_tile",
                "fire": "M_Lamp", "adobe": "plaster"}


def adopt(src, name):
    """Copy a snowkit/desertkit mesh into a kit Mesh: snow and sand faces
    dropped, each material renamed to the world's texgen surface, UVs
    re-projected at 52 texels/m by the kit."""
    me = K.Mesh(name)
    for pts, mat, uv, uv2 in src.faces:
        if mat in ("snow", "sand"):
            continue
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            continue
        fc = sum(pts, Vector()) / len(pts)
        me.face(pts, SNOW_TO_CITY.get(mat, mat), fc - n.normalized() * 0.01)
    return me, None


def reused():
    import snowkit as sk
    import desertkit as dk
    rnd = random.Random(1234)
    out = []
    for name, fn in (("fence", sk.fence), ("signpost", sk.signpost), ("bench", sk.bench), ("cart", sk.cart),
                     ("broken_cart", lambda r: sk.cart(r, broken=True)), ("barrels", sk.barrels),
                     ("log_pile", sk.log_pile), ("stump", sk.stump), ("stone_wall", sk.stone_wall),
                     ("lantern_post", sk.lantern), ("ruin_arch", sk.ruin_arch), ("ruin_pillar", sk.ruin_pillar),
                     ("ruin_wall", sk.ruin_wall), ("pots", dk.pots), ("urn", dk.urn), ("brazier", dk.brazier)):
        out.append((name, lambda fn=fn, name=name: _dress(*adopt(fn(rnd), name), name)))
    return out


# How each adopted piece is weathered (2026-09-30, the detail rollout)
DRESS = {"fence": dict(moss=3, blooms=0.4), "signpost": dict(moss=2), "bench": dict(moss=1),
         "cart": dict(moss=1, cargo=True), "broken_cart": dict(moss=5, blooms=0.3), "barrels": dict(moss=1),
         "log_pile": dict(moss=4), "stump": dict(moss=4, blooms=0.2), "stone_wall": dict(moss=6, blooms=0.3, ivy=1),
         "lantern_post": dict(moss=1), "ruin_arch": dict(moss=8, blooms=0.2, ivy=2), "ruin_pillar": dict(moss=5, ivy=1),
         "ruin_wall": dict(moss=8, blooms=0.2, ivy=2), "pots": dict(moss=3, blooms=0.9), "urn": dict(moss=2, blooms=0.9)}


def _dress(me, sh, name):
    """Weather an adopted mesh from its own faces: moss (and blooms) on faces
    that look up, ivy climbing the largest faces that look at the street (-y),
    a sack and a crate on the largest flat face of a cart."""
    kw = DRESS.get(name)
    if not kw:
        return me, sh
    rnd = random.Random(sum(map(ord, name)))
    ups, fronts = [], []
    for f in me.bm.faces:
        v = [x.co.copy() for x in f.verts]
        n = (v[1] - v[0]).cross(v[2] - v[0])
        if n.length < 1e-9 or me.mats[f.material_index] in ("M_Lamp", "glass"):
            continue
        n.normalize()
        c = sum(v, Vector()) / len(v)
        a = f.calc_area()
        if n.z > 0.75 and a > 0.01:
            ups.append((c, a))
        elif n.y < -0.8 and a > 0.3:
            fronts.append((c, min(x.z for x in v), a))
    if not ups:
        return me, sh
    for _ in range(kw.get("moss", 0)):
        c, a = rnd.choices(ups, weights=[w for _, w in ups])[0]
        s = min(0.35, math.sqrt(a) * 0.6)
        me.box(T(c.x + rnd.uniform(-s / 3, s / 3), c.y + rnd.uniform(-s / 3, s / 3), c.z + 0.03, rz=rnd.uniform(0, 90)),
               (s, s * 0.8, 0.07), "moss")
        if rnd.random() < kw.get("blooms", 0.0):
            me.box(T(c.x, c.y, c.z + 0.1), (0.08, 0.08, 0.06), rnd.choice(("cloth_red", "crops", "cloth_cream", "cloth_blue")))
    fronts.sort(key=lambda t: -t[2])
    for k in range(min(kw.get("ivy", 0), len(fronts))):
        c, z0, a = fronts[k]
        DT.ivy(me, rnd, Vector((c.x, c.y, z0)), (1, 0, 0), max(0.8, (c.z - z0) * 1.6), spread=0.6)
    if kw.get("cargo"):
        c, a = max(ups, key=lambda t: t[1])
        sack(me, c.x - 0.25, c.y, c.z, 0.8, rz=15)
        crate(me, c.x + 0.3, c.y + 0.05, c.z, 0.45, rz=-8)
    return me, sh


def _ship_dress(me, top, hw, L, rnd, cargo=(), stern=None, flag="cloth_red"):
    """A ship's secondary detail: two wales along each side, deck cargo, a
    stern lantern and an ensign (2026-09-30, the detail rollout)."""
    n = int(L - 2)
    for s in (-1, 1):
        for dz in (0.35, 0.8):
            for k in range(n):
                x0, x1 = -L / 2 + 1 + k, -L / 2 + 2 + k
                K.beam(me, (x0, s * hw(x0) * 1.01, top(x0) - dz), (x1, s * hw(x1) * 1.01, top(x1) - dz), 0.1, 0.08,
                       mat="timber")
    for x, y in cargo:
        z = top(x) - 0.15
        if rnd.random() < 0.5:
            crate(me, x, y, z, 0.6, rz=rnd.uniform(-10, 10))
        else:
            barrel(me, x, y, z, s=0.8)
        sack(me, x + 0.5, y * 0.6, z, 0.8, rz=rnd.uniform(0, 60))
    if stern is not None:
        zt = top(stern)
        rod(me, (stern, 0, zt), (stern - 0.4, 0, zt + 2.6), 0.05, "timber", n=5)
        me.box(T(stern - 0.4 - 0.5, 0, zt + 2.3), (1.0, 0.03, 0.6), flag)
        K.beam(me, (stern + 0.2, 0.9, zt + 1.4), (stern - 0.3, 0.9, zt + 1.4), 0.04, 0.04, mat="iron")
        me.box(T(stern - 0.3, 0.9, zt + 1.18), (0.2, 0.2, 0.3), "M_Lamp")


PROPS = [market_stall_a, market_stall_b, awning, sacks, goods_crates, fountain, planter, notice_board,
         street_lamp, wall_lantern_p, hanging_lantern, hanging_sign_p, banner_p, flag, balcony, clothesline, ladder,
         railing, post_chain, anvil, grindstone, trough, wagon, hay_stack, crane, bollard, fish_barrels, net_stack,
         rope_coil, statue_knight, hedge, iron_fence, gate_small, weapon_rack, chest, training_target, crop_field,
         scarecrow]
def rowboat():
    """A 4.2 m rowboat moored at a quay: floorboards, three thwarts, a pair
    of oars shipped along the gunwales. Placed like the ships (length +X)."""
    me = _m("rowboat")
    top, hw = hull(me, 4.2, 1.5, -0.35, 0.45, rise=0.25, n=8)
    for x in (-1.0, 0.2, 1.1):
        me.box(T(x, 0, top(x) - 0.16), (0.22, hw(x) * 1.9, 0.06), "timber")
    for s in (-1, 1):
        rod(me, (-1.5, s * 0.42, top(0) - 0.02), (1.2, s * 0.3, top(0) + 0.04), 0.035, "timber", n=5)
        me.box(T(1.3, s * 0.3, top(0) + 0.04), (0.42, 0.03, 0.14), "timber")
    crate(me, -0.5, 0.0, top(-0.5) - 0.13, 0.35, rz=12)  # a crate and a net (2026-09-30)
    me.box(T(0.6, 0.1, top(0.6) - 0.1), (0.5, 0.45, 0.1), "bark")
    return me, None


SHIPS = [ship_merchant, ship_fishing, rowboat]

# ---------------------------------------------------------------- garden / street (city rework)
def well():
    """A stone well: a ring of dressed blocks, water inside, two posts, a
    little shingle roof, the windlass and a bucket."""
    me = _m("well")
    for k in range(12):
        a = k * 30
        me.box(T(0.75 * math.cos(math.radians(a)), 0.75 * math.sin(math.radians(a)), 0.4, rz=a), (0.32, 0.42, 0.8),
               "fieldstone", faces={"+z": "ashlar"})
    cyl(me, 0, 0, 0.0, 0.45, 0.6, "water", n=12)
    for s in (-1, 1):
        K.beam(me, (s * 0.85, 0, 0.6), (s * 0.85, 0, 2.3), 0.14, 0.14)
    rod(me, (-0.8, 0, 1.6), (0.8, 0, 1.6), 0.08, "timber", n=6)
    K.beam(me, (0.8, 0, 1.6), (1.05, 0, 1.35), 0.05, 0.05, mat="iron")
    K.beam(me, (0, 0, 1.55), (0, 0, 0.95), 0.02, 0.02, mat="thatch")
    cyl(me, 0, 0, 0.7, 0.95, 0.15, "planks", n=8, r1=0.18)
    K.roof(me, -1.0, 1.0, -0.7, 0.7, 2.3, 40, "shingle", over_eave=0.2, over_gable=0.15, thick=0.08)
    rnd = random.Random(778)                             # moss, flowers, a bucket (2026-09-30)
    for _ in range(6):
        a = rnd.uniform(0, math.tau)
        me.box(T(0.75 * math.cos(a), 0.75 * math.sin(a), 0.83, rz=math.degrees(a)), (0.3, 0.2, 0.06), "moss")
    DT.pots(me, rnd, ((1.1, -0.6, 0.0), (-1.05, 0.7, 0.0)))
    cyl(me, 0.95, 0.5, 0.0, 0.32, 0.15, "planks", n=8, r1=0.17)
    return me, None


def ivy():
    """Ivy climbing a wall: leafy clumps on a 2 x 4 m patch in the plane
    y = 0, facing -Y -- stands against a facade."""
    me = _m("ivy")
    rnd = random.Random(12)
    for _ in range(26):
        z = rnd.uniform(0.0, 3.8) * (1 - rnd.random() * 0.35)
        w = rnd.uniform(0.35, 0.8) * (1.2 - z / 5)
        me.box(T(rnd.uniform(-1.0, 1.0) * (1.1 - z / 6), -0.04, z + 0.2, ry=rnd.uniform(-20, 20)),
               (w, 0.08, w * rnd.uniform(0.6, 1.0)), "moss")
    for _ in range(4):
        x = rnd.uniform(-0.8, 0.8)
        K.beam(me, (x, -0.02, 0.0), (x + rnd.uniform(-0.4, 0.4), -0.02, rnd.uniform(1.5, 3.5)), 0.04, 0.03, mat="bark")
    return me, None


def flower_bed():
    """A kerbed flower bed: dirt, green clumps, red, blue and yellow blooms."""
    me = _m("flower_bed")
    rnd = random.Random(13)
    me.box(T(0, 0, 0.12), (2.6, 1.1, 0.24), "fieldstone", faces={"+z": "dirt"})
    for _ in range(14):
        x, y = rnd.uniform(-1.1, 1.1), rnd.uniform(-0.4, 0.4)
        me.box(T(x, y, 0.32, rz=rnd.uniform(0, 90)), (0.28, 0.28, 0.2), "moss")
        me.box(T(x + 0.05, y, 0.45), (0.12, 0.12, 0.08), rnd.choice(("cloth_red", "cloth_blue", "crops", "cloth_cream")))
    return me, None


def garden_bed():
    """A vegetable bed in a plank frame: rows of greens and a row of grain."""
    me = _m("garden_bed")
    me.box(T(0, 0, 0.12), (3.0, 1.6, 0.24), "planks", faces={"+z": "dirt"})
    for k in range(4):
        y = -0.55 + k * 0.37
        for j in range(7):
            me.box(T(-1.2 + j * 0.4, y, 0.32), (0.26, 0.2, 0.18 + 0.05 * ((j + k) % 2)), "crops" if k == 3 else "moss")
    return me, None


PROPS += [well, ivy, flower_bed, garden_bed]
PROPS += [bunting_s, bunting_m]


# ---------------------------------------------------------------- trees
def _canopy(me, rnd, cx, cy, cz, r, mat="moss"):
    """A faceted leaf blob: two eight-sided cones base to base, jittered --
    the hedge's surface, so a tree and a hedge read as the same green."""
    k = rnd.uniform(0.85, 1.15)
    rot = rnd.uniform(0, 45)
    cyl(me, cx, cy, cz - r * 0.55 * k, cz, r * 0.35, mat, n=8, r1=r, rot=rot)
    cyl(me, cx, cy, cz, cz + r * 0.8 * k, r, mat, n=8, r1=r * 0.28, rot=rot)
    # leaf clumps on the blob's surface (2026-09-30, the detail rollout)
    for _ in range(int(6 + r * 4)):
        a, e = rnd.uniform(0, math.tau), rnd.uniform(-0.35, 0.9)
        rr = r * rnd.uniform(0.75, 0.95)
        px, py, pz = cx + rr * math.cos(a) * math.cos(e), cy + rr * math.sin(a) * math.cos(e), cz + r * 0.7 * math.sin(e)
        s = r * rnd.uniform(0.28, 0.42)
        cyl(me, px, py, pz - s * 0.5, pz, s * 0.3, mat, n=6, r1=s, rot=rnd.uniform(0, 60))
        cyl(me, px, py, pz, pz + s * 0.6, s, mat, n=6, r1=s * 0.25, rot=rnd.uniform(0, 60))


def _trunk(me, rnd, h, r0, branches):
    cyl(me, 0, 0, -0.1, h, r0, "bark", n=7, r1=r0 * 0.7)
    for (bx, by, bz) in branches:
        rod(me, (0, 0, h * 0.8), (bx, by, bz), r0 * 0.45, "bark", n=5, r1=r0 * 0.25)


def tree_broad():
    """A broad yard tree, ~6.5 m: the size of a two-storey house's eaves, so
    a yard reads as a yard and not a forest (the Octopath towns' trees)."""
    me, sh = _m("tree_broad"), K.Mesh("SHADOW_tree_broad")
    rnd = random.Random(21)
    _trunk(me, rnd, 2.6, 0.3, [(1.1, 0.4, 3.4), (-1.0, -0.5, 3.5), (0.2, -0.9, 4.2)])
    for (x, y, z, r) in ((0, 0, 4.3, 2.3), (1.3, 0.4, 3.8, 1.6), (-1.2, -0.5, 3.9, 1.7), (0.2, -1.0, 5.1, 1.5), (-0.3, 0.9, 5.0, 1.4)):
        _canopy(me, rnd, x, y, z, r)
    K.proxy_box(sh, -0.3, 0.3, -0.3, 0.3, -0.5, 2.8)
    K.proxy_box(sh, -2.2, 2.2, -2.2, 2.2, 2.8, 6.2)
    return me, sh


def tree_slim():
    """A slim tree, ~6.2 m: since 2026-09-30 a conifer (the user's sheet: dark
    green spires among the round trees), five drooping tiers on a trunk."""
    me, sh = _m("tree_slim"), K.Mesh("SHADOW_tree_slim")
    rnd = random.Random(22)
    cyl(me, 0, 0, -0.1, 1.6, 0.2, "bark", n=7, r1=0.15)
    for k, (z, r) in enumerate(((1.2, 1.7), (2.2, 1.45), (3.1, 1.2), (3.9, 0.95), (4.6, 0.7))):
        rot = rnd.uniform(0, 36)
        cyl(me, 0, 0, z, z + 0.35, r * 0.55, "moss", n=10, r1=r, rot=rot)
        cyl(me, 0, 0, z + 0.35, z + 1.3, r, "moss", n=10, r1=r * 0.18, rot=rot)
        for j in range(10):                              # the tier's ragged hem
            a = math.radians(rot) + j * math.tau / 10 + rnd.uniform(-0.1, 0.1)
            me.box(T(r * 0.95 * math.cos(a), r * 0.95 * math.sin(a), z + 0.28, rz=math.degrees(a)),
                   (0.34, 0.26, 0.16), "moss")
    cyl(me, 0, 0, 5.6, 6.3, 0.35, "moss", n=8, r1=0.02)
    K.proxy_box(sh, -0.25, 0.25, -0.25, 0.25, -0.5, 2.6)
    K.proxy_box(sh, -1.4, 1.4, -1.4, 1.4, 2.6, 5.8)
    return me, sh


PROPS += [tree_broad, tree_slim]
