"""
Emberglass Comprehensive Modular Asset Kit Generator for Blender 4.2 LTS
Creates all individual modular kit pieces from the Emberglass library reference sheet
arranged cleanly on an organized grid across 14 collections.
Saves to d:\assests\emberglass_modular_kit.blend
"""

import bpy
import sys
import os

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
    world = bpy.data.worlds.new("Emberglass_Kit_World")
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

def build_kit():
    print("Generating Complete Emberglass Modular Asset Kit...")
    clear_scene()
    
    scene = bpy.context.scene
    setup_world(scene)
    mats = materials.setup_all_materials()
    
    gx = 4.0
    gy = 4.0
    
    # 01. Walls & Foundation
    col_w = "01_Walls_Foundation"
    w_stone = bp.create_stone_foundation("wall_lower_straight", width=2.4, height=2.4, stone_mat=mats["M_Stone_Base"], has_quoins=True)
    w_stone.location = (0 * gx, 0 * gy, 0)
    bp.link_to_collection(w_stone, col_w)
    
    w_crn = bp.create_stone_foundation("wall_lower_corner", width=2.4, height=2.4, stone_mat=mats["M_Stone_Base"], has_quoins=True)
    w_crn.location = (1 * gx, 0 * gy, 0)
    bp.link_to_collection(w_crn, col_w)
    
    steps = bp.create_stone_steps("stairs_small", width=1.6, depth=1.2, height=0.6, stone_mat=mats["M_Stone_Base"])
    steps.location = (2 * gx, 0 * gy, 0)
    bp.link_to_collection(steps, col_w)
    
    # 02. Upper Walls
    col_up = "02_Walls_Upper"
    w_up = bp.create_timber_framed_wall("wall_upper_straight", width=2.4, height=2.4, style="straight", plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"])
    w_up.location = (0 * gx, 1 * gy, 0)
    bp.link_to_collection(w_up, col_up)
    
    w_cross = bp.create_timber_framed_wall("wall_upper_crossbrace", width=2.4, height=2.4, style="cross", plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"])
    w_cross.location = (1 * gx, 1 * gy, 0)
    bp.link_to_collection(w_cross, col_up)
    
    w_gable = bp.create_gable_wall("wall_upper_gable", width=4.0, height=2.4, plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    w_gable.location = (2.5 * gx, 1 * gy, 0)
    bp.link_to_collection(w_gable, col_up)

    # 03. Structural Timber
    col_t = "03_Structural_Timber"
    bv = bp.create_beam("wood_beam_vertical", length=2.4, width=0.18, depth=0.18, material=mats["M_Timber_Dark"])
    bv.location = (0 * gx, 2 * gy, 0)
    bp.link_to_collection(bv, col_t)
    
    bh = bp.create_beam("wood_beam_horizontal", length=2.4, width=0.18, depth=0.18, rotation=(0, 1.5708, 0), material=mats["M_Timber_Dark"])
    bh.location = (1 * gx, 2 * gy, 0)
    bp.link_to_collection(bh, col_t)
    
    corb = bp.create_wood_corbel("wood_corbel", size=0.38, timber_mat=mats["M_Timber_Dark"])
    corb.location = (2 * gx, 2 * gy, 0)
    bp.link_to_collection(corb, col_t)

    rafters = bp.create_rafter_tails("rafter_tails", span=3.0, length=2.4, axis="x", overhang_eave=0.4, spacing=0.5, timber_mat=mats["M_Timber_Dark"])
    rafters.location = (3 * gx, 2 * gy, 0)
    bp.link_to_collection(rafters, col_t)

    # 04. Roof Modules
    col_r = "04_Roof_System"
    r_red, _ = bp.create_ridge_roof_x("roof_main_red", span_y=3.0, length_x=2.4, height=1.8, tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"])
    r_red.location = (0 * gx, 3 * gy, 0)
    bp.link_to_collection(r_red, col_r)
    
    r_blue, _ = bp.create_ridge_roof_x("roof_main_blue", span_y=3.0, length_x=2.4, height=1.8, tile_mat=mats["M_Roof_Tiles_Blue"], timber_mat=mats["M_Timber_Dark"])
    r_blue.location = (1 * gx, 3 * gy, 0)
    bp.link_to_collection(r_blue, col_r)
    
    dorm = bp.create_front_dormer("roof_dormer", tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
    dorm.location = (2 * gx, 3 * gy, 0)
    bp.link_to_collection(dorm, col_r)
    
    chim = bp.create_chimney("chimney_stone", height=3.6, width=0.8, depth=0.8, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"], has_smoke=True, flue_pot=True)
    chim.location = (3 * gx, 3 * gy, 0)
    bp.link_to_collection(chim, col_r)

    # 05. Doors & Windows
    col_dw = "05_Doors_Windows"
    ds = bp.create_door_unit("door_single", width=1.1, height=2.1, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    ds.location = (0 * gx, 4 * gy, 0)
    bp.link_to_collection(ds, col_dw)
    
    dl = bp.create_door_unit("door_large", width=2.2, height=2.4, style="double", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"])
    dl.location = (1 * gx, 4 * gy, 0)
    bp.link_to_collection(dl, col_dw)
    
    ws = bp.create_window_unit("window_standard", width=0.9, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], has_shutters=True, has_planter=True, plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"])
    ws.location = (2 * gx, 4 * gy, 0)
    bp.link_to_collection(ws, col_dw)

    # 06. Walls & Fortifications
    col_fort = "06_Fortifications"
    cw = bp.create_curtain_wall("wall_straight", width=4.0, height=3.5, depth=1.2, stone_mat=mats["M_Stone_Base"])
    cw.location = (0 * gx, 5 * gy, 0)
    bp.link_to_collection(cw, col_fort)
    
    c_crn = bp.create_wall_corner("wall_corner", width=3.0, height=3.5, stone_mat=mats["M_Stone_Base"])
    c_crn.location = (1.5 * gx, 5 * gy, 0)
    bp.link_to_collection(c_crn, col_fort)
    
    tower = bp.create_wall_tower("wall_tower", radius=1.6, height=5.5, stone_mat=mats["M_Stone_Base"], banner_mat=mats["M_Cloth_Red"])
    tower.location = (3.0 * gx, 5 * gy, 0)
    bp.link_to_collection(tower, col_fort)
    
    c_gate = bp.create_castle_gate_portal("castle_gate", width=5.0, height=4.5, depth=1.8, stone_mat=mats["M_Stone_Base"], iron_mat=mats["M_Iron_Metal"], timber_mat=mats["M_Timber_Dark"])
    c_gate.location = (4.8 * gx, 5 * gy, 0)
    bp.link_to_collection(c_gate, col_fort)
    
    ret_w = bp.create_retaining_wall("retaining_wall", width=4.0, height=2.2, depth=1.0, stone_mat=mats["M_Stone_Base"], timber_mat=mats["M_Timber_Dark"])
    ret_w.location = (6.5 * gx, 5 * gy, 0)
    bp.link_to_collection(ret_w, col_fort)

    cliff_w = bp.create_cliff_wall("cliff_wall", width=4.0, height=2.8, stone_mat=mats["M_Stone_Base"], foliage_mat=mats["M_Foliage"])
    cliff_w.location = (8.0 * gx, 5 * gy, 0)
    bp.link_to_collection(cliff_w, col_fort)

    ruin_w = bp.create_ruin_wall("ruin_wall", width=3.5, height=2.5, stone_mat=mats["M_Stone_Base"], foliage_mat=mats["M_Foliage"])
    ruin_w.location = (9.5 * gx, 5 * gy, 0)
    bp.link_to_collection(ruin_w, col_fort)

    # 07. Stairs, Ramps & Bridges
    col_br = "07_Stairs_Ramps_Bridges"
    st_lg = bp.create_large_stairs("stairs_large", width=2.4, height=1.6, depth=3.0, stone_mat=mats["M_Stone_Base"])
    st_lg.location = (0 * gx, 6 * gy, 0)
    bp.link_to_collection(st_lg, col_br)

    ramp = bp.create_cart_ramp("ramp", width=2.2, length=3.5, height=1.2, stone_mat=mats["M_Stone_Base"])
    ramp.location = (1 * gx, 6 * gy, 0)
    bp.link_to_collection(ramp, col_br)

    plat = bp.create_stone_platform("platform", width=3.5, depth=3.5, height=1.0, stone_mat=mats["M_Stone_Base"])
    plat.location = (2.2 * gx, 6 * gy, 0)
    bp.link_to_collection(plat, col_br)

    arch_b = bp.create_arch_bridge("arch_bridge", span=5.0, width=2.0, arch_height=1.8, stone_mat=mats["M_Stone_Base"], foliage_mat=mats["M_Foliage"])
    arch_b.location = (3.8 * gx, 6 * gy, 0)
    bp.link_to_collection(arch_b, col_br)

    st_b = bp.create_stone_bridge("stone_bridge", length=4.5, width=2.2, stone_mat=mats["M_Stone_Base"], timber_mat=mats["M_Timber_Dark"])
    st_b.location = (5.6 * gx, 6 * gy, 0)
    bp.link_to_collection(st_b, col_br)

    # 08. Street & Ground Tiles
    col_gt = "08_Ground_Tiles"
    tile_types = ["stone_road", "cobblestone", "dirt_road", "plaza_tile", "wooden_deck", "dock_tile", "grassy_ground", "cliff_edge"]
    for i, tt in enumerate(tile_types):
        gt = bp.create_ground_tile(tt, tile_type=tt, size=3.0, height=0.15, mats=mats)
        gt.location = (i * gx, 7 * gy, 0)
        bp.link_to_collection(gt, col_gt)

    # 09. Fences & Barriers
    col_fen = "09_Fences_Barriers"
    f_wood = bp.create_fence_section("wood_fence", length=2.8, height=0.9, timber_mat=mats["M_Timber_Dark"])
    f_wood.location = (0 * gx, 8 * gy, 0)
    bp.link_to_collection(f_wood, col_fen)

    f_stone = bp.create_stone_fence("stone_fence", length=3.0, height=1.0, stone_mat=mats["M_Stone_Base"])
    f_stone.location = (1 * gx, 8 * gy, 0)
    bp.link_to_collection(f_stone, col_fen)

    f_iron = bp.create_iron_fence("iron_fence", length=2.8, height=1.2, iron_mat=mats["M_Iron_Metal"], stone_mat=mats["M_Stone_Base"])
    f_iron.location = (2 * gx, 8 * gy, 0)
    bp.link_to_collection(f_iron, col_fen)

    f_chain = bp.create_post_chain("post_chain", length=2.8, stone_mat=mats["M_Stone_Base"], iron_mat=mats["M_Iron_Metal"])
    f_chain.location = (3 * gx, 8 * gy, 0)
    bp.link_to_collection(f_chain, col_fen)

    f_hedge = bp.create_boxwood_hedge("hedge", length=3.0, height=1.1, width=0.6, hedge_mat=mats["M_Hedge_Green"])
    f_hedge.location = (4 * gx, 8 * gy, 0)
    bp.link_to_collection(f_hedge, col_fen)

    f_spikes = bp.create_defensive_spikes("spikes", length=2.8, timber_mat=mats["M_Timber_Dark"])
    f_spikes.location = (5 * gx, 8 * gy, 0)
    bp.link_to_collection(f_spikes, col_fen)

    f_gate = bp.create_small_gate("gate_small", width=1.1, height=1.1, timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"])
    f_gate.location = (6 * gx, 8 * gy, 0)
    bp.link_to_collection(f_gate, col_fen)

    # 10. Market & Street Props
    col_mkt = "10_Market_Street_Props"
    mkt_a = bp.create_market_stall_awning("market_stall_a", width=2.4, depth=1.4, height=2.2, stripe_mat=mats["M_Awning_Red"], timber_mat=mats["M_Timber_Dark"])
    mkt_a.location = (0 * gx, 9 * gy, 0)
    bp.link_to_collection(mkt_a, col_mkt)

    mkt_b = bp.create_market_stall_awning("market_stall_b", width=2.4, depth=1.4, height=2.2, stripe_mat=mats["M_Awning_Blue"], timber_mat=mats["M_Timber_Dark"])
    mkt_b.location = (1 * gx, 9 * gy, 0)
    bp.link_to_collection(mkt_b, col_mkt)

    cart = bp.create_handcart("cart", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"])
    cart.location = (2 * gx, 9 * gy, 0)
    bp.link_to_collection(cart, col_mkt)

    wagon = bp.create_cargo_wagon("wagon", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"])
    wagon.location = (3.2 * gx, 9 * gy, 0)
    bp.link_to_collection(wagon, col_mkt)

    sacks = bp.create_grain_sacks("sacks", num_sacks=3, straw_mat=mats["M_Straw"])
    sacks.location = (4.5 * gx, 9 * gy, 0)
    bp.link_to_collection(sacks, col_mkt)

    sp = bp.create_multi_signpost("signpost", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"])
    sp.location = (5.2 * gx, 9 * gy, 0)
    bp.link_to_collection(sp, col_mkt)

    nb = bp.create_notice_board("notice_board", timber_mat=mats["M_Timber_Dark"], roof_mat=mats["M_Roof_Tiles_Red"], paper_mat=mats["M_Plaster"])
    nb.location = (6.0 * gx, 9 * gy, 0)
    bp.link_to_collection(nb, col_mkt)

    # 11. Civic & Decorative Props
    col_dec = "11_Civic_Decorations"
    lamp = bp.create_street_lamp("street_lamp", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"])
    lamp.location = (0 * gx, 10 * gy, 0)
    bp.link_to_collection(lamp, col_dec)

    well = bp.create_village_well("well", stone_mat=mats["M_Stone_Base"], timber_mat=mats["M_Timber_Dark"], roof_mat=mats["M_Roof_Tiles_Red"], water_mat=mats["M_Glass"])
    well.location = (1 * gx, 10 * gy, 0)
    bp.link_to_collection(well, col_dec)

    fount = bp.create_water_fountain("fountain", stone_mat=mats["M_Marble_Statue"], water_mat=mats["M_Water_Fountain"])
    fount.location = (2.2 * gx, 10 * gy, 0)
    bp.link_to_collection(fount, col_dec)

    statue = bp.create_knight_statue("statue", stone_mat=mats["M_Marble_Statue"])
    statue.location = (3.5 * gx, 10 * gy, 0)
    bp.link_to_collection(statue, col_dec)

    bench = bp.create_wood_bench("bench", width=1.5, depth=0.5, height=0.55, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"])
    bench.location = (4.5 * gx, 10 * gy, 0)
    bp.link_to_collection(bench, col_dec)

    fbox = bp.create_flower_box_standalone("flower_box", length=1.4, timber_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"])
    fbox.location = (5.3 * gx, 10 * gy, 0)
    bp.link_to_collection(fbox, col_dec)

    # 12. Docks & Waterfront
    col_dk = "12_Docks_Waterfront"
    bollard = bp.create_dock_bollard("dock_post", timber_mat=mats["M_Timber_Dark"], rope_mat=mats["M_Straw"])
    bollard.location = (0 * gx, 11 * gy, 0)
    bp.link_to_collection(bollard, col_dk)

    pier = bp.create_dock_pier("pier", length=4.0, width=1.8, height=1.4, timber_mat=mats["M_Timber_Dark"])
    pier.location = (1 * gx, 11 * gy, 0)
    bp.link_to_collection(pier, col_dk)

    rboat = bp.create_rowboat("small_boat", length=3.2, width=1.2, timber_mat=mats["M_Timber_Dark"], oar_mat=mats["M_Wood_Planks"])
    rboat.location = (2.5 * gx, 11 * gy, 0)
    bp.link_to_collection(rboat, col_dk)

    sboat = bp.create_sailboat("sail_boat", length=4.8, width=1.8, timber_mat=mats["M_Timber_Dark"], sail_mat=mats["M_Canvas_Sail"], iron_mat=mats["M_Iron_Metal"])
    sboat.location = (4.0 * gx, 11 * gy, 0)
    bp.link_to_collection(sboat, col_dk)

    dk_crane = bp.create_dock_derrick_crane("dock_crane", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"])
    dk_crane.location = (5.8 * gx, 11 * gy, 0)
    bp.link_to_collection(dk_crane, col_dk)

    nets = bp.create_fishing_net_stack("net_stack", rope_mat=mats["M_Straw"], cloth_mat=mats["M_Canvas_Sail"])
    nets.location = (7.0 * gx, 11 * gy, 0)
    bp.link_to_collection(nets, col_dk)

    f_bar = bp.create_fish_barrel("fish_barrels", plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"], fish_mat=mats["M_Marble_Statue"])
    f_bar.location = (7.8 * gx, 11 * gy, 0)
    bp.link_to_collection(f_bar, col_dk)

    # 13. Nature & Environment
    col_nat = "13_Nature_Environment"
    tree_oak = bp.create_stylized_tree("tree_large", tree_type="oak", trunk_mat=mats["M_Timber_Dark"], foliage_mat=mats["M_Foliage"])
    tree_oak.location = (0 * gx, 12 * gy, 0)
    bp.link_to_collection(tree_oak, col_nat)

    tree_pine = bp.create_stylized_tree("tree_small", tree_type="pine", trunk_mat=mats["M_Timber_Dark"], foliage_mat=mats["M_Foliage"])
    tree_pine.location = (1.2 * gx, 12 * gy, 0)
    bp.link_to_collection(tree_pine, col_nat)

    tree_dead = bp.create_stylized_tree("dead_tree", tree_type="dead", trunk_mat=mats["M_Timber_Dark"])
    tree_dead.location = (2.2 * gx, 12 * gy, 0)
    bp.link_to_collection(tree_dead, col_nat)

    rock_lg = bp.create_rock_boulder("rock_large", size=(1.4, 1.1, 0.9), stone_mat=mats["M_Stone_Base"])
    rock_lg.location = (3.2 * gx, 12 * gy, 0)
    bp.link_to_collection(rock_lg, col_nat)

    boulder = bp.create_rock_boulder("boulder", size=(1.8, 1.4, 1.2), stone_mat=mats["M_Stone_Base"])
    boulder.location = (4.2 * gx, 12 * gy, 0)
    bp.link_to_collection(boulder, col_nat)

    pillar = bp.create_ruined_pillar("ruins_pillar", height=2.4, stone_mat=mats["M_Marble_Statue"])
    pillar.location = (5.2 * gx, 12 * gy, 0)
    bp.link_to_collection(pillar, col_nat)

    # 14. Interior Furniture
    col_int = "14_Interior_Furniture"
    bed = bp.create_medieval_bed("bed", timber_mat=mats["M_Timber_Dark"], cloth_mat=mats["M_Cloth_Red"], sheet_mat=mats["M_Cloth_White"])
    bed.location = (0 * gx, 13 * gy, 0)
    bp.link_to_collection(bed, col_int)

    chair = bp.create_dining_chair("chair", timber_mat=mats["M_Timber_Dark"])
    chair.location = (1 * gx, 13 * gy, 0)
    bp.link_to_collection(chair, col_int)

    bookshelf = bp.create_bookshelf_with_books("bookshelf", timber_mat=mats["M_Timber_Dark"], book_mat=mats["M_Book_Spines"])
    bookshelf.location = (1.8 * gx, 13 * gy, 0)
    bp.link_to_collection(bookshelf, col_int)

    fp = bp.create_hearth_fireplace("fireplace", stone_mat=mats["M_Stone_Base"], ember_mat=mats["M_Fire_Embers"], timber_mat=mats["M_Timber_Dark"])
    fp.location = (2.8 * gx, 13 * gy, 0)
    bp.link_to_collection(fp, col_int)

    rug = bp.create_carpet_rug("rug", width=2.0, length=2.8, rug_mat=mats["M_Carpet_Rug"])
    rug.location = (3.8 * gx, 13 * gy, 0)
    bp.link_to_collection(rug, col_int)

    chest = bp.create_treasure_chest("chest", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], gold_mat=mats["M_Gold_Brass"])
    chest.location = (4.8 * gx, 13 * gy, 0)
    bp.link_to_collection(chest, col_int)

    ladder = bp.create_wooden_ladder("ladder", length=2.8, timber_mat=mats["M_Timber_Dark"])
    ladder.location = (5.5 * gx, 13 * gy, 0)
    bp.link_to_collection(ladder, col_int)

    st_int = bp.create_interior_stairs("stairs_interior", width=1.0, height=2.4, timber_mat=mats["M_Timber_Dark"])
    st_int.location = (6.4 * gx, 13 * gy, 0)
    bp.link_to_collection(st_int, col_int)

    # Lighting
    sun_data = bpy.data.lights.new(name="SunPreview", type='SUN')
    sun_data.energy = 4.5
    sun_data.color = (1.0, 0.95, 0.88)
    sun_obj = bpy.data.objects.new("SunPreview", sun_data)
    sun_obj.rotation_euler = (0.785, 0.35, 0.65)
    scene.collection.objects.link(sun_obj)

    # Master Overview Camera
    from math import radians
    cam_data = bpy.data.cameras.new("Cam_Modular_Kit")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 68.0
    cam_obj = bpy.data.objects.new("Cam_Modular_Kit", cam_data)
    cx, cy, cz = 14.0, 26.0, 2.0
    dist = 50.0
    cam_obj.location = (cx + dist, cy - dist, cz + dist)
    cam_obj.rotation_euler = (radians(54.736), 0, radians(45.0))
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    out_path = "d:/assests/emberglass_modular_kit.blend"
    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print(f"Complete Emberglass Modular Asset Kit saved to: {out_path}")

if __name__ == "__main__":
    build_kit()
