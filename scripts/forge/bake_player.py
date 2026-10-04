"""Bake the player rig to raw sprite frames: 8 facings x 13 actions.

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background ^
        --python D:\\assests\\scripts\\forge\\bake_player.py -- [--turnaround]

`--turnaround` renders the four reference-sheet views at 8x size instead, for
comparing the figure against the sheet before committing to 480 frames.

BAKE_DEG is 26 and it is NOT free. Decision D1: eight facings only mean anything
under a camera with a locked yaw, and a sprite that shows its own top-of-helm has
to be baked at the elevation it will be viewed from or it will not sit on the
ground. The game camera's pitch is therefore welded to this number -- changing it
costs this bake, which is one command and a few minutes.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(HERE, "player_rig.blend")
RAW = os.path.join(HERE, "raw")

r = math.radians
# 96 px of figure inside a 128 px canvas, not 48 inside 64.
#
# The reference games draw a 48 px character because they render to 640x360 and
# upscale the WHOLE frame; a desktop window showing the character 240 px tall was
# spending 5 screen pixels on every sprite texel, and at that ratio the helm, the
# visor slit and the tree emblem are two pixels each. Doubling the bake halves
# that to 2.5 and the detail comes back. The figure's WORLD size is unchanged --
# only how many texels describe it.
SPRITE_PX, CANVAS_PX = 96, 128
# 14 degrees, not 26.
#
# The reference the user supplied is a near-eye-level frame: the horizon is IN
# the picture and the buildings present their fronts, not their roofs. That only
# happens when `pitch < halfFov`, which is Law 1 of the audit and the exact
# arithmetic nanobanna failed (34.4 against a 15 half-FOV, horizon 19 degrees off
# the top of every frame it ever rendered). At 14 against a 19 half-FOV the
# horizon sits inside the frame with room to spare.
#
# 8, not 14, after measuring the frame: the share of the picture above the
# horizon is `(halfFov - pitch) / (2 * halfFov)` and NOTHING else -- raising the
# camera does not add sky, because translating up leaves an infinite plane's
# horizon exactly where it was. 14 against a 19 half-FOV gave 13 percent sky and
# it read as a strip; 8 gives 29 percent, which is the reference frame.
#
# It is still not zero: a few degrees of elevation is what shows the ground the
# character is standing on rather than a wall of grass edge-on.
BAKE_DEG = 8.0

# rig yaw, degrees. 0 faces the camera. S is toward the viewer, N away.
FACINGS = {"s": 0, "sw": 45, "w": 90, "nw": 135,
           "n": 180, "ne": 225, "e": 270, "se": 315}

FRAMES = {"idle": 5, "walk": 9, "run": 9, "jump_rise": 3, "fall": 2, "land": 3,
          "dash": 4, "air_dash": 3, "dive": 3, "attack_1": 5, "attack_2": 5,
          "attack_3": 7, "hurt": 3}

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TURNAROUND = "--turnaround" in argv
# Overrides, for baking an alternative camera angle into its own folder without
# touching the shipped bake: --deg=38 --raw=<dir> --only=idle,walk
for _a in argv:
    if _a.startswith("--deg="):
        BAKE_DEG = float(_a[6:])
    elif _a.startswith("--raw="):
        RAW = _a[6:]
    elif _a.startswith("--only="):
        FRAMES = {k: v for k, v in FRAMES.items() if k in _a[7:].split(",")}

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
rig = bpy.data.objects["PlayerRig"]
meshes = [o for o in bpy.data.objects if o.type == "MESH"]

# --------------------------------------------------------------------------
# render settings
# --------------------------------------------------------------------------
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"
px = CANVAS_PX * (8 if TURNAROUND else 1)
scene.render.resolution_x = px
scene.render.resolution_y = px
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
# Anti-aliasing stays ON here and the hardening happens in the pixel pass.
# Rendering hard-edged at 64 px throws away the sub-pixel information the
# downscale needs, and the result is a jagged silhouette that no amount of
# post can put back.
scene.render.filter_size = 1.5
scene.eevee.taa_render_samples = 64
# AgX crushes a flat 10-colour palette into mud. Standard keeps the swatches
# where player_palette.py put them, which is what the quantiser expects.
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

# --------------------------------------------------------------------------
# camera: orthographic, at the bake elevation, framing the figure at 48 px
# inside a 64 px canvas
# --------------------------------------------------------------------------
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
mn = [1e9] * 3
mx = [-1e9] * 3
for o in meshes:
    oe = o.evaluated_get(dg)
    for c in oe.bound_box:
        w = oe.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
H = mx[2] - mn[2]
D = mx[1] - mn[1]
W = mx[0] - mn[0]

# At a tilted camera the figure's own depth adds to its screen height: a 26 deg
# view of a 15 px deep figure reads ~6 px taller than the figure is. Frame on
# the projected height, or the helm crest walks out of the canvas as soon as the
# rig yaws to a 3/4 view.
P = r(BAKE_DEG)
proj_h = H * math.cos(P) + max(D, W) * math.sin(P)
cd = bpy.data.cameras.new("BakeCam")
cd.type = "ORTHO"
cd.ortho_scale = proj_h * CANVAS_PX / SPRITE_PX
cam = bpy.data.objects.new("BakeCam", cd)
scene.collection.objects.link(cam)
# Aim at the figure's own centre, not the origin: the feet sit at z=0 and the
# crest at 48 px, so the origin is at the bottom edge of the frame.
mid = Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2))
dist = 12.0
cam.location = mid + Vector((0.0, -dist * math.cos(P), dist * math.sin(P)))
cam.rotation_euler = (r(90.0) - P, 0.0, 0.0)
scene.camera = cam

# --------------------------------------------------------------------------
# light: one warm key, a cool fill, and a rim. Matches the reference sheet's
# own treatment -- the figure is lit from the front-left with a cold bounce on
# the right, which is what keeps the green and the steel apart at 48 px.
# --------------------------------------------------------------------------
def _sun(name, energy, rot, colour):
    d = bpy.data.lights.new(name, type="SUN")
    d.energy = energy
    d.color = colour
    d.angle = r(12)
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    o.rotation_euler = tuple(r(a) for a in rot)
    return o


# The lights are NEUTRAL WHITE, and that is a hard requirement rather than a
# taste call. The pixel pass decides which swatch a pixel belongs to from its
# HUE, so any tint in the key light moves the material's hue and the quantiser
# mis-sorts it: a warm key at 0.94/0.84 dragged the lit face of the green tunic
# far enough toward yellow that it came out as gold, and the figure packed with
# gold speckle sprayed across its chest. Colour the world in the game's
# lighting, never in the bake.
_sun("KeySun", 3.2, (56, 0, -34), (1.0, 1.0, 1.0))
_sun("FillSun", 1.0, (68, 0, 62), (1.0, 1.0, 1.0))
_sun("RimSun", 1.3, (-62, 0, 170), (1.0, 1.0, 1.0))

world = bpy.data.worlds.new("BakeWorld")
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
bg.inputs[1].default_value = 0.35
scene.world = world

rig.rotation_mode = "XYZ"
os.makedirs(RAW, exist_ok=True)


def render_to(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


count = 0
if TURNAROUND:
    # The reference sheet's own four views, in its own order.
    out = os.path.join(HERE, "turnaround")
    os.makedirs(out, exist_ok=True)
    rig.animation_data.action = bpy.data.actions["pl_idle"]
    scene.frame_set(0)
    for name, yaw in (("front", 0), ("three_quarter", 35),
                      ("back", 180), ("three_quarter_sword", 325)):
        rig.rotation_euler = (0, 0, r(yaw))
        render_to(os.path.join(out, "player_%s.png" % name))
        count += 1
else:
    for action, nf in FRAMES.items():
        rig.animation_data.action = bpy.data.actions["pl_" + action]
        for fac, yaw in FACINGS.items():
            rig.rotation_euler = (0, 0, r(yaw))
            for f in range(nf):
                scene.frame_set(f)
                render_to(os.path.join(
                    RAW, "player_%s_%s_%02d.png" % (action, fac, f)))
                count += 1

rig.rotation_euler = (0, 0, 0)

print("BAKE " + json.dumps({
    "mode": "turnaround" if TURNAROUND else "full",
    "rendered": count,
    "bake_deg": BAKE_DEG,
    "height_u": round(H, 4),
    "projected_h_u": round(proj_h, 4),
    "ortho_scale": round(cd.ortho_scale, 4),
    "canvas_px": px,
}))
