"""
Emberglass Detail Material Library - finished-asset pass.
Additive only: takes the dict returned by materials.setup_all_materials() and adds
the weathering / secondary-detail materials. Nothing in materials.py is modified.
"""

import bpy
from materials import get_or_create_material, clear_material, create_color_ramp_node


def _principled(name, base_color, roughness=0.8, specular=0.3, metallic=0.0):
    """Flat stylized material - the hand-painted base every weathering layer sits on."""
    mat = get_or_create_material(name)
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = base_color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def _noise_ramp(name, ramp_stops, noise_scale=14.0, detail=4.0, roughness=0.78,
                bump_strength=0.0, bump_distance=0.04, scale=(1.0, 1.0, 1.0),
                metallic=0.0):
    """Procedural mottled material: object-space noise driving a colour ramp."""
    mat = get_or_create_material(name)
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    map_node = nodes.new(type='ShaderNodeMapping')
    map_node.inputs['Scale'].default_value = scale
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = noise_scale
    noise.inputs['Detail'].default_value = detail
    ramp = create_color_ramp_node(nodes, ramp_stops)

    links.new(tex_coord.outputs['Object'], map_node.inputs['Vector'])
    links.new(map_node.outputs['Vector'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic

    if bump_strength > 0.0:
        bump = nodes.new(type='ShaderNodeBump')
        bump.inputs['Strength'].default_value = bump_strength
        bump.inputs['Distance'].default_value = bump_distance
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def _emission(name, color, strength):
    mat = get_or_create_material(name)
    nodes, links = clear_material(mat)
    out = nodes.new(type='ShaderNodeOutputMaterial')
    emit = nodes.new(type='ShaderNodeEmission')
    emit.inputs['Color'].default_value = color
    emit.inputs['Strength'].default_value = strength
    links.new(emit.outputs['Emission'], out.inputs['Surface'])
    return mat


def setup_detail_materials(mats):
    """Add weathering + secondary detail materials to an existing material dict."""

    # --- Mortar: pale lime mortar, recessed behind the block faces -------------
    mats["M_Mortar"] = _noise_ramp("M_Mortar", [
        (0.0, (0.21, 0.20, 0.18, 1.0)),
        (0.5, (0.29, 0.27, 0.24, 1.0)),
        (1.0, (0.37, 0.35, 0.31, 1.0)),
    ], noise_scale=28.0, detail=5.0, roughness=0.95, bump_strength=0.25)

    # --- Masonry block variants: three limestone tones so courses read apart ---
    mats["M_Stone_Block_A"] = _noise_ramp("M_Stone_Block_A", [
        (0.0, (0.34, 0.31, 0.26, 1.0)),
        (0.45, (0.49, 0.44, 0.37, 1.0)),
        (1.0, (0.62, 0.57, 0.47, 1.0)),
    ], noise_scale=11.0, detail=6.0, roughness=0.86, bump_strength=0.30, bump_distance=0.05)

    mats["M_Stone_Block_B"] = _noise_ramp("M_Stone_Block_B", [
        (0.0, (0.27, 0.26, 0.24, 1.0)),
        (0.45, (0.40, 0.38, 0.35, 1.0)),
        (1.0, (0.52, 0.49, 0.44, 1.0)),
    ], noise_scale=13.0, detail=6.0, roughness=0.88, bump_strength=0.30, bump_distance=0.05)

    mats["M_Stone_Block_C"] = _noise_ramp("M_Stone_Block_C", [
        (0.0, (0.37, 0.31, 0.25, 1.0)),
        (0.45, (0.52, 0.45, 0.36, 1.0)),
        (1.0, (0.66, 0.58, 0.47, 1.0)),
    ], noise_scale=9.0, detail=6.0, roughness=0.84, bump_strength=0.28, bump_distance=0.05)

    # --- Cobbles: warmer and darker than the wall stone -----------------------
    mats["M_Cobble_A"] = _noise_ramp("M_Cobble_A", [
        (0.0, (0.30, 0.29, 0.28, 1.0)),
        (0.5, (0.44, 0.42, 0.39, 1.0)),
        (1.0, (0.57, 0.54, 0.49, 1.0)),
    ], noise_scale=18.0, detail=5.0, roughness=0.72, bump_strength=0.35)

    mats["M_Cobble_B"] = _noise_ramp("M_Cobble_B", [
        (0.0, (0.34, 0.30, 0.26, 1.0)),
        (0.5, (0.49, 0.43, 0.36, 1.0)),
        (1.0, (0.62, 0.55, 0.45, 1.0)),
    ], noise_scale=22.0, detail=5.0, roughness=0.70, bump_strength=0.35)

    mats["M_Cobble_Dirt"] = _noise_ramp("M_Cobble_Dirt", [
        (0.0, (0.20, 0.17, 0.13, 1.0)),
        (0.5, (0.30, 0.25, 0.19, 1.0)),
        (1.0, (0.40, 0.34, 0.26, 1.0)),
    ], noise_scale=26.0, detail=6.0, roughness=0.96)

    # --- Roof tiles: three fired-clay bakes, plus an aged/lichened fourth ------
    mats["M_Tile_A"] = _noise_ramp("M_Tile_A", [
        (0.0, (0.52, 0.22, 0.11, 1.0)),
        (0.5, (0.72, 0.34, 0.17, 1.0)),
        (1.0, (0.86, 0.48, 0.26, 1.0)),
    ], noise_scale=16.0, detail=4.0, roughness=0.78, bump_strength=0.22)

    mats["M_Tile_B"] = _noise_ramp("M_Tile_B", [
        (0.0, (0.33, 0.13, 0.09, 1.0)),
        (0.5, (0.48, 0.21, 0.13, 1.0)),
        (1.0, (0.61, 0.30, 0.19, 1.0)),
    ], noise_scale=19.0, detail=4.0, roughness=0.80, bump_strength=0.22)

    mats["M_Tile_C"] = _noise_ramp("M_Tile_C", [
        (0.0, (0.28, 0.16, 0.12, 1.0)),
        (0.5, (0.41, 0.24, 0.17, 1.0)),
        (1.0, (0.54, 0.34, 0.24, 1.0)),
    ], noise_scale=14.0, detail=4.0, roughness=0.83, bump_strength=0.22)

    # Aged tile: sun-bleached, lichen-spotted - for damaged and shaded courses
    mats["M_Tile_Aged"] = _noise_ramp("M_Tile_Aged", [
        (0.0, (0.22, 0.15, 0.10, 1.0)),
        (0.35, (0.34, 0.24, 0.15, 1.0)),
        (0.70, (0.44, 0.35, 0.21, 1.0)),
        (1.0, (0.36, 0.38, 0.23, 1.0)),
    ], noise_scale=24.0, detail=6.0, roughness=0.92, bump_strength=0.30)

    # --- Slate: cool blue-grey, the second roof in the library -------------
    mats["M_Slate_A"] = _noise_ramp("M_Slate_A", [
        (0.0, (0.16, 0.19, 0.25, 1.0)),
        (0.5, (0.25, 0.30, 0.39, 1.0)),
        (1.0, (0.35, 0.41, 0.52, 1.0)),
    ], noise_scale=16.0, detail=4.0, roughness=0.62, bump_strength=0.22)

    mats["M_Slate_B"] = _noise_ramp("M_Slate_B", [
        (0.0, (0.12, 0.15, 0.21, 1.0)),
        (0.5, (0.20, 0.24, 0.32, 1.0)),
        (1.0, (0.29, 0.34, 0.44, 1.0)),
    ], noise_scale=19.0, detail=4.0, roughness=0.64, bump_strength=0.22)

    mats["M_Slate_C"] = _noise_ramp("M_Slate_C", [
        (0.0, (0.17, 0.19, 0.22, 1.0)),
        (0.5, (0.27, 0.30, 0.35, 1.0)),
        (1.0, (0.38, 0.42, 0.48, 1.0)),
    ], noise_scale=13.0, detail=4.0, roughness=0.66, bump_strength=0.22)

    mats["M_Slate_Aged"] = _noise_ramp("M_Slate_Aged", [
        (0.0, (0.13, 0.15, 0.17, 1.0)),
        (0.40, (0.22, 0.25, 0.26, 1.0)),
        (0.75, (0.30, 0.33, 0.30, 1.0)),
        (1.0, (0.28, 0.34, 0.24, 1.0)),
    ], noise_scale=24.0, detail=6.0, roughness=0.78, bump_strength=0.28)

    # --- Wooden shingle: the third roof, warm brown ------------------------
    mats["M_Shingle_A"] = _noise_ramp("M_Shingle_A", [
        (0.0, (0.26, 0.18, 0.10, 1.0)),
        (0.5, (0.40, 0.28, 0.16, 1.0)),
        (1.0, (0.53, 0.39, 0.23, 1.0)),
    ], noise_scale=9.0, detail=6.0, roughness=0.88, bump_strength=0.30,
        scale=(1.0, 1.0, 6.0))

    mats["M_Shingle_B"] = _noise_ramp("M_Shingle_B", [
        (0.0, (0.21, 0.15, 0.09, 1.0)),
        (0.5, (0.33, 0.24, 0.14, 1.0)),
        (1.0, (0.45, 0.34, 0.20, 1.0)),
    ], noise_scale=11.0, detail=6.0, roughness=0.90, bump_strength=0.30,
        scale=(1.0, 1.0, 6.0))

    mats["M_Shingle_C"] = _noise_ramp("M_Shingle_C", [
        (0.0, (0.29, 0.22, 0.14, 1.0)),
        (0.5, (0.44, 0.34, 0.21, 1.0)),
        (1.0, (0.58, 0.46, 0.30, 1.0)),
    ], noise_scale=8.0, detail=6.0, roughness=0.86, bump_strength=0.30,
        scale=(1.0, 1.0, 6.0))

    mats["M_Shingle_Aged"] = _noise_ramp("M_Shingle_Aged", [
        (0.0, (0.19, 0.16, 0.12, 1.0)),
        (0.40, (0.30, 0.26, 0.19, 1.0)),
        (0.75, (0.40, 0.37, 0.26, 1.0)),
        (1.0, (0.34, 0.38, 0.24, 1.0)),
    ], noise_scale=20.0, detail=6.0, roughness=0.93, bump_strength=0.30)

    # --- Thatch: reed bundles, warm straw -----------------------------------
    mats["M_Thatch_A"] = _noise_ramp("M_Thatch_A", [
        (0.0, (0.35, 0.26, 0.12, 1.0)),
        (0.5, (0.55, 0.42, 0.20, 1.0)),
        (1.0, (0.72, 0.58, 0.30, 1.0)),
    ], noise_scale=30.0, detail=7.0, roughness=0.97, bump_strength=0.50,
        scale=(1.0, 6.0, 1.0))

    mats["M_Thatch_B"] = _noise_ramp("M_Thatch_B", [
        (0.0, (0.29, 0.21, 0.10, 1.0)),
        (0.5, (0.47, 0.35, 0.17, 1.0)),
        (1.0, (0.63, 0.49, 0.25, 1.0)),
    ], noise_scale=34.0, detail=7.0, roughness=0.97, bump_strength=0.50,
        scale=(1.0, 6.0, 1.0))

    mats["M_Thatch_Aged"] = _noise_ramp("M_Thatch_Aged", [
        (0.0, (0.24, 0.20, 0.12, 1.0)),
        (0.5, (0.38, 0.33, 0.19, 1.0)),
        (1.0, (0.44, 0.44, 0.24, 1.0)),
    ], noise_scale=26.0, detail=7.0, roughness=0.98, bump_strength=0.45)

    # --- Extra surfaces the wider library needs ----------------------------
    # --- Granite: the fortification stone. Cool, dark and slightly blue, so
    # a castle reads as a different material from a house at a glance.
    mats["M_Granite_A"] = _noise_ramp("M_Granite_A", [
        (0.0, (0.185, 0.196, 0.214, 1.0)),
        (0.45, (0.285, 0.300, 0.325, 1.0)),
        (1.0, (0.395, 0.412, 0.440, 1.0)),
    ], noise_scale=12.0, detail=6.0, roughness=0.80, bump_strength=0.34)

    mats["M_Granite_B"] = _noise_ramp("M_Granite_B", [
        (0.0, (0.145, 0.155, 0.172, 1.0)),
        (0.45, (0.230, 0.244, 0.268, 1.0)),
        (1.0, (0.330, 0.347, 0.375, 1.0)),
    ], noise_scale=15.0, detail=6.0, roughness=0.82, bump_strength=0.34)

    mats["M_Granite_C"] = _noise_ramp("M_Granite_C", [
        (0.0, (0.215, 0.216, 0.210, 1.0)),
        (0.45, (0.325, 0.325, 0.316, 1.0)),
        (1.0, (0.450, 0.448, 0.432, 1.0)),
    ], noise_scale=10.0, detail=6.0, roughness=0.78, bump_strength=0.34)

    # --- Ashlar: fine dressed ecclesiastical stone. Pale, cool, low contrast.
    mats["M_Ashlar_A"] = _noise_ramp("M_Ashlar_A", [
        (0.0, (0.455, 0.462, 0.455, 1.0)),
        (0.45, (0.605, 0.610, 0.598, 1.0)),
        (1.0, (0.730, 0.732, 0.715, 1.0)),
    ], noise_scale=8.0, detail=5.0, roughness=0.80, bump_strength=0.18,
        bump_distance=0.04)

    mats["M_Ashlar_B"] = _noise_ramp("M_Ashlar_B", [
        (0.0, (0.400, 0.410, 0.412, 1.0)),
        (0.45, (0.540, 0.550, 0.548, 1.0)),
        (1.0, (0.665, 0.672, 0.665, 1.0)),
    ], noise_scale=10.0, detail=5.0, roughness=0.82, bump_strength=0.18,
        bump_distance=0.04)

    mats["M_Ashlar_C"] = _noise_ramp("M_Ashlar_C", [
        (0.0, (0.470, 0.462, 0.438, 1.0)),
        (0.45, (0.625, 0.612, 0.580, 1.0)),
        (1.0, (0.750, 0.735, 0.700, 1.0)),
    ], noise_scale=7.0, detail=5.0, roughness=0.78, bump_strength=0.18,
        bump_distance=0.04)

    # --- Fieldstone: rough mid brown-grey for bridges, stairs, field walls.
    mats["M_Fieldstone_A"] = _noise_ramp("M_Fieldstone_A", [
        (0.0, (0.268, 0.258, 0.238, 1.0)),
        (0.45, (0.390, 0.374, 0.342, 1.0)),
        (1.0, (0.510, 0.490, 0.448, 1.0)),
    ], noise_scale=11.0, detail=6.0, roughness=0.88, bump_strength=0.36,
        bump_distance=0.05)

    mats["M_Fieldstone_B"] = _noise_ramp("M_Fieldstone_B", [
        (0.0, (0.215, 0.214, 0.205, 1.0)),
        (0.45, (0.325, 0.322, 0.305, 1.0)),
        (1.0, (0.440, 0.434, 0.410, 1.0)),
    ], noise_scale=14.0, detail=6.0, roughness=0.90, bump_strength=0.36,
        bump_distance=0.05)

    mats["M_Fieldstone_C"] = _noise_ramp("M_Fieldstone_C", [
        (0.0, (0.292, 0.262, 0.222, 1.0)),
        (0.45, (0.418, 0.378, 0.322, 1.0)),
        (1.0, (0.545, 0.498, 0.428, 1.0)),
    ], noise_scale=9.0, detail=6.0, roughness=0.86, bump_strength=0.36,
        bump_distance=0.05)

    # --- Matching mortars. A grey wall bedded in warm mortar reads wrong.
    mats["M_Mortar_Grey"] = _noise_ramp("M_Mortar_Grey", [
        (0.0, (0.120, 0.126, 0.136, 1.0)),
        (0.5, (0.175, 0.182, 0.195, 1.0)),
        (1.0, (0.235, 0.243, 0.258, 1.0)),
    ], noise_scale=28.0, detail=5.0, roughness=0.95, bump_strength=0.25)

    mats["M_Mortar_Pale"] = _noise_ramp("M_Mortar_Pale", [
        (0.0, (0.300, 0.305, 0.300, 1.0)),
        (0.5, (0.395, 0.400, 0.392, 1.0)),
        (1.0, (0.480, 0.484, 0.472, 1.0)),
    ], noise_scale=28.0, detail=5.0, roughness=0.95, bump_strength=0.22)

    mats["M_Sand"] = _noise_ramp("M_Sand", [
        (0.0, (0.42, 0.34, 0.22, 1.0)),
        (0.5, (0.58, 0.48, 0.32, 1.0)),
        (1.0, (0.72, 0.62, 0.44, 1.0)),
    ], noise_scale=40.0, detail=6.0, roughness=0.98, bump_strength=0.25)

    mats["M_Grass"] = _noise_ramp("M_Grass", [
        (0.0, (0.15, 0.25, 0.09, 1.0)),
        (0.5, (0.25, 0.38, 0.14, 1.0)),
        (1.0, (0.38, 0.50, 0.20, 1.0)),
    ], noise_scale=16.0, detail=6.0, roughness=0.95, bump_strength=0.30)

    mats["M_Water_Deep"] = _noise_ramp("M_Water_Deep", [
        (0.0, (0.06, 0.16, 0.22, 1.0)),
        (0.5, (0.10, 0.26, 0.34, 1.0)),
        (1.0, (0.18, 0.38, 0.46, 1.0)),
    ], noise_scale=8.0, detail=5.0, roughness=0.18)

    mats["M_Snow_Cap"] = _principled("M_Snow_Cap", (0.82, 0.86, 0.92, 1.0), 0.80)
    mats["M_Bark"] = _noise_ramp("M_Bark", [
        (0.0, (0.14, 0.10, 0.07, 1.0)),
        (0.5, (0.24, 0.17, 0.11, 1.0)),
        (1.0, (0.35, 0.26, 0.17, 1.0)),
    ], noise_scale=9.0, detail=7.0, roughness=0.94, bump_strength=0.45,
        scale=(1.0, 1.0, 7.0))

    mats["M_Leaf_Spring"] = _noise_ramp("M_Leaf_Spring", [
        (0.0, (0.11, 0.24, 0.09, 1.0)),
        (0.5, (0.20, 0.38, 0.14, 1.0)),
        (1.0, (0.33, 0.52, 0.20, 1.0)),
    ], noise_scale=14.0, detail=6.0, roughness=0.86)

    mats["M_Leaf_Pine"] = _noise_ramp("M_Leaf_Pine", [
        (0.0, (0.07, 0.17, 0.11, 1.0)),
        (0.5, (0.12, 0.26, 0.16, 1.0)),
        (1.0, (0.19, 0.35, 0.22, 1.0)),
    ], noise_scale=18.0, detail=6.0, roughness=0.88)

    mats["M_Linen"] = _noise_ramp("M_Linen", [
        (0.0, (0.66, 0.62, 0.54, 1.0)),
        (0.5, (0.80, 0.76, 0.68, 1.0)),
        (1.0, (0.90, 0.87, 0.80, 1.0)),
    ], noise_scale=28.0, detail=5.0, roughness=0.95)

    mats["M_Paper"] = _principled("M_Paper", (0.84, 0.79, 0.67, 1.0), 0.96)
    mats["M_Wool_Red"] = _principled("M_Wool_Red", (0.44, 0.13, 0.12, 1.0), 0.94)
    mats["M_Wool_Blue"] = _principled("M_Wool_Blue", (0.14, 0.22, 0.38, 1.0), 0.94)
    mats["M_Wool_Cream"] = _principled("M_Wool_Cream", (0.74, 0.68, 0.55, 1.0), 0.94)

    # Dark batten/decking seen through missing tiles
    mats["M_Roof_Void"] = _principled("M_Roof_Void", (0.07, 0.055, 0.045, 1.0), 0.95)

    # --- Weathered plaster: cream with damp staining and rain streaks ----------
    mats["M_Plaster_Weathered"] = _noise_ramp("M_Plaster_Weathered", [
        (0.0, (0.36, 0.30, 0.22, 1.0)),
        (0.30, (0.55, 0.47, 0.35, 1.0)),
        (0.65, (0.70, 0.62, 0.47, 1.0)),
        (1.0, (0.79, 0.72, 0.56, 1.0)),
    ], noise_scale=5.0, detail=8.0, roughness=0.92, bump_strength=0.18,
        bump_distance=0.06, scale=(2.2, 2.2, 0.55))

    # Second plaster tone so adjacent panels never read as one flat sheet
    mats["M_Plaster_Warm"] = _noise_ramp("M_Plaster_Warm", [
        (0.0, (0.30, 0.23, 0.15, 1.0)),
        (0.35, (0.49, 0.39, 0.26, 1.0)),
        (1.0, (0.66, 0.56, 0.39, 1.0)),
    ], noise_scale=6.0, detail=8.0, roughness=0.92, bump_strength=0.18,
        bump_distance=0.06, scale=(2.0, 2.0, 0.5))

    # Later patch repair: a colder, greyer lime that never quite matched
    mats["M_Plaster_Repair"] = _noise_ramp("M_Plaster_Repair", [
        (0.0, (0.31, 0.30, 0.27, 1.0)),
        (0.40, (0.46, 0.44, 0.39, 1.0)),
        (1.0, (0.60, 0.58, 0.51, 1.0)),
    ], noise_scale=9.0, detail=7.0, roughness=0.94, bump_strength=0.22,
        bump_distance=0.05, scale=(1.8, 1.8, 0.6))

    # Brick nogging revealed where plaster has fallen away
    mats["M_Brick_Nogging"] = _noise_ramp("M_Brick_Nogging", [
        (0.0, (0.28, 0.14, 0.10, 1.0)),
        (0.5, (0.45, 0.23, 0.16, 1.0)),
        (1.0, (0.58, 0.33, 0.23, 1.0)),
    ], noise_scale=30.0, detail=5.0, roughness=0.93, bump_strength=0.40)

    # Riven lath behind the nogging
    mats["M_Lath"] = _principled("M_Lath", (0.26, 0.18, 0.11, 1.0), 0.92)

    # --- Aged timber: greyer and drier than M_Timber_Dark ---------------------
    mats["M_Timber_Aged"] = _noise_ramp("M_Timber_Aged", [
        (0.0, (0.15, 0.11, 0.08, 1.0)),
        (0.4, (0.26, 0.19, 0.14, 1.0)),
        (0.75, (0.36, 0.28, 0.21, 1.0)),
        (1.0, (0.45, 0.39, 0.32, 1.0)),
    ], noise_scale=7.0, detail=7.0, roughness=0.88, bump_strength=0.28,
        bump_distance=0.05, scale=(1.0, 1.0, 9.0))

    # Raw split face where timber has chipped away - lighter heartwood
    mats["M_Timber_Chip"] = _principled("M_Timber_Chip", (0.47, 0.33, 0.20, 1.0), 0.82)

    # --- Growth: moss, lichen, ivy, weeds -------------------------------------
    mats["M_Moss"] = _noise_ramp("M_Moss", [
        (0.0, (0.09, 0.17, 0.07, 1.0)),
        (0.45, (0.17, 0.30, 0.11, 1.0)),
        (1.0, (0.30, 0.45, 0.17, 1.0)),
    ], noise_scale=34.0, detail=7.0, roughness=0.97, bump_strength=0.55, bump_distance=0.03)

    mats["M_Lichen"] = _noise_ramp("M_Lichen", [
        (0.0, (0.42, 0.46, 0.36, 1.0)),
        (0.5, (0.57, 0.60, 0.48, 1.0)),
        (1.0, (0.71, 0.73, 0.61, 1.0)),
    ], noise_scale=40.0, detail=8.0, roughness=0.98, bump_strength=0.30, bump_distance=0.02)

    mats["M_Ivy_Leaf"] = _noise_ramp("M_Ivy_Leaf", [
        (0.0, (0.07, 0.19, 0.08, 1.0)),
        (0.4, (0.13, 0.31, 0.12, 1.0)),
        (0.75, (0.21, 0.43, 0.16, 1.0)),
        (1.0, (0.34, 0.54, 0.22, 1.0)),
    ], noise_scale=12.0, detail=6.0, roughness=0.80, bump_strength=0.20)

    mats["M_Ivy_Stem"] = _principled("M_Ivy_Stem", (0.18, 0.13, 0.08, 1.0), 0.88)

    mats["M_Weed_Green"] = _noise_ramp("M_Weed_Green", [
        (0.0, (0.19, 0.27, 0.09, 1.0)),
        (0.5, (0.31, 0.41, 0.14, 1.0)),
        (1.0, (0.47, 0.56, 0.22, 1.0)),
    ], noise_scale=20.0, detail=5.0, roughness=0.92)

    # --- Soot around the chimney flue ------------------------------------------
    mats["M_Soot"] = _noise_ramp("M_Soot", [
        (0.0, (0.055, 0.046, 0.040, 1.0)),
        (0.5, (0.105, 0.088, 0.076, 1.0)),
        (1.0, (0.180, 0.152, 0.128, 1.0)),
    ], noise_scale=22.0, detail=7.0, roughness=0.99, bump_strength=0.20)

    # --- Aged ironwork: hinges, straps, brackets, nail heads -------------------
    mats["M_Iron_Aged"] = _noise_ramp("M_Iron_Aged", [
        (0.0, (0.050, 0.046, 0.044, 1.0)),
        (0.45, (0.095, 0.088, 0.082, 1.0)),
        (0.80, (0.17, 0.14, 0.12, 1.0)),
        (1.0, (0.30, 0.20, 0.13, 1.0)),
    ], noise_scale=26.0, detail=6.0, roughness=0.60, bump_strength=0.25, metallic=0.65)

    # --- Glass / glow ----------------------------------------------------------
    mats["M_Window_Warm"] = _emission("M_Window_Warm", (1.0, 0.72, 0.36, 1.0), 1.45)
    mats["M_Window_Dim"] = _emission("M_Window_Dim", (0.90, 0.62, 0.32, 1.0), 0.65)
    mats["M_Lantern_Flame"] = _emission("M_Lantern_Flame", (1.0, 0.64, 0.26, 1.0), 4.0)

    # --- Painted signboard + misc clutter -------------------------------------
    mats["M_Sign_Paint"] = _principled("M_Sign_Paint", (0.15, 0.09, 0.06, 1.0), 0.70)
    mats["M_Paint_Green"] = _principled("M_Paint_Green", (0.13, 0.25, 0.20, 1.0), 0.66)
    mats["M_Paint_Blue"] = _principled("M_Paint_Blue", (0.15, 0.23, 0.33, 1.0), 0.66)
    mats["M_Rope"] = _principled("M_Rope", (0.52, 0.42, 0.26, 1.0), 0.95)
    mats["M_Terracotta"] = _principled("M_Terracotta", (0.55, 0.28, 0.18, 1.0), 0.85)
    mats["M_Soil"] = _noise_ramp("M_Soil", [
        (0.0, (0.12, 0.085, 0.055, 1.0)),
        (0.5, (0.20, 0.145, 0.095, 1.0)),
        (1.0, (0.28, 0.20, 0.13, 1.0)),
    ], noise_scale=24.0, detail=6.0, roughness=0.98, bump_strength=0.30)

    return mats
