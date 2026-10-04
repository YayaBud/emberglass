"""
Export the city's STRUCTURE to GLB: terrain, fortification, roads.

    blender --background --python scripts/city/city_export_terrain.py

Fixes ledger C16. Before this, only buildings and props crossed into the game,
so the city would have stood on the world's own procedural ground with no
terraces, no walls and no streets under it.

Three GLBs, one per system, into the same NEW folder as the building exports:

    emberglass_terrain.glb   platforms, cliffs, water, waterfalls
    emberglass_walls.glb     curtain, towers, gates
    emberglass_roads.glb     carriageways, stairs, ramps, bridges, quay

WHY COL_ BOXES AND NOT A TRIMESH. `ModelLoader` turns authored `COL_*` boxes
into collision, and the navmesh bake parses static colliders. A trimesh off the
terrain would work but is expensive and needlessly precise: the ground is FLAT
per terrace, so one box per terrace platform gives exact collision for a few
hundred bytes. Walls get one box per segment. Roads need none -- they sit on the
terrace they belong to.
"""

import bpy
import os
import sys
import json
from math import ceil, hypot

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

import materials
import detail_materials
import city_materials
import city_geom as G
import city_plan as P
import city_lod
import city_terrain
import city_walls
import city_roads
import city_chunk

OUT_DIR = "D:/nanobanna_godot/assets/models/emberglass"

#: How far below its surface a terrace collider extends. Only the top face is
#: ever stood on; the depth just has to reach the level below.
SLAB_DEPTH = 6.0


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def add_collider(name, centre, size):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
    ob = bpy.context.active_object
    ob.name = "COL_" + name
    ob.scale = (size[0] * 0.5, size[1] * 0.5, size[2] * 0.5)
    return ob


#: How high a terrace's edge parapet stands above its own surface. The
#: retaining walls are visual geometry inside the terrain mesh, so without a
#: matching collider the player walks straight through one and falls a level.
PARAPET_H = 1.6


def _seg_box(p0, p1, thick):
    """An axis-aligned box spanning a segment, at least `thick` on each axis.

    `ModelLoader` reads a COL_ box as centre plus size and applies NO rotation,
    so a diagonal wall cannot be given a diagonal collider. The old code chose
    between a horizontal and a vertical box by which axis was longer, which is
    right for a rectangle's edge and wrong for everything in a radial city: a
    45-degree segment got a thin box laid across it, leaving the wall open.
    An AABB over a SHORT segment is a little thick and never has a gap, and
    the runs are resampled so the segments stay short.
    """
    cx, cy = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
    return ((cx, cy), (max(abs(p1[0] - p0[0]), thick),
                       max(abs(p1[1] - p0[1]), thick)))


#: Edge of the square a terrace slab is rasterised at. A terrace is a POLYGON
#: now, so one box per terrace would be its bounding box -- for the T0 sector
#: that is a 456 m square of solid floor over open water and over the two
#: terraces above it. 16 m squares, merged into runs, follow the real outline
#: to within half a building.
SLAB_CELL = 16.0


def _poly_strips(poly, cell):
    """Cover a polygon with axis-aligned boxes: rasterise, then merge runs.

    Returned as (x0, y0, x1, y1). Merging each row's inside cells into one
    strip is what keeps the count sane -- the five terraces rasterise to a few
    thousand cells and come back as roughly a hundred strips.
    """
    bx0, by0, bx1, by1 = G.bbox(poly)
    nx = max(1, int(ceil((bx1 - bx0) / cell)))
    ny = max(1, int(ceil((by1 - by0) / cell)))
    out = []
    for j in range(ny):
        cy = by0 + (j + 0.5) * cell
        run = None
        for i in range(nx + 1):
            inside = (i < nx
                      and G.contains(poly, bx0 + (i + 0.5) * cell, cy))
            if inside and run is None:
                run = i
            elif not inside and run is not None:
                out.append((bx0 + run * cell, by0 + j * cell,
                            bx0 + i * cell, by0 + (j + 1) * cell))
                run = None
    return out


