"""
Render all 109 Emberglass Library sprites with transparent background (RGBA)
for the Master Presentation Sheet.
Outputs to d:/assests/renders/sheet_sprites/
"""

import bpy
import bmesh
from mathutils import Vector
from math import radians, cos, sin, sqrt
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import materials
import builder_primitives as bp

out_dir = "d:/assests/renders/sheet_sprites"
os.makedirs(out_dir, exist_ok=True)

def render_buildings_transparent():
    """Render 8 baseline buildings with transparent film."""
    blend_path = "d:/assests/emberglass_buildings.blend"
    if not os.path.exists(blend_path):
        print(f"Warning: {blend_path} not found!")
        return
    print(f"Loading {blend_path}...")
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = True
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    
    bld_cams = [
        ("Cam_Cottage", "bld_cottage.png"),
        ("Cam_Townhouse", "bld_townhouse.png"),
        ("Cam_Tenement", "bld_tenement.png"),
        ("Cam_Tavern", "bld_tavern.png"),
        ("Cam_Shop", "bld_shop.png"),
        ("Cam_Blacksmith", "bld_blacksmith.png"),
        ("Cam_Stables", "bld_stables.png"),
        ("Cam_Warehouse", "bld_warehouse.png"),
    ]
    for cam_name, fname in bld_cams:
        if cam_name in bpy.data.objects:
            print(f"Rendering {cam_name} -> {fname}...")
            scene.camera = bpy.data.objects[cam_name]
            scene.render.filepath = os.path.join(out_dir, fname)
            bpy.ops.render.render(write_still=True)

def render_monuments_and_variations_transparent():
    """Render 8 monuments and 4 variations with transparent film."""
    blend_path = "d:/assests/emberglass_monuments.blend"
    if not os.path.exists(blend_path):
        print(f"Warning: {blend_path} not found!")
        return
    print(f"Loading {blend_path}...")
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = True
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    
    mon_cams = [
        ("Cam_Manor", "monument_noble_manor.png"),
        ("Cam_Guildhouse", "monument_guildhouse.png"),
        ("Cam_Chapel", "monument_chapel.png"),
        ("Cam_Church", "monument_church.png"),
        ("Cam_Windmill", "monument_windmill.png"),
        ("Cam_Watchtower", "monument_watchtower.png"),
        ("Cam_Gatehouse", "monument_gatehouse.png"),
        ("Cam_Keep", "monument_keep.png"),
        ("Cam_Townhouse_Normal", "variation_normal.png"),
        ("Cam_Townhouse_WithStall", "variation_with_stall.png"),
        ("Cam_Townhouse_Damaged", "variation_damaged.png"),
        ("Cam_Townhouse_Ruin", "variation_ruin.png"),
    ]
    for cam_name, fname in mon_cams:
        if cam_name in bpy.data.objects:
            print(f"Rendering {cam_name} -> {fname}...")
            scene.camera = bpy.data.objects[cam_name]
            scene.render.filepath = os.path.join(out_dir, fname)
            bpy.ops.render.render(write_still=True)

