"""Build the EMBERGLASS player: parts, textures, rig, and the whole movement set.

One deterministic pass from an empty file. Re-runnable: a proportion change is an
edit to `player_parts.py` and a re-run, never a transform stacked on a previous
result.

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background ^
        --python D:\\assests\\scripts\\forge\\build_player.py

Writes `scripts/forge/player_rig.blend` and `scripts/forge/tex/player_atlas.png`,
which `bake_player.py` renders from.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import player_parts as P  # noqa: E402  (must follow the sys.path insert)

r = math.radians
px = P.p
BLEND = os.path.join(HERE, "player_rig.blend")
TEX_DIR = os.path.join(HERE, "tex")
ATLAS_PATH = os.path.join(TEX_DIR, "player_atlas.png")

# --------------------------------------------------------------------------
# 1. clean slate, the figure, and its one shared texture
# --------------------------------------------------------------------------
bpy.ops.wm.read_homefile(use_empty=True)
meshes = P.build_all()

# Every part exists and every face has a paint job queued -- pack, paint, and
# rewrite UVs BEFORE parenting/animation, which only move objects around.
atlas_rgba = P.paint_and_uv(meshes)
S = atlas_rgba.shape[0]

os.makedirs(TEX_DIR, exist_ok=True)
img = bpy.data.images.new("PlayerAtlas", width=S, height=S, alpha=True)
# Set colorspace BEFORE writing pixel data. Setting it after foreach_set (even
# to the value it already defaults to) silently corrupts what save() writes --
# confirmed by a minimal repro: same array, same foreach_set+update, the only
# difference being colorspace assigned before vs after, saved as all-black
# fully-opaque in the "after" case every time.
img.colorspace_settings.name = "sRGB"
# `atlas_rgba` row 0 is the TOP of the picture (player_paint.Atlas.compose);
# bpy's Image.pixels buffer is bottom-to-top, so flip before assigning.
flipped = np.ascontiguousarray(np.flipud(atlas_rgba).astype(np.float32) / 255.0)
img.pixels.foreach_set(flipped.ravel())
# Without this, save() at 256px+ writes the image's default black/opaque
# placeholder instead of the data foreach_set just wrote (a 4px test did not
# need it; confirmed by a minimal repro at 64/128/256/512).
img.update()
img.filepath_raw = ATLAS_PATH
img.file_format = "PNG"
img.save()


def _material(name, roughness, spec_level):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Closest"
    tex.extension = "EXTEND"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = spec_level
    return m


# Both non-metallic: there is no environment to reflect, so "metal" here is
# just a rougher/tighter highlight, not a mirror.
mat_cloth = _material("P_Cloth", 0.85, 0.35)
mat_metal = _material("P_Metal", 0.45, 0.5)
for o in meshes:
    o.data.materials.append(mat_metal if o.get("metal") else mat_cloth)

# --------------------------------------------------------------------------
# 2. the rig -- 19 bones
#
# Two segments per limb, so a knee and an elbow can break. nanobanna's hero had
# one bone per limb and every pose came out stiff-legged; at 48 px a bent knee is
# three pixels and it is still the difference between a walk and a shuffle.
# --------------------------------------------------------------------------
BONES = {
    # name:        (head px,            tail px,             parent)
    "root":        ((0, 0, 0.0),        (0, 0, 3.0),         None),
    "hips":        ((0, 0, 12.0),       (0, 0, 18.5),        "root"),
    "torso":       ((0, 0, 18.5),       (0, 0, 24.0),        "hips"),
    "chest":       ((0, 0, 24.0),       (0, 0, 28.6),        "torso"),
    "head":        ((0, 0, 28.6),       (0, 0, 38.4),        "chest"),
    "crest":       ((0, 0, 45.0),       (0, -3.5, 48.0),     "head"),
    "cape_a":      ((0, 5.2, 27.6),     (0, 5.6, 15.2),      "chest"),
    "cape_b":      ((0, 5.6, 15.2),     (0, 6.0, 5.8),       "cape_a"),
    "shoulder_l":  ((-4.2, 0, 28.0),    (-8.6, 0, 28.0),     "chest"),
    "shoulder_r":  ((4.2, 0, 28.0),     (8.6, 0, 28.0),      "chest"),
    "upperarm_l":  ((-8.6, 0, 28.0),    (-8.6, 0, 21.0),     "shoulder_l"),
    "upperarm_r":  ((8.6, 0, 28.0),     (8.6, 0, 21.0),      "shoulder_r"),
    "forearm_l":   ((-8.6, 0, 21.0),    (-8.6, 0, 13.5),     "upperarm_l"),
    "forearm_r":   ((8.6, 0, 21.0),     (8.6, 0, 13.5),      "upperarm_r"),
    "thigh_l":     ((-3.4, 0, 12.0),    (-3.4, 0, 7.0),      "hips"),
    "thigh_r":     ((3.4, 0, 12.0),     (3.4, 0, 7.0),       "hips"),
    "shin_l":      ((-3.4, 0, 7.0),     (-3.4, 0, 0.2),      "thigh_l"),
    "shin_r":      ((3.4, 0, 7.0),      (3.4, 0, 0.2),       "thigh_r"),
    "sword":       ((8.9, -0.6, 17.0),  (8.9, -0.6, 1.0),    "forearm_r"),
}

# -1 is the figure's LEFT (x < 0) and 1 its RIGHT, matching player_parts.
MAP = {
    "hips": ["P_Belt", "P_Buckle", "P_Skirt", "P_SkirtHem", "P_Satchel",
             "P_SatchelFlap", "P_Pouch", "P_Scabbard", "P_ScabbardTip"],
    "torso": ["P_Torso", "P_Baldric", "P_Medallion", "P_StrapBuckle"],
    "chest": ["P_ScarfRoll", "P_ScarfDrape_-1", "P_ScarfDrape_1", "P_ScarfKnot",
              "P_ScarfTail"],
    "head": ["P_Helm", "P_HelmCrown", "P_HelmCap", "P_Brim", "P_Face",
             "P_Cheek_-1", "P_Cheek_1", "P_Hair", "P_HairTuft_-1",
             "P_HairTuft_1"],
    "crest": ["P_Plume_a", "P_Plume_b", "P_Plume_c", "P_Plume_d"],
    "cape_a": ["P_Cape_a"],
    "cape_b": ["P_Cape_b"],
    "shoulder_l": ["P_Pauldron_-1"],
    "shoulder_r": ["P_Pauldron_1"],
    "upperarm_l": ["P_Sleeve_-1"],
    "upperarm_r": ["P_Sleeve_1"],
    "forearm_l": ["P_Cuff_-1", "P_Gauntlet_-1", "P_GauntletCuff_-1"],
    "forearm_r": ["P_Cuff_1", "P_Gauntlet_1", "P_GauntletCuff_1"],
    "thigh_l": ["P_Leg_-1"],
    "thigh_r": ["P_Leg_1"],
    "shin_l": ["P_Boot_-1", "P_Sole_-1", "P_BootFold_-1", "P_BootStrap_-1"],
    "shin_r": ["P_Boot_1", "P_Sole_1", "P_BootFold_1", "P_BootStrap_1"],
    "sword": ["P_Sword_Grip", "P_Pommel", "P_Sword_Guard", "P_Sword_Blade",
              "P_Sword_Tip"],
}

arm_data = bpy.data.armatures.new("PlayerRig")
rig = bpy.data.objects.new("PlayerRig", arm_data)
bpy.context.scene.collection.objects.link(rig)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig

bpy.ops.object.mode_set(mode="EDIT")
for n, (h, t, _p) in BONES.items():
    b = arm_data.edit_bones.new(n)
    b.head = Vector((px(h[0]), px(h[1]), px(h[2])))
    b.tail = Vector((px(t[0]), px(t[1]), px(t[2])))
for n, (_h, _t, parent) in BONES.items():
    if parent:
        arm_data.edit_bones[n].parent = arm_data.edit_bones[parent]
        arm_data.edit_bones[n].use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")

# Parent through the operator, not by assigning `parent_bone` and restoring
# `matrix_world`. The assignment route looks equivalent and is not: bone space
# has its own Y running head-to-tail, so every part came out rotated 90 degrees
# about X -- the sword ended up lying flat behind the figure at Y -20 px. The
# operator writes the parent inverse that cancels it.
def _select(objs, active):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


attached = 0
for bone, parts in MAP.items():
    objs = []
    for pn in parts:
        o = bpy.data.objects.get(pn)
        if o is None:
            raise SystemExit("MAP names a part that does not exist: " + pn)
        objs.append(o)
    _select(objs, rig)
    bpy.ops.object.mode_set(mode="POSE")
    rig.data.bones.active = rig.data.bones[bone]
    bpy.ops.object.mode_set(mode="OBJECT")
    _select(objs, rig)
    bpy.ops.object.parent_set(type="BONE", keep_transform=True)
    attached += len(objs)

all_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
unattached = [o.name for o in all_meshes if o.parent is not rig]
assert not unattached, "not attached to the rig: %s" % unattached
assert attached == len(all_meshes), "attached %d of %d" % (attached, len(all_meshes))

for pb in rig.pose.bones:
    pb.rotation_mode = "XYZ"

# --------------------------------------------------------------------------
# 3. the movement set
#
# Every value is degrees, except a 4th element on `hips`, which is a LOCATION
# along the bone's own Y (head-to-tail) in world units -- the vertical bob.
#
# Two rules run through all of it, and they are what stop the result reading as
# a puppet:
#
#   OVERLAP. `crest`, `cape_a` and `cape_b` are never posed to match the body on
#   the same frame. They are keyed one or two frames behind, so the plume and the
#   cape arrive after the torso has already moved. Everything else about this
#   figure is rigid boxes; the lag is where the life is.
#
#   ASYMMETRIC TIMING. A slash spends one frame winding up and three recovering;
#   a landing squashes on the frame of contact and takes two to stand up. Even
#   spacing reads as a machine.
# --------------------------------------------------------------------------
SPECS = {
    # ---- idle: breathing only. Weight on the back foot, crest drifting. -----
    "idle": [
        (0, {"hips": (0, 0, 0, 0.0), "torso": (0, 0, 0), "chest": (0, 0, 0),
             "head": (0, 0, 0), "crest": (0, 0, 0), "cape_a": (0, 0, 0)}),
        (1, {"crest": (-4, 0, 0)}),
        (2, {"hips": (0, 0, 0, -0.010), "torso": (1.6, 0, 0), "chest": (1.4, 0, 0),
             "head": (-1.2, 0, 0), "cape_a": (2.0, 0, 0)}),
        (3, {"crest": (5, 0, 0), "cape_b": (2.6, 0, 0)}),
        (4, {"hips": (0, 0, 0, 0.0), "torso": (0, 0, 0), "chest": (0, 0, 0),
             "head": (0, 0, 0), "crest": (0, 0, 0), "cape_a": (0, 0, 0),
             "cape_b": (0, 0, 0)}),
    ],

    # ---- walk: contact / down / pass / up, hips dropping on each contact ----
    "walk": [
        (0, {"thigh_l": (26, 0, 0), "shin_l": (-14, 0, 0),
             "thigh_r": (-22, 0, 0), "shin_r": (-6, 0, 0),
             "upperarm_l": (-16, 0, 0), "upperarm_r": (16, 0, 0),
             "forearm_l": (-10, 0, 0), "forearm_r": (-8, 0, 0),
             "hips": (0, 0, 0, -0.030), "torso": (4, 0, 0), "chest": (0, 0, 2)}),
        (2, {"thigh_l": (0, 0, 0), "shin_l": (-4, 0, 0),
             "thigh_r": (0, 0, 0), "shin_r": (-4, 0, 0),
             "upperarm_l": (0, 0, 0), "upperarm_r": (0, 0, 0),
             "forearm_l": (-6, 0, 0), "forearm_r": (-6, 0, 0),
             "hips": (0, 0, 0, 0.0), "torso": (4, 0, 0), "chest": (0, 0, 0)}),
        (3, {"cape_a": (7, 0, 0), "cape_b": (10, 0, 0), "crest": (-6, 0, 0)}),
        (4, {"thigh_l": (-22, 0, 0), "shin_l": (-6, 0, 0),
             "thigh_r": (26, 0, 0), "shin_r": (-14, 0, 0),
             "upperarm_l": (16, 0, 0), "upperarm_r": (-16, 0, 0),
             "forearm_l": (-8, 0, 0), "forearm_r": (-10, 0, 0),
             "hips": (0, 0, 0, -0.030), "torso": (4, 0, 0), "chest": (0, 0, -2)}),
        (6, {"thigh_l": (0, 0, 0), "shin_l": (-4, 0, 0),
             "thigh_r": (0, 0, 0), "shin_r": (-4, 0, 0),
             "upperarm_l": (0, 0, 0), "upperarm_r": (0, 0, 0),
             "hips": (0, 0, 0, 0.0), "torso": (4, 0, 0), "chest": (0, 0, 0)}),
        (7, {"cape_a": (7, 0, 0), "cape_b": (10, 0, 0), "crest": (-6, 0, 0)}),
        (8, {"thigh_l": (26, 0, 0), "shin_l": (-14, 0, 0),
             "thigh_r": (-22, 0, 0), "shin_r": (-6, 0, 0),
             "upperarm_l": (-16, 0, 0), "upperarm_r": (16, 0, 0),
             "hips": (0, 0, 0, -0.030), "torso": (4, 0, 0), "chest": (0, 0, 2)}),
    ],

    # ---- run: longer stride, real forward lean, both feet off on the pass ---
    "run": [
        (0, {"thigh_l": (44, 0, 0), "shin_l": (-34, 0, 0),
             "thigh_r": (-34, 0, 0), "shin_r": (-20, 0, 0),
             "upperarm_l": (-38, 0, 0), "upperarm_r": (34, 0, 0),
             "forearm_l": (-46, 0, 0), "forearm_r": (-30, 0, 0),
             "hips": (0, 0, 0, -0.040), "torso": (13, 0, 0), "chest": (4, 0, 4),
             "head": (-7, 0, 0)}),
        (2, {"thigh_l": (6, 0, 0), "shin_l": (-46, 0, 0),
             "thigh_r": (-6, 0, 0), "shin_r": (-10, 0, 0),
             "upperarm_l": (0, 0, 0), "upperarm_r": (0, 0, 0),
             "hips": (0, 0, 0, 0.022), "torso": (13, 0, 0), "chest": (4, 0, 0)}),
        (3, {"cape_a": (22, 0, 0), "cape_b": (30, 0, 0), "crest": (-14, 0, 0)}),
        (4, {"thigh_l": (-34, 0, 0), "shin_l": (-20, 0, 0),
             "thigh_r": (44, 0, 0), "shin_r": (-34, 0, 0),
             "upperarm_l": (34, 0, 0), "upperarm_r": (-38, 0, 0),
             "forearm_l": (-30, 0, 0), "forearm_r": (-46, 0, 0),
             "hips": (0, 0, 0, -0.040), "torso": (13, 0, 0), "chest": (4, 0, -4),
             "head": (-7, 0, 0)}),
        (6, {"thigh_l": (-6, 0, 0), "shin_l": (-10, 0, 0),
             "thigh_r": (6, 0, 0), "shin_r": (-46, 0, 0),
             "upperarm_l": (0, 0, 0), "upperarm_r": (0, 0, 0),
             "hips": (0, 0, 0, 0.022), "torso": (13, 0, 0), "chest": (4, 0, 0)}),
        (7, {"cape_a": (22, 0, 0), "cape_b": (30, 0, 0), "crest": (-14, 0, 0)}),
        (8, {"thigh_l": (44, 0, 0), "shin_l": (-34, 0, 0),
             "thigh_r": (-34, 0, 0), "shin_r": (-20, 0, 0),
             "upperarm_l": (-38, 0, 0), "upperarm_r": (34, 0, 0),
             "hips": (0, 0, 0, -0.040), "torso": (13, 0, 0), "chest": (4, 0, 4)}),
    ],

    # ---- jump: the anticipation crouch is frame 0 of the rise, not its own ---
    "jump_rise": [
        (0, {"hips": (0, 0, 0, -0.075), "thigh_l": (44, 0, 0), "shin_l": (-56, 0, 0),
             "thigh_r": (44, 0, 0), "shin_r": (-56, 0, 0), "torso": (16, 0, 0),
             "upperarm_l": (-26, 0, 0), "upperarm_r": (-26, 0, 0)}),
        (1, {"hips": (0, 0, 0, 0.030), "thigh_l": (-16, 0, 0), "shin_l": (-10, 0, 0),
             "thigh_r": (6, 0, 0), "shin_r": (-26, 0, 0), "torso": (2, 0, 0),
             "upperarm_l": (-60, 0, 0), "upperarm_r": (-52, 0, 0),
             "crest": (-22, 0, 0)}),
        (2, {"hips": (0, 0, 0, 0.020), "thigh_l": (-22, 0, 0), "shin_l": (-6, 0, 0),
             "thigh_r": (14, 0, 0), "shin_r": (-34, 0, 0), "torso": (-4, 0, 0),
             "upperarm_l": (-72, 0, 0), "upperarm_r": (-64, 0, 0),
             "cape_a": (-26, 0, 0), "cape_b": (-34, 0, 0), "crest": (-26, 0, 0)}),
    ],
    "fall": [
        (0, {"hips": (0, 0, 0, 0.0), "thigh_l": (-18, 0, 0), "shin_l": (-24, 0, 0),
             "thigh_r": (10, 0, 0), "shin_r": (-38, 0, 0), "torso": (-6, 0, 0),
             "upperarm_l": (-84, 0, 0), "upperarm_r": (-76, 0, 0),
             "cape_a": (-30, 0, 0), "cape_b": (-40, 0, 0), "crest": (-30, 0, 0)}),
        (1, {"thigh_l": (-12, 0, 0), "shin_l": (-30, 0, 0),
             "thigh_r": (16, 0, 0), "shin_r": (-30, 0, 0), "torso": (-9, 0, 0),
             "upperarm_l": (-92, 0, 0), "upperarm_r": (-84, 0, 0),
             "cape_a": (-36, 0, 0), "cape_b": (-46, 0, 0), "crest": (-34, 0, 0)}),
    ],
    "land": [
        (0, {"hips": (0, 0, 0, -0.090), "thigh_l": (54, 0, 0), "shin_l": (-66, 0, 0),
             "thigh_r": (54, 0, 0), "shin_r": (-66, 0, 0), "torso": (22, 0, 0),
             "head": (10, 0, 0), "upperarm_l": (-34, 0, 0),
             "upperarm_r": (-34, 0, 0)}),
        (1, {"hips": (0, 0, 0, -0.040), "thigh_l": (26, 0, 0), "shin_l": (-34, 0, 0),
             "thigh_r": (26, 0, 0), "shin_r": (-34, 0, 0), "torso": (11, 0, 0),
             "head": (5, 0, 0), "crest": (16, 0, 0), "cape_a": (14, 0, 0)}),
        (2, {"hips": (0, 0, 0, 0.0), "thigh_l": (0, 0, 0), "shin_l": (0, 0, 0),
             "thigh_r": (0, 0, 0), "shin_r": (0, 0, 0), "torso": (0, 0, 0),
             "head": (0, 0, 0), "crest": (6, 0, 0), "cape_a": (6, 0, 0),
             "cape_b": (8, 0, 0)}),
    ],

    # ---- dash: the cape is the read. The body barely changes; the cloth does --
    "dash": [
        (0, {"hips": (0, 0, 0, -0.040), "torso": (26, 0, 0), "head": (-16, 0, 0),
             "thigh_l": (36, 0, 0), "shin_l": (-30, 0, 0),
             "thigh_r": (-30, 0, 0), "shin_r": (-14, 0, 0),
             "upperarm_l": (-40, 0, 0), "upperarm_r": (46, 0, 0)}),
        (1, {"cape_a": (62, 0, 0), "cape_b": (74, 0, 0), "crest": (-30, 0, 0)}),
        (2, {"hips": (0, 0, 0, -0.030), "torso": (30, 0, 0), "head": (-18, 0, 0),
             "thigh_l": (-26, 0, 0), "shin_l": (-18, 0, 0),
             "thigh_r": (40, 0, 0), "shin_r": (-34, 0, 0),
             "upperarm_l": (44, 0, 0), "upperarm_r": (-40, 0, 0),
             "cape_a": (70, 0, 0), "cape_b": (84, 0, 0)}),
        (3, {"hips": (0, 0, 0, -0.040), "torso": (26, 0, 0),
             "cape_a": (58, 0, 0), "cape_b": (70, 0, 0), "crest": (-24, 0, 0)}),
    ],
    "air_dash": [
        (0, {"torso": (24, 0, 0), "head": (-14, 0, 0),
             "thigh_l": (34, 0, 0), "shin_l": (-52, 0, 0),
             "thigh_r": (30, 0, 0), "shin_r": (-58, 0, 0),
             "upperarm_l": (-56, 0, 0), "upperarm_r": (40, 0, 0)}),
        (1, {"cape_a": (76, 0, 0), "cape_b": (88, 0, 0), "crest": (-34, 0, 0)}),
        (2, {"torso": (28, 0, 0), "thigh_l": (38, 0, 0), "shin_l": (-56, 0, 0),
             "thigh_r": (34, 0, 0), "shin_r": (-60, 0, 0),
             "cape_a": (82, 0, 0), "cape_b": (94, 0, 0)}),
    ],

    # ---- dive: sword-down point, then the impact -----------------------------
    "dive": [
        (0, {"torso": (-18, 0, 0), "head": (12, 0, 0),
             "upperarm_r": (-150, 0, 0), "forearm_r": (30, 0, 0),
             "upperarm_l": (-60, 0, 0),
             "thigh_l": (-26, 0, 0), "shin_l": (-14, 0, 0),
             "thigh_r": (-20, 0, 0), "shin_r": (-18, 0, 0),
             "sword": (52, 0, 0)}),
        (1, {"torso": (-6, 0, 0), "upperarm_r": (-166, 0, 0),
             "sword": (74, 0, 0), "cape_a": (-56, 0, 0), "cape_b": (-70, 0, 0),
             "crest": (-40, 0, 0)}),
        (2, {"hips": (0, 0, 0, -0.080), "torso": (30, 0, 0), "head": (14, 0, 0),
             "upperarm_r": (-40, 0, 0), "forearm_r": (44, 0, 0),
             "sword": (86, 0, 0),
             "thigh_l": (52, 0, 0), "shin_l": (-64, 0, 0),
             "thigh_r": (52, 0, 0), "shin_r": (-64, 0, 0),
             "cape_a": (34, 0, 0), "cape_b": (44, 0, 0)}),
    ],

    # ---- the three-hit chain. Right to left, back again, then an overhead ----
    "attack_1": [
        (0, {"torso": (0, 0, 0), "chest": (0, 0, 0), "head": (0, 0, 0),
             "upperarm_r": (0, 0, 0), "forearm_r": (0, 0, 0), "sword": (0, 0, 0)}),
        (1, {"chest": (0, 0, -26), "torso": (-6, 0, -10), "head": (0, 0, -14),
             "upperarm_r": (-54, 0, -20), "forearm_r": (-34, 0, 0),
             "sword": (-22, 0, 0)}),
        (2, {"chest": (0, 0, 30), "torso": (6, 0, 14), "head": (0, 0, 16),
             "upperarm_r": (46, 0, 34), "forearm_r": (-10, 0, 0),
             "sword": (40, 0, 0), "crest": (-16, 0, 0)}),
        (3, {"chest": (0, 0, 22), "torso": (4, 0, 10), "upperarm_r": (34, 0, 26),
             "cape_a": (-18, 0, 0), "cape_b": (-24, 0, 0)}),
        (4, {"chest": (0, 0, 0), "torso": (0, 0, 0), "head": (0, 0, 0),
             "upperarm_r": (0, 0, 0), "forearm_r": (0, 0, 0), "sword": (0, 0, 0),
             "crest": (0, 0, 0), "cape_a": (0, 0, 0), "cape_b": (0, 0, 0)}),
    ],
    "attack_2": [
        (0, {"chest": (0, 0, 22), "torso": (4, 0, 10), "upperarm_r": (34, 0, 26),
             "forearm_r": (-10, 0, 0), "sword": (30, 0, 0)}),
        (1, {"chest": (0, 0, 34), "torso": (8, 0, 16), "head": (0, 0, 18),
             "upperarm_r": (52, 0, 40), "forearm_r": (-40, 0, 0),
             "sword": (48, 0, 0)}),
        (2, {"chest": (0, 0, -34), "torso": (-8, 0, -16), "head": (0, 0, -18),
             "upperarm_r": (-40, 0, -34), "forearm_r": (-6, 0, 0),
             "sword": (-44, 0, 0), "crest": (18, 0, 0)}),
        (3, {"chest": (0, 0, -24), "torso": (-6, 0, -10),
             "upperarm_r": (-28, 0, -24), "cape_a": (20, 0, 0),
             "cape_b": (26, 0, 0)}),
        (4, {"chest": (0, 0, 0), "torso": (0, 0, 0), "head": (0, 0, 0),
             "upperarm_r": (0, 0, 0), "forearm_r": (0, 0, 0), "sword": (0, 0, 0),
             "crest": (0, 0, 0), "cape_a": (0, 0, 0), "cape_b": (0, 0, 0)}),
    ],
    "attack_3": [
        (0, {"chest": (0, 0, -20), "torso": (-6, 0, -8),
             "upperarm_r": (-30, 0, -20), "sword": (-30, 0, 0)}),
        (1, {"torso": (-20, 0, 0), "chest": (-10, 0, 0), "head": (-12, 0, 0),
             "upperarm_r": (-160, 0, 0), "forearm_r": (-30, 0, 0),
             "sword": (-20, 0, 0), "hips": (0, 0, 0, -0.030)}),
        (2, {"torso": (-24, 0, 0), "upperarm_r": (-172, 0, 0),
             "crest": (-24, 0, 0), "cape_a": (-26, 0, 0)}),
        (3, {"torso": (34, 0, 0), "chest": (12, 0, 0), "head": (16, 0, 0),
             "upperarm_r": (34, 0, 0), "forearm_r": (26, 0, 0),
             "sword": (30, 0, 0), "hips": (0, 0, 0, -0.050),
             "thigh_l": (30, 0, 0), "shin_l": (-30, 0, 0)}),
        (4, {"torso": (26, 0, 0), "upperarm_r": (26, 0, 0),
             "crest": (26, 0, 0), "cape_a": (30, 0, 0), "cape_b": (38, 0, 0)}),
        (5, {"torso": (14, 0, 0), "chest": (6, 0, 0), "head": (8, 0, 0),
             "upperarm_r": (14, 0, 0), "forearm_r": (12, 0, 0),
             "hips": (0, 0, 0, -0.020), "thigh_l": (12, 0, 0),
             "shin_l": (-12, 0, 0)}),
        (6, {"torso": (0, 0, 0), "chest": (0, 0, 0), "head": (0, 0, 0),
             "upperarm_r": (0, 0, 0), "forearm_r": (0, 0, 0), "sword": (0, 0, 0),
             "hips": (0, 0, 0, 0.0), "thigh_l": (0, 0, 0), "shin_l": (0, 0, 0),
             "crest": (0, 0, 0), "cape_a": (0, 0, 0), "cape_b": (0, 0, 0)}),
    ],

    # ---- hurt: torso snaps back on frame 1, head arrives on frame 2 ---------
    "hurt": [
        (0, {"torso": (0, 0, 0), "head": (0, 0, 0), "upperarm_l": (0, 0, 0),
             "upperarm_r": (0, 0, 0), "hips": (0, 0, 0, 0.0)}),
        (1, {"torso": (-26, 0, 0), "head": (-6, 0, 0), "upperarm_l": (-30, 0, 0),
             "upperarm_r": (-26, 0, 0), "hips": (0, 0, 0, -0.020),
             "thigh_l": (-14, 0, 0), "thigh_r": (10, 0, 0)}),
        (2, {"torso": (-10, 0, 0), "head": (-18, 0, 0), "upperarm_l": (-14, 0, 0),
             "upperarm_r": (-12, 0, 0), "crest": (-24, 0, 0),
             "cape_a": (-20, 0, 0), "cape_b": (-26, 0, 0)}),
    ],
}

FRAMES = {"idle": 5, "walk": 9, "run": 9, "jump_rise": 3, "fall": 2, "land": 3,
          "dash": 4, "air_dash": 3, "dive": 3, "attack_1": 5, "attack_2": 5,
          "attack_3": 7, "hurt": 3}

rig.animation_data_create()
for name, keys in SPECS.items():
    act = bpy.data.actions.new("pl_" + name)
    rig.animation_data.action = act
    for f, pose in keys:
        for bone, v in pose.items():
            pb = rig.pose.bones[bone]
            pb.rotation_euler = (r(v[0]), r(v[1]), r(v[2]))
            pb.keyframe_insert("rotation_euler", frame=f)
            if len(v) == 4:
                # A bone's local Y runs head to tail, so the hips' vertical bob
                # is location[1]. Using [2] leans the figure sideways instead --
                # the bug that made nanobanna's knight fall over mid-swing.
                pb.location = (0.0, v[3], 0.0)
                pb.keyframe_insert("location", frame=f)

# Only the ACTIVE action has a real user; the rest are purged on save. Losing a
# set of actions that way costs a full rebuild.
for a in bpy.data.actions:
    a.use_fake_user = True
# Leave the rig on NO action and at frame 0. With an action still assigned, the
# depsgraph evaluates that pose, and every later measurement of the figure is a
# measurement of whichever action happened to be created last.
rig.animation_data.action = None
bpy.context.scene.frame_set(0)
for pb in rig.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)

# --------------------------------------------------------------------------
# 4. report and save
# --------------------------------------------------------------------------
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
mn = [1e9] * 3
mx = [-1e9] * 3
for o in all_meshes:
    oe = o.evaluated_get(dg)
    for c in oe.bound_box:
        w = oe.matrix_world @ Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
H = mx[2] - mn[2]

bpy.ops.wm.save_as_mainfile(filepath=BLEND)

print("BUILD " + json.dumps({
    "meshes": len(all_meshes),
    "bones": len(BONES),
    "attached": attached,
    "height_u": round(H, 4),
    "height_px": round(H / P.PX, 1),
    "width_px": round((mx[0] - mn[0]) / P.PX, 1),
    "depth_px": round((mx[1] - mn[1]) / P.PX, 1),
    "z_max_px": round(mx[2] / P.PX, 2),
    "atlas_size": S,
    "atlas": ATLAS_PATH,
    "actions": sorted(a.name for a in bpy.data.actions),
    "frames_total": sum(FRAMES.values()),
    "blend": BLEND,
}))