def _outward(poly, mx, my, nx_, ny_, d=7.0):
    """Flip a segment normal so it points OUT of the polygon.

    Winding cannot be assumed: the terrace sectors are built outer-arc-first
    and the farm band is a thin annulus whose bbox centre is not inside it.
    Sampling is cheap and always right.
    """
    if G.contains(poly, mx + nx_ * d, my + ny_ * d):
        return -nx_, -ny_
    return nx_, ny_


def terrain_colliders():
    """Slabs under every terrace, plus a parapet along every edge that drops.

    The ground is flat per terrace, so boxes are EXACT collision in Z rather
    than an approximation -- only the outline is approximated, and only to
    SLAB_CELL. The edges are the part that would otherwise be missed: the
    retaining walls render but do not collide, so a player could walk off T2
    (+24) and fall to T0 without ever touching the wall visibly in the way.
    """
    out = []
    for i, (name, poly) in enumerate(P.TERRACE_POLYS):
        z = P.TERRACE_Z[name]
        for s, (x0, y0, x1, y1) in enumerate(_poly_strips(poly, SLAB_CELL)):
            out.append(add_collider(
                "terrace_%s_%d_%d" % (name, i, s),
                ((x0 + x1) * 0.5, (y0 + y1) * 0.5, z - SLAB_DEPTH * 0.5),
                (x1 - x0, y1 - y0, SLAB_DEPTH)))

        for k, (p0, p1) in enumerate(zip(poly, poly[1:] + poly[:1])):
            length = hypot(p1[0] - p0[0], p1[1] - p0[1])
            if length < 1.0:
                continue
            mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
            nx_, ny_ = _outward(poly, mx, my,
                                -(p1[1] - p0[1]) / length,
                                (p1[0] - p0[0]) / length)
            # Sample just outside: only a real drop needs a parapet, and a
            # stair or ramp landing there must stay walkable.
            sx, sy = mx + nx_ * 7.0, my + ny_ * 7.0
            if z - P.z_at(sx, sy) < 2.0:
                continue
            near = min((hypot(sx - tx, sy - ty)
                        for _n, (tx, ty), _a, _b, _k in P.TRANSITIONS),
                       default=1e9)
            gate = min((hypot(sx - gx, sy - gy)
                        for _n, (gx, gy), _f, _w in P.GATES), default=1e9)
            if min(near, gate) < 26.0:
                continue
            (cx, cy), (sxw, syw) = _seg_box(p0, p1, 1.2)
            out.append(add_collider(
                "parapet_%s_%d_%d" % (name, i, k),
                (cx, cy, z + PARAPET_H * 0.5), (sxw, syw, PARAPET_H)))
    return out


def wall_colliders():
    """One box per wall segment, minus the gate openings.

    A gate has to be walkable or the city has no way in, so each segment is
    split around any gate sitting on it.
    """
    out = []
    n = 0
    for whole in P.WALL_RUNS:
        # Short segments: _seg_box is an AABB, so its over-thickness is the
        # segment's own length on the short axis. 8 m keeps that under 6 m,
        # well inside the 26 m clear between the circuit and ring_3.
        run = G.resample(whole, 8.0)
        for p0, p1 in zip(run, run[1:]):
            length = hypot(p1[0] - p0[0], p1[1] - p0[1])
            if length < 0.5:
                continue
            base = min(P.z_at(*p0), P.z_at(*p1))
            ux = (p1[0] - p0[0]) / length
            uy = (p1[1] - p0[1]) / length

            # Fractions of this segment that a gate leaves open.
            gaps = []
            for gname, (gx, gy), _f, gw in P.GATES:
                if gname == "water":
                    continue
                if P._point_segment_distance(gx, gy, p0[0], p0[1],
                                             p1[0], p1[1]) > 3.0:
                    continue
                t = hypot(gx - p0[0], gy - p0[1]) / length
                half = (gw * 0.5 + 2.0) / length
                gaps.append((max(0.0, t - half), min(1.0, t + half)))
            gaps.sort()

            spans = []
            cursor = 0.0
            for g0, g1 in gaps:
                if g0 > cursor:
                    spans.append((cursor, g0))
                cursor = max(cursor, g1)
            if cursor < 1.0:
                spans.append((cursor, 1.0))

            for s0, s1 in spans:
                seg_len = (s1 - s0) * length
                if seg_len < 1.0:
                    continue
                e0 = (p0[0] + ux * s0 * length, p0[1] + uy * s0 * length)
                e1 = (p0[0] + ux * s1 * length, p0[1] + uy * s1 * length)
                (cx, cy), (sx, sy) = _seg_box(e0, e1, city_walls.WALL_T)
                out.append(add_collider(
                    "wall_%d" % n,
                    (cx, cy, base + city_walls.WALL_H * 0.5),
                    (sx, sy, city_walls.WALL_H)))
                n += 1
    return out


