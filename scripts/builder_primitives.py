"""
Emberglass 3D Component Builder Library for Blender 4.2 LTS
Full modular primitives for medieval stylized fantasy buildings.
All primary facades, windows, doors, signs, and props face outward (-Y by default)
with precise geometric alignment, bevels, and material slot assignments.
"""

import bpy
import bmesh
from math import radians, cos, sin, tan, pi
from mathutils import Vector, Matrix, Euler

def add_bevel_modifier(obj, width=0.015, segments=2):
    mod = obj.modifiers.new(name="Bevel", type='BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    mod.angle_limit = radians(35)
    return mod

def link_to_collection(obj, col_name):
    if col_name not in bpy.data.collections:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)
    else:
        col = bpy.data.collections[col_name]
    
    if obj.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(obj)
    if obj.name not in col.objects:
        col.objects.link(obj)
    return col

def add_box(bm, material_index=0):
    """Creates a 1x1x1 cube centered at (0,0,0) and assigns material_index."""
    res = bmesh.ops.create_cube(bm, size=1.0)
    vset = set(res['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = material_index
    return res['verts']

def add_diagonal_box(bm, p1, p2, width=0.14, depth=0.18, material_index=0):
    """Creates an oriented rectangular beam running between 3D points p1 and p2."""
    p1 = Vector(p1)
    p2 = Vector(p2)
    diff = p2 - p1
    length = diff.length
    if length < 0.001:
        return []
    mid = (p1 + p2) * 0.5
    dir_v = diff.normalized()
    z_axis = Vector((0, 0, 1))
    if abs(dir_v.dot(z_axis)) > 0.9999:
        rot = Matrix.Identity(3) if dir_v.z > 0 else Matrix.Scale(-1, 3, Vector((0, 0, 1)))
    else:
        rot = z_axis.rotation_difference(dir_v).to_matrix()
    
    verts = add_box(bm, material_index=material_index)
    for v in verts:
        local = Vector((v.co.x * width, v.co.y * depth, v.co.z * length))
        v.co = mid + rot @ local
    return verts

# -------------------------------------------------------------
# Basic Geometric Helpers
# -------------------------------------------------------------

def create_box(name, size=(1.0, 1.0, 1.0), location=(0,0,0), rotation=(0,0,0), material=None, bevel=0.0):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    bm = bmesh.new()
    verts = add_box(bm, material_index=0)
    for v in verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    bm.to_mesh(mesh)
    bm.free()
    
    obj.location = location
    obj.rotation_euler = rotation
    if material:
        obj.data.materials.append(material)
    if bevel > 0:
        add_bevel_modifier(obj, width=bevel, segments=2)
    return obj

def create_beam(name, length=2.0, width=0.18, depth=0.18, location=(0,0,0), rotation=(0,0,0), material=None, bevel=0.014):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    bm = bmesh.new()
    verts = add_box(bm, material_index=0)
    for v in verts:
        v.co.x *= width
        v.co.y *= depth
        v.co.z = (v.co.z + 0.5) * length
    bm.to_mesh(mesh)
    bm.free()
    
    obj.location = location
    obj.rotation_euler = rotation
    if material:
        obj.data.materials.append(material)
    if bevel > 0:
        add_bevel_modifier(obj, width=bevel, segments=2)
    return obj

def create_wood_corbel(name, size=0.35, timber_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat:
        obj.data.materials.append(timber_mat)
    bm = bmesh.new()
    verts = add_box(bm, material_index=0)
    for v in verts:
        v.co.x *= 0.14
        v.co.y = (v.co.y + 0.5) * size
        v.co.z = (v.co.z + 0.5) * size
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.02, segments=2)
    return obj

# -------------------------------------------------------------
# Walls & Foundation
# -------------------------------------------------------------

def create_stone_foundation(name, width=2.0, height=2.4, depth=0.25, location=(0,0,0), stone_mat=None, has_quoins=True):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    bm = bmesh.new()
    verts = add_box(bm, material_index=0)
    for v in verts:
        v.co.x *= width
        v.co.y *= depth
        v.co.z = (v.co.z + 0.5) * height
    
    plinth = add_box(bm, material_index=0)
    for v in plinth:
        v.co.x *= (width + 0.12)
        v.co.y *= (depth + 0.12)
        v.co.z = (v.co.z + 0.5) * 0.35
        
    ledge = add_box(bm, material_index=0)
    for v in ledge:
        v.co.x *= (width + 0.10)
        v.co.y *= (depth + 0.10)
        v.co.z = (v.co.z + 0.5) * 0.15 + (height - 0.15)
        
    if has_quoins and height >= 0.7:
        num_layers = int(height / 0.28)
        layer_h = height / max(1, num_layers)
        qw_long = 0.38
        qw_short = 0.24
        for lay in range(num_layers):
            z_c = (lay + 0.5) * layer_h
            is_alt = (lay % 2 == 1)
            lx = qw_long if not is_alt else qw_short
            ly = qw_short if not is_alt else qw_long
            for sx in [-1, 1]:
                for sy in [-1, 1]:
                    q_verts = add_box(bm, material_index=0)
                    px = sx * (width/2.0 - lx/2.0 + 0.02 * sx)
                    py = sy * (depth/2.0 - ly/2.0 + 0.02 * sy)
                    for v in q_verts:
                        v.co.x = v.co.x * lx + px
                        v.co.y = v.co.y * ly + py
                        v.co.z = v.co.z * (layer_h * 0.90) + z_c

    bm.to_mesh(mesh)
    bm.free()
    
    obj.location = location
    if stone_mat:
        obj.data.materials.append(stone_mat)
    add_bevel_modifier(obj, width=0.018, segments=2)
    return obj

def create_timber_framed_wall(name, width=2.0, height=2.4, depth=0.20, style="straight", location=(0,0,0), plaster_mat=None, timber_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if plaster_mat:
        obj.data.materials.append(plaster_mat)
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    verts = add_box(bm, material_index=0)
    for v in verts:
        v.co.x *= (width - 0.02)
        v.co.y *= (depth - 0.04)
        v.co.z = (v.co.z + 0.5) * height
        
    beam_w = 0.16
    beam_d = depth + 0.02
    
    def add_timber(cx, cy, cz, sx, sy, sz):
        t_verts = add_box(bm, material_index=1)
        for v in t_verts:
            v.co.x = v.co.x * sx + cx
            v.co.y = v.co.y * sy + cy
            v.co.z = v.co.z * sz + cz
            
    # Vertical posts
    add_timber(-width/2 + beam_w/2, 0, height/2, beam_w, beam_d, height)
    add_timber( width/2 - beam_w/2, 0, height/2, beam_w, beam_d, height)
    # Horizontal sills and girts
    add_timber(0, 0, beam_w/2, width - beam_w*2, beam_d, beam_w)
    add_timber(0, 0, height - beam_w/2, width - beam_w*2, beam_d, beam_w)
    add_timber(0, 0, height/2, width - beam_w*2, beam_d, beam_w)

    left_x = -width/2 + beam_w
    right_x = width/2 - beam_w
    mid_z = height / 2.0
    bot_z = beam_w
    top_z = height - beam_w
    
    if style in ("cross", "x_brace"):
        add_diagonal_box(bm, Vector((left_x, 0, bot_z)), Vector((right_x, 0, mid_z)), width=0.12, depth=beam_d, material_index=1)
        add_diagonal_box(bm, Vector((left_x, 0, mid_z)), Vector((right_x, 0, bot_z)), width=0.12, depth=beam_d, material_index=1)
        add_diagonal_box(bm, Vector((left_x, 0, mid_z)), Vector((right_x, 0, top_z)), width=0.12, depth=beam_d, material_index=1)
        add_diagonal_box(bm, Vector((left_x, 0, top_z)), Vector((right_x, 0, mid_z)), width=0.12, depth=beam_d, material_index=1)
    elif style == "brace_left":
        add_diagonal_box(bm, Vector((left_x, 0, bot_z)), Vector((right_x, 0, mid_z)), width=0.13, depth=beam_d, material_index=1)
        add_diagonal_box(bm, Vector((left_x, 0, mid_z)), Vector((right_x, 0, top_z)), width=0.13, depth=beam_d, material_index=1)
    elif style == "brace_right":
        add_diagonal_box(bm, Vector((right_x, 0, bot_z)), Vector((left_x, 0, mid_z)), width=0.13, depth=beam_d, material_index=1)
        add_diagonal_box(bm, Vector((right_x, 0, mid_z)), Vector((left_x, 0, top_z)), width=0.13, depth=beam_d, material_index=1)
    elif style == "chevron":
        add_diagonal_box(bm, Vector((left_x, 0, bot_z)), Vector((0, 0, top_z)), width=0.13, depth=beam_d, material_index=1)
        add_diagonal_box(bm, Vector((right_x, 0, bot_z)), Vector((0, 0, top_z)), width=0.13, depth=beam_d, material_index=1)
    
    bm.to_mesh(mesh)
    bm.free()
    
    obj.location = location
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

def create_gable_wall(name, width=4.0, height=2.4, depth=0.20, location=(0,0,0), plaster_mat=None, timber_mat=None, style="framed"):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if plaster_mat:
        obj.data.materials.append(plaster_mat)
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    half_w = width / 2.0
    half_d = (depth - 0.04) / 2.0
    
    v0 = bm.verts.new((-half_w, -half_d, 0))
    v1 = bm.verts.new(( half_w, -half_d, 0))
    v2 = bm.verts.new(( 0,      -half_d, height))
    f_front = bm.faces.new((v0, v1, v2))
    
    v3 = bm.verts.new((-half_w,  half_d, 0))
    v4 = bm.verts.new(( half_w,  half_d, 0))
    v5 = bm.verts.new(( 0,       half_d, height))
    f_back = bm.faces.new((v5, v4, v3))
    
    bm.faces.new((v0, v3, v4, v1))
    bm.faces.new((v0, v2, v5, v3))
    bm.faces.new((v1, v4, v5, v2))
    for f in bm.faces:
        f.material_index = 0
        
    beam_w = 0.16
    beam_d = depth + 0.03
    
    # Tie beam at base
    tie = add_box(bm, material_index=1)
    for v in tie:
        v.co.x *= width
        v.co.y *= beam_d
        v.co.z = (v.co.z + 0.5) * beam_w

    # King post in center
    kp = add_box(bm, material_index=1)
    for v in kp:
        v.co.x *= beam_w
        v.co.y *= beam_d
        v.co.z = (v.co.z + 0.5) * height
        
    # Diagonal principal rafters along both triangular slopes
    p_left = Vector((-half_w + 0.08, 0, 0.05))
    p_right = Vector((half_w - 0.08, 0, 0.05))
    p_apex = Vector((0, 0, height - 0.05))
    add_diagonal_box(bm, p_left, p_apex, width=beam_w, depth=beam_d, material_index=1)
    add_diagonal_box(bm, p_right, p_apex, width=beam_w, depth=beam_d, material_index=1)
    
    # Struts framing king post
    if style in ("framed", "cross"):
        p_mid_l = Vector((-half_w * 0.5, 0, 0.05))
        p_mid_r = Vector(( half_w * 0.5, 0, 0.05))
        p_kp_mid = Vector((0, 0, height * 0.55))
        add_diagonal_box(bm, p_mid_l, p_kp_mid, width=0.12, depth=beam_d, material_index=1)
        add_diagonal_box(bm, p_mid_r, p_kp_mid, width=0.12, depth=beam_d, material_index=1)
        
    bm.to_mesh(mesh)
    bm.free()
    
    obj.location = location
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

# -------------------------------------------------------------
# Roof Systems: Both X-Ridge and Y-Ridge
# -------------------------------------------------------------

def create_ridge_roof_x(name, span_y=4.0, length_x=4.8, height=None, overhang_eave=0.42, overhang_gable=0.30, tile_mat=None, timber_mat=None):
    """
    Ridge runs along X.
    Roof slopes down towards -Y (front) and +Y (back).
    Gables are at -X and +X.
    Apex is at z=pitch_height, where pitch_height = (span_y/2) * tan(48 deg).
    Eave overhang dips down below z=0 by overhang_eave * tan(48 deg).
    Bargeboards cap the gable verges at -total_tile_len/2 and +total_tile_len/2.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if tile_mat:
        obj.data.materials.append(tile_mat)
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    
    half_span = span_y / 2.0
    slope_angle = radians(48.0)
    pitch_height = half_span * tan(slope_angle)
    total_half_span = half_span + overhang_eave
    total_tile_len = length_x + overhang_gable * 2.0
    slope_len = total_half_span / cos(slope_angle)
    
    num_rows = 7
    row_len = slope_len / num_rows
    barge_thick = 0.09
    barge_w = 0.16
    
    for sign_y in [-1, 1]:
        dir_y = sign_y * cos(slope_angle)
        dir_z = -sin(slope_angle)
        norm_y = sign_y * sin(slope_angle)
        norm_z = cos(slope_angle)
        
        # 1. Decking
        verts = add_box(bm, material_index=1)
        for v in verts:
            lx = v.co.x * (total_tile_len - barge_thick * 2.0)
            ly = (v.co.y + 0.5) * slope_len
            lz = v.co.z * 0.08
            v.co.x = lx
            v.co.y = ly * dir_y + lz * norm_y
            v.co.z = pitch_height + ly * dir_z + lz * norm_z
            
        # 2. Stepped Overlapping Tile Courses
        tile_thick = 0.055
        for r in range(num_rows):
            verts = add_box(bm, material_index=0)
            y_start = r * row_len
            y_span = row_len * 1.32
            norm_offset = 0.05 + (r * 0.015)
            
            for v in verts:
                lx = v.co.x * (total_tile_len - barge_thick * 0.5)
                ly = y_start + (v.co.y + 0.5) * y_span
                lz = norm_offset + (v.co.z + 0.5) * tile_thick
                v.co.x = lx
                v.co.y = ly * dir_y + lz * norm_y
                v.co.z = pitch_height + ly * dir_z + lz * norm_z

        # 3. Bargeboards at outer gable edges
        for sign_x in [-1, 1]:
            end_x = sign_x * (total_tile_len/2.0 - barge_thick/2.0)
            verts = add_box(bm, material_index=1)
            for v in verts:
                lx = v.co.x * barge_thick + end_x
                ly = (v.co.y + 0.5) * (slope_len + 0.02)
                lz = v.co.z * barge_w + 0.05
                v.co.x = lx
                v.co.y = ly * dir_y + lz * norm_y
                v.co.z = pitch_height + ly * dir_z + lz * norm_z

        # 4. Gable Rafters / Lookouts along wall edge (at -length_x/2 and +length_x/2)
        if overhang_gable > 0.15:
            for sign_x in [-1, 1]:
                wall_x = sign_x * (length_x/2.0 - 0.05)
                verts = add_box(bm, material_index=1)
                for v in verts:
                    lx = v.co.x * 0.10 + wall_x
                    ly = (v.co.y + 0.5) * slope_len
                    lz = v.co.z * 0.12 - 0.06
                    v.co.x = lx
                    v.co.y = ly * dir_y + lz * norm_y
                    v.co.z = pitch_height + ly * dir_z + lz * norm_z
                
    # 5. Ridge Capping Tiles along X
    num_caps = int(total_tile_len / 0.35) + 1
    cap_w = total_tile_len / num_caps
    for c in range(num_caps):
        cx = -total_tile_len/2.0 + (c + 0.5) * cap_w
        verts = add_box(bm, material_index=0)
        for v in verts:
            v.co.x = v.co.x * (cap_w * 1.15) + cx
            v.co.y *= 0.44
            v.co.z = v.co.z * 0.12 + pitch_height + 0.09
            
    # 6. Apex Finials at outer gable edges
    for sign_x in [-1, 1]:
        end_x = sign_x * (total_tile_len/2.0 - barge_thick/2.0)
        verts = add_box(bm, material_index=1)
        for v in verts:
            v.co.x = v.co.x * 0.10 + end_x
            v.co.y *= 0.14
            v.co.z = (v.co.z + 0.5) * 0.55 + pitch_height - 0.05

    bm.to_mesh(mesh)
    bm.free()
    
    add_bevel_modifier(obj, width=0.014, segments=2)
    return obj, pitch_height

def create_ridge_roof_y(name, span_x=4.0, length_y=4.8, height=None, overhang_eave=0.42, overhang_gable=0.30, tile_mat=None, timber_mat=None):
    """
    Ridge runs along Y.
    Roof slopes down towards -X (left) and +X (right, facing lower-right towards camera).
    Gables are at -Y (facing lower-left towards camera) and +Y.
    Apex is at z=pitch_height, where pitch_height = (span_x/2) * tan(48 deg).
    Eave overhang dips down below z=0 by overhang_eave * tan(48 deg).
    Bargeboards cap the gable verges at -total_tile_len/2 and +total_tile_len/2.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if tile_mat:
        obj.data.materials.append(tile_mat)
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    
    half_span = span_x / 2.0
    slope_angle = radians(48.0)
    pitch_height = half_span * tan(slope_angle)
    total_half_span = half_span + overhang_eave
    total_tile_len = length_y + overhang_gable * 2.0
    slope_len = total_half_span / cos(slope_angle)
    
    num_rows = 7
    row_len = slope_len / num_rows
    barge_thick = 0.09
    barge_w = 0.16
    
    for sign_x in [-1, 1]:
        dir_x = sign_x * cos(slope_angle)
        dir_z = -sin(slope_angle)
        norm_x = sign_x * sin(slope_angle)
        norm_z = cos(slope_angle)
        
        # 1. Decking
        verts = add_box(bm, material_index=1)
        for v in verts:
            ly = v.co.y * (total_tile_len - barge_thick * 2.0)
            lx = (v.co.x + 0.5) * slope_len
            lz = v.co.z * 0.08
            v.co.x = lx * dir_x + lz * norm_x
            v.co.y = ly
            v.co.z = pitch_height + lx * dir_z + lz * norm_z
            
        # 2. Stepped Overlapping Tile Courses
        tile_thick = 0.055
        for r in range(num_rows):
            verts = add_box(bm, material_index=0)
            x_start = r * row_len
            x_span = row_len * 1.32
            norm_offset = 0.05 + (r * 0.015)
            
            for v in verts:
                ly = v.co.y * (total_tile_len - barge_thick * 0.5)
                lx = x_start + (v.co.x + 0.5) * x_span
                lz = norm_offset + (v.co.z + 0.5) * tile_thick
                v.co.x = lx * dir_x + lz * norm_x
                v.co.y = ly
                v.co.z = pitch_height + lx * dir_z + lz * norm_z

        # 3. Bargeboards at outer gable edges
        for sign_y in [-1, 1]:
            end_y = sign_y * (total_tile_len/2.0 - barge_thick/2.0)
            verts = add_box(bm, material_index=1)
            for v in verts:
                ly = v.co.y * barge_thick + end_y
                lx = (v.co.x + 0.5) * (slope_len + 0.02)
                lz = v.co.z * barge_w + 0.05
                v.co.x = lx * dir_x + lz * norm_x
                v.co.y = ly
                v.co.z = pitch_height + lx * dir_z + lz * norm_z

        # 4. Gable Rafters / Lookouts along wall edge (at -length_y/2 and +length_y/2)
        if overhang_gable > 0.15:
            for sign_y in [-1, 1]:
                wall_y = sign_y * (length_y/2.0 - 0.05)
                verts = add_box(bm, material_index=1)
                for v in verts:
                    ly = v.co.y * 0.10 + wall_y
                    lx = (v.co.x + 0.5) * slope_len
                    lz = v.co.z * 0.12 - 0.06
                    v.co.x = lx * dir_x + lz * norm_x
                    v.co.y = ly
                    v.co.z = pitch_height + lx * dir_z + lz * norm_z
                
    # 5. Ridge Capping Tiles along Y
    num_caps = int(total_tile_len / 0.35) + 1
    cap_w = total_tile_len / num_caps
    for c in range(num_caps):
        cy = -total_tile_len/2.0 + (c + 0.5) * cap_w
        verts = add_box(bm, material_index=0)
        for v in verts:
            v.co.x *= 0.44
            v.co.y = v.co.y * (cap_w * 1.15) + cy
            v.co.z = v.co.z * 0.12 + pitch_height + 0.09
            
    # 6. Apex Finials at outer gable edges
    for sign_y in [-1, 1]:
        end_y = sign_y * (total_tile_len/2.0 - barge_thick/2.0)
        verts = add_box(bm, material_index=1)
        for v in verts:
            v.co.x *= 0.14
            v.co.y = v.co.y * 0.10 + end_y
            v.co.z = (v.co.z + 0.5) * 0.55 + pitch_height - 0.05

    bm.to_mesh(mesh)
    bm.free()
    
    add_bevel_modifier(obj, width=0.014, segments=2)
    return obj, pitch_height

def create_front_dormer(name, tile_mat=None, timber_mat=None, plaster_mat=None, glow_mat=None):
    """
    Stylized dormer window sitting on roof slope.
    Front window faces -Y with hollow timber frame and radiant glowing amber glass pane.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [tile_mat, timber_mat, plaster_mat, glow_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    dw, dd, dh = 1.05, 1.25, 0.90
    fw = 0.09  # Timber frame width
    fd = 0.10  # Timber frame depth
    
    # 1. Plaster side cheeks extending in +Y into the roof
    for sx in [-dw/2.0 + 0.04, dw/2.0 - 0.04]:
        cheek = add_box(bm, material_index=2)
        for v in cheek:
            v.co.x = v.co.x * 0.08 + sx
            v.co.y = (v.co.y + 0.5) * dd
            v.co.z = (v.co.z + 0.5) * dh
            
    # 2. Hollow Timber Frame at Front (facing -Y)
    # Left & Right Jambs
    for sx in [-dw/2.0 + fw/2.0, dw/2.0 - fw/2.0]:
        jamb = add_box(bm, material_index=1)
        for v in jamb:
            v.co.x = v.co.x * fw + sx
            v.co.y = (v.co.y - 0.5) * fd
            v.co.z = (v.co.z + 0.5) * dh
            
    # Head / Lintel
    lintel = add_box(bm, material_index=1)
    for v in lintel:
        v.co.x *= dw
        v.co.y = (v.co.y - 0.5) * fd
        v.co.z = (v.co.z + 0.5) * fw + (dh - fw)
        
    # Window Sill (protrudes outward and sideways)
    sill = add_box(bm, material_index=1)
    for v in sill:
        v.co.x *= (dw + 0.12)
        v.co.y = (v.co.y - 0.5) * (fd + 0.08)
        v.co.z = (v.co.z + 0.5) * 0.08
        
    # 3. Radiant Glowing Amber Glass Pane (material_index=3, M_Window_Glow)
    gw = dw - fw * 2.0
    gh = dh - fw - 0.08
    glass = add_box(bm, material_index=3)
    for v in glass:
        v.co.x *= (gw + 0.01)
        v.co.y = v.co.y * 0.02 - (fd * 0.40)
        v.co.z = (v.co.z + 0.5) * gh + 0.08
        
    # Center Mullion divider on glass
    mull_v = add_box(bm, material_index=1)
    for v in mull_v:
        v.co.x *= 0.04
        v.co.y = v.co.y * 0.03 - (fd * 0.50)
        v.co.z = (v.co.z + 0.5) * gh + 0.08
        
    # 4. Front Plaster Triangle Gable above Head
    pitch = radians(45.0)
    dormer_pitch_h = (dw / 2.0) * tan(pitch)
    v0 = bm.verts.new((-dw/2.0, -fd/2.0, dh))
    v1 = bm.verts.new(( dw/2.0, -fd/2.0, dh))
    v2 = bm.verts.new(( 0,       -fd/2.0, dh + dormer_pitch_h))
    f_gf = bm.faces.new((v0, v1, v2))
    f_gf.material_index = 2
    
    # 5. Pitched Roof with Tiles and Bargeboards
    roof_half_w = dw * 0.65
    rlen = roof_half_w / cos(pitch)
    slope_roof_len = dd + 0.18
    
    for sign_x in [-1, 1]:
        # Roof tile surface
        verts = add_box(bm, material_index=0)
        for v in verts:
            lx = (v.co.x + 0.5) * rlen
            ly = (v.co.y + 0.5) * slope_roof_len
            lz = v.co.z * 0.06
            v.co.x = sign_x * (roof_half_w - lx * cos(pitch))
            v.co.y = ly - 0.12
            v.co.z = dh + lx * sin(pitch) + lz
            
        # Front Bargeboard along dormer roof slope
        barge = add_box(bm, material_index=1)
        for v in barge:
            lx = (v.co.x + 0.5) * rlen
            ly = v.co.y * 0.08 - 0.10
            lz = v.co.z * 0.12 + 0.03
            v.co.x = sign_x * (roof_half_w - lx * cos(pitch))
            v.co.y = ly
            v.co.z = dh + lx * sin(pitch) + lz
            
    # Small ridge cap on dormer
    d_cap = add_box(bm, material_index=0)
    for v in d_cap:
        v.co.x *= 0.18
        v.co.y = (v.co.y + 0.5) * slope_roof_len - 0.12
        v.co.z = v.co.z * 0.06 + dh + dormer_pitch_h + 0.03
            
    bm.to_mesh(mesh)
    bm.free()
    
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_chimney(name, height=3.8, width=0.8, depth=0.8, stone_mat=None, smoke_mat=None, has_smoke=True, flue_pot=True):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if stone_mat:
        obj.data.materials.append(stone_mat)
    if smoke_mat:
        obj.data.materials.append(smoke_mat)
        
    bm = bmesh.new()
    verts = add_box(bm, material_index=0)
    for v in verts:
        v.co.x *= width
        v.co.y *= depth
        v.co.z = (v.co.z + 0.5) * height
        
    band = add_box(bm, material_index=0)
    for v in band:
        v.co.x *= (width + 0.14)
        v.co.y *= (depth + 0.14)
        v.co.z = v.co.z * 0.16 + (height - 0.28)
        
    crown = add_box(bm, material_index=0)
    for v in crown:
        v.co.x *= (width + 0.20)
        v.co.y *= (depth + 0.20)
        v.co.z = v.co.z * 0.14 + (height - 0.06)
        
    flue = add_box(bm, material_index=0)
    for v in flue:
        v.co.x *= (width * 0.52)
        v.co.y *= (depth * 0.52)
        v.co.z = (v.co.z + 0.5) * 0.38 + height
        
    top_z = height + 0.38
    
    if flue_pot:
        pot = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=width*0.22, radius2=width*0.25, depth=0.22)
        for v in pot['verts']:
            v.co.z += top_z + 0.11
        for f in bm.faces:
            if any(v in set(pot['verts']) for v in f.verts):
                f.material_index = 0
        top_z += 0.22
        
    if has_smoke and smoke_mat:
        puffs = [
            (0.00,  0.02, top_z + 0.20, 0.28),
            (0.14, -0.06, top_z + 0.55, 0.22),
            (0.26, -0.16, top_z + 0.88, 0.16),
            (0.40, -0.25, top_z + 1.15, 0.11),
        ]
        for px, py, pz, pr in puffs:
            sph = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=pr)
            for v in sph['verts']:
                v.co.x += px
                v.co.y += py
                v.co.z += pz
            vset = set(sph['verts'])
            for f in bm.faces:
                if all(v in vset for v in f.verts):
                    f.material_index = 1
                    
    bm.to_mesh(mesh)
    bm.free()
    
    add_bevel_modifier(obj, width=0.016, segments=2)
    return obj

# -------------------------------------------------------------
# Windows & Doors: Hollow Frame & Radiant Glowing Glass
# -------------------------------------------------------------

def create_window_unit(name, width=0.9, height=1.15, timber_mat=None, glow_mat=None, plank_mat=None, foliage_mat=None, flower_mat=None, has_shutters=True, has_planter=True):
    """
    Stylized window unit with hollow timber frame border and radiant glowing amber glass in the center.
    Front faces towards -Y.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [timber_mat, glow_mat, plank_mat, foliage_mat, flower_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    fw = 0.09  # Frame timber width
    fd = 0.10  # Frame timber depth
    
    # 0. Left Jamb
    jamb_l = add_box(bm, material_index=0)
    for v in jamb_l:
        v.co.x = v.co.x * fw - (width/2.0 - fw/2.0)
        v.co.y = (v.co.y - 0.5) * fd
        v.co.z = (v.co.z + 0.5) * height
        
    # Right Jamb
    jamb_r = add_box(bm, material_index=0)
    for v in jamb_r:
        v.co.x = v.co.x * fw + (width/2.0 - fw/2.0)
        v.co.y = (v.co.y - 0.5) * fd
        v.co.z = (v.co.z + 0.5) * height
        
    # Top Head / Lintel
    head = add_box(bm, material_index=0)
    for v in head:
        v.co.x *= width
        v.co.y = (v.co.y - 0.5) * fd
        v.co.z = (v.co.z + 0.5) * fw + (height - fw)
        
    # Window Sill (protrudes outward and sideways)
    sill = add_box(bm, material_index=0)
    for v in sill:
        v.co.x *= (width + 0.16)
        v.co.y = (v.co.y - 0.5) * (fd + 0.08)
        v.co.z = (v.co.z + 0.5) * 0.08 - 0.04
        
    # 1. Radiant Glowing Amber Glass Pane (In center, completely unobstructed!)
    glass_w = width - fw * 2.0
    glass_h = height - fw
    glass = add_box(bm, material_index=1)
    for v in glass:
        v.co.x *= (glass_w + 0.01)
        v.co.y = v.co.y * 0.02 - (fd * 0.40)
        v.co.z = (v.co.z + 0.5) * glass_h + 0.04
        
    # Mullions (Vertical and Horizontal dividers on the glass)
    mull_v = add_box(bm, material_index=0)
    for v in mull_v:
        v.co.x *= 0.04
        v.co.y = v.co.y * 0.03 - (fd * 0.52)
        v.co.z = (v.co.z + 0.5) * glass_h + 0.04
        
    mull_h = add_box(bm, material_index=0)
    for v in mull_h:
        v.co.x *= glass_w
        v.co.y = v.co.y * 0.03 - (fd * 0.52)
        v.co.z = v.co.z * 0.04 + (height * 0.52)
        
    # 2. Wooden Shutters
    if has_shutters:
        shut_w = (width - 0.10) * 0.48
        shut_h = height * 0.88
        for sign_x in [-1, 1]:
            verts = add_box(bm, material_index=2)
            sx = sign_x * (width/2.0 + shut_w/2.0 - 0.01)
            for v in verts:
                v.co.x = v.co.x * shut_w + sx
                v.co.y = v.co.y * 0.04 - (fd * 0.35)
                v.co.z = (v.co.z + 0.5) * shut_h + 0.06
                
    # 3. Planter Box & Flowers
    if has_planter:
        pbox_w = width + 0.12
        verts = add_box(bm, material_index=2)
        for v in verts:
            v.co.x *= pbox_w
            v.co.y = (v.co.y - 0.5) * 0.20 - (fd + 0.02)
            v.co.z = (v.co.z + 0.5) * 0.20 - 0.20
            
        # Green Foliage
        verts = add_box(bm, material_index=3)
        for v in verts:
            v.co.x *= (pbox_w * 0.95)
            v.co.y = (v.co.y - 0.5) * 0.18 - (fd + 0.03)
            v.co.z = (v.co.z + 0.5) * 0.16 - 0.08
            
        # Bright Flower Blooms
        for i in range(7):
            fx = -pbox_w*0.40 + (i / 6.0) * (pbox_w * 0.80)
            verts = add_box(bm, material_index=4)
            for v in verts:
                v.co.x = v.co.x * 0.065 + fx
                v.co.y = v.co.y * 0.065 - (fd + 0.12)
                v.co.z = v.co.z * 0.065 + 0.06

    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_door_unit(name, width=1.1, height=2.1, style="single", timber_mat=None, plank_mat=None, iron_mat=None):
    """
    Heavy plank door with visible wooden planks and iron strap hinges. Front faces towards -Y.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [timber_mat, plank_mat, iron_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    fw = 0.12
    fd = 0.14
    
    # Frame Jambs and Lintel
    jamb_l = add_box(bm, material_index=0)
    for v in jamb_l:
        v.co.x = v.co.x * fw - (width/2.0 + fw/2.0)
        v.co.y = (v.co.y - 0.5) * fd
        v.co.z = (v.co.z + 0.5) * (height + fw)
        
    jamb_r = add_box(bm, material_index=0)
    for v in jamb_r:
        v.co.x = v.co.x * fw + (width/2.0 + fw/2.0)
        v.co.y = (v.co.y - 0.5) * fd
        v.co.z = (v.co.z + 0.5) * (height + fw)
        
    lintel = add_box(bm, material_index=0)
    for v in lintel:
        v.co.x *= (width + fw * 2.2)
        v.co.y = (v.co.y - 0.5) * fd
        v.co.z = (v.co.z + 0.5) * fw + height
        
    # Vertical Planks
    num_planks = 4 if style == "single" else 6
    plank_w = width / num_planks
    for i in range(num_planks):
        px = -width/2.0 + (i + 0.5) * plank_w
        verts = add_box(bm, material_index=1)
        for v in verts:
            v.co.x = v.co.x * (plank_w - 0.015) + px
            v.co.y = v.co.y * 0.06 - (fd * 0.42)
            v.co.z = (v.co.z + 0.5) * height
            
    # Iron Strap Hinges across planks
    for hz in [height * 0.25, height * 0.75]:
        verts = add_box(bm, material_index=2)
        for v in verts:
            v.co.x = (v.co.x + 0.5) * (width * 0.65) - (width * 0.48)
            v.co.y = v.co.y * 0.025 - (fd * 0.65)
            v.co.z = v.co.z * 0.055 + hz
            
    # Iron Ring / Handle
    verts = add_box(bm, material_index=2)
    for v in verts:
        v.co.x = v.co.x * 0.04 + (width * 0.28)
        v.co.y = v.co.y * 0.04 - (fd * 0.70)
        v.co.z = v.co.z * 0.09 + (height * 0.48)
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

# -------------------------------------------------------------
# Props & Street Life
# -------------------------------------------------------------

def create_lantern_prop(name, iron_mat=None, glow_mat=None, is_wall_mounted=True):
    """
    Warm amber street/wall lantern. Arm extends outward towards -Y.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [iron_mat, glow_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    cage_w, cage_h = 0.24, 0.38
    cage_y = -0.28
    
    if is_wall_mounted:
        wp = add_box(bm, material_index=0)
        for v in wp:
            v.co.x *= 0.08
            v.co.y = (v.co.y - 0.5) * 0.04
            v.co.z = (v.co.z + 0.5) * 0.35 - 0.05
            
        arm = add_box(bm, material_index=0)
        for v in arm:
            v.co.x *= 0.04
            v.co.y = (v.co.y - 0.5) * abs(cage_y)
            v.co.z = v.co.z * 0.04 + 0.26
            
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            strut = add_box(bm, material_index=0)
            for v in strut:
                v.co.x = v.co.x * 0.025 + sx * (cage_w/2 - 0.015)
                v.co.y = v.co.y * 0.025 + cage_y + sy * (cage_w/2 - 0.015)
                v.co.z = (v.co.z + 0.5) * cage_h
                
    top_cap = add_box(bm, material_index=0)
    for v in top_cap:
        v.co.x *= (cage_w + 0.06)
        v.co.y = v.co.y * (cage_w + 0.06) + cage_y
        v.co.z = (v.co.z + 0.5) * 0.14 + cage_h
        
    bot_cap = add_box(bm, material_index=0)
    for v in bot_cap:
        v.co.x *= (cage_w + 0.04)
        v.co.y = v.co.y * (cage_w + 0.04) + cage_y
        v.co.z = v.co.z * 0.04 - 0.02
        
    core = add_box(bm, material_index=1)
    for v in core:
        v.co.x *= (cage_w - 0.04)
        v.co.y = v.co.y * (cage_w - 0.04) + cage_y
        v.co.z = (v.co.z + 0.5) * (cage_h - 0.04) + 0.02
        
    bm.to_mesh(mesh)
    bm.free()
    
    light_data = bpy.data.lights.new(name=name + "_Light", type='POINT')
    light_data.energy = 45.0
    light_data.color = (1.0, 0.65, 0.18)
    light_data.shadow_soft_size = 0.15
    light_obj = bpy.data.objects.new(name + "_Light", light_data)
    light_obj.location = (0, cage_y, cage_h / 2.0)
    light_obj.parent = obj
    
    return obj, light_obj

def create_hanging_sign(name, emblem_type="tavern", timber_mat=None, iron_mat=None, emblem_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [iron_mat, timber_mat, emblem_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    arm_len = 0.95
    
    arm = add_box(bm, material_index=0)
    for v in arm:
        v.co.x *= 0.05
        v.co.y = (v.co.y - 0.5) * arm_len
        v.co.z = v.co.z * 0.05 + 0.65
        
    diag = add_box(bm, material_index=0)
    for v in diag:
        v.co.x *= 0.04
        v.co.y = (v.co.y - 0.5) * (arm_len * 0.6)
        v.co.z = (v.co.z + 0.5) * 0.45 + 0.20
        
    for hy in [-0.30, -0.75]:
        link = add_box(bm, material_index=0)
        for v in link:
            v.co.x *= 0.02
            v.co.y = v.co.y * 0.02 + hy
            v.co.z = (v.co.z + 0.5) * 0.15 + 0.48
            
    board = add_box(bm, material_index=1)
    board_w, board_h, board_y = 0.58, 0.52, -0.52
    for v in board:
        v.co.x *= 0.06
        v.co.y = v.co.y * board_w + board_y
        v.co.z = (v.co.z + 0.5) * board_h
        
    emblem = add_box(bm, material_index=2)
    for v in emblem:
        v.co.x *= 0.08
        v.co.y = v.co.y * 0.30 + board_y
        v.co.z = v.co.z * 0.30 + (board_h * 0.52)
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_barrel(name, radius=0.38, height=0.90, plank_mat=None, iron_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [plank_mat, iron_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    seg = 14
    body = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=radius*0.88, radius2=radius*0.88, depth=height)
    for v in body['verts']:
        t = abs(v.co.z / (height/2.0))
        scale = 1.0 + (1.0 - t**2) * 0.18
        v.co.x *= scale
        v.co.y *= scale
        v.co.z += height/2.0
    for f in bm.faces:
        f.material_index = 0
        
    for hz in [height*0.18, height*0.50, height*0.82]:
        hoop = bmesh.ops.create_cone(bm, cap_ends=False, segments=seg, radius1=radius*1.02, radius2=radius*1.02, depth=0.04)
        for v in hoop['verts']:
            v.co.z += hz
        vset = set(hoop['verts'])
        for f in bm.faces:
            if all(v in vset for v in f.verts):
                f.material_index = 1
                
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_crate(name, size=0.75, plank_mat=None, iron_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [plank_mat, iron_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    inner = add_box(bm, material_index=0)
    for v in inner:
        v.co.x *= (size - 0.04)
        v.co.y *= (size - 0.04)
        v.co.z = (v.co.z + 0.5) * (size - 0.04) + 0.02
        
    bw = 0.09
    for z_off in [0.03, size - 0.03]:
        border = add_box(bm, material_index=0)
        for v in border:
            v.co.x *= size
            v.co.y *= size
            v.co.z = v.co.z * bw + z_off
            
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            post = add_box(bm, material_index=0)
            for v in post:
                v.co.x = v.co.x * bw + sx * (size/2 - bw/2)
                v.co.y = v.co.y * bw + sy * (size/2 - bw/2)
                v.co.z = (v.co.z + 0.5) * size
                
    for cz in [0.04, size - 0.04]:
        for sx in [-1, 1]:
            for sy in [-1, 1]:
                corner = add_box(bm, material_index=1)
                for v in corner:
                    v.co.x = v.co.x * 0.05 + sx * (size/2 - 0.02)
                    v.co.y = v.co.y * 0.05 + sy * (size/2 - 0.02)
                    v.co.z = v.co.z * 0.06 + cz
                    
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_blacksmith_forge_hearth(name, stone_mat=None, ember_mat=None, iron_mat=None):
    """
    Open stone hearth basin with blazing hot coals, hood, flue, tree stump and anvil.
    Front faces towards -Y.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [stone_mat, ember_mat, iron_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    
    # 0. Stone Basin
    basin = add_box(bm, material_index=0)
    for v in basin:
        v.co.x *= 1.40
        v.co.y = (v.co.y - 0.5) * 1.10
        v.co.z = (v.co.z + 0.5) * 0.85
        
    # 1. Blazing Red/Orange Coals
    coal = add_box(bm, material_index=1)
    for v in coal:
        v.co.x *= 1.10
        v.co.y = (v.co.y - 0.5) * 0.80 - 0.10
        v.co.z = v.co.z * 0.14 + 0.86
        
    # Stone Hood and Flue
    hood = add_box(bm, material_index=0)
    for v in hood:
        v.co.x *= 1.40
        v.co.y = (v.co.y - 0.5) * 0.60
        v.co.z = (v.co.z + 0.5) * 1.80 + 0.85
        
    flue = add_box(bm, material_index=0)
    for v in flue:
        v.co.x *= 0.75
        v.co.y = (v.co.y - 0.5) * 0.60
        v.co.z = (v.co.z + 0.5) * 1.60 + 2.65
        
    # Oak Stump for Anvil (at y = -1.40)
    stump_y = -1.35
    stump = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.34, radius2=0.34, depth=0.55)
    for v in stump['verts']:
        v.co.y += stump_y
        v.co.z += 0.275
    vset = set(stump['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = 0
            
    # Heavy Cast Iron Anvil
    anvil = add_box(bm, material_index=2)
    for v in anvil:
        v.co.x *= 0.38
        v.co.y = v.co.y * 0.65 + stump_y
        v.co.z = v.co.z * 0.25 + 0.68
        
    horn = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.12, radius2=0.01, depth=0.32)
    for v in horn['verts']:
        vy = v.co.z
        vz = v.co.y
        v.co.y = vy + stump_y - 0.38
        v.co.z = vz + 0.72
    vset = set(horn['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = 2
            
    bm.to_mesh(mesh)
    bm.free()
    
    fire_light_data = bpy.data.lights.new(name=name + "_FireLight", type='POINT')
    fire_light_data.energy = 65.0
    fire_light_data.color = (1.0, 0.42, 0.06)
    fire_light_data.shadow_soft_size = 0.25
    fire_obj = bpy.data.objects.new(name + "_FireLight", fire_light_data)
    fire_obj.location = (0, -0.45, 1.10)
    fire_obj.parent = obj
    
    add_bevel_modifier(obj, width=0.014, segments=2)
    return obj, fire_obj

def create_market_stall_awning(name, width=2.4, depth=1.6, height=2.2, stripe_mat=None, timber_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [stripe_mat, timber_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    post_w = 0.10
    
    # Outer support posts at y = -depth
    for sx in [-width/2 + post_w/2, width/2 - post_w/2]:
        p = add_box(bm, material_index=1)
        for v in p:
            v.co.x = v.co.x * post_w + sx
            v.co.y = v.co.y * post_w - (depth - post_w/2)
            v.co.z = (v.co.z + 0.5) * height
            
    # Sloping canvas canopy
    slope_angle = radians(20.0)
    canopy_len = depth / cos(slope_angle)
    canopy = add_box(bm, material_index=0)
    for v in canopy:
        lx = v.co.x * (width + 0.15)
        ly = (v.co.y + 0.5) * canopy_len
        lz = v.co.z * 0.03
        v.co.x = lx
        v.co.y = -ly * cos(slope_angle)
        v.co.z = height + 0.35 - ly * sin(slope_angle) + lz
        
    flap = add_box(bm, material_index=0)
    for v in flap:
        v.co.x *= (width + 0.15)
        v.co.y = v.co.y * 0.02 - depth
        v.co.z = v.co.z * 0.20 + height - 0.04
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_balcony_unit(name, width=2.6, depth=1.1, timber_mat=None, plank_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [timber_mat, plank_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    num_beams = 3
    bw = 0.14
    for i in range(num_beams):
        bx = -width/2 + bw/2 + (i / (num_beams - 1)) * (width - bw)
        beam = add_box(bm, material_index=0)
        for v in beam:
            v.co.x = v.co.x * bw + bx
            v.co.y = (v.co.y - 0.5) * depth
            v.co.z = v.co.z * 0.18 - 0.09
            
    deck = add_box(bm, material_index=1)
    for v in deck:
        v.co.x *= width
        v.co.y = (v.co.y - 0.5) * depth
        v.co.z = v.co.z * 0.05 + 0.025
        
    rw, rh = 0.08, 0.95
    for px in [-width/2 + rw/2, 0, width/2 - rw/2]:
        p = add_box(bm, material_index=0)
        for v in p:
            v.co.x = v.co.x * rw + px
            v.co.y = v.co.y * rw - (depth - rw/2)
            v.co.z = (v.co.z + 0.5) * rh
            
    rail = add_box(bm, material_index=0)
    for v in rail:
        v.co.x *= (width + 0.05)
        v.co.y = v.co.y * 0.10 - (depth - rw/2)
        v.co.z = v.co.z * 0.06 + rh
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_stone_steps(name, width=1.6, depth=1.2, height=0.6, num_steps=3, stone_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if stone_mat:
        obj.data.materials.append(stone_mat)
        
    bm = bmesh.new()
    step_d = depth / num_steps
    step_h = height / num_steps
    for i in range(num_steps):
        s = add_box(bm, material_index=0)
        curr_d = depth - (i * step_d)
        for v in s:
            v.co.x *= (width + (num_steps - 1 - i) * 0.08)
            v.co.y = (v.co.y - 0.5) * curr_d
            v.co.z = (v.co.z + 0.5) * step_h + (i * step_h)
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.016, segments=2)
    return obj

def create_wood_bench(name, width=1.4, depth=0.45, height=0.50, timber_mat=None, plank_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [timber_mat, plank_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    for sx in [-width/2 + 0.1, width/2 - 0.1]:
        for sy in [-depth/2 + 0.08, depth/2 - 0.08]:
            p = add_box(bm, material_index=0)
            for v in p:
                v.co.x = v.co.x * 0.08 + sx
                v.co.y = v.co.y * 0.08 + sy
                v.co.z = (v.co.z + 0.5) * height
                
    seat = add_box(bm, material_index=1)
    for v in seat:
        v.co.x *= width
        v.co.y *= depth
        v.co.z = v.co.z * 0.06 + height
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_fence_section(name, length=2.0, height=0.85, timber_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    pw = 0.12
    for ex in [-length/2 + pw/2, length/2 - pw/2]:
        p = add_box(bm, material_index=0)
        for v in p:
            v.co.x = v.co.x * pw + ex
            v.co.y *= pw
            v.co.z = (v.co.z + 0.5) * height
            
    for rz in [height * 0.35, height * 0.80]:
        rail = add_box(bm, material_index=0)
        for v in rail:
            v.co.x *= (length - pw)
            v.co.y *= 0.06
            v.co.z = v.co.z * 0.08 + rz
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_flowerpot_prop(name, radius=0.22, height=0.35, stone_mat=None, foliage_mat=None, flower_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    for m in [stone_mat, foliage_mat, flower_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    pot = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=radius*0.75, radius2=radius, depth=height)
    for v in pot['verts']:
        v.co.z += height/2.0
    for f in bm.faces:
        f.material_index = 0
        
    shrub = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius*1.1)
    for v in shrub['verts']:
        v.co.z += height + 0.08
    vset = set(shrub['verts'])
    for f in bm.faces:
        if all(v in vset for v in f.verts):
            f.material_index = 1
            
    for i in range(5):
        ang = i * (2 * pi / 5.0)
        fx = cos(ang) * (radius * 0.6)
        fy = sin(ang) * (radius * 0.6)
        fl = add_box(bm, material_index=2)
        for v in fl:
            v.co.x = v.co.x * 0.06 + fx
            v.co.y = v.co.y * 0.06 + fy
            v.co.z = v.co.z * 0.06 + height + 0.20
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_hay_bale(name, width=0.75, length=1.2, height=0.55, straw_mat=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    if straw_mat:
        obj.data.materials.append(straw_mat)
        
    bm = bmesh.new()
    bale = add_box(bm, material_index=0)
    for v in bale:
        v.co.x *= width
        v.co.y *= length
        v.co.z = (v.co.z + 0.5) * height
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.03, segments=2)
    return obj

def create_rafter_tails(name, span=4.4, length=5.2, axis="y", overhang_eave=0.42, spacing=0.55, timber_mat=None):
    """
    Exposed rafter tails under roof eaves along the building length.
    If axis == 'y': Ridge is along Y, eaves are at -X and +X.
    If axis == 'x': Ridge is along X, eaves are at -Y and +Y.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    rw = 0.12
    rh = 0.14
    r_len = overhang_eave + 0.15
    
    num = max(2, int(length / spacing))
    step = length / num
    
    if axis == "y":
        half_span = span / 2.0
        for i in range(num + 1):
            py = -length/2.0 + i * step
            for sign_x in [-1, 1]:
                verts = add_box(bm, material_index=0)
                px = sign_x * (half_span + r_len/2.0 - 0.08)
                for v in verts:
                    v.co.x = v.co.x * r_len + px
                    v.co.y = v.co.y * rw + py
                    v.co.z = v.co.z * rh - rh/2.0
    else:
        half_span = span / 2.0
        for i in range(num + 1):
            px = -length/2.0 + i * step
            for sign_y in [-1, 1]:
                verts = add_box(bm, material_index=0)
                py = sign_y * (half_span + r_len/2.0 - 0.08)
                for v in verts:
                    v.co.x = v.co.x * rw + px
                    v.co.y = v.co.y * r_len + py
                    v.co.z = v.co.z * rh - rh/2.0

    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

def create_wall_strut(name, p1, p2, width=0.14, depth=0.18, timber_mat=None):
    """Creates a standalone diagonal timber strut between p1 and p2."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat:
        obj.data.materials.append(timber_mat)
    bm = bmesh.new()
    add_diagonal_box(bm, p1, p2, width=width, depth=depth, material_index=0)
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

def create_timber_framing_overlay(name, width, height, num_bays=2, has_crosses=True, depth=0.16, timber_mat=None):
    """
    Planar half-timber structural frame with posts, girts, and St. Andrew's cross braces (X).
    Centered at origin, facing -Y.
    """
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    bw = 0.14
    bd = depth
    
    bot = add_box(bm, material_index=0)
    for v in bot:
        v.co.x *= width
        v.co.y *= bd
        v.co.z = (v.co.z + 0.5) * bw
        
    top = add_box(bm, material_index=0)
    for v in top:
        v.co.x *= width
        v.co.y *= bd
        v.co.z = (v.co.z + 0.5) * bw + (height - bw)
        
    mid = add_box(bm, material_index=0)
    for v in mid:
        v.co.x *= width
        v.co.y *= bd
        v.co.z = (v.co.z + 0.5) * bw + (height/2.0 - bw/2.0)
        
    bay_w = width / num_bays
    for i in range(num_bays + 1):
        px = -width/2.0 + i * bay_w
        post = add_box(bm, material_index=0)
        for v in post:
            v.co.x = v.co.x * bw + px
            v.co.y *= bd
            v.co.z = (v.co.z + 0.5) * height
            
    if has_crosses:
        for b in range(num_bays):
            bx_l = -width/2.0 + b * bay_w + bw/2.0
            bx_r = -width/2.0 + (b + 1) * bay_w - bw/2.0
            add_diagonal_box(bm, Vector((bx_l, 0, bw)), Vector((bx_r, 0, height/2.0 - bw/2.0)), width=0.11, depth=bd, material_index=0)
            add_diagonal_box(bm, Vector((bx_l, 0, height/2.0 - bw/2.0)), Vector((bx_r, 0, bw)), width=0.11, depth=bd, material_index=0)
            add_diagonal_box(bm, Vector((bx_l, 0, height/2.0 + bw/2.0)), Vector((bx_r, 0, height - bw)), width=0.11, depth=bd, material_index=0)
            add_diagonal_box(bm, Vector((bx_l, 0, height - bw)), Vector((bx_r, 0, height/2.0 + bw/2.0)), width=0.11, depth=bd, material_index=0)

    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

def create_quenching_trough(name, length=1.3, width=0.6, height=0.55, timber_mat=None, water_mat=None, iron_mat=None):
    """Heavy water quenching trough for blacksmith with water surface and iron bands."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, water_mat, iron_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    thick = 0.07
    bot = add_box(bm, material_index=0)
    for v in bot:
        v.co.x *= length
        v.co.y *= width
        v.co.z = v.co.z * thick + thick/2.0
        
    for sy in [-width/2 + thick/2, width/2 - thick/2]:
        side = add_box(bm, material_index=0)
        for v in side:
            v.co.x *= length
            v.co.y = v.co.y * thick + sy
            v.co.z = (v.co.z + 0.5) * (height - thick) + thick
            
    for sx in [-length/2 + thick/2, length/2 - thick/2]:
        end = add_box(bm, material_index=0)
        for v in end:
            v.co.x = v.co.x * thick + sx
            v.co.y *= (width - thick*2)
            v.co.z = (v.co.z + 0.5) * (height - thick) + thick
            
    water = add_box(bm, material_index=1)
    for v in water:
        v.co.x *= (length - thick*2)
        v.co.y *= (width - thick*2)
        v.co.z = v.co.z * 0.04 + (height * 0.82)
        
    for sx in [-length*0.35, length*0.35]:
        band = add_box(bm, material_index=2)
        for v in band:
            v.co.x = v.co.x * 0.05 + sx
            v.co.y *= (width + 0.03)
            v.co.z = (v.co.z + 0.5) * height
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_potion_counter_prop(name, width=2.4, depth=0.75, height=0.88, timber_mat=None, plank_mat=None, potion_mats=None):
    """Shop / apothecary counter display with stacked glowing potion flasks (blue, red, green)."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    mats_list = [timber_mat, plank_mat]
    if potion_mats:
        mats_list.extend(potion_mats)
    for m in mats_list:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    for sx in [-width/2 + 0.08, width/2 - 0.08]:
        for sy in [-depth/2 + 0.08, depth/2 - 0.08]:
            p = add_box(bm, material_index=0)
            for v in p:
                v.co.x = v.co.x * 0.10 + sx
                v.co.y = v.co.y * 0.10 + sy
                v.co.z = (v.co.z + 0.5) * height
                
    top = add_box(bm, material_index=1)
    for v in top:
        v.co.x *= (width + 0.10)
        v.co.y *= (depth + 0.10)
        v.co.z = v.co.z * 0.08 + height
        
    shelf = add_box(bm, material_index=1)
    for v in shelf:
        v.co.x *= (width - 0.12)
        v.co.y *= (depth - 0.12)
        v.co.z = v.co.z * 0.04 + height * 0.35

    bottle_configs = [
        (-0.85, -0.10, 2, "round", 0.13),
        (-0.62,  0.10, 3, "tall",  0.18),
        (-0.40, -0.08, 4, "round", 0.12),
        ( 0.00,  0.08, 2, "tall",  0.20),
        ( 0.28, -0.10, 3, "round", 0.14),
        ( 0.50,  0.12, 4, "tall",  0.17),
        ( 0.75, -0.05, 2, "round", 0.12),
    ]
    
    for bx, by, mat_idx, btype, bh in bottle_configs:
        curr_mat = min(mat_idx, len(mats_list) - 1)
        z_base = height + 0.04
        if btype == "round":
            rad = bh * 0.45
            sph = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad)
            for v in sph['verts']:
                v.co.x += bx
                v.co.y += by
                v.co.z += z_base + rad
            vset = set(sph['verts'])
            for f in bm.faces:
                if all(v in vset for v in f.verts):
                    f.material_index = curr_mat
            neck = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=rad*0.35, radius2=rad*0.35, depth=bh*0.4)
            for v in neck['verts']:
                v.co.x += bx
                v.co.y += by
                v.co.z += z_base + rad*1.7 + bh*0.2
            vset = set(neck['verts'])
            for f in bm.faces:
                if all(v in vset for v in f.verts):
                    f.material_index = 0
        else:
            rad = bh * 0.28
            cyl = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=rad, radius2=rad*0.85, depth=bh*0.75)
            for v in cyl['verts']:
                v.co.x += bx
                v.co.y += by
                v.co.z += z_base + bh*0.38
            vset = set(cyl['verts'])
            for f in bm.faces:
                if all(v in vset for v in f.verts):
                    f.material_index = curr_mat
            cork = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=rad*0.45, radius2=rad*0.5, depth=bh*0.22)
            for v in cork['verts']:
                v.co.x += bx
                v.co.y += by
                v.co.z += z_base + bh*0.82
            vset = set(cork['verts'])
            for f in bm.faces:
                if all(v in vset for v in f.verts):
                    f.material_index = 0

    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_laundry_line_prop(name, p1, p2, sag=0.14, timber_mat=None, cloth_white=None, cloth_blue=None, cloth_red=None):
    """Hanging laundry line strung between two 3D points p1 and p2 with clothes hanging down."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, cloth_white, cloth_blue, cloth_red]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    p1 = Vector(p1)
    p2 = Vector(p2)
    diff = p2 - p1
    span = diff.length
    if span < 0.2:
        bm.free()
        return obj
        
    num_segs = 12
    rope_r = 0.012
    prev_pt = p1
    for i in range(1, num_segs + 1):
        t = i / num_segs
        curr_pt = p1 + diff * t
        curr_pt.z -= 4.0 * sag * t * (1.0 - t)
        add_diagonal_box(bm, prev_pt, curr_pt, width=rope_r*2, depth=rope_r*2, material_index=0)
        prev_pt = curr_pt
        
    clothes = [
        (0.22, 1, 0.42, 0.52),
        (0.48, 2, 0.36, 0.65),
        (0.74, 3, 0.40, 0.45),
    ]
    for frac, mat_idx, cw, ch in clothes:
        pt = p1 + diff * frac
        pt.z -= 4.0 * sag * frac * (1.0 - frac)
        item = add_box(bm, material_index=mat_idx)
        for v in item:
            v.co.x = v.co.x * cw + pt.x
            v.co.y = v.co.y * 0.025 + pt.y
            v.co.z = (v.co.z - 0.5) * ch + pt.z
            
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_hay_crane_hoist(name, length=1.6, timber_mat=None, iron_mat=None):
    """Cantilevered wooden crane hoist boom protruding from gable apex with pulley and hook."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    bw = 0.16
    boom = add_box(bm, material_index=0)
    for v in boom:
        v.co.x *= bw
        v.co.y = (v.co.y - 0.5) * length
        v.co.z *= bw
        
    add_diagonal_box(bm, Vector((0, -length * 0.75, -bw/2)), Vector((0, -0.1, -length * 0.65)), width=0.12, depth=0.12, material_index=0)
    
    wheel_y = -length + 0.18
    wheel = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.16, radius2=0.16, depth=0.06)
    for v in wheel['verts']:
        vx = v.co.z
        vz = v.co.x
        v.co.x = vx
        v.co.y += wheel_y
        v.co.z = vz - bw/2 - 0.14
    for f in bm.faces:
        if any(v in set(wheel['verts']) for v in f.verts):
            f.material_index = 1
            
    rope = add_box(bm, material_index=0)
    for v in rope:
        v.co.x *= 0.02
        v.co.y = v.co.y * 0.02 + wheel_y
        v.co.z = (v.co.z - 0.5) * 0.95 - bw/2 - 0.25
        
    hook = add_box(bm, material_index=1)
    for v in hook:
        v.co.x *= 0.08
        v.co.y = v.co.y * 0.06 + wheel_y
        v.co.z = v.co.z * 0.12 - bw/2 - 1.25
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_heraldic_banner(name, emblem_type="tavern", timber_mat=None, iron_mat=None, cloth_mat=None, gold_mat=None):
    """Hanging cloth banner with embroidered gold emblem (tankard, horse, hammers)."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat, cloth_mat, gold_mat]:
        if m:
            obj.data.materials.append(m)
            
    bm = bmesh.new()
    arm_len = 1.10
    arm = add_box(bm, material_index=1)
    for v in arm:
        v.co.x *= 0.06
        v.co.y = (v.co.y - 0.5) * arm_len
        v.co.z *= 0.06
        
    diag = add_box(bm, material_index=1)
    for v in diag:
        v.co.x *= 0.04
        v.co.y = (v.co.y - 0.5) * (arm_len * 0.7)
        v.co.z = (v.co.z + 0.5) * 0.45 - 0.45
        
    bw, bh = 0.55, 1.15
    by = -arm_len * 0.70
    cloth = add_box(bm, material_index=2)
    for v in cloth:
        v.co.x *= bw
        v.co.y = v.co.y * 0.02 + by
        v.co.z = (v.co.z - 0.5) * bh
        
    emblem = add_box(bm, material_index=3)
    for v in emblem:
        v.co.x *= (bw * 0.55)
        v.co.y = v.co.y * 0.04 + by
        v.co.z = v.co.z * (bw * 0.55) - (bh * 0.42)
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_firewood_stack(name, width=1.3, depth=0.55, height=0.75, timber_mat=None):
    """Stacked split logs for fuel."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat:
        obj.data.materials.append(timber_mat)
        
    bm = bmesh.new()
    r = 0.09
    num_x = int(width / (r * 2.1))
    num_z = int(height / (r * 1.8))
    for iz in range(num_z):
        off_x = (r if iz % 2 == 1 else 0.0)
        curr_nx = num_x - (1 if iz % 2 == 1 else 0)
        for ix in range(curr_nx):
            lx = -width/2.0 + r + ix * (r * 2.1) + off_x
            lz = r + iz * (r * 1.8)
            cyl = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=r*0.95, radius2=r*0.95, depth=depth)
            for v in cyl['verts']:
                vy = v.co.z
                vz = v.co.y
                v.co.x += lx
                v.co.y = vy
                v.co.z = vz + lz
            for f in bm.faces:
                f.material_index = 0

    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

# =============================================================
# FORTIFICATIONS & WALLS
# =============================================================
def create_curtain_wall(name, width=4.0, height=3.5, depth=1.2, stone_mat=None, banner_mat=None):
    """Crenellated stone curtain wall with battlements, parapet walkway, and machicolation corbels."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, banner_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Main wall body
    wall = add_box(bm, material_index=0)
    for v in wall:
        v.co.x *= width
        v.co.y *= depth
        v.co.z = (v.co.z + 0.5) * (height - 0.7)
        
    # Corbelled machicolation projection
    corb_h = 0.25
    corb_d = depth + 0.30
    corb = add_box(bm, material_index=0)
    for v in corb:
        v.co.x *= width
        v.co.y *= corb_d
        v.co.z = (v.co.z + 0.5) * corb_h + (height - 0.7)
        
    # Front parapet with merlons (crenellations)
    parapet_w = 0.25
    num_merlons = 4
    merlon_w = (width - 0.2) / (num_merlons * 2 - 1)
    for i in range(num_merlons):
        mx = -width/2.0 + 0.1 + merlon_w/2.0 + i * (merlon_w * 2)
        m_box = add_box(bm, material_index=0)
        for v in m_box:
            v.co.x = v.co.x * merlon_w + mx
            v.co.y = (v.co.y - 0.5) * parapet_w - corb_d/2.0 + parapet_w
            v.co.z = (v.co.z + 0.5) * 0.75 + (height - 0.7 + corb_h)
            
    # Back low curb rail for walkway
    curb = add_box(bm, material_index=0)
    for v in curb:
        v.co.x *= width
        v.co.y = (v.co.y + 0.5) * 0.15 + corb_d/2.0 - 0.15
        v.co.z = (v.co.z + 0.5) * 0.30 + (height - 0.7 + corb_h)
        
    # Optional heraldic banner hanging on front face
    if banner_mat:
        banner = add_box(bm, material_index=1)
        for v in banner:
            v.co.x *= 0.8
            v.co.y = v.co.y * 0.02 - depth/2.0 - 0.02
            v.co.z = (v.co.z - 0.5) * 1.5 + (height - 0.8)

    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_wall_corner(name, width=3.0, height=3.5, stone_mat=None):
    """90-degree stone corner fortification wall with crenellations."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat: obj.data.materials.append(stone_mat)
    bm = bmesh.new()
    d = 1.2
    
    # Leg 1 along X
    l1 = add_box(bm, material_index=0)
    for v in l1:
        v.co.x = (v.co.x + 0.5) * width - d/2.0
        v.co.y *= d
        v.co.z = (v.co.z + 0.5) * (height - 0.7)
    # Leg 2 along Y
    l2 = add_box(bm, material_index=0)
    for v in l2:
        v.co.x *= d
        v.co.y = (v.co.y + 0.5) * width - d/2.0
        v.co.z = (v.co.z + 0.5) * (height - 0.7)
        
    # Corner crenellations
    c_box = add_box(bm, material_index=0)
    for v in c_box:
        v.co.x = (v.co.x - 0.5) * 0.35 - d/2.0 + 0.35
        v.co.y = (v.co.y - 0.5) * 0.35 - d/2.0 + 0.35
        v.co.z = (v.co.z + 0.5) * 0.75 + (height - 0.7)
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_wall_tower(name, radius=1.6, height=5.5, stone_mat=None, banner_mat=None):
    """Fortified stone bastion tower with machicolations and battlements."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, banner_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Base shaft (octagonal)
    shaft = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=radius, radius2=radius, depth=height - 1.0)
    for v in shaft['verts']:
        v.co.z += (height - 1.0) / 2.0
    for f in bm.faces: f.material_index = 0
    
    # Corbelled top platform (wider)
    top_r = radius + 0.35
    top_h = 0.35
    top = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=top_r, radius2=top_r, depth=top_h)
    for v in top['verts']:
        v.co.z += height - 1.0 + top_h/2.0
        
    # Crenellated parapet teeth
    for i in range(8):
        ang = radians(i * 45)
        merlon = add_box(bm, material_index=0)
        for v in merlon:
            vx, vy = v.co.x * 0.45, v.co.y * 0.25
            v.co.x = vx * cos(ang) - vy * sin(ang) + cos(ang) * (top_r - 0.15)
            v.co.y = vx * sin(ang) + vy * cos(ang) + sin(ang) * (top_r - 0.15)
            v.co.z = (v.co.z + 0.5) * 0.8 + height - 1.0 + top_h
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_castle_gate_portal(name, width=5.0, height=4.5, depth=1.8, stone_mat=None, iron_mat=None, timber_mat=None, banner_mat=None):
    """Fortified gatehouse portal with archway, raised iron portcullis grille, and battlements."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, iron_mat, timber_mat, banner_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    arch_w, arch_h = 2.2, 3.2
    side_w = (width - arch_w) / 2.0
    
    # Left & Right stone piers
    for sign_x in [-1, 1]:
        pier = add_box(bm, material_index=0)
        for v in pier:
            v.co.x = v.co.x * side_w + sign_x * (width/2.0 - side_w/2.0)
            v.co.y *= depth
            v.co.z = (v.co.z + 0.5) * height
            
    # Top archway lintel block
    top_h = height - arch_h
    top = add_box(bm, material_index=0)
    for v in top:
        v.co.x *= arch_w
        v.co.y *= depth
        v.co.z = (v.co.z + 0.5) * top_h + arch_h
        
    # Iron Portcullis Grille (raised inside arch)
    grille_bars = 6
    for i in range(grille_bars):
        gx = -arch_w/2.0 + 0.2 + i * ((arch_w - 0.4)/(grille_bars - 1))
        bar = add_box(bm, material_index=1)
        for v in bar:
            v.co.x = v.co.x * 0.05 + gx
            v.co.y *= 0.05
            v.co.z = (v.co.z + 0.5) * 1.8 + (arch_h - 1.2)
    # Horizontal grille ties
    for gz in [arch_h - 1.0, arch_h - 0.4, arch_h + 0.2]:
        hbar = add_box(bm, material_index=1)
        for v in hbar:
            v.co.x *= (arch_w - 0.3)
            v.co.y *= 0.06
            v.co.z = v.co.z * 0.05 + gz
            
    # Top battlements
    merlons = 5
    mw = width / (merlons * 2 - 1)
    for i in range(merlons):
        mx = -width/2.0 + mw/2.0 + i * (mw * 2)
        m_box = add_box(bm, material_index=0)
        for v in m_box:
            v.co.x = v.co.x * mw + mx
            v.co.y = (v.co.y - 0.5) * 0.3 - depth/2.0 + 0.3
            v.co.z = (v.co.z + 0.5) * 0.75 + height
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_retaining_wall(name, width=4.0, height=2.2, depth=1.0, stone_mat=None, timber_mat=None):
    """Battered drystone retaining wall with timber coping rail."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, timber_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    wall = add_box(bm, material_index=0)
    for v in wall:
        v.co.x *= width
        v.co.y = v.co.y * depth - (0.15 if v.co.z > 0 else 0)
        v.co.z = (v.co.z + 0.5) * height
        
    cap = add_box(bm, material_index=1)
    for v in cap:
        v.co.x *= (width + 0.1)
        v.co.y *= (depth + 0.15)
        v.co.z = (v.co.z + 0.5) * 0.14 + height
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_cliff_wall(name, width=4.0, height=2.8, stone_mat=None, foliage_mat=None):
    """Rough natural rock embankment wall with climbing ivy."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, foliage_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Stepped rock blocks
    for i in range(3):
        rz = i * (height / 3.0)
        rh = height / 3.0 + 0.05
        block = add_box(bm, material_index=0)
        for v in block:
            v.co.x *= (width - i * 0.15)
            v.co.y = (v.co.y - 0.5) * (1.2 - i * 0.2)
            v.co.z = (v.co.z + 0.5) * rh + rz
            
    # Ivy patches on front
    for ix in [-1.2, 0.4, 1.3]:
        ivy = add_box(bm, material_index=1)
        for v in ivy:
            v.co.x = v.co.x * 0.65 + ix
            v.co.y = v.co.y * 0.06 - 1.25
            v.co.z = (v.co.z + 0.5) * 1.6 + 0.3
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.02, segments=2)
    return obj

def create_ruin_wall(name, width=3.5, height=2.5, stone_mat=None, foliage_mat=None):
    """Jagged broken crumbling stone wall."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, foliage_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Broken jagged sections
    steps = [2.4, 1.8, 1.2, 0.6]
    sw = width / len(steps)
    for i, sh in enumerate(steps):
        sx = -width/2.0 + sw/2.0 + i * sw
        b = add_box(bm, material_index=0)
        for v in b:
            v.co.x = v.co.x * sw + sx
            v.co.y *= 0.85
            v.co.z = (v.co.z + 0.5) * sh
            
    # Fallen stone debris at base
    for rx, ry in [(-0.8, -0.6), (0.6, -0.7), (1.2, 0.6)]:
        debris = add_box(bm, material_index=0)
        for v in debris:
            v.co.x = v.co.x * 0.45 + rx
            v.co.y = v.co.y * 0.35 + ry
            v.co.z = (v.co.z + 0.5) * 0.30
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.02, segments=2)
    return obj

# =============================================================
# STAIRS, RAMPS & BRIDGES
# =============================================================
def create_large_stairs(name, width=2.4, height=1.6, depth=3.0, stone_mat=None):
    """Grand stone staircase flight with side balustrades."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat: obj.data.materials.append(stone_mat)
    bm = bmesh.new()
    num_steps = 8
    sh = height / num_steps
    sd = depth / num_steps
    for i in range(num_steps):
        s = add_box(bm, material_index=0)
        for v in s:
            v.co.x *= (width - 0.4)
            v.co.y = (v.co.y - 0.5) * (depth - i * sd)
            v.co.z = (v.co.z + 0.5) * sh + i * sh
            
    # Left and right stone balustrades
    for sign_x in [-1, 1]:
        bal = add_box(bm, material_index=0)
        for v in bal:
            v.co.x = v.co.x * 0.20 + sign_x * (width/2.0 - 0.10)
            v.co.y = (v.co.y - 0.5) * (depth + 0.2)
            v.co.z = (v.co.z + 0.5) * (height + 0.4)
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_cart_ramp(name, width=2.2, length=3.5, height=1.2, stone_mat=None):
    """Inclined cobblestone cart ramp with curb stones."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat: obj.data.materials.append(stone_mat)
    bm = bmesh.new()
    
    # Wedge ramp
    v0 = bm.verts.new((-width/2, 0, 0))
    v1 = bm.verts.new(( width/2, 0, 0))
    v2 = bm.verts.new(( width/2, -length, height))
    v3 = bm.verts.new((-width/2, -length, height))
    v4 = bm.verts.new((-width/2, -length, 0))
    v5 = bm.verts.new(( width/2, -length, 0))
    bm.faces.new((v0, v1, v2, v3))
    bm.faces.new((v3, v2, v5, v4))
    bm.faces.new((v0, v3, v4))
    bm.faces.new((v1, v5, v2))
    bm.faces.new((v0, v4, v5, v1))
    for f in bm.faces: f.material_index = 0
    
    # Curb stones along sides
    for sign_x in [-1, 1]:
        c = add_box(bm, material_index=0)
        for v in c:
            v.co.x = v.co.x * 0.18 + sign_x * (width/2.0 - 0.09)
            v.co.y = (v.co.y - 0.5) * length
            v.co.z = (v.co.z + 0.5) * (height + 0.2)
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_stone_platform(name, width=3.5, depth=3.5, height=1.0, stone_mat=None):
    """Raised stone terrace platform with flagstone top."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat: obj.data.materials.append(stone_mat)
    bm = bmesh.new()
    
    base = add_box(bm, material_index=0)
    for v in base:
        v.co.x *= width
        v.co.y *= depth
        v.co.z = (v.co.z + 0.5) * (height - 0.1)
        
    top = add_box(bm, material_index=0)
    for v in top:
        v.co.x *= (width + 0.2)
        v.co.y *= (depth + 0.2)
        v.co.z = (v.co.z + 0.5) * 0.12 + (height - 0.1)
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_arch_bridge(name, span=5.0, width=2.0, arch_height=1.8, stone_mat=None, foliage_mat=None):
    """Classic medieval arched stone bridge with parapets."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, foliage_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Bridge deck span
    num_segs = 12
    for i in range(num_segs):
        ang = radians(180 * i / num_segs)
        ang_next = radians(180 * (i + 1) / num_segs)
        x0 = -cos(ang) * span/2.0
        x1 = -cos(ang_next) * span/2.0
        z0 = sin(ang) * (arch_height * 0.7) + 0.5
        z1 = sin(ang_next) * (arch_height * 0.7) + 0.5
        
        # Deck segment
        seg = add_box(bm, material_index=0)
        for v in seg:
            v.co.x = v.co.x * (x1 - x0) + (x0 + x1)/2.0
            v.co.y *= width
            v.co.z = v.co.z * 0.25 + (z0 + z1)/2.0
            
    # Parapets along both edges
    for sign_y in [-1, 1]:
        par = add_box(bm, material_index=0)
        for v in par:
            v.co.x *= (span + 0.4)
            v.co.y = v.co.y * 0.18 + sign_y * (width/2.0 - 0.09)
            v.co.z = (v.co.z + 0.5) * (arch_height + 0.6)
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_stone_bridge(name, length=4.5, width=2.2, stone_mat=None, timber_mat=None):
    """Stone pier flat bridge with heavy timber deck and railings."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, timber_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Stone abutment piers at ends
    for sign_x in [-1, 1]:
        pier = add_box(bm, material_index=0)
        for v in pier:
            v.co.x = v.co.x * 0.9 + sign_x * (length/2.0 - 0.45)
            v.co.y *= (width + 0.2)
            v.co.z = (v.co.z + 0.5) * 1.5
            
    # Timber stringer beams
    deck = add_box(bm, material_index=1)
    for v in deck:
        v.co.x *= (length + 0.2)
        v.co.y *= width
        v.co.z = (v.co.z + 0.5) * 0.18 + 1.5
        
    # Wooden bridge railings
    for sign_y in [-1, 1]:
        rail = add_box(bm, material_index=1)
        for v in rail:
            v.co.x *= length
            v.co.y = v.co.y * 0.10 + sign_y * (width/2.0 - 0.08)
            v.co.z = (v.co.z + 0.5) * 0.85 + 1.68
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

# =============================================================
# GROUND & STREET TILES
# =============================================================
def create_ground_tile(name, tile_type="stone_road", size=3.0, height=0.15, mats=None):
    """Standardized 3m x 3m ground tile module for roads, plazas, decks, and terrain."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    
    mat_main = mats.get("M_Cobblestone" if "Cobblestone" in mats else "M_Stone_Base")
    mat_sub = mats.get("M_Timber_Dark")
    
    if tile_type == "stone_road":
        mat_main = mats.get("M_Stone_Base")
    elif tile_type == "dirt_road":
        mat_main = mats.get("M_Dirt_Road", mats.get("M_Stone_Base"))
    elif tile_type == "plaza_tile":
        mat_main = mats.get("M_Marble_Statue", mats.get("M_Stone_Base"))
    elif tile_type in ("wooden_deck", "dock_tile"):
        mat_main = mats.get("M_Wood_Planks")
        mat_sub = mats.get("M_Timber_Dark")
    elif tile_type == "grassy_ground":
        mat_main = mats.get("M_Foliage")
    elif tile_type == "cliff_edge":
        mat_main = mats.get("M_Stone_Base")
        
    for m in [mat_main, mat_sub]:
        if m: obj.data.materials.append(m)
        
    bm = bmesh.new()
    base = add_box(bm, material_index=0)
    for v in base:
        v.co.x *= size
        v.co.y *= size
        v.co.z = (v.co.z + 0.5) * height
        
    # Detail overlays
    if tile_type == "dock_tile" and mat_sub:
        bumper = add_box(bm, material_index=1)
        for v in bumper:
            v.co.x *= size
            v.co.y = (v.co.y - 0.5) * 0.18 - size/2.0 + 0.18
            v.co.z = (v.co.z + 0.5) * (height + 0.08)
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

# =============================================================
# FENCES & BARRIERS
# =============================================================
def create_stone_fence(name, length=3.0, height=1.0, stone_mat=None):
    """Low mortared fieldstone boundary fence."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat: obj.data.materials.append(stone_mat)
    bm = bmesh.new()
    wall = add_box(bm, material_index=0)
    for v in wall:
        v.co.x *= length
        v.co.y *= 0.40
        v.co.z = (v.co.z + 0.5) * height
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_iron_fence(name, length=2.8, height=1.2, iron_mat=None, stone_mat=None):
    """Wrought iron spear-point fence with stone pilasters."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [iron_mat, stone_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Left and right stone end pilasters
    for sign_x in [-1, 1]:
        p = add_box(bm, material_index=1)
        for v in p:
            v.co.x = v.co.x * 0.35 + sign_x * (length/2.0 - 0.18)
            v.co.y *= 0.35
            v.co.z = (v.co.z + 0.5) * (height + 0.15)
            
    # Horizontal iron rails
    for rz in [0.25, height - 0.15]:
        hr = add_box(bm, material_index=0)
        for v in hr:
            v.co.x *= (length - 0.7)
            v.co.y *= 0.04
            v.co.z = v.co.z * 0.04 + rz
            
    # Vertical iron pickets with spear tips
    num_pickets = 12
    pw = (length - 0.8) / (num_pickets - 1)
    for i in range(num_pickets):
        px = - (length - 0.8)/2.0 + i * pw
        picket = add_box(bm, material_index=0)
        for v in picket:
            v.co.x = v.co.x * 0.03 + px
            v.co.y *= 0.03
            v.co.z = (v.co.z + 0.5) * height
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.006, segments=2)
    return obj

def create_post_chain(name, length=2.8, stone_mat=None, iron_mat=None):
    """Twin stone posts connected by a heavy sagging iron chain."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    for sign_x in [-1, 1]:
        p = add_box(bm, material_index=0)
        for v in p:
            v.co.x = v.co.x * 0.28 + sign_x * (length/2.0 - 0.14)
            v.co.y *= 0.28
            v.co.z = (v.co.z + 0.5) * 0.95
            
    # Sagging chain links
    num_links = 14
    for i in range(num_links):
        t = i / (num_links - 1)
        cx = -length/2.0 + 0.2 + t * (length - 0.4)
        cz = 0.80 - 0.28 * sin(t * 3.14159)
        link = add_box(bm, material_index=1)
        for v in link:
            v.co.x = v.co.x * 0.08 + cx
            v.co.y *= 0.04
            v.co.z = v.co.z * 0.06 + cz
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_boxwood_hedge(name, length=3.0, height=1.1, width=0.6, hedge_mat=None):
    """Clipped green topiary boxwood hedge."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if hedge_mat: obj.data.materials.append(hedge_mat)
    bm = bmesh.new()
    h = add_box(bm, material_index=0)
    for v in h:
        v.co.x *= length
        v.co.y *= width
        v.co.z = (v.co.z + 0.5) * height
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.05, segments=3)
    return obj

def create_defensive_spikes(name, length=2.8, timber_mat=None):
    """Row of angled sharpened wooden palisade stakes."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat: obj.data.materials.append(timber_mat)
    bm = bmesh.new()
    
    num_spikes = 7
    sw = length / (num_spikes - 1)
    for i in range(num_spikes):
        sx = -length/2.0 + i * sw
        cone = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.08, radius2=0.01, depth=1.3)
        for v in cone['verts']:
            # Angle forward by 30 deg
            vy = v.co.y * cos(radians(30)) - v.co.z * sin(radians(30))
            vz = v.co.y * sin(radians(30)) + v.co.z * cos(radians(30))
            v.co.x += sx
            v.co.y = vy - 0.3
            v.co.z = vz + 0.55
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_small_gate(name, width=1.1, height=1.1, timber_mat=None, iron_mat=None):
    """Swinging wooden picket wicket gate with iron strap hinges."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    num_pickets = 5
    pw = (width - 0.1) / num_pickets
    for i in range(num_pickets):
        px = -width/2.0 + pw/2.0 + i * pw
        p = add_box(bm, material_index=0)
        for v in p:
            v.co.x = v.co.x * (pw * 0.85) + px
            v.co.y *= 0.05
            v.co.z = (v.co.z + 0.5) * height
            
    # Z-bracing timbers
    for rz in [0.25, height - 0.25]:
        cross = add_box(bm, material_index=0)
        for v in cross:
            v.co.x *= width
            v.co.y *= 0.06
            v.co.z = v.co.z * 0.08 + rz
            
    # Iron hinges
    for rz in [0.25, height - 0.25]:
        hinge = add_box(bm, material_index=1)
        for v in hinge:
            v.co.x = v.co.x * 0.35 - width/2.0 + 0.18
            v.co.y = v.co.y * 0.07 - 0.03
            v.co.z = v.co.z * 0.04 + rz
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

# =============================================================
# MARKET & STREET PROPS
# =============================================================
def create_handcart(name, timber_mat=None, iron_mat=None):
    """Two-wheel wooden handcart with 12-spoke wheels."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    cw, cl, ch = 1.0, 1.6, 0.45
    # Cart bed & slats
    bed = add_box(bm, material_index=0)
    for v in bed:
        v.co.x *= cw
        v.co.y = (v.co.y - 0.5) * cl
        v.co.z = (v.co.z + 0.5) * ch + 0.45
        
    # Iron axle
    axle = add_box(bm, material_index=1)
    for v in axle:
        v.co.x *= (cw + 0.35)
        v.co.y = v.co.y * 0.08 - cl * 0.55
        v.co.z = v.co.z * 0.08 + 0.45
        
    # Spoked Wheels
    wheel_r = 0.45
    for sign_x in [-1, 1]:
        wx = sign_x * (cw/2.0 + 0.12)
        wy = -cl * 0.55
        rim = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=wheel_r, radius2=wheel_r, depth=0.08)
        for v in rim['verts']:
            vx = v.co.z
            vy_c = v.co.y
            vz = v.co.x
            v.co.x = vx + wx
            v.co.y = vy_c + wy
            v.co.z = vz + 0.45
            
    # Handles
    for sign_x in [-1, 1]:
        h = add_box(bm, material_index=0)
        for v in h:
            v.co.x = v.co.x * 0.06 + sign_x * (cw/2.0 - 0.1)
            v.co.y = (v.co.y - 0.5) * 0.85
            v.co.z = v.co.z * 0.06 + 0.55
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_cargo_wagon(name, timber_mat=None, iron_mat=None):
    """Four-wheel heavy wooden cargo wagon with spoked wheels."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    ww, wl, wh = 1.3, 2.6, 0.60
    # Wagon box body
    box = add_box(bm, material_index=0)
    for v in box:
        v.co.x *= ww
        v.co.y *= wl
        v.co.z = (v.co.z + 0.5) * wh + 0.55
        
    # Chassis beams
    for sign_x in [-1, 1]:
        beam = add_box(bm, material_index=0)
        for v in beam:
            v.co.x = v.co.x * 0.12 + sign_x * (ww/2.0 - 0.15)
            v.co.y *= (wl + 0.4)
            v.co.z = v.co.z * 0.12 + 0.50
            
    # 4 Wheels (smaller front r=0.40, larger rear r=0.50)
    wheel_data = [
        (-wl/2.0 + 0.4, 0.40),  # Front
        ( wl/2.0 - 0.4, 0.50),  # Rear
    ]
    for wy, wr in wheel_data:
        for sign_x in [-1, 1]:
            wx = sign_x * (ww/2.0 + 0.14)
            rim = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=wr, radius2=wr, depth=0.10)
            for v in rim['verts']:
                vx = v.co.z
                vy_c = v.co.y
                vz = v.co.x
                v.co.x = vx + wx
                v.co.y = vy_c + wy
                v.co.z = vz + wr
                
    # Front hitch tongue
    tongue = add_box(bm, material_index=0)
    for v in tongue:
        v.co.x *= 0.10
        v.co.y = (v.co.y - 0.5) * 1.4 - wl/2.0
        v.co.z = v.co.z * 0.10 + 0.45
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_grain_sacks(name, num_sacks=3, straw_mat=None):
    """Stack of burlap grain/flour sacks tied with twine."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if straw_mat: obj.data.materials.append(straw_mat)
    bm = bmesh.new()
    
    sack_coords = [
        (-0.25, 0.0, 0.20, (0.60, 0.45, 0.35)),
        ( 0.25, 0.0, 0.20, (0.58, 0.46, 0.35)),
        ( 0.0,  0.0, 0.52, (0.55, 0.42, 0.32)),
    ]
    for sx, sy, sz, (dx, dy, dz) in sack_coords[:num_sacks]:
        s = add_box(bm, material_index=0)
        for v in s:
            v.co.x = v.co.x * dx + sx
            v.co.y = v.co.y * dy + sy
            v.co.z = v.co.z * dz + sz
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.06, segments=3)
    return obj

def create_multi_signpost(name, timber_mat=None, iron_mat=None):
    """Wooden road crossroads signpost with 3 pointing placards."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Post
    post = add_box(bm, material_index=0)
    for v in post:
        v.co.x *= 0.16
        v.co.y *= 0.16
        v.co.z = (v.co.z + 0.5) * 2.4
        
    # 3 Directional placards
    placard_data = [
        (2.1, radians(0),   "North"),
        (1.9, radians(75),  "East"),
        (1.7, radians(-60), "West"),
    ]
    for pz, rot, _ in placard_data:
        p = add_box(bm, material_index=0)
        for v in p:
            lx = (v.co.x + 0.5) * 0.75
            ly = v.co.y * 0.04
            lz = v.co.z * 0.16 + pz
            v.co.x = lx * cos(rot) - ly * sin(rot)
            v.co.y = lx * sin(rot) + ly * cos(rot)
            v.co.z = lz
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_notice_board(name, timber_mat=None, roof_mat=None, paper_mat=None):
    """Village wooden notice bulletin board with pinned parchment."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, roof_mat, paper_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Twin timber posts
    for sign_x in [-1, 1]:
        p = add_box(bm, material_index=0)
        for v in p:
            v.co.x = v.co.x * 0.14 + sign_x * 0.85
            v.co.y *= 0.14
            v.co.z = (v.co.z + 0.5) * 2.5
            
    # Cork bulletin board
    board = add_box(bm, material_index=0)
    for v in board:
        v.co.x *= 1.6
        v.co.y *= 0.08
        v.co.z = (v.co.z + 0.5) * 1.1 + 1.1
        
    # Pitched wooden roof hood
    hood = add_box(bm, material_index=1 if roof_mat else 0)
    for v in hood:
        v.co.x *= 1.9
        v.co.y *= 0.45
        v.co.z = (v.co.z + 0.5) * 0.15 + 2.45
        
    # Pinned paper notices
    for px, pz in [(-0.45, 1.7), (0.1, 1.8), (0.5, 1.5), (-0.2, 1.3)]:
        paper = add_box(bm, material_index=2 if paper_mat else 0)
        for v in paper:
            v.co.x = v.co.x * 0.28 + px
            v.co.y = v.co.y * 0.01 - 0.05
            v.co.z = v.co.z * 0.35 + pz
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

# =============================================================
# CIVIC & DECORATIVE PROPS
# =============================================================
def create_street_lamp(name, timber_mat=None, iron_mat=None, glow_mat=None):
    """Tall wooden street lamp post with curved iron bracket and glowing lantern."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat, glow_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Tall post
    post = add_box(bm, material_index=0)
    for v in post:
        v.co.x *= 0.15
        v.co.y *= 0.15
        v.co.z = (v.co.z + 0.5) * 3.2
        
    # Iron curved bracket arm
    arm = add_box(bm, material_index=1)
    for v in arm:
        v.co.x *= 0.06
        v.co.y = (v.co.y - 0.5) * 0.75
        v.co.z = (v.co.z + 0.5) * 0.06 + 3.10
        
    # Glowing lantern cage
    lantern = add_box(bm, material_index=2)
    for v in lantern:
        v.co.x *= 0.26
        v.co.y = v.co.y * 0.26 - 0.65
        v.co.z = (v.co.z - 0.5) * 0.45 + 3.05
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_village_well(name, stone_mat=None, timber_mat=None, roof_mat=None, water_mat=None, iron_mat=None):
    """Circular stone village well with gabled timber roof, windlass crank, rope, and bucket."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, timber_mat, roof_mat, water_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    r = 1.05
    # Stone well basin
    cyl = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r, depth=0.85)
    for v in cyl['verts']:
        v.co.z += 0.425
    for f in bm.faces: f.material_index = 0
    
    # Water surface inside well
    water = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r * 0.82, radius2=r * 0.82, depth=0.02)
    for v in water['verts']:
        v.co.z += 0.55
    for f in bm.faces:
        if any(v in set(water['verts']) for v in f.verts):
            f.material_index = 3 if water_mat else 0
            
    # Two timber support posts
    for sign_x in [-1, 1]:
        p = add_box(bm, material_index=1)
        for v in p:
            v.co.x = v.co.x * 0.14 + sign_x * (r - 0.10)
            v.co.y *= 0.14
            v.co.z = (v.co.z + 0.5) * 2.3
            
    # Windlass wooden cylinder drum
    drum = add_box(bm, material_index=1)
    for v in drum:
        v.co.x *= (r * 1.6)
        v.co.y *= 0.14
        v.co.z = v.co.z * 0.14 + 1.45
        
    # Gabled tiled canopy roof
    roof_w = r * 2.4
    roof_d = 1.4
    roof = add_box(bm, material_index=2 if roof_mat else 1)
    for v in roof:
        v.co.x *= roof_w
        v.co.y *= roof_d
        v.co.z = (v.co.z + 0.5) * 0.35 + 2.3
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_water_fountain(name, stone_mat=None, water_mat=None):
    """Tiered circular stone water fountain with splashing water."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, water_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Lower stone pool basin
    r1 = 1.6
    pool = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r1, radius2=r1, depth=0.60)
    for v in pool['verts']: v.co.z += 0.30
    for f in bm.faces: f.material_index = 0
    
    # Lower water surface
    w1 = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r1 * 0.85, radius2=r1 * 0.85, depth=0.02)
    for v in w1['verts']: v.co.z += 0.45
    for f in bm.faces:
        if any(v in set(w1['verts']) for v in f.verts): f.material_index = 1
        
    # Center fluted pedestal
    ped = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.35, radius2=0.25, depth=1.1)
    for v in ped['verts']: v.co.z += 0.85
    for f in bm.faces:
        if any(v in set(ped['verts']) for v in f.verts): f.material_index = 0
        
    # Upper stone basin
    r2 = 0.85
    bowl = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r2, radius2=r2 * 0.6, depth=0.35)
    for v in bowl['verts']: v.co.z += 1.55
    for f in bm.faces:
        if any(v in set(bowl['verts']) for v in f.verts): f.material_index = 0
        
    # Upper water dome
    w2 = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r2 * 0.8, radius2=r2 * 0.8, depth=0.02)
    for v in w2['verts']: v.co.z += 1.65
    for f in bm.faces:
        if any(v in set(w2['verts']) for v in f.verts): f.material_index = 1
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_knight_statue(name, stone_mat=None):
    """Carved stone knight statue on stepped pedestal."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat: obj.data.materials.append(stone_mat)
    bm = bmesh.new()
    
    # Stepped pedestal plinth
    plinth = add_box(bm, material_index=0)
    for v in plinth:
        v.co.x *= 1.1
        v.co.y *= 1.1
        v.co.z = (v.co.z + 0.5) * 0.40
        
    column = add_box(bm, material_index=0)
    for v in column:
        v.co.x *= 0.80
        v.co.y *= 0.80
        v.co.z = (v.co.z + 0.5) * 0.85 + 0.40
        
    # Knight torso & legs
    torso = add_box(bm, material_index=0)
    for v in torso:
        v.co.x *= 0.45
        v.co.y *= 0.35
        v.co.z = (v.co.z + 0.5) * 1.1 + 1.25
        
    # Helmet head
    head = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.20, radius2=0.15, depth=0.35)
    for v in head['verts']: v.co.z += 2.50
    for f in bm.faces:
        if any(v in set(head['verts']) for v in f.verts): f.material_index = 0
        
    # Shield on left arm
    shield = add_box(bm, material_index=0)
    for v in shield:
        v.co.x = v.co.x * 0.12 - 0.35
        v.co.y = (v.co.y - 0.5) * 0.45
        v.co.z = (v.co.z + 0.5) * 0.70 + 1.40
        
    # Upright broadsword
    sword = add_box(bm, material_index=0)
    for v in sword:
        v.co.x = v.co.x * 0.05 + 0.30
        v.co.y = (v.co.y - 0.5) * 0.10
        v.co.z = (v.co.z + 0.5) * 1.15 + 1.15
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

def create_flower_box_standalone(name, length=1.4, timber_mat=None, foliage_mat=None, flower_mat=None):
    """Free-standing wooden planter box with flowers."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, foliage_mat, flower_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Wooden trough
    trough = add_box(bm, material_index=0)
    for v in trough:
        v.co.x *= length
        v.co.y *= 0.45
        v.co.z = (v.co.z + 0.5) * 0.45
        
    # Foliage dome
    fol = add_box(bm, material_index=1)
    for v in fol:
        v.co.x *= (length - 0.1)
        v.co.y *= 0.35
        v.co.z = (v.co.z + 0.5) * 0.30 + 0.45
        
    # Colorful flowers
    for fx in [-0.4, -0.1, 0.2, 0.5]:
        fl = add_box(bm, material_index=2)
        for v in fl:
            v.co.x = v.co.x * 0.12 + fx
            v.co.y = v.co.y * 0.12
            v.co.z = (v.co.z + 0.5) * 0.12 + 0.70
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

