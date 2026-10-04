"""
Emberglass library - the 89 detailed props.

Everything the sheet lists outside the 20 structures: walls, elevation, ground
tiles, fences, market and street props, decorations, docks, miscellany, nature
and interior. Built from the same detail vocabulary as the buildings, so a
barrel beside a townhouse reads as the same world.

House rule for this pass: handcrafted and lived-in, never cleaner. Nothing is
symmetric, nothing is unworn, every run of anything has one member out of line.
"""

import bpy
import bmesh
import random
from math import radians, cos, sin, tan, pi, atan2

import builder_primitives as bp
import detail_primitives as dp
import detail_architecture as da
from detail_primitives import (_begin, _end, _box, _blob, _cyl, _quad,
                               _prism_beam, _peg, _nail_head, _moss_clump,
                               _moss_run, _lichen_patch, _weed_tuft,
                               _ivy_leaf)
from detail_buildings import _link, _spread, SHADED

def _sm(mats, stone="limestone"):
    """The four stone slots for a palette: mortar, then blocks A, B and C.

    Castles are granite, churches ashlar, houses limestone and everything
    built by a village mason - bridges, stairs, field walls - fieldstone.
    A library where every stone is the same reads as one quarry.
    """
    mo, a, b, c = dp.STONE_PALETTES[stone]
    return [mats[mo], mats[a], mats[b], mats[c]]


TILE = 2.8          # ground tile module
RUN = 2.8           # fence / wall module length


# =============================================================================
# Local makers
# =============================================================================

def _plank_run(bm, mat, chip, rng, length, width, thick, n, loc, axis="x",
               gap=0.014, sag=0.0, nails=None):
    """A run of boards with unequal widths, slight warp and nail heads."""
    ws = [rng.uniform(0.82, 1.18) for _ in range(n)]
    tot = sum(ws)
    cursor = -width * 0.5
    for i in range(n):
        bw = (ws[i] / tot) * width
        c = cursor + bw * 0.5
        droop = sag * sin(pi * (i + 0.5) / n)
        if axis == "x":
            p = (loc[0], loc[1] + c, loc[2] - droop)
            rot = (0, pi / 2, 0)
            start = (p[0] - length * 0.5, p[1], p[2])
        else:
            p = (loc[0] + c, loc[1], loc[2] - droop)
            rot = (-pi / 2, 0, 0)          # Rx(-pi/2) sends local +Z to +Y
            start = (p[0], p[1] - length * 0.5, p[2])
        _prism_beam(bm, mat, length, bw - gap, thick, loc=start, rot=rot,
                    chamfer=0.008, rings=3, bow=rng.uniform(0.003, 0.012),
                    rng=rng, chips=1, chip_mat=chip, base=True)
        if nails is not None:
            for t in (0.06, 0.94):
                if axis == "x":
                    np_ = (start[0] + length * t, p[1], p[2] + thick * 0.55)
                else:
                    np_ = (p[0], start[1] + length * t, p[2] + thick * 0.55)
                _nail_head(bm, nails, np_, radius=0.018)
        cursor += bw


def _board_wall(bm, mat, chip, rng, length, height, thick, loc, axis="x",
                n=None, gap=0.012, nails=None, lean=0.0):
    """Upright boarding. A plank run lies flat, so sides need their own maker."""
    n = n or max(3, int(length / 0.22))
    ws = [rng.uniform(0.85, 1.15) for _ in range(n)]
    tot = sum(ws)
    cursor = -length * 0.5
    for i in range(n):
        bw = (ws[i] / tot) * length
        c = cursor + bw * 0.5
        p = (loc[0] + c, loc[1], loc[2]) if axis == "x" else \
            (loc[0], loc[1] + c, loc[2])
        _prism_beam(bm, mat, height, (bw - gap) if axis == "x" else thick,
                    thick if axis == "x" else (bw - gap),
                    loc=p, rot=(lean, 0, 0), chamfer=0.007, rings=3,
                    bow=rng.uniform(0.002, 0.008), rng=rng, chips=1,
                    chip_mat=chip, base=True)
        if nails is not None:
            for t in (0.12, 0.88):
                _nail_head(bm, nails, (p[0], p[1] - thick * 0.6,
                                       p[2] + height * t), radius=0.015)
        cursor += bw


def _coping(name, mats, width, depth, seed, loc):
    """Stone coping so a wall prop never shows the bare top of its core."""
    obj, mesh, bm = _begin(name, [mats["M_Stone_Block_A"],
                                  mats["M_Stone_Block_C"], mats["M_Moss"]])
    rng = random.Random(seed)
    n = max(4, int(width / 0.36))
    for i in range(n):
        x = -width * 0.5 + (i + 0.5) * (width / n)
        _box(bm, rng.choice([0, 1]),
             size=((width / n) * 0.94, depth, rng.uniform(0.14, 0.19)),
             loc=(x, 0, 0.0), rot=(0, 0, rng.uniform(-0.012, 0.012)),
             base=True)
        if rng.random() < 0.34:
            _moss_clump(bm, 2, (x, -depth * 0.45, 0.17),
                        rng.uniform(0.05, 0.10), rng)
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = loc
    return ob


def _rubble_course(bm, mats_idx, rng, length, height, thick, z, axis="x",
                   loc=(0, 0, 0), blocks=(0.20, 0.52), mortar=0.045):
    """One course of irregular facing stones along a straight run."""
    cursor = -length * 0.5
    guard = 0
    while cursor < length * 0.5 - 0.04 and guard < 48:
        guard += 1
        bl = min(rng.uniform(*blocks), length * 0.5 - cursor)
        if bl < 0.09:
            break
        c = cursor + bl * 0.5
        t = thick * rng.uniform(0.86, 1.10)
        bh = height * rng.uniform(0.76, 1.0)
        zc = z + (height - bh) * rng.uniform(-0.4, 0.4)
        mi = rng.choice(mats_idx)
        if axis == "x":
            _box(bm, mi, size=(bl - mortar, t, bh),
                 loc=(loc[0] + c, loc[1], zc),
                 rot=(rng.uniform(-0.02, 0.02), rng.uniform(-0.015, 0.015), 0))
        else:
            _box(bm, mi, size=(t, bl - mortar, bh),
                 loc=(loc[0], loc[1] + c, zc),
                 rot=(rng.uniform(-0.015, 0.015), rng.uniform(-0.02, 0.02), 0))
        cursor += bl


def _leaf_mass(bm, mat_list, rng, centre, rx, ry, rz, count, size=(0.10, 0.20)):
    """A body of foliage built from individual leaves, not a green sphere."""
    for _ in range(count):
        u = rng.uniform(0, 2 * pi)
        v = rng.uniform(-1.0, 1.0)
        s = (1.0 - v * v) ** 0.5
        p = (centre[0] + cos(u) * s * rx * rng.uniform(0.55, 1.0),
             centre[1] + sin(u) * s * ry * rng.uniform(0.55, 1.0),
             centre[2] + v * rz * rng.uniform(0.55, 1.0))
        _ivy_leaf(bm, rng.choice(mat_list), p, rng.uniform(*size),
                  (rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5),
                   rng.uniform(0, 2 * pi)), rng)


def _rope(bm, mat, rng, p0, p1, sag=0.18, segs=7, r=0.022):
    """A slack line - nothing in this library hangs straight."""
    import mathutils
    a, b = mathutils.Vector(p0), mathutils.Vector(p1)
    prev = None
    for i in range(segs + 1):
        t = i / segs
        p = a.lerp(b, t)
        p.z -= sag * sin(pi * t)
        if prev is not None:
            d = p - prev
            L = d.length
            if L > 0.005:
                rot = mathutils.Vector((0, 0, 1)).rotation_difference(
                    d.normalized()).to_euler()
                _cyl(bm, mat, r, L, ((prev + p) * 0.5),
                     rot=(rot.x, rot.y, rot.z), segments=6)
        prev = p


# =============================================================================
# 1. WALLS & FORTIFICATIONS
# =============================================================================