#: Chunk edge in metres. 760 x 650 m of terrain at 100 m gives ~40 occupied
#: squares of roughly 3k faces each -- small enough to cull usefully, large
#: enough that the draw-call count stays sane.
CHUNK = 100.0


def join_chunk(objs, name):
    """Join a chunk's objects into one mesh, keeping every material slot."""
    if len(objs) <= 1:
        return objs
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    return [joined]


def export(name, objs):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name + ".glb")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB",
                              use_selection=True, export_apply=True)
    faces = sum(len(o.data.polygons) for o in objs
                if o.type == 'MESH' and not o.name.startswith("COL_"))
    cols = sum(1 for o in objs if o.name.startswith("COL_"))
    return {"name": name, "faces": faces, "colliders": cols}


def main():
    """Build all three systems into one scene, then cut them into chunks."""
    clear_scene()
    city_lod.set_lod("city")
    mats = materials.setup_all_materials()
    detail_materials.setup_detail_materials(mats)
    # glTF cannot carry a procedural node graph: with Base Color
    # LINKED to a noise ramp it writes white, which is why the
    # first export produced a colourless city.
    city_materials.flatten()

    city_terrain.build_all(mats, "EXP_Terrain")
    city_walls.build_walls(mats, "EXP_Walls")
    city_roads.build_roads(mats, "EXP_Roads")
    source = [o for o in bpy.data.objects if o.type == 'MESH']
    total_faces = sum(len(o.data.polygons) for o in source)

    # Collision stays WHOLE. Physics does not benefit from frustum culling,
    # and 29 boxes split across 40 chunks would be 40 bodies for no gain.
    cols = terrain_colliders() + wall_colliders()
    col_rec = export("emberglass_collision", cols)
    print("  %-28s %8s        %3d colliders"
          % ("emberglass_collision", "-", col_rec["colliders"]))

    chunks = city_chunk.split_many(source, CHUNK, "chunk")
    for o in source:
        o.select_set(False)

    recs = []
    for (cx, cy), objs in sorted(chunks.items()):
        faces = sum(len(o.data.polygons) for o in objs)
        if faces == 0:
            continue
        name = "emberglass_chunk_%d_%d" % (cx, cy)
        # Same reason as the building export: terrain, walls and roads land in
        # the same chunk as separate objects, and each separate object is a
        # separate draw call in game. One mesh per chunk instead of three.
        objs = join_chunk(objs, name)
        export(name, objs)
        recs.append({"name": name, "cx": cx, "cy": cy, "faces": faces})

    with open(os.path.join(OUT_DIR, "structure.json"), "w") as f:
        json.dump({
            "lod": "city",
            "chunk_size": CHUNK,
            "collision": "emberglass_collision",
            "chunks": recs,
        }, f, indent=1)

    biggest = max(recs, key=lambda r: r["faces"]) if recs else None
    print()
    print("  %d chunks, %d faces total (source %d)"
          % (len(recs), sum(r["faces"] for r in recs), total_faces))
    if biggest:
        print("  largest chunk %s at %d faces"
              % (biggest["name"], biggest["faces"]))
    print("  -> %s" % OUT_DIR)


if __name__ == "__main__":
    main()