# =============================================================
# DOCKS & WATERFRONT
# =============================================================
def create_dock_bollard(name, timber_mat=None, rope_mat=None):
    """Heavy timber wharf mooring piling post wrapped with rope."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, rope_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    post = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.22, radius2=0.22, depth=1.3)
    for v in post['verts']: v.co.z += 0.65
    for f in bm.faces: f.material_index = 0
    
    # Coiled rope ring
    rope = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.28, radius2=0.28, depth=0.18)
    for v in rope['verts']: v.co.z += 0.85
    for f in bm.faces:
        if any(v in set(rope['verts']) for v in f.verts): f.material_index = 1
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_dock_pier(name, length=4.0, width=1.8, height=1.4, timber_mat=None):
    """Stilted wooden wharf pier on piles with plank decking."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat: obj.data.materials.append(timber_mat)
    bm = bmesh.new()
    
    # 4 Wharf piles
    for px in [-length/2.0 + 0.5, length/2.0 - 0.5]:
        for py in [-width/2.0 + 0.25, width/2.0 - 0.25]:
            pile = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.14, radius2=0.14, depth=height)
            for v in pile['verts']:
                v.co.x += px
                v.co.y += py
                v.co.z += height/2.0
            for f in bm.faces: f.material_index = 0
            
    # Deck planks
    deck = add_box(bm, material_index=0)
    for v in deck:
        v.co.x *= length
        v.co.y *= width
        v.co.z = (v.co.z + 0.5) * 0.15 + height
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_rowboat(name, length=3.2, width=1.2, timber_mat=None, oar_mat=None):
    """Wooden clinker rowboat with ribs, seats, and oars."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, oar_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Hull bottom & sides
    hull = add_box(bm, material_index=0)
    for v in hull:
        v.co.x = (v.co.x) * (width * (1.0 - abs(v.co.y) * 0.45))
        v.co.y *= length
        v.co.z = (v.co.z + 0.5) * 0.55
        
    # Bench thwarts
    for by in [-0.6, 0.4]:
        bench = add_box(bm, material_index=0)
        for v in bench:
            v.co.x *= (width * 0.8)
            v.co.y = v.co.y * 0.22 + by
            v.co.z = (v.co.z + 0.5) * 0.08 + 0.35
            
    # Two wooden oars
    for sign_x in [-1, 1]:
        oar = add_box(bm, material_index=1 if oar_mat else 0)
        for v in oar:
            v.co.x = (v.co.x + sign_x * 0.5) * 1.8
            v.co.y = v.co.y * 0.06 - 0.2
            v.co.z = v.co.z * 0.06 + 0.45
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_sailboat(name, length=4.8, width=1.8, timber_mat=None, sail_mat=None, iron_mat=None):
    """Single-mast merchant boat with furled canvas sail and rigging."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, sail_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Boat hull
    hull = add_box(bm, material_index=0)
    for v in hull:
        v.co.x = (v.co.x) * (width * (1.0 - abs(v.co.y) * 0.5))
        v.co.y *= length
        v.co.z = (v.co.z + 0.5) * 0.75
        
    # Mast
    mast = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.10, radius2=0.07, depth=3.8)
    for v in mast['verts']:
        v.co.y -= 0.3
        v.co.z += 1.9 + 0.75
    for f in bm.faces:
        if any(v in set(mast['verts']) for v in f.verts): f.material_index = 0
        
    # Boom
    boom = add_box(bm, material_index=0)
    for v in boom:
        v.co.x *= 0.08
        v.co.y = (v.co.y + 0.5) * 2.2 - 0.3
        v.co.z = v.co.z * 0.08 + 1.6
        
    # Furled canvas sail
    sail = add_box(bm, material_index=1)
    for v in sail:
        v.co.x *= 0.22
        v.co.y = (v.co.y + 0.5) * 2.1 - 0.3
        v.co.z = (v.co.z + 0.5) * 0.28 + 1.62
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_dock_derrick_crane(name, timber_mat=None, iron_mat=None):
    """Heavy timber dock derrick crane with winch drum and cargo hook."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Vertical mast
    mast = add_box(bm, material_index=0)
    for v in mast:
        v.co.x *= 0.22
        v.co.y *= 0.22
        v.co.z = (v.co.z + 0.5) * 3.8
        
    # Diagonal jib boom extending outward
    add_diagonal_box(bm, Vector((0, 0, 1.2)), Vector((0, -2.4, 3.4)), width=0.18, depth=0.18, material_index=0)
    
    # Tie strut
    add_diagonal_box(bm, Vector((0, 0, 3.6)), Vector((0, -2.4, 3.4)), width=0.12, depth=0.12, material_index=0)
    
    # Winch drum and pulley
    drum = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.22, radius2=0.22, depth=0.35)
    for v in drum['verts']:
        v.co.z += 1.0
    for f in bm.faces:
        if any(v in set(drum['verts']) for v in f.verts): f.material_index = 1
        
    # Hanging tackle and hook
    hook = add_box(bm, material_index=1)
    for v in hook:
        v.co.x *= 0.08
        v.co.y = v.co.y * 0.08 - 2.4
        v.co.z = (v.co.z - 0.5) * 1.5 + 3.4
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_fishing_net_stack(name, rope_mat=None, cloth_mat=None):
    """Stacked rolls of brown hemp fishing nets and rope coils."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [rope_mat, cloth_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    net1 = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.45, radius2=0.45, depth=0.7)
    for v in net1['verts']:
        vx = v.co.z
        v.co.z = v.co.x + 0.35
        v.co.x = vx - 0.2
    for f in bm.faces: f.material_index = 0
    
    net2 = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.35, radius2=0.35, depth=0.6)
    for v in net2['verts']:
        vx = v.co.z
        v.co.z = v.co.x + 0.65
        v.co.x = vx + 0.1
    for f in bm.faces:
        if any(v in set(net2['verts']) for v in f.verts): f.material_index = 1
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.02, segments=2)
    return obj

