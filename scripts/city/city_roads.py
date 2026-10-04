"""
Circulation: road surfaces, terrace transitions, bridges and the harbour quay.

Roads are laid as a surface strip per segment, sampling terrain z per cell so a
road climbs with the ground instead of hovering over it. Where a road crosses a
terrace edge there is a TRANSITION -- a stair, a ramp or a gatehouse -- because
the plan's rule is that no level change is ever a bare slope.

Axis-true only, which is what `city_plan.check_axis_true()` enforces: the game
camera's yaw is locked, so a diagonal street cannot be seen down.
"""

import bpy
import os
import sys
import random
from math import hypot, floor, cos, sin, pi, atan2

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

from detail_primitives import _begin, _end, _box, _quad, _blob
import builder_primitives as bp
import city_plan as P
import city_geom as G
import city_lod

# Slots
(S_COBBLE_A, S_COBBLE_B, S_DIRT, S_KERB, S_MOSS, S_STONE, S_TIMBER,
 S_WEED) = range(8)


def _slots(mats):
    return [mats["M_Cobble_A"], mats["M_Cobble_B"], mats["M_Cobble_Dirt"],
            mats["M_Ashlar_B"], mats["M_Moss"], mats["M_Granite_B"],
            mats["M_Timber_Aged"], mats["M_Weed_Green"]]


def _cell():
    L = city_lod.get_lod()
    return 1.6 * (1.0 + (L.scale - 1.0) * 0.35)


# =============================================================================
# Road surface
# =============================================================================

def _road_segment(bm, p0, p1, width, rng, cell, dirt=False, kerb=True):
    """One axis-true run of carriageway, following the ground."""
    ax, ay = p0
    bx, by = p1
    length = hypot(bx - ax, by - ay)
    if length < 0.3:
        return 0
    ux, uy = (bx - ax) / length, (by - ay) / length
    px, py = -uy, ux          # across the road
    n_long = max(1, int(round(length / cell)))
    n_across = max(2, int(round(width / cell)))
    dl = length / n_long
    dw = width / n_across
    n = 0
    base = S_DIRT if dirt else S_COBBLE_A
    alt = S_DIRT if dirt else S_COBBLE_B
    for i in range(n_long):
        t0, t1 = i * dl, (i + 1) * dl
        for j in range(n_across):
            o0 = -width * 0.5 + j * dw
            o1 = o0 + dw
            corners = []
            for (t, o) in ((t0, o0), (t1, o0), (t1, o1), (t0, o1)):
                x = ax + ux * t + px * o
                y = ay + uy * t + py * o
                corners.append((x, y, P.z_at(x, y) + 0.06
                                + rng.uniform(-0.02, 0.02)))
            m = alt if rng.random() < 0.34 else base
            _quad(bm, m, corners)
            n += 1
    if kerb and not dirt:
        for side in (-1, 1):
            o = side * (width * 0.5 + 0.18)
            cursor = 0.0
            while cursor < length - 0.2:
                bl = min(rng.uniform(1.4, 2.6), length - cursor)
                t = cursor + bl * 0.5
                x = ax + ux * t + px * o
                y = ay + uy * t + py * o
                z = P.z_at(x, y)
                # Streets are spokes and arcs now, so a kerb stone runs at any
                # bearing: yaw it to the road instead of choosing an axis.
                _box(bm, S_KERB, size=(bl - 0.06, 0.34, 0.30),
                     loc=(x, y, z + 0.14),
                     rot=(0, 0, atan2(uy, ux) + rng.uniform(-0.008, 0.008)))
                n += 1
                if rng.random() < 0.09:
                    _blob(bm, S_WEED, (x, y + 0.2, z + 0.16),
                          (rng.uniform(0.12, 0.28),) * 3)
                    n += 20
                cursor += bl
    return n


# =============================================================================
# Transitions: stairs and ramps
# =============================================================================

