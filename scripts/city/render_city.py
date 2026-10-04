"""
Render the city as it stands, for eyeballing between phases.

    blender --background --python scripts/city/render_city.py -- [view] [phase]

view : "top" (plan, for overlaying on the blueprint) or "iso" (default)
phase: highest phase to build - "terrain" (default) and more as they land.

Writes renders/city/<phase>_<view>.png. Judged by eye at output resolution,
which is the only way the scale errors in this thing ever show up.
"""

import bpy
import os
import sys
from math import radians
from mathutils import Vector

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

OUT_DIR = "d:/assests/renders/city"


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def setup_world(scene):
    world = bpy.data.worlds.new("CityWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.42, 0.48, 0.58, 1.0)
    bg.inputs[1].default_value = 0.85


def setup_sun():
    d = bpy.data.lights.new("Key", type='SUN')
    d.energy = 3.1
    d.angle = radians(2.5)
    d.color = (1.0, 0.95, 0.86)
    o = bpy.data.objects.new("Key", d)
    o.rotation_euler = (radians(50), radians(15), radians(35))
    bpy.context.scene.collection.objects.link(o)

    f = bpy.data.lights.new("Fill", type='SUN')
    f.energy = 0.9
    f.color = (0.72, 0.80, 0.95)
    fo = bpy.data.objects.new("Fill", f)
    fo.rotation_euler = (radians(58), 0, radians(215))
    bpy.context.scene.collection.objects.link(fo)


def setup_render(scene, res=2200):
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = False
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Standard'
    try:
        scene.eevee.taa_render_samples = 24
    except Exception:
        pass


def frame(scene, view):
    cd = bpy.data.cameras.new("Cam")
    cd.type = 'ORTHO'
    cam = bpy.data.objects.new("Cam", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam

    x0, y0, x1, y1 = P.TERRAIN
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    span = max(x1 - x0, y1 - y0)

    if view == "top":
        cam.location = (cx, cy, 400.0)
        cam.rotation_euler = (0, 0, 0)
        cd.ortho_scale = span * 1.02
    else:
        d = 600.0
        cam.location = (cx + d, cy - d, d)
        cam.rotation_euler = (radians(54.736), 0, radians(45.0))
        # Plan diagonal sets the horizontal; plan and height ADD on the
        # vertical. Same formula as the sprite driver.
        plan = (x1 - x0 + y1 - y0) * 0.7072
        cd.ortho_scale = max(plan, plan * 0.5774 + 60.0 * 0.8165) * 1.04
    cd.clip_start = 1.0
    cd.clip_end = 3000.0


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    view = argv[0] if argv else "iso"
    phase = argv[1] if len(argv) > 1 else "terrain"

    clear_scene()
    scene = bpy.context.scene
    city_lod.set_lod("city")
    setup_world(scene)
    setup_sun()
    setup_render(scene)

    mats = materials.setup_all_materials()
    detail_materials.setup_detail_materials(mats)

    stats = city_terrain.build_all(mats)
    if phase in ("walls", "roads", "all"):
        blocks, ntowers = city_walls.build_walls(mats)
        stats["walls"] = blocks
        stats["towers"] = ntowers
    if phase in ("roads", "all"):
        pieces, rlen = city_roads.build_roads(mats)
        stats["roads"] = pieces
        stats["road_m"] = int(rlen)
    for k, v in stats.items():
        print("  %-12s %8d" % (k, v))

    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            ev = o.evaluated_get(dg)
            total += len(ev.to_mesh().polygons)
            ev.to_mesh_clear()
    print("  %-12s %8d faces" % ("TOTAL", total))

    frame(scene, view)
    os.makedirs(OUT_DIR, exist_ok=True)
    scene.render.filepath = os.path.join(OUT_DIR, "%s_%s" % (phase, view))
    bpy.ops.render.render(write_still=True)
    print("wrote", scene.render.filepath + ".png")


if __name__ == "__main__":
    main()
