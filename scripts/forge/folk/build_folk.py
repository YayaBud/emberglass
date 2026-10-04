"""Build and bake the townsfolk: ten people, 8 facings x (idle 4 + walk 8), at
both camera angles (user, 2026-09-26: "different characters npcs fill the
world ... open blender make and then use them").

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background ^
        --python D:\\assests\\scripts\\forge\\folk\\build_folk.py -- [--only=farmer,guard]

Writes `raw/<deg>/<variant>/<action>_<facing>_<ff>.png` (EEVEE, the shading)
and `id_...png` beside each (Workbench flat, the exact material per pixel),
plus `palette.json`; `pack_folk.py` turns them into the game's atlases.

Same bake as the player (memory.md): orthographic, 8 and 22 degrees, neutral
white lights (the pixel pass sorts by colour, a tinted key mis-sorts it), 128
px canvas. Not the player's framing: the player is framed to 96 px of ITS
height; a child framed that way would be as tall as a guard. Everyone here is
drawn at the world's 52 texels per metre, feet 12 px off the canvas bottom.
"""
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
r = math.radians

CANVAS_PX, TPM, FOOT_PX = 128, 52.0, 12
DEGS = (8.0, 22.0)
FACINGS = {"s": 0, "sw": 45, "w": 90, "nw": 135, "n": 180, "ne": 225, "e": 270, "se": 315}
# sit, carry and work (2026-09-30, "city life" plan, Phase 5b; the outside review: "a person
# carrying a crate is far more useful visually than five stationary NPCs"). Appended after
# walk, so the old columns keep their place; the manifest carries every column to the game.
FRAMES = {"idle": 4, "walk": 8, "sit": 2, "carry": 8, "work": 4}

SKIN = {"light": "#e8b894", "mid": "#c68a60", "dark": "#8a5836"}
# name: what they wear. Colours are the swatches the pixel pass snaps to.
VARIANTS = {
    # 2026-09-29 (user: "the npcs are ugly ... make them real"): a trim colour each
    # (collar, cuffs, hem), dyed-cloth tones to the palette spec, sleeves that
    # match the shirt unless the person wears a chemise under a dress
    "farmer": dict(skin="mid", hair=("short", "#6a4424"), hat=("straw", "#d8b868"), shirt="#c8a878",
                   sleeve="#c8a878", legs="#6a4a30", shoes="#3a2a20", tunic="#9a7a4a", belt="#4a3222",
                   trim="#7a5a32", rolled=True),
    "merchant": dict(skin="light", hair=("short", "#3a2a1e"), hat=("cap", "#3a3446"), shirt="#e0d4b8",
                     sleeve="#9a3a2c", legs="#5a5460", shoes="#2a2020", coat="#9a3a2c", belt="#c8a040",
                     trim="#d8b060", width=1.12, mous="#3a2a1e"),
    "guard": dict(skin="light", hair=("short", "#5a3a22"), hat=("helmet", "#a8aeb6"), shirt="#2e4e8e",
                  sleeve="#7a828c", legs="#5a4a38", shoes="#2a2420", tunic="#2e4e8e", belt="#3a2a1e",
                  spear="#6a4a2a", trim="#d0a848"),
    "market_woman": dict(skin="mid", hair=("bun", "#4a3020"), hat=("scarf", "#c0503c"), shirt="#6a8a52",
                         sleeve="#ece2cc", dress="#6a8a52", apron="#ece2cc", shoes="#3a2a20",
                         trim="#c0503c", chemise=True),
    "noble_lady": dict(skin="light", hair=("long", "#8a5228"), shirt="#7a3e6a", sleeve="#7a3e6a",
                       dress="#7a3e6a", belt="#d8b040", shoes="#2a2020", trim="#e0c060"),
    "old_man": dict(skin="light", hair=("ring", "#d8d4cc"), beard="#d8d4cc", shirt="#6e5e4a", sleeve="#6e5e4a",
                    robe="#6e5e4a", shoes="#2a2020", hunch=10.0, stride=0.6, trim="#9a8a6a", belt="#4a3a2a"),
    "child": dict(skin="mid", hair=("short", "#8a5a2a"), shirt="#4a70b0", sleeve="#4a70b0", legs="#6a4a30",
                  shoes="#3a2a20", tunic="#4a70b0", scale=0.68, head=1.18, trim="#e0c890", belt="#6a4a2a"),
    "blacksmith": dict(skin="dark", hair=("short", "#1e1614"), beard="#2a1e18", shirt="#8e8a84", sleeve="#8e8a84",
                       legs="#3a3432", shoes="#2a2020", apron="#6a4430", width=1.18, trim="#4a3222", rolled=True),
    "monk": dict(skin="mid", hat=("hood", "#6a5236"), shirt="#6a5236", sleeve="#6a5236", robe="#6a5236",
                 belt="#d0c090", shoes="#3a2a20", trim="#8a6e48"),
    "young_woman": dict(skin="dark", hair=("long", "#1e1614"), shirt="#3e70a0", sleeve="#ece2cc",
                        dress="#3e70a0", belt="#8a5230", shoes="#2a2020", trim="#e8d4a0", chemise=True),
    # the harbour's own people (2026-09-30, "city life" plan): a fisher in a teal smock (a cool
    # note on the quays) and a dock hand with bare forearms and a sash
    "fisher": dict(skin="light", hair=("short", "#8a8478"), beard="#8a8478", hat=("cap", "#2e4a5e"), shirt="#3e6a78",
                   sleeve="#3e6a78", legs="#4a4a52", shoes="#2a2420", tunic="#3e6a78", apron="#c8b888",
                   trim="#c8b888", belt="#3a2a1e", width=1.08),
    "dockhand": dict(skin="mid", hair=("short", "#3a2418"), hat=("scarf", "#8a3a2e"), shirt="#b8a488",
                     sleeve="#b8a488", legs="#4a4038", shoes="#2a2020", tunic="#7a6a4e", belt="#8a3a2e",
                     trim="#5a4a36", width=1.15, rolled=True),
}

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
# --preview: two views of everyone at 4x, to judge the designs before the bake
PREVIEW = "--preview" in argv
REUSE = "--reuse" in argv
# --actions=a,b: render only these actions, keep every other existing frame
ONLY = next((a[10:].split(",") for a in argv if a.startswith("--actions=")), None)
for _a in argv:
    if _a.startswith("--only="):
        VARIANTS = {k: v for k, v in VARIANTS.items() if k in _a[7:].split(",")}


