"""
Assemble the city: terrain, fortification, circulation, and the buildings.

Buildings go in as COLLECTION INSTANCES. Each of the 21 types is built exactly
once at city LOD into a hidden source collection, and every placement is an
empty pointing at it. 710 placements therefore cost 21 unique meshes, roughly
1.2M faces, instead of ~41M.

    blender --background --python scripts/city/city_build.py -- [view]
"""

import bpy
import os
import sys
from math import radians

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

import materials
import detail_materials
import city_plan as P
import city_lod
import city_terrain
import city_walls
import city_roads
import city_blocks
import city_props
import library_buildings as LB
import library_props as LP

SRC_COLLECTION = "90_Sources"


def build_sources(mats, kinds, lod="city"):
    """Build each needed type once into a hidden source collection."""
    city_lod.set_lod(lod)
    fns = dict((n, f) for n, _c, f in LB.ALL_BUILDINGS)
    fns.update(dict((n, f) for n, _c, f in LP.ALL_PROPS))
    made = {}
    for kind in sorted(kinds):
        if kind not in fns:
            print("  MISSING generator:", kind)
            continue
        cname = "SRC_" + kind
        fns[kind](mats, cname, (0, 0, 0))
        col = bpy.data.collections.get(cname)
        if col is None:
            print("  generator produced nothing:", kind)
            continue
        made[kind] = col
    # Park the sources out of the render and out of the way.
    src = bpy.data.collections.new(SRC_COLLECTION)
    bpy.context.scene.collection.children.link(src)
    for kind, col in made.items():
        for sc in list(bpy.context.scene.collection.children):
            if sc is col:
                bpy.context.scene.collection.children.unlink(col)
        if col.name not in src.children:
            src.children.link(col)
    src.hide_render = True
    src.hide_viewport = True
    return made


def place_instances(placements, sources, col_name="60_Buildings"):
    col = bpy.data.collections.get(col_name)
    if col is None:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)
    n = 0
    for p in placements:
        src = sources.get(p.kind)
        if src is None:
            continue
        e = bpy.data.objects.new("B_%s_%d" % (p.kind, n), None)
        e.instance_type = 'COLLECTION'
        e.instance_collection = src
        e.location = (p.x, p.y, p.z)
        e.rotation_euler = (0.0, 0.0, radians(p.yaw))
        e.empty_display_size = 0.01
        col.objects.link(e)
        n += 1
    return n


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    view = argv[0] if argv else "iso"

    import render_city as R
    R.clear_scene()
    scene = bpy.context.scene
    city_lod.set_lod("city")
    R.setup_world(scene)
    R.setup_sun()
    R.setup_render(scene)

    mats = materials.setup_all_materials()
    detail_materials.setup_detail_materials(mats)

    stats = city_terrain.build_all(mats)
    blocks_n, towers = city_walls.build_walls(mats)
    roads_n, road_m = city_roads.build_roads(mats)

    placements, shortfall = city_blocks.build_all()
    kinds = set(p.kind for p in placements)
    print("  building %d source types at city LOD..." % len(kinds))
    sources = build_sources(mats, kinds)
    placed = place_instances(placements, sources)

    props = city_props.build_all()
    pkinds = set(p.kind for p in props)
    psources = build_sources(mats, pkinds - set(sources),
                             lod="city")
    psources.update(sources)
    nprops = place_instances(props, psources, col_name="70_Props")

    print("  %-14s %8d" % ("terrain", sum(stats.values())))
    print("  %-14s %8d  (%d towers)" % ("walls", blocks_n, towers))
    print("  %-14s %8d  (%.0f m)" % ("roads", roads_n, road_m))
    print("  %-14s %8d  from %d unique types"
          % ("buildings", placed, len(sources)))
    print("  %-14s %8d  from %d unique kinds"
          % ("props", nprops, len(pkinds)))
    if shortfall:
        print("  SHORTFALL:", shortfall)

    dg = bpy.context.evaluated_depsgraph_get()
    uniq = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            ev = o.evaluated_get(dg)
            uniq += len(ev.to_mesh().polygons)
            ev.to_mesh_clear()
    print("  %-14s %8d faces (unique geometry)" % ("TOTAL", uniq))

    R.frame(scene, view)
    os.makedirs(R.OUT_DIR, exist_ok=True)
    scene.render.filepath = os.path.join(R.OUT_DIR, "city_%s" % view)
    bpy.ops.render.render(write_still=True)
    print("wrote", scene.render.filepath + ".png")


if __name__ == "__main__":
    main()
