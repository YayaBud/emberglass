"""
Emberglass Monuments & Variations Batch Renderer
Renders high-resolution showcases from emberglass_monuments.blend and emberglass_modular_kit.blend.
"""

import bpy
import os

def render_monuments():
    render_dir = "d:/assests/renders"
    os.makedirs(render_dir, exist_ok=True)
    
    # 1. Render from emberglass_monuments.blend
    blend_path = "d:/assests/emberglass_monuments.blend"
    print(f"Loading {blend_path}...")
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.render.film_transparent = False
    
    # Cameras to render
    renders = [
        ("Cam_Monuments_Master", "monuments_master.png", 1920, 1080),
        ("Cam_Manor", "monument_noble_manor.png", 1280, 960),
        ("Cam_Guildhouse", "monument_guildhouse.png", 1280, 960),
        ("Cam_Chapel", "monument_chapel.png", 1280, 960),
        ("Cam_Church", "monument_church.png", 1280, 960),
        ("Cam_Windmill", "monument_windmill.png", 1280, 960),
        ("Cam_Watchtower", "monument_watchtower.png", 1280, 960),
        ("Cam_Gatehouse", "monument_gatehouse.png", 1280, 960),
        ("Cam_Keep", "monument_keep.png", 1280, 960),
        ("Cam_Townhouse_Normal", "variation_normal.png", 1280, 960),
        ("Cam_Townhouse_WithStall", "variation_with_stall.png", 1280, 960),
        ("Cam_Townhouse_Damaged", "variation_damaged.png", 1280, 960),
        ("Cam_Townhouse_Ruin", "variation_ruin.png", 1280, 960),
    ]
    
    for cam_name, filename, rx, ry in renders:
        if cam_name in bpy.data.objects:
            print(f"Rendering {cam_name} -> {filename} ({rx}x{ry})...")
            scene.camera = bpy.data.objects[cam_name]
            scene.render.resolution_x = rx
            scene.render.resolution_y = ry
            scene.render.filepath = os.path.join(render_dir, filename)
            bpy.ops.render.render(write_still=True)
        else:
            print(f"WARNING: Camera {cam_name} not found!")

    # 2. Render from emberglass_modular_kit.blend
    kit_path = "d:/assests/emberglass_modular_kit.blend"
    if os.path.exists(kit_path):
        print(f"Loading {kit_path}...")
        bpy.ops.wm.open_mainfile(filepath=kit_path)
        scene = bpy.context.scene
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.film_transparent = False
        
        if "Cam_Modular_Kit" in bpy.data.objects:
            print("Rendering Cam_Modular_Kit -> modular_kit_master.png...")
            scene.camera = bpy.data.objects["Cam_Modular_Kit"]
            scene.render.filepath = os.path.join(render_dir, "modular_kit_master.png")
            bpy.ops.render.render(write_still=True)

    print("All renders completed successfully!")

if __name__ == "__main__":
    render_monuments()
