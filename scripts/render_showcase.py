"""
Emberglass Renders Showcase Script
Renders high-resolution isometric preview images of each building and the master showcase.
Outputs to d:\assests\renders\
"""

import bpy
import os

def render_all():
    render_dir = "d:/assests/renders"
    os.makedirs(render_dir, exist_ok=True)
    
    scene = bpy.context.scene
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.render.film_transparent = False
    
    # Render Master Showcase
    if "Cam_Isometric_Master" in bpy.data.objects:
        scene.camera = bpy.data.objects["Cam_Isometric_Master"]
        scene.render.filepath = os.path.join(render_dir, "showcase_master.png")
        print("Rendering Master Showcase...")
        bpy.ops.render.render(write_still=True)
        
    # List of building cameras
    cameras = [
        ("Cam_Cottage", "bld_cottage.png"),
        ("Cam_Townhouse", "bld_townhouse.png"),
        ("Cam_Tavern", "bld_tavern.png"),
        ("Cam_Blacksmith", "bld_blacksmith.png"),
        ("Cam_Shop", "bld_shop.png"),
        ("Cam_Stables", "bld_stables.png"),
        ("Cam_Warehouse", "bld_warehouse.png"),
        ("Cam_Tenement", "bld_tenement.png"),
    ]
    
    for cam_name, filename in cameras:
        if cam_name in bpy.data.objects:
            print(f"Rendering {cam_name} -> {filename}...")
            scene.camera = bpy.data.objects[cam_name]
            scene.render.filepath = os.path.join(render_dir, filename)
            bpy.ops.render.render(write_still=True)
            
    print("All renders completed successfully!")

if __name__ == "__main__":
    render_all()
