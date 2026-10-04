"""
Fortification: curtain wall, towers, gates and the harbour arms.

Swept along `city_plan.WALL_RUNS`. A gap between two runs is an opening, not a
flag -- the water gate is the gap between run 1 and run 2.

Same reasoning as the retaining walls in `city_terrain`: the library's
`wall_straight` / `wall_tower` are 2.8 m sprite modules, and the circuit is
~1.5 km, so instancing them is ~540 pieces before anything else exists. The
masonry is coursed here at a block size that survives city viewing distance,
using the same stone palette so it reads as one city.
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

from detail_primitives import _begin, _end, _box, _blob
import builder_primitives as bp
import city_plan as P
import city_lod

# Material slots, in the order `_slots` builds them.
S_A, S_B, S_C, S_CAP, S_MOSS, S_TIMBER, S_IRON, S_DARK = range(8)

WALL_H = 8.5          # parapet walk level
WALL_T = 2.6          # thickness
MERLON_H = 1.5
TOWER_R = 3.4
TOWER_EXTRA = 4.0     # how far a tower rises above the wall walk


def _slots(mats):
    return [mats["M_Granite_A"], mats["M_Granite_B"], mats["M_Granite_C"],
            mats["M_Ashlar_B"], mats["M_Moss"], mats["M_Timber_Aged"],
            mats["M_Iron_Aged"], mats["M_Soot"]]


def _lod_sizes():
    L = city_lod.get_lod()
    k = 1.0 + (L.scale - 1.0) * 0.45
    return 0.85 * k, 1.9 * k      # course height, block length


# =============================================================================
# Pieces
# =============================================================================

def _coursed_run(bm, p0, p1, z_base, z_top, thickness, rng,
                 course_h, block_len, skip_spans=(), batter=0.02):
    """Coursed masonry along a segment, with staggered vertical joints.

    `skip_spans` are (t0, t1) fractions left open -- gateways punched through
    the curtain rather than modelled as separate objects.
    """
    ax, ay = p0
    bx, by = p1
    length = hypot(bx - ax, by - ay)
    if length < 0.2:
        return 0
    ux, uy = (bx - ax) / length, (by - ay) / length
    n = 0
    z = z_base
    course = 0
    while z < z_top - 0.01:
        ch = min(course_h * rng.uniform(0.9, 1.1), z_top - z)
        t = (z - z_base) / max(0.5, z_top - z_base)
        th = thickness * (1.0 - batter * t)
        cursor = -block_len * 0.5 if course % 2 else 0.0
        while cursor < length - 0.02:
            bl = min(block_len * rng.uniform(0.8, 1.2), length - cursor)
            if bl < 0.25:
                break
            mid = max(0.0, cursor) + bl * 0.5
            frac = mid / length
            if any(s0 <= frac <= s1 for s0, s1 in skip_spans):
                cursor += bl
                continue
            cx_ = ax + ux * mid
            cy_ = ay + uy * mid
            # The circuit is an organic polygon, so a segment runs at any
            # bearing: yaw each block to the run instead of picking an axis.
            yaw = atan2(uy, ux)
            _box(bm, rng.choice([S_A, S_B, S_C]),
                 size=(bl - 0.06, th, ch * 1.02),
                 loc=(cx_, cy_, z + ch * 0.5),
                 rot=(rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01),
                      yaw + rng.uniform(-0.012, 0.012)))
            n += 1
            if t < 0.28 and rng.random() < 0.07:
                _blob(bm, S_MOSS, (cx_ - uy * th * 0.55,
                                   cy_ + ux * th * 0.55, z + ch * 0.4),
                      (rng.uniform(0.2, 0.5),) * 3)
                n += 20
            cursor += bl
        z += ch
        course += 1
    return n


def _crenellate(bm, p0, p1, z, thickness, rng, merlon=2.0, gap=1.5,
                skip_spans=()):
    """Merlons and embrasures along a wall head."""
    ax, ay = p0
    bx, by = p1
    length = hypot(bx - ax, by - ay)
    if length < 0.5:
        return 0
    ux, uy = (bx - ax) / length, (by - ay) / length
    n = 0
    cursor = 0.0
    while cursor < length - merlon:
        frac = (cursor + merlon * 0.5) / length
        if not any(s0 <= frac <= s1 for s0, s1 in skip_spans):
            cx_ = ax + ux * (cursor + merlon * 0.5)
            cy_ = ay + uy * (cursor + merlon * 0.5)
            _box(bm, rng.choice([S_A, S_CAP, S_B]),
                 size=(merlon, thickness * 0.92, MERLON_H),
                 loc=(cx_, cy_, z + MERLON_H * 0.5),
                 rot=(0, 0, atan2(uy, ux) + rng.uniform(-0.01, 0.01)))
            n += 1
        cursor += merlon + gap
    return n


def _tower(bm, x, y, z_base, z_top, rng, course_h, block_len, radius=TOWER_R):
    """A drum tower: coursed rings, a corbel band, and a crenellated head."""
    n = 0
    z = z_base
    while z < z_top - 0.01:
        ch = min(course_h * rng.uniform(0.9, 1.1), z_top - z)
        t = (z - z_base) / max(0.5, z_top - z_base)
        r = radius * (1.0 - 0.05 * t)
        count = max(8, int(2 * pi * r / block_len))
        phase = rng.uniform(0, 2 * pi)
        for k in range(count):
            a = phase + 2 * pi * k / count
            arc = (2 * pi / count) * rng.uniform(0.82, 0.98)
            bw = 2.0 * r * sin(arc * 0.5)
            th = block_len * 0.55
            _box(bm, rng.choice([S_A, S_B, S_C]),
                 size=(bw, th, ch * 1.02),
                 loc=(x + cos(a) * (r - th * 0.4),
                      y + sin(a) * (r - th * 0.4), z + ch * 0.5),
                 rot=(0, 0, a + pi * 0.5))
            n += 1
        z += ch
    # Corbel band under the head, then merlons round the top.
    count = max(10, int(2 * pi * radius / (block_len * 0.8)))
    for k in range(count):
        a = 2 * pi * k / count
        _box(bm, S_CAP, size=(block_len * 0.7, block_len * 0.5, 0.45),
             loc=(x + cos(a) * (radius + 0.22),
                  y + sin(a) * (radius + 0.22), z_top - 0.30),
             rot=(0, 0, a + pi * 0.5))
        n += 1
    count = max(8, int(2 * pi * radius / 3.0))
    for k in range(count):
        a = 2 * pi * k / count
        _box(bm, rng.choice([S_A, S_CAP]), size=(2.0, 1.0, MERLON_H),
             loc=(x + cos(a) * (radius + 0.1),
                  y + sin(a) * (radius + 0.1), z_top + MERLON_H * 0.5),
             rot=(0, 0, a + pi * 0.5))
        n += 1
    return n


def _gate(bm, x, y, facing_deg, width, z_base, rng, course_h, block_len):
    """A gatehouse: two flanking masses, an arched head, doors in the reveal."""
    n = 0
    horiz = abs(cos(facing_deg * pi / 180.0)) > 0.5
    depth = 7.0
    pier = 4.2
    top = z_base + WALL_H + 3.5
    for side in (-1, 1):
        off = (width * 0.5 + pier * 0.5) * side
        px = x + (off if horiz else 0.0)
        py = y + (0.0 if horiz else off)
        p0 = (px - (0 if horiz else depth * 0.5),
              py - (depth * 0.5 if horiz else 0))
        p1 = (px + (0 if horiz else depth * 0.5),
              py + (depth * 0.5 if horiz else 0))
        if horiz:
            p0 = (px, py - depth * 0.5)
            p1 = (px, py + depth * 0.5)
        else:
            p0 = (px - depth * 0.5, py)
            p1 = (px + depth * 0.5, py)
        n += _coursed_run(bm, p0, p1, z_base, top, pier, rng,
                          course_h, block_len)
        n += _crenellate(bm, p0, p1, top, pier, rng)
    # The arch over the opening, as a flat lintel band plus voussoir blocks.
    arch_z = z_base + 5.6
    steps = 7
    for i in range(steps):
        a = pi * (i + 0.5) / steps
        bx_ = x + (cos(a) * width * 0.5 if horiz else 0.0)
        by_ = y + (0.0 if horiz else cos(a) * width * 0.5)
        bz = arch_z + sin(a) * 1.5
        size = ((width / steps) * 1.25, depth, 1.0) if horiz else \
               (depth, (width / steps) * 1.25, 1.0)
        _box(bm, S_CAP, size=size, loc=(bx_, by_, bz), rot=(0, 0, 0))
        n += 1
    # Solid above the arch, up to the walk.
    if horiz:
        p0, p1 = (x, y - depth * 0.5), (x, y + depth * 0.5)
    else:
        p0, p1 = (x - depth * 0.5, y), (x + depth * 0.5, y)
    n += _coursed_run(bm, p0, p1, arch_z + 2.0, top, width, rng,
                      course_h, block_len)
    n += _crenellate(bm, p0, p1, top, width, rng)
    # Timber leaves, set back in the reveal.
    for side in (-1, 1):
        lw = width * 0.47
        loff = side * width * 0.25
        if horiz:
            size = (lw, 0.35, 5.2)
            loc = (x, y + loff, z_base + 2.6)
        else:
            size = (0.35, lw, 5.2)
            loc = (x + loff, y, z_base + 2.6)
        _box(bm, S_TIMBER, size=size, loc=loc, rot=(0, 0, 0))
        n += 1
    return n


# =============================================================================
# Driver
# =============================================================================

def build_walls(mats, col_name="40_Walls", seed=6101):
    rng = random.Random(seed)
    course_h, block_len = _lod_sizes()
    obj, mesh, bm = _begin("For_Curtain", _slots(mats))

    gate_at = {g[0]: g for g in P.GATES}
    faces = 0
    towers = []

    for run in P.WALL_RUNS:
        for p0, p1 in zip(run, run[1:]):
            length = hypot(p1[0] - p0[0], p1[1] - p0[1])
            if length < 0.2:
                continue
            base = min(P.z_at(p0[0], p0[1]), P.z_at(p1[0], p1[1]))
            if base < P.WATER_Z + 0.1:
                base = P.WATER_Z
            top = base + WALL_H

            # Any land gate sitting on this segment punches a hole in it.
            spans = []
            for name, (gx, gy), facing, gw in P.GATES:
                if name == "water":
                    continue
                d = P._point_segment_distance(gx, gy, p0[0], p0[1],
                                              p1[0], p1[1])
                if d > 3.0:
                    continue
                t = hypot(gx - p0[0], gy - p0[1]) / length
                half = (gw * 0.5 + 4.6) / length
                spans.append((max(0.0, t - half), min(1.0, t + half)))

            faces += _coursed_run(bm, p0, p1, base, top, WALL_T, rng,
                                  course_h, block_len, skip_spans=spans)
            faces += _crenellate(bm, p0, p1, top, WALL_T, rng,
                                 skip_spans=spans)

            # Towers: both ends of every segment, plus regular spacing along.
            towers.append((p0[0], p0[1], base))
            towers.append((p1[0], p1[1], base))
            steps = int(length // P.TOWER_SPACING)
            ux = (p1[0] - p0[0]) / length
            uy = (p1[1] - p0[1]) / length
            for i in range(1, steps + 1):
                d = i * P.TOWER_SPACING
                if d > length - 8.0:
                    break
                tx, ty = p0[0] + ux * d, p0[1] + uy * d
                if any(s0 <= d / length <= s1 for s0, s1 in spans):
                    continue
                towers.append((tx, ty, base))

    # De-duplicate: segment ends coincide, and a tower built twice is 2x cost.
    seen = set()
    for tx, ty, base in towers:
        key = (round(tx / 3.0), round(ty / 3.0))
        if key in seen:
            continue
        seen.add(key)
        faces += _tower(bm, tx, ty, base, base + WALL_H + TOWER_EXTRA, rng,
                        course_h, block_len)

    for name, (gx, gy), facing, gw in P.GATES:
        if name == "water":
            continue
        base = P.z_at(gx, gy)
        faces += _gate(bm, gx, gy, facing, gw, base, rng,
                       course_h, block_len)

    ob = _end(obj, mesh, bm, bevel=0.0)
    ob.location = (0, 0, 0)
    bp.link_to_collection(ob, col_name)
    return faces, len(seen)


if __name__ == "__main__":
    import materials
    import detail_materials

    bpy.ops.wm.read_factory_settings(use_empty=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    city_lod.set_lod("city")
    m = materials.setup_all_materials()
    detail_materials.setup_detail_materials(m)
    blocks, ntowers = build_walls(m)
    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for o in bpy.data.collections["40_Walls"].objects:
        if o.type == 'MESH':
            ev = o.evaluated_get(dg)
            total += len(ev.to_mesh().polygons)
            ev.to_mesh_clear()
    print("  blocks %d  towers %d  faces %d" % (blocks, ntowers, total))