def create_fish_barrel(name, plank_mat=None, iron_mat=None, fish_mat=None):
    """Open wooden barrel packed with silver fish."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [plank_mat, iron_mat, fish_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    r, h = 0.38, 0.85
    b = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r * 0.85, depth=h)
    for v in b['verts']: v.co.z += h/2.0
    for f in bm.faces: f.material_index = 0
    
    # Fish mound at top
    fish = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r * 0.82, radius2=r * 0.70, depth=0.18)
    for v in fish['verts']: v.co.z += h - 0.05
    for f in bm.faces:
        if any(v in set(fish['verts']) for v in f.verts): f.material_index = 2 if fish_mat else 0
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

# =============================================================
# NATURE & ENVIRONMENT
# =============================================================
def create_stylized_tree(name, tree_type="oak", trunk_mat=None, foliage_mat=None):
    """Stylized fantasy trees: multi-puff round oak, layered conical pine, bush, or dead tree."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [trunk_mat, foliage_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    if tree_type == "pine":
        # Tapered trunk
        trunk = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.22, radius2=0.08, depth=4.2)
        for v in trunk['verts']: v.co.z += 2.1
        for f in bm.faces: f.material_index = 0
        
        # 4 Layered conical pine skirts
        layers = [(1.8, 1.3, 1.4), (1.4, 2.3, 1.3), (1.0, 3.2, 1.1), (0.6, 3.9, 0.9)]
        for r_base, z_base, l_h in layers:
            cone = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=r_base, radius2=0.1, depth=l_h)
            for v in cone['verts']: v.co.z += z_base + l_h/2.0
            for f in bm.faces:
                if any(v in set(cone['verts']) for v in f.verts): f.material_index = 1
                
    elif tree_type == "oak":
        # Thick organic trunk
        trunk = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.35, radius2=0.22, depth=2.4)
        for v in trunk['verts']: v.co.z += 1.2
        for f in bm.faces: f.material_index = 0
        
        # 3 Spherical foliage puffs
        puffs = [
            (0.0,  0.0,  2.8, 1.4),
            (-0.6, 0.3,  3.2, 1.1),
            ( 0.5, -0.3, 3.3, 1.1),
        ]
        for px, py, pz, pr in puffs:
            sphere = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=pr)
            for v in sphere['verts']:
                v.co.x += px
                v.co.y += py
                v.co.z += pz
            for f in bm.faces:
                if any(v in set(sphere['verts']) for v in f.verts): f.material_index = 1
                
    elif tree_type == "dead":
        # Gnarled bare trunk and branches
        trunk = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.28, radius2=0.12, depth=3.2)
        for v in trunk['verts']: v.co.z += 1.6
        for f in bm.faces: f.material_index = 0
        # Branches
        add_diagonal_box(bm, Vector((0, 0, 2.2)), Vector((-0.9, 0.3, 3.4)), width=0.12, depth=0.12, material_index=0)
        add_diagonal_box(bm, Vector((0, 0, 2.4)), Vector(( 0.8, -0.4, 3.5)), width=0.12, depth=0.12, material_index=0)
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

