"""
Render all 16 buildings and 4 variations with dynamic bounding-box auto-framing,
transparent background, zero neighbor bleed, and no square pedestals.
"""

import bpy
from mathutils import Vector
from math import radians
import os

out_dir = "d:/assests/renders/sheet_sprites"
os.makedirs(out_dir, exist_ok=True)

def setup_perfect_camera(scene):
    cam_name = "Cam_Perfect_Isolate"
    if cam_name in bpy.data.objects:
        cam_obj = bpy.data.objects[cam_name]
    else:
        cam_data = bpy.data.cameras.new(cam_name)
        cam_data.type = 'ORTHO'
        cam_obj = bpy.data.objects.new(cam_name, cam_data)
        scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    return cam_obj

def render_blend_collections(blend_path, item_list):
    print(f"\n--- Loading {blend_path} ---")
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = True
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    
    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass
        
    cam_obj = setup_perfect_camera(scene)
    
    for col_name, fname in item_list:
        col = bpy.data.collections.get(col_name)
        if not col:
            print(f"WARNING: Collection {col_name} not found!")
            continue
            
        # 1. Hide every object in the scene from render
        for obj in bpy.data.objects:
            obj.hide_render = True
            
        # 2. Reveal lights
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT' and ('sun' in obj.name.lower() or obj.name.startswith(col_name.split('_')[-1])):
                obj.hide_render = False
                
        # 3. Unhide target building objects (exclude pedestals / curbs / pavings)
        target_objs = []
        for obj in col.objects:
            name_low = obj.name.lower()
            if any(k in name_low for k in ["pedestal", "curb", "paving", "ground_plane", "base_plane"]):
                obj.hide_render = True
            else:
                obj.hide_render = False
                if obj.type == 'MESH':
                    target_objs.append(obj)
                    
        if not target_objs:
            print(f"WARNING: No mesh objects in {col_name}")
            continue
            
        # 4. Compute 3D bounding box of building
        all_corners = [corner for o in target_objs for corner in [o.matrix_world @ Vector(c) for c in o.bound_box]]
        min_x = min(c.x for c in all_corners)
        max_x = max(c.x for c in all_corners)
        min_y = min(c.y for c in all_corners)
        max_y = max(c.y for c in all_corners)
        min_z = min(c.z for c in all_corners)
        max_z = max(c.z for c in all_corners)
        
        center = Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0))
        dim = Vector((max_x - min_x, max_y - min_y, max_z - min_z))
        
        # 5. Position camera with standard isometric orientation
        dist = 40.0
        cam_obj.location = (center.x + dist, center.y - dist, center.z + dist)
        cam_obj.rotation_euler = (radians(54.736), 0, radians(45.0))
        
        # Scale: isometric projection diagonal extent
        iso_scale = max(dim.x + dim.y, dim.z * 1.5) * 0.95
        cam_obj.data.ortho_scale = max(iso_scale, 6.0)
        
        # 6. Render
        out_file = os.path.join(out_dir, fname)
        scene.render.filepath = out_file
        print(f"Rendering {col_name} -> {fname} (center={center.x:.1f},{center.y:.1f},{center.z:.1f} scale={cam_obj.data.ortho_scale:.1f})...")
        bpy.ops.render.render(write_still=True)

def main():
    # 8 Baseline Buildings
    baseline_items = [
        ("01_Building_Cottage", "bld_cottage.png"),
        ("02_Building_Townhouse", "bld_townhouse.png"),
        ("03_Building_Tavern", "bld_tavern.png"),
        ("04_Building_Blacksmith", "bld_blacksmith.png"),
        ("05_Building_Shop", "bld_shop.png"),
        ("06_Building_Stables", "bld_stables.png"),
        ("07_Building_Warehouse", "bld_warehouse.png"),
        ("08_Building_Tenement", "bld_tenement.png"),
    ]
    render_blend_collections("d:/assests/emberglass_buildings.blend", baseline_items)
    
    # 8 Monuments + 4 Variations
    monument_items = [
        ("01_Building_Noble_Manor", "monument_noble_manor.png"),
        ("02_Building_Guildhouse", "monument_guildhouse.png"),
        ("03_Building_Chapel", "monument_chapel.png"),
        ("04_Building_Church", "monument_church.png"),
        ("05_Building_Windmill", "monument_windmill.png"),
        ("06_Building_Watchtower", "monument_watchtower.png"),
        ("07_Building_Gatehouse", "monument_gatehouse.png"),
        ("08_Building_Keep", "monument_keep.png"),
        ("09_Variation_Townhouse_Normal", "variation_normal.png"),
        ("10_Variation_Townhouse_WithStall", "variation_with_stall.png"),
        ("11_Variation_Townhouse_Damaged", "variation_damaged.png"),
        ("12_Variation_Townhouse_Ruin", "variation_ruin.png"),
    ]
    render_blend_collections("d:/assests/emberglass_monuments.blend", monument_items)
    print("\n=== ALL BUILDINGS AND MONUMENTS PERFECTLY RENDERED ===")

if __name__ == "__main__":
    main()