def rgb(hexs):
    h = hexs.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# --------------------------------------------------------------------------
# scene, lights, camera
# --------------------------------------------------------------------------
bpy.ops.wm.read_homefile(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x = scene.render.resolution_y = CANVAS_PX
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.filter_size = 1.5
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
EEVEE = "BLENDER_EEVEE_NEXT"
try:
    scene.render.engine = EEVEE
except TypeError:
    EEVEE = "BLENDER_EEVEE"
    scene.render.engine = EEVEE
scene.eevee.taa_render_samples = 16
scene.display.shading.light = "FLAT"
scene.display.shading.color_type = "MATERIAL"
scene.display.render_aa = "OFF"
for _flag in ("show_object_outline", "show_cavity", "show_shadows", "show_specular_highlight"):
    if hasattr(scene.display.shading, _flag):
        setattr(scene.display.shading, _flag, False)


def sun(name, energy, rot):
    d = bpy.data.lights.new(name, type="SUN")
    d.energy, d.color, d.angle = energy, (1.0, 1.0, 1.0), r(12)
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    o.rotation_euler = tuple(r(a) for a in rot)


# the player's three neutral suns (bake_player.py)
sun("KeySun", 3.2, (56, 0, -34))
sun("FillSun", 1.0, (68, 0, 62))
sun("RimSun", 1.3, (-62, 0, 170))
world = bpy.data.worlds.new("FolkWorld")
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
bg.inputs[1].default_value = 0.35
scene.world = world

cd = bpy.data.cameras.new("FolkCam")
cd.type = "ORTHO"
cd.ortho_scale = CANVAS_PX / TPM
cam = bpy.data.objects.new("FolkCam", cd)
scene.collection.objects.link(cam)
scene.camera = cam


def aim(deg):
    """Feet at the origin land FOOT_PX above the canvas bottom: the target
    sits (64 - FOOT_PX) px of view-plane height above them."""
    p = r(deg)
    zc = (CANVAS_PX / 2 - FOOT_PX) / TPM / math.cos(p)
    cam.location = (0.0, -20.0 * math.cos(p), zc + 20.0 * math.sin(p))
    cam.rotation_euler = (r(90.0) - p, 0.0, 0.0)


# --------------------------------------------------------------------------
# the figure: meshes hung on empties, facing -Y (toward the camera at yaw 0)
# --------------------------------------------------------------------------
_mats = {}


def mat(hexs):
    if hexs in _mats:
        return _mats[hexs]
    m = bpy.data.materials.new("folk_" + hexs.lstrip("#"))
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    c = rgb(hexs)
    b.inputs["Base Color"].default_value = (lin(c[0]), lin(c[1]), lin(c[2]), 1.0)
    b.inputs["Roughness"].default_value = 0.85
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = 0.2
    m.diffuse_color = (lin(c[0]), lin(c[1]), lin(c[2]), 1.0)
    _mats[hexs] = m
    return m


_made = []


def empty(name, parent, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name, None)
    scene.collection.objects.link(o)
    o.parent, o.location = parent, loc
    o.rotation_mode = "XYZ"
    _made.append(o)
    return o


def part(kind, hexs, parent, loc, scale, rot=(0, 0, 0), top=0.6):
    """Spheres, cylinders and cones are unit-radius and 2 deep, so `scale` is
    their semi-axes; a cube is 1 on a side, so its `scale` is its size."""
    if kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1.0)
    elif kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=1.0, depth=2.0)
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=1.0, radius2=top, depth=2.0)
    else:
        bpy.ops.mesh.primitive_cube_add(size=1.0)
    o = bpy.context.active_object
    if kind != "cube":
        bpy.ops.object.shade_smooth()
    o.data.materials.append(mat(hexs))
    o.parent = parent
    o.location, o.scale, o.rotation_euler = loc, scale, tuple(r(a) for a in rot)
    _made.append(o)
    return o


