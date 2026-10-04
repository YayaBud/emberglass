"""
Render isolated buildings and monuments with transparent background,
no square pedestals, no neighbor bleed, and rich vibrant colors.
"""

import bpy
import os

out_dir = "d:/assests/renders/sheet_sprites"
os.makedirs(out_dir, exist_ok=True)

def render_isolated_baseline_buildings():
    blend_path = "d:/assests/emberglass_buildings.blend"
    print(f"Loading {blend_path} for isolated renders...")
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = True
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    
    # Enhanced color management for vibrant rich tones
    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass
        
    bld_map = [
        ("01_Building_Cottage", "Cam_Cottage", "bld_cottage.png", 6.8),
        ("02_Building_Townhouse", "Cam_Townhouse", "bld_townhouse.png", 8.2),
        ("03_Building_Tavern", "Cam_Tavern", "bld_tavern.png", 9.6),
        ("04_Building_Blacksmith", "Cam_Blacksmith", "bld_blacksmith.png", 7.8),
        ("05_Building_Shop", "Cam_Shop", "bld_shop.png", 7.8),
        ("06_Building_Stables", "Cam_Stables", "bld_stables.png", 8.2),
        ("07_Building_Warehouse", "Cam_Warehouse", "bld_warehouse.png", 8.2),
        ("08_Building_Tenement", "Cam_Tenement", "bld_tenement.png", 9.2),
    ]
    
    building_cols = [b[0] for b in bld_map]
    
    for col_name, cam_name, fname, oscale in bld_map:
        print(f"Isolating {col_name} -> {fname}...")
        # Hide all other building collections
        for c in bpy.data.collections:
            if c.name in building_cols:
                is_target = (c.name == col_name)
                for obj in c.objects:
                    # Hide pedestal/ground squares
                    if "pedestal" in obj.name.lower() or "paving" in obj.name.lower() or "curb" in obj.name.lower():
                        obj.hide_render = True
                    else:
                        obj.hide_render = not is_target
                        
        if cam_name in bpy.data.objects:
            cam = bpy.data.objects[cam_name]
            scene.camera = cam
            cam.data.type = 'ORTHO'
            cam.data.ortho_scale = oscale
            scene.render.filepath = os.path.join(out_dir, fname)
            bpy.ops.render.render(write_still=True)
        else:
            print(f"WARNING: Camera {cam_name} not found!")

def render_isolated_monuments_and_variations():
    blend_path = "d:/assests/emberglass_monuments.blend"
    print(f"Loading {blend_path} for isolated renders...")
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
        
    mon_map = [
        ("01_Building_Noble_Manor", "Cam_Manor", "monument_noble_manor.png", 10.5),
        ("02_Building_Guildhouse", "Cam_Guildhouse", "monument_guildhouse.png", 9.8),
        ("03_Building_Chapel", "Cam_Chapel", "monument_chapel.png", 8.8),
        ("04_Building_Church", "Cam_Church", "monument_church.png", 12.2),
        ("05_Building_Windmill", "Cam_Windmill", "monument_windmill.png", 10.5),
        ("06_Building_Watchtower", "Cam_Watchtower", "monument_watchtower.png", 11.2),
        ("07_Building_Gatehouse", "Cam_Gatehouse", "monument_gatehouse.png", 11.8),
        ("08_Building_Keep", "Cam_Keep", "monument_keep.png", 14.5),
        ("09_Variation_Townhouse_Normal", "Cam_Townhouse_Normal", "variation_normal.png", 6.8),
        ("10_Variation_Townhouse_WithStall", "Cam_Townhouse_WithStall", "variation_with_stall.png", 7.2),
        ("11_Variation_Townhouse_Damaged", "Cam_Townhouse_Damaged", "variation_damaged.png", 6.8),
        ("12_Variation_Townhouse_Ruin", "Cam_Townhouse_Ruin", "variation_ruin.png", 6.2),
    ]
    
    mon_cols = [m[0] for m in mon_map]
    
    # Also hide any loose empties or cursor meshes in master collection
    for obj in bpy.data.objects:
        if obj.name.startswith("Cam_") or obj.name.startswith("Sun_"):
            continue
        if obj.type == 'EMPTY' or 'gizmo' in obj.name.lower():
            obj.hide_render = True
            
    for col_name, cam_name, fname, oscale in mon_map:
        print(f"Isolating {col_name} -> {fname}...")
        for c in bpy.data.collections:
            if c.name in mon_cols:
                is_target = (c.name == col_name)
                for obj in c.objects:
                    if "pedestal" in obj.name.lower() or "paving" in obj.name.lower() or "curb" in obj.name.lower():
                        obj.hide_render = True
                    else:
                        obj.hide_render = not is_target
                        
        if cam_name in bpy.data.objects:
            cam = bpy.data.objects[cam_name]
            scene.camera = cam
            cam.data.type = 'ORTHO'
            cam.data.ortho_scale = oscale
            scene.render.filepath = os.path.join(out_dir, fname)
            bpy.ops.render.render(write_still=True)
        else:
            print(f"WARNING: Camera {cam_name} not found!")

def main():
    print("=== RENDERING ISOLATED HIGH-QUALITY BUILDINGS & MONUMENTS ===")
    render_isolated_baseline_buildings()
    render_isolated_monuments_and_variations()
    print("=== ISOLATED RENDERS COMPLETE ===")

if __name__ == "__main__":
    main()
