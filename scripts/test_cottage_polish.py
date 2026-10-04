"""
Refined Cottage matching exact orientation and layout of Reference 9:
- Gable on Left (-X)
- Front Facade on Right (-Y) with horizontal eave and front dormer
- Door, steps, lantern, shutters, and flower box on front facade
- Side awning, signpost, and barrels on left gable side
"""

import bpy
import bmesh
from math import radians, cos, sin, tan, pi
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import materials
import builder_primitives as bp

def setup_world(scene):
    world = bpy.data.worlds.new("Emberglass_World_Refined")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    
    out = nodes.new(type='ShaderNodeOutputWorld')
    bg = nodes.new(type='ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.07, 0.09, 0.12, 1.0)
    bg.inputs['Strength'].default_value = 1.0
    links.new(bg.outputs['Background'], out.inputs['Surface'])

def add_box(bm, material_index=0):
    res = bmesh.ops.create_cube(bm, size=1.0)
    vset = set(res['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = material_index
    return res['verts']

def create_ridge_roof_x(name, span_y=4.0, length_x=4.8, height=2.3, overhang_eave=0.45, overhang_gable=0.35, tile_mat=None, timber_mat=None):
    """
    Roof with ridge along X axis.
    Slopes down to -Y (front) and +Y (back).
    Gable bargeboards at -X (left) and +X (right).
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if tile_mat:
        obj.data.materials.append(tile_mat)
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    
    half_span = span_y / 2.0
    total_half_span = half_span + overhang_eave
    total_len = length_x + overhang_gable * 2.0
    
    slope_angle = radians(48.0)
    pitch_height = total_half_span * tan(slope_angle)
    slope_len = total_half_span / cos(slope_angle)
    
    num_rows = 7
    row_len = slope_len / num_rows
    
    # Slopes down to -Y (sign_y = -1) and +Y (sign_y = 1)
    for sign_y in [-1, 1]:
        dir_y = sign_y * cos(slope_angle)
        dir_z = -sin(slope_angle)
        norm_y = sign_y * sin(slope_angle)
        norm_z = cos(slope_angle)
        
        # 1. Under-decking (Timber)
        verts = add_box(bm, material_index=1)
        for v in verts:
            lx = v.co.x * (total_len - 0.06)
            ly = (v.co.y + 0.5) * slope_len
            lz = v.co.z * 0.10
            
            v.co.x = lx
            v.co.y = ly * dir_y + lz * norm_y
            v.co.z = pitch_height + ly * dir_z + lz * norm_z
            
        # 2. Stepped Tile Courses (Tile)
        tile_thick = 0.055
        for r in range(num_rows):
            verts = add_box(bm, material_index=0)
            y_start = r * row_len
            y_span = row_len * 1.35
            norm_offset = 0.06 + (r * 0.015)
            
            for v in verts:
                lx = v.co.x * (total_len + 0.02)
                ly = y_start + (v.co.y + 0.5) * y_span
                lz = norm_offset + (v.co.z + 0.5) * tile_thick
                
                v.co.x = lx
                v.co.y = ly * dir_y + lz * norm_y
                v.co.z = pitch_height + ly * dir_z + lz * norm_z

        # 3. Bargeboards at -X and +X gable ends
        barge_w = 0.18
        barge_thick = 0.09
        for end_x in [-total_len/2.0 + 0.03, total_len/2.0 - 0.03]:
            verts = add_box(bm, material_index=1)
            for v in verts:
                lx = v.co.x * barge_thick
                ly = (v.co.y + 0.5) * (slope_len + 0.1)
                lz = v.co.z * barge_w + 0.06
                
                v.co.x = lx + end_x
                v.co.y = ly * dir_y + lz * norm_y
                v.co.z = pitch_height + ly * dir_z + lz * norm_z
                
    # 4. Ridge Capping Tiles along X apex
    num_caps = int(total_len / 0.35) + 1
    cap_w = total_len / num_caps
    for c in range(num_caps):
        cx = -total_len/2.0 + (c + 0.5) * cap_w
        verts = add_box(bm, material_index=0)
        for v in verts:
            v.co.x = v.co.x * (cap_w * 1.15) + cx
            v.co.y *= 0.44
            v.co.z = v.co.z * 0.12 + pitch_height + 0.09
            
    # 5. Apex Finials at gable ends
    for end_x in [-total_len/2.0 + 0.03, total_len/2.0 - 0.03]:
        verts = add_box(bm, material_index=1)
        for v in verts:
            v.co.x = v.co.x * 0.10 + end_x
            v.co.y *= 0.14
            v.co.z = (v.co.z + 0.5) * 0.65 + pitch_height - 0.10

    bm.to_mesh(mesh)
    bm.free()
    
    bp.add_bevel_modifier(obj, width=0.014, segments=2)
    return obj, pitch_height

def create_front_dormer(name, tile_mat=None, timber_mat=None, plaster_mat=None, glow_mat=None):
    """Attic window dormer facing -Y"""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [tile_mat, timber_mat, plaster_mat, glow_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    dw, dd, dh = 1.05, 1.1, 0.95
    
    # Plaster body
    verts = add_box(bm, material_index=2)
    for v in verts:
        v.co.x *= (dw - 0.08)
        v.co.y = (v.co.y + 0.5) * dd
        v.co.z = (v.co.z + 0.5) * dh
        
    # Timber frame
    verts = add_box(bm, material_index=1)
    for v in verts:
        v.co.x *= dw
        v.co.y = v.co.y * 0.12 - 0.02
        v.co.z = (v.co.z + 0.5) * (dh + 0.1)
        
    # Glowing window pane
    verts = add_box(bm, material_index=3)
    for v in verts:
        v.co.x *= (dw * 0.68)
        v.co.y = v.co.y * 0.04 - 0.04
        v.co.z = v.co.z * 0.48 + (dh * 0.55)
        
    # Mini-pitched roof
    pitch = radians(45.0)
    half_w = dw * 0.65
    rlen = half_w / cos(pitch)
    for sign_x in [-1, 1]:
        verts = add_box(bm, material_index=0)
        for v in verts:
            lx = (v.co.x + 0.5) * rlen
            ly = (v.co.y + 0.5) * (dd * 1.15)
            lz = v.co.z * 0.06
            v.co.x = sign_x * (half_w - lx * cos(pitch))
            v.co.y = ly - 0.05
            v.co.z = dh + lx * sin(pitch) + lz
            
    bm.to_mesh(mesh)
    bm.free()
    
    bp.add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def test_cottage_exact():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in bpy.data.collections:
        bpy.data.collections.remove(col)
        
    scene = bpy.context.scene
    setup_world(scene)
    mats = materials.setup_all_materials()
    col = "Cottage_Exact"
    
    # Cottage Dimensions:
    # Length along X (Front facade) = 4.6m
    # Depth along Y (Gable side) = 3.8m
    # Front is facing -Y!
    # Left gable is facing -X!
    w_x = 4.6
    d_y = 3.8
    h_stone = 1.0
    h_wall = 2.4
    
    # 1. Pedestal Base
    base = bp.create_box("Pedestal_Base", size=(7.8, 7.2, 0.4), location=(0, 0, -0.2), material=mats["M_Stone_Base"], bevel=0.03)
    paving = bp.create_box("Pedestal_Paving", size=(7.5, 6.9, 0.06), location=(0, 0, 0.02), material=mats["M_Cobblestone"], bevel=0.01)
    bp.link_to_collection(base, col)
    bp.link_to_collection(paving, col)
    
    # 2. Lower Stone Masonry Base
    stone_body = bp.create_stone_foundation("Cottage_Stone", width=w_x, height=h_stone, depth=d_y, stone_mat=mats["M_Stone_Base"])
    bp.link_to_collection(stone_body, col)
    
    # 3. Upper Plaster Walls
    plaster = bp.create_box("Cottage_Plaster", size=(w_x - 0.06, d_y - 0.06, h_wall - h_stone), location=(0, 0, h_stone + (h_wall - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)
    
    # Timber Corner Posts
    for sx in [-w_x/2 + 0.1, w_x/2 - 0.1]:
        for sy in [-d_y/2 + 0.1, d_y/2 - 0.1]:
            p = bp.create_beam("Cottage_CornerPost", length=h_wall - h_stone, width=0.18, depth=0.18, location=(sx, sy, h_stone), material=mats["M_Timber_Dark"])
            bp.link_to_collection(p, col)
            
    # Girt timber belt
    girt_front = bp.create_box("Cottage_GirtFront", size=(w_x, 0.16, 0.16), location=(0, -d_y/2, h_stone), material=mats["M_Timber_Dark"], bevel=0.01)
    bp.link_to_collection(girt_front, col)
    girt_left = bp.create_box("Cottage_GirtLeft", size=(0.16, d_y, 0.16), location=(-w_x/2, 0, h_stone), material=mats["M_Timber_Dark"], bevel=0.01)
    bp.link_to_collection(girt_left, col)
    
    # Top plate timber
    top_front = bp.create_box("Cottage_TopFront", size=(w_x + 0.2, 0.18, 0.18), location=(0, -d_y/2, h_wall), material=mats["M_Timber_Dark"], bevel=0.01)
    bp.link_to_collection(top_front, col)

    # 4. Gable End on Left (-X) and Right (+X)
    gable_h = 2.2
    gable_left = bp.create_gable_wall("Cottage_Gable_Left", width=d_y, height=gable_h, location=(-w_x/2, 0, h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"])
    gable_left.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(gable_left, col)
    
    gable_right = bp.create_gable_wall("Cottage_Gable_Right", width=d_y, height=gable_h, location=(w_x/2, 0, h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"])
    gable_right.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(gable_right, col)

    # 5. Roof with Ridge along X, sloping down to -Y (Front) and +Y (Back)
    roof, r_peak = create_ridge_roof_x("Cottage_Roof", span_y=d_y, length_x=w_x, height=gable_h, overhang_eave=0.45, overhang_gable=0.35, tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (0, 0, h_wall)
    bp.link_to_collection(roof, col)

    # 6. Roof Dormer on Front Slope (facing -Y)
    dormer = create_front_dormer("Cottage_Dormer", tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
    dormer.location = (0.7, -1.3, h_wall + 0.7)
    bp.link_to_collection(dormer, col)

    # 7. Stone Chimney on the Left Ridge Peak
    chimney = bp.create_chimney("Cottage_Chimney", height=4.2, width=0.8, depth=0.8, stone_mat=mats["M_Stone_Base"])
    chimney.location = (-w_x/2 + 0.8, 0.4, 0.6)
    bp.link_to_collection(chimney, col)

    # 8. Front Entrance (Facing -Y)
    door = bp.create_door_unit("Cottage_Door", width=1.1, height=2.0, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    door.location = (-0.2, -d_y/2 - 0.05, 0)
    bp.link_to_collection(door, col)
    
    steps = bp.create_stone_steps("Cottage_Steps", width=1.6, depth=1.0, height=0.45, num_steps=2, stone_mat=mats["M_Stone_Base"])
    steps.location = (-0.2, -d_y/2 - 1.05, 0)
    bp.link_to_collection(steps, col)

    # 9. Front Windows (Facing -Y)
    win_r = bp.create_window_unit("Cottage_WinFront_R", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    win_r.location = (1.3, -d_y/2 - 0.05, 0.8)
    bp.link_to_collection(win_r, col)
    
    win_l = bp.create_window_unit("Cottage_WinFront_L", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=False, has_planter=False)
    win_l.location = (-1.5, -d_y/2 - 0.05, 0.8)
    bp.link_to_collection(win_l, col)

    # 10. Wall Lantern & Sign
    lantern, light = bp.create_lantern_prop("Cottage_Lantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    lantern.location = (0.55, -d_y/2 - 0.15, 1.8)
    bp.link_to_collection(lantern, col)
    bp.link_to_collection(light, col)
    
    sign = bp.create_hanging_sign("Cottage_Sign", emblem_type="tavern", timber_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"], emblem_mat=mats["M_Gold_Brass"])
    sign.location = (-w_x/2 - 0.1, -d_y/2 + 0.6, 1.8)
    sign.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(sign, col)

    # 11. Left Side Lean-To Awning with Bench and Barrels (Ref 9)
    awning = bp.create_market_stall_awning("Cottage_Awning", width=1.8, depth=1.2, height=1.7, stripe_mat=mats["M_Awning_Red"], timber_mat=mats["M_Timber_Dark"])
    awning.location = (-w_x/2 - 0.05, 0.2, 0)
    awning.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(awning, col)
    
    bar1 = bp.create_barrel("Cottage_Bar1", radius=0.36, height=0.85, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    bar1.location = (-w_x/2 - 0.5, -0.6, 0)
    bp.link_to_collection(bar1, col)
    
    crate1 = bp.create_crate("Cottage_Crate1", size=0.7, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    crate1.location = (-w_x/2 - 0.55, 1.2, 0)
    bp.link_to_collection(crate1, col)

    # 12. Camera & Lights
    cam_data = bpy.data.cameras.new("Cam_Cottage_Exact")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 9.8
    cam_obj = bpy.data.objects.new("Cam_Cottage_Exact", cam_data)
    cam_obj.location = (16.0, -16.0, 16.0)
    cam_obj.rotation_euler = (radians(54.736), 0, radians(45.0))
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    
    sun_data = bpy.data.lights.new("Sun_Key", type='SUN')
    sun_data.energy = 5.0
    sun_data.color = (1.0, 0.94, 0.86)
    sun_data.angle = radians(8.0)
    sun_obj = bpy.data.objects.new("Sun_Key", sun_data)
    sun_obj.rotation_euler = (radians(50.0), radians(15.0), radians(35.0))
    scene.collection.objects.link(sun_obj)
    
    sky_data = bpy.data.lights.new("Sun_Fill", type='SUN')
    sky_data.energy = 2.0
    sky_data.color = (0.6, 0.75, 0.95)
    sky_obj = bpy.data.objects.new("Sun_Fill", sky_data)
    sky_obj.rotation_euler = (radians(130.0), radians(15.0), radians(-145.0))
    scene.collection.objects.link(sky_obj)

    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.render.filepath = "d:/assests/renders/test_cottage_exact.png"
    print("Rendering exact cottage test...")
    bpy.ops.render.render(write_still=True)
    print("Exact cottage test rendered successfully!")

if __name__ == "__main__":
    test_cottage_exact()