def shade(hexs, k):
    """The same colour, k x as bright (k < 1 darker), for noses, soles, seams."""
    c = rgb(hexs)
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(x * 255 * k)))) for x in c)


def build(v):
    """One person. Returns the joints the poses drive.

    2026-09-29 (user: "the npcs are ugly ... make them real"): a head large
    enough to carry a face at 52 texels/m (eyes, brows, nose, mouth, ears, a
    blush), hair with volume and a fringe, arms with a shoulder, a bent elbow,
    a cuff and a hand, a rounded chest, collar and hem trim, tapered legs and
    rounded shoes. The joints the poses drive are unchanged; elbows are fixed."""
    k = v.get("scale", 1.0)
    wd = v.get("width", 1.0)
    skin = SKIN[v["skin"]]
    trim = v.get("trim") or shade(v["shirt"], 0.7)
    j = {}
    root = j["root"] = empty("root", None)
    root.scale = (k, k, k)
    hip_h, thigh, shin = 0.86, 0.42, 0.38
    pelvis = empty("pelvis", root, (0, 0, hip_h))
    long_skirt = v.get("dress") or v.get("robe")
    legc = v.get("legs") or long_skirt
    for side, sx in (("L", 1), ("R", -1)):
        t = j["thigh" + side] = empty("thigh" + side, pelvis, (0.085 * sx * wd, 0, 0))
        part("cone", legc, t, (0, 0, -thigh / 2), (0.066 * wd, 0.066, thigh / 2 + 0.02), top=1.18)
        kn = j["knee" + side] = empty("knee" + side, t, (0, 0, -thigh))
        part("cone", legc, kn, (0, 0, -shin / 2), (0.048 * wd, 0.048, shin / 2 + 0.02), top=1.2)
        # a rounded shoe with a darker sole
        part("sphere", v["shoes"], kn, (0, -0.045, -shin - 0.035), (0.058 * wd, 0.105, 0.05))
        part("cyl", shade(v["shoes"], 0.6), kn, (0, -0.045, -shin - 0.075), (0.056 * wd, 0.1, 0.01))
    torso = j["torso"] = empty("torso", root, (0, 0, hip_h - 0.02))
    tl = 0.5
    part("cone", v["shirt"], torso, (0, 0, tl / 2), (0.18 * wd, 0.115 * wd, tl / 2), top=1.14)
    # a rounded chest and shoulders: the cone alone read as a tube
    part("sphere", v["shirt"], torso, (0, 0, tl - 0.1), (0.205 * wd, 0.13 * wd, 0.13))
    part("cyl", trim, torso, (0, 0, tl + 0.005), (0.075, 0.065, 0.022))                     # collar
    if v.get("tunic"):
        part("cone", v["tunic"], torso, (0, 0, -0.04), (0.205 * wd, 0.14 * wd, 0.14), top=0.86)
        part("cyl", trim, torso, (0, 0, -0.17), (0.215 * wd, 0.15 * wd, 0.014))             # tunic hem
    if v.get("coat"):
        part("cone", v["coat"], torso, (0, 0, -0.1), (0.235 * wd, 0.16 * wd, 0.24), top=0.8)
        part("cube", trim, torso, (0, -0.16 * wd, 0.02), (0.035, 0.01, 0.5))                  # coat front edge
    if long_skirt:
        part("cone", long_skirt, torso, (0, 0, -0.37), (0.27 * wd, 0.22 * wd, 0.42), top=0.62)
        part("cone", trim, torso, (0, 0, -0.77), (0.275 * wd, 0.225 * wd, 0.03), top=0.97)   # hem band
    if v.get("apron"):
        if long_skirt:
            part("cube", v["apron"], torso, (0, -0.158 * wd, -0.2), (0.25 * wd, 0.02, 0.48), rot=(-6, 0, 0))
        else:
            part("cube", v["apron"], torso, (0, -0.15 * wd, 0.0), (0.26 * wd, 0.025, 0.78))
        for sx in (-1, 1):                                                                     # the straps
            part("cube", v["apron"], torso, (0.09 * sx * wd, -0.12 * wd, tl - 0.12), (0.03, 0.02, 0.2), rot=(-18, 0, 0))
    if v.get("belt"):
        part("cyl", v["belt"], torso, (0, 0, 0.04), (0.2 * wd, 0.135 * wd, 0.03))
        part("cube", "#d8b860", torso, (0, -0.135 * wd, 0.04), (0.045, 0.012, 0.04))           # buckle
    bare = v.get("rolled")
    for side, sx in (("L", 1), ("R", -1)):
        s = j["sh" + side] = empty("sh" + side, torso, (0.215 * sx * wd, 0, tl - 0.06))
        puff = 0.078 if v.get("chemise") else 0.066
        part("sphere", v["sleeve"], s, (0, 0, -0.02), (puff, puff, puff * 1.05))             # shoulder
        part("cone", v["sleeve"], s, (0, 0, -0.14), (0.058, 0.058, 0.13), top=0.82)          # upper arm
        el = empty("el" + side, s, (0, 0, -0.27))
        el.rotation_euler = (r(-14), 0, r(4 * sx))                                             # a relaxed bend
        fore = skin if bare else v["sleeve"]
        part("cone", fore, el, (0, 0, -0.12), (0.046, 0.046, 0.12), top=0.86)
        if not bare:
            part("cyl", trim, el, (0, 0, -0.22), (0.048, 0.048, 0.014))                       # cuff
        part("sphere", skin, el, (0, -0.01, -0.28), (0.042, 0.05, 0.055))                     # hand
    if v.get("spear"):
        part("cyl", v["spear"], j["shR"], (0, -0.05, -0.2), (0.018, 0.018, 1.0))
        part("cone", "#a8aeb6", j["shR"], (0, -0.05, 0.92), (0.04, 0.04, 0.12), top=0.0)
    hs = 0.145 * v.get("head", 1.0)
    head = j["head"] = empty("head", torso, (0, 0, tl + 0.05 + hs))
    part("cyl", skin, torso, (0, 0, tl + 0.03), (0.055, 0.055, 0.05))
    part("sphere", skin, head, (0, 0, 0), (hs * 0.96, hs * 0.94, hs * 1.06))
    for sx in (-1, 1):
        part("sphere", skin, head, (hs * 0.93 * sx, 0.0, -hs * 0.05), (hs * 0.16, hs * 0.1, hs * 0.24))   # ears
    # the face: eyes, brows, nose, mouth, and a warm blush on lighter skin
    brow = (v.get("hair") or (None, shade(skin, 0.45)))[1]
    for sx in (-1, 1):
        part("sphere", "#1e1818", head, (0.36 * hs * sx, -hs * 0.9, hs * 0.08), (hs * 0.11, hs * 0.07, hs * 0.14))
        part("cube", brow, head, (0.36 * hs * sx, -hs * 0.9, hs * 0.3), (hs * 0.3, hs * 0.08, hs * 0.08), rot=(0, 8 * sx, 0))
        if v["skin"] != "dark":
            part("sphere", "#e0907c", head, (0.55 * hs * sx, -hs * 0.8, -hs * 0.2), (hs * 0.16, hs * 0.06, hs * 0.1))
    part("sphere", shade(skin, 0.82), head, (0, -hs * 0.98, -hs * 0.08), (hs * 0.12, hs * 0.12, hs * 0.14))   # nose
    part("cube", "#7a3a34", head, (0, -hs * 0.93, -hs * 0.42), (hs * 0.3, hs * 0.06, hs * 0.07))            # mouth
    if v.get("beard"):
        part("sphere", v["beard"], head, (0, -hs * 0.6, -hs * 0.58), (hs * 0.66, hs * 0.46, hs * 0.58))
    if v.get("mous"):
        part("cube", v["mous"], head, (0, -hs * 0.96, -hs * 0.3), (hs * 0.5, hs * 0.08, hs * 0.1))
    hair = v.get("hair")
    if hair:
        style, hc = hair
        if style == "ring":
            part("sphere", hc, head, (0, hs * 0.32, -hs * 0.05), (hs * 1.04, hs * 0.8, hs * 0.72))
        else:
            part("sphere", hc, head, (0, hs * 0.22, hs * 0.2), (hs * 1.05, hs * 0.94, hs * 0.98))
            part("sphere", hc, head, (0, -hs * 0.62, hs * 0.58), (hs * 0.9, hs * 0.34, hs * 0.3))      # fringe
        if style == "long":
            part("sphere", hc, head, (0, hs * 0.55, -hs * 0.95), (hs * 1.05, hs * 0.55, hs * 1.55))    # falls behind
            for sx in (-1, 1):
                part("sphere", hc, head, (hs * 0.82 * sx, -hs * 0.05, -hs * 0.7), (hs * 0.26, hs * 0.3, hs * 0.9))
        if style == "bun":
            part("sphere", hc, head, (0, hs * 0.95, hs * 0.55), (hs * 0.45, hs * 0.45, hs * 0.45))
    hat = v.get("hat")
    if hat:
        kind, hc = hat
        if kind == "straw":
            part("cyl", hc, head, (0, 0, hs * 0.72), (hs * 2.2, hs * 2.2, 0.012))
            part("cyl", hc, head, (0, 0, hs * 1.0), (hs * 0.95, hs * 0.95, hs * 0.32))
            part("cyl", "#8a4a2a", head, (0, 0, hs * 0.78), (hs * 0.97, hs * 0.97, hs * 0.07))   # band
        elif kind == "cap":
            part("sphere", hc, head, (0, hs * 0.12, hs * 0.62), (hs * 1.12, hs * 1.08, hs * 0.55))
        elif kind == "helmet":
            part("sphere", hc, head, (0, 0.0, hs * 0.3), (hs * 1.12, hs * 1.1, hs * 0.95))
            part("cyl", hc, head, (0, 0, hs * 0.05), (hs * 1.25, hs * 1.22, 0.012))
        elif kind == "scarf":
            part("sphere", hc, head, (0, hs * 0.28, hs * 0.18), (hs * 1.1, hs * 0.95, hs * 1.02))
            part("sphere", hc, head, (0, hs * 1.0, -hs * 0.2), (hs * 0.35, hs * 0.3, hs * 0.35))
        elif kind == "hood":
            part("sphere", hc, head, (0, hs * 0.3, hs * 0.12), (hs * 1.22, hs * 1.08, hs * 1.15))
            part("cone", hc, torso, (0, 0.03, tl - 0.02), (0.25 * wd, 0.2 * wd, 0.1), top=0.6)
    # a crate held at the chest, drawn only in the carry frames (pose)
    crate = empty("crate", torso, (0, -0.25 * wd, 0.2))
    j["crate"] = [part("cube", "#8a6a42", crate, (0, 0, 0), (0.38, 0.26, 0.26)),
                  part("cube", "#5a4028", crate, (0, -0.132, 0.06), (0.39, 0.01, 0.04)),
                  part("cube", "#5a4028", crate, (0, -0.132, -0.07), (0.39, 0.01, 0.04))]
    # (a hoe here took the packed cell from the body's width to 130 x 128 px, the whole canvas:
    # ~330 MB of sheets; work is a bend-and-lift now, with nothing held out)
    j["hunch"] = v.get("hunch", 0.0)
    j["spear"] = bool(v.get("spear"))
    j["stride"] = v.get("stride", 1.0)
    j["k"] = k
    return j

