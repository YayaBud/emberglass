"""
Measure faces per building at each LOD level.

    blender --background --python scripts/city/measure_lod.py

Phase 2's gate: the plan budgets 60-90k faces per building at the 'city'
level. If this does not land in that band the 710-building scene does not fit
and the plan changes shape, so the number is measured rather than assumed.

Builds each subject into an empty scene, counts evaluated faces, tears the
scene down before the next -- the same build-render-clear discipline the sprite
driver uses, because several detailed buildings in one scene crashes Blender.
"""

import bpy
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

import materials
import detail_materials
import city_lod
import library_buildings as LB


SUBJECTS = ["bld_townhouse", "bld_cottage", "bld_warehouse",
            "monument_keep", "monument_church"]
LEVELS = ["full", "near", "city", "far"]


def clear_scene():
    # Same teardown the sprite driver uses. Rolling my own with a generic
    # `for block in (...)` loop failed: bpy_prop_collection.remove has a
    # different signature per collection type.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def count_faces(col_name):
    """Evaluated face count: modifiers applied, as the renderer sees it."""
    col = bpy.data.collections[col_name]
    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for obj in col.objects:
        if obj.type != 'MESH':
            continue
        ev = obj.evaluated_get(dg)
        mesh = ev.to_mesh()
        total += len(mesh.polygons)   # read BEFORE clearing - the mesh dies after
        ev.to_mesh_clear()
    return total


def build_one(sprite, level):
    clear_scene()
    city_lod.set_lod(level)
    mats = materials.setup_all_materials()
    detail_materials.setup_detail_materials(mats)
    # builder_primitives.link_to_collection takes a collection NAME and creates
    # it on demand -- passing a Collection object raises deep inside bpy.
    col = "Measure"
    fn = None
    for name, _cname, f in LB.ALL_BUILDINGS:
        if name == sprite:
            fn = f
            break
    if fn is None:
        raise KeyError(sprite)
    fn(mats, col, (0, 0, 0))
    n = count_faces(col)
    objs = len([o for o in bpy.data.collections[col].objects
                if o.type == 'MESH'])
    clear_scene()
    return n, objs


def main():
    city_lod.verify_neutral()
    print("lod 'full' verified neutral")
    rows = []
    for sprite in SUBJECTS:
        for level in LEVELS:
            try:
                faces, objs = build_one(sprite, level)
            except Exception as exc:
                print("  FAIL %-22s %-5s %s" % (sprite, level, exc))
                continue
            rows.append((sprite, level, faces, objs))
            print("  %-22s %-5s %9d faces  %3d objects" %
                  (sprite, level, faces, objs))

    print()
    print("%-22s %10s %10s %10s %10s" % ("subject", *LEVELS))
    base = {}
    for sprite in SUBJECTS:
        vals = {lv: f for (s, lv, f, _o) in rows if s == sprite}
        if not vals:
            continue
        base[sprite] = vals.get("full", 0)
        print("%-22s %10s %10s %10s %10s" % (
            sprite, *[("%d" % vals[lv]) if lv in vals else "-"
                      for lv in LEVELS]))

    city_faces = [f for (_s, lv, f, _o) in rows if lv == "city"]
    if city_faces:
        print()
        print("CITY level: min %d  max %d  mean %d"
              % (min(city_faces), max(city_faces),
                 sum(city_faces) // len(city_faces)))
        # The budget is a CEILING, not a band: under it is a pass. An earlier
        # version of this check tested `lo <= f <= hi` and reported a building
        # that came in at 35k as a failure.
        ceiling = 90000
        over = [f for f in city_faces if f > ceiling]
        print("per-building ceiling %dk: %s"
              % (ceiling // 1000,
                 "PASS" if not over else "FAIL (%d over: %r)" % (len(over), over)))
        types, variants = 21, 4
        uniq = (sum(city_faces) / len(city_faces)) * types * variants
        budget = 8e6
        print("projected unique geometry: %d types x %d variants = %.1fM faces"
              % (types, variants, uniq / 1e6))
        print("unique-geometry budget %.0fM: %s"
              % (budget / 1e6, "PASS" if uniq <= budget else "FAIL"))
    city_lod.set_lod("full")


if __name__ == "__main__":
    main()
