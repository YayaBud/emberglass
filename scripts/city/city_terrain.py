"""
City terrain: terrace platforms, cliff faces, water bodies and waterfalls.

Everything here reads its coordinates from `city_plan`. Nothing is hard-coded.

WHY THIS IS NOT BUILT FROM THE GROUND-TILE ASSETS. The library's `grassy_ground`,
`cobblestone` and `cliff_edge` are 2.8 m sprite modules. The terrain is
760 x 650 m -- tiling it would be ~63,000 prop instances before a single
building exists. So the ground is generated here as slabs: one quad per cell for
the walkable surface, boxes for the skirts, and the library's masonry vocabulary
only along the edges where it is actually seen.

Cell size and strata detail come from `city_lod`, so the whole terrain coarsens
with everything else.
"""

import bpy
import os
import sys
import random
from math import floor, hypot

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

from detail_primitives import _begin, _end, _box, _quad, _blob, _weed_tuft
import city_plan as P
import city_geom as G
import city_lod


# =============================================================================
# Slab surfaces
# =============================================================================

def _patch(x, y, size=34.0):
    """Low-frequency hash so ground variation forms PATCHES, not confetti.

    Picking an alternate material per cell at random produced a checkerboard:
    at a 23 m cell every swap is a hard-edged square the size of a house plot.
    Same fix the roof tiles needed -- vary on a scale larger than the cell.
    """
    i = int(floor(x / size))
    j = int(floor(y / size))
    h = (i * 73856093) ^ (j * 19349663)
    h = (h ^ (h >> 13)) & 0xFFFF
    return h / 65535.0


def _surface(bm, mat_idx, rect, z, cell, rng, jitter=0.06, mats_alt=None,
             alt_chance=0.0, skip=None):
    """A walkable surface as one quad per cell, with a little z jitter.

    `skip(x, y) -> bool` drops cells, which is how water and open ground are
    punched out of a platform without a boolean operation.
    """
    x0, y0, x1, y1 = rect
    nx = max(1, int(round((x1 - x0) / cell)))
    ny = max(1, int(round((y1 - y0) / cell)))
    dx = (x1 - x0) / nx
    dy = (y1 - y0) / ny
    n = 0
    for i in range(nx):
        for j in range(ny):
            ax, bx = x0 + i * dx, x0 + (i + 1) * dx
            ay, by = y0 + j * dy, y0 + (j + 1) * dy
            if skip is not None and skip((ax + bx) * 0.5, (ay + by) * 0.5):
                continue
            m = mat_idx
            if mats_alt:
                cxm, cym = (ax + bx) * 0.5, (ay + by) * 0.5
                p = _patch(cxm, cym)
                if p < alt_chance:
                    m = mats_alt[int(p / max(1e-6, alt_chance)
                                     * len(mats_alt)) % len(mats_alt)]
            h = [z + rng.uniform(-jitter, jitter) for _ in range(4)]
            _quad(bm, m, [(ax, ay, h[0]), (bx, ay, h[1]),
                          (bx, by, h[2]), (ax, by, h[3])])
            n += 1
    return n


def _outside_z(p0, p1, normal, fallback, samples=9, out=6.0):
    """Lowest ground level just outside an edge, so a wall reaches the ground.

    Sampled rather than assumed: a terrace edge can front onto the next
    terrace down for part of its length and onto bare ground for the rest.
    Taking the LOWEST keeps the wall buried at worst, never floating.
    """
    nx_, ny_ = normal
    lo = None
    for i in range(samples):
        t = (i + 0.5) / samples
        x = p0[0] + (p1[0] - p0[0]) * t + nx_ * out
        y = p0[1] + (p1[1] - p0[1]) * t + ny_ * out
        terr = P.terrace_at(x, y)
        z = P.TERRACE_Z[terr] if terr else (
            P.WATER_Z if P.in_water(x, y) else 0.0)
        lo = z if lo is None else min(lo, z)
    return fallback if lo is None else lo