def clear():
    for o in _made:
        bpy.data.objects.remove(o, do_unlink=True)
    _made.clear()


def spear_up(j):
    """A guard's spear arm stays down in every pose, the spear upright: tilted with the arm,
    its 2 m reached 1.08 m forward and widened every packed cell to 114 px (2026-09-30)."""
    if j["spear"]:
        j["shR"].rotation_euler = (0, 0, 0)


def pose(j, action, f):
    """Idle breathes over 4 frames; walk is one full stride over 8; sit breathes over 2
    on a bench-high seat; carry walks with a crate at the chest; work bends and lifts over 4."""
    st = j["stride"]
    j["torso"].rotation_euler = (r(j["hunch"]), 0, 0)
    j["root"].location = (0, 0, 0)
    for n in ("thighL", "thighR", "kneeL", "kneeR", "shL", "shR", "head"):
        j[n].rotation_euler = (0, 0, 0)
    for o in j["crate"]:
        o.hide_render = action != "carry"
    if action == "sit":
        # thighs level, shins down, the hips lowered to a 0.47 m seat so the shoes stay on
        # the ground line the game anchors every frame to; hands on the knees
        j["root"].location = (0, 0, -(0.86 * j["k"] - 0.47))
        for side in ("L", "R"):
            j["thigh" + side].rotation_euler = (r(-90), 0, 0)
            j["knee" + side].rotation_euler = (r(90), 0, 0)
            j["sh" + side].rotation_euler = (r(-28), 0, 0)
        spear_up(j)
        j["torso"].rotation_euler = (r(j["hunch"] + 6 + 1.5 * f), 0, 0)
        j["head"].rotation_euler = (r(-4 - 2 * f), 0, 0)
        return
    if action == "work":
        # bend and lift over four frames: down to the crop, the sack, the rope, and up
        # a guard stands easy instead: bent, the spear leaned out past the cell (50 px)
        # (a 38 deg bend put the farmer's brim 41 px out; 26 keeps the cell near the walk's)
        bend = (5, 16, 26, 14)[f] if not j["spear"] else (2, 4, 5, 3)[f]
        reach = (-16, -34, -50, -28)[f]
        squat = (8, 20, 26, 14)[f]
        for side in ("L", "R"):
            j["sh" + side].rotation_euler = (r(reach), 0, r(-5 if side == "L" else 5))
            j["thigh" + side].rotation_euler = (r(-squat), 0, 0)
            j["knee" + side].rotation_euler = (r(squat * 1.6), 0, 0)
        spear_up(j)
        j["root"].location = (0, 0, -0.012 * squat * j["k"])
        j["torso"].rotation_euler = (r(j["hunch"] + bend), 0, 0)
        j["head"].rotation_euler = (r(-bend * 0.3), 0, 0)
        return
    if action == "carry":
        # the walk's legs, the arms forward round the crate, leaning back a little
        ph = f / 8.0 * math.tau
        a, b = r(22 * st), r(38 * st)
        for side, off in (("L", 0.0), ("R", math.pi)):
            p = ph + off
            j["thigh" + side].rotation_euler = (-a * math.sin(p), 0, 0)
            j["knee" + side].rotation_euler = (b * max(0.0, math.cos(p)), 0, 0)
            j["sh" + side].rotation_euler = (r(-58), 0, r(-6 if side == "L" else 6))
        spear_up(j)
        j["root"].location = (0, 0, 0.018 * st * math.cos(2 * ph))
        j["torso"].rotation_euler = (r(j["hunch"] - 3), 0, r(2 * math.sin(ph)))
        return
    if action == "idle":
        ph = f / 4.0 * math.tau
        j["torso"].rotation_euler = (r(j["hunch"] + 1.2 * math.sin(ph)), 0, 0)
        j["shL"].rotation_euler = (r(2.0 * math.sin(ph)), 0, r(3))
        j["shR"].rotation_euler = (r(2.0 * math.sin(ph)), 0, r(-3))
        j["head"].rotation_euler = (r(-1.5 * math.sin(ph)), 0, 0)
        return
    ph = f / 8.0 * math.tau
    a, b, c = r(26 * st), r(42 * st), r(24 * st)
    for side, off in (("L", 0.0), ("R", math.pi)):
        p = ph + off
        j["thigh" + side].rotation_euler = (-a * math.sin(p), 0, 0)
        j["knee" + side].rotation_euler = (b * max(0.0, math.cos(p)), 0, 0)
        j["sh" + side].rotation_euler = (0 if side == "R" and j["spear"] else c * math.sin(p), 0, 0)
    j["root"].location = (0, 0, 0.022 * st * math.cos(2 * ph))
    j["torso"].rotation_euler = (r(j["hunch"] + 3), 0, r(4 * math.sin(ph)))