def setup_prop_render_scene():
    """Creates a clean studio scene for prop sprite rendering."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
        
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = True
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    
    # Lighting: Warm key sun + cool fill
    sun_data = bpy.data.lights.new("StudioSun", type='SUN')
    sun_data.energy = 4.2
    sun_data.color = (1.0, 0.94, 0.86)
    sun_obj = bpy.data.objects.new("StudioSun", sun_data)
    sun_obj.rotation_euler = (radians(45), radians(20), radians(60))
    scene.collection.objects.link(sun_obj)
    
    fill_data = bpy.data.lights.new("StudioFill", type='SUN')
    fill_data.energy = 1.6
    fill_data.color = (0.75, 0.85, 1.0)
    fill_obj = bpy.data.objects.new("StudioFill", fill_data)
    fill_obj.rotation_euler = (radians(-30), radians(-40), radians(-120))
    scene.collection.objects.link(fill_obj)
    
    # Orthographic Camera
    cam_data = bpy.data.cameras.new("PropCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 4.5
    cam_obj = bpy.data.objects.new("PropCam", cam_data)
    cam_obj.rotation_euler = (radians(54.736), 0, radians(45.0))
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    
    return cam_obj, cam_data

def render_prop_sprite(prop_obj, fname, cam_obj, cam_data, ortho_scale=4.5, z_offset=0.0):
    """Frames and renders a single prop object."""
    scene = bpy.context.scene
    # Position camera based on bounds
    bbox = [prop_obj.matrix_world @ Vector(corner) for corner in prop_obj.bound_box]
    center = sum(bbox, Vector((0,0,0))) / 8.0
    center.z += z_offset
    
    dist = 25.0
    cam_obj.location = (center.x + dist, center.y - dist, center.z + dist)
    cam_data.ortho_scale = ortho_scale
    
    scene.render.filepath = os.path.join(out_dir, fname)
    bpy.ops.render.render(write_still=True)
    
    # Cleanup object
    bpy.data.objects.remove(prop_obj, do_unlink=True)

def render_all_props():
    """Generates and renders all modular kit props."""
    cam_obj, cam_data = setup_prop_render_scene()
    mats = materials.setup_all_materials()
    scene = bpy.context.scene
    
    props = [
        # BOX 3: WALLS & FORTIFICATIONS
        (lambda: bp.create_curtain_wall("wall_straight", width=3.6, height=3.2, depth=1.2, stone_mat=mats["M_Stone_Base"]), "wall_straight.png", 5.2, 0.0),
        (lambda: bp.create_wall_corner("wall_corner", width=2.8, height=3.2, stone_mat=mats["M_Stone_Base"]), "wall_corner.png", 4.8, 0.0),
        (lambda: bp.create_wall_tower("wall_tower", radius=1.5, height=5.2, stone_mat=mats["M_Stone_Base"], banner_mat=mats["M_Cloth_Red"]), "wall_tower.png", 6.8, 0.2),
        (lambda: bp.create_castle_gate_portal("gatehouse_wall", width=4.0, height=3.8, depth=1.5, stone_mat=mats["M_Stone_Base"], iron_mat=mats["M_Iron_Metal"], banner_mat=mats["M_Cloth_Red"]), "wall_gatehouse.png", 5.6, 0.0),
        (lambda: bp.create_castle_gate_portal("castle_gate", width=5.0, height=4.5, depth=1.8, stone_mat=mats["M_Stone_Base"], iron_mat=mats["M_Iron_Metal"], timber_mat=mats["M_Timber_Dark"]), "castle_gate.png", 6.6, 0.0),
        (lambda: bp.create_retaining_wall("retaining_wall", width=3.8, height=2.2, depth=1.0, stone_mat=mats["M_Stone_Base"], timber_mat=mats["M_Timber_Dark"]), "retaining_wall.png", 4.8, 0.0),
        (lambda: bp.create_cliff_wall("cliff_wall", width=3.8, height=2.8, stone_mat=mats["M_Stone_Base"], foliage_mat=mats["M_Foliage"]), "cliff_wall.png", 5.0, 0.0),
        (lambda: bp.create_ruin_wall("ruin_wall", width=3.4, height=2.4, stone_mat=mats["M_Stone_Base"], foliage_mat=mats["M_Foliage"]), "ruin_wall.png", 4.8, 0.0),

        # BOX 4: STAIRS, RAMPS & ELEVATION
        (lambda: bp.create_stone_steps("stairs_small", width=1.8, depth=1.4, height=0.7, stone_mat=mats["M_Stone_Base"]), "stairs_small.png", 3.0, 0.0),
        (lambda: bp.create_large_stairs("stairs_large", width=2.2, height=1.6, depth=2.8, stone_mat=mats["M_Stone_Base"]), "stairs_large.png", 4.2, 0.0),
        (lambda: bp.create_cart_ramp("ramp", width=2.2, length=3.4, height=1.2, stone_mat=mats["M_Stone_Base"]), "ramp.png", 4.6, 0.0),
        (lambda: bp.create_stone_platform("platform", width=3.2, depth=3.2, height=1.0, stone_mat=mats["M_Stone_Base"]), "platform.png", 4.8, 0.0),
        (lambda: bp.create_arch_bridge("arch_bridge", span=4.8, width=2.0, arch_height=1.8, stone_mat=mats["M_Stone_Base"], foliage_mat=mats["M_Foliage"]), "arch_bridge.png", 5.6, 0.0),
        (lambda: bp.create_stone_bridge("stone_bridge", length=4.4, width=2.2, stone_mat=mats["M_Stone_Base"], timber_mat=mats["M_Timber_Dark"]), "stone_bridge.png", 5.4, 0.0),

        # BOX 5: STREET & GROUND TILES
        (lambda: bp.create_ground_tile("stone_road", tile_type="stone_road", size=2.8, height=0.15, mats=mats), "stone_road.png", 3.8, 0.0),
        (lambda: bp.create_ground_tile("cobblestone", tile_type="cobblestone", size=2.8, height=0.15, mats=mats), "cobblestone.png", 3.8, 0.0),
        (lambda: bp.create_ground_tile("dirt_road", tile_type="dirt_road", size=2.8, height=0.15, mats=mats), "dirt_road.png", 3.8, 0.0),
        (lambda: bp.create_ground_tile("plaza_tile", tile_type="plaza_tile", size=2.8, height=0.15, mats=mats), "plaza_tile.png", 3.8, 0.0),
        (lambda: bp.create_ground_tile("wooden_deck", tile_type="wooden_deck", size=2.8, height=0.15, mats=mats), "wooden_deck.png", 3.8, 0.0),
        (lambda: bp.create_ground_tile("dock_tile", tile_type="dock_tile", size=2.8, height=0.15, mats=mats), "dock_tile.png", 3.8, 0.0),
        (lambda: bp.create_ground_tile("grassy_ground", tile_type="grassy_ground", size=2.8, height=0.15, mats=mats), "grassy_ground.png", 3.8, 0.0),
        (lambda: bp.create_ground_tile("cliff_edge", tile_type="cliff_edge", size=2.8, height=0.15, mats=mats), "cliff_edge.png", 3.8, 0.0),

        # BOX 6: FENCES & BARRIERS
        (lambda: bp.create_fence_section("wood_fence", length=2.8, height=0.9, timber_mat=mats["M_Timber_Dark"]), "wood_fence.png", 3.6, 0.0),
        (lambda: bp.create_stone_fence("stone_fence", length=2.8, height=1.0, stone_mat=mats["M_Stone_Base"]), "stone_fence.png", 3.6, 0.0),
        (lambda: bp.create_iron_fence("iron_fence", length=2.8, height=1.2, iron_mat=mats["M_Iron_Metal"], stone_mat=mats["M_Stone_Base"]), "iron_fence.png", 3.6, 0.0),
        (lambda: bp.create_railing("railing", length=2.8, height=0.9, timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"]), "railing.png", 3.6, 0.0),
        (lambda: bp.create_post_chain("post_chain", length=2.8, stone_mat=mats["M_Stone_Base"], iron_mat=mats["M_Iron_Metal"]), "post_chain.png", 3.6, 0.0),
        (lambda: bp.create_boxwood_hedge("hedge", length=2.8, height=1.1, width=0.6, hedge_mat=mats["M_Hedge_Green"]), "hedge.png", 3.6, 0.0),
        (lambda: bp.create_defensive_spikes("spikes", length=2.8, timber_mat=mats["M_Timber_Dark"]), "spikes.png", 3.6, 0.0),
        (lambda: bp.create_small_gate("gate_small", width=1.2, height=1.1, timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"]), "gate_small.png", 2.4, 0.0),

        # BOX 7: MARKET & STREET PROPS
        (lambda: bp.create_market_stall_awning("market_stall_a", width=2.4, depth=1.4, height=2.2, stripe_mat=mats["M_Awning_Red"], timber_mat=mats["M_Timber_Dark"]), "market_stall_a.png", 3.8, 0.0),
        (lambda: bp.create_market_stall_awning("market_stall_b", width=2.4, depth=1.4, height=2.2, stripe_mat=mats["M_Awning_Blue"], timber_mat=mats["M_Timber_Dark"]), "market_stall_b.png", 3.8, 0.0),
        (lambda: bp.create_handcart("cart", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"]), "cart.png", 3.2, 0.0),
        (lambda: bp.create_cargo_wagon("wagon", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"]), "wagon.png", 4.2, 0.0),
        (lambda: bp.create_crate_stack("crates", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"]), "crates.png", 2.6, 0.0),
        (lambda: bp.create_barrel_group("barrels", plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"]), "barrels.png", 2.4, 0.0),
        (lambda: bp.create_grain_sacks("sacks", num_sacks=3, straw_mat=mats["M_Straw"]), "sacks.png", 2.2, 0.0),
        (lambda: bp.create_multi_signpost("signpost", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"]), "signpost.png", 3.0, 0.2),
        (lambda: bp.create_notice_board("notice_board", timber_mat=mats["M_Timber_Dark"], roof_mat=mats["M_Roof_Tiles_Red"], paper_mat=mats["M_Plaster"]), "notice_board.png", 3.2, 0.0),

        # BOX 8: DECORATIONS & SMALL PROPS
        (lambda: bp.create_street_lamp("street_lamp", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"]), "street_lamp.png", 3.4, 0.2),
        (lambda: bp.create_wall_lantern("wall_lantern", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"]), "wall_lantern.png", 2.0, 0.0),
        (lambda: bp.create_hanging_lantern("hanging_lantern", iron_mat=mats["M_Iron_Metal"], glow_mat=mats["M_Lantern_Glow"]), "hanging_lantern.png", 3.6, 0.2),
        (lambda: bp.create_village_well("well", stone_mat=mats["M_Stone_Base"], timber_mat=mats["M_Timber_Dark"], roof_mat=mats["M_Roof_Tiles_Red"], water_mat=mats["M_Glass"]), "well.png", 3.4, 0.0),
        (lambda: bp.create_wood_bench("bench", width=1.5, depth=0.5, height=0.55, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"]), "bench.png", 2.4, 0.0),
        (lambda: bp.create_planter("planter", stone_mat=mats["M_Stone_Base"], flower_mat=mats["M_Flowers"], foliage_mat=mats["M_Foliage"]), "planter.png", 2.2, 0.0),
        (lambda: bp.create_water_fountain("fountain", stone_mat=mats["M_Marble_Statue"], water_mat=mats["M_Water_Fountain"]), "fountain.png", 3.6, 0.0),
        (lambda: bp.create_knight_statue("statue", stone_mat=mats["M_Marble_Statue"]), "statue.png", 3.4, 0.2),
        (lambda: bp.create_stylized_tree("tree_small", tree_type="pine", trunk_mat=mats["M_Timber_Dark"], foliage_mat=mats["M_Foliage"]), "tree_small.png", 4.2, 0.2),
        (lambda: bp.create_stylized_tree("tree_large", tree_type="oak", trunk_mat=mats["M_Timber_Dark"], foliage_mat=mats["M_Foliage"]), "tree_large.png", 4.8, 0.2),
        (lambda: bp.create_bush("bush", foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"]), "bush.png", 2.2, 0.0),
        (lambda: bp.create_flower_box_standalone("flower_box", length=1.4, timber_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"]), "flower_box.png", 2.2, 0.0),

        # BOX 9: DOCKS & WATERFRONT
        (lambda: bp.create_dock_bollard("dock_post", timber_mat=mats["M_Timber_Dark"], rope_mat=mats["M_Straw"]), "dock_post.png", 2.2, 0.0),
        (lambda: bp.create_dock_platform("dock_platform", width=2.4, depth=2.4, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"]), "dock_platform.png", 3.8, 0.0),
        (lambda: bp.create_dock_pier("pier", length=3.8, width=1.8, height=1.4, timber_mat=mats["M_Timber_Dark"]), "pier.png", 4.6, 0.0),
        (lambda: bp.create_rowboat("small_boat", length=3.2, width=1.2, timber_mat=mats["M_Timber_Dark"], oar_mat=mats["M_Wood_Planks"]), "small_boat.png", 4.0, 0.0),
        (lambda: bp.create_sailboat("sail_boat", length=4.6, width=1.8, timber_mat=mats["M_Timber_Dark"], sail_mat=mats["M_Canvas_Sail"], iron_mat=mats["M_Iron_Metal"]), "sail_boat.png", 5.6, 0.3),
        (lambda: bp.create_dock_derrick_crane("crane", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"]), "crane.png", 4.8, 0.2),
        (lambda: bp.create_fishing_net_stack("net_stack", rope_mat=mats["M_Straw"], cloth_mat=mats["M_Canvas_Sail"]), "net_stack.png", 2.6, 0.0),
        (lambda: bp.create_fish_barrel("fish_barrels", plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron_Metal"], fish_mat=mats["M_Marble_Statue"]), "fish_barrels.png", 2.4, 0.0),

        # BOX 10: MISCELLANEOUS
        (lambda: bp.create_clothesline_standalone("clothesline", span=2.8, timber_mat=mats["M_Timber_Dark"], cloth_white=mats["M_Cloth_White"], cloth_blue=mats["M_Cloth_Blue"], cloth_red=mats["M_Cloth_Red"]), "clothesline.png", 3.8, 0.0),
        (lambda: bp.create_heraldic_banner("banners", emblem_type="tavern", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], cloth_mat=mats["M_Cloth_Red"], gold_mat=mats["M_Gold_Brass"]), "banners.png", 3.2, 0.0),
        (lambda: bp.create_flags_standalone("flags", timber_mat=mats["M_Timber_Dark"], banner_mat=mats["M_Cloth_Red"], iron_mat=mats["M_Iron_Metal"]), "flags.png", 3.2, 0.0),
        (lambda: bp.create_awning_standalone("awning", width=2.4, depth=1.3, stripe_mat=mats["M_Awning_Blue"], timber_mat=mats["M_Timber_Dark"]), "awning.png", 3.4, 0.0),
        (lambda: bp.create_balcony_unit("balcony", width=2.2, depth=1.1, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"]), "balcony.png", 3.2, 0.0),
        (lambda: bp.create_chimney_smoke_standalone("chimney_smoke", stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke"]), "chimney_smoke.png", 3.8, 0.2),
        (lambda: bp.create_bookshelf_with_books("bookshelf", timber_mat=mats["M_Timber_Dark"], book_mat=mats["M_Book_Spines"]), "bookshelf.png", 2.8, 0.0),
        (lambda: bp.create_table_set("table_set", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"]), "table_set.png", 3.2, 0.0),
        (lambda: bp.create_hay_bale("hay_stack", width=1.2, length=1.6, height=0.9, straw_mat=mats["M_Straw"]), "hay_stack.png", 2.6, 0.0),
        (lambda: bp.create_firewood_stack("wood_pile", width=1.6, height=0.9, depth=0.9, timber_mat=mats["M_Timber_Dark"]), "wood_pile.png", 2.6, 0.0),

        # BOX 11: ENVIRONMENT / NATURE
        (lambda: bp.create_rock_boulder("rock_large", size=(1.5, 1.2, 1.0), stone_mat=mats["M_Stone_Base"]), "rock_large.png", 2.6, 0.0),
        (lambda: bp.create_rock_small("rock_small", stone_mat=mats["M_Stone_Base"]), "rock_small.png", 2.0, 0.0),
        (lambda: bp.create_rock_boulder("boulder", size=(1.8, 1.4, 1.2), stone_mat=mats["M_Stone_Base"]), "boulder.png", 3.0, 0.0),
        (lambda: bp.create_grass_patch("grass_patch", radius=1.0, grass_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"]), "grass_patch.png", 2.4, 0.0),
        (lambda: bp.create_flowers("flowers", radius=0.8, foliage_mat=mats["M_Foliage"], flower_mat=mats["M_Flowers"]), "flowers.png", 2.2, 0.0),
        (lambda: bp.create_tree_group("tree_group", trunk_mat=mats["M_Timber_Dark"], foliage_mat=mats["M_Foliage"]), "tree_group.png", 5.2, 0.2),
        (lambda: bp.create_vines("vines", height=2.4, foliage_mat=mats["M_Foliage"]), "vines.png", 3.2, 0.0),
        (lambda: bp.create_ivy_wall("ivy_wall", width=2.4, height=2.4, stone_mat=mats["M_Stone_Base"], foliage_mat=mats["M_Foliage"]), "ivy_wall.png", 3.6, 0.0),
        (lambda: bp.create_stylized_tree("dead_tree", tree_type="dead", trunk_mat=mats["M_Timber_Dark"]), "dead_tree.png", 4.2, 0.2),
        (lambda: bp.create_ruined_pillar("ruins_pillar", height=2.4, stone_mat=mats["M_Marble_Statue"]), "ruins_pillar.png", 3.6, 0.1),

        # BOX 12: INTERIOR / OPTIONAL
        (lambda: bp.create_medieval_bed("bed", timber_mat=mats["M_Timber_Dark"], cloth_mat=mats["M_Cloth_Red"], sheet_mat=mats["M_Cloth_White"]), "bed.png", 3.2, 0.0),
        (lambda: bp.create_table("table", width=1.8, depth=1.0, height=0.85, timber_mat=mats["M_Timber_Dark"]), "table.png", 2.8, 0.0),
        (lambda: bp.create_dining_chair("chair", timber_mat=mats["M_Timber_Dark"]), "chair.png", 2.0, 0.0),
        (lambda: bp.create_shelf("shelf", width=1.2, height=1.8, depth=0.4, timber_mat=mats["M_Timber_Dark"], pottery_mat=mats["M_Wood_Planks"]), "shelf.png", 2.8, 0.0),
        (lambda: bp.create_hearth_fireplace("fireplace", stone_mat=mats["M_Stone_Base"], ember_mat=mats["M_Fire_Embers"], timber_mat=mats["M_Timber_Dark"]), "fireplace.png", 3.4, 0.0),
        (lambda: bp.create_carpet_rug("rug", width=2.0, length=2.8, rug_mat=mats["M_Carpet_Rug"]), "rug.png", 3.4, 0.0),
        (lambda: bp.create_curtain("curtain", width=1.4, height=2.2, cloth_mat=mats["M_Cloth_Blue"], rod_mat=mats["M_Gold_Brass"]), "curtain.png", 3.2, 0.0),
        (lambda: bp.create_treasure_chest("chest", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron_Metal"], gold_mat=mats["M_Gold_Brass"]), "chest.png", 2.2, 0.0),
        (lambda: bp.create_wooden_ladder("ladder", length=2.8, timber_mat=mats["M_Timber_Dark"]), "ladder.png", 3.2, 0.0),
        (lambda: bp.create_interior_stairs("stairs_interior", width=1.0, height=2.4, timber_mat=mats["M_Timber_Dark"]), "stairs_interior.png", 3.6, 0.0),
    ]
    
    total = len(props)
    for idx, (gen_fn, fname, oscale, zoff) in enumerate(props, 1):
        target_path = os.path.join(out_dir, fname)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
            print(f"[{idx}/{total}] Already rendered {fname}, skipping...")
            continue
        print(f"[{idx}/{total}] Generating & rendering {fname}...")
        obj = gen_fn()
        scene.collection.objects.link(obj)
        render_prop_sprite(obj, fname, cam_obj, cam_data, ortho_scale=oscale, z_offset=zoff)

def main():
    print("=== STARTING FULL EMBERGLASS SPRITE BATCH RENDERING ===")
    render_buildings_transparent()
    render_monuments_and_variations_transparent()
    render_all_props()
    print("=== ALL SPRITES RENDERED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