def _stair_flight(bm, x, y, axis, z_low, z_high, width, rng, run=None):
    """Treads with a projecting nosing, plus cheek walls kept LOW.

    Full-height cheeks hide every tread at this camera angle -- that was
    established during the library pass and holds here too.
    """
    rise = z_high - z_low
    if rise < 0.3:
        return 0
    tread_h = 0.34
    steps = max(2, int(round(rise / tread_h)))
    th = rise / steps
    tl = 0.62
    run = run or (steps * tl)
    n = 0
    for i in range(steps):
        z = z_low + (i + 0.5) * th
        d = -run * 0.5 + (i + 0.5) * (run / steps)
        if axis == "y":
            loc = (x, y + d, z)
            size = (width, run / steps + 0.10, th * 1.04)
            nose = (width, 0.16, 0.10)
            nloc = (x, y + d - (run / steps) * 0.5, z + th * 0.5)
        else:
            loc = (x + d, y, z)
            size = (run / steps + 0.10, width, th * 1.04)
            nose = (0.16, width, 0.10)
            nloc = (x + d - (run / steps) * 0.5, y, z + th * 0.5)
        _box(bm, rng.choice([S_STONE, S_KERB]), size=size, loc=loc,
             rot=(0, 0, rng.uniform(-0.006, 0.006)))
        _box(bm, S_KERB, size=nose, loc=nloc, rot=(0, 0, 0))
        n += 2
        if rng.random() < 0.12:
            _blob(bm, S_MOSS,
                  (loc[0] + rng.uniform(-width * 0.4, width * 0.4),
                   loc[1], z + th * 0.5), (rng.uniform(0.1, 0.25),) * 3)
            n += 20
    # Low cheek walls: knee height only, so the treads stay visible.
    for side in (-1, 1):
        o = side * (width * 0.5 + 0.22)
        if axis == "y":
            size = (0.40, run, 0.55)
            loc = (x + o, y, z_low + rise * 0.5 + 0.3)
        else:
            size = (run, 0.40, 0.55)
            loc = (x, y + o, z_low + rise * 0.5 + 0.3)
        _box(bm, S_KERB, size=size, loc=loc, rot=(0, 0, 0))
        n += 1
    return n


def _ramp(bm, x, y, axis, z_low, z_high, width, run, rng):
    """A masonry wedge with a cobbled surface, in short stepped courses."""
    rise = z_high - z_low
    if rise < 0.3:
        return 0
    n = 0
    steps = max(4, int(run / 2.2))
    for i in range(steps):
        f0 = i / steps
        f1 = (i + 1) / steps
        z0 = z_low + rise * f0
        z1 = z_low + rise * f1
        d = -run * 0.5 + (f0 + f1) * 0.5 * run
        h = max(0.35, z1 - z0)
        if axis == "y":
            size = (width, run / steps + 0.06, (z1 - z_low) + 0.5)
            loc = (x, y + d, z_low + ((z1 - z_low) + 0.5) * 0.5 - 0.25)
        else:
            size = (run / steps + 0.06, width, (z1 - z_low) + 0.5)
            loc = (x + d, y, z_low + ((z1 - z_low) + 0.5) * 0.5 - 0.25)
        _box(bm, rng.choice([S_STONE, S_KERB, S_STONE]), size=size, loc=loc,
             rot=(0, 0, 0))
        n += 1
    return n


# =============================================================================
# Bridges
# =============================================================================

def _bridge(bm, x, y, axis, span, width, deck_z, water_z, rng, arches=3):
    n = 0
    # Deck
    if axis == "x":
        _box(bm, S_STONE, size=(span, width, 0.55),
             loc=(x, y, deck_z - 0.28), rot=(0, 0, 0))
    else:
        _box(bm, S_STONE, size=(width, span, 0.55),
             loc=(x, y, deck_z - 0.28), rot=(0, 0, 0))
    n += 1
    # Piers and arch rings
    for i in range(arches + 1):
        f = i / arches
        d = -span * 0.5 + span * f
        px = x + (d if axis == "x" else 0.0)
        py = y + (0.0 if axis == "x" else d)
        h = deck_z - water_z
        size = (1.5, width * 1.05, h) if axis == "x" else (width * 1.05, 1.5, h)
        _box(bm, S_STONE, size=size, loc=(px, py, water_z + h * 0.5),
             rot=(0, 0, 0))
        n += 1
    for i in range(arches):
        cf = (i + 0.5) / arches
        d = -span * 0.5 + span * cf
        r = (span / arches) * 0.42
        for k in range(7):
            a = pi * (k + 0.5) / 7
            ox = cos(a) * r
            oz = sin(a) * r
            px = x + ((d + ox) if axis == "x" else 0.0)
            py = y + (0.0 if axis == "x" else (d + ox))
            size = ((r * 0.9), width * 0.98, 0.5) if axis == "x" \
                else (width * 0.98, (r * 0.9), 0.5)
            _box(bm, S_KERB, size=size,
                 loc=(px, py, water_z + h * 0.55 + oz * 0.55), rot=(0, 0, 0))
            n += 1
    # Parapets
    for side in (-1, 1):
        o = side * (width * 0.5 + 0.2)
        if axis == "x":
            _box(bm, S_KERB, size=(span, 0.38, 0.95),
                 loc=(x, y + o, deck_z + 0.45), rot=(0, 0, 0))
        else:
            _box(bm, S_KERB, size=(0.38, span, 0.95),
                 loc=(x + o, y, deck_z + 0.45), rot=(0, 0, 0))
        n += 1
    return n


# =============================================================================
# Quay and piers
# =============================================================================