def create_rock_boulder(name, size=(1.2, 0.9, 0.7), stone_mat=None):
    """Multifaceted stylized granite boulder."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat: obj.data.materials.append(stone_mat)
    bm = bmesh.new()
    
    ico = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    for v in ico['verts']:
        v.co.x *= size[0] * 0.5
        v.co.y *= size[1] * 0.5
        v.co.z = (v.co.z + 1.0) * size[2] * 0.5
    for f in bm.faces: f.material_index = 0
    
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.03, segments=2)
    return obj

def create_ruined_pillar(name, height=2.4, stone_mat=None, foliage_mat=None):
    """Broken ancient stone column with fluting and ivy base."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, foliage_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Base plinth
    base = add_box(bm, material_index=0)
    for v in base:
        v.co.x *= 0.85
        v.co.y *= 0.85
        v.co.z = (v.co.z + 0.5) * 0.35
        
    # Fluted column shaft (broken at top)
    col = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.35, radius2=0.35, depth=height - 0.35)
    for v in col['verts']:
        v.co.z += (height - 0.35)/2.0 + 0.35
    for f in bm.faces:
        if any(v in set(col['verts']) for v in f.verts): f.material_index = 0
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.015, segments=2)
    return obj

# =============================================================
# INTERIOR FURNITURE
# =============================================================
def create_medieval_bed(name, timber_mat=None, cloth_mat=None, sheet_mat=None):
    """Wooden frame bed with mattress, folded blanket, and pillows."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, cloth_mat, sheet_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    bw, bl = 1.4, 2.1
    # Frame
    frame = add_box(bm, material_index=0)
    for v in frame:
        v.co.x *= bw
        v.co.y *= bl
        v.co.z = (v.co.z + 0.5) * 0.35
        
    # Headboard
    head = add_box(bm, material_index=0)
    for v in head:
        v.co.x *= bw
        v.co.y = (v.co.y - 0.5) * 0.12 + bl/2.0
        v.co.z = (v.co.z + 0.5) * 0.95
        
    # Mattress
    mat = add_box(bm, material_index=2 if sheet_mat else 0)
    for v in mat:
        v.co.x *= (bw - 0.12)
        v.co.y *= (bl - 0.20)
        v.co.z = (v.co.z + 0.5) * 0.22 + 0.30
        
    # Folded blanket
    blanket = add_box(bm, material_index=1 if cloth_mat else 0)
    for v in blanket:
        v.co.x *= (bw - 0.10)
        v.co.y = (v.co.y - 0.5) * (bl * 0.6) - bl * 0.1
        v.co.z = (v.co.z + 0.5) * 0.08 + 0.52
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_dining_chair(name, timber_mat=None):
    """High-back wooden dining chair."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat: obj.data.materials.append(timber_mat)
    bm = bmesh.new()
    
    # 4 Legs
    for sx in [-0.20, 0.20]:
        for sy in [-0.20, 0.20]:
            leg = add_box(bm, material_index=0)
            for v in leg:
                v.co.x = v.co.x * 0.05 + sx
                v.co.y = v.co.y * 0.05 + sy
                v.co.z = (v.co.z + 0.5) * 0.50
                
    # Seat
    seat = add_box(bm, material_index=0)
    for v in seat:
        v.co.x *= 0.50
        v.co.y *= 0.50
        v.co.z = (v.co.z + 0.5) * 0.06 + 0.50
        
    # Tall backrest
    back = add_box(bm, material_index=0)
    for v in back:
        v.co.x *= 0.46
        v.co.y = (v.co.y + 0.5) * 0.05 + 0.20
        v.co.z = (v.co.z + 0.5) * 0.65 + 0.56
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.006, segments=2)
    return obj