def render(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


if PREVIEW:
    scene.render.resolution_x = scene.render.resolution_y = CANVAS_PX * 4
    out = os.path.join(HERE, "preview")
    os.makedirs(out, exist_ok=True)
    aim(22.0)
    for name, v in VARIANTS.items():
        j = build(v)
        for fac, action, f in (("s", "idle", 0), ("sw", "walk", 2), ("e", "walk", 6), ("n", "walk", 0)):
            j["root"].rotation_euler = (0, 0, r(FACINGS[fac]))
            pose(j, action, f)
            render(os.path.join(out, "%s_%s.png" % (name, fac)))
        clear()
    print("FOLK preview done")
    raise SystemExit(0)

palette = {}
count = 0
for name, v in VARIANTS.items():
    j = build(v)
    palette[name] = sorted({m.name[5:] for m in _mats.values() if any(
        s.material == m for o in _made if o.type == "MESH" for s in o.material_slots)})
    for engine, prefix in ((EEVEE, ""), ("BLENDER_WORKBENCH", "id_")):
        scene.render.engine = engine
        for deg in DEGS:
            aim(deg)
            out = os.path.join(RAW, "%02d" % int(deg), name)
            os.makedirs(out, exist_ok=True)
            for fac, yaw in FACINGS.items():
                j["root"].rotation_euler = (0, 0, r(yaw))
                for action, nf in FRAMES.items():
                    for f in range(nf):
                        path = os.path.join(out, "%s%s_%s_%02d.png" % (prefix, action, fac, f))
                        # --reuse: keep an existing idle or walk frame (the extra actions
                        # added 2026-09-30 hide their crate and hoe there, so those frames
                        # are unchanged); everything else renders
                        if REUSE and action in ("idle", "walk") and os.path.exists(path):
                            continue
                        if ONLY and action not in ONLY and os.path.exists(path):
                            continue
                        pose(j, action, f)
                        render(path)
                        count += 1
    clear()
    print("FOLK built", name, flush=True)

# merged with the palette on disk, so an --only= bake keeps everyone else in the pack
_pp = os.path.join(HERE, "palette.json")
if os.path.exists(_pp):
    palette = {**json.load(open(_pp))["variants"], **palette}
with open(_pp, "w") as fh:
    json.dump({"skin": SKIN, "variants": palette, "tpm": TPM, "canvas_px": CANVAS_PX,
               "foot_px": FOOT_PX, "degs": list(DEGS), "frames": FRAMES}, fh, indent=1)
print("FOLK " + json.dumps({"variants": list(VARIANTS), "rendered": count}))
