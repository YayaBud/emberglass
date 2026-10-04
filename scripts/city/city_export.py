"""
Phase 9: export the city's building and prop types to GLB for the Godot game.

    blender --background --python scripts/city/city_export.py -- [filter]

Writes one GLB per type into a NEW folder,
`D:/nanobanna_godot/assets/models/emberglass/`. Nothing already in that
project is touched: not `assets/models/`, not the forged town, not any scene.

Each GLB carries authored `COL_*` boxes, because that is what the game's
`ModelLoader` turns into collision and what its navmesh bake parses. A trimesh
off a 58k-face building would snag agents on window sills, which that project's
own notes already record.

Colliders are derived from the built geometry rather than typed by hand: the
walls of a building are one box sized from its bounding box, inset so the
collider sits inside the facade rather than proud of it.
"""

import bpy
import os
import sys
import json
from math import radians
from mathutils import Vector

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

import materials
import detail_materials
import city_materials
import city_lod
import city_blocks as B
import city_props as PR
import library_buildings as LB
import library_props as LP

OUT_DIR = "D:/nanobanna_godot/assets/models/emberglass"

# Props that are scenery the player walks through, not obstacles.
NO_COLLIDER = {
    "grass_patch", "flowers", "grassy_ground", "plaza_tile", "vines",
    "ivy_wall", "banners", "flags", "clothesline", "awning", "balcony",
    "hanging_lantern", "wall_lantern", "dock_post",
}


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for c in o.bound_box:
            p = o.matrix_world @ Vector(c)
            lo.x, lo.y, lo.z = min(lo.x, p.x), min(lo.y, p.y), min(lo.z, p.z)
            hi.x, hi.y, hi.z = max(hi.x, p.x), max(hi.y, p.y), max(hi.z, p.z)
    return lo, hi


def add_collider(name, centre, size):
    """One COL_ box. Material is irrelevant -- it never renders."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
    ob = bpy.context.active_object
    ob.name = "COL_" + name
    ob.scale = (size[0] * 0.5, size[1] * 0.5, size[2] * 0.5)
    return ob


def make_colliders(kind, objs):
    """Derive collision from the built geometry.

    One box for the body, inset 12% on plan so it sits inside the facade
    rather than proud of it -- an agent brushing a wall should not catch on a
    windowsill that the visual mesh has and the collider should not.
    """
    lo, hi = bounds(objs)
    size = hi - lo
    if size.x <= 0 or size.y <= 0:
        return []
    inset = 0.88
    centre = ((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5,
              lo.z + size.z * 0.5)
    return [add_collider(kind, centre,
                         (size.x * inset, size.y * inset, size.z))]


def join_meshes(meshes, name):
    """Join a list of mesh objects into one. Returns [joined]."""
    if len(meshes) <= 1:
        return meshes
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    return [joined]


def export_one(mats, kind, fn, lod="city"):
    clear_scene()
    city_lod.set_lod(lod)
    m = materials.setup_all_materials()
    detail_materials.setup_detail_materials(m)
    # glTF cannot carry a procedural node graph: with Base Color
    # LINKED to a noise ramp it writes white, which is why the
    # first export produced a colourless city.
    city_materials.flatten()
    cname = "EXP_" + kind
    fn(m, cname, (0, 0, 0))
    col = bpy.data.collections.get(cname)
    if col is None:
        return None
    meshes = [o for o in col.objects if o.type == 'MESH']
    if not meshes:
        return None

    # Drop the whole thing so its feet sit on z = 0, which is what the game
    # expects when it places a piece on the ground.
    lo, hi = bounds(meshes)
    for o in meshes:
        o.location.z -= lo.z
    bpy.context.view_layer.update()

    # JOIN INTO ONE MESH. The library builds one object per component -- a
    # townhouse is ~59 of them -- which is right for a sprite render and wrong
    # for a game: each object becomes its own MultiMesh and its own draw call.
    # Unmerged, 20 types across the city's buckets produced 11,718 draw calls
    # and held the frame at 32 ms. Joining keeps every material as a slot on one
    # mesh, so the geometry and the look are unchanged and the call count falls
    # by roughly fifty times.
    meshes = join_meshes(meshes, kind)

    cols = [] if kind in NO_COLLIDER else make_colliders(kind, meshes)
    faces = sum(len(o.data.polygons) for o in meshes)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, kind + ".glb")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in meshes + cols:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB",
                              use_selection=True, export_apply=True)
    lo2, hi2 = bounds(meshes)
    return {
        "kind": kind,
        "faces": faces,
        "colliders": len(cols),
        "size": [round(hi2.x - lo2.x, 2), round(hi2.y - lo2.y, 2),
                 round(hi2.z - lo2.z, 2)],
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    filt = argv[0] if argv else ""

    placements, _ = B.build_all()
    props = PR.build_all()
    kinds = sorted(set(p.kind for p in placements)
                   | set(p.kind for p in props))
    if filt:
        kinds = [k for k in kinds if filt in k]

    fns = dict((n, f) for n, _c, f in LB.ALL_BUILDINGS)
    fns.update(dict((n, f) for n, _c, f in LP.ALL_PROPS))

    manifest = []
    for i, kind in enumerate(kinds):
        fn = fns.get(kind)
        if fn is None:
            print("  [%2d/%2d] %-22s NO GENERATOR" % (i + 1, len(kinds), kind))
            continue
        try:
            rec = export_one(None, kind, fn)
        except Exception as exc:
            print("  [%2d/%2d] %-22s FAILED %s"
                  % (i + 1, len(kinds), kind, exc))
            continue
        if rec is None:
            print("  [%2d/%2d] %-22s EMPTY" % (i + 1, len(kinds), kind))
            continue
        manifest.append(rec)
        print("  [%2d/%2d] %-22s %7d faces  %d col  %sm"
              % (i + 1, len(kinds), kind, rec["faces"], rec["colliders"],
                 rec["size"]))

    if manifest:
        mp = os.path.join(OUT_DIR, "manifest.json")
        with open(mp, "w") as f:
            json.dump({"lod": "city", "types": manifest}, f, indent=1)
        print()
        print("exported %d types, %d total faces -> %s"
              % (len(manifest), sum(r["faces"] for r in manifest), OUT_DIR))


if __name__ == "__main__":
    main()