def create_bookshelf_with_books(name, timber_mat=None, book_mat=None):
    """Three-tier wooden bookshelf packed with colorful book spines."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, book_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    w, d, h = 1.3, 0.40, 2.0
    # Left and right uprights
    for sign_x in [-1, 1]:
        side = add_box(bm, material_index=0)
        for v in side:
            v.co.x = v.co.x * 0.08 + sign_x * (w/2.0 - 0.04)
            v.co.y *= d
            v.co.z = (v.co.z + 0.5) * h
            
    # Shelves
    for sz in [0.05, 0.65, 1.25, 1.95]:
        shelf = add_box(bm, material_index=0)
        for v in shelf:
            v.co.x *= (w - 0.16)
            v.co.y *= d
            v.co.z = v.co.z * 0.06 + sz
            
    # Books on lower two shelves
    for sz in [0.08, 0.68]:
        for bx in [-0.4, -0.15, 0.1, 0.35]:
            book = add_box(bm, material_index=1 if book_mat else 0)
            for v in book:
                v.co.x = v.co.x * 0.18 + bx
                v.co.y = (v.co.y - 0.5) * (d * 0.8)
                v.co.z = (v.co.z + 0.5) * 0.42 + sz
                
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_hearth_fireplace(name, stone_mat=None, ember_mat=None, timber_mat=None):
    """Stone fireplace with arched opening, mantel shelf, and glowing fire coals."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, ember_mat, timber_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    fw, fd, fh = 1.6, 0.70, 1.5
    # Stone surround
    for sign_x in [-1, 1]:
        jamb = add_box(bm, material_index=0)
        for v in jamb:
            v.co.x = v.co.x * 0.35 + sign_x * (fw/2.0 - 0.175)
            v.co.y *= fd
            v.co.z = (v.co.z + 0.5) * fh
            
    # Lintel
    lintel = add_box(bm, material_index=0)
    for v in lintel:
        v.co.x *= (fw - 0.7)
        v.co.y *= fd
        v.co.z = (v.co.z + 0.5) * 0.40 + (fh - 0.40)
        
    # Timber mantel shelf
    mantel = add_box(bm, material_index=2 if timber_mat else 0)
    for v in mantel:
        v.co.x *= (fw + 0.25)
        v.co.y *= (fd + 0.15)
        v.co.z = (v.co.z + 0.5) * 0.12 + fh
        
    # Glowing coal bed
    embers = add_box(bm, material_index=1 if ember_mat else 0)
    for v in embers:
        v.co.x *= (fw * 0.5)
        v.co.y = v.co.y * (fd * 0.6) - 0.05
        v.co.z = (v.co.z + 0.5) * 0.15
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_carpet_rug(name, width=2.0, length=2.8, rug_mat=None):
    """Embroidered ornate patterned floor rug with fringes."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if rug_mat: obj.data.materials.append(rug_mat)
    bm = bmesh.new()
    rug = add_box(bm, material_index=0)
    for v in rug:
        v.co.x *= width
        v.co.y *= length
        v.co.z = (v.co.z + 0.5) * 0.02
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_treasure_chest(name, timber_mat=None, iron_mat=None, gold_mat=None):
    """Arched wooden treasure chest with iron bands and brass keyhole plate."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat, gold_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    cw, cd, ch = 0.9, 0.6, 0.5
    # Chest base box
    box = add_box(bm, material_index=0)
    for v in box:
        v.co.x *= cw
        v.co.y *= cd
        v.co.z = (v.co.z + 0.5) * ch
        
    # Arched lid
    lid = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=cd/2.0, radius2=cd/2.0, depth=cw)
    for v in lid['verts']:
        vx = v.co.z
        vy = v.co.y
        vz = v.co.x
        v.co.x = vx
        v.co.y = vy
        v.co.z = vz + ch
    for f in bm.faces:
        if any(v in set(lid['verts']) for v in f.verts): f.material_index = 0
        
    # Iron bands
    for sign_x in [-1, 1]:
        band = add_box(bm, material_index=1)
        for v in band:
            v.co.x = v.co.x * 0.06 + sign_x * (cw * 0.35)
            v.co.y *= (cd + 0.03)
            v.co.z = (v.co.z + 0.5) * (ch + 0.25)
            
    # Brass lock clasp
    clasp = add_box(bm, material_index=2 if gold_mat else 1)
    for v in clasp:
        v.co.x *= 0.12
        v.co.y = v.co.y * 0.04 - cd/2.0 - 0.02
        v.co.z = v.co.z * 0.15 + ch
        
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_wooden_ladder(name, length=2.8, timber_mat=None):
    """Utility wooden ladder with rungs."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat: obj.data.materials.append(timber_mat)
    bm = bmesh.new()
    
    lw = 0.50
    # Side rails
    for sign_x in [-1, 1]:
        rail = add_box(bm, material_index=0)
        for v in rail:
            v.co.x = v.co.x * 0.06 + sign_x * (lw/2.0 - 0.03)
            v.co.y *= 0.08
            v.co.z = (v.co.z + 0.5) * length
            
    # Rungs
    num_rungs = 8
    rw = length / (num_rungs + 1)
    for i in range(1, num_rungs + 1):
        rung = add_box(bm, material_index=0)
        for v in rung:
            v.co.x *= (lw - 0.06)
            v.co.y *= 0.04
            v.co.z = v.co.z * 0.04 + i * rw
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.006, segments=2)
    return obj

def create_interior_stairs(name, width=1.0, height=2.4, timber_mat=None):
    """Open-riser interior timber staircase."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat: obj.data.materials.append(timber_mat)
    bm = bmesh.new()
    
    num_steps = 10
    sh = height / num_steps
    sd = 0.28
    for i in range(num_steps):
        tread = add_box(bm, material_index=0)
        for v in tread:
            v.co.x *= width
            v.co.y = v.co.y * (sd + 0.04) - (i * sd)
            v.co.z = v.co.z * 0.05 + (i * sh) + sh
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

