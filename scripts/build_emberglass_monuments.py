"""
Emberglass Monumental Buildings & Building State Variations Generator (Polished Edition)
Direct 1:1 reproduction of the new Emberglass concept art sheet:
- 8 Monumental Buildings: Noble Manor, Guildhouse, Chapel, Church (Cathedral),
  Windmill, Watchtower, Gatehouse, Castle Keep
- 4 Building State Variations: Townhouse Normal, With Stall, Damaged, Ruin
Built for Blender 4.2 LTS headless.
"""

import bpy
import bmesh
import sys
import os
from math import radians, cos, sin, tan, pi
from mathutils import Vector, Matrix, Euler

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
    world = bpy.data.worlds.new("Emberglass_Monuments_World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    
    out = nodes.new(type='ShaderNodeOutputWorld')
    bg = nodes.new(type='ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.055, 0.075, 0.105, 1.0)
    bg.inputs['Strength'].default_value = 1.0
    links.new(bg.outputs['Background'], out.inputs['Surface'])

def create_pedestal(name, width, depth, height=0.4, origin=(0,0,0), mats=None, col_name=None):
    base = bp.create_box(name + "_Curb", size=(width, depth, height), location=(origin[0], origin[1], origin[2] - height/2.0), material=mats["M_Stone_Base"], bevel=0.03)
    pave = bp.create_box(name + "_Paving", size=(width - 0.25, depth - 0.25, 0.06), location=(origin[0], origin[1], origin[2] + 0.02), material=mats["M_Cobblestone"], bevel=0.01)
    if col_name:
        bp.link_to_collection(base, col_name)
        bp.link_to_collection(pave, col_name)
    return base, pave

# -------------------------------------------------------------
# Architectural Helpers for Monuments
# -------------------------------------------------------------

def create_cylinder(name, radius=0.3, height=1.0, location=(0,0,0), material=None, segments=16):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if material:
        obj.data.materials.append(material)
    bm = bmesh.new()
    cyl = bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=height)
    for v in cyl['verts']:
        v.co.z += height / 2.0
    bm.to_mesh(mesh)
    bm.free()
    obj.location = location
    bp.add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_arched_stained_glass_window(name, width=1.1, height=2.4, stone_mat=None, glass_mat=None, iron_mat=None):
    """Gothic pointed lancet stained-glass window with stone arch surround."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, glass_mat, iron_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    fw = 0.15
    fd = 0.22
    
    # Left & Right Stone Jambs
    for sx in [-width/2 - fw/2, width/2 + fw/2]:
        j = bp.add_box(bm, material_index=0)
        for v in j:
            v.co.x = v.co.x * fw + sx
            v.co.y = (v.co.y - 0.5) * fd
            v.co.z = (v.co.z + 0.5) * (height - width/2)
            
    # Projecting Sill
    sill = bp.add_box(bm, material_index=0)
    for v in sill:
        v.co.x *= (width + fw * 3.0)
        v.co.y = (v.co.y - 0.5) * (fd + 0.12)
        v.co.z = (v.co.z + 0.5) * 0.14 - 0.10
        
    # Stone Arch Top
    arch_segments = 12
    r_out = width/2 + fw
    r_in = width/2
    cy = -fd/2
    cz = height - width/2
    
    for i in range(arch_segments):
        a0 = pi * (i / arch_segments)
        a1 = pi * ((i + 1) / arch_segments)
        v0 = bm.verts.new((cos(a0) * r_out, cy - fd/2, cz + sin(a0) * r_out))
        v1 = bm.verts.new((cos(a1) * r_out, cy - fd/2, cz + sin(a1) * r_out))
        v2 = bm.verts.new((cos(a1) * r_in,  cy - fd/2, cz + sin(a1) * r_in))
        v3 = bm.verts.new((cos(a0) * r_in,  cy - fd/2, cz + sin(a0) * r_in))
        f_front = bm.faces.new((v0, v1, v2, v3))
        f_front.material_index = 0
        
        v4 = bm.verts.new((cos(a0) * r_out, cy + fd/2, cz + sin(a0) * r_out))
        v5 = bm.verts.new((cos(a1) * r_out, cy + fd/2, cz + sin(a1) * r_out))
        v6 = bm.verts.new((cos(a1) * r_in,  cy + fd/2, cz + sin(a1) * r_in))
        v7 = bm.verts.new((cos(a0) * r_in,  cy + fd/2, cz + sin(a0) * r_in))
        f_back = bm.faces.new((v7, v6, v5, v4))
        f_back.material_index = 0
        
        f_top = bm.faces.new((v0, v4, v5, v1))
        f_top.material_index = 0
        f_bot = bm.faces.new((v3, v2, v6, v7))
        f_bot.material_index = 0

    # Radiant Stained Glass Pane
    g_body = bp.add_box(bm, material_index=1)
    for v in g_body:
        v.co.x *= width
        v.co.y = v.co.y * 0.04 - fd * 0.35
        v.co.z = (v.co.z + 0.5) * (height - width/2)
        
    for i in range(arch_segments):
        a0 = pi * (i / arch_segments)
        a1 = pi * ((i + 1) / arch_segments)
        v0 = bm.verts.new((0, cy, cz))
        v1 = bm.verts.new((cos(a0) * width/2, cy, cz + sin(a0) * width/2))
        v2 = bm.verts.new((cos(a1) * width/2, cy, cz + sin(a1) * width/2))
        f_g = bm.faces.new((v0, v1, v2))
        f_g.material_index = 1
        
    # Vertical Iron Tracery Mullion
    mull = bp.add_box(bm, material_index=2)
    for v in mull:
        v.co.x *= 0.04
        v.co.y = v.co.y * 0.04 - fd * 0.40
        v.co.z = (v.co.z + 0.5) * height
        
    bm.to_mesh(mesh)
    bm.free()
    bp.add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

def create_gothic_rose_window(name, radius=1.6, depth=0.35, stone_mat=None, glass_mat=None):
    """Circular Gothic rose window with stone tracery spokes and radiant stained glass."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, glass_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    segs = 24
    rim_w = 0.22
    
    for i in range(segs):
        a0 = 2 * pi * (i / segs)
        a1 = 2 * pi * ((i + 1) / segs)
        r0 = radius + rim_w
        r1 = radius
        v0 = bm.verts.new((cos(a0)*r0, -depth/2, sin(a0)*r0))
        v1 = bm.verts.new((cos(a1)*r0, -depth/2, sin(a1)*r0))
        v2 = bm.verts.new((cos(a1)*r1, -depth/2, sin(a1)*r1))
        v3 = bm.verts.new((cos(a0)*r1, -depth/2, sin(a0)*r1))
        f = bm.faces.new((v0, v1, v2, v3))
        f.material_index = 0
        
        v4 = bm.verts.new((cos(a0)*r0, depth/2, sin(a0)*r0))
        v5 = bm.verts.new((cos(a1)*r0, depth/2, sin(a1)*r0))
        v6 = bm.verts.new((cos(a1)*r1, depth/2, sin(a1)*r1))
        v7 = bm.verts.new((cos(a0)*r1, depth/2, sin(a0)*r1))
        f = bm.faces.new((v7, v6, v5, v4))
        f.material_index = 0
        
        f_ext = bm.faces.new((v0, v4, v5, v1))
        f_ext.material_index = 0
        f_int = bm.faces.new((v3, v2, v6, v7))
        f_int.material_index = 0

    disc_v0 = bm.verts.new((0, 0, 0))
    for i in range(segs):
        a0 = 2 * pi * (i / segs)
        a1 = 2 * pi * ((i + 1) / segs)
        v1 = bm.verts.new((cos(a0)*radius, 0, sin(a0)*radius))
        v2 = bm.verts.new((cos(a1)*radius, 0, sin(a1)*radius))
        f = bm.faces.new((disc_v0, v1, v2))
        f.material_index = 1
        
    num_spokes = 8
    for sp in range(num_spokes):
        ang = 2 * pi * (sp / num_spokes)
        spoke = bp.add_box(bm, material_index=0)
        for v in spoke:
            v.co.x *= 0.09
            v.co.y *= (depth * 0.7)
            v.co.z = (v.co.z + 0.5) * radius
            
            rx = v.co.x * cos(ang) - v.co.z * sin(ang)
            rz = v.co.x * sin(ang) + v.co.z * cos(ang)
            v.co.x = rx
            v.co.z = rz

    boss = bp.add_box(bm, material_index=0)
    for v in boss:
        v.co.x *= 0.45
        v.co.y *= (depth * 0.9)
        v.co.z *= 0.45
        
    bm.to_mesh(mesh)
    bm.free()
    bp.add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_octagonal_stone_tower(name, r_base=2.6, r_top=2.0, height=7.8, stone_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat:
        obj.data.materials.append(stone_mat)
        
    bm = bmesh.new()
    segs = 8
    plinth_h = 1.0
    r_plinth = r_base + 0.22
    
    b_verts = []
    p_verts = []
    t_verts = []
    
    for i in range(segs):
        ang = 2 * pi * (i / segs) + pi/8
        b_verts.append(bm.verts.new((cos(ang)*r_plinth, sin(ang)*r_plinth, 0)))
        p_verts.append(bm.verts.new((cos(ang)*r_base, sin(ang)*r_base, plinth_h)))
        t_verts.append(bm.verts.new((cos(ang)*r_top, sin(ang)*r_top, height)))
        
    for i in range(segs):
        i_next = (i + 1) % segs
        f1 = bm.faces.new((b_verts[i], b_verts[i_next], p_verts[i_next], p_verts[i]))
        f1.material_index = 0
        f2 = bm.faces.new((p_verts[i], p_verts[i_next], t_verts[i_next], t_verts[i]))
        f2.material_index = 0
        
    rim_verts = []
    r_rim = r_top + 0.18
    for i in range(segs):
        ang = 2 * pi * (i / segs) + pi/8
        rim_verts.append(bm.verts.new((cos(ang)*r_rim, sin(ang)*r_rim, height + 0.25)))
        
    for i in range(segs):
        i_next = (i + 1) % segs
        f3 = bm.faces.new((t_verts[i], t_verts[i_next], rim_verts[i_next], rim_verts[i]))
        f3.material_index = 0
        
    bm.to_mesh(mesh)
    bm.free()
    bp.add_bevel_modifier(obj, width=0.018, segments=2)
    return obj

def create_crenellated_parapet(name, width_x=4.2, depth_y=4.2, height=1.1, wall_thick=0.35, merlons_per_side=4, stone_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat:
        obj.data.materials.append(stone_mat)
        
    bm = bmesh.new()
    for side in ['front', 'back', 'left', 'right']:
        if side in ['front', 'back']:
            sy = -depth_y/2 + wall_thick/2 if side == 'front' else depth_y/2 - wall_thick/2
            base = bp.add_box(bm, material_index=0)
            for v in base:
                v.co.x *= width_x
                v.co.y = v.co.y * wall_thick + sy
                v.co.z = (v.co.z + 0.5) * 0.35
        else:
            sx = -width_x/2 + wall_thick/2 if side == 'left' else width_x/2 - wall_thick/2
            base = bp.add_box(bm, material_index=0)
            for v in base:
                v.co.x = v.co.x * wall_thick + sx
                v.co.y *= (depth_y - wall_thick * 2.0)
                v.co.z = (v.co.z + 0.5) * 0.35
                
    merlon_w = (width_x / (merlons_per_side * 2 - 1))
    merlon_h = height - 0.35
    
    for side in ['front', 'back']:
        sy = -depth_y/2 + wall_thick/2 if side == 'front' else depth_y/2 - wall_thick/2
        for m in range(merlons_per_side):
            mx = -width_x/2 + merlon_w/2 + m * (merlon_w * 2)
            merlon = bp.add_box(bm, material_index=0)
            for v in merlon:
                v.co.x = v.co.x * (merlon_w * 0.92) + mx
                v.co.y = v.co.y * wall_thick + sy
                v.co.z = (v.co.z + 0.5) * merlon_h + 0.35
                
    merlons_y = merlons_per_side
    merlon_d = (depth_y / (merlons_y * 2 - 1))
    for side in ['left', 'right']:
        sx = -width_x/2 + wall_thick/2 if side == 'left' else width_x/2 - wall_thick/2
        for m in range(1, merlons_y - 1):
            my = -depth_y/2 + merlon_d/2 + m * (merlon_d * 2)
            merlon = bp.add_box(bm, material_index=0)
            for v in merlon:
                v.co.x = v.co.x * wall_thick + sx
                v.co.y = v.co.y * (merlon_d * 0.92) + my
                v.co.z = (v.co.z + 0.5) * merlon_h + 0.35
                
    bm.to_mesh(mesh)
    bm.free()
    bp.add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_machicolation_cornice(name, width_x=4.2, depth_y=4.2, proj=0.40, height=0.65, stone_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat:
        obj.data.materials.append(stone_mat)
        
    bm = bmesh.new()
    num_corbels = 6
    spacing_x = width_x / (num_corbels - 1)
    
    for i in range(num_corbels):
        cx = -width_x/2 + i * spacing_x
        corb = bp.add_box(bm, material_index=0)
        for v in corb:
            v.co.x = v.co.x * 0.22 + cx
            v.co.y = (v.co.y - 0.5) * (proj + 0.1) - depth_y/2 + 0.05
            v.co.z = (v.co.z + 0.5) * height
            if v.co.z < height * 0.6:
                v.co.y *= 0.6
                
    slab = bp.add_box(bm, material_index=0)
    for v in slab:
        v.co.x *= (width_x + proj * 2)
        v.co.y *= (depth_y + proj * 2)
        v.co.z = v.co.z * 0.18 + height
        
    bm.to_mesh(mesh)
    bm.free()
    bp.add_bevel_modifier(obj, width=0.014, segments=2)
    return obj

def create_pyramidal_roof(name, base_w=2.4, base_d=2.4, height=2.2, tile_mat=None, finial_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [tile_mat, finial_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    apex = bm.verts.new((0, 0, height))
    v0 = bm.verts.new((-base_w/2, -base_d/2, 0))
    v1 = bm.verts.new(( base_w/2, -base_d/2, 0))
    v2 = bm.verts.new(( base_w/2,  base_d/2, 0))
    v3 = bm.verts.new((-base_w/2,  base_d/2, 0))
    
    f0 = bm.faces.new((v0, v1, apex))
    f1 = bm.faces.new((v1, v2, apex))
    f2 = bm.faces.new((v2, v3, apex))
    f3 = bm.faces.new((v3, v0, apex))
    for f in [f0, f1, f2, f3]:
        f.material_index = 0
        
    fin = bp.add_box(bm, material_index=1)
    for v in fin:
        v.co.x *= 0.12
        v.co.y *= 0.12
        v.co.z = (v.co.z + 0.5) * 0.65 + height
        
    ball = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.10)
    for v in ball['verts']:
        v.co.z += height + 0.45
    for f in bm.faces:
        if any(v in set(ball['verts']) for v in f.verts):
            f.material_index = 1
            
    bm.to_mesh(mesh)
    bm.free()
    bp.add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_octagonal_spire(name, radius=2.0, height=7.5, slate_mat=None, gold_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [slate_mat, gold_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    segs = 8
    b_verts = []
    apex = bm.verts.new((0, 0, height))
    
    for i in range(segs):
        ang = 2 * pi * (i / segs) + pi/8
        b_verts.append(bm.verts.new((cos(ang)*radius, sin(ang)*radius, 0)))
        
    for i in range(segs):
        i_next = (i + 1) % segs
        f = bm.faces.new((b_verts[i], b_verts[i_next], apex))
        f.material_index = 0
        
    v_bar = bp.add_box(bm, material_index=1)
    for v in v_bar:
        v.co.x *= 0.10
        v.co.y *= 0.10
        v.co.z = (v.co.z + 0.5) * 1.30 + height
        
    h_bar = bp.add_box(bm, material_index=1)
    for v in h_bar:
        v.co.x *= 0.70
        v.co.y *= 0.10
        v.co.z = v.co.z * 0.10 + height + 0.85
        
    bm.to_mesh(mesh)
    bm.free()
    bp.add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

# -------------------------------------------------------------
# 1. Noble Manor (Grand multi-gabled 2.5-story mansion)
# -------------------------------------------------------------
def build_noble_manor(origin=(0, 0, 0), mats=None):
    col = "01_Building_Noble_Manor"
    ox, oy, oz = origin
    w_main, d_main = 6.0, 8.0
    w_wing, d_wing = 4.4, 4.8
    h_stone, h_1st, h_2nd = 1.8, 2.5, 2.3
    h_eaves = h_stone + h_1st + h_2nd
    
    create_pedestal("Manor_Pedestal", 14.0, 14.0, origin=origin, mats=mats, col_name=col)
    
    # 1. Stone Foundation (L-shaped)
    f_main = bp.create_stone_foundation("Manor_Fnd_Main", width=w_main, height=h_stone, depth=d_main, location=(ox - 1.2, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(f_main, col)
    
    f_wing = bp.create_stone_foundation("Manor_Fnd_Wing", width=w_wing, height=h_stone, depth=d_wing, location=(ox + w_main/2.0, oy - 1.4, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(f_wing, col)
    
    belt = bp.create_box("Manor_BeltCourse", size=(w_main + w_wing + 0.4, d_main + 0.4, 0.16), location=(ox + 0.8, oy, oz + h_stone), material=mats["M_Stone_Trim"], bevel=0.02)
    bp.link_to_collection(belt, col)
    
    # 2. Upper Floors: Plaster Infill + Timber Framing
    plaster_main = bp.create_box("Manor_Plaster_Main", size=(w_main - 0.08, d_main - 0.08, h_1st + h_2nd), location=(ox - 1.2, oy, oz + h_stone + (h_1st + h_2nd)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster_main, col)
    
    plaster_wing = bp.create_box("Manor_Plaster_Wing", size=(w_wing - 0.08, d_wing - 0.08, h_1st + h_2nd), location=(ox + w_main/2.0, oy - 1.4, oz + h_stone + (h_1st + h_2nd)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster_wing, col)
    
    # Timber posts & struts on side wing (+X facade)
    wing_post = bp.create_beam("Manor_Wing_Post", length=h_1st + h_2nd, width=0.18, depth=0.18, location=(ox + w_main/2.0 + w_wing/2.0 - 0.1, oy - 1.4, oz + h_stone), material=mats["M_Timber_Dark"])
    bp.link_to_collection(wing_post, col)
    
    wing_strut = bp.create_wall_strut("Manor_Wing_Strut", (ox + w_main/2.0 + w_wing/2.0 - 0.1, oy - 1.4 - d_wing/2 + 0.3, oz + h_stone), (ox + w_main/2.0 + w_wing/2.0 - 0.1, oy - 1.4 + 1.2, oz + h_stone + h_1st), width=0.12, depth=0.16, timber_mat=mats["M_Timber_Dark"])
    bp.link_to_collection(wing_strut, col)
    
    # Side wing glowing casement window
    w_side = bp.create_window_unit("Manor_Win_Side", width=0.95, height=1.2, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=True)
    w_side.location = (ox + w_main/2.0 + w_wing/2.0, oy - 1.4, oz + h_stone + 0.5)
    w_side.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(w_side, col)

    # Jettied 2nd floor overhang corbels
    for i in range(7):
        cx = (ox - 1.2 - w_main/2) + i * (w_main / 6.0)
        corb = bp.create_wood_corbel(f"Manor_Corbel_Front_{i}", size=0.35, timber_mat=mats["M_Timber_Dark"])
        corb.location = (cx, oy - d_main/2, oz + h_stone + h_1st)
        bp.link_to_collection(corb, col)
        
    for sx in [-w_main/2 + 0.1, w_main/2 - 0.1]:
        p = bp.create_beam("Manor_Post", length=h_1st + h_2nd, width=0.20, depth=0.20, location=(ox - 1.2 + sx, oy - d_main/2 + 0.1, oz + h_stone), material=mats["M_Timber_Dark"])
        bp.link_to_collection(p, col)
        
    # 3. Roof System (Multi-Gabled Slate)
    roof_main, pitch_h_m = bp.create_ridge_roof_y("Manor_Roof_Main", span_x=w_main, length_y=d_main, overhang_eave=0.45, overhang_gable=0.35, tile_mat=mats["M_Roof_Tiles_Slate"], timber_mat=mats["M_Timber_Dark"])
    roof_main.location = (ox - 1.2, oy, oz + h_eaves)
    bp.link_to_collection(roof_main, col)
    
    roof_wing, pitch_h_w = bp.create_ridge_roof_x("Manor_Roof_Wing", span_y=d_wing, length_x=w_wing + 0.2, overhang_eave=0.35, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Slate"], timber_mat=mats["M_Timber_Dark"])
    roof_wing.location = (ox + w_main/2.0, oy - 1.4, oz + h_eaves)
    bp.link_to_collection(roof_wing, col)
    
    gable_mf = bp.create_gable_wall("Manor_Gable_MF", width=w_main, height=pitch_h_m, location=(ox - 1.2, oy - d_main/2, oz + h_eaves), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="ornate")
    bp.link_to_collection(gable_mf, col)
    
    gable_mb = bp.create_gable_wall("Manor_Gable_MB", width=w_main, height=pitch_h_m, location=(ox - 1.2, oy + d_main/2, oz + h_eaves), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="ornate")
    gable_mb.rotation_euler = (0, 0, radians(180))
    bp.link_to_collection(gable_mb, col)
    
    gable_wf = bp.create_gable_wall("Manor_Gable_WF", width=d_wing, height=pitch_h_w, location=(ox + w_main/2.0 + w_wing/2.0, oy - 1.4, oz + h_eaves), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="ornate")
    gable_wf.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(gable_wf, col)

    # 4. Dormers
    dorm1 = bp.create_front_dormer("Manor_Dormer1", tile_mat=mats["M_Roof_Tiles_Slate"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
    dorm1.location = (ox + 0.6, oy - 1.4 - d_wing/2.0, oz + h_eaves + 0.4)
    bp.link_to_collection(dorm1, col)

    # 5. Grand Entrance Portico
    steps = bp.create_stone_steps("Manor_Steps", width=2.4, depth=1.4, height=0.45, num_steps=3, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox - 1.2, oy - d_main/2.0 - 0.7, oz)
    bp.link_to_collection(steps, col)
    
    portico = bp.create_box("Manor_Portico_Roof", size=(2.6, 1.4, 0.22), location=(ox - 1.2, oy - d_main/2.0 - 0.7, oz + 2.9), material=mats["M_Roof_Tiles_Slate"], bevel=0.03)
    bp.link_to_collection(portico, col)
    
    for sx in [-1.1, 1.1]:
        col_post = bp.create_beam("Manor_Portico_Post", length=2.45, width=0.18, depth=0.18, location=(ox - 1.2 + sx, oy - d_main/2.0 - 1.3, oz + 0.45), material=mats["M_Timber_Dark"])
        bp.link_to_collection(col_post, col)
        
    door = bp.create_door_unit("Manor_Door", width=1.4, height=2.3, style="grand", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    door.location = (ox - 1.2, oy - d_main/2.0 - 0.05, oz + 0.45)
    bp.link_to_collection(door, col)
    
    port_lantern, p_light = bp.create_lantern_prop("Manor_Portico_Lantern", iron_mat=mats["M_Iron"], glow_mat=mats["M_Lantern_Glow"], is_wall_mounted=False)
    port_lantern.location = (ox - 1.2, oy - d_main/2.0 - 0.7, oz + 2.7)
    bp.link_to_collection(port_lantern, col)
    if p_light:
        bp.link_to_collection(p_light, col)

    # 6. Windows & Flower Boxes
    w1 = bp.create_window_unit("Manor_Win_F1", width=1.05, height=1.35, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=True)
    w1.location = (ox - 1.2 - 1.6, oy - d_main/2.0 - 0.05, oz + h_stone + 0.6)
    bp.link_to_collection(w1, col)
    
    w2 = bp.create_window_unit("Manor_Win_F2", width=1.05, height=1.35, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=True)
    w2.location = (ox - 1.2 + 1.6, oy - d_main/2.0 - 0.05, oz + h_stone + 0.6)
    bp.link_to_collection(w2, col)
    
    w3 = bp.create_window_unit("Manor_Win_F3", width=1.05, height=1.35, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=True)
    w3.location = (ox - 1.2, oy - d_main/2.0 - 0.05, oz + h_stone + h_1st + 0.4)
    bp.link_to_collection(w3, col)

    # 7. Twin Tall Chimneys with Stylized Smoke
    chim1 = bp.create_chimney("Manor_Chimney_1", height=4.5, width=1.1, depth=1.1, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke_Stylized"], has_smoke=True, flue_pot=True)
    chim1.location = (ox - 1.2 - w_main/2.0 - 0.3, oy + 1.2, oz + h_stone)
    bp.link_to_collection(chim1, col)
    
    chim2 = bp.create_chimney("Manor_Chimney_2", height=3.8, width=0.95, depth=0.95, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke_Stylized"], has_smoke=True, flue_pot=True)
    chim2.location = (ox + w_main/2.0 + w_wing/2.0 + 0.3, oy - 1.4, oz + h_stone + h_1st)
    bp.link_to_collection(chim2, col)

    lamp = bp.create_street_lamp("Manor_StreetLamp", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron"], glow_mat=mats["M_Lantern_Glow"])
    lamp.location = (ox + 4.8, oy - 5.2, oz)
    bp.link_to_collection(lamp, col)
    
    statue = bp.create_knight_statue("Manor_Statue", stone_mat=mats["M_Stone_Base"])
    statue.location = (ox - 4.5, oy - 4.8, oz)
    bp.link_to_collection(statue, col)

# -------------------------------------------------------------
# 2. Guildhouse (Grand 3-bay civic hall with arched ground floor)
# -------------------------------------------------------------
def build_guildhouse(origin=(0, 0, 0), mats=None):
    col = "02_Building_Guildhouse"
    ox, oy, oz = origin
    w, d = 5.8, 7.6
    h_stone, h_2nd, h_3rd = 2.6, 2.3, 2.1
    h_eaves = h_stone + h_2nd + h_3rd
    
    create_pedestal("Guildhouse_Pedestal", 12.0, 12.0, origin=origin, mats=mats, col_name=col)
    
    # 1. Ashlar Stone Ground Floor with 3 Arches
    stone_base = bp.create_stone_foundation("Guildhouse_StoneBase", width=w, height=h_stone, depth=d, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(stone_base, col)
    
    c_door = bp.create_door_unit("Guildhouse_PortalDoor", width=1.4, height=2.2, style="arched", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    c_door.location = (ox, oy - d/2.0 - 0.05, oz)
    bp.link_to_collection(c_door, col)
    
    steps = bp.create_stone_steps("Guildhouse_Steps", width=2.0, depth=0.9, height=0.30, num_steps=2, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox, oy - d/2.0 - 0.45, oz)
    bp.link_to_collection(steps, col)
    
    for sx in [-1.8, 1.8]:
        aw = create_arched_stained_glass_window(f"Guildhouse_ArchWin_{sx}", width=0.85, height=1.6, stone_mat=mats["M_Stone_Trim"], glass_mat=mats["M_Stained_Glass"], iron_mat=mats["M_Iron"])
        aw.location = (ox + sx, oy - d/2.0 - 0.05, oz + 0.6)
        bp.link_to_collection(aw, col)
        
    cornice = bp.create_box("Guildhouse_Cornice", size=(w + 0.35, d + 0.35, 0.20), location=(ox, oy, oz + h_stone), material=mats["M_Stone_Trim"], bevel=0.03)
    bp.link_to_collection(cornice, col)
    
    # 2. Upper Floors: Timber Framing & Plaster
    plaster = bp.create_box("Guildhouse_Plaster", size=(w - 0.06, d - 0.06, h_2nd + h_3rd), location=(ox, oy, oz + h_stone + (h_2nd + h_3rd)/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)
    
    # Side Wall (+X) Timber Struts & Window
    s_post = bp.create_beam("Guildhouse_Side_Post", length=h_2nd + h_3rd, width=0.18, depth=0.18, location=(ox + w/2.0 - 0.1, oy, oz + h_stone), material=mats["M_Timber_Dark"])
    bp.link_to_collection(s_post, col)
    
    s_strut = bp.create_wall_strut("Guildhouse_Side_Strut", (ox + w/2.0 - 0.1, oy - d/2.0 + 0.5, oz + h_stone), (ox + w/2.0 - 0.1, oy + 1.2, oz + h_stone + h_2nd), width=0.12, depth=0.16, timber_mat=mats["M_Timber_Dark"])
    bp.link_to_collection(s_strut, col)
    
    s_win = bp.create_window_unit("Guildhouse_Win_Side", width=0.90, height=1.2, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=False)
    s_win.location = (ox + w/2.0, oy + 0.8, oz + h_stone + 0.5)
    s_win.rotation_euler = (0, 0, radians(-90))
    bp.link_to_collection(s_win, col)
    
    for i in range(6):
        cx = ox - w/2.0 + 0.4 + i * (w - 0.8) / 5.0
        corb = bp.create_wood_corbel(f"Guild_Corbel_{i}", size=0.32, timber_mat=mats["M_Timber_Dark"])
        corb.location = (cx, oy - d/2.0, oz + h_stone)
        bp.link_to_collection(corb, col)
        
    for fl_idx, fz in enumerate([oz + h_stone + 0.4, oz + h_stone + h_2nd + 0.3]):
        for bx in [-1.8, 0, 1.8]:
            win = bp.create_window_unit(f"Guildhouse_Win_F{fl_idx}_{bx}", width=0.90, height=1.25, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=False)
            win.location = (ox + bx, oy - d/2.0 - 0.05, fz)
            bp.link_to_collection(win, col)
            
    # 3. Steep Pitched Roof with Slate Tiles
    roof, pitch_h = bp.create_ridge_roof_y("Guildhouse_Roof", span_x=w, length_y=d, overhang_eave=0.40, overhang_gable=0.35, tile_mat=mats["M_Roof_Tiles_Slate"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_eaves)
    bp.link_to_collection(roof, col)
    
    gable_f = bp.create_gable_wall("Guildhouse_Gable_F", width=w, height=pitch_h, location=(ox, oy - d/2.0, oz + h_eaves), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="ornate")
    bp.link_to_collection(gable_f, col)
    
    gable_b = bp.create_gable_wall("Guildhouse_Gable_B", width=w, height=pitch_h, location=(ox, oy + d/2.0, oz + h_eaves), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    gable_b.rotation_euler = (0, 0, radians(180))
    bp.link_to_collection(gable_b, col)
    
    crane = bp.create_hay_crane_hoist("Guildhouse_Crane", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron"])
    crane.location = (ox, oy - d/2.0 - 0.1, oz + h_eaves + pitch_h * 0.55)
    bp.link_to_collection(crane, col)
    
    sign = bp.create_hanging_sign("Guildhouse_Sign", emblem_type="hammer", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron"], emblem_mat=mats["M_Gold"])
    sign.location = (ox + 1.6, oy - d/2.0 - 0.6, oz + h_stone + 1.2)
    bp.link_to_collection(sign, col)
    
    for bx in [-2.2, 2.2]:
        ban = bp.create_heraldic_banner(f"Guildhouse_Banner_{bx}", emblem_type="lion", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron"], cloth_mat=mats["M_Guild_Red"], gold_mat=mats["M_Gold"])
        ban.location = (ox + bx, oy - d/2.0 - 0.25, oz + h_stone + 1.8)
        bp.link_to_collection(ban, col)

# -------------------------------------------------------------
# 3. Chapel (Stone sanctuary with open belfry bellcote & bell)
# -------------------------------------------------------------
def build_chapel(origin=(0, 0, 0), mats=None):
    col = "03_Building_Chapel"
    ox, oy, oz = origin
    w, d = 4.6, 7.4
    h_wall = 4.2
    
    create_pedestal("Chapel_Pedestal", 11.0, 11.0, origin=origin, mats=mats, col_name=col)
    
    stone_nave = bp.create_box("Chapel_StoneWalls", size=(w, d, h_wall), location=(ox, oy, oz + h_wall/2.0), material=mats["M_Stone_Wall"], bevel=0.03)
    bp.link_to_collection(stone_nave, col)
    
    plinth = bp.create_box("Chapel_Plinth", size=(w + 0.35, d + 0.35, 0.70), location=(ox, oy, oz + 0.35), material=mats["M_Stone_Base"], bevel=0.04)
    bp.link_to_collection(plinth, col)
    
    # Buttress Pilasters along side
    for sy in [-d/2 + 0.3, 0, d/2 - 0.3]:
        b_butt = bp.create_box(f"Chapel_Buttress_{sy}", size=(0.42, 0.55, h_wall * 0.85), location=(ox + w/2.0 + 0.15, oy + sy, oz + (h_wall * 0.85)/2.0), material=mats["M_Stone_Trim"], bevel=0.02)
        bp.link_to_collection(b_butt, col)
        
    for wy in [-1.5, 1.5]:
        win = create_arched_stained_glass_window(f"Chapel_Win_{wy}", width=0.85, height=1.9, stone_mat=mats["M_Stone_Trim"], glass_mat=mats["M_Stained_Glass"], iron_mat=mats["M_Iron"])
        win.location = (ox + w/2.0 + 0.08, oy + wy, oz + 1.2)
        win.rotation_euler = (0, 0, radians(-90))
        bp.link_to_collection(win, col)
        
    f_win = create_arched_stained_glass_window("Chapel_Win_Front", width=0.95, height=1.9, stone_mat=mats["M_Stone_Trim"], glass_mat=mats["M_Stained_Glass"], iron_mat=mats["M_Iron"])
    f_win.location = (ox, oy - d/2.0 - 0.05, oz + 2.4)
    bp.link_to_collection(f_win, col)

    door = bp.create_door_unit("Chapel_Door", width=1.3, height=2.2, style="arched", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    door.location = (ox, oy - d/2.0 - 0.05, oz)
    bp.link_to_collection(door, col)
    
    steps = bp.create_stone_steps("Chapel_Steps", width=1.8, depth=0.8, height=0.25, num_steps=2, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox, oy - d/2.0 - 0.4, oz)
    bp.link_to_collection(steps, col)

    roof, pitch_h = bp.create_ridge_roof_y("Chapel_Roof", span_x=w, length_y=d, overhang_eave=0.42, overhang_gable=0.35, tile_mat=mats["M_Roof_Tiles_Slate"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_wall)
    bp.link_to_collection(roof, col)
    
    gable_f = bp.create_gable_wall("Chapel_Gable_F", width=w, height=pitch_h, location=(ox, oy - d/2.0, oz + h_wall), plaster_mat=mats["M_Stone_Wall"], timber_mat=mats["M_Stone_Trim"], style="plain")
    bp.link_to_collection(gable_f, col)
    
    gable_b = bp.create_gable_wall("Chapel_Gable_B", width=w, height=pitch_h, location=(ox, oy + d/2.0, oz + h_wall), plaster_mat=mats["M_Stone_Wall"], timber_mat=mats["M_Stone_Trim"], style="plain")
    gable_b.rotation_euler = (0, 0, radians(180))
    bp.link_to_collection(gable_b, col)

    # 6. Open Belfry Bellcote with Hanging Brass Bell
    bc_w, bc_d, bc_h = 1.6, 1.4, 2.2
    
    for bx in [-bc_w/2 + 0.18, bc_w/2 - 0.18]:
        for by in [oy - d/2.0 + 0.22, oy - d/2.0 + bc_d - 0.18]:
            pier = bp.create_box(f"Chapel_Bellcote_Pier_{bx}_{by}", size=(0.28, 0.28, bc_h), location=(ox + bx, by, oz + h_wall + pitch_h + bc_h/2.0 - 0.2), material=mats["M_Stone_Trim"], bevel=0.02)
            bp.link_to_collection(pier, col)
            
    bc_top = bp.create_box("Chapel_Bellcote_Top", size=(bc_w + 0.2, bc_d + 0.2, 0.22), location=(ox, oy - d/2.0 + bc_d/2.0, oz + h_wall + pitch_h + bc_h - 0.2), material=mats["M_Stone_Trim"], bevel=0.02)
    bp.link_to_collection(bc_top, col)
    
    bc_roof = create_pyramidal_roof("Chapel_Bellcote_Spire", base_w=bc_w + 0.35, base_d=bc_d + 0.35, height=1.6, tile_mat=mats["M_Roof_Tiles_Slate"], finial_mat=mats["M_Gold"])
    bc_roof.location = (ox, oy - d/2.0 + bc_d/2.0, oz + h_wall + pitch_h + bc_h - 0.1)
    bp.link_to_collection(bc_roof, col)
    
    bell = create_cylinder("Chapel_Bell", radius=0.28, height=0.45, location=(ox, oy - d/2.0 + bc_d/2.0, oz + h_wall + pitch_h + 0.8), material=mats["M_Gold"])
    bp.link_to_collection(bell, col)
    
    hedge = bp.create_boxwood_hedge("Chapel_Hedge", length=3.2, height=0.75, width=0.55, hedge_mat=mats["M_Hedge_Green"])
    hedge.location = (ox + 3.2, oy - 2.5, oz)
    bp.link_to_collection(hedge, col)
    
    bench = bp.create_wood_bench("Chapel_Bench", width=1.5, depth=0.55, height=0.65, timber_mat=mats["M_Timber_Dark"])
    bench.location = (ox + 3.2, oy - 1.2, oz)
    bp.link_to_collection(bench, col)

# -------------------------------------------------------------
# 4. Church (Cathedral with soaring bell tower spire & rose window)
# -------------------------------------------------------------
def build_church(origin=(0, 0, 0), mats=None):
    col = "04_Building_Church"
    ox, oy, oz = origin
    w_nave, d_nave = 6.4, 11.0
    h_nave = 6.8
    w_twr, d_twr = 3.8, 3.8
    h_twr_belfry = 11.5
    
    create_pedestal("Church_Pedestal", 16.0, 16.0, origin=origin, mats=mats, col_name=col)
    
    nave = bp.create_box("Church_Nave_Walls", size=(w_nave, d_nave, h_nave), location=(ox + 1.4, oy, oz + h_nave/2.0), material=mats["M_Stone_Wall"], bevel=0.03)
    bp.link_to_collection(nave, col)
    
    plinth = bp.create_box("Church_Nave_Plinth", size=(w_nave + 0.4, d_nave + 0.4, 0.85), location=(ox + 1.4, oy, oz + 0.42), material=mats["M_Stone_Base"], bevel=0.04)
    bp.link_to_collection(plinth, col)
    
    for wy in [-4.0, -1.5, 1.0, 3.5]:
        b = bp.create_box(f"Church_Buttress_{wy}", size=(0.55, 0.65, h_nave * 0.9), location=(ox + 1.4 + w_nave/2.0 + 0.25, oy + wy, oz + (h_nave * 0.9)/2.0), material=mats["M_Stone_Trim"], bevel=0.03)
        bp.link_to_collection(b, col)
        
        win = create_arched_stained_glass_window(f"Church_Win_Side_{wy}", width=0.95, height=2.4, stone_mat=mats["M_Stone_Trim"], glass_mat=mats["M_Stained_Glass"], iron_mat=mats["M_Iron"])
        win.location = (ox + 1.4 + w_nave/2.0 + 0.08, oy + wy + 1.2, oz + 2.0)
        win.rotation_euler = (0, 0, radians(-90))
        bp.link_to_collection(win, col)
        
    roof, pitch_h = bp.create_ridge_roof_y("Church_Nave_Roof", span_x=w_nave, length_y=d_nave, overhang_eave=0.45, overhang_gable=0.40, tile_mat=mats["M_Roof_Tiles_Slate"], timber_mat=mats["M_Stone_Trim"])
    roof.location = (ox + 1.4, oy, oz + h_nave)
    bp.link_to_collection(roof, col)
    
    gable_f = bp.create_gable_wall("Church_Gable_F", width=w_nave, height=pitch_h, location=(ox + 1.4, oy - d_nave/2.0, oz + h_nave), plaster_mat=mats["M_Stone_Wall"], timber_mat=mats["M_Stone_Trim"], style="plain")
    bp.link_to_collection(gable_f, col)

    portal = bp.create_door_unit("Church_WestPortal", width=1.8, height=2.7, style="arched", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    portal.location = (ox + 1.4, oy - d_nave/2.0 - 0.05, oz)
    bp.link_to_collection(portal, col)
    
    steps = bp.create_stone_steps("Church_Portal_Steps", width=2.6, depth=1.2, height=0.35, num_steps=3, stone_mat=mats["M_Stone_Base"])
    steps.location = (ox + 1.4, oy - d_nave/2.0 - 0.6, oz)
    bp.link_to_collection(steps, col)
    
    rose = create_gothic_rose_window("Church_RoseWindow", radius=1.35, depth=0.35, stone_mat=mats["M_Stone_Trim"], glass_mat=mats["M_Stained_Glass"])
    rose.location = (ox + 1.4, oy - d_nave/2.0 - 0.1, oz + h_nave + pitch_h * 0.42)
    bp.link_to_collection(rose, col)

    # 2. Soaring Bell Tower (at Front-Left of Nave)
    tx, ty = ox - w_nave/2.0 - 0.3, oy - d_nave/2.0 + d_twr/2.0
    twr_base = bp.create_box("Church_Tower_Shaft", size=(w_twr, d_twr, h_twr_belfry), location=(tx, ty, oz + h_twr_belfry/2.0), material=mats["M_Stone_Wall"], bevel=0.04)
    bp.link_to_collection(twr_base, col)
    
    twr_plinth = bp.create_box("Church_Tower_Plinth", size=(w_twr + 0.4, d_twr + 0.4, 1.2), location=(tx, ty, oz + 0.6), material=mats["M_Stone_Base"], bevel=0.04)
    bp.link_to_collection(twr_plinth, col)
    
    for sz in [4.2, 7.8, h_twr_belfry]:
        sc = bp.create_box(f"Church_Twr_Band_{sz}", size=(w_twr + 0.25, d_twr + 0.25, 0.22), location=(tx, ty, oz + sz), material=mats["M_Stone_Trim"], bevel=0.03)
        bp.link_to_collection(sc, col)
        
    for bx in [-0.8, 0.8]:
        louver = bp.create_box(f"Church_BelfryLouver_{bx}", size=(0.7, 0.2, 1.8), location=(tx + bx, ty - d_twr/2.0 - 0.05, oz + 8.8), material=mats["M_Iron"], bevel=0.02)
        bp.link_to_collection(louver, col)
        
    parapet = create_crenellated_parapet("Church_Tower_Parapet", width_x=w_twr + 0.2, depth_y=d_twr + 0.2, height=1.1, merlons_per_side=3, stone_mat=mats["M_Stone_Trim"])
    parapet.location = (tx, ty, oz + h_twr_belfry)
    bp.link_to_collection(parapet, col)
    
    spire = create_octagonal_spire("Church_SoaringSpire", radius=w_twr * 0.46, height=6.0, slate_mat=mats["M_Roof_Tiles_Slate"], gold_mat=mats["M_Gold"])
    spire.location = (tx, ty, oz + h_twr_belfry + 1.0)
    bp.link_to_collection(spire, col)

# -------------------------------------------------------------
# 5. Windmill (Tapered octagonal stone tower with 4 lattice sails)
# -------------------------------------------------------------
def build_windmill(origin=(0, 0, 0), mats=None):
    col = "05_Building_Windmill"
    ox, oy, oz = origin
    r_b, r_t = 2.6, 2.0
    h_tower = 7.8
    
    create_pedestal("Windmill_Pedestal", 14.0, 14.0, origin=origin, mats=mats, col_name=col)
    
    tower = create_octagonal_stone_tower("Windmill_StoneTower", r_base=r_b, r_top=r_t, height=h_tower, stone_mat=mats["M_Stone_Wall"])
    tower.location = (ox, oy, oz)
    bp.link_to_collection(tower, col)
    
    door = bp.create_door_unit("Windmill_GroundDoor", width=1.1, height=2.0, style="arched", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    door.location = (ox, oy - r_b - 0.05, oz)
    bp.link_to_collection(door, col)
    
    w1 = bp.create_window_unit("Windmill_Win1", width=0.75, height=0.95, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=False, has_planter=False)
    w1.location = (ox, oy - r_t * 1.15, oz + 4.2)
    bp.link_to_collection(w1, col)

    # 2. Elevated Wooden Balcony & Slender Timber Staircase
    balc = bp.create_balcony_unit("Windmill_Balcony", width=2.4, depth=1.6, timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"])
    balc.location = (ox + r_b * 0.85, oy, oz + 2.8)
    balc.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(balc, col)
    
    st_stringer = bp.create_box("Windmill_Stair_Beam", size=(0.90, 3.4, 0.14), location=(ox + r_b * 1.15, oy - 1.5, oz + 1.4), material=mats["M_Timber_Dark"], bevel=0.01)
    st_stringer.rotation_euler = (radians(-42), 0, 0)
    bp.link_to_collection(st_stringer, col)
    
    for si in range(8):
        sy = oy - 2.6 + si * (2.4 / 7.0)
        sz = oz + 0.35 + si * (2.4 / 7.0)
        step = bp.create_box(f"Windmill_Step_{si}", size=(0.90, 0.28, 0.07), location=(ox + r_b * 1.15, sy, sz), material=mats["M_Wood_Planks"], bevel=0.01)
        bp.link_to_collection(step, col)

    # 3. Rotating Timber Cap & Slender Steering Tail Pole
    cap_mesh = bpy.data.meshes.new("Windmill_Cap_mesh")
    cap_obj = bpy.data.objects.new("Windmill_Cap", cap_mesh)
    cap_obj.data.materials.append(mats["M_Roof_Tiles_Slate"])
    cap_obj.data.materials.append(mats["M_Timber_Dark"])
    
    bm = bmesh.new()
    cap_r = r_t + 0.35
    cap_h = 2.2
    c_apex = bm.verts.new((0, -0.2, cap_h))
    base_segs = 16
    cb_verts = []
    for i in range(base_segs):
        ang = 2 * pi * (i / base_segs)
        cb_verts.append(bm.verts.new((cos(ang)*cap_r, sin(ang)*cap_r, 0)))
    for i in range(base_segs):
        i_next = (i + 1) % base_segs
        f = bm.faces.new((cb_verts[i], cb_verts[i_next], c_apex))
        f.material_index = 0
        
    # Slender angled tail spar
    tail = bp.add_box(bm, material_index=1)
    for v in tail:
        v.co.x *= 0.16
        v.co.y = (v.co.y + 0.5) * 4.8
        v.co.z = v.co.z * 0.16 - (v.co.y / 4.8) * 3.8 + 0.6
        
    bm.to_mesh(cap_mesh)
    bm.free()
    bp.add_bevel_modifier(cap_obj, width=0.015, segments=2)
    cap_obj.location = (ox, oy, oz + h_tower + 0.2)
    bp.link_to_collection(cap_obj, col)

    # 4. 4 Windmill Sails (Blades)
    hub_pos = (ox, oy - cap_r - 0.35, oz + h_tower + 1.2)
    hub = create_cylinder("Windmill_Hub", radius=0.45, height=0.6, location=hub_pos, material=mats["M_Timber_Dark"])
    hub.rotation_euler = (radians(90), 0, 0)
    bp.link_to_collection(hub, col)
    
    sails_mesh = bpy.data.meshes.new("Windmill_Sails_mesh")
    sails_obj = bpy.data.objects.new("Windmill_Sails", sails_mesh)
    sails_obj.data.materials.append(mats["M_Timber_Dark"])
    sails_obj.data.materials.append(mats["M_Canvas_Sail"])
    
    bm_s = bmesh.new()
    sail_len = 5.4
    sail_w = 1.15
    
    for blade_idx in range(4):
        blade_ang = radians(blade_idx * 90.0 + 15.0)
        cos_a = cos(blade_ang)
        sin_a = sin(blade_ang)
        
        spine = bp.add_box(bm_s, material_index=0)
        for v in spine:
            v.co.x = (v.co.x + 0.5) * sail_len
            v.co.y *= 0.16
            v.co.z *= 0.16
            
            rx = v.co.x * cos_a - v.co.z * sin_a
            rz = v.co.x * sin_a + v.co.z * cos_a
            v.co.x = rx
            v.co.z = rz
            
        cloth = bp.add_box(bm_s, material_index=1)
        for v in cloth:
            v.co.x = (v.co.x + 0.5) * (sail_len * 0.82) + (sail_len * 0.16)
            v.co.y = v.co.y * 0.04 - 0.08
            v.co.z = (v.co.z + 0.5) * sail_w
            
            rx = v.co.x * cos_a - v.co.z * sin_a
            rz = v.co.x * sin_a + v.co.z * cos_a
            v.co.x = rx
            v.co.z = rz
            
        for bar_i in range(8):
            bx_dist = (sail_len * 0.18) + bar_i * (sail_len * 0.10)
            bar = bp.add_box(bm_s, material_index=0)
            for v in bar:
                v.co.x = v.co.x * 0.06 + bx_dist
                v.co.y *= 0.08
                v.co.z = (v.co.z + 0.5) * (sail_w + 0.1)
                
                rx = v.co.x * cos_a - v.co.z * sin_a
                rz = v.co.x * sin_a + v.co.z * cos_a
                v.co.x = rx
                v.co.z = rz
                
    bm_s.to_mesh(sails_mesh)
    bm_s.free()
    bp.add_bevel_modifier(sails_obj, width=0.008, segments=2)
    sails_obj.location = hub_pos
    bp.link_to_collection(sails_obj, col)

    sacks = bp.create_grain_sacks("Windmill_Sacks", num_sacks=5, straw_mat=mats["M_Straw_Hay"])
    sacks.location = (ox - 2.8, oy - 2.8, oz)
    bp.link_to_collection(sacks, col)
    
    cart = bp.create_handcart("Windmill_Cart", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron"])
    cart.location = (ox - 3.4, oy - 1.2, oz)
    bp.link_to_collection(cart, col)

# -------------------------------------------------------------
# 6. Watchtower (Defensive stone tower with machicolations & bartizans)
# -------------------------------------------------------------
def build_watchtower(origin=(0, 0, 0), mats=None):
    col = "06_Building_Watchtower"
    ox, oy, oz = origin
    w, d = 4.2, 4.2
    h_shaft = 9.2
    
    create_pedestal("Watchtower_Pedestal", 11.0, 11.0, origin=origin, mats=mats, col_name=col)
    
    plinth = bp.create_box("Watchtower_Plinth", size=(w + 0.6, d + 0.6, 2.2), location=(ox, oy, oz + 1.1), material=mats["M_Stone_Base"], bevel=0.06)
    bp.link_to_collection(plinth, col)
    
    shaft = bp.create_box("Watchtower_Shaft", size=(w, d, h_shaft), location=(ox, oy, oz + h_shaft/2.0), material=mats["M_Stone_Wall"], bevel=0.03)
    bp.link_to_collection(shaft, col)
    
    for bz in [3.8, 6.8]:
        band = bp.create_box(f"Watchtower_Belt_{bz}", size=(w + 0.22, d + 0.22, 0.20), location=(ox, oy, oz + bz), material=mats["M_Stone_Trim"], bevel=0.02)
        bp.link_to_collection(band, col)
        
    for face in ['F', 'B', 'L', 'R']:
        slit = bp.create_box(f"Watchtower_ArrowSlit_{face}", size=(0.14, 0.25, 0.95), location=(ox, oy - d/2.0 - 0.05 if face=='F' else oy, oz + 5.2), material=mats["M_Stone_Base"])
        if face == 'L': slit.location = (ox - w/2.0 - 0.05, oy, oz + 5.2)
        elif face == 'R': slit.location = (ox + w/2.0 + 0.05, oy, oz + 5.2)
        elif face == 'B': slit.location = (ox, oy + d/2.0 + 0.05, oz + 5.2)
        bp.link_to_collection(slit, col)

    machi = create_machicolation_cornice("Watchtower_Machicolations", width_x=w, depth_y=d, proj=0.45, height=0.75, stone_mat=mats["M_Stone_Trim"])
    machi.location = (ox, oy, oz + h_shaft)
    bp.link_to_collection(machi, col)

    parapet = create_crenellated_parapet("Watchtower_Battlements", width_x=w + 0.9, depth_y=d + 0.9, height=1.2, merlons_per_side=4, stone_mat=mats["M_Stone_Trim"])
    parapet.location = (ox, oy, oz + h_shaft + 0.75)
    bp.link_to_collection(parapet, col)

    for bx in [-w/2 - 0.45, w/2 + 0.45]:
        bart_turret = create_cylinder(f"Watchtower_Bartizan_{bx}", radius=0.60, height=1.8, location=(ox + bx, oy - d/2.0 - 0.45, oz + h_shaft + 0.9), material=mats["M_Stone_Trim"])
        bp.link_to_collection(bart_turret, col)
        
        bart_cone = create_pyramidal_roof(f"Watchtower_BartRoof_{bx}", base_w=1.4, base_d=1.4, height=1.6, tile_mat=mats["M_Roof_Tiles_Slate"], finial_mat=mats["M_Gold"])
        bart_cone.location = (ox + bx, oy - d/2.0 - 0.45, oz + h_shaft + 1.8)
        bp.link_to_collection(bart_cone, col)

    shelter = bp.create_box("Watchtower_LookoutHouse", size=(2.2, 2.2, 2.1), location=(ox, oy + 0.4, oz + h_shaft + 0.75 + 1.05), material=mats["M_Wood_Planks"], bevel=0.02)
    bp.link_to_collection(shelter, col)
    
    s_roof, _ = bp.create_ridge_roof_y("Watchtower_LookoutRoof", span_x=2.4, length_y=2.4, overhang_eave=0.25, overhang_gable=0.20, tile_mat=mats["M_Roof_Tiles_Slate"], timber_mat=mats["M_Timber_Dark"])
    s_roof.location = (ox, oy + 0.4, oz + h_shaft + 0.75 + 2.1)
    bp.link_to_collection(s_roof, col)

    pole = create_cylinder("Watchtower_Flagpole", radius=0.07, height=4.2, location=(ox - 1.2, oy - 1.2, oz + h_shaft + 0.75 + 2.1), material=mats["M_Timber_Dark"])
    bp.link_to_collection(pole, col)
    
    banner = bp.create_heraldic_banner("Watchtower_Banner", emblem_type="dragon", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron"], cloth_mat=mats["M_Guild_Blue"], gold_mat=mats["M_Gold"])
    banner.location = (ox - 1.2, oy - 1.2, oz + h_shaft + 0.75 + 2.6)
    bp.link_to_collection(banner, col)

# -------------------------------------------------------------
# 7. Gatehouse (Fortress portal with twin towers & portcullis)
# -------------------------------------------------------------
def build_gatehouse(origin=(0, 0, 0), mats=None):
    col = "07_Building_Gatehouse"
    ox, oy, oz = origin
    w_gate, d_gate = 3.6, 4.4
    w_twr, d_twr = 3.8, 6.0
    h_twr = 9.4
    h_arch = 4.4
    
    create_pedestal("Gatehouse_Pedestal", 16.0, 14.0, origin=origin, mats=mats, col_name=col)
    
    # 1. Twin Flanking Defensive Towers (Stepping Forward into -Y)
    for sign_x, name in [(-1, "Left"), (1, "Right")]:
        tx = ox + sign_x * (w_gate/2.0 + w_twr/2.0)
        ty = oy - 0.6  # Projects 1.2m forward of central wall
        
        t_shaft = bp.create_box(f"Gatehouse_Tower_{name}", size=(w_twr, d_twr, h_twr), location=(tx, ty, oz + h_twr/2.0), material=mats["M_Stone_Wall"], bevel=0.04)
        bp.link_to_collection(t_shaft, col)
        
        t_plinth = bp.create_box(f"Gatehouse_Plinth_{name}", size=(w_twr + 0.4, d_twr + 0.4, 1.4), location=(tx, ty, oz + 0.7), material=mats["M_Stone_Base"], bevel=0.05)
        bp.link_to_collection(t_plinth, col)
        
        t_para = create_crenellated_parapet(f"Gatehouse_Parapet_{name}", width_x=w_twr + 0.2, depth_y=d_twr + 0.2, height=1.1, merlons_per_side=3, stone_mat=mats["M_Stone_Trim"])
        t_para.location = (tx, ty, oz + h_twr)
        bp.link_to_collection(t_para, col)
        
        aslit = bp.create_box(f"Gatehouse_Slit_{name}", size=(0.14, 0.25, 1.1), location=(tx, ty - d_twr/2.0 - 0.05, oz + 5.2), material=mats["M_Stone_Base"])
        bp.link_to_collection(aslit, col)
        
        ban = bp.create_heraldic_banner(f"Gatehouse_Banner_{name}", emblem_type="lion", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron"], cloth_mat=mats["M_Guild_Red"], gold_mat=mats["M_Gold"])
        ban.location = (tx, ty - d_twr/2.0 - 0.25, oz + 5.0)
        bp.link_to_collection(ban, col)

    # 2. Central Archway Portal with Iron Portcullis Grille
    gate_portal = bp.create_castle_gate_portal("Gatehouse_Portal", width=w_gate + 0.4, height=h_arch, depth=d_gate, stone_mat=mats["M_Stone_Wall"], iron_mat=mats["M_Iron"], timber_mat=mats["M_Wood_Planks"], banner_mat=mats["M_Cloth_Red"])
    gate_portal.location = (ox, oy + 0.2, oz)
    bp.link_to_collection(gate_portal, col)
    
    # Upper Guard Chamber spanning over the archway
    upper_chamber = bp.create_box("Gatehouse_UpperChamber", size=(w_gate + 0.2, d_gate, h_twr - h_arch - 0.8), location=(ox, oy + 0.2, oz + h_arch + (h_twr - h_arch - 0.8)/2.0), material=mats["M_Stone_Wall"], bevel=0.03)
    bp.link_to_collection(upper_chamber, col)
    
    mid_para = create_crenellated_parapet("Gatehouse_MidParapet", width_x=w_gate + 0.2, depth_y=d_gate, height=1.0, merlons_per_side=3, stone_mat=mats["M_Stone_Trim"])
    mid_para.location = (ox, oy + 0.2, oz + h_twr - 0.8)
    bp.link_to_collection(mid_para, col)

# -------------------------------------------------------------
# 8. Castle Keep (Norman Great Keep with 4 corner bastions)
# -------------------------------------------------------------
def build_keep(origin=(0, 0, 0), mats=None):
    col = "08_Building_Keep"
    ox, oy, oz = origin
    w, d = 9.6, 9.6
    h_main = 11.2
    w_bast = 2.6
    
    create_pedestal("Keep_Pedestal", 16.0, 16.0, origin=origin, mats=mats, col_name=col)
    
    body = bp.create_box("Keep_MainBody", size=(w, d, h_main), location=(ox, oy, oz + h_main/2.0), material=mats["M_Stone_Wall"], bevel=0.04)
    bp.link_to_collection(body, col)
    
    plinth = bp.create_box("Keep_Plinth", size=(w + 0.8, d + 0.8, 2.0), location=(ox, oy, oz + 1.0), material=mats["M_Stone_Base"], bevel=0.08)
    bp.link_to_collection(plinth, col)
    
    # Belt courses on side (+X)
    for bz in [4.2, 7.8]:
        sc = bp.create_box(f"Keep_SideBand_{bz}", size=(w + 0.2, d + 0.2, 0.22), location=(ox, oy, oz + bz), material=mats["M_Stone_Trim"], bevel=0.02)
        bp.link_to_collection(sc, col)
        
    # 4 Corner Bastions with Steep Pyramidal Roofs (3.2m height)
    h_bast = h_main + 2.6
    for sx in [-w/2 + w_bast/4, w/2 - w_bast/4]:
        for sy in [-d/2 + w_bast/4, d/2 - w_bast/4]:
            bast = bp.create_box(f"Keep_Bastion_{sx}_{sy}", size=(w_bast, w_bast, h_bast), location=(ox + sx, oy + sy, oz + h_bast/2.0), material=mats["M_Stone_Wall"], bevel=0.04)
            bp.link_to_collection(bast, col)
            
            b_roof = create_pyramidal_roof(f"Keep_BastRoof_{sx}_{sy}", base_w=w_bast + 0.3, base_d=w_bast + 0.3, height=3.2, tile_mat=mats["M_Roof_Tiles_Slate"], finial_mat=mats["M_Gold"])
            b_roof.location = (ox + sx, oy + sy, oz + h_bast)
            bp.link_to_collection(b_roof, col)

    parapet = create_crenellated_parapet("Keep_MainBattlements", width_x=w + 0.4, depth_y=d + 0.4, height=1.3, merlons_per_side=6, stone_mat=mats["M_Stone_Trim"])
    parapet.location = (ox, oy, oz + h_main)
    bp.link_to_collection(parapet, col)

    twr_top = bp.create_box("Keep_CentralWatchtower", size=(3.6, 3.6, 3.2), location=(ox, oy, oz + h_main + 1.6), material=mats["M_Stone_Wall"], bevel=0.03)
    bp.link_to_collection(twr_top, col)
    
    twr_roof = create_pyramidal_roof("Keep_WatchtowerRoof", base_w=4.0, base_d=4.0, height=2.8, tile_mat=mats["M_Roof_Tiles_Slate"], finial_mat=mats["M_Gold"])
    twr_roof.location = (ox, oy, oz + h_main + 3.2)
    bp.link_to_collection(twr_roof, col)
    
    banner = bp.create_heraldic_banner("Keep_RoyalBanner", emblem_type="lion", timber_mat=mats["M_Timber_Dark"], iron_mat=mats["M_Iron"], cloth_mat=mats["M_Guild_Red"], gold_mat=mats["M_Gold"])
    banner.location = (ox, oy - 1.9, oz + h_main + 3.4)
    bp.link_to_collection(banner, col)

    # 5. Elevated Forebuilding Entrance
    fore_proj = bp.create_box("Keep_Forebuilding_Body", size=(2.6, 2.4, 3.2), location=(ox - 2.8, oy - d/2.0 - 1.2, oz + 1.6), material=mats["M_Stone_Wall"], bevel=0.04)
    bp.link_to_collection(fore_proj, col)
    
    f_stairs = bp.create_large_stairs("Keep_ForebuildingStairs", width=1.4, height=2.8, depth=3.2, stone_mat=mats["M_Stone_Base"])
    f_stairs.location = (ox - 2.8, oy - d/2.0 - 2.4, oz)
    bp.link_to_collection(f_stairs, col)
    
    door = bp.create_door_unit("Keep_FirstFloorDoor", width=1.4, height=2.4, style="grand", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    door.location = (ox - 2.8, oy - d/2.0 - 0.05, oz + 2.8)
    bp.link_to_collection(door, col)

    for wx in [-1.5, 1.5]:
        win = bp.create_window_unit(f"Keep_HallWin_{wx}", width=1.05, height=1.6, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=False, has_planter=False)
        win.location = (ox + wx, oy - d/2.0 - 0.05, oz + 6.4)
        bp.link_to_collection(win, col)

# -------------------------------------------------------------
# 9. Variation: Townhouse Normal (Pristine half-timbered house)
# -------------------------------------------------------------
def build_townhouse_normal(origin=(0, 0, 0), mats=None):
    col = "09_Variation_Townhouse_Normal"
    ox, oy, oz = origin
    w, d = 4.4, 5.2
    h_stone, h_1st = 1.0, 2.6
    
    create_pedestal("Townhouse_Norm_Pedestal", 9.6, 9.6, origin=origin, mats=mats, col_name=col)
    
    fnd = bp.create_stone_foundation("Townhouse_Norm_Stone", width=w, height=h_stone, depth=d, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(fnd, col)
    
    plaster = bp.create_box("Townhouse_Norm_Plaster", size=(w - 0.06, d - 0.06, h_1st), location=(ox, oy, oz + h_stone + h_1st/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)
    
    for sx in [-w/2 + 0.1, w/2 - 0.1]:
        for sy in [-d/2 + 0.1, d/2 - 0.1]:
            p = bp.create_beam("Townhouse_Norm_Post", length=h_1st, width=0.18, depth=0.18, location=(ox + sx, oy + sy, oz + h_stone), material=mats["M_Timber_Dark"])
            bp.link_to_collection(p, col)
            
    strut = bp.create_wall_strut("Townhouse_Norm_Strut", (ox + w/2, oy - d/2 + 0.3, oz + h_stone), (ox + w/2, oy + 0.5, oz + h_stone + h_1st - 0.1), width=0.12, depth=0.16, timber_mat=mats["M_Timber_Dark"])
    bp.link_to_collection(strut, col)

    roof, pitch_h = bp.create_ridge_roof_y("Townhouse_Norm_Roof", span_x=w, length_y=d, overhang_eave=0.40, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_stone + h_1st)
    bp.link_to_collection(roof, col)
    
    gable_f = bp.create_gable_wall("Townhouse_Norm_GableF", width=w, height=pitch_h, location=(ox, oy - d/2.0, oz + h_stone + h_1st), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    bp.link_to_collection(gable_f, col)
    
    dorm = bp.create_front_dormer("Townhouse_Norm_Dormer", tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"], plaster_mat=mats["M_Plaster"], glow_mat=mats["M_Window_Glow"])
    dorm.location = (ox + 0.8, oy - 1.2, oz + h_stone + h_1st + 0.35)
    bp.link_to_collection(dorm, col)
    
    door = bp.create_door_unit("Townhouse_Norm_Door", width=1.1, height=2.1, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    door.location = (ox - 0.8, oy - d/2.0 - 0.05, oz)
    bp.link_to_collection(door, col)
    
    win = bp.create_window_unit("Townhouse_Norm_Win", width=0.9, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=True)
    win.location = (ox + 1.0, oy - d/2.0 - 0.05, oz + h_stone + 0.4)
    bp.link_to_collection(win, col)
    
    chim = bp.create_chimney("Townhouse_Norm_Chimney", height=3.6, width=0.85, depth=0.85, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke_Stylized"], has_smoke=True, flue_pot=True)
    chim.location = (ox - w/2.0 - 0.25, oy + 0.8, oz + h_stone)
    bp.link_to_collection(chim, col)

# -------------------------------------------------------------
# 10. Variation: Townhouse With Stall (Integrated market counter)
# -------------------------------------------------------------
def build_townhouse_with_stall(origin=(0, 0, 0), mats=None):
    col = "10_Variation_Townhouse_WithStall"
    ox, oy, oz = origin
    w, d = 4.4, 5.2
    h_stone, h_1st = 1.0, 2.6
    
    create_pedestal("Townhouse_Stall_Pedestal", 9.6, 9.6, origin=origin, mats=mats, col_name=col)
    
    fnd = bp.create_stone_foundation("Townhouse_Stall_Stone", width=w, height=h_stone, depth=d, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(fnd, col)
    
    plaster = bp.create_box("Townhouse_Stall_Plaster", size=(w - 0.06, d - 0.06, h_1st), location=(ox, oy, oz + h_stone + h_1st/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)
    
    for sx in [-w/2 + 0.1, w/2 - 0.1]:
        for sy in [-d/2 + 0.1, d/2 - 0.1]:
            p = bp.create_beam("Townhouse_Stall_Post", length=h_1st, width=0.18, depth=0.18, location=(ox + sx, oy + sy, oz + h_stone), material=mats["M_Timber_Dark"])
            bp.link_to_collection(p, col)
            
    roof, pitch_h = bp.create_ridge_roof_y("Townhouse_Stall_Roof", span_x=w, length_y=d, overhang_eave=0.40, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy, oz + h_stone + h_1st)
    bp.link_to_collection(roof, col)
    
    gable_f = bp.create_gable_wall("Townhouse_Stall_GableF", width=w, height=pitch_h, location=(ox, oy - d/2.0, oz + h_stone + h_1st), plaster_mat=mats["M_Plaster"], timber_mat=mats["M_Timber_Dark"], style="framed")
    bp.link_to_collection(gable_f, col)
    
    door = bp.create_door_unit("Townhouse_Stall_Door", width=1.1, height=2.1, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    door.location = (ox - 0.8, oy - d/2.0 - 0.05, oz)
    bp.link_to_collection(door, col)
    
    win = bp.create_window_unit("Townhouse_Stall_Win", width=0.9, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=True)
    win.location = (ox + 1.0, oy - d/2.0 - 0.05, oz + h_stone + 0.4)
    bp.link_to_collection(win, col)
    
    chim = bp.create_chimney("Townhouse_Stall_Chimney", height=3.6, width=0.85, depth=0.85, stone_mat=mats["M_Stone_Base"], smoke_mat=mats["M_Smoke_Stylized"], has_smoke=True, flue_pot=True)
    chim.location = (ox - w/2.0 - 0.25, oy + 0.8, oz + h_stone)
    bp.link_to_collection(chim, col)
    
    awning = bp.create_market_stall_awning("Townhouse_Stall_Awning", width=3.2, depth=1.6, height=2.3, stripe_mat=mats["M_Awning_Stripe_Green"], timber_mat=mats["M_Timber_Dark"])
    awning.location = (ox + 2.2 + 0.8, oy - 0.6, oz)
    awning.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(awning, col)
    
    counter = bp.create_box("Townhouse_Stall_Counter", size=(1.2, 2.6, 0.85), location=(ox + 3.2, oy - 0.6, oz + 0.42), material=mats["M_Wood_Planks"], bevel=0.02)
    bp.link_to_collection(counter, col)
    
    crate1 = bp.create_crate("Townhouse_Stall_Crate1", size=0.65, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    crate1.location = (ox + 3.2, oy - 1.2, oz + 0.85)
    bp.link_to_collection(crate1, col)
    
    crate2 = bp.create_crate("Townhouse_Stall_Crate2", size=0.65, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    crate2.location = (ox + 3.2, oy, oz + 0.85)
    bp.link_to_collection(crate2, col)
    
    sacks = bp.create_grain_sacks("Townhouse_Stall_Sacks", num_sacks=3, straw_mat=mats["M_Straw_Hay"])
    sacks.location = (ox + 3.4, oy + 1.2, oz)
    bp.link_to_collection(sacks, col)
    
    barrel = bp.create_barrel("Townhouse_Stall_Barrel", radius=0.35, height=0.85, plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    barrel.location = (ox + 1.8, oy - 2.8, oz)
    bp.link_to_collection(barrel, col)

# -------------------------------------------------------------
# 11. Variation: Townhouse Damaged (Breached roof & broken walls)
# -------------------------------------------------------------
def build_townhouse_damaged(origin=(0, 0, 0), mats=None):
    col = "11_Variation_Townhouse_Damaged"
    ox, oy, oz = origin
    w, d = 4.4, 5.2
    h_stone, h_1st = 1.0, 2.6
    
    create_pedestal("Townhouse_Damaged_Pedestal", 9.6, 9.6, origin=origin, mats=mats, col_name=col)
    
    fnd = bp.create_stone_foundation("Townhouse_Damaged_Stone", width=w, height=h_stone, depth=d, location=(ox, oy, oz), stone_mat=mats["M_Stone_Base"], has_quoins=True)
    bp.link_to_collection(fnd, col)
    
    plaster = bp.create_box("Townhouse_Damaged_Plaster", size=(w - 0.06, d - 0.06, h_1st), location=(ox, oy, oz + h_stone + h_1st/2.0), material=mats["M_Plaster"])
    bp.link_to_collection(plaster, col)
    
    # Broken corner post
    p1 = bp.create_beam("Townhouse_Damaged_Post1", length=h_1st * 0.7, width=0.18, depth=0.18, location=(ox - w/2 + 0.1, oy - d/2 + 0.1, oz + h_stone), material=mats["M_Timber_Dark"])
    bp.link_to_collection(p1, col)
    
    # Front door
    door = bp.create_door_unit("Townhouse_Damaged_Door", width=1.1, height=2.1, style="single", timber_mat=mats["M_Timber_Dark"], plank_mat=mats["M_Wood_Planks"], iron_mat=mats["M_Iron"])
    door.location = (ox - 0.8, oy - d/2.0 - 0.05, oz)
    bp.link_to_collection(door, col)
    
    # Broken window
    win = bp.create_window_unit("Townhouse_Damaged_Win", width=0.9, height=1.15, timber_mat=mats["M_Timber_Dark"], glow_mat=mats["M_Window_Glow"], plank_mat=mats["M_Wood_Planks"], foliage_mat=mats["M_Foliage_Hedge"], flower_mat=mats["M_Flower_Petals"], has_shutters=True, has_planter=False)
    win.location = (ox + 1.0, oy - d/2.0 - 0.05, oz + h_stone + 0.4)
    bp.link_to_collection(win, col)

    roof, pitch_h = bp.create_ridge_roof_y("Townhouse_Damaged_Roof", span_x=w, length_y=d * 0.65, overhang_eave=0.40, overhang_gable=0.30, tile_mat=mats["M_Roof_Tiles_Red"], timber_mat=mats["M_Timber_Dark"])
    roof.location = (ox, oy + 0.8, oz + h_stone + h_1st)
    bp.link_to_collection(roof, col)
    
    for ri in range(4):
        rx = -w/2.0 + 0.6 + ri * (w - 1.2) / 3.0
        rf_beam = bp.create_beam(f"Townhouse_Damaged_Rafter_{ri}", length=2.2, width=0.12, depth=0.14, location=(ox + rx, oy - 1.2, oz + h_stone + h_1st + 0.4), material=mats["M_Timber_Dark"])
        rf_beam.rotation_euler = (radians(25), 0, radians(15 if ri%2==0 else -15))
        bp.link_to_collection(rf_beam, col)
        
    chim = bp.create_chimney("Townhouse_Damaged_Chimney", height=2.4, width=0.85, depth=0.85, stone_mat=mats["M_Stone_Base"], smoke_mat=None, has_smoke=False, flue_pot=False)
    chim.location = (ox - w/2.0 - 0.25, oy + 0.8, oz + h_stone)
    chim.rotation_euler = (0, radians(12), 0)
    bp.link_to_collection(chim, col)
    
    for bi in range(6):
        bx = ox + (bi % 3) * 0.8 - 0.8
        by = oy - 2.8 + (bi // 3) * 0.7
        rubble = bp.create_box(f"Townhouse_Rubble_{bi}", size=(0.35, 0.45, 0.22), location=(bx, by, oz + 0.11), material=mats["M_Stone_Trim"], bevel=0.03)
        rubble.rotation_euler = (radians(15), radians(-20), radians(35))
        bp.link_to_collection(rubble, col)

# -------------------------------------------------------------
# 12. Variation: Townhouse Ruin (Overgrown collapsed ancient ruin)
# -------------------------------------------------------------
def build_townhouse_ruin(origin=(0, 0, 0), mats=None):
    col = "12_Variation_Townhouse_Ruin"
    ox, oy, oz = origin
    w, d = 4.4, 5.2
    
    create_pedestal("Townhouse_Ruin_Pedestal", 9.6, 9.6, origin=origin, mats=mats, col_name=col)
    
    w_left = bp.create_ruin_wall("Townhouse_Ruin_WallL", width=d, height=2.2, stone_mat=mats["M_Stone_Wall"], foliage_mat=mats["M_Hedge_Green"])
    w_left.location = (ox - w/2.0 + 0.2, oy, oz)
    w_left.rotation_euler = (0, 0, radians(90))
    bp.link_to_collection(w_left, col)
    
    w_back = bp.create_ruin_wall("Townhouse_Ruin_WallB", width=w, height=1.8, stone_mat=mats["M_Stone_Wall"], foliage_mat=mats["M_Hedge_Green"])
    w_back.location = (ox, oy + d/2.0 - 0.2, oz)
    bp.link_to_collection(w_back, col)
    
    w_front = bp.create_ruin_wall("Townhouse_Ruin_WallF", width=w * 0.5, height=1.1, stone_mat=mats["M_Stone_Wall"], foliage_mat=mats["M_Hedge_Green"])
    w_front.location = (ox - 1.0, oy - d/2.0 + 0.2, oz)
    bp.link_to_collection(w_front, col)
    
    for ti in range(4):
        bx = ox + (ti - 1.5) * 0.7
        rot_beam = bp.create_beam(f"Townhouse_Ruin_Beam_{ti}", length=3.4, width=0.16, depth=0.18, location=(bx, oy - 0.5, oz + 0.2 + ti * 0.15), material=mats["M_Timber_Dark"])
        rot_beam.rotation_euler = (radians(12 * (ti+1)), radians(-15), radians(30 * ti))
        bp.link_to_collection(rot_beam, col)
        
    hedge1 = bp.create_boxwood_hedge("Townhouse_Ruin_Hedge1", length=2.2, height=1.1, width=0.8, hedge_mat=mats["M_Hedge_Green"])
    hedge1.location = (ox + 1.2, oy - 1.2, oz)
    bp.link_to_collection(hedge1, col)
    
    hedge2 = bp.create_boxwood_hedge("Townhouse_Ruin_Hedge2", length=1.6, height=0.85, width=0.6, hedge_mat=mats["M_Hedge_Green"])
    hedge2.location = (ox - 1.4, oy + 1.6, oz)
    bp.link_to_collection(hedge2, col)
    
    boulder1 = bp.create_rock_boulder("Townhouse_Ruin_Rock1", size=(1.3, 0.9, 0.7), stone_mat=mats["M_Stone_Wall"])
    boulder1.location = (ox + 1.8, oy + 0.6, oz)
    bp.link_to_collection(boulder1, col)
    
    boulder2 = bp.create_rock_boulder("Townhouse_Ruin_Rock2", size=(0.9, 0.7, 0.5), stone_mat=mats["M_Stone_Wall"])
    boulder2.location = (ox - 0.8, oy - 2.4, oz)
    bp.link_to_collection(boulder2, col)

# -------------------------------------------------------------
# Cameras and Lights Setup
# -------------------------------------------------------------
def setup_monuments_cameras_and_lights(coords):
    col = "00_Lighting_and_Cameras"
    
    # Master Camera: Frame all 12 monuments completely with ample margins
    cx, cy, cz = 36.0, 24.0, 4.0
    cam_data = bpy.data.cameras.new("Cam_Monuments_Master")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 110.0
    cam_obj = bpy.data.objects.new("Cam_Monuments_Master", cam_data)
    dist = 75.0
    cam_obj.location = (cx + dist, cy - dist, cz + dist)
    cam_obj.rotation_euler = (radians(54.736), 0, radians(45.0))
    bp.link_to_collection(cam_obj, col)
    bpy.context.scene.camera = cam_obj
    
    camera_scales = {
        "Manor": (19.0, 4.5),
        "Guildhouse": (17.5, 5.0),
        "Chapel": (16.0, 4.2),
        "Church": (26.0, 8.5),
        "Windmill": (24.0, 6.8),
        "Watchtower": (18.0, 5.5),
        "Gatehouse": (19.0, 4.8),
        "Keep": (22.0, 6.5),
        "Townhouse_Normal": (15.0, 3.5),
        "Townhouse_WithStall": (15.0, 3.5),
        "Townhouse_Damaged": (15.0, 3.5),
        "Townhouse_Ruin": (15.0, 3.5),
    }
    
    for b_name, (bx, by, bz) in coords.items():
        scale, z_focus = camera_scales.get(b_name, (16.0, 4.0))
        b_cam_data = bpy.data.cameras.new(f"Cam_{b_name}")
        b_cam_data.type = 'ORTHO'
        b_cam_data.ortho_scale = scale
        b_cam_obj = bpy.data.objects.new(f"Cam_{b_name}", b_cam_data)
        i_dist = 28.0
        b_cam_obj.location = (bx + i_dist, by - i_dist, bz + z_focus + i_dist)
        b_cam_obj.rotation_euler = (radians(54.736), 0, radians(45.0))
        bp.link_to_collection(b_cam_obj, col)

    sun_data = bpy.data.lights.new(name="Sun_KeyLight", type='SUN')
    sun_data.energy = 5.5
    sun_data.color = (1.0, 0.94, 0.88)
    sun_data.angle = radians(6.0)
    sun_obj = bpy.data.objects.new("Sun_KeyLight", sun_data)
    sun_obj.rotation_euler = (radians(50.0), radians(15.0), radians(35.0))
    bp.link_to_collection(sun_obj, col)

    sky_data = bpy.data.lights.new(name="Sun_SkyFill", type='SUN')
    sky_data.energy = 2.2
    sky_data.color = (0.60, 0.75, 0.95)
    sky_obj = bpy.data.objects.new("Sun_SkyFill", sky_data)
    sky_obj.rotation_euler = (radians(130.0), radians(15.0), radians(-145.0))
    bp.link_to_collection(sky_obj, col)

# -------------------------------------------------------------
# Main Assembly Execution
# -------------------------------------------------------------
def build_all_monuments():
    print("Generating Complete Emberglass Monuments & Building Variations...")
    clear_scene()
    
    scene = bpy.context.scene
    setup_world(scene)
    mats = materials.setup_all_materials()
    
    sx, sy = 24.0, 24.0
    
    monuments_coords = {
        "Townhouse_Normal":    (0 * sx, 0 * sy, 0),
        "Townhouse_WithStall": (1 * sx, 0 * sy, 0),
        "Townhouse_Damaged":   (2 * sx, 0 * sy, 0),
        "Townhouse_Ruin":      (3 * sx, 0 * sy, 0),
        
        "Manor":               (0 * sx, 1 * sy, 0),
        "Guildhouse":          (1 * sx, 1 * sy, 0),
        "Chapel":              (2 * sx, 1 * sy, 0),
        "Church":              (3 * sx, 1 * sy, 0),
        
        "Windmill":            (0 * sx, 2 * sy, 0),
        "Watchtower":          (1 * sx, 2 * sy, 0),
        "Gatehouse":           (2 * sx, 2 * sy, 0),
        "Keep":                (3 * sx, 2 * sy, 0),
    }

    print("1/12: Assembling Townhouse Normal...")
    build_townhouse_normal(origin=monuments_coords["Townhouse_Normal"], mats=mats)
    
    print("2/12: Assembling Townhouse With Stall...")
    build_townhouse_with_stall(origin=monuments_coords["Townhouse_WithStall"], mats=mats)
    
    print("3/12: Assembling Townhouse Damaged...")
    build_townhouse_damaged(origin=monuments_coords["Townhouse_Damaged"], mats=mats)
    
    print("4/12: Assembling Townhouse Ruin...")
    build_townhouse_ruin(origin=monuments_coords["Townhouse_Ruin"], mats=mats)
    
    print("5/12: Assembling Noble Manor...")
    build_noble_manor(origin=monuments_coords["Manor"], mats=mats)
    
    print("6/12: Assembling Guildhouse...")
    build_guildhouse(origin=monuments_coords["Guildhouse"], mats=mats)
    
    print("7/12: Assembling Chapel...")
    build_chapel(origin=monuments_coords["Chapel"], mats=mats)
    
    print("8/12: Assembling Church (Cathedral)...")
    build_church(origin=monuments_coords["Church"], mats=mats)
    
    print("9/12: Assembling Windmill...")
    build_windmill(origin=monuments_coords["Windmill"], mats=mats)
    
    print("10/12: Assembling Watchtower...")
    build_watchtower(origin=monuments_coords["Watchtower"], mats=mats)
    
    print("11/12: Assembling Gatehouse...")
    build_gatehouse(origin=monuments_coords["Gatehouse"], mats=mats)
    
    print("12/12: Assembling Castle Keep...")
    build_keep(origin=monuments_coords["Keep"], mats=mats)

    print("Setting up Cameras & Lights...")
    setup_monuments_cameras_and_lights(monuments_coords)

    output_path = "d:/assests/emberglass_monuments.blend"
    bpy.ops.wm.save_as_mainfile(filepath=output_path)
    print(f"Emberglass Monuments Master file saved to: {output_path}")

if __name__ == "__main__":
    build_all_monuments()
