"""Workbench previews of the kit's GLBs: geometry check before Godot sees them.

    blender --background --factory-startup --python scripts/forge/kit/preview.py

Each material gets a flat colour of its own, so a misplaced part shows up as
the wrong colour in the wrong place. Two views per piece: front three-quarter
from the -Y side and back three-quarter. Writes renders/kit/<name>.png.
"""
import math
import os
import zlib

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
KIT = os.path.join(ROOT, "game", "assets", "models", "kit")
OUT = os.path.join(ROOT, "renders", "kit")
COLS = {"fieldstone": (0.45, 0.45, 0.45), "plaster": (0.9, 0.86, 0.75), "timber": (0.35, 0.22, 0.12),
        "planks": (0.55, 0.38, 0.22), "thatch": (0.8, 0.68, 0.35), "slate": (0.25, 0.3, 0.4),
        "brick": (0.6, 0.3, 0.22), "M_Window_Warm": (1.0, 0.8, 0.2), "M_Window_Dim": (0.6, 0.45, 0.2),
        "iron": (0.05, 0.05, 0.05), "moss": (0.3, 0.5, 0.2), "cobble": (0.55, 0.55, 0.5)}


def shoot(name, glb):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb)
    for ob in list(bpy.context.scene.objects):
        if ob.name.startswith(("SHADOW_", "COL_")):
            ob.hide_render = True
    for m in bpy.data.materials:
        c = COLS.get(m.name)
        if c is None:
            h = zlib.crc32(m.name.encode())
            c = ((h & 255) / 255, (h >> 8 & 255) / 255, (h >> 16 & 255) / 255)
        m.diffuse_color = (*c, 1)
    vis = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]
    pts = [o.matrix_world @ Vector(c) for o in vis for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    centre, size = (lo + hi) / 2, (hi - lo).length
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 640, 520
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    os.makedirs(OUT, exist_ok=True)
    paths = []
    for tag, az in (("front", -35), ("back", 145)):
        d = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0.55)).normalized()
        cam.location = centre + d * size * 1.25
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        p = os.path.join(OUT, f"{name}_{tag}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    return paths


for f in sorted(os.listdir(KIT)):
    if f.endswith(".glb"):
        print("preview:", shoot(f[4:-4], os.path.join(KIT, f)))