# =============================================================
# ADDITIONAL MODULAR PROPS & DECORATIONS
# =============================================================
def assign_mat_to_verts(bm, verts, mat_idx):
    for v in verts:
        for f in v.link_faces:
            f.material_index = mat_idx

def create_railing(name, length=2.8, height=0.9, timber_mat=None, iron_mat=None):
    """Balustrade railing with timber handrail and vertical spindles."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # End posts
    pw = 0.12
    for sign_x in [-1, 1]:
        post = add_box(bm, material_index=0)
        for v in post:
            v.co.x = v.co.x * pw + sign_x * (length/2.0 - pw/2.0)
            v.co.y *= pw
            v.co.z = (v.co.z + 0.5) * (height + 0.08)
            
    # Top handrail
    top = add_box(bm, material_index=0)
    for v in top:
        v.co.x *= length
        v.co.y *= (pw + 0.02)
        v.co.z = v.co.z * 0.08 + height
        
    # Bottom runner rail
    bot = add_box(bm, material_index=0)
    for v in bot:
        v.co.x *= length
        v.co.y *= (pw - 0.02)
        v.co.z = v.co.z * 0.06 + 0.15
        
    # Vertical spindles / balusters
    num_spindles = 8
    sw = (length - 0.3) / (num_spindles + 1)
    for i in range(1, num_spindles + 1):
        sx = -length/2.0 + 0.15 + i * sw
        sp = add_box(bm, material_index=1 if iron_mat else 0)
        for v in sp:
            v.co.x = v.co.x * 0.04 + sx
            v.co.y *= 0.04
            v.co.z = (v.co.z + 0.5) * (height - 0.22) + 0.18
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_wall_lantern(name, timber_mat=None, iron_mat=None, glow_mat=None):
    """Wall-mounted iron bracket lantern with glowing amber light."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [iron_mat, timber_mat, glow_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Wall mounting plate
    plate = add_box(bm, material_index=0)
    for v in plate:
        v.co.x *= 0.15
        v.co.y = v.co.y * 0.03 + 0.015
        v.co.z = (v.co.z + 0.5) * 0.45 + 0.8
        
    # Curved iron bracket arm
    arm = add_box(bm, material_index=0)
    for v in arm:
        v.co.x *= 0.04
        v.co.y = (v.co.y - 0.5) * 0.55
        v.co.z = v.co.z * 0.04 + 1.2
        
    # Strut
    add_diagonal_box(bm, Vector((0, 0, 0.9)), Vector((0, -0.4, 1.2)), width=0.03, depth=0.03, material_index=0)
    
    # Lantern frame & cap
    ly = -0.45
    cap = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.18, radius2=0.02, depth=0.15)
    for v in cap['verts']:
        v.co.y += ly
        v.co.z += 1.25
    for f in bm.faces:
        if f.material_index != 0: f.material_index = 0
        
    # Glowing glass core
    glass = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.12, radius2=0.10, depth=0.25)
    for v in glass['verts']:
        v.co.y += ly
        v.co.z += 1.05
    assign_mat_to_verts(bm, glass['verts'], 2 if glow_mat else 0)
        
    # Iron cage struts
    for i in range(6):
        ang = radians(i * 60)
        strut = add_box(bm, material_index=0)
        for v in strut:
            vx = v.co.x * 0.02 + cos(ang) * 0.13
            vy = v.co.y * 0.02 + sin(ang) * 0.13 + ly
            v.co.x = vx
            v.co.y = vy
            v.co.z = (v.co.z + 0.5) * 0.26 + 0.92
            
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_hanging_lantern(name, iron_mat=None, glow_mat=None):
    """Tall ornate iron lamp post with arched gooseneck and hanging lantern."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [iron_mat, glow_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Cast iron base
    base = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.25, radius2=0.08, depth=0.35)
    for v in base['verts']:
        v.co.z += 0.175
        
    # Slender vertical pole
    pole = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.06, radius2=0.045, depth=2.4)
    for v in pole['verts']:
        v.co.z += 1.45
        
    # Arched gooseneck top arm
    arch_pts = [
        Vector((0, 0, 2.65)),
        Vector((0, -0.15, 2.85)),
        Vector((0, -0.35, 2.95)),
        Vector((0, -0.55, 2.85)),
        Vector((0, -0.65, 2.65))
    ]
    for idx in range(len(arch_pts) - 1):
        add_diagonal_box(bm, arch_pts[idx], arch_pts[idx+1], width=0.04, depth=0.04, material_index=0)
        
    # Small chain link
    add_diagonal_box(bm, Vector((0, -0.65, 2.65)), Vector((0, -0.65, 2.45)), width=0.02, depth=0.02, material_index=0)
    
    # Hanging lantern
    ly = -0.65
    cap = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.18, radius2=0.02, depth=0.14)
    for v in cap['verts']:
        v.co.y += ly
        v.co.z += 2.40
        
    glass = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.13, radius2=0.10, depth=0.26)
    for v in glass['verts']:
        v.co.y += ly
        v.co.z += 2.22
    assign_mat_to_verts(bm, glass['verts'], 1 if glow_mat else 0)
        
    # Bottom drop finial
    finial = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.08, radius2=0.01, depth=0.10)
    for v in finial['verts']:
        v.co.y += ly
        v.co.z += 2.05
        
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_planter(name, stone_mat=None, flower_mat=None, foliage_mat=None):
    """Carved stone floral planter urn with blooming flowers."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, foliage_mat, flower_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Stone urn body
    urn_w = 0.85
    urn_h = 0.65
    urn = add_box(bm, material_index=0)
    for v in urn:
        v.co.x *= (urn_w if v.co.z > 0 else urn_w * 0.75)
        v.co.y *= (urn_w if v.co.z > 0 else urn_w * 0.75)
        v.co.z = (v.co.z + 0.5) * urn_h
        
    # Rim lip
    rim = add_box(bm, material_index=0)
    for v in rim:
        v.co.x *= (urn_w + 0.12)
        v.co.y *= (urn_w + 0.12)
        v.co.z = v.co.z * 0.10 + urn_h
        
    # Foliage dome
    fol = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.45)
    for v in fol['verts']:
        v.co.z = v.co.z * 0.65 + urn_h + 0.25
    assign_mat_to_verts(bm, fol['verts'], 1 if foliage_mat else 0)
        
    # Flower blooms
    for fx, fy, fz in [(-0.25, -0.15, urn_h + 0.35), (0.22, -0.18, urn_h + 0.40), (0.0, 0.22, urn_h + 0.38), (0.15, 0.15, urn_h + 0.50)]:
        fl = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.10)
        for v in fl['verts']:
            v.co.x += fx
            v.co.y += fy
            v.co.z += fz
        assign_mat_to_verts(bm, fl['verts'], 2 if flower_mat else 0)
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_bush(name, foliage_mat=None, flower_mat=None):
    """Lush stylized foliage shrub with flower berry highlights."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [foliage_mat, flower_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # 5 overlapping foliage spheres for natural stylized silhouette
    clusters = [
        (0.0, 0.0, 0.45, 0.55),
        (-0.35, -0.20, 0.35, 0.42),
        (0.35, -0.18, 0.38, 0.44),
        (-0.15, 0.32, 0.40, 0.45),
        (0.25, 0.28, 0.32, 0.38),
    ]
    for cx, cy, cz, rad in clusters:
        ico = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad)
        for v in ico['verts']:
            v.co.x = v.co.x * 1.1 + cx
            v.co.y = v.co.y * 1.05 + cy
            v.co.z = v.co.z * 0.85 + cz
        assign_mat_to_verts(bm, ico['verts'], 0)
            
    # Red/orange berry flower specks
    if flower_mat:
        berries = [
            (-0.3, -0.4, 0.4), (0.35, -0.3, 0.45), (0.0, -0.48, 0.5),
            (-0.4, 0.1, 0.55), (0.42, 0.1, 0.42), (0.1, 0.45, 0.48)
        ]
        for bx, by, bz in berries:
            b_ico = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.065)
            for v in b_ico['verts']:
                v.co.x += bx
                v.co.y += by
                v.co.z += bz
            assign_mat_to_verts(bm, b_ico['verts'], 1)
                
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_dock_platform(name, width=2.6, depth=2.6, height=1.3, timber_mat=None, plank_mat=None):
    """Heavy timber dock platform on pilings with cross-ties and plank deck."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, plank_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # 4 corner timber pilings
    pw = 0.22
    for sign_x in [-1, 1]:
        for sign_y in [-1, 1]:
            px = sign_x * (width/2.0 - pw/2.0)
            py = sign_y * (depth/2.0 - pw/2.0)
            pile = add_box(bm, material_index=0)
            for v in pile:
                v.co.x = v.co.x * pw + px
                v.co.y = v.co.y * pw + py
                v.co.z = (v.co.z + 0.5) * (height + 0.25)
                
    # Horizontal bearer beams
    for sign_y in [-1, 1]:
        by = sign_y * (depth/2.0 - pw/2.0)
        bm_beam = add_box(bm, material_index=0)
        for v in bm_beam:
            v.co.x *= (width - pw)
            v.co.y = v.co.y * 0.16 + by
            v.co.z = v.co.z * 0.18 + height - 0.12
            
    # Deck planks
    num_planks = 7
    pw_plank = width / num_planks
    for i in range(num_planks):
        px = -width/2.0 + pw_plank/2.0 + i * pw_plank
        plank = add_box(bm, material_index=1 if plank_mat else 0)
        for v in plank:
            v.co.x = v.co.x * (pw_plank - 0.02) + px
            v.co.y *= (depth + 0.15)
            v.co.z = v.co.z * 0.07 + height
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.01, segments=2)
    return obj

