"""
Render the detailed townhouse as a transparent sheet sprite, framed the way the
master sheet compositor expects. Drops it straight into renders/sheet_sprites/.

    blender --background --python scripts/render_townhouse_sprite.py
"""

import bpy
import os
from math import radians
from mathutils import Vector

BLEND = "d:/assests/emberglass_townhouse_detailed.blend"
OUT = "d:/assests/renders/sheet_sprites/bld_townhouse.png"

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.film_transparent = True
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'

# The sheet shows buildings with no ground under them
targets = []
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    drop = any(k in obj.name.lower() for k in ("cobble", "pedestal", "curb",
                                               "paving", "apron"))
    obj.hide_render = drop
    if not drop:
        targets.append(obj)

corners = [o.matrix_world @ Vector(c) for o in targets for c in o.bound_box]
mn = Vector((min(c.x for c in corners), min(c.y for c in corners),
             min(c.z for c in corners)))
mx = Vector((max(c.x for c in corners), max(c.y for c in corners),
             max(c.z for c in corners)))
centre, dim = (mn + mx) * 0.5, mx - mn

cam = scene.camera
d = 60.0
cam.location = (centre.x + d, centre.y - d, centre.z + d)
cam.rotation_euler = (radians(54.736), 0, radians(45.0))
cam.data.ortho_scale = max((dim.x + dim.y) * 0.7072, dim.z * 1.18) * 1.06

os.makedirs(os.path.dirname(OUT), exist_ok=True)
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("wrote " + OUT)