def wall_straight(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    _link(dp.create_masonry_box("Wl_Straight", RUN, 0.95, 3.0, stone="granite",
                                location=(ox, oy, oz), mats=mats, seed=3001,
                                course_h=0.30, block_len=(0.22, 0.62),
                                shaded_faces=SHADED, moss_amount=0.20,
                                lichen_amount=0.12, weeds=True), col)
    cr = da.create_crenellation("Wl_Straight_Cren", RUN + 0.24, 1.15,
                                stone="granite",
                                mats=mats, seed=3003, merlon=0.46, gap=0.36,
                                height=0.68, thick=0.30)
    cr.location = (ox, oy, oz + 3.0)
    _link(cr, col)
    wk = dp.create_cobble_apron("Wl_Straight_Walk", RUN - 0.20, 0.55,
                                stone="granite",
                                mats=mats, seed=3005, cobble=0.40,
                                location=(ox, oy, oz + 3.03), kerb=False,
                                weeds=True, thickness=0.10)
    _link(wk, col)
    _link(dp.create_ivy_climber("Wl_Straight_Ivy", height=2.1, width=0.9,
                                mats=mats, seed=3007, stems=3, density=1.1),
          col).location = (ox - 0.75, oy - 0.48, oz + 0.15)


def wall_corner(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    _link(dp.create_masonry_box("Wl_Corner", 2.1, 2.1, 3.0, stone="granite",
                                location=(ox, oy, oz), mats=mats, seed=3011,
                                course_h=0.30, block_len=(0.22, 0.62),
                                shaded_faces=SHADED, moss_amount=0.20,
                                lichen_amount=0.12, weeds=True), col)
    cr = da.create_crenellation("Wl_Corner_Cren", 2.34, 2.34, mats=mats,
                                stone="granite",
                                seed=3013, merlon=0.46, gap=0.36, height=0.68,
                                thick=0.30)
    cr.location = (ox, oy, oz + 3.0)
    _link(cr, col)
    _link(dp.create_cobble_apron("Wl_Corner_Walk", 1.7, 1.7, mats=mats,
                                 stone="granite",
                                 seed=3015, cobble=0.40,
                                 location=(ox, oy, oz + 3.03), kerb=False,
                                 weeds=True, thickness=0.10), col)
    iv = dp.create_ivy_climber("Wl_Corner_Ivy", height=2.4, width=1.0,
                               mats=mats, seed=3017, stems=3, corner=True)
    iv.location = (ox - 1.05, oy - 1.05, oz + 0.12)
    iv.rotation_euler = (0, 0, radians(-90))
    _link(iv, col)


def wall_tower(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    _link(da.create_round_tower("Wl_Tower", radius=1.45, height=4.4, mats=mats,
                                stone="granite",
                                seed=3021, course_h=0.30, batter=0.05,
                                arrow_slits=3, string_courses=(2.7,)), col)
    cr = da.create_crenellation("Wl_Tower_Cren", 0, 0, mats=mats, seed=3023,
                                stone="granite",
                                merlon=0.42, gap=0.34, height=0.62, thick=0.30,
                                round_plan=True, radius=1.48)
    cr.location = (ox, oy, oz + 4.5)
    _link(cr, col)
    ban = da.create_banner("Wl_Tower_Banner", width=0.74, height=1.75,
                           mats=mats, seed=3025, colour="red")
    ban.location = (ox + 0.3, oy - 1.42, oz + 3.05)
    _link(ban, col)


def wall_gatehouse(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    port = da.create_arch_portal("Wl_Gate_Portal", width=2.3, height=2.8,
                                 stone="granite",
                                 depth=1.25, mats=mats, seed=3031, gate=False,
                                 portcullis=True)
    port.location = (ox, oy, oz)
    _link(port, col)
    for sgn in (-1, 1):
        _link(dp.create_masonry_box(f"Wl_Gate_Pier{sgn}", 0.95, 1.25, 3.5, stone="granite",
                                    location=(ox + sgn * 1.65, oy, oz),
                                    mats=mats, seed=3033 + (sgn > 0) * 7,
                                    course_h=0.30, block_len=(0.22, 0.60),
                                    shaded_faces=SHADED, moss_amount=0.18,
                                    weeds=True), col)
    _link(dp.create_masonry_box("Wl_Gate_Head", 2.5, 1.25, 1.0, stone="granite",
                                location=(ox, oy, oz + 2.5), mats=mats,
                                seed=3037, course_h=0.28, plinth=False,
                                ground_moss=False, weeds=False,
                                shaded_faces=SHADED, moss_amount=0.14), col)
    cr = da.create_crenellation("Wl_Gate_Cren", 4.3, 1.45, mats=mats,
                                stone="granite",
                                seed=3039, merlon=0.44, gap=0.34, height=0.64,
                                thick=0.30)
    cr.location = (ox, oy, oz + 3.5)
    _link(cr, col)
    for i, sgn in enumerate((-1, 1)):
        ban = da.create_banner(f"Wl_Gate_Ban{i}", width=0.70, height=1.55,
                               mats=mats, seed=3041 + i * 5,
                               colour="blue" if i else "red")
        ban.location = (ox + sgn * 0.82, oy - 0.68, oz + 2.75)
        _link(ban, col)


def castle_gate(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    port = da.create_arch_portal("Cst_Gate", width=2.9, height=3.4, depth=1.6,
                                 stone="granite",
                                 mats=mats, seed=3051, gate=True,
                                 portcullis=True)
    port.location = (ox, oy, oz)
    _link(port, col)
    for sgn in (-1, 1):
        _link(dp.create_masonry_box(f"Cst_Pier{sgn}", 1.15, 1.6, 4.2, stone="granite",
                                    location=(ox + sgn * 2.05, oy, oz),
                                    mats=mats, seed=3053 + (sgn > 0) * 7,
                                    course_h=0.31, block_len=(0.24, 0.64),
                                    shaded_faces=SHADED, moss_amount=0.18,
                                    weeds=True), col)
        for i in range(4):
            cb = dp.create_corbel_bracket(f"Cst_Corb{sgn}{i}", mats=mats,
                                          seed=3057 + i * 3, size=0.34,
                                          projection=0.26)
            cb.location = (ox + sgn * 2.05, oy - 0.8 + i * 0.52, oz + 3.75)
            _link(cb, col)
    _link(dp.create_masonry_box("Cst_Head", 3.2, 1.6, 1.1, stone="granite",
                                location=(ox, oy, oz + 3.1), mats=mats,
                                seed=3061, course_h=0.29, plinth=False,
                                ground_moss=False, weeds=False,
                                shaded_faces=SHADED, moss_amount=0.14), col)
    cr = da.create_crenellation("Cst_Cren", 5.5, 1.85, mats=mats, seed=3063,
                                stone="granite",
                                merlon=0.50, gap=0.38, height=0.72, thick=0.34)
    cr.location = (ox, oy, oz + 4.2)
    _link(cr, col)
    for i, sgn in enumerate((-1, 1)):
        ban = da.create_banner(f"Cst_Ban{i}", width=0.80, height=2.0,
                               mats=mats, seed=3065 + i * 5,
                               colour="red" if i else "blue")
        ban.location = (ox + sgn * 1.05, oy - 0.86, oz + 3.35)
        _link(ban, col)


def retaining_wall(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    _link(dp.create_masonry_box("Ret_Wall", RUN, 1.0, 2.1, stone="fieldstone",
                                location=(ox, oy, oz), mats=mats, seed=3071,
                                course_h=0.24, block_len=(0.18, 0.50),
                                shaded_faces=SHADED, moss_amount=0.26,
                                lichen_amount=0.14, weeds=True,
                                weed_rows=3), col)
    # Earth bank retained behind it, spilling over
    obj, mesh, bm = _begin("Ret_Bank", [mats["M_Soil"], mats["M_Grass"],
                                        mats["M_Weed_Green"],
                                        mats["M_Foliage"], mats["M_Flowers"]])
    rng = random.Random(3073)
    _box(bm, 0, size=(RUN, 1.35, 2.0), loc=(0, 0.95, 1.0))
    for i in range(int(RUN / 0.22)):
        x = -RUN * 0.5 + (i + 0.5) * 0.22
        _blob(bm, 1, (x + rng.uniform(-0.04, 0.04),
                      rng.uniform(0.20, 0.55), 2.02 + rng.uniform(-0.03, 0.05)),
              (0.20, 0.22, 0.10), rot=(0, 0, rng.uniform(0, pi)))
        if rng.random() < 0.55:
            _weed_tuft(bm, 2, (x, rng.uniform(0.18, 0.45), 2.06),
                       rng.uniform(0.14, 0.26), rng, blades=rng.randint(5, 8))
    _leaf_mass(bm, [3, 3, 1], rng, (0.0, 0.85, 2.25), RUN * 0.45, 0.45, 0.18, 70)
    for _ in range(9):
        _blob(bm, 4, (rng.uniform(-RUN * 0.45, RUN * 0.45),
                      rng.uniform(0.35, 1.0), 2.25 + rng.uniform(0, 0.12)),
              (0.035, 0.035, 0.035))
    bnk = _end(obj, mesh, bm, bevel=0.008, segments=2)
    bnk.location = (ox, oy, oz)
    _link(bnk, col)
    # Timber shoring posts leaning on the face
    _link(dp.create_timber_frame("Ret_Posts", [
        {"p0": (ox - 0.95, oy - 0.72, oz), "p1": (ox - 0.95, oy - 0.50, oz + 2.1),
         "w": 0.17, "d": 0.17, "chips": 3, "moss": True},
        {"p0": (ox + 0.85, oy - 0.72, oz), "p1": (ox + 0.85, oy - 0.50, oz + 2.1),
         "w": 0.16, "d": 0.16, "chips": 3},
        {"p0": (ox - 1.15, oy - 0.62, oz + 1.9), "p1": (ox + 1.15, oy - 0.62, oz + 1.9),
         "w": 0.14, "d": 0.13, "chips": 3, "moss": True}], mats=mats,
        seed=3075), col)


def cliff_wall(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Clf_Wall", [mats["M_Granite_A"], mats["M_Granite_B"],
                                        mats["M_Granite_C"], mats["M_Moss"],
                                        mats["M_Weed_Green"], mats["M_Soil"],
                                        mats["M_Grass"]])
    rng = random.Random(3081)
    w, h, d = RUN, 2.8, 1.2
    # Strata: irregular slabs stacked with overhangs, never a flat face
    z = 0.0
    i = 0
    while z < h:
        sh = rng.uniform(0.22, 0.46)
        sh = min(sh, h - z)
        n = max(3, int(w / rng.uniform(0.45, 0.85)))
        cursor = -w * 0.5
        for k in range(n):
            bl = (w / n) * rng.uniform(0.85, 1.20)
            bl = min(bl, w * 0.5 - cursor)
            if bl < 0.10:
                break
            proj = rng.uniform(-0.10, 0.16)
            _box(bm, rng.choice([0, 1, 2, 0]),
                 size=(bl - 0.02, d * rng.uniform(0.8, 1.05), sh * 1.04),
                 loc=(cursor + bl * 0.5, proj, z + sh * 0.5),
                 rot=(rng.uniform(-0.05, 0.05), rng.uniform(-0.04, 0.04),
                      rng.uniform(-0.05, 0.05)))
            cursor += bl
        if rng.random() < 0.55:
            _moss_run(bm, 3, (-w * 0.45, -d * 0.5 - 0.02, z + sh),
                      (w * 0.45, -d * 0.5 - 0.02, z + sh),
                      int(w / 0.26), 0.085, rng, skip=0.42)
        z += sh
        i += 1
    # Grassy crown and ledge growth
    _box(bm, 5, size=(w, d * 0.95, 0.18), loc=(0, 0.02, h + 0.06))
    for k in range(int(w / 0.20)):
        x = -w * 0.5 + (k + 0.5) * 0.20
        _blob(bm, 6, (x, rng.uniform(-0.25, 0.3), h + 0.16),
              (0.19, 0.20, 0.09), rot=(0, 0, rng.uniform(0, pi)))
        if rng.random() < 0.6:
            _weed_tuft(bm, 4, (x, rng.uniform(-0.4, 0.25), h + 0.18),
                       rng.uniform(0.14, 0.28), rng, blades=rng.randint(5, 8))
    for _ in range(7):
        _weed_tuft(bm, 4, (rng.uniform(-w * 0.45, w * 0.45),
                           -d * 0.5 - 0.04, rng.uniform(0.4, h - 0.3)),
                   rng.uniform(0.10, 0.20), rng, blades=4)
    ob = _end(obj, mesh, bm, bevel=0.012, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    iv = dp.create_ivy_climber("Clf_Ivy", height=2.0, width=1.0, mats=mats,
                               seed=3083, stems=3, density=1.2)
    iv.location = (ox + 0.8, oy - 0.62, oz + 0.2)
    _link(iv, col)


def ruin_wall(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Rn_Wall", _sm(mats, "fieldstone") +
                           [mats["M_Moss"], mats["M_Lichen"],
                            mats["M_Weed_Green"]])
    rng = random.Random(3091)
    w, d = RUN, 0.75
    # Broken profile: the wall head falls away in steps
    prof = [(-w * 0.5, 2.5), (-w * 0.22, 2.2), (0.05, 1.35), (w * 0.28, 1.75),
            (w * 0.5, 0.55)]
    _box(bm, 0, size=(w - 0.16, d - 0.20, 1.0), loc=(0, 0, 0.5))
    for i in range(len(prof) - 1):
        x0, h0 = prof[i]
        x1, h1 = prof[i + 1]
        seg = x1 - x0
        n_c = max(2, int(max(h0, h1) / 0.26))
        for c in range(n_c):
            z = c * 0.26
            frac = z / max(0.05, max(h0, h1))
            hh = h0 + (h1 - h0) * ((c + 0.5) / n_c)
            if z > hh:
                continue
            _rubble_course(bm, [1, 2, 3], rng, seg * 0.98, 0.26, 0.24, z,
                           axis="x", loc=(x0 + seg * 0.5, -d * 0.35, 0),
                           blocks=(0.16, 0.42))
            _rubble_course(bm, [1, 2, 3], rng, seg * 0.98, 0.26, 0.24, z,
                           axis="x", loc=(x0 + seg * 0.5, d * 0.35, 0),
                           blocks=(0.16, 0.42))
            if rng.random() < 0.30:
                _moss_clump(bm, 4, (x0 + rng.uniform(0, seg), -d * 0.5,
                                    z + 0.22), rng.uniform(0.06, 0.13), rng)
            if rng.random() < 0.18:
                _lichen_patch(bm, 5, (x0 + rng.uniform(0, seg), -d * 0.5, z),
                              rng.uniform(0.06, 0.11), 1, rng, plates=3)
    # Fallen stones at the foot
    for _ in range(11):
        s = rng.uniform(0.14, 0.30)
        _blob(bm, rng.choice([1, 2, 3]),
              (rng.uniform(-w * 0.55, w * 0.55), -d * 0.5 - rng.uniform(0.1, 0.7),
               s * 0.4), (s, s * rng.uniform(0.7, 1.1), s * rng.uniform(0.5, 0.8)),
              rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(9):
        _weed_tuft(bm, 6, (rng.uniform(-w * 0.5, w * 0.5),
                           -d * 0.5 - rng.uniform(0.0, 0.6), 0.02),
                   rng.uniform(0.12, 0.26), rng, blades=rng.randint(5, 8))
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    iv = dp.create_ivy_climber("Rn_Ivy", height=1.9, width=1.1, mats=mats,
                               seed=3093, stems=3, density=1.35)
    iv.location = (ox - 0.9, oy - 0.42, oz + 0.1)
    _link(iv, col)


# =============================================================================
# 2. STAIRS, RAMPS & ELEVATION
# =============================================================================

def stairs_small(mats, col, o=(0, 0, 0)):
    st = dp.create_stone_steps_detailed("St_Small", mats=mats, seed=3101,
                                        width=1.9, depth=1.30, height=0.88,
                                        n_steps=5, kerbs=False,
                                        stone="fieldstone")
    st.location = o
    _link(st, col)


def stairs_large(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    st = dp.create_stone_steps_detailed("St_Large", mats=mats, seed=3103,
                                        width=2.2, depth=2.6, height=1.95,
                                        n_steps=9, kerbs=False,
                                        stone="fieldstone")
    st.location = o
    _link(st, col)
    for sgn in (-1, 1):
        _link(dp.create_masonry_box(f"St_Large_Cheek{sgn}", 0.32, 2.9, 1.0, stone="fieldstone",
                                    location=(ox + sgn * 1.36, oy - 0.05, oz),
                                    mats=mats, seed=3105 + (sgn > 0) * 5,
                                    course_h=0.24, block_len=(0.18, 0.46),
                                    shaded_faces=SHADED, moss_amount=0.24,
                                    weeds=True, ledge=True), col)


def ramp(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Rmp", _sm(mats, "fieldstone") +
                           [mats["M_Moss"], mats["M_Weed_Green"],
                            mats["M_Cobble_A"], mats["M_Cobble_B"]])
    rng = random.Random(3111)
    w, L, h = 2.3, 3.4, 1.35
    ang = atan2(h, L)

    # Solid core so the ramp reads as built earth-and-stone, not as steps
    n_sl = 22
    for i in range(n_sl):
        t = (i + 0.5) / n_sl
        y = -L * 0.5 + t * L
        z = t * h
        _box(bm, 0, size=(w - 0.22, L / n_sl * 1.1, z + 0.06),
             loc=(0, y, (z + 0.06) * 0.5))

    # Cobbled running surface, laid across the slope and slightly dished
    rows = int((L / cos(ang)) / 0.24)
    for r in range(rows):
        t = (r + 0.5) / rows
        y = -L * 0.5 + t * L
        z = t * h
        n_c = int(w / 0.25)
        for c in range(n_c):
            x = -w * 0.5 + (c + 0.5) * (w / n_c) + rng.uniform(-0.015, 0.015)
            dish = 0.022 * (1.0 - (2.0 * (c + 0.5) / n_c - 1.0) ** 2)
            _box(bm, rng.choice([6, 7, 6]),
                 size=((w / n_c) * 0.88, 0.26, 0.13),
                 loc=(x, y, z + 0.055 - dish),
                 rot=(ang, 0, rng.uniform(-0.10, 0.10)))
        if rng.random() < 0.18:
            _weed_tuft(bm, 5, (rng.uniform(-w * 0.44, w * 0.44), y, z + 0.09),
                       rng.uniform(0.08, 0.16), rng, blades=4)

    # Retaining walls rising with the ramp, coursed and capped
    for sgn in (-1, 1):
        n_c = int(L / 0.40)
        for c in range(n_c):
            t = (c + 0.5) / n_c
            y = -L * 0.5 + t * L
            zt = t * h + 0.42
            n_cr = max(1, int(zt / 0.26))
            for k in range(n_cr):
                _rubble_course(bm, [1, 2, 3], rng, 0.40, 0.26, 0.30,
                               k * 0.26, axis="y",
                               loc=(sgn * (w * 0.5 + 0.12), y, 0),
                               blocks=(0.18, 0.38))
            _box(bm, 3, size=(0.40, 0.42, 0.15),
                 loc=(sgn * (w * 0.5 + 0.12), y, n_cr * 0.26), base=True)
            if rng.random() < 0.32:
                _moss_clump(bm, 4, (sgn * (w * 0.5 + 0.12), y,
                                    n_cr * 0.26 + 0.16),
                            rng.uniform(0.05, 0.10), rng)
    _moss_run(bm, 4, (-w * 0.5, -L * 0.5, 0.03), (w * 0.5, -L * 0.5, 0.03),
              6, 0.08, rng, skip=0.4)
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


def platform(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    _link(dp.create_masonry_box("Plt", 3.2, 3.2, 1.0, location=(ox, oy, oz),
                                stone="fieldstone",
                                mats=mats, seed=3121, course_h=0.26,
                                block_len=(0.20, 0.55), shaded_faces=SHADED,
                                moss_amount=0.22, lichen_amount=0.12,
                                weeds=True), col)
    _link(dp.create_cobble_apron("Plt_Deck", 2.9, 2.9, mats=mats, seed=3123,
                                 stone="fieldstone",
                                 cobble=0.42, location=(ox, oy, oz + 1.03),
                                 kerb=False, weeds=True, thickness=0.10), col)


def arch_bridge(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Arb", _sm(mats, "fieldstone") +
                           [mats["M_Moss"], mats["M_Weed_Green"],
                            mats["M_Lichen"]])
    rng = random.Random(3131)
    span, wid, rise = 4.6, 2.0, 1.55
    r = span * 0.5
    # Voussoir ring on both faces
    n_v = max(13, int(pi * r / 0.30))
    for sgn in (-1, 1):
        for i in range(n_v):
            a0 = pi * (i + 0.5) / n_v
            vr = r + 0.28
            _box(bm, rng.choice([1, 2, 3]),
                 size=((pi * vr / n_v) * 0.95, 0.30, 0.56),
                 loc=(-cos(a0) * vr, sgn * (wid * 0.5 - 0.15),
                      rise - r + sin(a0) * vr),
                 rot=(0, a0 - pi * 0.5, 0))
            if rng.random() < 0.22:
                _moss_clump(bm, 4, (-cos(a0) * (vr + 0.30),
                                    sgn * (wid * 0.5 + 0.02),
                                    rise - r + sin(a0) * (vr + 0.30)),
                            rng.uniform(0.05, 0.11), rng)
    # Barrel soffit between the rings
    for i in range(n_v):
        a0 = pi * (i + 0.5) / n_v
        vr = r + 0.10
        _box(bm, 0, size=((pi * vr / n_v) * 1.02, wid - 0.34, 0.22),
             loc=(-cos(a0) * vr, 0, rise - r + sin(a0) * vr),
             rot=(0, a0 - pi * 0.5, 0))
    # Spandrels and abutments
    for sgn in (-1, 1):
        for c in range(4):
            z = c * 0.30
            xr = r + 0.40
            _rubble_course(bm, [1, 2, 3], rng, 1.5, 0.30, 0.34, z, axis="x",
                           loc=(sgn * (xr - 0.55), 0, 0), blocks=(0.20, 0.48))
    # Deck: cambered setts with a parapet each side
    n_d = int(span / 0.28) + 4
    for i in range(n_d):
        t = i / (n_d - 1.0)
        x = -span * 0.5 - 0.5 + t * (span + 1.0)
        camber = rise * 0.30 * max(0.0, 1.0 - (2 * t - 1) ** 2)
        for c in range(int(wid / 0.28)):
            y = -wid * 0.5 + (c + 0.5) * (wid / int(wid / 0.28))
            _box(bm, rng.choice([1, 2, 3]), size=(0.26, 0.26, 0.14),
                 loc=(x, y, rise + 0.10 + camber),
                 rot=(0, 0, rng.uniform(-0.09, 0.09)))
        for sgn in (-1, 1):
            _box(bm, rng.choice([1, 3]), size=(0.27, 0.26, 0.62),
                 loc=(x, sgn * (wid * 0.5 + 0.08), rise + 0.16 + camber),
                 base=True)
            _box(bm, 3, size=(0.29, 0.34, 0.12),
                 loc=(x, sgn * (wid * 0.5 + 0.08), rise + 0.78 + camber),
                 base=True)
            if rng.random() < 0.22:
                _moss_clump(bm, 4, (x, sgn * (wid * 0.5 + 0.06),
                                    rise + 0.62 + camber),
                            rng.uniform(0.04, 0.09), rng)
        if rng.random() < 0.16:
            _weed_tuft(bm, 5, (x, wid * 0.5 * rng.uniform(-0.8, 0.8),
                               rise + 0.17 + camber), rng.uniform(0.09, 0.17),
                       rng, blades=5)
    # Abutments: without them the ring floats with nothing to spring from
    for sgn in (-1, 1):
        for c in range(6):
            _rubble_course(bm, [1, 2, 3], rng, 1.15, 0.30, wid + 0.10,
                           c * 0.30, axis="x",
                           loc=(sgn * (r + 0.72), 0, 0), blocks=(0.24, 0.52))
        _box(bm, 3, size=(1.25, wid + 0.22, 0.16),
             loc=(sgn * (r + 0.72), 0, 1.80), base=True)
        for _ in range(4):
            _moss_clump(bm, 4, (sgn * (r + 0.72) + rng.uniform(-0.5, 0.5),
                                -wid * 0.5 - 0.06, rng.uniform(0.1, 1.6)),
                        rng.uniform(0.06, 0.12), rng)
        for _ in range(3):
            _weed_tuft(bm, 5, (sgn * (r + 0.72) + rng.uniform(-0.5, 0.5),
                               -wid * 0.5 - 0.10, 0.02),
                       rng.uniform(0.11, 0.22), rng, blades=6)
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    iv = dp.create_ivy_climber("Arb_Ivy", height=1.4, width=0.9, mats=mats,
                               seed=3133, stems=2, density=1.3)
    iv.location = (ox - 1.9, oy - wid * 0.5 - 0.10, oz + 0.15)
    _link(iv, col)


def stone_bridge(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Stb", _sm(mats, "fieldstone") +
                           [mats["M_Moss"], mats["M_Weed_Green"],
                            mats["M_Timber_Aged"], mats["M_Timber_Chip"]])
    rng = random.Random(3141)
    L, wid = 4.4, 2.2
    # Two piers, cutwatered and carried right up to the bearers
    for sgn in (-1, 1):
        for c in range(5):
            _rubble_course(bm, [1, 2, 3], rng, 1.15, 0.24, wid * 0.92,
                           c * 0.24, axis="x", loc=(sgn * L * 0.30, 0, 0),
                           blocks=(0.22, 0.46))
        _box(bm, 3, size=(1.30, wid + 0.10, 0.14),
             loc=(sgn * L * 0.30, 0, 1.20), base=True)
        for cut in (-1, 1):
            _cyl(bm, 2, 0.34, 1.20, (sgn * L * 0.30, cut * wid * 0.46, 0.0),
                 segments=6, radius2=0.22, base=True)
        for _ in range(3):
            _moss_clump(bm, 4, (sgn * L * 0.30 + rng.uniform(-0.4, 0.4),
                                -wid * 0.5, rng.uniform(0.05, 1.0)),
                        rng.uniform(0.05, 0.11), rng)
    # Bank abutments at each end
    for sgn in (-1, 1):
        for c in range(5):
            _rubble_course(bm, [1, 2, 3], rng, 0.85, 0.24, wid * 0.95,
                           c * 0.24, axis="x",
                           loc=(sgn * (L * 0.5 + 0.30), 0, 0),
                           blocks=(0.20, 0.44))
    # Timber deck on stone bearers
    for sgn in (-1, 1):
        _box(bm, 6, size=(L + 0.2, 0.16, 0.16), loc=(0, sgn * (wid * 0.5 - 0.12), 1.16))
    _plank_run(bm, 6, 7, rng, L + 0.3, wid, 0.09, int(wid / 0.24),
               (0, 0, 1.22), axis="x", sag=0.035, nails=1)
    # Parapet posts and rails, one leaning
    for sgn in (-1, 1):
        for i in range(5):
            x = -L * 0.5 + i * (L / 4.0)
            lean = radians(rng.uniform(-5, 5))
            _prism_beam(bm, 6, 0.85, 0.10, 0.10,
                        loc=(x, sgn * (wid * 0.5 - 0.03), 1.26),
                        rot=(lean, 0, 0), chamfer=0.010, rings=3, rng=rng,
                        chips=2, chip_mat=7, base=True)
        for zz in (1.65, 1.95):
            _prism_beam(bm, 6, L + 0.1, 0.07, 0.08,
                        loc=(-(L + 0.1) * 0.5, sgn * (wid * 0.5 - 0.03), zz),
                        rot=(0, pi / 2, 0), chamfer=0.008, rings=4,
                        bow=0.02, rng=rng, chips=2, chip_mat=7, base=True)
    for _ in range(6):
        _moss_clump(bm, 4, (rng.uniform(-L * 0.5, L * 0.5),
                            rng.uniform(-wid * 0.5, wid * 0.5), 1.27),
                    rng.uniform(0.04, 0.08), rng, squash=0.3)
    for _ in range(5):
        _weed_tuft(bm, 5, (rng.uniform(-L * 0.4, L * 0.4),
                           rng.choice([-1, 1]) * (wid * 0.5 - 0.06), 1.26),
                   rng.uniform(0.08, 0.16), rng, blades=4)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


# =============================================================================
# 3. STREET & GROUND TILES
# =============================================================================

def _tile_begin(name, mats, extra=()):
    return _begin(name, [mats["M_Soil"], mats["M_Cobble_Dirt"],
                         mats["M_Moss"], mats["M_Weed_Green"]] +
                  [mats[k] for k in extra])


def stone_road(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _tile_begin("Gt_StoneRoad", mats,
                                ("M_Stone_Block_A", "M_Stone_Block_B",
                                 "M_Stone_Block_C"))
    rng = random.Random(3201)
    _box(bm, 1, size=(TILE, TILE, 0.14), loc=(0, 0, -0.07))
    # Big irregular flagstones with open joints
    rows = 5
    for r in range(rows):
        y = -TILE * 0.5 + (r + 0.5) * (TILE / rows)
        cursor = -TILE * 0.5
        phase = rng.uniform(0.0, 0.4)
        while cursor < TILE * 0.5 - 0.06:
            bl = min(rng.uniform(0.42, 0.85), TILE * 0.5 - cursor)
            if bl < 0.12:
                break
            if rng.random() > 0.045:
                _box(bm, rng.choice([4, 5, 6, 4]),
                     size=(bl - 0.05, (TILE / rows) - 0.05,
                           rng.uniform(0.09, 0.13)),
                     loc=(cursor + bl * 0.5 + phase * 0.0, y,
                          rng.uniform(-0.02, 0.01)),
                     rot=(rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02),
                          rng.uniform(-0.05, 0.05)), base=True)
            cursor += bl
    for _ in range(16):
        _weed_tuft(bm, 3, (rng.uniform(-TILE * 0.48, TILE * 0.48),
                           rng.uniform(-TILE * 0.48, TILE * 0.48), 0.02),
                   rng.uniform(0.07, 0.15), rng, blades=rng.randint(3, 6))
    for _ in range(12):
        _moss_clump(bm, 2, (rng.uniform(-TILE * 0.48, TILE * 0.48),
                            rng.uniform(-TILE * 0.48, TILE * 0.48), 0.03),
                    rng.uniform(0.04, 0.09), rng, squash=0.3)
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = o
    _link(ob, col)


def cobblestone(mats, col, o=(0, 0, 0)):
    ob = dp.create_cobble_apron("Gt_Cobble", TILE, TILE, mats=mats, seed=3203,
                                cobble=0.24, location=o, kerb=False,
                                weeds=True, thickness=0.14)
    _link(ob, col)


def dirt_road(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _tile_begin("Gt_Dirt", mats,
                                ("M_Cobble_A", "M_Cobble_B", "M_Grass"))
    rng = random.Random(3205)
    _box(bm, 0, size=(TILE, TILE, 0.16), loc=(0, 0, -0.06))
    # Cart ruts and churned earth
    for sgn in (-1, 1):
        for i in range(int(TILE / 0.16)):
            y = -TILE * 0.5 + (i + 0.5) * 0.16
            _box(bm, 1, size=(0.42, 0.16, 0.06),
                 loc=(sgn * 0.62 + rng.uniform(-0.05, 0.05), y, 0.0),
                 rot=(0, rng.uniform(-0.03, 0.03), rng.uniform(-0.05, 0.05)))
    for i in range(int(TILE / 0.22)):
        for j in range(int(TILE / 0.22)):
            x = -TILE * 0.5 + (i + 0.5) * 0.22 + rng.uniform(-0.04, 0.04)
            y = -TILE * 0.5 + (j + 0.5) * 0.22 + rng.uniform(-0.04, 0.04)
            _blob(bm, rng.choice([0, 1, 0]), (x, y, rng.uniform(0.0, 0.03)),
                  (rng.uniform(0.10, 0.17), rng.uniform(0.10, 0.17), 0.045),
                  rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(18):
        _blob(bm, rng.choice([4, 5]),
              (rng.uniform(-TILE * 0.48, TILE * 0.48),
               rng.uniform(-TILE * 0.48, TILE * 0.48), 0.02),
              (rng.uniform(0.04, 0.09),) * 3, rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(14):
        _weed_tuft(bm, 3, (rng.uniform(-TILE * 0.48, TILE * 0.48),
                           rng.uniform(-TILE * 0.48, TILE * 0.48), 0.03),
                   rng.uniform(0.09, 0.19), rng, blades=rng.randint(4, 7))
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = o
    _link(ob, col)


def plaza_tile(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _tile_begin("Gt_Plaza", mats,
                                ("M_Stone_Block_A", "M_Stone_Block_C",
                                 "M_Granite_A", "M_Granite_C"))
    rng = random.Random(3207)
    _box(bm, 1, size=(TILE, TILE, 0.14), loc=(0, 0, -0.07))
    n = 8
    s = TILE / n
    for i in range(n):
        for j in range(n):
            x = -TILE * 0.5 + (i + 0.5) * s
            y = -TILE * 0.5 + (j + 0.5) * s
            border = (i in (0, n - 1)) or (j in (0, n - 1))
            mi = 6 if border else (4 if (i + j) % 2 == 0 else 7)
            if rng.random() < 0.03:
                continue
            _box(bm, mi, size=(s - 0.035, s - 0.035, rng.uniform(0.09, 0.12)),
                 loc=(x + rng.uniform(-0.012, 0.012),
                      y + rng.uniform(-0.012, 0.012), rng.uniform(-0.015, 0.008)),
                 rot=(rng.uniform(-0.012, 0.012), rng.uniform(-0.012, 0.012),
                      rng.uniform(-0.025, 0.025)), base=True)
    for _ in range(9):
        _weed_tuft(bm, 3, (rng.uniform(-TILE * 0.45, TILE * 0.45),
                           rng.uniform(-TILE * 0.45, TILE * 0.45), 0.02),
                   rng.uniform(0.05, 0.11), rng, blades=3)
    for _ in range(8):
        _moss_clump(bm, 2, (rng.uniform(-TILE * 0.45, TILE * 0.45),
                            rng.uniform(-TILE * 0.45, TILE * 0.45), 0.03),
                    rng.uniform(0.035, 0.07), rng, squash=0.28)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = o
    _link(ob, col)


def wooden_deck(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _tile_begin("Gt_Deck", mats,
                                ("M_Timber_Aged", "M_Timber_Chip",
                                 "M_Iron_Aged"))
    rng = random.Random(3209)
    for sgn in (-1, 1):
        _box(bm, 4, size=(TILE, 0.15, 0.14), loc=(0, sgn * TILE * 0.35, -0.08))
    _plank_run(bm, 4, 5, rng, TILE, TILE, 0.10, int(TILE / 0.24), (0, 0, 0.0),
               axis="x", sag=0.018, nails=6)
    for _ in range(10):
        _moss_clump(bm, 2, (rng.uniform(-TILE * 0.45, TILE * 0.45),
                            rng.uniform(-TILE * 0.45, TILE * 0.45), 0.06),
                    rng.uniform(0.035, 0.075), rng, squash=0.28)
    for _ in range(5):
        _weed_tuft(bm, 3, (rng.uniform(-TILE * 0.45, TILE * 0.45),
                           rng.uniform(-TILE * 0.45, TILE * 0.45), 0.05),
                   rng.uniform(0.06, 0.12), rng, blades=3)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def dock_tile(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _tile_begin("Gt_Dock", mats,
                                ("M_Timber_Aged", "M_Timber_Chip",
                                 "M_Iron_Aged", "M_Rope"))
    rng = random.Random(3211)
    for sgn in (-1, 1):
        _box(bm, 4, size=(TILE, 0.17, 0.18), loc=(0, sgn * TILE * 0.33, -0.10))
    _plank_run(bm, 4, 5, rng, TILE, TILE, 0.10, int(TILE / 0.26), (0, 0, 0.0),
               axis="x", sag=0.030, nails=6)
    # Mooring cleat and a coiled rope, because a dock is used
    _box(bm, 6, size=(0.10, 0.28, 0.10), loc=(0.85, -0.85, 0.10))
    for i in range(4):
        _cyl(bm, 7, 0.16 - i * 0.022, 0.05, (-0.9, 0.75, 0.08 + i * 0.045),
             segments=10)
    for _ in range(12):
        _moss_clump(bm, 2, (rng.uniform(-TILE * 0.45, TILE * 0.45),
                            rng.uniform(-TILE * 0.45, TILE * 0.45), 0.06),
                    rng.uniform(0.04, 0.09), rng, squash=0.26)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def grassy_ground(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _tile_begin("Gt_Grass", mats,
                                ("M_Grass", "M_Foliage", "M_Flowers",
                                 "M_Stone_Block_B"))
    rng = random.Random(3213)
    _box(bm, 0, size=(TILE, TILE, 0.14), loc=(0, 0, -0.07))
    n = int(TILE / 0.20)
    for i in range(n):
        for j in range(n):
            x = -TILE * 0.5 + (i + 0.5) * (TILE / n) + rng.uniform(-0.04, 0.04)
            y = -TILE * 0.5 + (j + 0.5) * (TILE / n) + rng.uniform(-0.04, 0.04)
            _blob(bm, rng.choice([4, 4, 5]), (x, y, 0.02),
                  (rng.uniform(0.11, 0.17), rng.uniform(0.11, 0.17),
                   rng.uniform(0.04, 0.08)), rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(46):
        _weed_tuft(bm, 3, (rng.uniform(-TILE * 0.48, TILE * 0.48),
                           rng.uniform(-TILE * 0.48, TILE * 0.48), 0.03),
                   rng.uniform(0.10, 0.22), rng, blades=rng.randint(4, 7))
    for _ in range(14):
        _blob(bm, 6, (rng.uniform(-TILE * 0.45, TILE * 0.45),
                      rng.uniform(-TILE * 0.45, TILE * 0.45),
                      rng.uniform(0.10, 0.18)), (0.035, 0.035, 0.035))
    for _ in range(6):
        s = rng.uniform(0.08, 0.16)
        _blob(bm, 7, (rng.uniform(-TILE * 0.45, TILE * 0.45),
                      rng.uniform(-TILE * 0.45, TILE * 0.45), s * 0.35),
              (s, s * 0.8, s * 0.55), rot=(0, 0, rng.uniform(0, pi)))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def cliff_edge(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _tile_begin("Gt_CliffEdge", mats,
                                ("M_Granite_A", "M_Granite_B", "M_Granite_C",
                                 "M_Grass"))
    rng = random.Random(3215)
    _box(bm, 0, size=(TILE, TILE * 0.55, 0.16), loc=(0, TILE * 0.22, -0.06))
    n = int(TILE / 0.20)
    for i in range(n):
        x = -TILE * 0.5 + (i + 0.5) * (TILE / n)
        _blob(bm, 7, (x + rng.uniform(-0.04, 0.04),
                      rng.uniform(0.15, TILE * 0.45), 0.03),
              (0.18, 0.19, 0.08), rot=(0, 0, rng.uniform(0, pi)))
        if rng.random() < 0.65:
            _weed_tuft(bm, 3, (x, rng.uniform(-0.05, TILE * 0.4), 0.04),
                       rng.uniform(0.11, 0.22), rng, blades=rng.randint(4, 7))
    # The face falling away toward -Y, in broken strata
    z = 0.0
    while z > -1.5:
        sh = rng.uniform(0.20, 0.40)
        cursor = -TILE * 0.5
        while cursor < TILE * 0.5 - 0.05:
            bl = min(rng.uniform(0.32, 0.72), TILE * 0.5 - cursor)
            if bl < 0.10:
                break
            _box(bm, rng.choice([4, 5, 6]),
                 size=(bl - 0.02, rng.uniform(0.40, 0.72), sh * 1.05),
                 loc=(cursor + bl * 0.5,
                      rng.uniform(-0.25, 0.05) + z * 0.22, z - sh * 0.5),
                 rot=(rng.uniform(-0.06, 0.06), rng.uniform(-0.05, 0.05),
                      rng.uniform(-0.07, 0.07)))
            cursor += bl
        if rng.random() < 0.6:
            _moss_run(bm, 2, (-TILE * 0.45, -0.32 + z * 0.22, z),
                      (TILE * 0.45, -0.32 + z * 0.22, z),
                      int(TILE / 0.28), 0.08, rng, skip=0.45)
        z -= sh
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = o
    _link(ob, col)


# =============================================================================
# 4. FENCES & BARRIERS
# =============================================================================

def wood_fence(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Fn_Wood", [mats["M_Timber_Aged"],
                                       mats["M_Timber_Chip"],
                                       mats["M_Iron_Aged"], mats["M_Moss"],
                                       mats["M_Weed_Green"]])
    rng = random.Random(3301)
    n_post = 4
    for i in range(n_post):
        x = -RUN * 0.5 + i * (RUN / (n_post - 1.0))
        lean = radians(rng.uniform(-6, 6)) if i == 2 else radians(rng.uniform(-2, 2))
        _prism_beam(bm, 0, rng.uniform(1.0, 1.12), 0.13, 0.13, loc=(x, 0, 0),
                    rot=(lean, 0, 0), chamfer=0.012, rings=4, bow=0.012,
                    rng=rng, chips=3, chip_mat=1, base=True)
        _moss_clump(bm, 3, (x, 0, 0.05), rng.uniform(0.05, 0.09), rng)
    for zz in (0.42, 0.78):
        for i in range(n_post - 1):
            x0 = -RUN * 0.5 + i * (RUN / (n_post - 1.0))
            seg = RUN / (n_post - 1.0)
            _prism_beam(bm, 0, seg + 0.05, 0.075, 0.055,
                        loc=(x0 - 0.02, 0, zz + rng.uniform(-0.02, 0.02)),
                        rot=(0, pi / 2, 0), chamfer=0.008, rings=3,
                        bow=0.018, rng=rng, chips=2, chip_mat=1, base=True)
            for t in (0.05, 0.95):
                _nail_head(bm, 2, (x0 + seg * t, -0.035, zz), radius=0.017)
    for _ in range(7):
        _weed_tuft(bm, 4, (rng.uniform(-RUN * 0.5, RUN * 0.5),
                           rng.uniform(-0.09, 0.09), 0.01),
                   rng.uniform(0.11, 0.24), rng, blades=rng.randint(4, 7))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def stone_fence(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    _link(dp.create_masonry_box("Fn_Stone", RUN, 0.45, 0.95, stone="fieldstone",
                                location=(ox, oy, oz), mats=mats, seed=3311,
                                course_h=0.20, block_len=(0.14, 0.42),
                                shaded_faces=SHADED, moss_amount=0.30,
                                lichen_amount=0.16, weeds=True, weed_rows=3,
                                quoins=False), col)
    obj, mesh, bm = _begin("Fn_Stone_Cap", [mats["M_Fieldstone_C"],
                                            mats["M_Fieldstone_A"],
                                            mats["M_Moss"]])
    rng = random.Random(3313)
    # Coping stones set on edge, the way a dry wall is finished
    n = int(RUN / 0.22)
    for i in range(n):
        x = -RUN * 0.5 + (i + 0.5) * (RUN / n)
        _box(bm, rng.choice([0, 1]),
             size=((RUN / n) * 0.92, 0.50, rng.uniform(0.22, 0.30)),
             loc=(x, rng.uniform(-0.02, 0.02), 0.0),
             rot=(0, rng.uniform(-0.10, 0.10), rng.uniform(-0.03, 0.03)),
             base=True)
        if rng.random() < 0.30:
            _moss_clump(bm, 2, (x, -0.24, 0.20), rng.uniform(0.04, 0.085), rng)
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = (ox, oy, oz + 0.95)
    _link(ob, col)


def iron_fence(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Fn_Iron", [mats["M_Iron_Aged"],
                                       mats["M_Fieldstone_B"],
                                       mats["M_Fieldstone_C"],
                                       mats["M_Moss"], mats["M_Weed_Green"]])
    rng = random.Random(3321)
    for sgn in (-1, 1):
        for c in range(4):
            _box(bm, rng.choice([1, 2]), size=(0.34, 0.34, 0.26),
                 loc=(sgn * RUN * 0.5, 0, c * 0.26), base=True)
        _box(bm, 2, size=(0.42, 0.42, 0.13), loc=(sgn * RUN * 0.5, 0, 1.04),
             base=True)
        _moss_clump(bm, 3, (sgn * RUN * 0.5, -0.18, 0.06),
                    rng.uniform(0.05, 0.09), rng)
    for zz in (0.30, 0.92):
        _box(bm, 0, size=(RUN - 0.34, 0.045, 0.055), loc=(0, 0, zz))
    n = 13
    for i in range(n):
        x = -RUN * 0.5 + 0.28 + i * ((RUN - 0.56) / (n - 1.0))
        h = rng.uniform(1.16, 1.24)
        _box(bm, 0, size=(0.042, 0.042, h), loc=(x, 0, 0), base=True,
             rot=(radians(rng.uniform(-1.6, 1.6)), 0, 0))
        _cyl(bm, 0, 0.042, 0.13, (x, 0, h), segments=4, radius2=0.004,
             base=True)
    for _ in range(6):
        _weed_tuft(bm, 4, (rng.uniform(-RUN * 0.5, RUN * 0.5),
                           rng.uniform(-0.07, 0.07), 0.01),
                   rng.uniform(0.09, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=1, angle=44.0)
    ob.location = o
    _link(ob, col)


def railing(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Fn_Railing", [mats["M_Timber_Aged"],
                                          mats["M_Timber_Chip"],
                                          mats["M_Iron_Aged"], mats["M_Moss"]])
    rng = random.Random(3331)
    for sgn in (-1, 1):
        _prism_beam(bm, 0, 1.0, 0.115, 0.115, loc=(sgn * RUN * 0.5, 0, 0),
                    chamfer=0.012, rings=4, bow=0.010, rng=rng, chips=3,
                    chip_mat=1, base=True)
        _blob(bm, 0, (sgn * RUN * 0.5, 0, 1.03), (0.085, 0.085, 0.10))
    n = 11
    drums = [(0.040, 0.26), (0.056, 0.16), (0.038, 0.30)]
    for i in range(n):
        x = -RUN * 0.5 + 0.22 + i * ((RUN - 0.44) / (n - 1.0))
        # Turned spindle: three stacked drums running bottom rail to handrail
        zz = 0.16
        for (rr, hh) in drums:
            _cyl(bm, 0, rr, hh, (x + rng.uniform(-0.006, 0.006), 0, zz),
                 segments=8, base=True)
            zz += hh
    _prism_beam(bm, 0, RUN + 0.1, 0.10, 0.08,
                loc=(-(RUN + 0.1) * 0.5, 0, 0.88), rot=(0, pi / 2, 0),
                chamfer=0.010, rings=4, bow=0.022, rng=rng, chips=3,
                chip_mat=1, base=True)
    _prism_beam(bm, 0, RUN - 0.2, 0.07, 0.055,
                loc=(-(RUN - 0.2) * 0.5, 0, 0.13), rot=(0, pi / 2, 0),
                chamfer=0.008, rings=3, bow=0.014, rng=rng, base=True)
    for _ in range(4):
        _moss_clump(bm, 3, (rng.uniform(-RUN * 0.5, RUN * 0.5), 0.0, 0.03),
                    rng.uniform(0.04, 0.08), rng)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = o
    _link(ob, col)


def post_chain(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Fn_PostChain", [mats["M_Fieldstone_A"],
                                            mats["M_Fieldstone_C"],
                                            mats["M_Iron_Aged"],
                                            mats["M_Moss"],
                                            mats["M_Weed_Green"]])
    rng = random.Random(3341)
    n = 4
    xs = [-RUN * 0.5 + i * (RUN / (n - 1.0)) for i in range(n)]
    for i, x in enumerate(xs):
        for c in range(3):
            _box(bm, rng.choice([0, 1]),
                 size=(0.26 - c * 0.02, 0.26 - c * 0.02, 0.24),
                 loc=(x, 0, c * 0.24),
                 rot=(0, 0, rng.uniform(-0.03, 0.03)), base=True)
        _blob(bm, 1, (x, 0, 0.76), (0.15, 0.15, 0.10))
        _box(bm, 2, size=(0.05, 0.05, 0.08), loc=(x, 0, 0.80), base=True)
        _moss_clump(bm, 3, (x, -0.13, 0.04), rng.uniform(0.045, 0.085), rng)
    for i in range(n - 1):
        # Chain as alternating links, sagging between posts
        x0, x1 = xs[i], xs[i + 1]
        segs = 9
        for k in range(segs):
            t = (k + 0.5) / segs
            x = x0 + (x1 - x0) * t
            z = 0.82 - 0.17 * sin(pi * t)
            _cyl(bm, 2, 0.032, 0.016, (x, 0, z),
                 rot=(pi / 2 if k % 2 else 0, 0, 0), segments=8)
    for _ in range(5):
        _weed_tuft(bm, 4, (rng.uniform(-RUN * 0.5, RUN * 0.5),
                           rng.uniform(-0.09, 0.09), 0.01),
                   rng.uniform(0.09, 0.18), rng, blades=4)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def hedge(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Fn_Hedge", [mats["M_Hedge_Green"],
                                        mats["M_Foliage"], mats["M_Ivy_Leaf"],
                                        mats["M_Ivy_Stem"], mats["M_Soil"],
                                        mats["M_Flowers"]])
    rng = random.Random(3351)
    h, w = 1.05, 0.62
    _box(bm, 4, size=(RUN, w * 0.7, 0.10), loc=(0, 0, 0.05))
    # Solid inner body: a hedge is opaque, the leaves only break its edge
    for i in range(int(RUN / 0.16)):
        x = -RUN * 0.5 + (i + 0.5) * 0.16
        hh = h * 0.80 + 0.07 * sin(i * 0.55)
        _box(bm, 0, size=(0.17, w * 0.80, hh),
             loc=(x, rng.uniform(-0.02, 0.02), 0.06),
             rot=(0, 0, rng.uniform(-0.04, 0.04)), base=True)
    # Woody stems inside, then a clipped-but-scruffy leaf body
    for i in range(int(RUN / 0.32)):
        x = -RUN * 0.5 + (i + 0.5) * 0.32
        _box(bm, 3, size=(0.045, 0.045, h * 0.8), loc=(x, 0, 0.05), base=True,
             rot=(radians(rng.uniform(-6, 6)), 0, 0))
    n = int(RUN / 0.07)
    for i in range(n):
        x = -RUN * 0.5 + (i + 0.5) * (RUN / n)
        # Top line dips and rises - a real hedge is never level
        hh = h + 0.09 * sin(i * 0.55) + rng.uniform(-0.04, 0.04)
        for _ in range(12):
            p = (x + rng.uniform(-0.07, 0.07),
                 rng.uniform(-w * 0.58, w * 0.58),
                 rng.uniform(0.10, hh + 0.05))
            _ivy_leaf(bm, rng.choice([0, 0, 1, 2]), p, rng.uniform(0.10, 0.19),
                      (rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5),
                       rng.uniform(0, 2 * pi)), rng)
    for _ in range(10):
        _blob(bm, 5, (rng.uniform(-RUN * 0.5, RUN * 0.5),
                      rng.uniform(-w * 0.5, w * 0.5), rng.uniform(0.6, h)),
              (0.030, 0.030, 0.030))
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = o
    _link(ob, col)


def spikes(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Fn_Spikes", [mats["M_Timber_Aged"],
                                         mats["M_Timber_Chip"],
                                         mats["M_Rope"], mats["M_Soil"],
                                         mats["M_Weed_Green"]])
    rng = random.Random(3361)
    _box(bm, 3, size=(RUN, 1.05, 0.62), loc=(0, 0, 0.26))
    for i in range(int(RUN / 0.18)):
        x = -RUN * 0.5 + (i + 0.5) * 0.18
        _blob(bm, 3, (x + rng.uniform(-0.03, 0.03), rng.uniform(-0.36, 0.36),
                      0.56), (0.19, 0.22, 0.12), rot=(0, 0, rng.uniform(0, pi)))
        if rng.random() < 0.5:
            _weed_tuft(bm, 4, (x, rng.uniform(-0.4, 0.4), 0.60),
                       rng.uniform(0.12, 0.24), rng, blades=5)
    n = 7
    for i in range(n):
        x = -RUN * 0.5 + 0.22 + i * ((RUN - 0.44) / (n - 1.0))
        lean = radians(rng.uniform(40, 54))
        L = rng.uniform(1.55, 1.90)
        _prism_beam(bm, 0, L, 0.185, 0.185, loc=(x, 0.22, 0.34),
                    rot=(lean, 0, radians(rng.uniform(-8, 8))),
                    chamfer=0.014, rings=4, bow=0.018, rng=rng, chips=3,
                    chip_mat=1, taper=0.16, base=True)
        if i % 2 == 0:
            _prism_beam(bm, 0, L * 0.85, 0.165, 0.165,
                        loc=(x + 0.13, -0.24, 0.34),
                        rot=(-lean, 0, radians(rng.uniform(-8, 8))),
                        chamfer=0.012, rings=3, rng=rng, chips=2, chip_mat=1,
                        taper=0.18, base=True)
    # Lashing rail tying the row together
    _prism_beam(bm, 0, RUN - 0.2, 0.095, 0.095,
                loc=(-(RUN - 0.2) * 0.5, 0.0, 0.62), rot=(0, pi / 2, 0),
                chamfer=0.010, rings=4, bow=0.02, rng=rng, base=True)
    for i in range(n):
        x = -RUN * 0.5 + 0.22 + i * ((RUN - 0.44) / (n - 1.0))
        for k in range(3):
            _cyl(bm, 2, 0.075, 0.032, (x, 0.02, 0.56 + k * 0.038),
                 rot=(pi / 2, 0, 0), segments=8)
    for _ in range(6):
        _weed_tuft(bm, 4, (rng.uniform(-RUN * 0.5, RUN * 0.5),
                           rng.uniform(-0.2, 0.2), 0.10),
                   rng.uniform(0.10, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def gate_small(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Fn_Gate", [mats["M_Timber_Aged"],
                                       mats["M_Timber_Chip"],
                                       mats["M_Iron_Aged"], mats["M_Moss"],
                                       mats["M_Weed_Green"]])
    rng = random.Random(3371)
    w, h = 1.30, 1.30
    for sgn in (-1, 1):
        _prism_beam(bm, 0, h + 0.55, 0.185, 0.185,
                    loc=(sgn * (w * 0.5 + 0.10), 0, 0),
                    rot=(radians(rng.uniform(-1.2, 1.2)), 0, 0), chamfer=0.014,
                    rings=4, bow=0.010, rng=rng, chips=3, chip_mat=1,
                    base=True)
        _blob(bm, 0, (sgn * (w * 0.5 + 0.10), 0, h + 0.56),
              (0.125, 0.125, 0.125))
        _moss_clump(bm, 3, (sgn * (w * 0.5 + 0.10), -0.11, 0.04),
                    rng.uniform(0.05, 0.09), rng)
    # Leaf hung slightly open and sagging on its hinges
    swing = radians(18.0)
    tmp = bmesh.new()
    n_b = 5
    for i in range(n_b):
        x = -w * 0.5 + (i + 0.5) * (w / n_b)
        _prism_beam(tmp, 0, h, (w / n_b) - 0.020, 0.115, loc=(x, 0, 0),
                    chamfer=0.010, rings=3, bow=0.008, rng=rng, chips=2,
                    chip_mat=1, base=True)
    # Perimeter frame, so the leaf has an edge instead of a flat face
    for zz in (0.10, h - 0.10):
        _box(tmp, 0, size=(w + 0.02, 0.115, 0.105), loc=(0, 0.095, zz))
    for sx in (-1, 1):
        _box(tmp, 0, size=(0.075, 0.135, h), loc=(sx * w * 0.5, 0.012, h * 0.5))
    for zz in (0.20, h - 0.20):
        _box(tmp, 0, size=(w * 0.96, 0.075, 0.125), loc=(0, 0.072, zz))
    _box(tmp, 0, size=(w * 1.12, 0.055, 0.095), loc=(0, -0.095, h * 0.5),
         rot=(0, -0.70, 0))
    for zz in (0.18, h - 0.18):
        for t in (0.10, 0.45, 0.80):
            _nail_head(tmp, 2, (-w * 0.5 + w * t, -0.030, zz), radius=0.017)
        _box(tmp, 2, size=(w * 0.55, 0.020, 0.055), loc=(-w * 0.20, -0.030, zz))
    _cyl(tmp, 2, 0.045, 0.014, (w * 0.34, -0.040, h * 0.52),
         rot=(pi / 2, 0, 0), segments=10)
    sagm = 0.035
    import mathutils
    rotm = mathutils.Matrix.Rotation(swing, 3, 'Z')
    pivot = mathutils.Vector((-w * 0.5, 0.0, 0.0))
    for v in tmp.verts:
        p = rotm @ (v.co - pivot)
        v.co = mathutils.Vector((-w * 0.5 + p.x, p.y,
                                 p.z + 0.16 - sagm * (p.x + w * 0.5) / w))
    tm = bpy.data.meshes.new("_tmp_gate")
    tmp.to_mesh(tm)
    tmp.free()
    bm.from_mesh(tm)
    bpy.data.meshes.remove(tm)
    for _ in range(5):
        _weed_tuft(bm, 4, (rng.uniform(-w * 0.6, w * 0.6),
                           rng.uniform(-0.1, 0.1), 0.01),
                   rng.uniform(0.09, 0.19), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


# =============================================================================
# Shared makers for the remaining sections
# =============================================================================

def _tree(bm, rng, trunk_mat, bark_mat, leaf_mats, height=3.0, spread=1.25,
          branches=5, leaves=340, dead=False, lean=0.0, origin=(0.0, 0.0)):
    """A tree grown from a leaning trunk and forking limbs, not a cone on a stick."""
    segs = max(4, int(height / 0.45))
    px, py, pz = origin[0], origin[1], 0.0
    lx, ly = sin(lean), 0.0
    nodes = []
    for i in range(segs):
        t = i / segs
        seg_h = height / segs
        nx = px + lx * seg_h + rng.uniform(-0.06, 0.06)
        ny = py + ly * seg_h + rng.uniform(-0.06, 0.06)
        nz = pz + seg_h
        r = 0.20 * (1.0 - t * 0.68) + 0.035
        import mathutils
        _d = mathutils.Vector((nx - px, ny - py, nz - pz))
        _rot = mathutils.Vector((0, 0, 1)).rotation_difference(
            _d.normalized()).to_euler()
        _cyl(bm, bark_mat, r, _d.length * 1.14,
             ((px + nx) * 0.5, (py + ny) * 0.5, (pz + nz) * 0.5),
             rot=(_rot.x, _rot.y, _rot.z), segments=7)
        if t > 0.32:
            nodes.append((nx, ny, nz, r))
        px, py, pz = nx, ny, nz
    crown = []
    for b in range(branches):
        if not nodes:
            break
        bx, by, bz, br = nodes[rng.randrange(len(nodes))]
        ang = rng.uniform(0, 2 * pi)
        L = spread * rng.uniform(0.55, 1.05)
        ex = bx + cos(ang) * L
        ey = by + sin(ang) * L
        ez = bz + rng.uniform(0.18, 0.75)
        import mathutils
        d = mathutils.Vector((ex - bx, ey - by, ez - bz))
        rot = mathutils.Vector((0, 0, 1)).rotation_difference(
            d.normalized()).to_euler()
        _cyl(bm, bark_mat, br * 0.62, d.length, ((bx + ex) * 0.5, (by + ey) * 0.5,
                                                 (bz + ez) * 0.5),
             rot=(rot.x, rot.y, rot.z), segments=6)
        crown.append((ex, ey, ez))
        if rng.random() < 0.5:
            ex2 = ex + cos(ang + 0.8) * L * 0.55
            ey2 = ey + sin(ang + 0.8) * L * 0.55
            ez2 = ez + rng.uniform(0.1, 0.4)
            d2 = mathutils.Vector((ex2 - ex, ey2 - ey, ez2 - ez))
            rot2 = mathutils.Vector((0, 0, 1)).rotation_difference(
                d2.normalized()).to_euler()
            _cyl(bm, bark_mat, br * 0.40, d2.length,
                 ((ex + ex2) * 0.5, (ey + ey2) * 0.5, (ez + ez2) * 0.5),
                 rot=(rot2.x, rot2.y, rot2.z), segments=5)
            crown.append((ex2, ey2, ez2))
    if not dead and crown:
        per = max(8, leaves // len(crown))
        for (cx, cy, cz) in crown:
            _leaf_mass(bm, leaf_mats, rng, (cx, cy, cz),
                       spread * 0.52, spread * 0.52, spread * 0.44, per,
                       size=(0.11, 0.21))


def _sack(bm, cloth_mat, rope_mat, rng, loc, s=0.34, tipped=False):
    """A grain sack: a bulging body cinched at the neck."""
    x, y, z = loc
    yaw = rng.uniform(0, pi)
    _blob(bm, cloth_mat, (x, y, z + s * 0.52), (s * 0.62, s * 0.55, s * 0.58),
          rot=(0, 0, yaw), subdiv=1)
    _blob(bm, cloth_mat, (x, y, z + s * 0.20), (s * 0.70, s * 0.62, s * 0.34),
          rot=(0, 0, yaw), subdiv=1)
    _cyl(bm, rope_mat, s * 0.26, s * 0.07, (x, y, z + s * 0.88), segments=8)
    for k in range(3):
        a = yaw + k * 2.1
        _blob(bm, cloth_mat, (x + cos(a) * s * 0.18, y + sin(a) * s * 0.18,
                              z + s * 1.02), (s * 0.13, s * 0.13, s * 0.17),
              rot=(rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), a))


# =============================================================================
# 5. MARKET & STREET PROPS
# =============================================================================

def market_stall_a(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    aw = da.create_striped_awning("Mk_StallA_Awning", width=2.30, depth=1.30,
                                  mats=mats, seed=3401, colour="red",
                                  posts=False, height=2.15)
    aw.location = (ox, oy - 0.32, oz)
    _link(aw, col)
    obj, mesh, bm = _begin("Mk_StallA", [mats["M_Timber_Aged"],
                                         mats["M_Timber_Chip"],
                                         mats["M_Foliage"], mats["M_Flowers"],
                                         mats["M_Straw"], mats["M_Iron_Aged"]])
    rng = random.Random(3403)
    _plank_run(bm, 0, 1, rng, 2.25, 0.85, 0.07, 4, (0, -0.70, 0.88),
               axis="x", sag=0.014, nails=5)
    # Four posts run the full height and carry the canopy, so the stall is
    # one structure rather than a counter standing under a separate tent.
    for sgn in (-1, 1):
        for sy, ph in ((-1, 2.18), (1, 2.18)):
            _prism_beam(bm, 0, ph, 0.10, 0.10,
                        loc=(sgn * 1.02, -0.70 + sy * 0.32, 0.0),
                        rot=(radians(rng.uniform(-1.5, 1.5)), 0, 0),
                        chamfer=0.011, rings=4, bow=0.012, rng=rng, chips=3,
                        chip_mat=1, base=True)
    for sy in (-1, 1):
        _prism_beam(bm, 0, 2.12, 0.07, 0.07,
                    loc=(-1.06, -0.70 + sy * 0.32, 2.05), rot=(0, pi / 2, 0),
                    chamfer=0.008, rings=3, bow=0.014, rng=rng, base=True)
    _prism_beam(bm, 0, 2.0, 0.055, 0.055, loc=(-1.0, -0.70, 0.34),
                rot=(0, pi / 2, 0), chamfer=0.008, rings=3, rng=rng, base=True)
    # Produce piled on the counter, spilling
    for i in range(22):
        x = rng.uniform(-1.0, 1.0)
        y = -0.70 + rng.uniform(-0.28, 0.28)
        s = rng.uniform(0.055, 0.105)
        _blob(bm, rng.choice([2, 2, 3]), (x, y, 0.93 + s * 0.4),
              (s, s, s * 0.85), rot=(0, 0, rng.uniform(0, pi)))
    for i in range(4):
        _blob(bm, 4, (-0.75 + i * 0.5, -0.62, 1.02), (0.17, 0.13, 0.07),
              rot=(0, 0, rng.uniform(0, pi)))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    for i, (bx, by) in enumerate([(1.28, -0.35), (-1.30, 0.15)]):
        b = dp.create_crate_detailed(f"Mk_StallA_Crate{i}", mats=mats,
                                     seed=3405 + i * 7, size=0.52)
        b.location = (ox + bx, oy + by, oz)
        b.rotation_euler = (0, 0, radians(rng.uniform(-25, 25)))
        _link(b, col)


def market_stall_b(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    aw = da.create_striped_awning("Mk_StallB_Awning", width=2.30, depth=1.30,
                                  mats=mats, seed=3411, colour="blue",
                                  posts=False, height=2.15)
    aw.location = (ox, oy - 0.32, oz)
    _link(aw, col)
    obj, mesh, bm = _begin("Mk_StallB", [mats["M_Timber_Aged"],
                                         mats["M_Timber_Chip"],
                                         mats["M_Cloth_White"],
                                         mats["M_Iron_Aged"],
                                         mats["M_Potion_Red"],
                                         mats["M_Potion_Blue"],
                                         mats["M_Potion_Green"]])
    rng = random.Random(3413)
    _plank_run(bm, 0, 1, rng, 2.25, 0.85, 0.07, 4, (0, -0.70, 0.88),
               axis="x", sag=0.014, nails=3)
    # Four posts run the full height and carry the canopy, so the stall is
    # one structure rather than a counter standing under a separate tent.
    for sgn in (-1, 1):
        for sy, ph in ((-1, 2.18), (1, 2.18)):
            _prism_beam(bm, 0, ph, 0.10, 0.10,
                        loc=(sgn * 1.02, -0.70 + sy * 0.32, 0.0),
                        rot=(radians(rng.uniform(-1.5, 1.5)), 0, 0),
                        chamfer=0.011, rings=4, bow=0.012, rng=rng, chips=3,
                        chip_mat=1, base=True)
    for sy in (-1, 1):
        _prism_beam(bm, 0, 2.12, 0.07, 0.07,
                    loc=(-1.06, -0.70 + sy * 0.32, 2.05), rot=(0, pi / 2, 0),
                    chamfer=0.008, rings=3, bow=0.014, rng=rng, base=True)
    # Bolts of cloth and glassware
    for i in range(5):
        _box(bm, 2, size=(0.30, 0.26, 0.12),
             loc=(-0.85 + i * 0.42, -0.72, 0.95 + (i % 2) * 0.12),
             rot=(0, 0, radians(rng.uniform(-14, 14))))
    for i in range(7):
        mi = rng.choice([4, 5, 6])
        x = -0.85 + i * 0.29
        _cyl(bm, mi, 0.055, 0.17, (x, -0.55, 0.92), segments=8, base=True)
        _cyl(bm, mi, 0.022, 0.07, (x, -0.55, 1.09), segments=6, base=True)
    _box(bm, 0, size=(0.46, 0.05, 0.28), loc=(0, -1.16, 1.62),
         rot=(radians(-12), 0, 0))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    b = dp.create_barrel_detailed("Mk_StallB_Barrel", mats=mats, seed=3415,
                                  radius=0.30, height=0.76, mossy=True)
    b.location = (ox + 1.30, oy - 0.20, oz)
    _link(b, col)


def cart(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Mk_Cart", [mats["M_Timber_Aged"],
                                       mats["M_Timber_Chip"],
                                       mats["M_Iron_Aged"], mats["M_Straw"],
                                       mats["M_Foliage"]])
    rng = random.Random(3421)
    bw, bl, bz = 1.10, 1.60, 0.66
    _plank_run(bm, 0, 1, rng, bl, bw, 0.075, 5, (0, 0, bz), axis="y",
               sag=0.012, nails=2)
    # Upright sides and tailboard
    for sgn in (-1, 1):
        _board_wall(bm, 0, 1, rng, bl, 0.46, 0.055,
                    (sgn * bw * 0.5, 0, bz + 0.04), axis="y", nails=2)
    _board_wall(bm, 0, 1, rng, bw, 0.46, 0.055, (0, bl * 0.5, bz + 0.04),
                axis="x", nails=2)
    for sgn in (-1, 1):
        _prism_beam(bm, 0, bl + 0.06, 0.075, 0.06,
                    loc=(sgn * bw * 0.5, -(bl + 0.06) * 0.5, bz + 0.50),
                    rot=(-pi / 2, 0, 0), chamfer=0.007, rings=3, bow=0.012,
                    rng=rng, chips=2, chip_mat=1, base=True)
    # Axle and bearers under the bed
    _cyl(bm, 2, 0.055, bw + 0.42, (0, -0.05, 0.44), rot=(0, pi / 2, 0),
         segments=8)
    for sgn in (-1, 1):
        _box(bm, 0, size=(0.10, bl * 0.9, 0.10), loc=(sgn * bw * 0.32, 0, bz - 0.07))
    # Wheels: the wheel lies in the YZ plane, so only Rx may be used
    for sgn in (-1, 1):
        cx, cz, r = sgn * (bw * 0.5 + 0.10), 0.44, 0.44
        _cyl(bm, 2, r + 0.05, 0.075, (cx, -0.05, cz), rot=(0, pi / 2, 0),
             segments=20)
        for k in range(12):
            a = 2 * pi * k / 12
            _box(bm, 0, size=(0.15, (2 * pi * r / 12) * 1.04, 0.075),
                 loc=(cx, -0.05 + cos(a) * r, cz + sin(a) * r),
                 rot=(a - pi / 2, 0, 0))
        for k in range(8):
            a = 2 * pi * k / 8 + 0.2
            _box(bm, 0, size=(0.06, 0.06, r * 0.90),
                 loc=(cx, -0.05 + cos(a) * r * 0.47, cz + sin(a) * r * 0.47),
                 rot=(a - pi / 2, 0, 0))
        _cyl(bm, 0, 0.12, 0.19, (cx, -0.05, cz), rot=(0, pi / 2, 0), segments=10)
        _cyl(bm, 2, 0.05, 0.24, (cx, -0.05, cz), rot=(0, pi / 2, 0), segments=8)
    # Shafts running forward, with a cross bar
    for sgn in (-1, 1):
        _prism_beam(bm, 0, 1.45, 0.075, 0.075,
                    loc=(sgn * bw * 0.34, -bl * 0.5, bz - 0.05),
                    rot=(radians(99), 0, 0), chamfer=0.010, rings=4,
                    bow=0.02, rng=rng, chips=2, chip_mat=1, base=True)
    _cyl(bm, 0, 0.045, bw * 0.78, (0, -bl * 0.5 - 1.38, bz + 0.17),
         rot=(0, pi / 2, 0), segments=8)
    # Load
    for i in range(11):
        _blob(bm, 3, (rng.uniform(-bw * 0.36, bw * 0.36),
                      rng.uniform(-bl * 0.34, bl * 0.38), bz + 0.19),
              (0.20, 0.17, 0.09), rot=(0, 0, rng.uniform(0, pi)))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def wagon(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Mk_Wagon", [mats["M_Timber_Aged"],
                                        mats["M_Timber_Chip"],
                                        mats["M_Iron_Aged"],
                                        mats["M_Canvas_Sail"],
                                        mats["M_Rope"], mats["M_Linen"]])
    rng = random.Random(3431)
    bw, bl, bz = 1.30, 2.40, 0.86
    _plank_run(bm, 0, 1, rng, bl, bw, 0.08, 6, (0, 0, bz), axis="y",
               sag=0.014, nails=2)
    for sgn in (-1, 1):
        _board_wall(bm, 0, 1, rng, bl, 0.52, 0.06,
                    (sgn * bw * 0.5, 0, bz + 0.04), axis="y", nails=2)
        _prism_beam(bm, 0, bl + 0.06, 0.08, 0.065,
                    loc=(sgn * bw * 0.5, -(bl + 0.06) * 0.5, bz + 0.56),
                    rot=(-pi / 2, 0, 0), chamfer=0.008, rings=4, bow=0.014,
                    rng=rng, chips=2, chip_mat=1, base=True)
    for sgn in (-1, 1):
        _board_wall(bm, 0, 1, rng, bw, 0.52, 0.06, (0, sgn * bl * 0.5, bz + 0.04),
                    axis="x", nails=2)
    # Tilt: five hoops with a slack canvas stretched over them
    hoop_z = bz + 0.56
    rise = 0.78
    for i in range(5):
        y = -bl * 0.40 + i * (bl * 0.80 / 4.0)
        for k in range(11):
            a = pi * (k + 0.5) / 11
            _box(bm, 0, size=(0.055, 0.055, (pi * bw * 0.5 / 11) * 1.25),
                 loc=(cos(a) * bw * 0.5, y, hoop_z + sin(a) * rise),
                 rot=(0, a - pi * 0.5, 0))
    for k in range(16):
        a = pi * (k + 0.5) / 16
        sag = 0.045 * sin(a)
        _box(bm, 3 if k % 4 else 5,
             size=((pi * bw * 0.5 / 16) * 2.05, bl * 0.94, 0.040),
             loc=(cos(a) * (bw * 0.5 + 0.050), 0,
                  hoop_z + sin(a) * (rise + 0.050) - sag),
             rot=(0, a - pi * 0.5, 0))
    # Puckered canvas over the end hoop, and a lashing along the side
    for k in range(9):
        a = pi * (k + 0.5) / 9
        _box(bm, 3, size=(0.15, 0.04, 0.17),
             loc=(cos(a) * bw * 0.46, -bl * 0.46, hoop_z + sin(a) * rise * 0.94),
             rot=(0, a - pi * 0.5, 0))
    _rope(bm, 4, rng, (-bw * 0.5, -bl * 0.44, bz + 0.52),
          (bw * 0.5, -bl * 0.44, bz + 0.52), sag=0.09, segs=6, r=0.018)
    # Running gear
    for sgn in (-1, 1):
        for yy, r in ((-bl * 0.32, 0.40), (bl * 0.32, 0.54)):
            cx, cz = sgn * (bw * 0.5 + 0.11), r
            _cyl(bm, 2, r + 0.045, 0.07, (cx, yy, cz), rot=(0, pi / 2, 0),
                 segments=18)
            for k in range(10):
                a = 2 * pi * k / 10
                _box(bm, 0, size=(0.14, (2 * pi * r / 10) * 1.04, 0.07),
                     loc=(cx, yy + cos(a) * r, cz + sin(a) * r),
                     rot=(a - pi / 2, 0, 0))
            for k in range(7):
                a = 2 * pi * k / 7 + 0.3
                _box(bm, 0, size=(0.055, 0.055, r * 0.90),
                     loc=(cx, yy + cos(a) * r * 0.47, cz + sin(a) * r * 0.47),
                     rot=(a - pi / 2, 0, 0))
            _cyl(bm, 0, 0.11, 0.17, (cx, yy, cz), rot=(0, pi / 2, 0),
                 segments=10)
        for yy in (-bl * 0.32, bl * 0.32):
            _cyl(bm, 2, 0.05, bw + 0.46, (0, yy, 0.40 if yy < 0 else 0.54),
                 rot=(0, pi / 2, 0), segments=8)
    _prism_beam(bm, 0, 1.70, 0.095, 0.095, loc=(0, -bl * 0.5, bz - 0.14),
                rot=(radians(97), 0, 0), chamfer=0.010, rings=4, bow=0.02,
                rng=rng, chips=2, chip_mat=1, base=True)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def crates(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    specs = [(0.66, -0.34, -0.20, 0.0, 8, True), (0.58, 0.36, -0.10, -17, 9, True),
             (0.52, 0.02, 0.44, 12, 10, False), (0.46, -0.30, 0.38, 26, 11, True)]
    for i, (s, x, y, r, sd, lid) in enumerate(specs):
        c = dp.create_crate_detailed(f"Mk_Crates_{i}", mats=mats, seed=3441 + sd,
                                     size=s, lid=lid, stencil=(i % 2 == 0))
        z = 0.0 if i < 2 else 0.60
        c.location = (ox + x, oy + y, oz + z)
        c.rotation_euler = (0, 0, radians(r))
        _link(c, col)


def barrels(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    for i, (x, y, r, h, tip, op, ms) in enumerate([
            (-0.36, -0.10, 0.34, 0.86, False, False, True),
            (0.34, -0.22, 0.32, 0.82, False, True, False),
            (0.10, 0.48, 0.33, 0.84, False, False, True),
            (0.86, 0.30, 0.31, 0.80, True, False, True)]):
        b = dp.create_barrel_detailed(f"Mk_Barrels_{i}", mats=mats,
                                      seed=3451 + i * 7, radius=r, height=h,
                                      open_top=op, tilted=tip, mossy=ms)
        b.location = (ox + x, oy + y, oz)
        _link(b, col)


def sacks(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Mk_Sacks", [mats["M_Linen"], mats["M_Rope"],
                                        mats["M_Wool_Cream"], mats["M_Straw"],
                                        mats["M_Timber_Aged"]])
    rng = random.Random(3461)
    _plank_run(bm, 4, 4, rng, 1.3, 0.95, 0.06, 4, (0, 0, 0.0), axis="x",
               nails=None)
    for i, (x, y, s) in enumerate([(-0.32, -0.16, 0.42), (0.26, -0.22, 0.38),
                                   (0.02, 0.24, 0.40), (0.40, 0.26, 0.34)]):
        _sack(bm, rng.choice([0, 2]), 1, rng, (x, y, 0.06), s=s)
    for _ in range(14):
        _blob(bm, 3, (rng.uniform(-0.6, 0.6), rng.uniform(-0.5, 0.5),
                      rng.uniform(0.06, 0.10)),
              (0.035, 0.03, 0.02), rot=(0, 0, rng.uniform(0, pi)))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def signpost(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Mk_Signpost", [mats["M_Timber_Aged"],
                                           mats["M_Timber_Chip"],
                                           mats["M_Iron_Aged"],
                                           mats["M_Sign_Paint"],
                                           mats["M_Moss"],
                                           mats["M_Weed_Green"],
                                           mats["M_Stone_Block_B"]])
    rng = random.Random(3471)
    for k in range(6):
        a = 2 * pi * k / 6
        _blob(bm, 6, (cos(a) * 0.19, sin(a) * 0.19, 0.045),
              (0.15, 0.13, 0.09), rot=(0, 0, rng.uniform(0, pi)))
    _prism_beam(bm, 0, 2.35, 0.135, 0.135, loc=(0, 0, 0.04),
                rot=(radians(2.5), 0, 0), chamfer=0.014, rings=5, bow=0.022,
                rng=rng, chips=4, chip_mat=1, base=True)
    _blob(bm, 0, (0, 0, 2.42), (0.10, 0.10, 0.11))
    for i, (zz, ang, L) in enumerate([(2.05, 0.0, 0.85), (1.72, 2.4, 0.72),
                                      (1.40, 4.1, 0.78)]):
        dx, dy = cos(ang), sin(ang)
        _box(bm, 0, size=(L, 0.055, 0.19),
             loc=(dx * (L * 0.5 + 0.09), dy * (L * 0.5 + 0.09), zz),
             rot=(0, radians(rng.uniform(-4, 4)), ang))
        _box(bm, 3, size=(L * 0.72, 0.016, 0.075),
             loc=(dx * (L * 0.52 + 0.09), dy * (L * 0.52 + 0.09), zz),
             rot=(0, 0, ang))
        for t in (0.0,):
            _nail_head(bm, 2, (dx * 0.12, dy * 0.12, zz), radius=0.020)
    _moss_run(bm, 4, (-0.10, -0.10, 0.06), (0.10, 0.10, 0.06), 4, 0.06, rng,
              skip=0.3)
    for _ in range(5):
        _weed_tuft(bm, 5, (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0.01),
                   rng.uniform(0.10, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def notice_board(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Mk_Notice", [mats["M_Timber_Aged"],
                                         mats["M_Timber_Chip"],
                                         mats["M_Iron_Aged"], mats["M_Paper"],
                                         mats["M_Tile_B"], mats["M_Tile_Aged"],
                                         mats["M_Moss"], mats["M_Sign_Paint"]])
    rng = random.Random(3481)
    w, h, z0 = 1.45, 1.05, 0.95
    for sgn in (-1, 1):
        _prism_beam(bm, 0, z0 + h + 0.12, 0.125, 0.125,
                    loc=(sgn * (w * 0.5 - 0.05), 0, 0),
                    rot=(radians(rng.uniform(-2, 2)), 0, 0), chamfer=0.012,
                    rings=4, bow=0.014, rng=rng, chips=3, chip_mat=1, base=True)
        _moss_clump(bm, 6, (sgn * (w * 0.5 - 0.05), -0.10, 0.05),
                    rng.uniform(0.05, 0.09), rng)
    # Boards run vertically on the face
    for i in range(6):
        x = -w * 0.5 + 0.09 + i * ((w - 0.18) / 5.0)
        _prism_beam(bm, 0, h, ((w - 0.18) / 5.0) - 0.012, 0.05,
                    loc=(x, -0.045, z0), chamfer=0.007, rings=3, bow=0.005,
                    rng=rng, chips=1, chip_mat=1, base=True)
    for zz in (z0 + 0.10, z0 + h - 0.10):
        _box(bm, 0, size=(w - 0.10, 0.045, 0.075), loc=(0, 0.02, zz))
    # Pinned notices, none of them straight
    for i in range(5):
        _box(bm, 3, size=(rng.uniform(0.20, 0.30), 0.012,
                          rng.uniform(0.22, 0.32)),
             loc=(rng.uniform(-w * 0.34, w * 0.34), -0.075,
                  z0 + rng.uniform(0.22, h - 0.20)),
             rot=(0, radians(rng.uniform(-9, 9)), 0))
        _nail_head(bm, 2, (rng.uniform(-w * 0.3, w * 0.3), -0.085,
                           z0 + rng.uniform(0.3, h - 0.25)), radius=0.016)
    # Little shingled hood
    for i in range(7):
        x = -w * 0.5 + (i + 0.5) * (w / 7.0)
        _box(bm, rng.choice([4, 4, 5]), size=(w / 7.0 - 0.012, 0.42, 0.045),
             loc=(x, -0.11, z0 + h + 0.16), rot=(radians(28), 0, 0))
    _box(bm, 0, size=(w + 0.06, 0.05, 0.07), loc=(0, -0.26, z0 + h + 0.06))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


# =============================================================================
# 6. DECORATIONS & SMALL PROPS
# =============================================================================

def street_lamp(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Dc_StreetLamp", [mats["M_Iron_Aged"],
                                             mats["M_Stone_Block_B"],
                                             mats["M_Stone_Block_C"],
                                             mats["M_Moss"],
                                             mats["M_Weed_Green"]])
    rng = random.Random(3501)
    for c in range(3):
        _box(bm, rng.choice([1, 2]), size=(0.36 - c * 0.04, 0.36 - c * 0.04, 0.16),
             loc=(0, 0, c * 0.16), rot=(0, 0, rng.uniform(-0.03, 0.03)),
             base=True)
    _cyl(bm, 0, 0.065, 2.55, (0, 0, 0.46), segments=10, radius2=0.048,
         base=True)
    for zz in (0.62, 1.55, 2.45):
        _cyl(bm, 0, 0.085, 0.07, (0, 0, zz), segments=10)
    for k in range(4):
        a = 2 * pi * k / 4
        _box(bm, 0, size=(0.022, 0.022, 0.30),
             loc=(cos(a) * 0.10, sin(a) * 0.10, 2.62), rot=(0.42, 0, a))
    _moss_clump(bm, 3, (0.16, -0.10, 0.06), 0.07, rng)
    for _ in range(4):
        _weed_tuft(bm, 4, (rng.uniform(-0.28, 0.28), rng.uniform(-0.28, 0.28),
                           0.01), rng.uniform(0.09, 0.17), rng, blades=4)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    lamp = dp.create_lantern_bracket("Dc_StreetLamp_Head", mats=mats,
                                     seed=3503, reach=0.0, lantern=True,
                                     lit=True)
    lamp.location = (ox, oy, oz + 3.28)
    _link(lamp, col)


def wall_lantern(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    b = dp.create_lantern_bracket("Dc_WallLantern", mats=mats, seed=3511,
                                  reach=0.46, lantern=True, lit=True)
    b.location = (ox, oy, oz + 1.55)
    _link(b, col)
    _link(dp.create_masonry_box("Dc_WallLantern_Wall", 1.15, 0.38, 2.2,
                                location=(ox, oy + 0.19, oz), mats=mats,
                                seed=3513, course_h=0.24,
                                block_len=(0.16, 0.44), shaded_faces=SHADED,
                                moss_amount=0.26, weeds=True), col)


def hanging_lantern(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Dc_HangLantern_Arm", [mats["M_Timber_Aged"],
                                                  mats["M_Timber_Chip"],
                                                  mats["M_Iron_Aged"],
                                                  mats["M_Moss"]])
    rng = random.Random(3521)
    _prism_beam(bm, 0, 2.5, 0.135, 0.135, loc=(0, 0, 0), chamfer=0.014,
                rings=5, bow=0.02, rng=rng, chips=4, chip_mat=1, base=True)
    _prism_beam(bm, 0, 0.95, 0.085, 0.085, loc=(0, 0, 2.42),
                rot=(0, radians(-96), 0), chamfer=0.010, rings=3, rng=rng,
                chips=2, chip_mat=1, base=True)
    _box(bm, 2, size=(0.026, 0.026, 0.55), loc=(-0.38, 0, 2.05),
         rot=(0, radians(-40), 0))
    _moss_clump(bm, 3, (0.0, -0.10, 0.05), 0.08, rng)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    lamp = dp.create_lantern_bracket("Dc_HangLantern", mats=mats, seed=3523,
                                     reach=0.10, lantern=True, lit=True)
    lamp.location = (ox - 0.80, oy, oz + 2.34)
    lamp.rotation_euler = (0, 0, radians(180))
    _link(lamp, col)


def well(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Dc_Well", _sm(mats, "fieldstone") +
                           [mats["M_Moss"], mats["M_Weed_Green"],
                            mats["M_Timber_Aged"], mats["M_Iron_Aged"],
                            mats["M_Water_Deep"], mats["M_Rope"],
                            mats["M_Timber_Chip"]])
    rng = random.Random(3531)
    r = 0.85
    _cyl(bm, 8, r - 0.14, 0.05, (0, 0, 0.62), segments=16)
    for c in range(4):
        z = c * 0.22
        n = max(10, int(2 * pi * r / 0.34))
        for k in range(n):
            a = 2 * pi * k / n + (0.15 if c % 2 else 0.0)
            _box(bm, rng.choice([1, 2, 3]),
                 size=((2 * pi * r / n) * 0.92, 0.28, 0.20),
                 loc=(cos(a) * r, sin(a) * r, z),
                 rot=(rng.uniform(-0.02, 0.02), 0, a + pi * 0.5), base=True)
            if rng.random() < 0.22:
                _moss_clump(bm, 4, (cos(a) * (r + 0.13), sin(a) * (r + 0.13),
                                    z + 0.18), rng.uniform(0.05, 0.10), rng)
    n = max(12, int(2 * pi * r / 0.28))
    for k in range(n):
        a = 2 * pi * k / n
        _box(bm, rng.choice([1, 3]), size=((2 * pi * r / n) * 0.94, 0.40, 0.13),
             loc=(cos(a) * r, sin(a) * r, 0.88), rot=(0, 0, a + pi * 0.5),
             base=True)
    for sgn in (-1, 1):
        _prism_beam(bm, 6, 1.42, 0.11, 0.11, loc=(sgn * (r - 0.07), 0, 0.90),
                    rot=(0, radians(sgn * -7), 0), chamfer=0.012, rings=4,
                    bow=0.012, rng=rng, chips=3, chip_mat=10, base=True)
    _cyl(bm, 6, 0.10, 1.35, (0, 0, 2.20), rot=(0, pi / 2, 0), segments=10)
    _cyl(bm, 7, 0.05, 1.55, (0, 0, 2.20), rot=(0, pi / 2, 0), segments=8)
    _box(bm, 7, size=(0.10, 0.28, 0.05), loc=(0.72, 0.13, 2.20))
    _box(bm, 7, size=(0.05, 0.05, 0.22), loc=(0.72, 0.26, 2.10))
    _rope(bm, 9, rng, (0.02, 0.0, 2.14), (0.02, 0.0, 1.35), sag=0.0, segs=4,
          r=0.020)
    for i in range(4):
        _box(bm, 6, size=(0.30, 0.09, 0.09), loc=(0.02, 0, 1.24 - i * 0.0),
             rot=(0, 0, i * 0.4))
    _cyl(bm, 7, 0.20, 0.05, (0.02, 0, 1.06), segments=12)
    for i in range(4):
        _box(bm, 6, size=(0.36, 0.055, 0.30), loc=(0.02, 0, 1.22),
             rot=(0, 0, i * pi / 4))
    # Shingled roof over the shaft
    for sgn in (-1, 1):
        for rr in range(3):
            for cc in range(6):
                x = sgn * (0.16 + rr * 0.30)
                y = -0.78 + cc * 0.31
                _box(bm, rng.choice([1, 3]), size=(0.30, 0.30, 0.05),
                     loc=(x, y, 2.55 - rr * 0.20),
                     rot=(0, radians(sgn * 34), 0))
    _box(bm, 6, size=(0.14, 1.95, 0.10), loc=(0, 0, 2.62))
    for _ in range(7):
        _weed_tuft(bm, 5, (rng.uniform(-1.1, 1.1), rng.uniform(-1.1, 1.1), 0.01),
                   rng.uniform(0.10, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


def bench(mats, col, o=(0, 0, 0)):
    b = dp.create_bench_detailed("Dc_Bench", mats=mats, seed=3541, length=1.75,
                                 mossy=True)
    b.location = o
    _link(b, col)


def planter(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Dc_Planter", [mats["M_Fieldstone_A"],
                                          mats["M_Fieldstone_C"],
                                          mats["M_Mortar"], mats["M_Soil"],
                                          mats["M_Foliage"], mats["M_Flowers"],
                                          mats["M_Moss"], mats["M_Ivy_Leaf"]])
    rng = random.Random(3551)
    w, d, h = 1.25, 0.80, 0.52
    for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
        run = d * 0.5 if ax == 0 else w * 0.5
        for c in range(2):
            _rubble_course(bm, [0, 1], rng, run * 2, h * 0.5, 0.20, c * h * 0.5,
                           axis="y" if ax == 0 else "x",
                           loc=(sgn * w * 0.5 if ax == 0 else 0,
                                sgn * d * 0.5 if ax == 1 else 0, 0),
                           blocks=(0.16, 0.34))
    _box(bm, 3, size=(w - 0.28, d - 0.28, 0.12), loc=(0, 0, h - 0.04))
    _leaf_mass(bm, [4, 4, 7], rng, (0, 0, h + 0.20), w * 0.44, d * 0.40, 0.22, 110)
    for _ in range(16):
        _blob(bm, 5, (rng.uniform(-w * 0.38, w * 0.38),
                      rng.uniform(-d * 0.32, d * 0.32),
                      h + rng.uniform(0.10, 0.34)), (0.035, 0.035, 0.035))
    for _ in range(5):
        L = rng.uniform(0.14, 0.30)
        _box(bm, 4, size=(0.04, 0.04, L),
             loc=(rng.uniform(-w * 0.4, w * 0.4), -d * 0.5 - 0.03,
                  h - L * 0.4), rot=(rng.uniform(-0.25, 0.25), 0, 0))
    _moss_run(bm, 6, (-w * 0.5, -d * 0.5 - 0.02, 0.02),
              (w * 0.5, -d * 0.5 - 0.02, 0.02), 6, 0.06, rng, skip=0.4)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


def fountain(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Dc_Fountain", _sm(mats, "ashlar") +
                           [mats["M_Moss"], mats["M_Water_Deep"],
                            mats["M_Lichen"], mats["M_Weed_Green"]])
    rng = random.Random(3561)
    r = 1.35
    _cyl(bm, 5, r - 0.22, 0.06, (0, 0, 0.44), segments=20)
    for c in range(2):
        n = max(14, int(2 * pi * r / 0.34))
        for k in range(n):
            a = 2 * pi * k / n + (0.14 if c else 0.0)
            _box(bm, rng.choice([1, 2, 3]),
                 size=((2 * pi * r / n) * 0.92, 0.32, 0.24),
                 loc=(cos(a) * r, sin(a) * r, c * 0.24),
                 rot=(rng.uniform(-0.02, 0.02), 0, a + pi * 0.5), base=True)
            if rng.random() < 0.24:
                _moss_clump(bm, 4, (cos(a) * (r + 0.15), sin(a) * (r + 0.15),
                                    c * 0.24 + 0.2), rng.uniform(0.05, 0.10), rng)
            if rng.random() < 0.14:
                _lichen_patch(bm, 6, (cos(a) * (r + 0.16), sin(a) * (r + 0.16),
                                      c * 0.24), rng.uniform(0.05, 0.09), 2,
                              rng, plates=2)
    n = max(16, int(2 * pi * r / 0.30))
    for k in range(n):
        a = 2 * pi * k / n
        _box(bm, rng.choice([1, 3]), size=((2 * pi * r / n) * 0.94, 0.44, 0.13),
             loc=(cos(a) * r, sin(a) * r, 0.48), rot=(0, 0, a + pi * 0.5),
             base=True)
    # Central pier and dished bowls
    for c in range(3):
        _cyl(bm, rng.choice([1, 3]), 0.28 - c * 0.04, 0.24, (0, 0, 0.50 + c * 0.24),
             segments=14, base=True)
    _cyl(bm, 3, 0.62, 0.14, (0, 0, 1.22), segments=18, base=True)
    _cyl(bm, 5, 0.54, 0.05, (0, 0, 1.33), segments=18)
    _cyl(bm, 1, 0.17, 0.55, (0, 0, 1.36), segments=12, base=True)
    _cyl(bm, 3, 0.38, 0.11, (0, 0, 1.91), segments=14, base=True)
    _cyl(bm, 5, 0.31, 0.04, (0, 0, 1.99), segments=14)
    _blob(bm, 3, (0, 0, 2.12), (0.13, 0.13, 0.16))
    # Water falling from the upper bowl
    for k in range(6):
        a = 2 * pi * k / 6 + 0.3
        _box(bm, 5, size=(0.055, 0.055, 0.60),
             loc=(cos(a) * 0.34, sin(a) * 0.34, 1.64),
             rot=(0, radians(rng.uniform(-5, 5)), a))
    for _ in range(6):
        _weed_tuft(bm, 7, (rng.uniform(-1.6, 1.6), rng.uniform(-1.6, 1.6), 0.01),
                   rng.uniform(0.09, 0.18), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


def statue(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Dc_Statue", [mats["M_Mortar_Pale"],
                                         mats["M_Ashlar_A"],
                                         mats["M_Ashlar_C"],
                                         mats["M_Marble_Statue"],
                                         mats["M_Moss"], mats["M_Lichen"],
                                         mats["M_Weed_Green"]])
    rng = random.Random(3571)
    for c in range(3):
        s = 1.25 - c * 0.18
        n = 4
        for i in range(n):
            for j in range(n):
                if not (i in (0, n - 1) or j in (0, n - 1)):
                    continue
                x = -s * 0.5 + (i + 0.5) * (s / n)
                y = -s * 0.5 + (j + 0.5) * (s / n)
                _box(bm, rng.choice([1, 2]),
                     size=(s / n * 0.94, s / n * 0.94, 0.22),
                     loc=(x, y, c * 0.22), rot=(0, 0, rng.uniform(-0.02, 0.02)),
                     base=True)
    _box(bm, 2, size=(0.78, 0.78, 0.14), loc=(0, 0, 0.66), base=True)
    _box(bm, 1, size=(0.62, 0.62, 0.95), loc=(0, 0, 0.80), base=True)
    _box(bm, 2, size=(0.76, 0.76, 0.13), loc=(0, 0, 1.75), base=True)
    # Weathered figure - a silhouette, not a portrait
    _cyl(bm, 3, 0.22, 0.95, (0, 0, 1.88), segments=10, radius2=0.17, base=True)
    _blob(bm, 3, (0, 0, 2.98), (0.17, 0.17, 0.21))
    _box(bm, 3, size=(0.12, 0.12, 0.62), loc=(-0.27, 0.02, 2.30),
         rot=(0, radians(16), 0))
    _box(bm, 3, size=(0.12, 0.12, 0.70), loc=(0.27, -0.03, 2.28),
         rot=(0, radians(-34), 0))
    _box(bm, 3, size=(0.30, 0.10, 0.52), loc=(0.42, -0.05, 2.62),
         rot=(0, radians(-52), 0))
    _box(bm, 3, size=(0.52, 0.22, 0.42), loc=(0, 0.06, 2.20),
         rot=(radians(7), 0, 0))
    for _ in range(9):
        a = rng.uniform(0, 2 * pi)
        _moss_clump(bm, 4, (cos(a) * 0.34, sin(a) * 0.34,
                            rng.uniform(1.80, 2.90)),
                    rng.uniform(0.04, 0.085), rng, squash=0.45)
    for _ in range(7):
        a = rng.uniform(0, 2 * pi)
        _lichen_patch(bm, 5, (cos(a) * 0.30, sin(a) * 0.30,
                              rng.uniform(1.9, 2.9)), rng.uniform(0.05, 0.10),
                      2, rng, plates=3)
    _moss_run(bm, 4, (-0.62, -0.62, 0.03), (0.62, -0.62, 0.03), 6, 0.08, rng,
              skip=0.35)
    for _ in range(5):
        _weed_tuft(bm, 6, (rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), 0.01),
                   rng.uniform(0.10, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


def tree_small(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_TreeSmall", [mats["M_Bark"], mats["M_Bark"],
                                            mats["M_Leaf_Pine"],
                                            mats["M_Foliage"],
                                            mats["M_Leaf_Spring"],
                                            mats["M_Grass"],
                                            mats["M_Weed_Green"]])
    rng = random.Random(3581)
    _tree(bm, rng, 0, 1, [2, 3, 4], height=2.4, spread=0.95, branches=5,
          leaves=260, lean=0.05)
    for _ in range(9):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0.15, 0.55)
        _blob(bm, 5, (cos(a) * d, sin(a) * d, 0.03), (0.17, 0.16, 0.07),
              rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(7):
        a = rng.uniform(0, 2 * pi)
        _weed_tuft(bm, 6, (cos(a) * rng.uniform(0.2, 0.6),
                           sin(a) * rng.uniform(0.2, 0.6), 0.02),
                   rng.uniform(0.10, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = o
    _link(ob, col)


def tree_large(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_TreeLarge", [mats["M_Bark"], mats["M_Bark"],
                                            mats["M_Leaf_Spring"],
                                            mats["M_Foliage"],
                                            mats["M_Leaf_Pine"],
                                            mats["M_Grass"],
                                            mats["M_Weed_Green"],
                                            mats["M_Moss"]])
    rng = random.Random(3583)
    _tree(bm, rng, 0, 1, [2, 3, 4], height=3.9, spread=1.75, branches=8,
          leaves=620, lean=-0.07)
    for k in range(7):
        a = 2 * pi * k / 7
        _blob(bm, 1, (cos(a) * 0.30, sin(a) * 0.30, 0.09),
              (0.22, 0.17, 0.18), rot=(0, 0, a))
        _moss_clump(bm, 7, (cos(a) * 0.30, sin(a) * 0.30, 0.16),
                    rng.uniform(0.05, 0.10), rng)
    for _ in range(12):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0.2, 0.9)
        _blob(bm, 5, (cos(a) * d, sin(a) * d, 0.03), (0.19, 0.18, 0.08),
              rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(9):
        a = rng.uniform(0, 2 * pi)
        _weed_tuft(bm, 6, (cos(a) * rng.uniform(0.3, 0.95),
                           sin(a) * rng.uniform(0.3, 0.95), 0.02),
                   rng.uniform(0.11, 0.22), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = o
    _link(ob, col)


def bush(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_Bush", [mats["M_Hedge_Green"],
                                       mats["M_Foliage"], mats["M_Ivy_Leaf"],
                                       mats["M_Ivy_Stem"], mats["M_Flowers"],
                                       mats["M_Soil"], mats["M_Weed_Green"]])
    rng = random.Random(3591)
    _blob(bm, 5, (0, 0, 0.04), (0.55, 0.50, 0.08))
    for k in range(6):
        a = 2 * pi * k / 6
        _box(bm, 3, size=(0.035, 0.035, 0.42),
             loc=(cos(a) * 0.09, sin(a) * 0.09, 0.02),
             rot=(radians(rng.uniform(6, 20)), 0, a), base=True)
    for i in range(3):
        c = (rng.uniform(-0.18, 0.18), rng.uniform(-0.16, 0.16),
             0.34 + rng.uniform(-0.06, 0.12))
        _leaf_mass(bm, [0, 0, 1, 2], rng, c, 0.40, 0.38, 0.30, 130,
                   size=(0.10, 0.19))
    for _ in range(11):
        _blob(bm, 4, (rng.uniform(-0.30, 0.30), rng.uniform(-0.28, 0.28),
                      rng.uniform(0.25, 0.62)), (0.034, 0.034, 0.034))
    for _ in range(5):
        _weed_tuft(bm, 6, (rng.uniform(-0.5, 0.5), rng.uniform(-0.45, 0.45),
                           0.02), rng.uniform(0.09, 0.17), rng, blades=4)
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = o
    _link(ob, col)


def flower_box(mats, col, o=(0, 0, 0)):
    b = dp.create_flower_box_standalone_detailed("Dc_FlowerBox", mats=mats,
                                                 seed=3601, length=1.45)
    b.location = o
    _link(b, col)


# =============================================================================
# 7. DOCKS & WATERFRONT
# =============================================================================

def _piles(bm, tim, chip, rope, rng, positions, height, r=0.13):
    for (x, y) in positions:
        _prism_beam(bm, tim, height * rng.uniform(0.95, 1.06), r, r,
                    loc=(x, y, 0.0),
                    rot=(radians(rng.uniform(-3, 3)),
                         radians(rng.uniform(-3, 3)), 0),
                    chamfer=0.012, rings=4, bow=0.018, rng=rng, chips=3,
                    chip_mat=chip, base=True)


def dock_post(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Dk_Post", [mats["M_Timber_Aged"],
                                       mats["M_Timber_Chip"], mats["M_Rope"],
                                       mats["M_Moss"], mats["M_Iron_Aged"]])
    rng = random.Random(3701)
    _prism_beam(bm, 0, 1.55, 0.26, 0.26, loc=(0, 0, 0),
                rot=(radians(2), radians(-2), 0), chamfer=0.018, rings=5,
                bow=0.02, rng=rng, chips=5, chip_mat=1, base=True)
    _cyl(bm, 0, 0.19, 0.12, (0, 0, 1.55), segments=10, radius2=0.155,
         base=True)
    _cyl(bm, 4, 0.20, 0.05, (0, 0, 1.44), segments=10)
    for i in range(7):
        _cyl(bm, 2, 0.20 - i * 0.004, 0.055, (0, 0, 0.62 + i * 0.055),
             segments=10)
    _rope(bm, 2, rng, (0.17, 0.05, 0.98), (0.95, 0.55, 0.30), sag=0.22,
          segs=8, r=0.026)
    for _ in range(6):
        a = rng.uniform(0, 2 * pi)
        _moss_clump(bm, 3, (cos(a) * 0.16, sin(a) * 0.16,
                            rng.uniform(0.03, 0.35)),
                    rng.uniform(0.05, 0.10), rng, squash=0.5)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = o
    _link(ob, col)


def dock_platform(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Dk_Platform", [mats["M_Timber_Aged"],
                                           mats["M_Timber_Chip"],
                                           mats["M_Iron_Aged"],
                                           mats["M_Moss"], mats["M_Rope"]])
    rng = random.Random(3711)
    w, d, h = 2.6, 2.6, 1.30
    _piles(bm, 0, 1, 4, rng, [(sx * (w * 0.5 - 0.16), sy * (d * 0.5 - 0.16))
                              for sx in (-1, 1) for sy in (-1, 1)] +
           [(0, sy * (d * 0.5 - 0.16)) for sy in (-1, 1)], h)
    for sgn in (-1, 1):
        _box(bm, 0, size=(w, 0.16, 0.17), loc=(0, sgn * (d * 0.5 - 0.16), h - 0.08))
    _box(bm, 0, size=(w, 0.14, 0.15), loc=(0, 0, h - 0.08))
    _plank_run(bm, 0, 1, rng, w, d, 0.10, int(d / 0.26), (0, 0, h), axis="x",
               sag=0.028, nails=2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _box(bm, 0, size=(0.20, 0.20, 0.30),
                 loc=(sx * (w * 0.5 - 0.14), sy * (d * 0.5 - 0.14), h + 0.10),
                 base=True)
    for _ in range(14):
        _moss_clump(bm, 3, (rng.uniform(-w * 0.45, w * 0.45),
                            rng.uniform(-d * 0.45, d * 0.45), h + 0.06),
                    rng.uniform(0.04, 0.085), rng, squash=0.26)
    for i in range(4):
        _cyl(bm, 4, 0.17 - i * 0.025, 0.05, (w * 0.28, -d * 0.30, h + 0.08 + i * 0.045),
             segments=10)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def pier(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Dk_Pier", [mats["M_Timber_Aged"],
                                       mats["M_Timber_Chip"],
                                       mats["M_Iron_Aged"], mats["M_Moss"],
                                       mats["M_Rope"]])
    rng = random.Random(3721)
    L, w, h = 4.2, 1.7, 1.25
    pos = []
    for i in range(5):
        y = -L * 0.5 + i * (L / 4.0)
        for sx in (-1, 1):
            pos.append((sx * (w * 0.5 - 0.14), y))
    _piles(bm, 0, 1, 4, rng, pos, h)
    for sx in (-1, 1):
        _box(bm, 0, size=(0.15, L, 0.16), loc=(sx * (w * 0.5 - 0.14), 0, h - 0.08))
    for i in range(int(L / 0.52)):
        y = -L * 0.5 + (i + 0.5) * 0.52
        _box(bm, 0, size=(w, 0.13, 0.13), loc=(0, y, h - 0.09))
    _plank_run(bm, 0, 1, rng, L, w, 0.09, int(w / 0.24), (0, 0, h), axis="y",
               sag=0.030, nails=2)
    for i in range(4):
        y = -L * 0.5 + 0.4 + i * (L * 0.8 / 3.0)
        for sx in (-1, 1):
            _prism_beam(bm, 0, 0.72, 0.09, 0.09,
                        loc=(sx * (w * 0.5 - 0.08), y, h + 0.02),
                        rot=(0, radians(sx * -4), 0), chamfer=0.010, rings=3,
                        rng=rng, chips=2, chip_mat=1, base=True)
    for sx in (-1, 1):
        _prism_beam(bm, 0, L - 0.4, 0.07, 0.07,
                    loc=(sx * (w * 0.5 - 0.08), -(L - 0.4) * 0.5, h + 0.62),
                    rot=(-pi / 2, 0, 0), chamfer=0.008, rings=4, bow=0.024,
                    rng=rng, chips=2, chip_mat=1, base=True)
    for _ in range(16):
        _moss_clump(bm, 3, (rng.uniform(-w * 0.45, w * 0.45),
                            rng.uniform(-L * 0.45, L * 0.45), h + 0.05),
                    rng.uniform(0.04, 0.08), rng, squash=0.26)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def _hull(bm, plank_mat, chip, rng, length, beam, depth, rows=4, floor_mat=None):
    """Clinker hull: strakes follow the waterline curve station by station.

    halfwidth(y) traces an ellipse in plan; each strake is laid as short
    segments yawed to the local tangent, so the planking wraps the hull
    instead of flying off it.
    """
    n_st = 18

    def halfw(y, wfac):
        t = min(1.0, abs(2.0 * y / length))
        return (beam * 0.5) * wfac * max(0.06, (1.0 - t * t) ** 0.5)

    for r in range(rows):
        t = r / max(1, rows - 1.0)
        z = depth * (0.10 + 0.92 * t)
        wfac = 0.52 + 0.48 * t
        sh = depth / rows * 1.45
        for k in range(n_st):
            y0 = -length * 0.5 + k * (length / n_st)
            y1 = y0 + length / n_st
            ym = (y0 + y1) * 0.5
            w0, w1 = halfw(y0, wfac), halfw(y1, wfac)
            wm = halfw(ym, wfac)
            yaw = atan2(w1 - w0, y1 - y0)
            seg = ((y1 - y0) ** 2 + (w1 - w0) ** 2) ** 0.5
            for sgn in (-1, 1):
                _box(bm, plank_mat, size=(0.075, seg * 1.10, sh),
                     loc=(sgn * wm, ym, z),
                     rot=(0, 0, -sgn * yaw))
        if r == 0 and floor_mat is not None:
            for k in range(n_st):
                ym = -length * 0.5 + (k + 0.5) * (length / n_st)
                _box(bm, floor_mat,
                     size=(halfw(ym, wfac) * 1.9, length / n_st * 1.05, 0.07),
                     loc=(0, ym, z - sh * 0.35))

    # Keel, stem and stern posts
    _box(bm, plank_mat, size=(0.12, length * 0.97, 0.13), loc=(0, 0, 0.03))
    for sgn in (-1, 1):
        _prism_beam(bm, plank_mat, depth * 1.55, 0.13, 0.13,
                    loc=(0, sgn * length * 0.49, 0.0),
                    rot=(radians(sgn * -20), 0, 0), chamfer=0.010, rings=3,
                    rng=rng, chips=2, chip_mat=chip, base=True)
    # Gunwale capping, following the same curve
    for k in range(n_st):
        y0 = -length * 0.5 + k * (length / n_st)
        y1 = y0 + length / n_st
        ym = (y0 + y1) * 0.5
        w0, w1 = halfw(y0, 1.0), halfw(y1, 1.0)
        yaw = atan2(w1 - w0, y1 - y0)
        seg = ((y1 - y0) ** 2 + (w1 - w0) ** 2) ** 0.5
        for sgn in (-1, 1):
            _box(bm, plank_mat, size=(0.11, seg * 1.10, 0.075),
                 loc=(sgn * halfw(ym, 1.0), ym, depth * 1.02),
                 rot=(0, 0, -sgn * yaw))


def small_boat(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Dk_SmallBoat", [mats["M_Wood_Planks"],
                                            mats["M_Timber_Aged"],
                                            mats["M_Timber_Chip"],
                                            mats["M_Rope"], mats["M_Moss"],
                                            mats["M_Linen"]])
    rng = random.Random(3731)
    L, B, D = 2.9, 1.15, 0.52
    _hull(bm, 0, 2, rng, L, B, D, rows=4, floor_mat=1)
    for i in range(3):
        y = -L * 0.26 + i * 0.52
        _plank_run(bm, 1, 2, rng, B * 0.92, 0.22, 0.055, 1, (0, y, D - 0.06),
                   axis="x", nails=None)
    for sgn in (-1, 1):
        _prism_beam(bm, 1, 1.55, 0.06, 0.055, loc=(sgn * B * 0.4, -0.2, D - 0.02),
                    rot=(radians(78), 0, radians(sgn * 28)), chamfer=0.007,
                    rings=3, rng=rng, chips=1, chip_mat=2, taper=0.7, base=True)
        _box(bm, 1, size=(0.20, 0.42, 0.028),
             loc=(sgn * (B * 0.4 + 0.42), -0.2 + 0.28, D + 0.28),
             rot=(0, 0, radians(sgn * 28)))
    for i in range(4):
        _cyl(bm, 3, 0.15 - i * 0.02, 0.045, (0, L * 0.34, D - 0.02 + i * 0.04),
             segments=10)
    _box(bm, 5, size=(B * 0.62, 0.55, 0.05), loc=(0, -L * 0.30, D - 0.05),
         rot=(0, 0, radians(12)))
    for _ in range(8):
        _moss_clump(bm, 4, (rng.uniform(-B * 0.5, B * 0.5),
                            rng.uniform(-L * 0.45, L * 0.45), 0.06),
                    rng.uniform(0.035, 0.07), rng, squash=0.35)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def sail_boat(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Dk_SailBoat", [mats["M_Wood_Planks"],
                                           mats["M_Timber_Aged"],
                                           mats["M_Timber_Chip"],
                                           mats["M_Rope"],
                                           mats["M_Canvas_Sail"],
                                           mats["M_Iron_Aged"],
                                           mats["M_Guild_Red"]])
    rng = random.Random(3741)
    L, B, D = 4.3, 1.65, 0.80
    _hull(bm, 0, 2, rng, L, B, D, rows=5, floor_mat=1)
    _plank_run(bm, 1, 2, rng, B * 0.9, L * 0.55, 0.05, 4, (0, L * 0.16, D - 0.05),
               axis="x", nails=5)
    for sgn in (-1, 1):
        _prism_beam(bm, 1, L * 0.92, 0.075, 0.07,
                    loc=(sgn * B * 0.46, -L * 0.46, D - 0.02),
                    rot=(-pi / 2, 0, 0), chamfer=0.008, rings=4, bow=0.02,
                    rng=rng, chips=2, chip_mat=2, base=True)
    # Mast, yard and a sail with real belly
    _prism_beam(bm, 1, 3.5, 0.11, 0.11, loc=(0, -L * 0.10, D - 0.10),
                rot=(radians(-3), 0, 0), chamfer=0.010, rings=5, bow=0.02,
                rng=rng, chips=3, chip_mat=2, base=True)
    _prism_beam(bm, 1, 2.05, 0.06, 0.06, loc=(-1.02, -L * 0.10, D + 2.72),
                rot=(0, pi / 2, 0), chamfer=0.008, rings=4, bow=0.03, rng=rng,
                base=True)
    rows = 8
    for r in range(rows):
        t = (r + 0.5) / rows
        z = D + 2.72 - t * 2.05
        wfac = 0.35 + 0.65 * t
        belly = 0.26 * sin(pi * t)
        n = 7
        for k in range(n):
            x = (-1.0 + 2.0 * (k + 0.5) / n) * 1.0 * wfac
            _box(bm, 4 if r % 4 != 1 else 6,
                 size=(2.0 * wfac / n * 1.05, 0.03, 2.05 / rows * 1.08),
                 loc=(x, -L * 0.10 + belly * (1.0 - abs(x) / max(0.05, wfac)),
                      z), rot=(0, 0, 0))
    _rope(bm, 3, rng, (-1.02, -L * 0.10, D + 2.72), (0, L * 0.42, D + 0.10),
          sag=0.10, segs=7, r=0.020)
    _rope(bm, 3, rng, (1.02, -L * 0.10, D + 2.72), (0, -L * 0.46, D + 0.10),
          sag=0.10, segs=7, r=0.020)
    _cyl(bm, 5, 0.22, 0.06, (0, -L * 0.42, D - 0.04), segments=10)
    for _ in range(9):
        _moss_clump(bm, 3, (rng.uniform(-B * 0.5, B * 0.5),
                            rng.uniform(-L * 0.45, L * 0.45), 0.07),
                    rng.uniform(0.04, 0.075), rng, squash=0.3)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def crane(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Dk_Crane", [mats["M_Timber_Aged"],
                                        mats["M_Timber_Chip"],
                                        mats["M_Iron_Aged"], mats["M_Rope"],
                                        mats["M_Moss"], mats["M_Wood_Planks"]])
    rng = random.Random(3751)
    _plank_run(bm, 0, 1, rng, 1.5, 1.5, 0.11, 5, (0, 0, 0.0), axis="x",
               nails=2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _prism_beam(bm, 0, 0.55, 0.13, 0.13, loc=(sx * 0.58, sy * 0.58, 0.10),
                        chamfer=0.012, rings=3, rng=rng, chips=2, chip_mat=1,
                        base=True)
    _prism_beam(bm, 0, 3.3, 0.21, 0.21, loc=(0, 0, 0.10),
                rot=(radians(1.5), 0, 0), chamfer=0.016, rings=5, bow=0.022,
                rng=rng, chips=4, chip_mat=1, base=True)
    for sgn in (-1, 1):
        _prism_beam(bm, 0, 1.75, 0.10, 0.10, loc=(sgn * 0.55, 0.0, 0.14),
                    rot=(0, radians(sgn * -22), 0), chamfer=0.010, rings=4,
                    rng=rng, chips=2, chip_mat=1, base=True)
    # Jib out over the water, with a stay back to the mast head
    _prism_beam(bm, 0, 2.45, 0.135, 0.135, loc=(0, 0.12, 3.24),
                rot=(radians(-66), 0, 0), chamfer=0.012, rings=4, bow=0.02,
                rng=rng, chips=3, chip_mat=1, base=True)
    _rope(bm, 3, rng, (0, 0.05, 3.40), (0, 2.22, 4.20), sag=0.06, segs=6,
          r=0.022)
    for i in range(3):
        _cyl(bm, 2, 0.14, 0.055, (0, 2.24 - i * 0.0, 4.18 - i * 0.0),
             rot=(pi / 2, 0, 0), segments=12)
    _rope(bm, 3, rng, (0, 2.24, 4.12), (0, 2.24, 2.05), sag=0.0, segs=4,
          r=0.020)
    _cyl(bm, 2, 0.12, 0.05, (0, 2.24, 1.98), segments=10)
    _box(bm, 2, size=(0.05, 0.05, 0.30), loc=(0, 2.24, 1.80))
    _cyl(bm, 2, 0.16, 0.04, (0, 2.24, 1.62), segments=10)
    # Treadwheel drum on the frame
    _cyl(bm, 0, 0.52, 0.42, (0, -0.18, 1.55), rot=(0, pi / 2, 0), segments=14)
    for k in range(10):
        a = 2 * pi * k / 10
        _box(bm, 0, size=(0.46, 0.10, 0.10),
             loc=(0, -0.18 + cos(a) * 0.52, 1.55 + sin(a) * 0.52),
             rot=(a, pi / 2, 0))
    for _ in range(7):
        _moss_clump(bm, 4, (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), 0.09),
                    rng.uniform(0.04, 0.085), rng, squash=0.3)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def net_stack(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Dk_NetStack", [mats["M_Rope"], mats["M_Linen"],
                                           mats["M_Timber_Aged"],
                                           mats["M_Timber_Chip"],
                                           mats["M_Iron_Aged"],
                                           mats["M_Moss"], mats["M_Foliage"]])
    rng = random.Random(3761)
    # Drying frame
    for sx in (-1, 1):
        _prism_beam(bm, 2, 1.35, 0.10, 0.10, loc=(sx * 0.85, 0.20, 0.0),
                    rot=(radians(rng.uniform(-6, 6)), 0, 0), chamfer=0.010,
                    rings=3, rng=rng, chips=2, chip_mat=3, base=True)
    _prism_beam(bm, 2, 1.85, 0.07, 0.07, loc=(-0.92, 0.20, 1.28),
                rot=(0, pi / 2, 0), chamfer=0.008, rings=4, bow=0.03, rng=rng,
                base=True)
    # Net: a mesh of sagging cords, not a blob
    for i in range(13):
        x = -0.82 + i * (1.64 / 12.0)
        _rope(bm, 0, rng, (x, 0.20, 1.26), (x * 0.72, -0.30, 0.10),
              sag=0.14 + 0.05 * sin(i * 0.9), segs=6, r=0.013)
    for j in range(5):
        t = (j + 1) / 6.0
        z = 1.26 - t * 1.10
        _rope(bm, 0, rng, (-0.85 + t * 0.20, 0.20 - t * 0.48, z),
              (0.85 - t * 0.20, 0.20 - t * 0.48, z), sag=0.10, segs=8, r=0.013)
    # Heaped spare net and floats on the ground
    for i in range(4):
        _blob(bm, 0, (rng.uniform(-0.6, 0.6), rng.uniform(-0.7, -0.25),
                      rng.uniform(0.06, 0.18)),
              (rng.uniform(0.22, 0.34), rng.uniform(0.18, 0.28), 0.14),
              rot=(0, 0, rng.uniform(0, pi)), subdiv=1)
    for i in range(7):
        _blob(bm, 1, (rng.uniform(-0.7, 0.7), rng.uniform(-0.75, -0.2),
                      rng.uniform(0.08, 0.26)), (0.075, 0.06, 0.06),
              rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(5):
        _moss_clump(bm, 5, (rng.uniform(-0.8, 0.8), rng.uniform(-0.6, 0.3), 0.02),
                    rng.uniform(0.04, 0.08), rng)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=1, angle=44.0)
    ob.location = o
    _link(ob, col)


def fish_barrels(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    for i, (x, y, op, tip) in enumerate([(-0.34, -0.12, True, False),
                                         (0.32, -0.20, False, False),
                                         (0.04, 0.44, True, False)]):
        b = dp.create_barrel_detailed(f"Dk_Fish_{i}", mats=mats,
                                      seed=3771 + i * 7, radius=0.33,
                                      height=0.80, open_top=op, tilted=tip,
                                      mossy=True)
        b.location = (ox + x, oy + y, oz)
        _link(b, col)
    obj, mesh, bm = _begin("Dk_Fish_Catch", [mats["M_Water"], mats["M_Linen"],
                                             mats["M_Rope"], mats["M_Straw"],
                                             mats["M_Timber_Aged"]])
    rng = random.Random(3773)
    for (bx, by) in [(-0.34, -0.12), (0.04, 0.44)]:
        for i in range(9):
            a = rng.uniform(0, 2 * pi)
            d = rng.uniform(0.0, 0.20)
            _blob(bm, 1, (bx + cos(a) * d, by + sin(a) * d,
                          0.74 + rng.uniform(0.0, 0.06)),
                  (0.075, 0.032, 0.030),
                  rot=(0, rng.uniform(-0.3, 0.3), rng.uniform(0, 2 * pi)))
    _plank_run(bm, 4, 4, rng, 1.05, 0.62, 0.05, 3, (0.90, 0.10, 0.0),
               axis="y", nails=None)
    for i in range(6):
        _blob(bm, 1, (0.90 + rng.uniform(-0.22, 0.22),
                      0.10 + rng.uniform(-0.22, 0.22), 0.08),
              (0.085, 0.034, 0.030),
              rot=(0, 0, rng.uniform(0, 2 * pi)))
    for i in range(4):
        _cyl(bm, 2, 0.16 - i * 0.022, 0.045, (-0.92, 0.42, 0.04 + i * 0.04),
             segments=10)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


# =============================================================================
# 8. MISCELLANEOUS
# =============================================================================

def clothesline(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Ms_Clothesline", [mats["M_Timber_Aged"],
                                              mats["M_Timber_Chip"],
                                              mats["M_Rope"],
                                              mats["M_Linen"],
                                              mats["M_Wool_Blue"],
                                              mats["M_Wool_Red"],
                                              mats["M_Moss"],
                                              mats["M_Weed_Green"]])
    rng = random.Random(3801)
    span = 3.0
    for sgn in (-1, 1):
        _prism_beam(bm, 0, 2.05, 0.12, 0.12, loc=(sgn * span * 0.5, 0, 0),
                    rot=(radians(rng.uniform(-4, 4)), 0, 0), chamfer=0.012,
                    rings=4, bow=0.016, rng=rng, chips=3, chip_mat=1, base=True)
        _box(bm, 0, size=(0.42, 0.07, 0.07), loc=(sgn * span * 0.5, 0, 1.96))
        _moss_clump(bm, 6, (sgn * span * 0.5, -0.10, 0.05), 0.07, rng)
    _rope(bm, 2, rng, (-span * 0.5, 0, 1.94), (span * 0.5, 0, 1.94), sag=0.20,
          segs=12, r=0.017)
    items = [(-1.10, 0.52, 0.66, 3), (-0.48, 0.44, 0.54, 4), (0.12, 0.58, 0.72, 3),
             (0.72, 0.40, 0.48, 5), (1.20, 0.50, 0.60, 3)]
    for i, (x, w, h, mi) in enumerate(items):
        sag = 0.20 * sin(pi * (x + span * 0.5) / span)
        top = 1.94 - sag
        rows = max(4, int(h / 0.14))
        for r in range(rows):
            t = (r + 0.5) / rows
            ww = w * (1.0 - 0.14 * t) * (1.0 + 0.05 * sin(t * 6))
            _box(bm, mi, size=(ww, 0.022, (h / rows) * 1.10),
                 loc=(x + 0.03 * sin(t * 4), 0.0, top - 0.04 - t * h),
                 rot=(0, 0, radians(rng.uniform(-2.5, 2.5))))
        for sgn in (-1, 1):
            _box(bm, 0, size=(0.028, 0.055, 0.10),
                 loc=(x + sgn * w * 0.40, 0.0, top + 0.01))
    for _ in range(5):
        _weed_tuft(bm, 7, (rng.uniform(-span * 0.5, span * 0.5),
                           rng.uniform(-0.15, 0.15), 0.01),
                   rng.uniform(0.10, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = o
    _link(ob, col)


def banners(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    _link(dp.create_masonry_box("Ms_Banners_Wall", 2.1, 0.42, 2.6, stone="granite",
                                location=(ox, oy + 0.21, oz), mats=mats,
                                seed=3811, course_h=0.26,
                                block_len=(0.18, 0.48), shaded_faces=SHADED,
                                moss_amount=0.22, weeds=True), col)
    for i, (x, colr, h) in enumerate([(-0.62, "red", 1.85), (0.0, "cream", 2.05),
                                      (0.62, "blue", 1.72)]):
        b = da.create_banner(f"Ms_Banner_{i}", width=0.52, height=h, mats=mats,
                             seed=3813 + i * 7, colour=colr)
        b.location = (ox + x, oy, oz + 2.35 - h)
        _link(b, col)


def flags(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Ms_Flags", [mats["M_Timber_Aged"],
                                        mats["M_Iron_Aged"],
                                        mats["M_Guild_Red"],
                                        mats["M_Guild_Blue"],
                                        mats["M_Gold_Brass"],
                                        mats["M_Timber_Chip"]])
    rng = random.Random(3821)
    for i, (x, lean, L, mi) in enumerate([(-0.45, 14, 2.15, 2),
                                          (0.30, -9, 2.55, 3)]):
        _prism_beam(bm, 0, L, 0.075, 0.075, loc=(x, 0, 0),
                    rot=(0, radians(lean), 0), chamfer=0.009, rings=4,
                    bow=0.014, rng=rng, chips=2, chip_mat=5, base=True)
        tipx = x + sin(radians(lean)) * L
        tipz = cos(radians(lean)) * L
        _blob(bm, 4, (tipx, 0, tipz + 0.06), (0.055, 0.055, 0.07))
        # Pennant streaming, tapering to a tail
        rows = 9
        for r in range(rows):
            t = (r + 0.5) / rows
            wv = 0.10 * sin(t * 5.2 + i)
            _box(bm, mi, size=(0.115, 0.022, 0.62 * (1.0 - 0.55 * t)),
                 loc=(tipx - 0.09 - t * 1.05, wv,
                      tipz - 0.30 - t * 0.22 + 0.05 * sin(t * 6)),
                 rot=(0, radians(6 * sin(t * 5)), radians(12 * sin(t * 4))))
    ob = _end(obj, mesh, bm, bevel=0.005, segments=1, angle=45.0)
    ob.location = o
    _link(ob, col)


def awning(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    a = da.create_striped_awning("Ms_Awning", width=2.5, depth=1.55, mats=mats,
                                 seed=3831, colour="blue", posts=False,
                                 height=2.30)
    a.location = (ox, oy, oz)
    _link(a, col)
    _link(dp.create_coated_box("Ms_Awning_Wall", 2.9, 0.95, 3.0,
                               location=(ox, oy + 0.48, oz + 1.50), mats=mats,
                               seed=3833, faces=("-Y", "+X", "+Y", "-X"),
                               coat=0.20, damage=2, moss_base=True), col)
    _link(_coping("Ms_Awning_Coping", mats, 3.02, 1.07, 4001,
                  (ox, oy + 0.48, oz + 3.00)), col)


def balcony(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Ms_Balcony", [mats["M_Timber_Aged"],
                                          mats["M_Timber_Chip"],
                                          mats["M_Iron_Aged"],
                                          mats["M_Foliage"],
                                          mats["M_Flowers"], mats["M_Moss"],
                                          mats["M_Linen"]])
    rng = random.Random(3841)
    w, d, z = 2.35, 1.05, 1.55
    for cx in _spread(w * 0.5 - 0.22, 4):
        for i in range(5):
            t = (i + 0.5) / 5.0
            proj = d * 0.82 * (t ** 1.6)
            _box(bm, 0, size=(0.10, proj + 0.08, 0.085),
                 loc=(cx, -(proj + 0.08) * 0.5, z - 0.55 + t * 0.52))
    _plank_run(bm, 0, 1, rng, w, d, 0.075, int(d / 0.24), (0, -d * 0.5, z),
               axis="x", sag=0.018, nails=2)
    for sgn in (-1, 1):
        _prism_beam(bm, 0, 1.0, 0.10, 0.10, loc=(sgn * (w * 0.5 - 0.06), -d + 0.06, z),
                    chamfer=0.010, rings=3, rng=rng, chips=2, chip_mat=1,
                    base=True)
    _prism_beam(bm, 0, w - 0.02, 0.09, 0.075, loc=(-(w - 0.02) * 0.5, -d + 0.06, z + 0.92),
                rot=(0, pi / 2, 0), chamfer=0.009, rings=4, bow=0.022, rng=rng,
                chips=2, chip_mat=1, base=True)
    n = 9
    for i in range(n):
        x = -w * 0.5 + 0.18 + i * ((w - 0.36) / (n - 1.0))
        zz = z + 0.06
        for (rr, hh) in [(0.042, 0.30), (0.058, 0.16), (0.040, 0.40)]:
            _cyl(bm, 0, rr, hh, (x, -d + 0.06, zz), segments=8, base=True)
            zz += hh
    # Lived-in: a planter and a cloth over the rail
    _box(bm, 0, size=(0.95, 0.24, 0.24), loc=(-0.55, -d + 0.20, z + 0.14))
    _leaf_mass(bm, [3, 3], rng, (-0.55, -d + 0.20, z + 0.34), 0.42, 0.11, 0.10, 45)
    for _ in range(7):
        _blob(bm, 4, (-0.55 + rng.uniform(-0.40, 0.40), -d + 0.14,
                      z + rng.uniform(0.30, 0.44)), (0.032, 0.032, 0.032))
    for r in range(6):
        t = (r + 0.5) / 6.0
        _box(bm, 6, size=(0.52, 0.022, 0.12),
             loc=(0.72, -d + 0.02 - 0.03 * sin(pi * t), z + 0.95 - t * 0.60),
             rot=(0, 0, radians(rng.uniform(-3, 3))))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    _link(dp.create_coated_box("Ms_Balcony_Wall", w + 0.7, 1.05, 3.4,
                               location=(ox, oy + 0.53, oz + 1.70), mats=mats,
                               seed=3843, faces=("-Y", "+X", "+Y", "-X"),
                               coat=0.20, damage=2, moss_base=True), col)
    _link(_coping("Ms_Balcony_Coping", mats, w + 0.82, 1.17, 4003,
                  (ox, oy + 0.53, oz + 3.40)), col)


def chimney_smoke(mats, col, o=(0, 0, 0)):
    c = dp.create_chimney_detailed("Ms_ChimneySmoke", height=2.9, width=0.98,
                                   depth=0.98, mats=mats, seed=3851,
                                   smoke=True, soot=True)
    c.location = o
    _link(c, col)


def bookshelf(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("In_Bookshelf", [mats["M_Timber_Aged"],
                                            mats["M_Timber_Chip"],
                                            mats["M_Book_Spines"],
                                            mats["M_Guild_Red"],
                                            mats["M_Guild_Blue"],
                                            mats["M_Paper"],
                                            mats["M_Iron_Aged"]])
    rng = random.Random(3861)
    w, d, h = 1.35, 0.42, 2.05
    for sgn in (-1, 1):
        _prism_beam(bm, 0, h, 0.085, d, loc=(sgn * (w * 0.5 - 0.04), 0, 0),
                    chamfer=0.010, rings=4, bow=0.008, rng=rng, chips=3,
                    chip_mat=1, base=True)
    _plank_run(bm, 0, 1, rng, w, d, 0.045, 2, (0, 0, h - 0.03), axis="x",
               nails=6)
    _box(bm, 0, size=(w, d, 0.05), loc=(0, 0.0, 0.10))
    # Back boards stand upright; a plank run can only lie flat
    for i in range(6):
        bx = -w * 0.5 + (i + 0.5) * (w / 6.0)
        _prism_beam(bm, 0, h - 0.06, (w / 6.0) - 0.012, 0.032,
                    loc=(bx, d * 0.5 - 0.02, 0.03), chamfer=0.006, rings=3,
                    bow=0.005, rng=rng, chips=1, chip_mat=1, base=True)
    shelves = [0.42, 0.84, 1.26, 1.66]
    for si, sz in enumerate(shelves):
        _box(bm, 0, size=(w - 0.10, d - 0.05, 0.045), loc=(0, 0, sz))
        x = -w * 0.5 + 0.12
        lean_next = False
        while x < w * 0.5 - 0.12:
            bw = rng.uniform(0.035, 0.075)
            bh = rng.uniform(0.22, 0.31)
            if x + bw > w * 0.5 - 0.12:
                break
            lean = radians(rng.uniform(10, 22)) if lean_next else 0.0
            lean_next = (rng.random() < 0.12)
            _box(bm, rng.choice([2, 2, 3, 4]),
                 size=(bw, d - 0.12, bh),
                 loc=(x + bw * 0.5, -0.02, sz + 0.025 + bh * 0.5),
                 rot=(0, lean, 0))
            x += bw + 0.006
        if rng.random() < 0.6:
            for k in range(rng.randint(2, 4)):
                _box(bm, rng.choice([2, 5]), size=(rng.uniform(0.16, 0.24),
                                                   d - 0.16, 0.042),
                     loc=(rng.uniform(-w * 0.3, w * 0.3), -0.02,
                          sz + 0.05 + k * 0.045),
                     rot=(0, 0, radians(rng.uniform(-8, 8))))
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = o
    _link(ob, col)


def table_set(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    table(mats, col, (ox, oy, oz))
    for i, (x, y, r) in enumerate([(-1.05, 0.10, 88), (1.05, -0.12, -94),
                                   (0.10, 0.95, 172)]):
        chair(mats, col, (ox + x, oy + y, oz), rot=r, seed=3871 + i * 7,
              name=f"Ms_TableSet_Chair{i}")


def hay_stack(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Ms_HayStack", [mats["M_Straw"], mats["M_Thatch_A"],
                                           mats["M_Thatch_Aged"],
                                           mats["M_Timber_Aged"],
                                           mats["M_Weed_Green"],
                                           mats["M_Timber_Chip"]])
    rng = random.Random(3881)
    r, h = 1.05, 1.55
    _cyl(bm, 3, 0.10, 2.35, (0, 0, 0), segments=6, base=True)
    rows = 11
    for i in range(rows):
        t = i / (rows - 1.0)
        rr = r * (1.0 - 0.72 * max(0.0, t - 0.45) / 0.55)
        z = t * h
        n = max(8, int(2 * pi * rr / 0.19))
        for k in range(n):
            a = 2 * pi * k / n + rng.uniform(-0.1, 0.1)
            _box(bm, rng.choice([0, 0, 1, 2]),
                 size=(0.20, 0.30, (h / rows) * 1.5),
                 loc=(cos(a) * rr, sin(a) * rr, z + (h / rows) * 0.5),
                 rot=(radians(rng.uniform(-14, 14)), radians(rng.uniform(4, 22)),
                      a + pi * 0.5))
    # Ragged crown and a few stalks pulled loose
    for _ in range(26):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0, 0.30)
        _box(bm, rng.choice([0, 1]), size=(0.05, 0.05, rng.uniform(0.20, 0.42)),
             loc=(cos(a) * d, sin(a) * d, h + 0.05),
             rot=(radians(rng.uniform(-40, 40)), radians(rng.uniform(-40, 40)),
                  a))
    for _ in range(18):
        a = rng.uniform(0, 2 * pi)
        d = r + rng.uniform(0.02, 0.55)
        _box(bm, 0, size=(0.04, 0.04, rng.uniform(0.12, 0.28)),
             loc=(cos(a) * d, sin(a) * d, 0.03),
             rot=(radians(rng.uniform(60, 100)), 0, a))
    for _ in range(5):
        _weed_tuft(bm, 4, (rng.uniform(-1.4, 1.4), rng.uniform(-1.4, 1.4), 0.01),
                   rng.uniform(0.10, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.005, segments=1, angle=44.0)
    ob.location = o
    _link(ob, col)


def wood_pile(mats, col, o=(0, 0, 0)):
    b = dp.create_firewood_stack_detailed("Ms_WoodPile", mats=mats, seed=3891,
                                          width=1.75, depth=0.62, height=1.05)
    b.location = o
    _link(b, col)


# =============================================================================
# 9. ENVIRONMENT / NATURE
# =============================================================================

def _rock_cluster(bm, stone_mats, moss_mat, weed_mat, rng, specs):
    """Angular fieldstones - faceted, never smooth pebbles."""
    for (x, y, s, sq) in specs:
        mi = rng.choice(stone_mats)
        _blob(bm, mi, (x, y, s * sq * 0.5),
              (s, s * rng.uniform(0.72, 1.05), s * sq),
              rot=(rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25),
                   rng.uniform(0, pi)), subdiv=1)
        # Broken faces cut into the lump
        for _ in range(rng.randint(2, 4)):
            a = rng.uniform(0, 2 * pi)
            _box(bm, mi, size=(s * rng.uniform(0.5, 0.9), s * 0.16,
                               s * rng.uniform(0.4, 0.8)),
                 loc=(x + cos(a) * s * 0.52, y + sin(a) * s * 0.52,
                      s * sq * rng.uniform(0.3, 0.8)),
                 rot=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3),
                      a + pi * 0.5))
        if rng.random() < 0.75:
            _moss_clump(bm, moss_mat, (x + rng.uniform(-s * 0.3, s * 0.3),
                                       y + rng.uniform(-s * 0.3, s * 0.3),
                                       s * sq * 0.95),
                        s * rng.uniform(0.22, 0.42), rng, squash=0.42)
        if rng.random() < 0.5:
            a = rng.uniform(0, 2 * pi)
            _weed_tuft(bm, weed_mat, (x + cos(a) * s * 0.8, y + sin(a) * s * 0.8,
                                      0.01), rng.uniform(0.09, 0.19), rng,
                       blades=5)


def rock_large(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_RockLarge", [mats["M_Granite_A"],
                                            mats["M_Granite_B"],
                                            mats["M_Granite_C"],
                                            mats["M_Moss"],
                                            mats["M_Weed_Green"],
                                            mats["M_Lichen"]])
    rng = random.Random(3901)
    _rock_cluster(bm, [0, 1, 2], 3, 4, rng,
                  [(0.0, 0.0, 0.92, 0.80), (0.78, -0.42, 0.42, 0.72),
                   (-0.62, 0.55, 0.34, 0.66)])
    for _ in range(6):
        a = rng.uniform(0, 2 * pi)
        _lichen_patch(bm, 5, (cos(a) * 0.62, sin(a) * 0.62,
                              rng.uniform(0.2, 0.8)), rng.uniform(0.07, 0.14),
                      2, rng, plates=3)
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = o
    _link(ob, col)


def rock_small(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_RockSmall", [mats["M_Granite_A"],
                                            mats["M_Granite_B"],
                                            mats["M_Granite_C"],
                                            mats["M_Moss"],
                                            mats["M_Weed_Green"],
                                            mats["M_Lichen"]])
    rng = random.Random(3903)
    _rock_cluster(bm, [0, 1, 2], 3, 4, rng,
                  [(0.0, 0.0, 0.34, 0.75), (0.34, 0.20, 0.22, 0.70),
                   (-0.28, 0.24, 0.17, 0.66), (0.14, -0.32, 0.13, 0.62)])
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = o
    _link(ob, col)


def boulder(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_Boulder", [mats["M_Granite_B"],
                                          mats["M_Granite_A"],
                                          mats["M_Granite_C"], mats["M_Moss"],
                                          mats["M_Weed_Green"],
                                          mats["M_Lichen"], mats["M_Soil"]])
    rng = random.Random(3905)
    _blob(bm, 6, (0, 0, 0.05), (1.10, 1.00, 0.10))
    _rock_cluster(bm, [0, 1, 2], 3, 4, rng, [(0.0, 0.0, 1.28, 0.86)])
    # Moss collars the shaded foot and creeps up the north face
    _moss_run(bm, 3, (-0.95, -0.45, 0.06), (0.95, -0.45, 0.06), 8, 0.11, rng,
              skip=0.25)
    for _ in range(9):
        a = rng.uniform(0, 2 * pi)
        _lichen_patch(bm, 5, (cos(a) * 0.9, sin(a) * 0.9, rng.uniform(0.3, 1.1)),
                      rng.uniform(0.08, 0.16), 2, rng, plates=3)
    for _ in range(6):
        a = rng.uniform(0, 2 * pi)
        _weed_tuft(bm, 4, (cos(a) * rng.uniform(0.9, 1.3),
                           sin(a) * rng.uniform(0.9, 1.3), 0.02),
                   rng.uniform(0.11, 0.22), rng, blades=6)
    ob = _end(obj, mesh, bm, bevel=0.010, segments=2)
    ob.location = o
    _link(ob, col)


def grass_patch(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_GrassPatch", [mats["M_Soil"], mats["M_Grass"],
                                             mats["M_Weed_Green"],
                                             mats["M_Foliage"],
                                             mats["M_Flowers"],
                                             mats["M_Granite_B"]])
    rng = random.Random(3911)
    r = 1.05
    _blob(bm, 0, (0, 0, 0.03), (r, r * 0.92, 0.08))
    for _ in range(38):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0, r * 0.95)
        _blob(bm, rng.choice([1, 1, 3]), (cos(a) * d, sin(a) * d, 0.05),
              (rng.uniform(0.12, 0.20), rng.uniform(0.12, 0.20),
               rng.uniform(0.05, 0.10)), rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(62):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0, r)
        _weed_tuft(bm, 2, (cos(a) * d, sin(a) * d, 0.04),
                   rng.uniform(0.11, 0.26), rng, blades=rng.randint(4, 8))
    for _ in range(11):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0, r * 0.9)
        _blob(bm, 4, (cos(a) * d, sin(a) * d, rng.uniform(0.12, 0.22)),
              (0.034, 0.034, 0.034))
    for _ in range(4):
        a = rng.uniform(0, 2 * pi)
        s = rng.uniform(0.07, 0.14)
        _blob(bm, 5, (cos(a) * rng.uniform(0.3, r), sin(a) * rng.uniform(0.3, r),
                      s * 0.35), (s, s * 0.8, s * 0.55),
              rot=(0, 0, rng.uniform(0, pi)))
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = o
    _link(ob, col)


def flowers(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_Flowers", [mats["M_Soil"], mats["M_Foliage"],
                                          mats["M_Weed_Green"],
                                          mats["M_Flowers"],
                                          mats["M_Flower_Petals"],
                                          mats["M_Ivy_Leaf"]])
    rng = random.Random(3913)
    r = 0.90
    _blob(bm, 0, (0, 0, 0.03), (r, r * 0.9, 0.07))
    for _ in range(24):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0, r * 0.9)
        _blob(bm, 1, (cos(a) * d, sin(a) * d, 0.05),
              (rng.uniform(0.11, 0.18), rng.uniform(0.11, 0.18), 0.06),
              rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(32):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0, r * 0.95)
        x, y = cos(a) * d, sin(a) * d
        hh = rng.uniform(0.22, 0.46)
        lean = rng.uniform(-0.22, 0.22)
        _box(bm, 2, size=(0.022, 0.022, hh), loc=(x, y, 0.03),
             rot=(lean, rng.uniform(-0.2, 0.2), 0), base=True)
        head = (x + lean * hh * 0.6, y, 0.03 + hh)
        for k in range(5):
            aa = 2 * pi * k / 5
            _ivy_leaf(bm, rng.choice([3, 4]),
                      (head[0] + cos(aa) * 0.035, head[1] + sin(aa) * 0.035,
                       head[2]), rng.uniform(0.045, 0.075),
                      (rng.uniform(0.8, 1.5), 0, aa), rng)
        _blob(bm, rng.choice([3, 4]), head, (0.028, 0.028, 0.028))
    for _ in range(14):
        a = rng.uniform(0, 2 * pi)
        _weed_tuft(bm, 2, (cos(a) * rng.uniform(0, r), sin(a) * rng.uniform(0, r),
                           0.04), rng.uniform(0.10, 0.20), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = o
    _link(ob, col)


def tree_group(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_TreeGroup", [mats["M_Bark"], mats["M_Bark"],
                                            mats["M_Leaf_Pine"],
                                            mats["M_Leaf_Spring"],
                                            mats["M_Foliage"],
                                            mats["M_Grass"],
                                            mats["M_Weed_Green"],
                                            mats["M_Moss"]])
    rng = random.Random(3915)
    for i, (x, y, h, sp, ln) in enumerate([(-1.25, 0.35, 3.40, 1.30, -0.08),
                                           (1.30, -0.55, 2.65, 1.05, 0.10),
                                           (0.05, 1.45, 2.10, 0.85, 0.04)]):
        _tree(bm, rng, 0, 1, [2, 3, 4], height=h, spread=sp, branches=6,
              leaves=int(300 * sp), lean=ln, origin=(x, y))
    for _ in range(16):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0.2, 1.5)
        _blob(bm, 5, (cos(a) * d, sin(a) * d, 0.03), (0.19, 0.18, 0.08),
              rot=(0, 0, rng.uniform(0, pi)))
    for _ in range(14):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0.2, 1.6)
        _weed_tuft(bm, 6, (cos(a) * d, sin(a) * d, 0.02),
                   rng.uniform(0.10, 0.22), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = o
    _link(ob, col)


def vines(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("Nt_Vines_Arm", [mats["M_Timber_Aged"],
                                            mats["M_Timber_Chip"],
                                            mats["M_Moss"]])
    rng = random.Random(3921)
    for sgn in (-1, 1):
        _prism_beam(bm, 0, 2.45, 0.115, 0.115, loc=(sgn * 1.05, 0, 0),
                    rot=(radians(rng.uniform(-3, 3)), 0, 0), chamfer=0.012,
                    rings=4, bow=0.016, rng=rng, chips=3, chip_mat=1, base=True)
        _moss_clump(bm, 2, (sgn * 1.05, -0.10, 0.05), 0.075, rng)
    _prism_beam(bm, 0, 2.35, 0.085, 0.085, loc=(-1.17, 0, 2.38),
                rot=(0, pi / 2, 0), chamfer=0.010, rings=4, bow=0.028, rng=rng,
                chips=2, chip_mat=1, base=False)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)
    # Growth hanging off the rail rather than climbing a wall
    obj, mesh, bm = _begin("Nt_Vines", [mats["M_Ivy_Stem"], mats["M_Ivy_Leaf"],
                                        mats["M_Moss"], mats["M_Flowers"]])
    rng = random.Random(3923)
    for i in range(9):
        x = -1.0 + i * 0.25 + rng.uniform(-0.05, 0.05)
        L = rng.uniform(0.75, 1.85)
        px, pz = x, 2.34
        segs = max(3, int(L / 0.24))
        for k in range(segs):
            nx = px + rng.uniform(-0.07, 0.07)
            nz = pz - L / segs
            _box(bm, 0, size=(0.022, 0.022, L / segs * 1.1),
                 loc=((px + nx) * 0.5, rng.uniform(-0.04, 0.04), (pz + nz) * 0.5))
            for _ in range(rng.randint(2, 5)):
                _ivy_leaf(bm, rng.choice([1, 1, 2]),
                          (nx + rng.uniform(-0.11, 0.11),
                           rng.uniform(-0.09, 0.05),
                           nz + rng.uniform(-0.08, 0.08)),
                          rng.uniform(0.075, 0.145),
                          (rng.uniform(-1.4, 1.4), rng.uniform(-1.4, 1.4),
                           rng.uniform(0, 2 * pi)), rng)
            if rng.random() < 0.07:
                _blob(bm, 3, (nx, -0.05, nz), (0.032, 0.032, 0.032))
            px, pz = nx, nz
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = (ox, oy, oz)
    _link(ob, col)


def ivy_wall(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    _link(dp.create_masonry_box("Nt_IvyWall", 2.4, 0.50, 2.45,
                                location=(ox, oy, oz), mats=mats, seed=3931,
                                course_h=0.26, block_len=(0.18, 0.50),
                                shaded_faces=SHADED, moss_amount=0.30,
                                lichen_amount=0.16, weeds=True,
                                weed_rows=3), col)
    for i, (x, h, w, sd, den) in enumerate([(-0.72, 2.35, 1.05, 3933, 1.45),
                                            (0.30, 2.05, 0.95, 3937, 1.30),
                                            (0.95, 1.55, 0.75, 3941, 1.15)]):
        iv = dp.create_ivy_climber(f"Nt_IvyWall_Ivy{i}", height=h, width=w,
                                   mats=mats, seed=sd, stems=3, density=den)
        iv.location = (ox + x, oy - 0.25, oz + 0.10)
        _link(iv, col)


def dead_tree(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_DeadTree", [mats["M_Bark"], mats["M_Timber_Aged"],
                                           mats["M_Moss"], mats["M_Weed_Green"],
                                           mats["M_Soil"], mats["M_Lichen"]])
    import mathutils
    rng = random.Random(3951)
    # Trunk: a continuous tapering stack that leans and kinks
    px, py, pz = 0.0, 0.0, 0.0
    segs = 9
    H = 3.3
    nodes = []
    lean_x, lean_y = 0.10, -0.04
    for i in range(segs):
        t = i / segs
        sh = H / segs
        nx = px + lean_x * sh + rng.uniform(-0.05, 0.05)
        ny = py + lean_y * sh + rng.uniform(-0.05, 0.05)
        nz = pz + sh
        r = 0.26 * (1.0 - t * 0.74) + 0.03
        d = mathutils.Vector((nx - px, ny - py, nz - pz))
        rt = mathutils.Vector((0, 0, 1)).rotation_difference(
            d.normalized()).to_euler()
        _cyl(bm, 0, r, d.length * 1.16,
             ((px + nx) * 0.5, (py + ny) * 0.5, (pz + nz) * 0.5),
             rot=(rt.x, rt.y, rt.z), segments=7, radius2=r * 0.88)
        if t > 0.22:
            nodes.append((nx, ny, nz, r))
        px, py, pz = nx, ny, nz
    # Limbs: each one bends through two or three joints, tapering to a snap
    for b in range(6):
        bx, by, bz_, br = nodes[rng.randrange(len(nodes))]
        ang = rng.uniform(0, 2 * pi)
        rise = rng.uniform(0.35, 0.95)
        r = br * rng.uniform(0.55, 0.78)
        for j in range(rng.randint(2, 3)):
            L = rng.uniform(0.55, 1.00) * (1.0 - j * 0.22)
            ang += rng.uniform(-0.55, 0.55)
            rise += rng.uniform(-0.18, 0.30)
            ex = bx + cos(ang) * L
            ey = by + sin(ang) * L
            ez = bz_ + rise * L
            d = mathutils.Vector((ex - bx, ey - by, ez - bz_))
            rt = mathutils.Vector((0, 0, 1)).rotation_difference(
                d.normalized()).to_euler()
            _cyl(bm, 0, r, d.length * 1.10,
                 ((bx + ex) * 0.5, (by + ey) * 0.5, (bz_ + ez) * 0.5),
                 rot=(rt.x, rt.y, rt.z), segments=6, radius2=r * 0.62)
            bx, by, bz_ = ex, ey, ez
            r *= 0.62
        # Splintered stub where the limb broke
        _cyl(bm, 1, r * 1.1, 0.16, (bx, by, bz_), segments=5, radius2=0.01)
    # Buttressed root flare
    for k in range(7):
        a = 2 * pi * k / 7 + rng.uniform(-0.2, 0.2)
        _blob(bm, 0, (cos(a) * 0.26, sin(a) * 0.26, 0.09),
              (0.20, 0.15, 0.16), rot=(0, 0, a))
        _moss_clump(bm, 2, (cos(a) * 0.28, sin(a) * 0.28, 0.17),
                    rng.uniform(0.05, 0.10), rng)
    for _ in range(8):
        a = rng.uniform(0, 2 * pi)
        _lichen_patch(bm, 5, (cos(a) * 0.19, sin(a) * 0.19,
                              rng.uniform(0.3, 2.2)), rng.uniform(0.06, 0.12),
                      2, rng, plates=3)
    for i in range(3):
        a = rng.uniform(0, 2 * pi)
        _prism_beam(bm, 0, rng.uniform(0.7, 1.3), 0.075, 0.075,
                    loc=(cos(a) * 0.55, sin(a) * 0.55, 0.07),
                    rot=(radians(86), 0, a), chamfer=0.008, rings=3,
                    bow=0.03, rng=rng, chips=3, chip_mat=1, taper=0.5,
                    base=True)
    for _ in range(9):
        a = rng.uniform(0, 2 * pi)
        _weed_tuft(bm, 3, (cos(a) * rng.uniform(0.25, 1.0),
                           sin(a) * rng.uniform(0.25, 1.0), 0.01),
                   rng.uniform(0.10, 0.22), rng, blades=5)
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = o
    _link(ob, col)


def ruins_pillar(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("Nt_RuinsPillar", _sm(mats, "ashlar") +
                           [mats["M_Moss"], mats["M_Lichen"],
                            mats["M_Weed_Green"]])
    rng = random.Random(3961)
    # Stepped base, drum shaft snapped off part-way, capital lying beside it
    for c in range(2):
        s = 1.05 - c * 0.18
        n = 3
        for i in range(n):
            for j in range(n):
                if not (i in (0, n - 1) or j in (0, n - 1)):
                    continue
                _box(bm, rng.choice([1, 2, 3]),
                     size=(s / n * 0.94, s / n * 0.94, 0.20),
                     loc=(-s * 0.5 + (i + 0.5) * (s / n),
                          -s * 0.5 + (j + 0.5) * (s / n), c * 0.20),
                     rot=(0, 0, rng.uniform(-0.02, 0.02)), base=True)
    drums = 5
    for i in range(drums):
        z = 0.40 + i * 0.36
        r = 0.34 - i * 0.012
        chip = (i == drums - 1)
        _cyl(bm, rng.choice([1, 2, 3]), r, 0.34, (rng.uniform(-0.02, 0.02),
                                                  rng.uniform(-0.02, 0.02), z),
             segments=12, base=True)
        # Fluting
        for k in range(10):
            a = 2 * pi * k / 10
            _box(bm, 0, size=(0.05, 0.07, 0.30),
                 loc=(cos(a) * r, sin(a) * r, z + 0.17),
                 rot=(0, 0, a + pi * 0.5))
        if chip:
            for k in range(4):
                a = rng.uniform(0, 2 * pi)
                _box(bm, rng.choice([1, 3]), size=(0.20, 0.16, 0.14),
                     loc=(cos(a) * r * 0.7, sin(a) * r * 0.7, z + 0.30),
                     rot=(rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), a))
        if rng.random() < 0.55:
            a = rng.uniform(0, 2 * pi)
            _moss_clump(bm, 4, (cos(a) * (r + 0.04), sin(a) * (r + 0.04),
                                z + rng.uniform(0.05, 0.3)),
                        rng.uniform(0.05, 0.11), rng, squash=0.45)
        if rng.random() < 0.4:
            a = rng.uniform(0, 2 * pi)
            _lichen_patch(bm, 5, (cos(a) * (r + 0.03), sin(a) * (r + 0.03), z),
                          rng.uniform(0.05, 0.10), 2, rng, plates=2)
    # Fallen capital and a scatter of drum fragments
    _box(bm, 3, size=(0.72, 0.72, 0.26), loc=(0.95, -0.55, 0.13),
         rot=(radians(12), radians(-8), radians(24)))
    _box(bm, 1, size=(0.56, 0.56, 0.14), loc=(0.95, -0.55, 0.32),
         rot=(radians(12), radians(-8), radians(24)))
    for i in range(4):
        a = rng.uniform(0, 2 * pi)
        d = rng.uniform(0.75, 1.5)
        _cyl(bm, rng.choice([1, 2, 3]), rng.uniform(0.16, 0.30),
             rng.uniform(0.20, 0.34), (cos(a) * d, sin(a) * d, 0.13),
             rot=(radians(88), 0, a), segments=10)
    for _ in range(9):
        a = rng.uniform(0, 2 * pi)
        _weed_tuft(bm, 6, (cos(a) * rng.uniform(0.5, 1.5),
                           sin(a) * rng.uniform(0.5, 1.5), 0.01),
                   rng.uniform(0.11, 0.24), rng, blades=6)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = o
    _link(ob, col)


# =============================================================================
# 10. INTERIOR / OPTIONAL
# =============================================================================

def bed(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("In_Bed", [mats["M_Timber_Aged"],
                                      mats["M_Timber_Chip"], mats["M_Linen"],
                                      mats["M_Wool_Red"], mats["M_Straw"],
                                      mats["M_Wool_Cream"]])
    rng = random.Random(3971)
    w, L, h = 1.30, 2.10, 0.52
    # Heavy corner posts, taller at the head
    for sx in (-1, 1):
        for sy in (-1, 1):
            _prism_beam(bm, 0, h + (1.15 if sy < 0 else 0.46), 0.155, 0.155,
                        loc=(sx * (w * 0.5 - 0.07), sy * (L * 0.5 - 0.07), 0),
                        rot=(radians(rng.uniform(-1.2, 1.2)), 0, 0),
                        chamfer=0.014, rings=4, bow=0.008, rng=rng, chips=3,
                        chip_mat=1, base=True)
            _blob(bm, 0, (sx * (w * 0.5 - 0.07), sy * (L * 0.5 - 0.07),
                          h + (1.15 if sy < 0 else 0.46)),
                  (0.10, 0.10, 0.11))
    # Side and end rails
    for sy in (-1, 1):
        _prism_beam(bm, 0, w - 0.06, 0.13, 0.17,
                    loc=(-(w - 0.06) * 0.5, sy * (L * 0.5 - 0.07), h - 0.14),
                    rot=(0, pi / 2, 0), chamfer=0.010, rings=3, rng=rng,
                    chips=2, chip_mat=1, base=True)
    for sx in (-1, 1):
        _prism_beam(bm, 0, L - 0.06, 0.13, 0.17,
                    loc=(sx * (w * 0.5 - 0.07), -(L - 0.06) * 0.5, h - 0.14),
                    rot=(-pi / 2, 0, 0), chamfer=0.010, rings=3, rng=rng,
                    chips=2, chip_mat=1, base=True)
    # Rope lattice under the mattress, visible at the rails
    for i in range(7):
        t = (i + 0.5) / 7.0
        _box(bm, 0, size=(w - 0.14, 0.035, 0.035),
             loc=(0, -L * 0.44 + t * L * 0.88, h - 0.15))
    # Headboard boards plus a top rail
    for i in range(5):
        _prism_beam(bm, 0, 1.02, w / 5.0 - 0.016, 0.065,
                    loc=(-w * 0.5 + (i + 0.5) * (w / 5.0), -L * 0.5 + 0.02, h),
                    chamfer=0.008, rings=3, bow=0.006, rng=rng, chips=2,
                    chip_mat=1, base=True)
    _prism_beam(bm, 0, w, 0.11, 0.10, loc=(-w * 0.5, -L * 0.5 + 0.02, h + 1.02),
                rot=(0, pi / 2, 0), chamfer=0.009, rings=3, rng=rng,
                base=True)
    # Straw mattress: a sagging body, not a slab
    for i in range(9):
        t = (i + 0.5) / 9.0
        sag = 0.035 * sin(pi * t)
        _blob(bm, 4, (0, -L * 0.42 + t * L * 0.84, h + 0.12 - sag),
              (w * 0.45, L * 0.065, 0.13), subdiv=1)
    # Sheet, then a blanket thrown back, then a pillow
    for i in range(9):
        t = i / 8.0
        _box(bm, 2, size=(w * 0.92, L * 0.10, 0.05),
             loc=(0, -L * 0.40 + t * L * 0.80,
                  h + 0.23 - 0.02 * sin(t * 4.5)),
             rot=(radians(rng.uniform(-2, 2)), 0, 0))
    for i in range(8):
        t = i / 7.0
        _box(bm, 3, size=(w * 0.98, L * 0.075, 0.075),
             loc=(rng.uniform(-0.02, 0.02), L * 0.02 + t * L * 0.42,
                  h + 0.28 + 0.05 * sin(t * 3.4)),
             rot=(radians(rng.uniform(-4, 4)), 0,
                  radians(rng.uniform(-3, 3))))
    # Turned-back corner of the blanket
    for i in range(4):
        _box(bm, 2, size=(w * 0.42, L * 0.06, 0.045),
             loc=(w * 0.20, L * 0.02 + i * 0.07, h + 0.34 + i * 0.015),
             rot=(radians(-18), 0, radians(rng.uniform(-6, 6))))
    _blob(bm, 5, (0, -L * 0.34, h + 0.30), (w * 0.36, 0.22, 0.12), subdiv=1)
    _blob(bm, 5, (rng.uniform(-0.1, 0.1), -L * 0.30, h + 0.34),
          (w * 0.26, 0.16, 0.09), subdiv=1)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def table(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("In_Table", [mats["M_Timber_Aged"],
                                        mats["M_Timber_Chip"],
                                        mats["M_Iron_Aged"],
                                        mats["M_Linen"], mats["M_Terracotta"]])
    rng = random.Random(3981)
    w, d, h = 1.75, 0.95, 0.78
    _plank_run(bm, 0, 1, rng, w, d, 0.075, 4, (0, 0, h), axis="x", sag=0.012,
               nails=2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _prism_beam(bm, 0, h, 0.11, 0.11,
                        loc=(sx * (w * 0.5 - 0.16), sy * (d * 0.5 - 0.13), 0),
                        rot=(radians(sy * -1.5), radians(sx * 1.5), 0),
                        chamfer=0.012, rings=3, bow=0.008, rng=rng, chips=2,
                        chip_mat=1, base=True)
    for sy in (-1, 1):
        _prism_beam(bm, 0, w - 0.32, 0.065, 0.065,
                    loc=(-(w - 0.32) * 0.5, sy * (d * 0.5 - 0.13), h * 0.32),
                    rot=(0, pi / 2, 0), chamfer=0.008, rings=3, rng=rng,
                    base=True)
    _prism_beam(bm, 0, d - 0.26, 0.055, 0.055, loc=(0, -(d - 0.26) * 0.5, h * 0.32),
                rot=(-pi / 2, 0, 0), chamfer=0.007, rings=3, rng=rng,
                base=True)
    # A table in use: cloth, a jug, a couple of bowls
    for i in range(5):
        t = i / 4.0
        _box(bm, 3, size=(0.62, d * 0.22, 0.02),
             loc=(-0.42, -d * 0.44 + t * d * 0.88, h + 0.05 - 0.01 * sin(t * 4)),
             rot=(0, 0, radians(rng.uniform(-2, 2))))
    _cyl(bm, 4, 0.10, 0.22, (0.38, -0.08, h + 0.04), segments=10, radius2=0.075,
         base=True)
    _cyl(bm, 4, 0.05, 0.05, (0.38, -0.08, h + 0.26), segments=8, base=True)
    _box(bm, 2, size=(0.05, 0.035, 0.13), loc=(0.48, -0.08, h + 0.16),
         rot=(0, radians(18), 0))
    for (bx, by) in ((0.58, 0.26), (0.20, 0.30)):
        _cyl(bm, 4, 0.115, 0.055, (bx, by, h + 0.05), segments=12)
        _cyl(bm, 4, 0.090, 0.02, (bx, by, h + 0.085), segments=12)
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def chair(mats, col, o=(0, 0, 0), rot=0.0, seed=3991, name="In_Chair"):
    obj, mesh, bm = _begin(name, [mats["M_Timber_Aged"], mats["M_Timber_Chip"],
                                  mats["M_Straw"], mats["M_Wool_Cream"]])
    rng = random.Random(seed)
    w, d, sh = 0.50, 0.50, 0.46
    for sx in (-1, 1):
        for sy in (-1, 1):
            back = (sy < 0)
            _prism_beam(bm, 0, sh + (0.60 if back else 0.0), 0.070, 0.070,
                        loc=(sx * (w * 0.5 - 0.05), sy * (d * 0.5 - 0.05), 0),
                        rot=(radians(sy * -2.5), radians(sx * 2.5), 0),
                        chamfer=0.009, rings=3, bow=0.007, rng=rng, chips=2,
                        chip_mat=1, base=True)
            if back:
                _blob(bm, 0, (sx * (w * 0.5 - 0.05), sy * (d * 0.5 - 0.05),
                              sh + 0.60), (0.050, 0.050, 0.055))
    # Seat frame rails, then a rush weave inside them
    for sy in (-1, 1):
        _prism_beam(bm, 0, w - 0.04, 0.055, 0.075,
                    loc=(-(w - 0.04) * 0.5, sy * (d * 0.5 - 0.05), sh - 0.05),
                    rot=(0, pi / 2, 0), chamfer=0.007, rings=3, rng=rng,
                    base=True)
    for sx in (-1, 1):
        _prism_beam(bm, 0, d - 0.04, 0.055, 0.075,
                    loc=(sx * (w * 0.5 - 0.05), -(d - 0.04) * 0.5, sh - 0.05),
                    rot=(-pi / 2, 0, 0), chamfer=0.007, rings=3, rng=rng,
                    base=True)
    for i in range(7):
        t = (i + 0.5) / 7.0
        _box(bm, 2, size=(w * 0.86, d / 7.0 * 0.82, 0.024),
             loc=(0, -d * 0.41 + t * d * 0.82, sh + 0.010),
             rot=(0, 0, radians(rng.uniform(-2, 2))))
        _box(bm, 2, size=(w / 7.0 * 0.82, d * 0.86, 0.022),
             loc=(-w * 0.41 + t * w * 0.82, 0, sh + 0.028),
             rot=(0, 0, radians(rng.uniform(-2, 2))))
    # Back: two horizontal splats between the rear posts
    for zz in (sh + 0.26, sh + 0.50):
        _prism_beam(bm, 0, w - 0.10, 0.075, 0.042,
                    loc=(-(w - 0.10) * 0.5, -d * 0.5 + 0.05, zz),
                    rot=(0, pi / 2, 0), chamfer=0.006, rings=3, bow=0.012,
                    rng=rng, chips=1, chip_mat=1, base=True)
    # Stretchers all round, one set lower than the other as a real chair has
    for sy, zz in ((-1, 0.17), (1, 0.13)):
        _prism_beam(bm, 0, w - 0.10, 0.042, 0.042,
                    loc=(-(w - 0.10) * 0.5, sy * (d * 0.5 - 0.05), zz),
                    rot=(0, pi / 2, 0), chamfer=0.005, rings=2, rng=rng,
                    base=True)
    for sx in (-1, 1):
        _prism_beam(bm, 0, d - 0.10, 0.042, 0.042,
                    loc=(sx * (w * 0.5 - 0.05), -(d - 0.10) * 0.5, 0.22),
                    rot=(-pi / 2, 0, 0), chamfer=0.005, rings=2, rng=rng,
                    base=True)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = o
    ob.rotation_euler = (0, 0, radians(rot))
    _link(ob, col)


def shelf(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("In_Shelf", [mats["M_Timber_Aged"],
                                        mats["M_Timber_Chip"],
                                        mats["M_Terracotta"],
                                        mats["M_Iron_Aged"], mats["M_Linen"],
                                        mats["M_Straw"], mats["M_Foliage"]])
    rng = random.Random(4001)
    w, d, h = 1.20, 0.34, 1.75
    for sgn in (-1, 1):
        _prism_beam(bm, 0, h, 0.075, d, loc=(sgn * (w * 0.5 - 0.04), 0, 0),
                    chamfer=0.010, rings=4, bow=0.008, rng=rng, chips=3,
                    chip_mat=1, base=True)
    for sz in (0.34, 0.78, 1.22, 1.64):
        _prism_beam(bm, 0, w, d - 0.03, 0.045, loc=(-w * 0.5, 0, sz),
                    rot=(0, pi / 2, 0), chamfer=0.008, rings=3, bow=0.010,
                    rng=rng, chips=2, chip_mat=1, base=True)
        for sgn in (-1, 1):
            _box(bm, 3, size=(0.05, 0.02, 0.14),
                 loc=(sgn * (w * 0.5 - 0.10), d * 0.42, sz - 0.07),
                 rot=(0.5, 0, 0))
        # Contents: pots, crocks, a bundle, none of them aligned
        x = -w * 0.5 + 0.14
        while x < w * 0.5 - 0.12:
            kind = rng.random()
            if kind < 0.55:
                rr = rng.uniform(0.055, 0.095)
                hh = rng.uniform(0.13, 0.24)
                _cyl(bm, 2, rr, hh, (x + rr, rng.uniform(-0.04, 0.04),
                                     sz + 0.023), segments=10,
                     radius2=rr * rng.uniform(0.7, 1.0), base=True)
                _cyl(bm, 2, rr * 1.12, 0.025,
                     (x + rr, 0, sz + 0.023 + hh), segments=10, base=True)
                x += rr * 2 + 0.035
            elif kind < 0.8:
                bw = rng.uniform(0.12, 0.2)
                _box(bm, rng.choice([4, 5]), size=(bw, d - 0.12, 0.13),
                     loc=(x + bw * 0.5, 0, sz + 0.09),
                     rot=(0, 0, radians(rng.uniform(-10, 10))))
                x += bw + 0.04
            else:
                _blob(bm, 6, (x + 0.09, 0, sz + 0.10), (0.09, 0.08, 0.07),
                      rot=(0, 0, rng.uniform(0, pi)))
                x += 0.22
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = o
    _link(ob, col)


def fireplace(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("In_Fireplace", [mats["M_Mortar"],
                                            mats["M_Stone_Block_A"],
                                            mats["M_Stone_Block_B"],
                                            mats["M_Stone_Block_C"],
                                            mats["M_Soot"],
                                            mats["M_Fire_Embers"],
                                            mats["M_Timber_Aged"],
                                            mats["M_Iron_Aged"],
                                            mats["M_Moss"]])
    rng = random.Random(4011)
    w, d, h = 2.15, 0.85, 2.45
    ow, oh = 1.35, 1.45
    # Jambs, breast and a heavy timber bressummer
    for sgn in (-1, 1):
        for c in range(int(oh / 0.26)):
            _rubble_course(bm, [1, 2, 3], rng, (w - ow) * 0.5, 0.26, d,
                           c * 0.26, axis="x",
                           loc=(sgn * (ow + (w - ow) * 0.5) * 0.5, 0, 0),
                           blocks=(0.20, 0.44))
    for c in range(int((h - oh - 0.22) / 0.26)):
        _rubble_course(bm, [1, 2, 3], rng, w, 0.26, d, oh + 0.22 + c * 0.26,
                       axis="x", loc=(0, 0, 0), blocks=(0.22, 0.52))
    _prism_beam(bm, 6, w + 0.08, 0.26, d * 0.72, loc=(-(w + 0.08) * 0.5, -d * 0.1, oh),
                rot=(0, pi / 2, 0), chamfer=0.020, rings=4, bow=0.010, rng=rng,
                chips=4, chip_mat=6, base=True)
    # Firebox: sooted back, cracked hearth slab, live embers, iron crane
    # Sooted firebox, set back so the opening reads as a cavity
    _box(bm, 4, size=(ow, d * 0.62, oh), loc=(0, d * 0.26, oh * 0.5))
    for sgn in (-1, 1):
        _box(bm, 4, size=(0.10, d * 0.60, oh),
             loc=(sgn * ow * 0.5, d * 0.06, oh * 0.5))
    _box(bm, 4, size=(ow, d * 0.60, 0.12), loc=(0, d * 0.06, oh - 0.05))
    for i in range(3):
        _box(bm, 3, size=(ow / 3.0 * 0.95, d + 0.22, 0.10),
             loc=(-ow * 0.5 + (i + 0.5) * (ow / 3.0), -d * 0.12, 0.05),
             rot=(0, 0, radians(rng.uniform(-1.5, 1.5))), base=True)
    for i in range(7):
        _prism_beam(bm, 6, rng.uniform(0.32, 0.55), 0.06, 0.06,
                    loc=(rng.uniform(-0.28, 0.28), rng.uniform(-0.08, 0.14), 0.11),
                    rot=(radians(rng.uniform(70, 100)), 0,
                         radians(rng.uniform(0, 180))),
                    chamfer=0.006, rings=2, rng=rng, base=True)
    for i in range(10):
        _blob(bm, 5, (rng.uniform(-0.30, 0.30), rng.uniform(-0.06, 0.16),
                      rng.uniform(0.11, 0.20)),
              (rng.uniform(0.04, 0.08),) * 3)
    _box(bm, 7, size=(0.045, 0.045, oh * 0.85), loc=(-ow * 0.44, d * 0.10, 0.12))
    _box(bm, 7, size=(0.55, 0.04, 0.04), loc=(-ow * 0.18, d * 0.10, oh * 0.80))
    for i in range(3):
        _cyl(bm, 7, 0.028, 0.018, (-ow * 0.02, d * 0.10, oh * 0.74 - i * 0.05),
             rot=(pi / 2 if i % 2 else 0, 0, 0), segments=8)
    _cyl(bm, 7, 0.155, 0.22, (-ow * 0.02, d * 0.10, oh * 0.48), segments=12,
         radius2=0.125)
    # Mantel clutter
    for i, (x, rr, hh) in enumerate([(-0.62, 0.055, 0.14), (-0.30, 0.045, 0.10),
                                     (0.55, 0.06, 0.16)]):
        _cyl(bm, 3, rr, hh, (x, -d * 0.16, oh + 0.30), segments=8, base=True)
    ob = _end(obj, mesh, bm, bevel=0.008, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


def rug(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("In_Rug", [mats["M_Carpet_Rug"], mats["M_Guild_Red"],
                                      mats["M_Guild_Blue"],
                                      mats["M_Wool_Cream"],
                                      mats["M_Gold_Brass"]])
    rng = random.Random(4021)
    w, L = 1.75, 2.45
    rows = 20
    for r in range(rows):
        t = (r + 0.5) / rows
        y = -L * 0.5 + t * L
        ripple = 0.012 * sin(t * 7.0)
        border = (t < 0.09 or t > 0.91)
        _box(bm, 1 if border else 0, size=(w, L / rows * 1.06, 0.020),
             loc=(0, y, 0.012 + ripple),
             rot=(radians(rng.uniform(-1.2, 1.2)), 0,
                  radians(rng.uniform(-0.6, 0.6))))
    for sgn in (-1, 1):
        _box(bm, 1, size=(w * 0.075, L, 0.022), loc=(sgn * w * 0.46, 0, 0.016))
    # Woven medallion and guard stripes
    for i in range(3):
        _box(bm, rng.choice([2, 3, 4]),
             size=(w * (0.50 - i * 0.12), L * (0.30 - i * 0.07), 0.024),
             loc=(0, 0, 0.018 + i * 0.001), rot=(0, 0, radians(45 if i == 1 else 0)))
    for sgn in (-1, 1):
        _box(bm, 3, size=(w * 0.80, L * 0.02, 0.023), loc=(0, sgn * L * 0.30, 0.018))
    # Fringe: individual threads, a few kinked
    for sgn in (-1, 1):
        for i in range(26):
            x = -w * 0.46 + i * (w * 0.92 / 25.0)
            _box(bm, 3, size=(0.012, 0.11, 0.012),
                 loc=(x, sgn * (L * 0.5 + 0.055), 0.010),
                 rot=(0, 0, radians(rng.uniform(-14, 14))))
    ob = _end(obj, mesh, bm, bevel=0.004, segments=1, angle=46.0)
    ob.location = o
    _link(ob, col)


def curtain(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    obj, mesh, bm = _begin("In_Curtain", [mats["M_Timber_Aged"],
                                          mats["M_Iron_Aged"],
                                          mats["M_Wool_Blue"],
                                          mats["M_Wool_Cream"],
                                          mats["M_Rope"],
                                          mats["M_Timber_Chip"]])
    rng = random.Random(4031)
    w, h = 1.70, 2.05
    _cyl(bm, 1, 0.032, w + 0.30, (0, 0, h), rot=(0, pi / 2, 0), segments=10)
    for sgn in (-1, 1):
        _blob(bm, 1, (sgn * (w * 0.5 + 0.15), 0, h), (0.055, 0.055, 0.055))
        _box(bm, 0, size=(0.07, 0.10, 0.16), loc=(sgn * (w * 0.5 + 0.09), 0.055, h))
    # Two drapes, gathered, each fold a separate slab
    for sgn in (-1, 1):
        folds = 7
        for i in range(folds):
            t = (i + 0.5) / folds
            x = sgn * (0.06 + t * (w * 0.5 - 0.06))
            bulge = 0.055 * sin(pi * t)
            tie = 0.30 * sin(pi * min(1.0, t * 1.15))
            _box(bm, 2 if i % 2 else 3,
                 size=((w * 0.5 - 0.06) / folds * 1.35, 0.055 + bulge,
                       h - 0.10),
                 loc=(x, -0.02 - bulge * 0.5, (h - 0.10) * 0.5 + 0.02),
                 rot=(0, radians(sgn * -3.5 * (1 - t)), 0))
            _cyl(bm, 1, 0.028, 0.015, (x, 0.0, h), rot=(pi / 2, 0, 0),
                 segments=8)
        # Tieback holding the drape in at mid height
        _rope(bm, 4, rng, (sgn * 0.08, -0.12, h * 0.46),
              (sgn * (w * 0.5 - 0.02), -0.02, h * 0.50), sag=0.05, segs=5,
              r=0.020)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = (ox, oy, oz)
    _link(ob, col)


def chest(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("In_Chest", [mats["M_Timber_Aged"],
                                        mats["M_Timber_Chip"],
                                        mats["M_Iron_Aged"],
                                        mats["M_Gold_Brass"],
                                        mats["M_Wool_Red"], mats["M_Linen"]])
    rng = random.Random(4041)
    w, d, h = 1.05, 0.62, 0.58
    for face in range(4):
        ang = face * pi / 2
        n = 4
        for i in range(n):
            z = (i + 0.5) * (h / n)
            ln = w if face % 2 == 0 else d
            _box(bm, 0, size=(ln - 0.02, 0.05, h / n - 0.014),
                 loc=(sin(ang) * (d * 0.5 if face % 2 == 0 else w * 0.5),
                      -cos(ang) * (d * 0.5 if face % 2 == 0 else w * 0.5), z),
                 rot=(radians(rng.uniform(-1.0, 1.0)), 0, ang))
    for sx in (-1, 1):
        for sy in (-1, 1):
            _prism_beam(bm, 0, h, 0.075, 0.075, loc=(sx * w * 0.5, sy * d * 0.5, 0),
                        chamfer=0.009, rings=3, rng=rng, chips=2, chip_mat=1,
                        base=True)
    # Domed, banded lid tipped open
    lid_ang = radians(26)
    rows = 6
    for i in range(rows):
        t = (i + 0.5) / rows
        a = pi * t
        _box(bm, 0, size=(w, (pi * d * 0.5 / rows) * 1.08, 0.055),
             loc=(0,
                  -cos(a) * d * 0.5 * cos(lid_ang) + sin(lid_ang) * (sin(a) * d * 0.42) - d * 0.0,
                  h + sin(a) * d * 0.42 * cos(lid_ang) + cos(lid_ang) * 0.02 +
                  cos(a) * d * 0.5 * sin(lid_ang)),
             rot=(a - pi * 0.5 + lid_ang, 0, 0))
    for sx in (-0.30, 0.30):
        _box(bm, 2, size=(0.075, d * 1.02, 0.025), loc=(sx * w, 0, h * 0.5))
        for zz in (h * 0.22, h * 0.76):
            _nail_head(bm, 2, (sx * w, -d * 0.5 - 0.02, zz), rot=(pi / 2, 0, 0),
                       radius=0.019)
    _box(bm, 2, size=(0.18, 0.05, 0.16), loc=(0, -d * 0.5 - 0.02, h - 0.10))
    _cyl(bm, 3, 0.05, 0.02, (0, -d * 0.5 - 0.05, h - 0.13), rot=(pi / 2, 0, 0),
         segments=10)
    for i in range(9):
        _blob(bm, rng.choice([3, 4, 5]),
              (rng.uniform(-0.32, 0.32), rng.uniform(-0.18, 0.18),
               h - 0.06 + rng.uniform(0, 0.05)),
              (rng.uniform(0.035, 0.07),) * 3, rot=(0, 0, rng.uniform(0, pi)))
    ob = _end(obj, mesh, bm, bevel=0.007, segments=2)
    ob.location = o
    _link(ob, col)


def ladder(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("In_Ladder", [mats["M_Timber_Aged"],
                                         mats["M_Timber_Chip"],
                                         mats["M_Iron_Aged"], mats["M_Moss"]])
    rng = random.Random(4051)
    L, w = 2.85, 0.52
    for sgn in (-1, 1):
        _prism_beam(bm, 0, L, 0.075, 0.055, loc=(sgn * w * 0.5, 0, 0),
                    rot=(radians(-11), 0, 0), chamfer=0.009, rings=5,
                    bow=0.020, rng=rng, chips=4, chip_mat=1, base=True)
    n = 9
    for i in range(n):
        t = (i + 0.5) / n
        z = t * L * cos(radians(11))
        y = t * L * sin(radians(11))
        _cyl(bm, 0, 0.028, w + 0.02, (0, y, z), rot=(0, pi / 2, 0), segments=8)
        if rng.random() < 0.25:
            _box(bm, 2, size=(0.05, 0.02, 0.02), loc=(w * 0.5, y, z))
    _moss_clump(bm, 3, (-w * 0.5, 0.02, 0.04), 0.06, rng)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = o
    _link(ob, col)


def stairs_interior(mats, col, o=(0, 0, 0)):
    obj, mesh, bm = _begin("In_Stairs", [mats["M_Timber_Aged"],
                                         mats["M_Timber_Chip"],
                                         mats["M_Iron_Aged"], mats["M_Moss"]])
    rng = random.Random(4061)
    w, h, run = 1.10, 2.10, 2.30
    n = 9
    sh, sd = h / n, run / n
    rake = atan2(h, run)

    # Stringers: a sawn zig-zag each side, cut to the rake
    for sgn in (-1, 1):
        _box(bm, 0, size=(0.075, (run ** 2 + h ** 2) ** 0.5 + 0.22, 0.30),
             loc=(sgn * (w * 0.5 + 0.04), 0, h * 0.5 - 0.17),
             rot=(rake, 0, 0))
    for i in range(n):
        y = -run * 0.5 + (i + 0.5) * sd
        z = (i + 1) * sh
        # Tread with a projecting nosing, and a riser board behind it
        _prism_beam(bm, 0, w, sd * 1.22, 0.058,
                    loc=(-w * 0.5, y - sd * 0.10, z - 0.03),
                    rot=(0, pi / 2, 0), chamfer=0.009, rings=3, bow=0.006,
                    rng=rng, chips=2, chip_mat=1, base=True)
        _box(bm, 0, size=(w - 0.03, 0.042, sh - 0.055),
             loc=(0, y + sd * 0.48, z - sh * 0.5 - 0.02))
        for sgn in (-1, 1):
            _nail_head(bm, 2, (sgn * (w * 0.5 - 0.07), y - sd * 0.32,
                               z + 0.002), radius=0.016)
    # Newels at both ends
    for i, (y, z, hh) in enumerate([(-run * 0.5 - 0.06, 0.0, 1.05),
                                    (run * 0.5 + 0.06, h, 0.95)]):
        _prism_beam(bm, 0, hh, 0.11, 0.11,
                    loc=(w * 0.5 + 0.04, y, z), chamfer=0.011, rings=3,
                    rng=rng, chips=2, chip_mat=1, base=True)
        _blob(bm, 0, (w * 0.5 + 0.04, y, z + hh), (0.080, 0.080, 0.090))
    # Balusters rising with the flight, then the handrail over them
    for i in range(8):
        t = (i + 0.5) / 8.0
        y = -run * 0.5 + t * run
        z = t * h + 0.12
        zz = z
        for (rr, hh) in [(0.030, 0.22), (0.042, 0.13), (0.028, 0.33)]:
            _cyl(bm, 0, rr, hh, (w * 0.5 + 0.04, y, zz), segments=8, base=True)
            zz += hh
    _prism_beam(bm, 0, (run ** 2 + h ** 2) ** 0.5, 0.085, 0.065,
                loc=(w * 0.5 + 0.04, -run * 0.5, 0.80),
                rot=(rake - pi / 2, 0, 0), chamfer=0.008, rings=4, bow=0.018,
                rng=rng, chips=2, chip_mat=1, base=True)
    ob = _end(obj, mesh, bm, bevel=0.006, segments=2)
    ob.location = o
    _link(ob, col)


ALL_PROPS = []


def _register(fn, sprite, collection):
    ALL_PROPS.append((sprite, collection, fn))


for _fn, _sp in [
        (wall_straight, "wall_straight"), (wall_corner, "wall_corner"),
        (wall_tower, "wall_tower"), (wall_gatehouse, "wall_gatehouse"),
        (castle_gate, "castle_gate"), (retaining_wall, "retaining_wall"),
        (cliff_wall, "cliff_wall"), (ruin_wall, "ruin_wall"),
        (stairs_small, "stairs_small"), (stairs_large, "stairs_large"),
        (ramp, "ramp"), (platform, "platform"),
        (arch_bridge, "arch_bridge"), (stone_bridge, "stone_bridge"),
        (stone_road, "stone_road"), (cobblestone, "cobblestone"),
        (dirt_road, "dirt_road"), (plaza_tile, "plaza_tile"),
        (wooden_deck, "wooden_deck"), (dock_tile, "dock_tile"),
        (grassy_ground, "grassy_ground"), (cliff_edge, "cliff_edge"),
        (wood_fence, "wood_fence"), (stone_fence, "stone_fence"),
        (iron_fence, "iron_fence"), (railing, "railing"),
        (post_chain, "post_chain"), (hedge, "hedge"),
        (spikes, "spikes"), (gate_small, "gate_small")]:
    _register(_fn, _sp, "P_" + _sp)


for _fn, _sp in [
        (market_stall_a, "market_stall_a"), (market_stall_b, "market_stall_b"),
        (cart, "cart"), (wagon, "wagon"), (crates, "crates"),
        (barrels, "barrels"), (sacks, "sacks"), (signpost, "signpost"),
        (notice_board, "notice_board"),
        (street_lamp, "street_lamp"), (wall_lantern, "wall_lantern"),
        (hanging_lantern, "hanging_lantern"), (well, "well"), (bench, "bench"),
        (planter, "planter"), (fountain, "fountain"), (statue, "statue"),
        (tree_small, "tree_small"), (tree_large, "tree_large"), (bush, "bush"),
        (flower_box, "flower_box"),
        (dock_post, "dock_post"), (dock_platform, "dock_platform"),
        (pier, "pier"), (small_boat, "small_boat"), (sail_boat, "sail_boat"),
        (crane, "crane"), (net_stack, "net_stack"),
        (fish_barrels, "fish_barrels"),
        (clothesline, "clothesline"), (banners, "banners"), (flags, "flags"),
        (awning, "awning"), (balcony, "balcony"),
        (chimney_smoke, "chimney_smoke"), (bookshelf, "bookshelf"),
        (table_set, "table_set"), (hay_stack, "hay_stack"),
        (wood_pile, "wood_pile"),
        (rock_large, "rock_large"), (rock_small, "rock_small"),
        (boulder, "boulder"), (grass_patch, "grass_patch"),
        (flowers, "flowers"), (tree_group, "tree_group"), (vines, "vines"),
        (ivy_wall, "ivy_wall"), (dead_tree, "dead_tree"),
        (ruins_pillar, "ruins_pillar"),
        (bed, "bed"), (table, "table"), (chair, "chair"), (shelf, "shelf"),
        (fireplace, "fireplace"), (rug, "rug"), (curtain, "curtain"),
        (chest, "chest"), (ladder, "ladder"),
        (stairs_interior, "stairs_interior")]:
    _register(_fn, _sp, "P_" + _sp)