def create_clothesline_standalone(name, span=3.0, timber_mat=None, cloth_white=None, cloth_blue=None, cloth_red=None):
    """Standalone outdoor clothesline between two forked wooden posts with hanging laundry."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, cloth_white, cloth_blue, cloth_red]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # 2 Wooden posts with T-bars
    post_h = 1.9
    for sign_x in [-1, 1]:
        px = sign_x * (span/2.0)
        post = add_box(bm, material_index=0)
        for v in post:
            v.co.x = v.co.x * 0.10 + px
            v.co.y *= 0.10
            v.co.z = (v.co.z + 0.5) * post_h
            
        tbar = add_box(bm, material_index=0)
        for v in tbar:
            v.co.x = v.co.x * 0.08 + px
            v.co.y *= 0.70
            v.co.z = v.co.z * 0.08 + post_h
            
    # Rope line
    p1 = Vector((-span/2.0, 0, post_h))
    p2 = Vector(( span/2.0, 0, post_h))
    num_segs = 12
    sag = 0.16
    diff = p2 - p1
    prev_pt = p1
    for i in range(1, num_segs + 1):
        t = i / num_segs
        curr_pt = p1 + diff * t
        curr_pt.z -= 4.0 * sag * t * (1.0 - t)
        add_diagonal_box(bm, prev_pt, curr_pt, width=0.02, depth=0.02, material_index=0)
        prev_pt = curr_pt
        
    # Clothes items
    clothes = [
        (0.24, 1, 0.45, 0.55),
        (0.50, 2, 0.38, 0.65),
        (0.76, 3, 0.42, 0.48),
    ]
    for frac, mat_idx, cw, ch in clothes:
        pt = p1 + diff * frac
        pt.z -= 4.0 * sag * frac * (1.0 - frac)
        item = add_box(bm, material_index=mat_idx)
        for v in item:
            v.co.x = v.co.x * cw + pt.x
            v.co.y = v.co.y * 0.02 + pt.y
            v.co.z = (v.co.z - 0.5) * ch + pt.z
            
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_flags_standalone(name, timber_mat=None, banner_mat=None, iron_mat=None):
    """Heraldic banner flag on a wooden pole with wall bracket."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, banner_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Slanted flagpole
    pole_len = 2.4
    ang = radians(30)
    p0 = Vector((0, 0, 0.5))
    p1 = Vector((0, -pole_len * cos(ang), 0.5 + pole_len * sin(ang)))
    add_diagonal_box(bm, p0, p1, width=0.06, depth=0.06, material_index=0)
    
    # Iron wall base mount
    mount = add_box(bm, material_index=2 if iron_mat else 0)
    for v in mount:
        v.co.x *= 0.16
        v.co.y *= 0.16
        v.co.z = v.co.z * 0.20 + 0.5
        
    # Cloth flag
    flag = add_box(bm, material_index=1 if banner_mat else 0)
    for v in flag:
        v.co.x *= 0.02
        v.co.y = (v.co.y - 0.5) * 1.1 + p1.y + 0.3
        v.co.z = (v.co.z - 0.5) * 0.7 + p1.z - 0.15
        
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_awning_standalone(name, width=2.4, depth=1.4, stripe_mat=None, timber_mat=None):
    """Cantilevered striped shop awning on diagonal timber wall struts."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stripe_mat, timber_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Slanted canopy
    ang = radians(22)
    canopy = add_box(bm, material_index=0)
    for v in canopy:
        v.co.x *= width
        vy = (v.co.y - 0.5) * depth
        vz = v.co.z * 0.05
        v.co.y = vy * cos(ang) - vz * sin(ang)
        v.co.z = vy * sin(ang) + vz * cos(ang) + 1.8
        
    # Scalloped front valance
    valance = add_box(bm, material_index=0)
    for v in valance:
        v.co.x *= width
        v.co.y = v.co.y * 0.03 - depth * cos(ang)
        v.co.z = (v.co.z - 0.5) * 0.25 + 1.8 - depth * sin(ang)
        
    # Diagonal timber struts
    for sign_x in [-1, 1]:
        sx = sign_x * (width/2.0 - 0.15)
        p_wall = Vector((sx, 0, 1.2))
        p_front = Vector((sx, -depth * cos(ang) * 0.9, 1.8 - depth * sin(ang) * 0.9))
        add_diagonal_box(bm, p_wall, p_front, width=0.08, depth=0.08, material_index=1 if timber_mat else 0)
        
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_chimney_smoke_standalone(name, stone_mat=None, smoke_mat=None):
    """Stone chimney top with billowing stylized smoke cloud puffs."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, smoke_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Chimney stack
    stack = add_box(bm, material_index=0)
    for v in stack:
        v.co.x *= 0.75
        v.co.y *= 0.75
        v.co.z = (v.co.z + 0.5) * 1.4
        
    # Cap rim
    cap = add_box(bm, material_index=0)
    for v in cap:
        v.co.x *= 0.88
        v.co.y *= 0.88
        v.co.z = v.co.z * 0.12 + 1.4
        
    # Smoke cloud puffs drifting upward
    puffs = [
        (0.0, 0.0, 1.65, 0.22),
        (0.12, -0.08, 1.95, 0.32),
        (0.28, -0.15, 2.35, 0.42),
        (0.48, -0.22, 2.80, 0.52),
    ]
    for px, py, pz, rad in puffs:
        ico = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad)
        for v in ico['verts']:
            v.co.x += px
            v.co.y += py
            v.co.z += pz
        assign_mat_to_verts(bm, ico['verts'], 1 if smoke_mat else 0)
            
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_table(name, width=1.8, depth=1.0, height=0.85, timber_mat=None):
    """Rustic tavern wooden dining table with turned legs and stretcher."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if timber_mat: obj.data.materials.append(timber_mat)
    bm = bmesh.new()
    
    # Tabletop slab
    top = add_box(bm, material_index=0)
    for v in top:
        v.co.x *= width
        v.co.y *= depth
        v.co.z = v.co.z * 0.08 + height - 0.04
        
    # 4 legs
    lw = 0.10
    lx = width/2.0 - 0.16
    ly = depth/2.0 - 0.16
    for sign_x in [-1, 1]:
        for sign_y in [-1, 1]:
            leg = add_box(bm, material_index=0)
            for v in leg:
                v.co.x = v.co.x * lw + sign_x * lx
                v.co.y = v.co.y * lw + sign_y * ly
                v.co.z = (v.co.z + 0.5) * (height - 0.08)
                
    # Lower H-stretcher
    str_x = add_box(bm, material_index=0)
    for v in str_x:
        v.co.x *= (width - 0.32)
        v.co.y *= 0.06
        v.co.z = v.co.z * 0.06 + 0.18
        
    for sign_x in [-1, 1]:
        str_y = add_box(bm, material_index=0)
        for v in str_y:
            v.co.x = v.co.x * 0.06 + sign_x * lx
            v.co.y *= (depth - 0.32)
            v.co.z = v.co.z * 0.06 + 0.18
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_table_set(name, timber_mat=None, iron_mat=None):
    """Tavern dining table set complete with two chairs, beer mugs, and bowls."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # 1. Central table
    w, d, h = 1.6, 0.9, 0.82
    top = add_box(bm, material_index=0)
    for v in top:
        v.co.x *= w
        v.co.y *= d
        v.co.z = v.co.z * 0.08 + h - 0.04
        
    lx = w/2.0 - 0.14
    ly = d/2.0 - 0.14
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            leg = add_box(bm, material_index=0)
            for v in leg:
                v.co.x = v.co.x * 0.09 + sx * lx
                v.co.y = v.co.y * 0.09 + sy * ly
                v.co.z = (v.co.z + 0.5) * (h - 0.08)
                
    # 2. Chairs on left and right
    for sign_x in [-1, 1]:
        cx = sign_x * (w/2.0 + 0.35)
        seat = add_box(bm, material_index=0)
        for v in seat:
            v.co.x = v.co.x * 0.45 + cx
            v.co.y *= 0.45
            v.co.z = v.co.z * 0.05 + 0.48
        cback = add_box(bm, material_index=0)
        for v in cback:
            v.co.x = v.co.x * 0.05 + cx + sign_x * 0.20
            v.co.y *= 0.45
            v.co.z = (v.co.z + 0.5) * 0.55 + 0.48
        for csx in [-1, 1]:
            for csy in [-1, 1]:
                cl = add_box(bm, material_index=0)
                for v in cl:
                    v.co.x = v.co.x * 0.05 + cx + csx * 0.18
                    v.co.y = v.co.y * 0.05 + csy * 0.18
                    v.co.z = (v.co.z + 0.5) * 0.48
                    
    # 3. Pewter/Clay Mugs on table
    for mx, my in [(-0.35, -0.15), (0.35, 0.15)]:
        mug = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.07, radius2=0.06, depth=0.14)
        for v in mug['verts']:
            v.co.x += mx
            v.co.y += my
            v.co.z += h + 0.07
        assign_mat_to_verts(bm, mug['verts'], 1 if iron_mat else 0)
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_curtain(name, width=1.4, height=2.2, cloth_mat=None, rod_mat=None):
    """Interior gathered fabric curtains with brass rod, rings, and tiebacks."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [cloth_mat, rod_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Curtain rod
    rod = add_box(bm, material_index=1 if rod_mat else 0)
    for v in rod:
        v.co.x *= (width + 0.25)
        v.co.y *= 0.04
        v.co.z = v.co.z * 0.04 + height
        
    # Finials
    for sx in [-1, 1]:
        fin = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.06)
        for v in fin['verts']:
            v.co.x += sx * (width/2.0 + 0.14)
            v.co.z += height
        assign_mat_to_verts(bm, fin['verts'], 1 if rod_mat else 0)
            
    # Draped curtains pulled to sides
    cw = width * 0.42
    for sx in [-1, 1]:
        cx = sx * (width/2.0 - cw/2.0)
        drape = add_box(bm, material_index=0)
        for v in drape:
            cinch = (0.70 if 0.3 < (v.co.z + 0.5) < 0.6 else 1.0)
            v.co.x = v.co.x * cw * cinch + cx
            v.co.y = v.co.y * 0.12 * cinch
            v.co.z = (v.co.z + 0.5) * height
            
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_shelf(name, width=1.2, height=1.8, depth=0.4, timber_mat=None, pottery_mat=None):
    """Interior display shelving unit with potion bottles, pottery, and books."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, pottery_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Side panels
    for sx in [-1, 1]:
        side = add_box(bm, material_index=0)
        for v in side:
            v.co.x = v.co.x * 0.05 + sx * (width/2.0 - 0.025)
            v.co.y *= depth
            v.co.z = (v.co.z + 0.5) * height
            
    # Back panel
    back = add_box(bm, material_index=0)
    for v in back:
        v.co.x *= width
        v.co.y = v.co.y * 0.03 + depth/2.0 - 0.015
        v.co.z = (v.co.z + 0.5) * height
        
    # Shelves
    num_shelves = 4
    sh_step = height / (num_shelves + 1)
    for i in range(1, num_shelves + 1):
        sz = i * sh_step
        shelf = add_box(bm, material_index=0)
        for v in shelf:
            v.co.x *= (width - 0.05)
            v.co.y *= (depth - 0.03)
            v.co.z = v.co.z * 0.04 + sz
            
    # Pottery jars on shelf
    sz2 = 2 * sh_step
    for jx in [-0.3, 0.0, 0.25]:
        pot = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.08, radius2=0.05, depth=0.18)
        for v in pot['verts']:
            v.co.x += jx
            v.co.y += 0.0
            v.co.z += sz2 + 0.09
        assign_mat_to_verts(bm, pot['verts'], 1 if pottery_mat else 0)
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_grass_patch(name, radius=1.0, grass_mat=None, flower_mat=None):
    """Lush stylized grassy ground mound with blade tufts and flowers."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [grass_mat, flower_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    # Ground mound
    base = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius)
    for v in base['verts']:
        v.co.z = max(0.0, v.co.z * 0.35)
    assign_mat_to_verts(bm, base['verts'], 0)
        
    # 3D Grass blade tufts
    tuft_coords = [
        (-0.4, -0.3), (0.35, -0.2), (-0.1, 0.35), (0.4, 0.25), (0.0, -0.05)
    ]
    for tx, ty in tuft_coords:
        for b_i in range(4):
            ang = radians(b_i * 90 + 20)
            blade = add_box(bm, material_index=0)
            for v in blade:
                vx = v.co.x * 0.04
                vy = (v.co.y - 0.5) * 0.18
                v.co.x = vx * cos(ang) - vy * sin(ang) + tx
                v.co.y = vx * sin(ang) + vy * cos(ang) + ty
                v.co.z = (v.co.z + 0.5) * 0.35 + 0.15
                
    # Flowers
    if flower_mat:
        for fx, fy, fz in [(-0.25, 0.15, 0.28), (0.2, -0.15, 0.30), (-0.1, -0.3, 0.22), (0.35, 0.1, 0.25)]:
            fl = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.05)
            for v in fl['verts']:
                v.co.x += fx
                v.co.y += fy
                v.co.z += fz
            assign_mat_to_verts(bm, fl['verts'], 1)
                
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_flowers(name, radius=0.8, foliage_mat=None, flower_mat=None):
    """Vibrant wildflower cluster with foliage stems and colorful blooms."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [foliage_mat, flower_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    for i in range(5):
        ang = radians(i * 72)
        r = 0.35
        fx = cos(ang) * r
        fy = sin(ang) * r
        stem = add_box(bm, material_index=0)
        for v in stem:
            v.co.x = v.co.x * 0.05 + fx
            v.co.y = v.co.y * 0.05 + fy
            v.co.z = (v.co.z + 0.5) * 0.45
            
        bloom = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.10)
        for v in bloom['verts']:
            v.co.x += fx
            v.co.y += fy
            v.co.z += 0.48
        assign_mat_to_verts(bm, bloom['verts'], 1 if flower_mat else 0)
            
    c_bloom = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.12)
    for v in c_bloom['verts']:
        v.co.z += 0.55
    assign_mat_to_verts(bm, c_bloom['verts'], 1 if flower_mat else 0)
        
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_tree_group(name, trunk_mat=None, foliage_mat=None):
    """Scenic cluster of three stylized trees on a grassy mound."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [trunk_mat, foliage_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    base = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.8)
    for v in base['verts']:
        v.co.z = max(0.0, v.co.z * 0.25)
    assign_mat_to_verts(bm, base['verts'], 1 if foliage_mat else 0)
        
    t1_cyl = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.16, radius2=0.10, depth=2.8)
    for v in t1_cyl['verts']:
        v.co.x -= 0.6
        v.co.y -= 0.3
        v.co.z += 1.4
    assign_mat_to_verts(bm, t1_cyl['verts'], 0)
    for cz, cr, ch in [(1.8, 0.9, 1.1), (2.4, 0.7, 1.0), (3.0, 0.5, 0.9)]:
        cone = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=cr, radius2=0.02, depth=ch)
        for v in cone['verts']:
            v.co.x -= 0.6
            v.co.y -= 0.3
            v.co.z += cz
        assign_mat_to_verts(bm, cone['verts'], 1 if foliage_mat else 0)
        
    t2_cyl = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.14, radius2=0.09, depth=2.2)
    for v in t2_cyl['verts']:
        v.co.x += 0.7
        v.co.y -= 0.2
        v.co.z += 1.1
    assign_mat_to_verts(bm, t2_cyl['verts'], 0)
    for cz, cr, ch in [(1.4, 0.75, 0.9), (1.9, 0.55, 0.8), (2.4, 0.38, 0.7)]:
        cone = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=cr, radius2=0.02, depth=ch)
        for v in cone['verts']:
            v.co.x += 0.7
            v.co.y -= 0.2
            v.co.z += cz
        assign_mat_to_verts(bm, cone['verts'], 1 if foliage_mat else 0)
        
    t3_cyl = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.12, radius2=0.08, depth=1.6)
    for v in t3_cyl['verts']:
        v.co.y += 0.8
        v.co.z += 0.8
    assign_mat_to_verts(bm, t3_cyl['verts'], 0)
    ico = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.65)
    for v in ico['verts']:
        v.co.y += 0.8
        v.co.z += 1.8
    assign_mat_to_verts(bm, ico['verts'], 1 if foliage_mat else 0)
    
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_vines(name, height=2.4, foliage_mat=None):
    """Hanging vine tendrils with leaves cascading down."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if foliage_mat: obj.data.materials.append(foliage_mat)
    bm = bmesh.new()
    
    strands = [-0.45, -0.15, 0.15, 0.45]
    for vx in strands:
        vh = height * 0.85
        strand = add_box(bm, material_index=0)
        for v in strand:
            v.co.x = v.co.x * 0.04 + vx
            v.co.y *= 0.04
            v.co.z = (v.co.z - 0.5) * vh + height
            
        num_leaves = 6
        for li in range(num_leaves):
            lz = height - (li + 1) * (vh / (num_leaves + 1))
            leaf = add_box(bm, material_index=0)
            for v in leaf:
                v.co.x = v.co.x * 0.12 + vx + (0.04 if li % 2 == 0 else -0.04)
                v.co.y *= 0.08
                v.co.z = v.co.z * 0.08 + lz
                
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_ivy_wall(name, width=2.4, height=2.4, stone_mat=None, foliage_mat=None):
    """Stone wall section covered in climbing ivy foliage."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [stone_mat, foliage_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    wall = add_box(bm, material_index=0)
    for v in wall:
        v.co.x *= width
        v.co.y *= 0.40
        v.co.z = (v.co.z + 0.5) * height
        
    ivy_patches = [
        (-0.7, -0.21, 0.9, 0.65, 1.2),
        (0.2, -0.21, 1.2, 0.85, 1.6),
        (0.8, -0.21, 0.7, 0.55, 1.0),
    ]
    for ix, iy, iz, iw, ih in ivy_patches:
        patch = add_box(bm, material_index=1 if foliage_mat else 0)
        for v in patch:
            v.co.x = v.co.x * iw + ix
            v.co.y = v.co.y * 0.06 + iy
            v.co.z = v.co.z * ih + iz
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.012, segments=2)
    return obj

def create_rock_small(name, stone_mat=None):
    """Small cluster of fieldstones and pebbles."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    if stone_mat: obj.data.materials.append(stone_mat)
    bm = bmesh.new()
    
    pebbles = [
        (0.0, 0.0, 0.18, 0.28),
        (-0.35, -0.15, 0.12, 0.18),
        (0.30, 0.18, 0.14, 0.22),
    ]
    for px, py, pz, rad in pebbles:
        ico = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rad)
        for v in ico['verts']:
            v.co.x = v.co.x * 1.2 + px
            v.co.y = v.co.y * 0.9 + py
            v.co.z = max(0.0, v.co.z * 0.75 + pz)
        assign_mat_to_verts(bm, ico['verts'], 0)
            
    bm.to_mesh(mesh)
    bm.free()
    return obj