def _quay(bm, rng, cell):
    """Stone quay round the harbour basin, with timber piers reaching in.

    The basin is a polygon now, so the quay follows its OUTLINE and the piers
    stand normal to it. Walking a bounding box put the quay across open water
    on two sides and left the real edge bare.
    """
    basin = None
    for name, poly in P.WATER_POLYS:
        if name == "harbour":
            basin = poly
    if basin is None:
        return 0

    n = 0
    edge = G.resample(list(basin) + [basin[0]], 9.0)
    for a_, b_ in zip(edge, edge[1:]):
        mx, my = (a_[0] + b_[0]) * 0.5, (a_[1] + b_[1]) * 0.5
        inx, iny = mx * 0.90, my * 0.90
        if P.in_water(inx, iny):
            continue          # that stretch faces open water, not the city
        n += _road_segment(bm, a_, b_, 7.0, rng, cell, kerb=False)

    # Piers reaching out into the basin, normal to the quay.
    for k in range(6):
        idx = int(len(edge) * (k + 0.5) / 6.0) % (len(edge) - 1)
        px, py = edge[idx]
        L = hypot(px, py) or 1.0
        ox, oy = px / L, py / L          # outward, away from the city centre
        plen = 17.0
        cxp = px + ox * plen * 0.5
        cyp = py + oy * plen * 0.5
        yaw = atan2(oy, ox)
        _box(bm, S_TIMBER, size=(plen, 3.4, 0.42),
             loc=(cxp, cyp, 0.55), rot=(0, 0, yaw))
        n += 1
        posts = int(plen / 2.6)
        for i in range(posts):
            t = (i + 0.5) / posts
            bxp = px + ox * plen * t
            byp = py + oy * plen * t
            for side in (-1, 1):
                _box(bm, S_TIMBER, size=(0.30, 0.30, 2.8),
                     loc=(bxp - oy * side * 1.5, byp + ox * side * 1.5, -0.7),
                     rot=(rng.uniform(-0.02, 0.02),
                          rng.uniform(-0.02, 0.02), yaw))
                n += 1
    return n


# =============================================================================
# Driver
# =============================================================================

def build_roads(mats, col_name="50_Roads", seed=7101):
    rng = random.Random(seed)
    cell = _cell()
    obj, mesh, bm = _begin("Cir_Roads", _slots(mats))
    faces = 0
    road_len = 0.0

    for name, width, pts in P.ALL_ROADS:
        dirt = name in ("south_road",)
        # Rings are long arcs and spokes are bowed, so resample to keep every
        # piece about one cell long: the surface then follows the curve
        # instead of chording across it.
        rp = G.resample(pts, 9.0)
        for p0, p1 in zip(rp, rp[1:]):
            road_len += hypot(p1[0] - p0[0], p1[1] - p0[1])
            faces += _road_segment(bm, p0, p1, width, rng, cell, dirt=dirt)

    for tname, (tx, ty), t_from, t_to, kind in P.TRANSITIONS:
        z_hi = P.TERRACE_Z[t_from]
        z_lo = P.TERRACE_Z[t_to]
        if z_lo > z_hi:
            z_hi, z_lo = z_lo, z_hi
        axis = "y"
        if kind.startswith("stairs"):
            w = 9.0 if "large" in kind else 5.0
            faces += _stair_flight(bm, tx, ty, axis, z_lo, z_hi, w, rng)
        elif kind.startswith("ramp"):
            faces += _ramp(bm, tx, ty, axis, z_lo, z_hi, 9.0, 34.0, rng)
        else:
            faces += _ramp(bm, tx, ty, "x", z_lo, z_hi, 8.0, 26.0, rng)

    for bname, (bx, by), asset, axis in P.BRIDGES:
        # Sample along the bridge's OWN axis, far enough to reach dry
        # bank: a 52 m span probed 30 m on X regardless of axis, so a
        # north-south bridge read the water on both sides and fell
        # back to the 4 m floor -- a deck hanging over its own river.
        off = 44.0
        ends = ((bx - off, by), (bx + off, by)) if axis == 'x' \
            else ((bx, by - off), (bx, by + off))
        banks = [P.z_at(ex, ey) for (ex, ey) in ends
                 if not P.in_water(ex, ey)]
        deck_z = max(banks) if banks else P.WATER_Z + 4.0
        faces += _bridge(bm, bx, by, axis, 52.0, 9.0, deck_z, P.WATER_Z, rng,
                         arches=3 if asset == "stone_bridge" else 2)

    faces += _quay(bm, rng, cell)

    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = (0, 0, 0)
    bp.link_to_collection(ob, col_name)
    return faces, road_len


if __name__ == "__main__":
    import materials
    import detail_materials

    bpy.ops.wm.read_factory_settings(use_empty=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    city_lod.set_lod("city")
    m = materials.setup_all_materials()
    detail_materials.setup_detail_materials(m)
    pieces, length = build_roads(m)
    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for o in bpy.data.collections["50_Roads"].objects:
        if o.type == 'MESH':
            ev = o.evaluated_get(dg)
            total += len(ev.to_mesh().polygons)
            ev.to_mesh_clear()
    print("  pieces %d  road_len %.0f m  faces %d" % (pieces, length, total))
