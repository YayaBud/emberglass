"""
Emberglass 8 Assembled Showcase Buildings Generator for Blender 4.2 LTS
Direct 1:1 reproduction of the Emberglass reference sheets.
Dual-axis roof systems, precise isometric elevations, warm glowing windows,
and authentic medieval street props.
"""

import bpy
import sys
import os
from math import radians, cos, sin, tan, pi
from mathutils import Vector, Euler

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import materials
import builder_primitives as bp

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in bpy.data.collections:
        bpy.data.collections.remove(col)

def setup_world(scene):
    world = bpy.data.worlds.new("Emberglass_Showcase_World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    
    out = nodes.new(type='ShaderNodeOutputWorld')
    bg = nodes.new(type='ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.055, 0.075, 0.105, 1.0)  # Emberglass dark vignette
    bg.inputs['Strength'].default_value = 1.0
    links.new(bg.outputs['Background'], out.inputs['Surface'])

def create_pedestal(name, width, depth, height=0.4, origin=(0,0,0), mats=None, col_name=None):
    base = bp.create_box(name + "_Curb", size=(width, depth, height), location=(origin[0], origin[1], origin[2] - height/2.0), material=mats["M_Stone_Base"], bevel=0.03)
    pave = bp.create_box(name + "_Paving", size=(width - 0.2, depth - 0.2, 0.06), location=(origin[0], origin[1], origin[2] + 0.02), material=mats["M_Cobblestone"], bevel=0.01)
    if col_name:
        bp.link_to_collection(base, col_name)
        bp.link_to_collection(pave, col_name)
    return base, pave

# -------------------------------------------------------------
# 1. bld_cottage (Single House - Ref 9)
# Gable faces -Y (Lower-Left), Roof Slope & Door face +X (Lower-Right)
# -------------------------------------------------------------
def build_cottage(origin=(0, 0, 0), mats=None):
    col = "01_Building_Cottage"
    ox, oy, oz = origin
    w_x, d_y = 4.2, 5.0
    h_stone, h_wall = 0.9, 2.6
    
    create_pedestal("Cottage_Pedestal", 9.6, 9.6, origin=origin, mats=mats, col_name=col)
    
    # Foundation with Corner Quoins
    stone = bp.create_stone_foundation("Cottage_Stone", width=w_x, height=h_stone, depth=d_y, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone, col)
    
    plaster = bp.create_box("Cottage_Plaster", size=(w_x - 0.06, d_y - 0.06, h_wall - h_stone), location=(ox, oy, oz + h_stone + (h_wall - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)
    
    # Timber posts and girts
    for sx in [-w_x/2 + 0.1, w_x/2 - 0.1]:
        for sy in [-d_y/2 + 0.1, d_y/2 - 0.1]:
            p = bp.create_beam("Cottage_Post", length=h_wall - h_stone, width=0.18, depth=0.18, location=(ox + sx, oy + sy, oz + h_stone), material=mats["M_Timber_Dark"])
            bp.link_to_collection(p, col)
            
    top_x = bp.create_box("Cottage_Top_R", size=(0.18, d_y + 0.2, 0.18), location=(ox + w_x/2, oy, oz + h_wall), material=mats["M_Timber_Dark"], bevel=0.01)
    bp.link_to_collection(top_x, col)

    # Diagonal half-timber wall struts on side facade (+X)
    strut1 = bp.create_wall_strut("Cottage_Strut1", (ox + w_x/2, oy - d_y/2 + 0.3, oz + h_stone), (ox + w_x/2, oy - 1.2, oz + h_wall - 0.1), width=0.12, depth=0.16, timber_mat=mats["M_Timber_Dark"])
    bp.link_to_collection(strut1, col)
    strut2 = bp.create_wall_strut("Cottage_Strut2", (ox + w_x/2, oy + d_y/2 - 0.3, oz + h_stone), (ox + w_x/2, oy + 2.0, oz + h_wall - 0.1), width=0.12, depth=0.16, timber_mat=mats["M_Timber_Dark"])
    bp.link_to_collection(strut2, col)

    # Roof (Ridge along Y, slopes to -X and +X)
    roof, pitch_h = bp.create_ridge_roof_y("Cottage_Roof", span_x=w_x, length_y=d_y, overhang_eave=0.40, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(roof, col)

    # Exposed Rafter Tails under roof eaves
    rafters = bp.create_rafter_tails("Cottage_Rafters", span=w_x, length=d_y, axis="y", overhang_eave=0.40, spacing=0.55, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(rafters, col)

    # Gables at -Y (Front) and +Y (Back) with framed principal rafters and struts
    gable_f = bp.create_gable_wall("Cottage_Gable_F", width=w_x, height=pitch_h, location=(ox, oy - d_y/2, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    bp.link_to_collection(gable_f, col)
    
    gable_b = bp.create_gable_wall("Cottage_Gable_B", width=w_x, height=pitch_h, location=(ox, oy + d_y/2, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_b.rotation_euler = (0, 0, radians(180))
    bp.link_to_collection(gable_b, col)

    # Stone Chimney with Molded Cap, Flue Pot, and Stylized 3D Smoke Puffs
    chimney = bp.create_chimney("Cottage_Chimney", height=3.6, width=0.75, depth=0.75, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"], has_smoke=True, flue_pot=True)
    chimney.location = (ox, oy + 0.8, oz + h_wall + pitch_h - 1.2)
    bp.link_to_collection(chimney, col)

    # Gable Facade (-Y, Lower-Left): Window, Bench, Railing Fence, Flowers
    win_f = bp.create_window_unit("Cottage_Win_F", width=0.9, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    win_f.location = (ox - 0.9, oy - d_y/2, oz + 0.9)
    bp.link_to_collection(win_f, col)
    
    bench = bp.create_wood_bench("Cottage_Bench", width=1.3, depth=0.45, height=0.50, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"])
    bench.location = (ox - 0.9, oy - d_y/2 - 0.45, oz)
    bp.link_to_collection(bench, col)
    
    fence = bp.create_fence_section("Cottage_Fence", length=2.2, height=0.85, timber_mat=mats["M_Timber_Dark"])
    fence.location = (ox - 2.6, oy - d_y/2 - 0.35, oz)
    bp.link_to_collection(fence, col)
    
    pot1 = bp.create_flowerpot_prop("Cottage_Pot1", radius=0.22, height=0.35, stone_mat=mats["M_Stone_Base"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"])
    pot1.location = (ox + 0.9, oy - d_y/2 - 0.30, oz)
    bp.link_to_collection(pot1, col)

    # Street Lantern on wooden post at front-left
    lamp_post = bp.create_beam("Cottage_LampPost", length=2.5, width=0.14, depth=0.14, location=(ox - 2.4, oy - d_y/2 - 0.8, oz), material=mats["M_Timber_Dark"])
    bp.link_to_collection(lamp_post, col)
    lantern_f, light_f = bp.create_lantern_prop("Cottage_PostLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    lantern_f.location = (ox - 2.4, oy - d_y/2 - 0.8, oz + 2.3)
    bp.link_to_collection(lantern_f, col)
    bp.link_to_collection(light_f, col)

    # Side Facade (+X, Lower-Right): Entrance Door, Windows, Planter, Dormer
    door = bp.create_door_unit("Cottage_Door", width=1.1, height=2.1, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    door.location = (ox + w_x/2, oy - 0.5, oz)
    door.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(door, col)
    
    steps = bp.create_stone_steps("Cottage_Steps", width=1.5, depth=0.9, height=0.45, num_steps=2, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox + w_x/2, oy - 0.5, oz)
    steps.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(steps, col)
    
    lantern_d, light_d = bp.create_lantern_prop("Cottage_DoorLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    lantern_d.location = (ox + w_x/2, oy + 0.45, oz + 1.8)
    lantern_d.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(lantern_d, col)
    bp.link_to_collection(light_d, col)

    win_s = bp.create_window_unit("Cottage_Win_S", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    win_s.location = (ox + w_x/2, oy + 1.25, oz + 0.9)
    win_s.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(win_s, col)

    # Dormer on +X Roof Slope (Window faces +X down the slope)
    dormer = bp.create_front_dormer("Cottage_Dormer", tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
    dormer.location = (ox + 1.2, oy - 0.5, oz + h_wall + 1.1)
    dormer.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(dormer, col)

    # Small lean-to market stall at side-back
    awning = bp.create_market_stall_awning("Cottage_Awning", width=1.6, depth=1.1, height=1.8, stripe_mat=mats["M_Awning_Red"], timber_mat=mats["M_Timber_Dark"])
    awning.location = (ox + w_x/2, oy + 2.1, oz)
    awning.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(awning, col)

    c1 = bp.create_crate("Cottage_Crate1", size=0.65, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    c1.location = (ox + w_x/2 + 0.6, oy + 1.8, oz)
    bp.link_to_collection(c1, col)
    
    b1 = bp.create_barrel("Cottage_Barrel1", radius=0.34, height=0.82, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    b1.location = (ox + w_x/2 + 0.6, oy + 2.5, oz)
    bp.link_to_collection(b1, col)

# -------------------------------------------------------------
# 2. bld_townhouse (Townhouse - Ref 8)
# Multi-floor townhouse. Gable at -Y, Long side at +X. Ridge along Y.
# -------------------------------------------------------------
def build_townhouse(origin=(0, 0, 0), mats=None):
    col = "02_Building_Townhouse"
    ox, oy, oz = origin
    w_x, d_y = 4.4, 5.4
    h_stone, h1, h2 = 1.1, 2.6, 4.8
    
    create_pedestal("Townhouse_Pedestal", 10.0, 10.0, origin=origin, mats=mats, col_name=col)
    
    # Ground stone base with Corner Quoins
    stone = bp.create_stone_foundation("Townhouse_Stone", width=w_x, height=h_stone, depth=d_y, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone, col)
    
    # Ground floor plaster
    gf_plaster = bp.create_box("Townhouse_GF_Plaster", size=(w_x - 0.06, d_y - 0.06, h1 - h_stone), location=(ox, oy, oz + h_stone + (h1 - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(gf_plaster, col)
    
    # 1st floor jetty overhang (cantilevered out by 0.20m)
    j_w, j_d = w_x + 0.35, d_y + 0.35
    jetty = bp.create_box("Townhouse_1F_Plaster", size=(j_w - 0.06, j_d - 0.06, h2 - h1), location=(ox, oy, oz + h1 + (h2 - h1)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(jetty, col)
    
    # Jetty decorative corbel beam band
    band = bp.create_box("Townhouse_Girt_Band", size=(j_w + 0.1, j_d + 0.1, 0.18), location=(ox, oy, oz + h1), material=mats["M_Timber_Dark"], bevel=0.015)
    bp.link_to_collection(band, col)

    # Cantilever jetty timber corbel brackets along front (-Y)
    for kx in [-w_x/2 + 0.35, 0, w_x/2 - 0.35]:
        corb = bp.create_wood_corbel(f"Townhouse_Corbel_{kx}", size=0.32, timber_mat=mats["M_Timber_Dark"])
        corb.location = (ox + kx, oy - d_y/2, oz + h1)
        bp.link_to_collection(corb, col)

    # St. Andrew's Cross Timber Framing Overlay on 1F Front Facade (-Y)
    tf_front = bp.create_timber_framing_overlay("Townhouse_TF_Front", width=j_w - 0.2, height=h2 - h1, num_bays=2, has_crosses=True, depth=0.12, timber_mat=mats["M_Timber_Dark"])
    tf_front.location = (ox, oy - j_d/2, oz + h1)
    bp.link_to_collection(tf_front, col)
    
    # Roof (Ridge along Y)
    roof, pitch_h = bp.create_ridge_roof_y("Townhouse_Roof", span_x=j_w, length_y=j_d, overhang_eave=0.42, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h2)
    bp.link_to_collection(roof, col)

    # Exposed Rafter Tails under roof eaves
    rafters = bp.create_rafter_tails("Townhouse_Rafters", span=j_w, length=j_d, axis="y", overhang_eave=0.42, spacing=0.55, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (ox, oy, oz + h2)
    bp.link_to_collection(rafters, col)

    # Gable at -Y (Front) and +Y (Back) with framed principal rafters and struts
    gable_f = bp.create_gable_wall("Townhouse_Gable_F", width=j_w, height=pitch_h, location=(ox, oy - j_d/2, oz + h2), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    bp.link_to_collection(gable_f, col)
    
    gable_b = bp.create_gable_wall("Townhouse_Gable_B", width=j_w, height=pitch_h, location=(ox, oy + j_d/2, oz + h2), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_b.rotation_euler = (0, 0, radians(180))
    bp.link_to_collection(gable_b, col)

    # Chimney with Molded Cap, Flue Pot, and Stylized 3D Smoke Puffs
    chimney = bp.create_chimney("Townhouse_Chimney", height=3.8, width=0.85, depth=0.85, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"], has_smoke=True, flue_pot=True)
    chimney.location = (ox - 0.6, oy - j_d/2 + 0.8, oz + h2 + pitch_h - 1.2)
    bp.link_to_collection(chimney, col)

    # Gable Facade (-Y, Lower-Left):
    # GF: 2 Windows
    for wx in [-1.1, 1.1]:
        w = bp.create_window_unit("Townhouse_GF_Win", width=0.85, height=1.05, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w.location = (ox + wx, oy - d_y/2, oz + 0.9)
        bp.link_to_collection(w, col)
        
    # 1F: 2 Windows with shutters
    for wx in [-1.1, 1.1]:
        w = bp.create_window_unit("Townhouse_1F_Win", width=0.85, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w.location = (ox + wx, oy - j_d/2, oz + h1 + 0.7)
        bp.link_to_collection(w, col)
        
    # Attic: Small window in gable apex
    w_attic = bp.create_window_unit("Townhouse_Attic_Win", width=0.65, height=0.75, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], has_shutters=False, has_planter=False)
    w_attic.location = (ox, oy - j_d/2, oz + h2 + 1.1)
    bp.link_to_collection(w_attic, col)

    # Hanging trade sign on post on far left
    sign = bp.create_hanging_sign("Townhouse_Sign", emblem_type="tavern", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], emblem_mat=mats["M_Gold_Brass"])
    sign.location = (ox - w_x/2 - 0.2, oy - d_y/2 - 0.3, oz + 1.2)
    bp.link_to_collection(sign, col)

    # Side Facade (+X, Lower-Right):
    # GF: Door with steps, lantern, window, wooden bench
    door = bp.create_door_unit("Townhouse_Door", width=1.1, height=2.1, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    door.location = (ox + w_x/2, oy - 1.0, oz)
    door.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(door, col)
    
    steps = bp.create_stone_steps("Townhouse_Steps", width=1.6, depth=1.0, height=0.50, num_steps=3, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox + w_x/2, oy - 1.0, oz)
    steps.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(steps, col)

    lantern, light = bp.create_lantern_prop("Townhouse_DoorLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    lantern.location = (ox + w_x/2, oy - 0.05, oz + 2.0)
    lantern.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(lantern, col)
    bp.link_to_collection(light, col)

    win_s = bp.create_window_unit("Townhouse_Win_S_GF", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    win_s.location = (ox + w_x/2, oy + 0.9, oz + 0.9)
    win_s.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(win_s, col)

    bench = bp.create_wood_bench("Townhouse_Bench", width=1.4, depth=0.45, height=0.50, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"])
    bench.location = (ox + w_x/2 + 0.45, oy + 1.8, oz)
    bench.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(bench, col)

    # 1F: 3 Windows with flower boxes along +X
    for wy in [-1.5, 0.0, 1.5]:
        w = bp.create_window_unit("Townhouse_1F_Win_S", width=0.80, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w.location = (ox + j_w/2, oy + wy, oz + h1 + 0.7)
        w.rotation_euler = (0, 0, radians(90))
        bp.link_to_collection(w, col)

# -------------------------------------------------------------
# 3. bld_tavern (Tavern - Ref 6)
# Grand tavern with covered terrace at -Y, and Gable at +X with red beer banner!
# Ridge along X.
# -------------------------------------------------------------
def build_tavern(origin=(0, 0, 0), mats=None):
    col = "03_Building_Tavern"
    ox, oy, oz = origin
    w_x, d_y = 6.2, 4.4
    h_stone, h1, h2 = 1.0, 2.7, 4.9
    
    create_pedestal("Tavern_Pedestal", 11.2, 9.6, origin=origin, mats=mats, col_name=col)
    
    # Foundation with Corner Quoins
    stone = bp.create_stone_foundation("Tavern_Stone", width=w_x, height=h_stone, depth=d_y, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone, col)
    
    plaster_gf = bp.create_box("Tavern_GF_Plaster", size=(w_x - 0.06, d_y - 0.06, h1 - h_stone), location=(ox, oy, oz + h_stone + (h1 - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster_gf, col)
    
    # 1F overhang
    j_w, j_d = w_x + 0.35, d_y + 0.35
    plaster_1f = bp.create_box("Tavern_1F_Plaster", size=(j_w - 0.06, j_d - 0.06, h2 - h1), location=(ox, oy, oz + h1 + (h2 - h1)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster_1f, col)
    
    band = bp.create_box("Tavern_Girt_Band", size=(j_w + 0.1, j_d + 0.1, 0.18), location=(ox, oy, oz + h1), material=mats["M_Timber_Dark"], bevel=0.015)
    bp.link_to_collection(band, col)

    # Cantilever jetty timber corbel brackets along front (-Y)
    for kx in [-w_x/2 + 0.4, -0.6, 0.8, w_x/2 - 0.4]:
        corb = bp.create_wood_corbel(f"Tavern_Corbel_{kx}", size=0.32, timber_mat=mats["M_Timber_Dark"])
        corb.location = (ox + kx, oy - d_y/2, oz + h1)
        bp.link_to_collection(corb, col)

    # St. Andrew's Cross Timber Framing Overlay on 1F Front Facade (-Y)
    tf_front = bp.create_timber_framing_overlay("Tavern_TF_Front", width=j_w - 0.3, height=h2 - h1, num_bays=3, has_crosses=True, depth=0.12, timber_mat=mats["M_Timber_Dark"])
    tf_front.location = (ox, oy - j_d/2, oz + h1)
    bp.link_to_collection(tf_front, col)

    # Terracotta Roof (Ridge along X, slopes to -Y and +Y)
    roof, pitch_h = bp.create_ridge_roof_x("Tavern_Roof", span_y=j_d, length_x=j_w, overhang_eave=0.42, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h2)
    bp.link_to_collection(roof, col)

    # Exposed Rafter Tails along front and back eaves
    rafters = bp.create_rafter_tails("Tavern_Rafters", span=j_d, length=j_w, axis="x", overhang_eave=0.42, spacing=0.55, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (ox, oy, oz + h2)
    bp.link_to_collection(rafters, col)

    # Gables at -X (Left) and +X (Right) with framed principal rafters and struts
    gable_l = bp.create_gable_wall("Tavern_Gable_L", width=j_d, height=pitch_h, location=(ox - j_w/2, oy, oz + h2), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_l.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(gable_l, col)
    
    gable_r = bp.create_gable_wall("Tavern_Gable_R", width=j_d, height=pitch_h, location=(ox + j_w/2, oy, oz + h2), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_r.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(gable_r, col)

    # Two glowing dormers on the front roof slope (-Y)
    for dx in [-1.6, 1.4]:
        d = bp.create_front_dormer("Tavern_Dormer", tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
        d.location = (ox + dx, oy - 1.25, oz + h2 + 1.05)
        bp.link_to_collection(d, col)

    # Chimney with Molded Cap, Flue Pot, and Stylized 3D Smoke Puffs
    chimney = bp.create_chimney("Tavern_Chimney", height=3.8, width=0.85, depth=0.85, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"], has_smoke=True, flue_pot=True)
    chimney.location = (ox + j_w/2 - 0.7, oy, oz + h2 + pitch_h - 1.2)
    bp.link_to_collection(chimney, col)

    # Front Facade (-Y, Lower-Left):
    # Main double entrance door with flanking lanterns
    door = bp.create_door_unit("Tavern_Door", width=1.4, height=2.2, style="double", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    door.location = (ox + 0.2, oy - d_y/2, oz)
    bp.link_to_collection(door, col)
    
    steps = bp.create_stone_steps("Tavern_Steps", width=2.0, depth=1.1, height=0.50, num_steps=3, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox + 0.2, oy - d_y/2, oz)
    bp.link_to_collection(steps, col)

    for lx in [-0.8, 1.2]:
        l, lt = bp.create_lantern_prop("Tavern_DoorLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
        l.location = (ox + lx, oy - d_y/2, oz + 2.0)
        bp.link_to_collection(l, col)
        bp.link_to_collection(lt, col)

    # GF Windows flanking door
    w_r = bp.create_window_unit("Tavern_GF_Win_R", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    w_r.location = (ox + 2.1, oy - d_y/2, oz + 0.9)
    bp.link_to_collection(w_r, col)

    # 1F: 3 glowing windows across front
    for wx in [-1.8, 0.2, 2.1]:
        w = bp.create_window_unit("Tavern_1F_Win", width=0.85, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w.location = (ox + wx, oy - j_d/2, oz + h1 + 0.7)
        bp.link_to_collection(w, col)

    # Stacked Ale Barrels Pyramid near front entrance
    b1 = bp.create_barrel("Tavern_AleBarrel1", radius=0.36, height=0.85, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    b1.location = (ox + 1.6, oy - d_y/2 - 0.5, oz)
    bp.link_to_collection(b1, col)
    b2 = bp.create_barrel("Tavern_AleBarrel2", radius=0.36, height=0.85, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    b2.location = (ox + 2.3, oy - d_y/2 - 0.5, oz)
    bp.link_to_collection(b2, col)
    b3 = bp.create_barrel("Tavern_AleBarrel3", radius=0.32, height=0.78, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    b3.location = (ox + 1.95, oy - d_y/2 - 0.5, oz + 0.75)
    bp.link_to_collection(b3, col)

    # Left Terrace (-X) with wooden railings and seating
    terrace = bp.create_box("Tavern_Terrace", size=(2.0, 3.2, 0.45), location=(ox - w_x/2 - 1.0, oy - 0.4, oz + 0.225), material=mats["M_Stone_Base"], bevel=0.02)
    bp.link_to_collection(terrace, col)
    
    t_fence = bp.create_fence_section("Tavern_Terrace_Fence", length=2.8, height=0.85, timber_mat=mats["M_Timber_Dark"])
    t_fence.location = (ox - w_x/2 - 1.9, oy - 0.4, oz + 0.45)
    t_fence.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(t_fence, col)

    # Right Gable (+X, Lower-Right):
    w_g1 = bp.create_window_unit("Tavern_Gable_Win_GF", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    w_g1.location = (ox + w_x/2, oy, oz + 0.9)
    w_g1.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(w_g1, col)
    
    w_g2 = bp.create_window_unit("Tavern_Gable_Win_1F", width=0.85, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    w_g2.location = (ox + j_w/2, oy, oz + h1 + 0.7)
    w_g2.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(w_g2, col)

    # FAMOUS RED TAVERN BEER BANNER with gold crest
    banner = bp.create_heraldic_banner("Tavern_RedBanner", emblem_type="tavern", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], cloth_mat=mats["M_Cloth_Red"], gold_mat=mats["M_Gold_Brass"])
    banner.location = (ox + j_w/2, oy - 0.6, oz + h1 + 1.2)
    banner.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(banner, col)

    b_lantern, b_light = bp.create_lantern_prop("Tavern_BannerLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    b_lantern.location = (ox + j_w/2 + 1.2, oy - 0.6, oz + h1 + 1.4)
    b_lantern.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(b_lantern, col)
    bp.link_to_collection(b_light, col)

# -------------------------------------------------------------
# 4. bld_blacksmith (Blacksmith - Ref 4)
# Workshop shed at -Y, Blazing Open Hearth & Navy Roof at +X!
# Ridge along Y.
# -------------------------------------------------------------
def build_blacksmith(origin=(0, 0, 0), mats=None):
    col = "04_Building_Blacksmith"
    ox, oy, oz = origin
    w_x, d_y = 4.4, 4.8
    h_stone, h_wall = 1.0, 2.6
    
    create_pedestal("Blacksmith_Pedestal", 10.4, 10.0, origin=origin, mats=mats, col_name=col)
    
    # Foundation with Corner Quoins
    stone = bp.create_stone_foundation("Blacksmith_Stone", width=w_x, height=h_stone, depth=d_y, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone, col)
    
    plaster = bp.create_box("Blacksmith_Plaster", size=(w_x - 0.06, d_y - 0.06, h_wall - h_stone), location=(ox, oy, oz + h_stone + (h_wall - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)

    # St. Andrew's Cross Timber Framing Overlay on Front Workshop Wall (-Y)
    tf_bs = bp.create_timber_framing_overlay("Blacksmith_TF_Workshop", width=w_x - 0.4, height=h_wall - h_stone, num_bays=2, has_crosses=True, depth=0.12, timber_mat=mats["M_Timber_Dark"])
    tf_bs.location = (ox, oy - d_y/2, oz + h_stone)
    bp.link_to_collection(tf_bs, col)
    
    # Navy Slate Blue Roof (Ridge along Y)
    roof, pitch_h = bp.create_ridge_roof_y("Blacksmith_Roof", span_x=w_x, length_y=d_y, overhang_eave=0.42, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Blue"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(roof, col)

    # Exposed Rafter Tails under roof eaves
    rafters = bp.create_rafter_tails("Blacksmith_Rafters", span=w_x, length=d_y, axis="y", overhang_eave=0.42, spacing=0.55, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(rafters, col)

    # Gable at -Y (Workshop side) and +Y with framed principal rafters and struts
    gable_f = bp.create_gable_wall("Blacksmith_Gable_F", width=w_x, height=pitch_h, location=(ox, oy - d_y/2, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    bp.link_to_collection(gable_f, col)
    
    gable_b = bp.create_gable_wall("Blacksmith_Gable_B", width=w_x, height=pitch_h, location=(ox, oy + d_y/2, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_b.rotation_euler = (0, 0, radians(180))
    bp.link_to_collection(gable_b, col)

    # Massive stone forge chimney with Molded Cap, Flue Pot, and Stylized 3D Smoke Puffs
    chimney = bp.create_chimney("Blacksmith_Chimney", height=4.2, width=1.0, depth=1.0, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"], has_smoke=True, flue_pot=True)
    chimney.location = (ox - 0.4, oy - d_y/2 + 1.2, oz + h_wall + pitch_h - 1.2)
    bp.link_to_collection(chimney, col)

    # Workshop Covered Shed built onto Gable (-Y, Lower-Left):
    shed_d = 2.0
    for sx in [-w_x/2 + 0.2, w_x/2 - 0.2]:
        p = bp.create_beam("Blacksmith_ShedPost", length=2.2, width=0.18, depth=0.18, location=(ox + sx, oy - d_y/2 - shed_d, oz), material=mats["M_Timber_Dark"])
        bp.link_to_collection(p, col)
        
    s_roof = bp.create_box("Blacksmith_ShedRoof", size=(w_x + 0.4, shed_d + 0.4, 0.08), location=(ox, oy - d_y/2 - shed_d/2, oz + 2.3), rotation=(radians(14), 0, 0), material=mats["M_Roof_Tiles_Blue"], bevel=0.01)
    bp.link_to_collection(s_roof, col)

    # Workbench and Stacked Split Firewood under shed
    wb = bp.create_box("Blacksmith_Workbench", size=(1.4, 0.6, 0.8), location=(ox - 0.6, oy - d_y/2 - 1.2, oz + 0.4), material=mats["M_Wood_Planks"], bevel=0.02)
    bp.link_to_collection(wb, col)

    wood_stack = bp.create_firewood_stack("Blacksmith_Firewood", width=1.3, depth=0.55, height=0.75, timber_mat=mats["M_Timber_Dark"])
    wood_stack.location = (ox + 1.1, oy - d_y/2 - 1.4, oz)
    bp.link_to_collection(wood_stack, col)
    
    # Hanging crossed hammers signpost on post
    bs_sign = bp.create_hanging_sign("Blacksmith_Sign", emblem_type="blacksmith", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], emblem_mat=mats["M_Iron_Metal"])
    bs_sign.location = (ox - w_x/2 - 0.3, oy - d_y/2 - shed_d + 0.2, oz + 1.4)
    bp.link_to_collection(bs_sign, col)

    # Side Facade (+X, Lower-Right):
    # BLAZING OPEN FORGE HEARTH with hot embers, stone hood, oak stump & heavy iron anvil!
    hearth, f_light = bp.create_blacksmith_forge_hearth("Blacksmith_Hearth", stone_mat=mats["M_Stone_Base"], ember_mat=mats["M_Fire_Embers"], iron_mat=mats["M_Iron_Metal"])
    hearth.location = (ox + w_x/2 + 0.15, oy + 0.3, oz)
    hearth.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(hearth, col)
    bp.link_to_collection(f_light, col)

    # Water Quenching Trough with dark water and iron hoops
    trough = bp.create_quenching_trough("Blacksmith_Trough", length=1.3, width=0.6, height=0.55, timber_mat=mats["M_Timber_Dark"], water_mat=mats["M_Glass"], iron_mat=mats["M_Iron_Metal"])
    trough.location = (ox + w_x/2 + 1.2, oy - 1.0, oz)
    bp.link_to_collection(trough, col)

    # Upper 1F Windows
    for wy in [-1.1, 1.3]:
        w = bp.create_window_unit("Blacksmith_Win_S", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w.location = (ox + w_x/2, oy + wy, oz + 1.2)
        w.rotation_euler = (0, 0, radians(90))
        bp.link_to_collection(w, col)

    # Dormer on +X roof slope (facing +X)
    dormer = bp.create_front_dormer("Blacksmith_Dormer", tile_mat=mats["M_Roof_Tiles_Blue"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
    dormer.location = (ox + 1.2, oy + 0.2, oz + h_wall + 1.1)
    dormer.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(dormer, col)


# -------------------------------------------------------------
# 5. bld_shop (Shop / Merchant - Ref 5)
# Striped awning outdoor stall at -Y, Gable with door at +X!
# Ridge along X.
# -------------------------------------------------------------
def build_shop(origin=(0, 0, 0), mats=None):
    col = "05_Building_Shop"
    ox, oy, oz = origin
    w_x, d_y = 5.2, 4.4
    h_stone, h_wall = 1.0, 2.7
    
    create_pedestal("Shop_Pedestal", 10.4, 9.6, origin=origin, mats=mats, col_name=col)
    
    # Foundation with Corner Quoins
    stone = bp.create_stone_foundation("Shop_Stone", width=w_x, height=h_stone, depth=d_y, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone, col)
    
    plaster = bp.create_box("Shop_Plaster", size=(w_x - 0.06, d_y - 0.06, h_wall - h_stone), location=(ox, oy, oz + h_stone + (h_wall - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)

    # Navy Blue Roof (Ridge along X)
    roof, pitch_h = bp.create_ridge_roof_x("Shop_Roof", span_y=d_y, length_x=w_x, overhang_eave=0.42, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Blue"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(roof, col)

    # Exposed Rafter Tails along front and back eaves
    rafters = bp.create_rafter_tails("Shop_Rafters", span=d_y, length=w_x, axis="x", overhang_eave=0.42, spacing=0.55, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(rafters, col)

    # Gables at -X (Left) and +X (Right) with framed principal rafters and struts
    gable_l = bp.create_gable_wall("Shop_Gable_L", width=d_y, height=pitch_h, location=(ox - w_x/2, oy, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_l.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(gable_l, col)
    
    gable_r = bp.create_gable_wall("Shop_Gable_R", width=d_y, height=pitch_h, location=(ox + w_x/2, oy, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_r.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(gable_r, col)

    # Glowing dormer on the front slope (-Y)
    dormer = bp.create_front_dormer("Shop_Dormer", tile_mat=mats["M_Roof_Tiles_Blue"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
    dormer.location = (ox - 0.6, oy - 1.25, oz + h_wall + 1.05)
    bp.link_to_collection(dormer, col)

    # Chimney with Molded Cap, Flue Pot, and Stylized 3D Smoke Puffs
    chimney = bp.create_chimney("Shop_Chimney", height=3.8, width=0.8, depth=0.8, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"], has_smoke=True, flue_pot=True)
    chimney.location = (ox + w_x/2 - 0.7, oy, oz + h_wall + pitch_h - 1.2)
    bp.link_to_collection(chimney, col)

    # Front Facade (-Y, Lower-Left):
    # Blue and White Striped Awning Market Stall
    awning = bp.create_market_stall_awning("Shop_Awning", width=2.8, depth=1.6, height=2.2, stripe_mat=mats["M_Awning_Blue"], timber_mat=mats["M_Timber_Dark"])
    awning.location = (ox - 0.6, oy - d_y/2, oz)
    bp.link_to_collection(awning, col)

    # Display Counter with Glowing Potion Bottles (Blue, Red, Green)
    potion_mats = [mats["M_Potion_Blue"], mats["M_Potion_Red"], mats["M_Potion_Green"]]
    counter = bp.create_potion_counter_prop("Shop_PotionCounter", width=2.4, depth=0.75, height=0.88, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], potion_mats=potion_mats)
    counter.location = (ox - 0.6, oy - d_y/2 - 0.9, oz)
    bp.link_to_collection(counter, col)

    # Stacked Produce Crates next to stall
    c1 = bp.create_crate("Shop_Crate1", size=0.65, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    c1.location = (ox + 1.1, oy - d_y/2 - 0.9, oz)
    bp.link_to_collection(c1, col)
    c2 = bp.create_crate("Shop_Crate2", size=0.52, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    c2.location = (ox + 1.1, oy - d_y/2 - 0.9, oz + 0.65)
    bp.link_to_collection(c2, col)

    # Hanging potion bottle sign on post at left
    sign = bp.create_hanging_sign("Shop_PotionSign", emblem_type="shop", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], emblem_mat=mats["M_Awning_Blue"])
    sign.location = (ox - w_x/2 - 0.2, oy - d_y/2 - 0.4, oz + 1.2)
    bp.link_to_collection(sign, col)

    # Right Gable (+X, Lower-Right):
    # Entrance Door with steps and lantern
    door = bp.create_door_unit("Shop_Door", width=1.1, height=2.1, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    door.location = (ox + w_x/2, oy - 0.8, oz)
    door.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(door, col)
    
    steps = bp.create_stone_steps("Shop_Steps", width=1.5, depth=0.9, height=0.45, num_steps=2, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox + w_x/2, oy - 0.8, oz)
    steps.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(steps, col)

    lantern, light = bp.create_lantern_prop("Shop_DoorLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    lantern.location = (ox + w_x/2, oy + 0.1, oz + 1.9)
    lantern.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(lantern, col)
    bp.link_to_collection(light, col)

    # Windows on Gable (+X)
    w_gf = bp.create_window_unit("Shop_Win_GF", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    w_gf.location = (ox + w_x/2, oy + 1.0, oz + 0.9)
    w_gf.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(w_gf, col)

    w_attic = bp.create_window_unit("Shop_Win_Attic", width=0.85, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    w_attic.location = (ox + w_x/2, oy, oz + h_wall + 0.8)
    w_attic.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(w_attic, col)

# -------------------------------------------------------------
# 6. bld_stables (Stables - Ref 3)
# Open stable stalls at -Y, Gable with horse banner at +X!
# Ridge along X.
# -------------------------------------------------------------
def build_stables(origin=(0, 0, 0), mats=None):
    col = "06_Building_Stables"
    ox, oy, oz = origin
    w_x, d_y = 6.4, 4.6
    h_stone, h_wall = 0.8, 2.6
    
    create_pedestal("Stables_Pedestal", 11.2, 9.6, origin=origin, mats=mats, col_name=col)
    
    # Foundation with Corner Quoins
    stone = bp.create_stone_foundation("Stables_Stone", width=w_x, height=h_stone, depth=d_y, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone, col)
    
    plaster = bp.create_box("Stables_Plaster", size=(w_x - 0.06, d_y - 0.06, h_wall - h_stone), location=(ox, oy, oz + h_stone + (h_wall - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)

    # Weathered timber shingle roof (Ridge along X)
    roof, pitch_h = bp.create_ridge_roof_x("Stables_Roof", span_y=d_y, length_x=w_x, overhang_eave=0.42, overhang_gable=0.30, tile_mat=mats["M_Wood_Planks"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(roof, col)

    # Exposed Rafter Tails along front and back eaves
    rafters = bp.create_rafter_tails("Stables_Rafters", span=d_y, length=w_x, axis="x", overhang_eave=0.42, spacing=0.55, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(rafters, col)

    # Gables at -X and +X with framed principal rafters and struts
    gable_l = bp.create_gable_wall("Stables_Gable_L", width=d_y, height=pitch_h, location=(ox - w_x/2, oy, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_l.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(gable_l, col)
    
    gable_r = bp.create_gable_wall("Stables_Gable_R", width=d_y, height=pitch_h, location=(ox + w_x/2, oy, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_r.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(gable_r, col)

    # Upper Hay Crane Hoist Beam protruding from right gable apex (+X)
    crane = bp.create_hay_crane_hoist("Stables_HayCrane", length=1.7, timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"])
    crane.location = (ox + w_x/2 + 0.1, oy, oz + h_wall + pitch_h - 0.15)
    crane.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(crane, col)

    # Chimney with Molded Cap, Flue Pot, and Stylized 3D Smoke Puffs
    chimney = bp.create_chimney("Stables_Chimney", height=3.4, width=0.75, depth=0.75, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"], has_smoke=True, flue_pot=True)
    chimney.location = (ox + w_x/2 - 0.8, oy + d_y/2 - 0.8, oz + h_wall + pitch_h - 1.2)
    bp.link_to_collection(chimney, col)

    # Front Facade (-Y, Lower-Left):
    # Open stable stalls with timber posts and paddock railings
    stall_d = 1.8
    for sx in [-w_x/2 + 0.3, -0.2, w_x/2 - 0.3]:
        p = bp.create_beam("Stables_Post", length=2.2, width=0.18, depth=0.18, location=(ox + sx, oy - d_y/2 - stall_d, oz), material=mats["M_Timber_Dark"])
        bp.link_to_collection(p, col)

    # Paddock fence enclosing stalls
    fence1 = bp.create_fence_section("Stables_Fence1", length=2.8, height=0.85, timber_mat=mats["M_Timber_Dark"])
    fence1.location = (ox - 1.6, oy - d_y/2 - stall_d, oz)
    bp.link_to_collection(fence1, col)
    
    fence2 = bp.create_fence_section("Stables_Fence2", length=2.8, height=0.85, timber_mat=mats["M_Timber_Dark"])
    fence2.location = (ox + 1.4, oy - d_y/2 - stall_d, oz)
    bp.link_to_collection(fence2, col)

    # Water Feed Trough for horses
    feed_trough = bp.create_quenching_trough("Stables_FeedTrough", length=1.4, width=0.6, height=0.50, timber_mat=mats["M_Timber_Dark"], water_mat=mats["M_Glass"], iron_mat=mats["M_Iron_Metal"])
    feed_trough.location = (ox - 0.2, oy - d_y/2 - 0.7, oz)
    bp.link_to_collection(feed_trough, col)

    # Hay bales stacked in paddock
    bale1 = bp.create_hay_bale("Stables_Hay1", width=0.75, length=1.2, height=0.55, straw_mat=mats["M_Straw"])
    bale1.location = (ox - 1.8, oy - d_y/2 - 0.8, oz)
    bp.link_to_collection(bale1, col)

    bale2 = bp.create_hay_bale("Stables_Hay2", width=0.75, length=1.2, height=0.55, straw_mat=mats["M_Straw"])
    bale2.location = (ox - 1.8, oy - d_y/2 - 0.8, oz + 0.55)
    bp.link_to_collection(bale2, col)

    bale3 = bp.create_hay_bale("Stables_Hay3", width=0.75, length=1.2, height=0.55, straw_mat=mats["M_Straw"])
    bale3.location = (ox + 1.6, oy - d_y/2 - 0.8, oz)
    bp.link_to_collection(bale3, col)

    # 1F Windows
    for wx in [-1.5, 1.5]:
        w = bp.create_window_unit("Stables_Win_1F", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], has_shutters=True, has_planter=False)
        w.location = (ox + wx, oy - d_y/2, oz + 1.2)
        bp.link_to_collection(w, col)

    # Right Gable (+X, Lower-Right):
    # Stable entrance door, window, and HANGING HORSE HEAD HERALDIC BANNER!
    door = bp.create_door_unit("Stables_Door", width=1.3, height=2.1, style="double", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    door.location = (ox + w_x/2, oy - 0.6, oz)
    door.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(door, col)

    w_g = bp.create_window_unit("Stables_Gable_Win", width=0.85, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], has_shutters=True, has_planter=False)
    w_g.location = (ox + w_x/2, oy, oz + h_wall + 0.8)
    w_g.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(w_g, col)

    banner = bp.create_heraldic_banner("Stables_HorseBanner", emblem_type="stables", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], cloth_mat=mats["M_Awning_Red"], gold_mat=mats["M_Gold_Brass"])
    banner.location = (ox + w_x/2 + 0.1, oy + 1.2, oz + 1.8)
    banner.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(banner, col)

# -------------------------------------------------------------
# 7. bld_warehouse (Warehouse - Ref 2)
# Gable cargo doors at -Y, Lean-to storage shed at +X!
# Ridge along Y.
# -------------------------------------------------------------
def build_warehouse(origin=(0, 0, 0), mats=None):
    col = "07_Building_Warehouse"
    ox, oy, oz = origin
    w_x, d_y = 4.8, 6.0
    h_stone, h_wall = 1.0, 2.7
    
    create_pedestal("Warehouse_Pedestal", 10.4, 10.8, origin=origin, mats=mats, col_name=col)
    
    # Foundation with Corner Quoins
    stone = bp.create_stone_foundation("Warehouse_Stone", width=w_x, height=h_stone, depth=d_y, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone, col)
    
    plaster = bp.create_box("Warehouse_Plaster", size=(w_x - 0.06, d_y - 0.06, h_wall - h_stone), location=(ox, oy, oz + h_stone + (h_wall - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)

    # St. Andrew's Cross Timber Framing Overlay on Front Cargo Facade (-Y)
    tf_w = bp.create_timber_framing_overlay("Warehouse_TF_Gable", width=w_x - 0.4, height=h_wall - h_stone, num_bays=2, has_crosses=True, depth=0.12, timber_mat=mats["M_Timber_Dark"])
    tf_w.location = (ox, oy - d_y/2, oz + h_stone)
    bp.link_to_collection(tf_w, col)

    # Navy Slate Blue Roof (Ridge along Y)
    roof, pitch_h = bp.create_ridge_roof_y("Warehouse_Roof", span_x=w_x, length_y=d_y, overhang_eave=0.42, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Blue"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(roof, col)

    # Exposed Rafter Tails under roof eaves
    rafters = bp.create_rafter_tails("Warehouse_Rafters", span=w_x, length=d_y, axis="y", overhang_eave=0.42, spacing=0.55, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(rafters, col)

    # Gables at -Y (Front Cargo Entrance) and +Y with framed principal rafters and struts
    gable_f = bp.create_gable_wall("Warehouse_Gable_F", width=w_x, height=pitch_h, location=(ox, oy - d_y/2, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    bp.link_to_collection(gable_f, col)
    
    gable_b = bp.create_gable_wall("Warehouse_Gable_B", width=w_x, height=pitch_h, location=(ox, oy + d_y/2, oz + h_wall), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_b.rotation_euler = (0, 0, radians(180))
    bp.link_to_collection(gable_b, col)

    # Upper Cargo Hoisting Crane with Pulley and Hook protruding from front gable apex
    crane = bp.create_hay_crane_hoist("Warehouse_CraneHoist", length=1.8, timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"])
    crane.location = (ox + 0.2, oy - d_y/2 - 0.1, oz + h_wall + pitch_h - 0.15)
    bp.link_to_collection(crane, col)

    # Front Gable Facade (-Y, Lower-Left):
    # Large heavy cargo double entrance door
    door = bp.create_door_unit("Warehouse_CargoDoor", width=1.5, height=2.2, style="double", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    door.location = (ox + 0.2, oy - d_y/2, oz)
    bp.link_to_collection(door, col)
    
    steps = bp.create_stone_steps("Warehouse_Steps", width=2.0, depth=1.0, height=0.45, num_steps=2, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox + 0.2, oy - d_y/2, oz)
    bp.link_to_collection(steps, col)

    lantern, light = bp.create_lantern_prop("Warehouse_DoorLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    lantern.location = (ox + 1.2, oy - d_y/2, oz + 2.0)
    bp.link_to_collection(lantern, col)
    bp.link_to_collection(light, col)

    # Window on left with flower box
    win_l = bp.create_window_unit("Warehouse_Win_L", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
    win_l.location = (ox - 1.3, oy - d_y/2, oz + 0.9)
    bp.link_to_collection(win_l, col)

    # Side Facade (+X, Lower-Right):
    # Long covered lean-to storage shed packed with crates, barrels, and sacks!
    shed_w = 1.8
    for sy in [-d_y/2 + 0.8, 0, d_y/2 - 0.8]:
        p = bp.create_beam("Warehouse_ShedPost", length=2.1, width=0.18, depth=0.18, location=(ox + w_x/2 + shed_w, oy + sy, oz), material=mats["M_Timber_Dark"])
        bp.link_to_collection(p, col)

    s_roof = bp.create_box("Warehouse_ShedRoof", size=(shed_w + 0.3, d_y + 0.2, 0.08), location=(ox + w_x/2 + shed_w/2, oy, oz + 2.2), rotation=(0, radians(-14), 0), material=mats["M_Roof_Tiles_Blue"], bevel=0.01)
    bp.link_to_collection(s_roof, col)

    # Stacked crates and barrels under storage shed
    for i, cy in enumerate([-1.6, -0.6, 0.6, 1.6]):
        c = bp.create_crate(f"Warehouse_Crate_{i}", size=0.70, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
        c.location = (ox + w_x/2 + 0.8, oy + cy, oz)
        bp.link_to_collection(c, col)

    for i, by in enumerate([-1.1, 1.1]):
        b = bp.create_barrel(f"Warehouse_Barrel_{i}", radius=0.36, height=0.88, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
        b.location = (ox + w_x/2 + 1.1, oy + by, oz)
        bp.link_to_collection(b, col)

    # Lantern hanging under shed
    s_lantern, s_light = bp.create_lantern_prop("Warehouse_ShedLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    s_lantern.location = (ox + w_x/2 + shed_w, oy - 1.2, oz + 1.9)
    s_lantern.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(s_lantern, col)
    bp.link_to_collection(s_light, col)

# -------------------------------------------------------------
# 8. bld_tenement (Tenement - Ref 7)
# 3 levels! Arched portal door, 2 dormers at -Y, corner balcony with laundry!
# Ridge along X.
# -------------------------------------------------------------
def build_tenement(origin=(0, 0, 0), mats=None):
    col = "08_Building_Tenement"
    ox, oy, oz = origin
    w_x, d_y = 6.4, 4.6
    h_stone, h1, h2 = 1.2, 2.8, 5.2
    
    create_pedestal("Tenement_Pedestal", 11.6, 9.8, origin=origin, mats=mats, col_name=col)
    
    # Foundation with Corner Quoins
    stone = bp.create_stone_foundation("Tenement_Stone", width=w_x, height=h_stone, depth=d_y, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone, col)
    
    plaster_gf = bp.create_box("Tenement_GF_Plaster", size=(w_x - 0.06, d_y - 0.06, h1 - h_stone), location=(ox, oy, oz + h_stone + (h1 - h_stone)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster_gf, col)
    
    # 1F overhang
    j_w, j_d = w_x + 0.40, d_y + 0.40
    plaster_1f = bp.create_box("Tenement_1F_Plaster", size=(j_w - 0.06, j_d - 0.06, h2 - h1), location=(ox, oy, oz + h1 + (h2 - h1)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster_1f, col)
    
    band = bp.create_box("Tenement_Girt_Band", size=(j_w + 0.1, j_d + 0.1, 0.18), location=(ox, oy, oz + h1), material=mats["M_Timber_Dark"], bevel=0.015)
    bp.link_to_collection(band, col)

    # Cantilever jetty timber corbel brackets along front (-Y)
    for kx in [-w_x/2 + 0.5, -0.8, 0.6, w_x/2 - 0.5]:
        corb = bp.create_wood_corbel(f"Tenement_Corbel_{kx}", size=0.35, timber_mat=mats["M_Timber_Dark"])
        corb.location = (ox + kx, oy - d_y/2, oz + h1)
        bp.link_to_collection(corb, col)

    # St. Andrew's Cross Timber Framing Overlay on 1F Front Facade (-Y)
    tf_ten = bp.create_timber_framing_overlay("Tenement_TF_Front", width=j_w - 0.3, height=h2 - h1, num_bays=3, has_crosses=True, depth=0.12, timber_mat=mats["M_Timber_Dark"])
    tf_ten.location = (ox, oy - j_d/2, oz + h1)
    bp.link_to_collection(tf_ten, col)

    # Navy Blue Slate Roof (Ridge along X)
    roof, pitch_h = bp.create_ridge_roof_x("Tenement_Roof", span_y=j_d, length_x=j_w, overhang_eave=0.42, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Blue"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h2)
    bp.link_to_collection(roof, col)

    # Exposed Rafter Tails along front and back eaves
    rafters = bp.create_rafter_tails("Tenement_Rafters", span=j_d, length=j_w, axis="x", overhang_eave=0.42, spacing=0.55, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (ox, oy, oz + h2)
    bp.link_to_collection(rafters, col)

    # Gables at -X (Left) and +X (Right) with framed principal rafters and struts
    gable_l = bp.create_gable_wall("Tenement_Gable_L", width=j_d, height=pitch_h, location=(ox - j_w/2, oy, oz + h2), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_l.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(gable_l, col)
    
    gable_r = bp.create_gable_wall("Tenement_Gable_R", width=j_d, height=pitch_h, location=(ox + j_w/2, oy, oz + h2), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_r.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(gable_r, col)

    # TWO glowing dormer windows on front roof slope (-Y)
    for dx in [-1.5, 1.5]:
        d = bp.create_front_dormer("Tenement_Dormer", tile_mat=mats["M_Roof_Tiles_Blue"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
        d.location = (ox + dx, oy - 1.30, oz + h2 + 1.10)
        bp.link_to_collection(d, col)

    # Chimney with Molded Cap, Flue Pot, and Stylized 3D Smoke Puffs
    chimney = bp.create_chimney("Tenement_Chimney", height=4.2, width=0.9, depth=0.9, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"], has_smoke=True, flue_pot=True)
    chimney.location = (ox + j_w/2 - 0.8, oy, oz + h2 + pitch_h - 1.2)
    bp.link_to_collection(chimney, col)

    # Front Facade (-Y, Lower-Left):
    # Main arched stone portal entrance door
    door = bp.create_door_unit("Tenement_Door", width=1.3, height=2.2, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["Wood_Planks" if "Wood_Planks" in mats else "M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    door.location = (ox + 0.4, oy - d_y/2, oz)
    bp.link_to_collection(door, col)
    
    steps = bp.create_stone_steps("Tenement_Steps", width=1.8, depth=1.1, height=0.50, num_steps=3, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox + 0.4, oy - d_y/2, oz)
    bp.link_to_collection(steps, col)

    lantern, light = bp.create_lantern_prop("Tenement_DoorLantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    lantern.location = (ox - 0.5, oy - d_y/2, oz + 2.0)
    bp.link_to_collection(lantern, col)
    bp.link_to_collection(light, col)

    # Flanking GF windows
    for wx in [-1.8, 2.1]:
        w = bp.create_window_unit("Tenement_GF_Win", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w.location = (ox + wx, oy - d_y/2, oz + 0.9)
        bp.link_to_collection(w, col)

    # 1F: 3 glowing windows
    for wx in [-1.8, 0.4, 2.1]:
        w = bp.create_window_unit("Tenement_1F_Win", width=0.85, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w.location = (ox + wx, oy - j_d/2, oz + h1 + 0.7)
        bp.link_to_collection(w, col)

    # Left Corner Balcony (-X) with wooden railing
    balcony = bp.create_balcony_unit("Tenement_Balcony", width=2.4, depth=1.2, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"])
    balcony.location = (ox - j_w/2 + 0.6, oy - j_d/2, oz + h1)
    bp.link_to_collection(balcony, col)

    # Hanging Laundry Line strung along the balcony with white shirt, blue pants, red cloth!
    laundry = bp.create_laundry_line_prop("Tenement_Laundry",
        (ox - j_w/2 + 0.6 - 1.0, oy - j_d/2 - 1.0, oz + h1 + 1.1),
        (ox - j_w/2 + 0.6 + 1.0, oy - j_d/2 - 1.0, oz + h1 + 1.1),
        sag=0.14, timber_mat=mats["M_Timber_Dark"],
        cloth_white=mats["M_Cloth_White"], cloth_blue=mats["M_Cloth_Blue"], cloth_red=mats["M_Cloth_Red"])
    bp.link_to_collection(laundry, col)

    # Right Gable (+X, Lower-Right):
    for wy in [-1.0, 1.0]:
        w = bp.create_window_unit("Tenement_Win_R_GF", width=0.85, height=1.1, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w.location = (ox + w_x/2, oy + wy, oz + 0.9)
        w.rotation_euler = (0, 0, radians(90))
        bp.link_to_collection(w, col)
        
        w1 = bp.create_window_unit("Tenement_Win_R_1F", width=0.85, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"], has_shutters=True, has_planter=True)
        w1.location = (ox + j_w/2, oy + wy, oz + h1 + 0.7)
        w1.rotation_euler = (0, 0, radians(90))
        bp.link_to_collection(w1, col)

    # Second Laundry Line strung under Right Gable eave
    laundry_r = bp.create_laundry_line_prop("Tenement_Laundry_Right",
        (ox + j_w/2 + 0.12, oy - 1.1, oz + h2 + 0.55),
        (ox + j_w/2 + 0.12, oy + 1.1, oz + h2 + 0.55),
        sag=0.12, timber_mat=mats["M_Timber_Dark"],
        cloth_white=mats["M_Cloth_White"], cloth_blue=mats["M_Cloth_Blue"], cloth_red=mats["M_Cloth_Red"])
    bp.link_to_collection(laundry_r, col)

# -------------------------------------------------------------
# Setup Cameras & Lighting
# -------------------------------------------------------------
def setup_showcase_cameras_and_lights(building_coords):
    col = "00_Lighting_and_Cameras"
    
    # Master Camera (Centered on average coords: x=33.0, y=11.0, z=3.5)
    cx, cy, cz = 33.0, 11.0, 3.5
    cam_data = bpy.data.cameras.new("Cam_Isometric_Master")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 78.0
    cam_obj = bpy.data.objects.new("Cam_Isometric_Master", cam_data)
    dist = 55.0
    cam_obj.location = (cx + dist, cy - dist, cz + dist)
    cam_obj.rotation_euler = (radians(54.736), 0, radians(45.0))
    bp.link_to_collection(cam_obj, col)
    bpy.context.scene.camera = cam_obj

    # Individual Building Orthographic Cameras (Framed to capture chimneys, smoke, and full details)
    for b_name, (bx, by, bz) in building_coords.items():
        b_cam_data = bpy.data.cameras.new(f"Cam_{b_name}")
        b_cam_data.type = 'ORTHO'
        b_cam_data.ortho_scale = 15.0
        b_cam_obj = bpy.data.objects.new(f"Cam_{b_name}", b_cam_data)
        i_dist = 25.0
        b_cam_obj.location = (bx + i_dist, by - i_dist, bz + 3.4 + i_dist)
        b_cam_obj.rotation_euler = (radians(54.736), 0, radians(45.0))
        bp.link_to_collection(b_cam_obj, col)

    # Key Sunlight (Warm Golden Fantasy Sun)
    sun_data = bpy.data.lights.new(name="Sun_KeyLight", type='SUN')
    sun_data.energy = 5.5
    sun_data.color = (1.0, 0.94, 0.88)
    sun_data.angle = radians(6.0)
    sun_obj = bpy.data.objects.new("Sun_KeyLight", sun_data)
    sun_obj.rotation_euler = (radians(50.0), radians(15.0), radians(35.0))
    bp.link_to_collection(sun_obj, col)

    # Sky Fill Light (Deep Cyan / Twilight Blue)
    sky_data = bpy.data.lights.new(name="Sun_SkyFill", type='SUN')
    sky_data.energy = 2.2
    sky_data.color = (0.60, 0.75, 0.95)
    sky_obj = bpy.data.objects.new("Sun_SkyFill", sky_data)
    sky_obj.rotation_euler = (radians(130.0), radians(15.0), radians(-145.0))
    bp.link_to_collection(sky_obj, col)

# -------------------------------------------------------------
# Main Assembly
# -------------------------------------------------------------
def build_all_buildings():
    print("Building all 8 Emberglass showcase buildings (Exact 1:1 copies)...")
    clear_scene()
    
    scene = bpy.context.scene
    setup_world(scene)
    mats = materials.setup_all_materials()
    
    spacing_x = 22.0
    spacing_y = 22.0
    
    building_coords = {
        "Cottage":    (0 * spacing_x,  1 * spacing_y, 0),
        "Townhouse":  (1 * spacing_x,  1 * spacing_y, 0),
        "Tavern":     (2 * spacing_x,  1 * spacing_y, 0),
        "Blacksmith": (3 * spacing_x,  1 * spacing_y, 0),
        "Shop":       (0 * spacing_x,  0 * spacing_y, 0),
        "Stables":    (1 * spacing_x,  0 * spacing_y, 0),
        "Warehouse":  (2 * spacing_x,  0 * spacing_y, 0),
        "Tenement":   (3 * spacing_x,  0 * spacing_y, 0),
    }

    print("1/8: Assembling Cottage (Ref 9)...")
    build_cottage(origin=building_coords["Cottage"], mats=mats)
    
    print("2/8: Assembling Townhouse (Ref 8)...")
    build_townhouse(origin=building_coords["Townhouse"], mats=mats)
    
    print("3/8: Assembling Tavern (Ref 6)...")
    build_tavern(origin=building_coords["Tavern"], mats=mats)
    
    print("4/8: Assembling Blacksmith (Ref 4)...")
    build_blacksmith(origin=building_coords["Blacksmith"], mats=mats)
    
    print("5/8: Assembling Shop (Ref 5)...")
    build_shop(origin=building_coords["Shop"], mats=mats)
    
    print("6/8: Assembling Stables (Ref 3)...")
    build_stables(origin=building_coords["Stables"], mats=mats)
    
    print("7/8: Assembling Warehouse (Ref 2)...")
    build_warehouse(origin=building_coords["Warehouse"], mats=mats)
    
    print("8/8: Assembling Tenement (Ref 7)...")
    build_tenement(origin=building_coords["Tenement"], mats=mats)

    print("Setting up Cameras & Lights...")
    setup_showcase_cameras_and_lights(building_coords)

    output_path = "d:/assests/emberglass_buildings.blend"
    bpy.ops.wm.save_as_mainfile(filepath=output_path)
    print(f"Master file saved to: {output_path}")

if __name__ == "__main__":
    build_all_buildings()