def create_crate_stack(name, timber_mat=None, iron_mat=None):
    """Pyramid stack of wooden cargo crates."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [timber_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    cs = 0.65
    positions = [
        (-cs/2.0 - 0.04, 0, cs/2.0),
        ( cs/2.0 + 0.04, 0, cs/2.0),
        ( 0.0, 0, cs + cs/2.0 + 0.02)
    ]
    for px, py, pz in positions:
        c = add_box(bm, material_index=0)
        for v in c:
            v.co.x = v.co.x * cs + px
            v.co.y = v.co.y * cs + py
            v.co.z = v.co.z * cs + pz
            
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj

def create_barrel_group(name, plank_mat=None, iron_mat=None):
    """Cluster of wooden storage barrels (two upright, one tipped)."""
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in [plank_mat, iron_mat]:
        if m: obj.data.materials.append(m)
    bm = bmesh.new()
    
    r1, r2, h = 0.32, 0.38, 0.85
    for bx, by in [(-0.35, 0.0), (0.35, -0.15)]:
        b1 = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r1, radius2=r2, depth=h/2.0)
        for v in b1['verts']:
            v.co.x += bx
            v.co.y += by
            v.co.z += h/4.0
        b2 = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r2, radius2=r1, depth=h/2.0)
        for v in b2['verts']:
            v.co.x += bx
            v.co.y += by
            v.co.z += 3*h/4.0
            
    b_ly = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r1, radius2=r2, depth=h/2.0)
    for v in b_ly['verts']:
        vx = v.co.z
        vz = v.co.x
        v.co.x = vx
        v.co.y += 0.45
        v.co.z = vz + r2
        
    for f in bm.faces: f.material_index = 0
    bm.to_mesh(mesh)
    bm.free()
    add_bevel_modifier(obj, width=0.008, segments=2)
    return obj


