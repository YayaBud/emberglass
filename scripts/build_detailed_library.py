"""
Build every library asset at finished-asset density and render it to a
transparent sheet sprite.

    blender --background --python scripts/build_detailed_library.py -- [stage] [filter]

stage: "buildings", "props", or "all" (default).
filter: optional substring; only assets whose sprite name contains it are built.

Each asset is built into an empty scene, rendered, and the scene is torn down
before the next one. Peak memory is therefore one asset, not the whole library -
twenty 400k-face buildings in one scene crashes Blender outright.

Output: renders/sheet_sprites_detailed/<name>.png, framed the way
build_master_presentation_sheet.py expects (transparent, isometric, trimmed).
"""

import bpy
import sys
import os
import traceback
from math import radians
from mathutils import Vector

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import materials
import detail_materials
import builder_primitives as bp

OUT_DIR = "d:/assests/renders/sheet_sprites_detailed"


# -----------------------------------------------------------------------------
# Scene rig - identical to the townhouse pass so every asset matches
# -----------------------------------------------------------------------------

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)


def setup_world(scene):
    world = bpy.data.worlds.new("Emberglass_Library_World")
    scene.world = world
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    out = nodes.new(type='ShaderNodeOutputWorld')
    bg = nodes.new(type='ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.055, 0.075, 0.105, 1.0)
    bg.inputs['Strength'].default_value = 1.0
    links.new(bg.outputs['Background'], out.inputs['Surface'])


def setup_lights():
    col = "00_Lighting"
    for nm, energy, colr, rot in [
            ("Sun_KeyLight", 5.0, (1.0, 0.90, 0.76), (50.0, 15.0, 35.0)),
            ("Sun_SkyFill", 1.45, (0.56, 0.68, 0.88), (130.0, 15.0, -145.0)),
            ("Sun_WarmBounce", 1.2, (1.0, 0.82, 0.62), (-28.0, 0.0, 30.0))]:
        ld = bpy.data.lights.new(name=nm, type='SUN')
        ld.energy = energy
        ld.color = colr
        if nm == "Sun_KeyLight":
            ld.angle = radians(6.0)
        o = bpy.data.objects.new(nm, ld)
        o.rotation_euler = tuple(radians(a) for a in rot)
        bp.link_to_collection(o, col)


def setup_vintage_grade(scene):
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    rl = tree.nodes.new("CompositorNodeRLayers")
    bal = tree.nodes.new("CompositorNodeColorBalance")
    bal.correction_method = 'LIFT_GAMMA_GAIN'
    bal.lift = (1.010, 1.000, 0.980)
    bal.gamma = (1.020, 1.000, 0.962)
    bal.gain = (1.045, 1.010, 0.945)
    hsv = tree.nodes.new("CompositorNodeHueSat")
    hsv.inputs['Saturation'].default_value = 0.92
    hsv.inputs['Value'].default_value = 1.02
    comp = tree.nodes.new("CompositorNodeComposite")
    tree.links.new(rl.outputs['Image'], bal.inputs['Image'])
    tree.links.new(bal.outputs['Image'], hsv.inputs['Image'])
    tree.links.new(hsv.outputs['Image'], comp.inputs['Image'])


def setup_render(scene, res=900):
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = True
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass
    try:
        scene.eevee.taa_render_samples = 48
        scene.eevee.use_raytracing = True
    except Exception:
        pass


def frame_and_render(scene, fname, margin=1.07):
    cd = bpy.data.cameras.new("Cam_Sprite")
    cd.type = 'ORTHO'
    cam = bpy.data.objects.new("Cam_Sprite", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Objects positioned after creation still carry a stale matrix_world until
    # the depsgraph is flushed; without this the fit measures LOCAL bounds and
    # silently crops. It cost the lighthouse its cap.
    bpy.context.view_layer.update()

    targets = [o for o in bpy.data.objects if o.type == 'MESH']
    if not targets:
        print("  EMPTY SCENE")
        return False
    corners = [o.matrix_world @ Vector(c) for o in targets for c in o.bound_box]
    mn = Vector((min(c.x for c in corners), min(c.y for c in corners),
                 min(c.z for c in corners)))
    mx = Vector((max(c.x for c in corners), max(c.y for c in corners),
                 max(c.z for c in corners)))
    centre, dim = (mn + mx) * 0.5, mx - mn

    d = 80.0
    cam.location = (centre.x + d, centre.y - d, centre.z + d)
    cam.rotation_euler = (radians(54.736), 0, radians(45.0))
    # Isometric screen extent. The plan diagonal sets the horizontal; on the
    # vertical the plan diagonal and the height ADD. max(plan, z * k) misses
    # that sum and silently crops anything tall - it took the lighthouse cap.
    plan = (dim.x + dim.y) * 0.7072
    iso = max(plan, plan * 0.5774 + dim.z * 0.8165, dim.z * 1.18)
    cam.data.ortho_scale = max(iso * margin, 1.2)

    scene.render.filepath = os.path.join(OUT_DIR, fname)
    bpy.ops.render.render(write_still=True)
    return True


# -----------------------------------------------------------------------------

def collect_tasks(stage):
    """(sprite_filename, collection_name, callable(mats, col, origin)) list."""
    tasks = []
    if stage in ("buildings", "all"):
        import library_buildings as lb
        tasks += lb.ALL_BUILDINGS
    if stage in ("props", "all"):
        import library_props as lp
        tasks += lp.ALL_PROPS
    return tasks


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stage = argv[0] if argv else "all"
    filt = argv[1] if len(argv) > 1 else None

    os.makedirs(OUT_DIR, exist_ok=True)
    tasks = collect_tasks(stage)
    if filt:
        tasks = [t for t in tasks if filt in t[0]]
    print(f"stage={stage} assets={len(tasks)}")

    ok, failed = 0, []
    for i, (fname, col, fn) in enumerate(tasks):
        print(f"[{i + 1:3d}/{len(tasks)}] {fname}")
        try:
            clear_scene()
            scene = bpy.context.scene
            setup_world(scene)
            mats = materials.setup_all_materials()
            mats = detail_materials.setup_detail_materials(mats)
            fn(mats, col, (0.0, 0.0, 0.0))
            setup_lights()
            setup_vintage_grade(scene)
            setup_render(scene)
            if frame_and_render(scene, fname + ".png"):
                ok += 1
            else:
                failed.append(fname)
        except Exception:
            failed.append(fname)
            traceback.print_exc()

    print(f"\nDONE {ok}/{len(tasks)} rendered into {OUT_DIR}")
    if failed:
        print("FAILED: " + ", ".join(failed))


if __name__ == "__main__":
    main()