def _retaining_run(bm, mats_idx, coping_idx, moss_idx, p0, p1, normal,
                   z_top, z_bot, rng, course_h, block_len, batter=0.055):
    """A coursed masonry retaining wall along one edge.

    NOT built from the library's `retaining_wall` prop: that is a 2.8 m sprite
    module, and the terrace edges run to roughly 3 km, so it would be ~1,070
    instances before a single building exists. Coursed here instead, at a
    block size that survives city viewing distance.

    The batter (each course set back as it rises) is what stops this reading as
    a flat extruded strip - a real retaining wall leans into the bank it holds.
    """
    ax, ay = p0
    bx, by = p1
    horiz = abs(bx - ax) > abs(by - ay)
    length = abs(bx - ax) + abs(by - ay)
    if length < 0.2:
        return 0
    nx_, ny_ = normal
    n = 0
    z = z_bot
    course = 0
    while z < z_top - 0.01:
        ch = min(course_h * rng.uniform(0.88, 1.12), z_top - z)
        t = (z - z_bot) / max(0.5, z_top - z_bot)
        set_back = batter * (z_top - z_bot) * t
        cursor = 0.0
        # Stagger every other course so the vertical joints never line up.
        if course % 2:
            cursor -= block_len * 0.5
        while cursor < length - 0.02:
            bl = min(block_len * rng.uniform(0.75, 1.25), length - cursor)
            if bl < 0.25:
                break
            mid = max(0.0, cursor) + bl * 0.5
            off = set_back + rng.uniform(-0.05, 0.05)
            if horiz:
                loc = (min(ax, bx) + mid, ay - ny_ * off, z + ch * 0.5)
                size = (bl - 0.06, course_h * 0.85, ch * 1.02)
            else:
                loc = (ax - nx_ * off, min(ay, by) + mid, z + ch * 0.5)
                size = (course_h * 0.85, bl - 0.06, ch * 1.02)
            _box(bm, rng.choice(mats_idx), size=size, loc=loc,
                 rot=(rng.uniform(-0.012, 0.012), rng.uniform(-0.012, 0.012),
                      rng.uniform(-0.015, 0.015)))
            n += 1
            # Moss gathers in the lower courses where the wall stays damp.
            if t < 0.35 and rng.random() < 0.10:
                mx = loc[0] + (0 if horiz else -nx_ * 0.30)
                my = loc[1] + (-ny_ * 0.30 if horiz else 0)
                _blob(bm, moss_idx, (mx, my, z + ch * 0.5),
                      (rng.uniform(0.25, 0.6),) * 3)
                n += 20
            cursor += bl
        z += ch
        course += 1
    # Coping course, projecting proud of the face to throw a shadow line.
    cursor = 0.0
    while cursor < length - 0.02:
        bl = min(block_len * 1.3 * rng.uniform(0.85, 1.15), length - cursor)
        if bl < 0.25:
            break
        mid = cursor + bl * 0.5
        if horiz:
            loc = (min(ax, bx) + mid, ay + ny_ * 0.10, z_top + 0.18)
            size = (bl - 0.05, course_h * 1.25, 0.38)
        else:
            loc = (ax + nx_ * 0.10, min(ay, by) + mid, z_top + 0.18)
            size = (course_h * 1.25, bl - 0.05, 0.38)
        _box(bm, coping_idx, size=size, loc=loc,
             rot=(0, 0, rng.uniform(-0.01, 0.01)))
        n += 1
        cursor += bl
    return n


def _skirt(bm, strata_mats, rect, z_top, z_bot, cell, rng, cap_mat=None):
    """The vertical face of a platform, in broken courses.

    Built as boxes rather than quads so the strata read as rock with depth
    under raking light instead of as a cut-out.
    """
    x0, y0, x1, y1 = rect
    edges = [
        ((x0, y0), (x1, y0), (0.0, -1.0)),
        ((x1, y0), (x1, y1), (1.0, 0.0)),
        ((x1, y1), (x0, y1), (0.0, 1.0)),
        ((x0, y1), (x0, y0), (-1.0, 0.0)),
    ]
    n = 0
    for (ax, ay), (bx, by), (nx_, ny_) in edges:
        length = abs(bx - ax) + abs(by - ay)
        if length < 0.01:
            continue
        horiz = abs(bx - ax) > abs(by - ay)
        z = z_bot
        while z < z_top - 0.01:
            sh = min(rng.uniform(cell * 0.45, cell * 0.95), z_top - z)
            cursor = 0.0
            while cursor < length - 0.02:
                bl = min(rng.uniform(cell * 0.7, cell * 1.6), length - cursor)
                if bl < 0.15:
                    break
                t = cursor + bl * 0.5
                proj = rng.uniform(-0.18, 0.30)
                px = (ax + (t if horiz else 0.0)) if horiz else ax
                py = ay if horiz else (ay + (t if not horiz else 0.0))
                if horiz:
                    px = min(ax, bx) + t
                    py = ay + ny_ * proj
                    size = (bl - 0.04, cell * 0.9, sh * 1.03)
                else:
                    px = ax + nx_ * proj
                    py = min(ay, by) + t
                    size = (cell * 0.9, bl - 0.04, sh * 1.03)
                _box(bm, rng.choice(strata_mats), size=size,
                     loc=(px, py, z + sh * 0.5),
                     rot=(rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03),
                          rng.uniform(-0.04, 0.04)))
                cursor += bl
                n += 1
            z += sh
    return n


