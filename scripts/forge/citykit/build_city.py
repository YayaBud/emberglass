"""Build, export and render the Emberglass city kit.

    "D:\\Blender Foundation\\Blender 4.2\\blender.exe" --background --factory-startup \\
        --python D:/assests/scripts/forge/citykit/build_city.py [-- --norender]

Exports game/assets/models/citykit/city_<name>.glb (visual + SHADOW_ proxy
+ COL_ hull, as the kit does) and city_manifest.json; renders every asset
textured (the texgen maps, nearest-filtered) on a small pedestal to
renders/citykit/, with meta.json for `sheet.py`.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import citykit as C  # noqa: E402
import cityprops as P  # noqa: E402
import newkit as N  # noqa: E402  (2026-09-30: the new assets)

K = C.K
ROOT = K.ROOT
OUT = os.path.join(ROOT, "game", "assets", "models", "citykit")
REN = os.path.join(ROOT, "renders", "citykit")
TEXDIR = os.path.join(ROOT, "game", "assets", "tex")
WET = {"quay_wall", "pier", "harbour_arm", "water_gate", "bridge_arch", "bridge_long", "ship_merchant",
       "ship_fishing", "chain_boom", "lighthouse", "bridge_covered", "dock_platform", "sluice_gate", "riverbank",
       "ship_cargo", "sailboat", "dock_barge", "mill_house"}


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons) if ob else 0


def bbox(obs):
    pts = [Vector(c) for o in obs for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


def collect():
    items = []
    for cat, fns in (("building", C.BUILDINGS), ("variant", C.VARIANTS), ("structure", C.STRUCTURES),
                     ("prop", P.PROPS), ("ship", P.SHIPS), ("building", N.BUILDINGS), ("variant", N.VARIANTS),
                     ("structure", N.STRUCTURES), ("prop", N.PROPS), ("ship", N.SHIPS)):
        for fn in fns:
            items.append((cat, fn.__name__.replace("_p", "") if fn.__name__.endswith("_p") else fn.__name__, fn))
    for name, fn in P.reused():
        items.append(("reused", name, fn))
    return items


def godot(v):
    """Blender (x, y, z) -> the GLB's / Godot's (x, z, -y)."""
    return [round(v.x, 2), round(v.z, 2), round(-v.y, 2)]


def lamp_points(ob):
    """Every lantern, lamp head, brazier or hearth in the asset: its M_Lamp
    faces clustered within 0.9 m, one area-weighted point per cluster. The
    game hangs a real light on each (they were emission only)."""
    names = [m.name for m in ob.data.materials]
    cl = []
    for p in ob.data.polygons:
        if not names or names[p.material_index] != "M_Lamp" or p.area < 1e-6:
            continue
        c = Vector(p.center)
        for k in cl:
            if (k[0] / k[1] - c).length < 0.9:
                k[0] += c * p.area
                k[1] += p.area
                break
        else:
            cl.append([c * p.area, p.area])
    return [godot(k[0] / k[1]) for k in cl]


def build_all():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    built, report = [], {}
    for cat, name, fn in collect():
        C.SMOKE.clear()
        C.FRONT.clear()
        res = fn()
        me, sh = res[0], res[1]
        extra = res[2] if len(res) > 2 else None
        vis = me.build()
        vis.name = name
        parts = [vis]
        if extra is not None:
            parts.append(extra.build())
        shob = None
        if sh is not None and sh.bm.faces:
            shob = sh.build()
            shob.name = "SHADOW_" + name
        lo, hi = bbox(parts)
        col = K.Mesh("COL_" + name)
        K.proxy_box(col, lo.x, hi.x, lo.y, hi.y, lo.z, hi.z, mat="COL")
        colob = K._nomat(col.build())
        colob.name = "COL_" + name
        export = parts + [o for o in (shob, colob) if o]
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in export:
            o.select_set(True)
        os.makedirs(OUT, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"city_{name}.glb"), export_format="GLB",
                                  use_selection=True, export_apply=True)
        for o in (shob, colob):
            if o:
                o.hide_render = True
                o.hide_viewport = True
        size = [round(hi[i] - lo[i], 2) for i in range(3)]
        report[name] = dict(cat=cat, tris=sum(tris(p) for p in parts), shadow_tris=tris(shob), size=size,
                            materials=sorted({m.name for p in parts for m in p.data.materials}),
                            lamps=lamp_points(vis), smoke=[godot(Vector(v)) for v in C.SMOKE],
                            # per storey: [storey, floor height, front wall z (Godot, +Z front), x0, x1]
                            front=[[f, round(z, 2), round(-y, 2), round(x0, 2), round(x1, 2)] for f, z, y, x0, x1 in C.FRONT])
        print(f"city: {cat:<9} {name:<18} tris {report[name]['tris']:>6}  shadow {report[name]['shadow_tris']:>4}  "
              f"size {size}")
        built.append((cat, name, parts))
    with open(os.path.join(OUT, "city_manifest.json"), "w") as f:
        json.dump(report, f, indent=1)
    return built, report


def texture_materials():
    for m in bpy.data.materials:
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        if bsdf is None:
            continue
        alb = os.path.join(TEXDIR, f"{m.name}_albedo.png")
        if os.path.exists(alb):
            img = nt.nodes.new("ShaderNodeTexImage")
            img.image = bpy.data.images.load(alb, check_existing=True)
            img.interpolation = "Closest"
            nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
            nrm = os.path.join(TEXDIR, f"{m.name}_normal.png")
            if os.path.exists(nrm):
                ni = nt.nodes.new("ShaderNodeTexImage")
                ni.image = bpy.data.images.load(nrm, check_existing=True)
                ni.image.colorspace_settings.name = "Non-Color"
                ni.interpolation = "Closest"
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nm.inputs["Strength"].default_value = 0.7
                nt.links.new(ni.outputs["Color"], nm.inputs["Color"])
                nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
            bsdf.inputs["Roughness"].default_value = 0.85
        elif m.name in ("M_Window_Warm", "M_Window_Dim"):
            c = (1.0, 0.62, 0.3) if m.name == "M_Window_Warm" else (1.0, 0.55, 0.25)
            bsdf.inputs["Emission Color"].default_value = (*c, 1)
            bsdf.inputs["Emission Strength"].default_value = 4.0 if m.name == "M_Window_Warm" else 1.6
        elif m.name == "water":
            bsdf.inputs["Base Color"].default_value = (0.05, 0.16, 0.24, 1)
            bsdf.inputs["Roughness"].default_value = 0.08
        elif m.name == "iron":
            bsdf.inputs["Metallic"].default_value = 0.6
            bsdf.inputs["Roughness"].default_value = 0.5


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = 24
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.32, 0.36, 0.46, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.55
    sc.world = w
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.2
    sun.data.color = (1.0, 0.9, 0.78)
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    cam.data.clip_end = 1000
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def shoot(sc, cam, cat, name, parts):
    lo, hi = bbox(parts)
    pad = 0.8 if cat in ("prop", "reused") else 1.5
    ped = K.Mesh("PED")
    surf = "water" if name in WET else ("grass" if name in ("crop_field", "scarecrow", "hay_stack", "barn",
                                                              "windmill") else "cobble")
    ped.box(K.T((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, -0.06 if surf != "water" else -0.3),
            (hi.x - lo.x + 2 * pad, hi.y - lo.y + 2 * pad, 0.12), surf)
    pob = ped.build()
    if surf == "water":
        pob.data.materials[0] = bpy.data.materials["water"]
    else:
        m = bpy.data.materials[surf]
        if not m.node_tree.nodes.get("Image Texture"):
            texture_one(m)
    everything = parts + [pob]
    for o in sc.objects:
        if o.type == "MESH":
            o.hide_render = o not in everything
    d = Vector((-0.62, -1.0, 0.72)).normalized()
    fwd = -d
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd)
    blo, bhi = bbox(everything)
    centre = (blo + bhi) / 2
    corners = [Vector((x, y, z)) for x in (blo.x, bhi.x) for y in (blo.y, bhi.y) for z in (blo.z, bhi.z)]
    ex = max(max(abs((p - centre).dot(right)) for p in corners), max(abs((p - centre).dot(up)) for p in corners))
    cam.data.ortho_scale = 2 * ex * 1.06
    cam.location = centre + d * 300
    cam.rotation_euler = fwd.to_track_quat("-Z", "Y").to_euler()
    res = 760 if cat in ("building", "ship", "variant", "structure") else 480
    sc.render.resolution_x = sc.render.resolution_y = res
    path = os.path.join(REN, f"{name}.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(pob)
    return path


def texture_one(m):
    pass


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    built, report = build_all()
    print(f"city: {len(built)} assets exported to {OUT}")
    if "--norender" in argv:
        return
    for name in ("grass", "cobble"):
        if name not in bpy.data.materials:
            K._material(name)
    texture_materials()
    sc, cam = setup_render()
    os.makedirs(REN, exist_ok=True)
    meta = []
    for cat, name, parts in built:
        path = shoot(sc, cam, cat, name, parts)
        meta.append(dict(cat=cat, name=name, file=path, **{k: report[name][k] for k in ("tris", "shadow_tris", "size")}))
        print("render:", name)
    with open(os.path.join(REN, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)


main()
