"""
Emberglass Material Library for Blender 4.2 LTS - Enhanced Stylized Palette
Rich, vibrant, cozy fantasy colors matching the Emberglass concept art.
"""

import bpy

def clear_material(mat):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    return nodes, links

def get_or_create_material(name):
    if name in bpy.data.materials:
        mat = bpy.data.materials[name]
    else:
        mat = bpy.data.materials.new(name=name)
    return mat

def create_color_ramp_node(nodes, pos_colors):
    ramp = nodes.new(type='ShaderNodeValToRGB')
    elements = ramp.color_ramp.elements
    while len(elements) < len(pos_colors):
        elements.new(0.5)
    while len(elements) > len(pos_colors):
        elements.remove(elements[-1])
    for i, (pos, col) in enumerate(pos_colors):
        elements[i].position = pos
        elements[i].color = col
    return ramp

def setup_all_materials():
    materials = {}

    # 1. Dark Structural Timber (Exposed framing, beams, posts, rafters)
    # Procedural vertical grain with warm golden oak undertones and subtle bump
    mat = get_or_create_material("M_Timber_Dark")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    map_node = nodes.new(type='ShaderNodeMapping')
    map_node.inputs['Scale'].default_value = (1.0, 1.0, 10.0)
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 8.0
    noise.inputs['Detail'].default_value = 4.0
    noise.inputs['Roughness'].default_value = 0.6
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.13, 0.08, 0.05, 1.0)),
        (0.5, (0.22, 0.14, 0.09, 1.0)),
        (1.0, (0.32, 0.20, 0.12, 1.0))
    ])
    bump = nodes.new(type='ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.15
    bump.inputs['Distance'].default_value = 0.08
    
    links.new(tex_coord.outputs['Object'], map_node.inputs['Vector'])
    links.new(map_node.outputs['Vector'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.68
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Timber_Dark"] = mat

    # 2. Medium Wood Planks (Doors, shutters, crates, barrels, stalls, benches)
    mat = get_or_create_material("M_Wood_Planks")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 10.0
    noise.inputs['Detail'].default_value = 3.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.38, 0.22, 0.12, 1.0)),
        (0.5, (0.50, 0.30, 0.16, 1.0)),
        (1.0, (0.62, 0.40, 0.22, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.65
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Wood_Planks"] = mat

    # 3. Stone Masonry Base / Foundation (Voronoi chiseled limestone blocks)
    mat = get_or_create_material("M_Stone_Base")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    voro = nodes.new(type='ShaderNodeTexVoronoi')
    voro.inputs['Scale'].default_value = 7.0
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 14.0
    mix = nodes.new(type='ShaderNodeMix')
    mix.data_type = 'FLOAT'
    mix.inputs['Factor'].default_value = 0.4
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.18, 0.17, 0.15, 1.0)),
        (0.35, (0.38, 0.35, 0.32, 1.0)),
        (0.85, (0.54, 0.50, 0.45, 1.0))
    ])
    bump = nodes.new(type='ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.22
    bump.inputs['Distance'].default_value = 0.05
    
    links.new(tex_coord.outputs['Object'], voro.inputs['Vector'])
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    links.new(voro.outputs['Distance'], mix.inputs[2])
    links.new(noise.outputs['Fac'], mix.inputs[3])
    links.new(mix.outputs['Result'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(mix.outputs['Result'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.88
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Stone_Base"] = mat

    # 4. Upper Plaster / Stucco / Wattle-and-Daub
    mat = get_or_create_material("M_Plaster")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 12.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.78, 0.72, 0.62, 1.0)),
        (0.5, (0.86, 0.81, 0.72, 1.0)),
        (1.0, (0.92, 0.88, 0.80, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.82
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Plaster"] = mat

    # 5. Terracotta Red Roof Tiles (Townhouse, Tavern, Cottage)
    mat = get_or_create_material("M_Roof_Tiles_Red")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 14.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.50, 0.15, 0.08, 1.0)),
        (0.5, (0.76, 0.26, 0.15, 1.0)),
        (1.0, (0.88, 0.36, 0.20, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.58
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Roof_Tiles_Red"] = mat

    # 6. Navy Slate Blue Roof Tiles (Warehouse, Tenement, Shop, Blacksmith)
    mat = get_or_create_material("M_Roof_Tiles_Blue")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 14.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.09, 0.13, 0.20, 1.0)),
        (0.5, (0.18, 0.28, 0.44, 1.0)),
        (1.0, (0.28, 0.40, 0.58, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.50
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Roof_Tiles_Blue"] = mat

    # 7. Weathered / Mossy Timber Shingles (Stables)
    mat = get_or_create_material("M_Roof_Tiles_Weathered")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 10.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.25, 0.20, 0.13, 1.0)),
        (0.6, (0.40, 0.32, 0.20, 1.0)),
        (1.0, (0.34, 0.40, 0.22, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.78
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Roof_Tiles_Weathered"] = mat

    # 8. Wrought Iron / Dark Metal
    mat = get_or_create_material("M_Iron_Metal")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.09, 0.09, 0.10, 1.0)
    bsdf.inputs['Metallic'].default_value = 0.94
    bsdf.inputs['Roughness'].default_value = 0.35
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Iron_Metal"] = mat

    # 9. Warm Cozy Window Glass (Radiant Interior Amber Emission)
    mat = get_or_create_material("M_Window_Glow")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (1.0, 0.82, 0.32, 1.0)
    bsdf.inputs['Emission Color'].default_value = (1.0, 0.72, 0.18, 1.0)
    bsdf.inputs['Emission Strength'].default_value = 14.0
    bsdf.inputs['Roughness'].default_value = 0.15
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Window_Glow"] = mat

    # 10. Lantern Core Light
    mat = get_or_create_material("M_Lantern_Glow")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (1.0, 0.65, 0.10, 1.0)
    bsdf.inputs['Emission Color'].default_value = (1.0, 0.65, 0.10, 1.0)
    bsdf.inputs['Emission Strength'].default_value = 28.0
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Lantern_Glow"] = mat

    # 11. Blacksmith Fire Embers / Hearth Glow
    mat = get_or_create_material("M_Fire_Embers")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    voro = nodes.new(type='ShaderNodeTexVoronoi')
    voro.inputs['Scale'].default_value = 16.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (1.0, 0.12, 0.02, 1.0)),
        (0.4, (1.0, 0.45, 0.04, 1.0)),
        (0.9, (1.0, 0.90, 0.25, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], voro.inputs['Vector'])
    links.new(voro.outputs['Distance'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 35.0
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Fire_Embers"] = mat

    # 12. Striped Canvas Awning (Blue & White)
    mat = get_or_create_material("M_Awning_Blue")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    sep_xyz = nodes.new(type='ShaderNodeSeparateXYZ')
    math_mul = nodes.new(type='ShaderNodeMath')
    math_mul.operation = 'MULTIPLY'
    math_mul.inputs[1].default_value = 6.0
    math_fract = nodes.new(type='ShaderNodeMath')
    math_fract.operation = 'FRACT'
    math_step = nodes.new(type='ShaderNodeMath')
    math_step.operation = 'GREATER_THAN'
    math_step.inputs[1].default_value = 0.5
    mix_rgb = nodes.new(type='ShaderNodeMix')
    mix_rgb.data_type = 'RGBA'
    mix_rgb.inputs[6].default_value = (0.12, 0.28, 0.54, 1.0)
    mix_rgb.inputs[7].default_value = (0.94, 0.92, 0.86, 1.0)
    
    links.new(tex_coord.outputs['Generated'], sep_xyz.inputs['Vector'])
    links.new(sep_xyz.outputs['X'], math_mul.inputs[0])
    links.new(math_mul.outputs['Value'], math_fract.inputs[0])
    links.new(math_fract.outputs['Value'], math_step.inputs[0])
    links.new(math_step.outputs['Value'], mix_rgb.inputs['Factor'])
    links.new(mix_rgb.outputs[2], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Awning_Blue"] = mat

    # 13. Striped Canvas Awning (Red & White)
    mat = get_or_create_material("M_Awning_Red")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    sep_xyz = nodes.new(type='ShaderNodeSeparateXYZ')
    math_mul = nodes.new(type='ShaderNodeMath')
    math_mul.operation = 'MULTIPLY'
    math_mul.inputs[1].default_value = 6.0
    math_fract = nodes.new(type='ShaderNodeMath')
    math_fract.operation = 'FRACT'
    math_step = nodes.new(type='ShaderNodeMath')
    math_step.operation = 'GREATER_THAN'
    math_step.inputs[1].default_value = 0.5
    mix_rgb = nodes.new(type='ShaderNodeMix')
    mix_rgb.data_type = 'RGBA'
    mix_rgb.inputs[6].default_value = (0.76, 0.18, 0.14, 1.0)
    mix_rgb.inputs[7].default_value = (0.94, 0.92, 0.86, 1.0)
    
    links.new(tex_coord.outputs['Generated'], sep_xyz.inputs['Vector'])
    links.new(sep_xyz.outputs['X'], math_mul.inputs[0])
    links.new(math_mul.outputs['Value'], math_fract.inputs[0])
    links.new(math_fract.outputs['Value'], math_step.inputs[0])
    links.new(math_step.outputs['Value'], mix_rgb.inputs['Factor'])
    links.new(mix_rgb.outputs[2], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Awning_Red"] = mat

    # 14. Foliage & Hedges
    mat = get_or_create_material("M_Foliage")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 16.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.16, 0.35, 0.10, 1.0)),
        (0.6, (0.26, 0.52, 0.18, 1.0)),
        (1.0, (0.38, 0.65, 0.24, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.60
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Foliage"] = mat

    # 15. Flowers & Blossoms (Bright Floral Accents)
    mat = get_or_create_material("M_Flowers")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.95, 0.28, 0.45, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.50
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Flowers"] = mat

    # 16. Golden Brass / Sign Emblems
    mat = get_or_create_material("M_Gold_Brass")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.94, 0.72, 0.22, 1.0)
    bsdf.inputs['Metallic'].default_value = 0.88
    bsdf.inputs['Roughness'].default_value = 0.28
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Gold_Brass"] = mat

    # 17. Golden Straw / Hay
    mat = get_or_create_material("M_Straw")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 18.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.64, 0.52, 0.22, 1.0)),
        (0.7, (0.84, 0.72, 0.35, 1.0)),
        (1.0, (0.94, 0.84, 0.45, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.90
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Straw"] = mat

    # 18. Cobblestone Ground Pavers
    mat = get_or_create_material("M_Cobblestone")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    voro = nodes.new(type='ShaderNodeTexVoronoi')
    voro.inputs['Scale'].default_value = 8.0
    ramp = create_color_ramp_node(nodes, [
        (0.0, (0.16, 0.15, 0.14, 1.0)),
        (0.4, (0.34, 0.32, 0.30, 1.0)),
        (0.9, (0.46, 0.44, 0.40, 1.0))
    ])
    links.new(tex_coord.outputs['Object'], voro.inputs['Vector'])
    links.new(voro.outputs['Distance'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Cobblestone"] = mat

    # 19. White Linen Fabric (Laundry, Flour sacks)
    mat = get_or_create_material("M_Cloth_White")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.88, 0.86, 0.82, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.90
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Cloth_White"] = mat

    # 20. Blue Cloth (Hanging laundry)
    mat = get_or_create_material("M_Cloth_Blue")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.22, 0.36, 0.58, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Cloth_Blue"] = mat

    # 21. Red Fabric Banner (Tavern heraldic banner)
    mat = get_or_create_material("M_Cloth_Red")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.72, 0.14, 0.12, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.80
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Cloth_Red"] = mat

    # 22. Stylized Smoke Puffs
    mat = get_or_create_material("M_Smoke")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.82, 0.82, 0.85, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.95
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Smoke"] = mat

    # 23. Glowing Potion Glass (Cyan / Blue Elixir)
    mat = get_or_create_material("M_Potion_Blue")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.15, 0.55, 0.95, 1.0)
    bsdf.inputs['Emission Color'].default_value = (0.20, 0.65, 1.0, 1.0)
    bsdf.inputs['Emission Strength'].default_value = 6.0
    bsdf.inputs['Roughness'].default_value = 0.10
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Potion_Blue"] = mat

    # 24. Glowing Potion Glass (Red Health Potion)
    mat = get_or_create_material("M_Potion_Red")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.95, 0.15, 0.20, 1.0)
    bsdf.inputs['Emission Color'].default_value = (1.0, 0.20, 0.25, 1.0)
    bsdf.inputs['Emission Strength'].default_value = 6.0
    bsdf.inputs['Roughness'].default_value = 0.10
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Potion_Red"] = mat

    # 25. Glowing Potion Glass (Green Stamina / Poison Elixir)
    mat = get_or_create_material("M_Potion_Green")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.20, 0.85, 0.25, 1.0)
    bsdf.inputs['Emission Color'].default_value = (0.25, 0.95, 0.30, 1.0)
    bsdf.inputs['Emission Strength'].default_value = 6.0
    bsdf.inputs['Roughness'].default_value = 0.10
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Potion_Green"] = mat

    # 26. Clear Water / Glass Surface
    mat = get_or_create_material("M_Glass")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.12, 0.30, 0.42, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.05
    bsdf.inputs['Transmission Weight'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Glass"] = mat
    materials["M_Water"] = mat

    # 27. Fountain / River Water (Reflective Cyan Blue with Depth)
    mat = get_or_create_material("M_Water_Fountain")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.10, 0.45, 0.65, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.08
    bsdf.inputs['Transmission Weight'].default_value = 0.65
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Water_Fountain"] = mat

    # 28. Canvas Sail / Windmill Blade Cloth
    mat = get_or_create_material("M_Canvas_Sail")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.86, 0.82, 0.72, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Canvas_Sail"] = mat

    # 29. Stained Glass (Chapel & Church Windows)
    mat = get_or_create_material("M_Stained_Glass")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.85, 0.55, 0.15, 1.0)
    bsdf.inputs['Emission Color'].default_value = (0.95, 0.65, 0.20, 1.0)
    bsdf.inputs['Emission Strength'].default_value = 8.0
    bsdf.inputs['Roughness'].default_value = 0.15
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Stained_Glass"] = mat

    # 30. Clipped Boxwood Hedge
    mat = get_or_create_material("M_Hedge_Green")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.16, 0.38, 0.14, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Hedge_Green"] = mat

    # 31. Packed Dirt Road
    mat = get_or_create_material("M_Dirt_Road")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.36, 0.26, 0.17, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.90
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Dirt_Road"] = mat

    # 32. Marble Statue / Carved Stone
    mat = get_or_create_material("M_Marble_Statue")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.75, 0.76, 0.78, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.45
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Marble_Statue"] = mat

    # 33. Book Spines (Leather & Parchment)
    mat = get_or_create_material("M_Book_Spines")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.50, 0.20, 0.18, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.60
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Book_Spines"] = mat

    # 34. Carpet / Tapestry Rug
    mat = get_or_create_material("M_Carpet_Rug")
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.65, 0.15, 0.15, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.90
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    materials["M_Carpet_Rug"] = mat

    # Helpful aliases for builder scripts
    aliases = {
        "M_Iron": "M_Iron_Metal",
        "M_Gold": "M_Gold_Brass",
        "M_Brass": "M_Gold_Brass",
        "M_Roof_Tiles_Slate": "M_Roof_Tiles_Blue",
        "M_Stone_Wall": "M_Stone_Base",
        "M_Stone_Trim": "M_Stone_Base",
        "M_Smoke_Stylized": "M_Smoke",
        "M_Straw_Hay": "M_Straw",
        "M_Flower_Petals": "M_Flowers",
        "M_Foliage_Hedge": "M_Hedge_Green",
        "M_Guild_Red": "M_Cloth_Red",
        "M_Guild_Blue": "M_Cloth_Blue",
        "M_Awning_Stripe_Green": "M_Awning_Blue",
        "M_Awning_Stripe_Red": "M_Awning_Red",
    }
    for alias, target in aliases.items():
        if target in materials:
            materials[alias] = materials[target]

    return materials