# =============================================================================
# Builders
# =============================================================================

def build_ground(mats, col_name, seed=5101):
    """The natural ground the city sits on, outside every terrace."""
    L = city_lod.get_lod()
    # Terrain cell is a WORLD size, not a per-building detail level: it
    # scales far more gently than L.scale, or the ground becomes 23 m
    # slabs and every material change reads as a city block.
    cell = 9.0 * (1.0 + (L.scale - 1.0) * 0.25)
    rng = random.Random(seed)
    obj, mesh, bm = _begin("Ter_Ground", [
        mats["M_Grass"], mats["M_Soil"], mats["M_Foliage"],
        mats["M_Sand"], mats["M_Weed_Green"]])

    def skip(x, y):
        return (hypot(x, y) > P.GROUND_R or P.in_water(x, y)
                or P.terrace_at(x, y) is not None)

    n = _surface(bm, 0, P.TERRAIN, 0.0, cell, rng, jitter=0.5,
                 mats_alt=[1, 2], alt_chance=0.22, skip=skip)
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = (0, 0, 0)
    _link(ob, col_name)
    return n


def build_terraces(mats, col_name, seed=5107):
    """Five stepped platforms, each a surface plus a rock skirt."""
    L = city_lod.get_lod()
    cell = 5.0 * (1.0 + (L.scale - 1.0) * 0.25)
    rng = random.Random(seed)
    obj, mesh, bm = _begin("Ter_Platforms", [
        mats["M_Grass"], mats["M_Soil"], mats["M_Cobble_Dirt"],
        mats["M_Granite_A"], mats["M_Granite_B"], mats["M_Granite_C"],
        mats["M_Moss"],
        mats["M_Fieldstone_A"], mats["M_Fieldstone_B"], mats["M_Ashlar_B"]])

    # Course and block size are what decide whether ~3 km of retaining wall
    # fits the budget. At city LOD these give roughly 90k faces for the lot.
    course_h = 0.95 * (1.0 + (L.scale - 1.0) * 0.45)
    block_len = 2.0 * (1.0 + (L.scale - 1.0) * 0.45)
    faces = 0
    # Lowest first: each platform is drawn at its own z over its own polygon,
    # and a cell belongs to the HIGHEST platform containing it.
    for name, poly in P.TERRACE_POLYS:
        z = P.TERRACE_Z[name]
        rect = G.bbox(poly)

        def skip(x, y, _n=name):
            return P.terrace_at(x, y) != _n or P.in_water(x, y)

        faces += _surface(bm, 2, rect, z, cell, rng, jitter=0.08,
                          mats_alt=[0, 1], alt_chance=0.18, skip=skip)
        below = max([v for k, v in P.TERRACE_Z.items() if v < z]
                    + [P.WATER_Z])
        if z - below <= 0.5:
            continue
        # Walk the platform's OUTLINE, not a box. A radial terrace edge is an
        # arc, so the retaining wall follows it segment by segment; the foot of
        # each run is the ground just outside that segment.
        outline = G.resample(poly + [poly[0]], 14.0)
        for a, b in zip(outline, outline[1:]):
            mx, my = (a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = (dx * dx + dy * dy) ** 0.5
            if L < 1.0:
                continue
            nrm = (-dy / L, dx / L)
            # Point the normal away from the platform.
            if P.terrace_at(mx + nrm[0] * 5.0, my + nrm[1] * 5.0) == name:
                nrm = (-nrm[0], -nrm[1])
            foot = _outside_z(a, b, nrm, below)
            if z - foot <= 0.3:
                continue
            bx0, by0, bx1, by1 = P.BUILT
            built = (bx0 - 30.0 <= mx <= bx1 + 30.0
                     and by0 - 30.0 <= my <= by1 + 30.0)
            if built:
                faces += _retaining_run(
                    bm, [7, 8, 9], 9, 6, a, b, nrm, z, foot, rng,
                    course_h=course_h, block_len=block_len)
            else:
                faces += _skirt(bm, [3, 4, 5],
                                (min(a[0], b[0]), min(a[1], b[1]),
                                 max(a[0], b[0]), max(a[1], b[1])),
                                z, foot, cell, rng)

    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = (0, 0, 0)
    _link(ob, col_name)
    return faces


def build_water(mats, col_name, seed=5113):
    """Estuary, channels, tributary and harbour basin at a single level."""
    L = city_lod.get_lod()
    cell = 12.0 * (1.0 + (L.scale - 1.0) * 0.25)
    rng = random.Random(seed)
    obj, mesh, bm = _begin("Ter_Water", [
        mats["M_Water_Deep"], mats["M_Sand"], mats["M_Soil"]])
    faces = 0
    for name, poly in P.WATER_POLYS:
        def skip(x, y, _p=poly):
            return (hypot(x, y) > P.GROUND_R
                    or not G.contains(_p, x, y)
                    or G.contains(P.LIGHTHOUSE_ISLAND, x, y))
        faces += _surface(bm, 0, G.bbox(poly), P.WATER_Z, cell, rng,
                          jitter=0.03, skip=skip)
    # The lighthouse islet: a rock standing out of the water.
    isl = G.bbox(P.LIGHTHOUSE_ISLAND)
    faces += _surface(bm, 1, isl, 0.6, cell * 0.4, rng, jitter=0.12,
                      skip=lambda x, y: not G.contains(P.LIGHTHOUSE_ISLAND,
                                                       x, y))
    faces += _skirt(bm, [1, 2, 1], isl, 0.6, P.WATER_Z - 0.4,
                    cell * 0.4, rng)
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = (0, 0, 0)
    _link(ob, col_name)
    return faces


def build_waterfalls(mats, col_name, seed=5119):
    """The three structural drops, as falling sheets with foam at the base."""
    L = city_lod.get_lod()
    rng = random.Random(seed)
    obj, mesh, bm = _begin("Ter_Waterfalls", [
        mats["M_Water_Deep"], mats["M_Plaster_Weathered"],
        mats["M_Granite_B"]])
    faces = 0
    for name, (x, y), z_top, z_bot in P.WATERFALLS:
        width = 16.0
        drop = z_top - z_bot
        # The sheet, in a few vertical panels so it is not one flat plane.
        panels = max(3, L.detail(6))
        for i in range(panels):
            fx = x - width * 0.5 + width * (i + 0.5) / panels
            pw = width / panels * 0.96
            _box(bm, 0, size=(pw, 0.9 + rng.uniform(0, 0.5), drop),
                 loc=(fx, y + rng.uniform(-0.3, 0.3), z_bot + drop * 0.5),
                 rot=(0, 0, rng.uniform(-0.02, 0.02)))
            faces += 6
        # Foam where it lands.
        for _ in range(L.detail(14)):
            _blob(bm, 1,
                  (x + rng.uniform(-width * 0.6, width * 0.6),
                   y + rng.uniform(-3.0, 3.0),
                   z_bot + rng.uniform(0.1, 1.4)),
                  (rng.uniform(0.8, 2.0),) * 3)
            faces += 20
        # Worn rock lip at the head.
        for _ in range(L.detail(8)):
            _box(bm, 2, size=(rng.uniform(2.0, 4.5), rng.uniform(1.2, 2.4),
                              rng.uniform(0.5, 1.1)),
                 loc=(x + rng.uniform(-width * 0.6, width * 0.6),
                      y + rng.uniform(-1.2, 1.2), z_top - 0.3),
                 rot=(0, 0, rng.uniform(0, 3.14)))
            faces += 6
    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = (0, 0, 0)
    _link(ob, col_name)
    return faces


def _link(obj, col_name):
    import builder_primitives as bp
    bp.link_to_collection(obj, col_name)


def build_all(mats, col_name="30_Terrain"):
    out = {}
    out["ground"] = build_ground(mats, col_name)
    out["terraces"] = build_terraces(mats, col_name)
    out["water"] = build_water(mats, col_name)
    out["waterfalls"] = build_waterfalls(mats, col_name)
    return out


if __name__ == "__main__":
    import materials
    import detail_materials

    bpy.ops.wm.read_factory_settings(use_empty=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    city_lod.set_lod("city")
    m = materials.setup_all_materials()
    detail_materials.setup_detail_materials(m)
    stats = build_all(m)
    total = 0
    dg = bpy.context.evaluated_depsgraph_get()
    for o in bpy.data.collections["30_Terrain"].objects:
        if o.type == 'MESH':
            ev = o.evaluated_get(dg)
            total += len(ev.to_mesh().polygons)
            ev.to_mesh_clear()
    for k, v in stats.items():
        print("  %-12s %8d" % (k, v))
    print("  %-12s %8d faces" % ("TOTAL", total))
