"""
Emberglass library - the 20 detailed structures.

Each one calls the shared `build_structure()` for its anatomy and then adds only
what makes it that building. Footprints match the blockout originals so the
sheet layout and relative scale are unchanged.
"""

import bpy
import random
from math import radians, cos, sin, tan, pi

import builder_primitives as bp
import detail_primitives as dp
import detail_architecture as da
from detail_buildings import (build_structure, add_window, window_row, add_door,
                              add_lantern, add_sign, add_ivy, clutter, _link,
                              _spread, SHADED)


# =============================================================================
# 1-8  Town buildings
# =============================================================================

def build_cottage(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 4.2, 5.0
    L = build_structure("Cot", mats, col, o, w=w, d=d, base_h=0.85,
                        stone="fieldstone",
                        storey_h=(1.75,), jetty=0.0, roof_axis="y", pitch=50.0,
                        palette="clay", seed=101, overhang=(0.46, 0.34),
                        chimney=[(-0.95, 0.9, 2.6, 0.82)])
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    window_row("Cot_WinY", mats, col, "y", [-1.15, 1.15], oy - hd + 0.02,
               gf + 0.30, 61, width=0.86, height=1.05, planter=True)
    window_row("Cot_WinX", mats, col, "x", [1.25], ox + hw + 0.02, gf + 0.30,
               77, width=0.86, height=1.05, planter=True)
    add_window("Cot_Attic", mats, col, ox, oy - hd - 0.14, L["eaves"] + 0.75, 0,
               91, width=0.60, height=0.72, planter=False, pane_cols=2,
               pane_rows=3, stone_sill=False)
    add_door("Cot_Door", mats, col, ox + hw + 0.02, oy - 1.10, gf - 0.55, 90,
             71, ground=oz, width=1.05)
    add_lantern("Cot_Lamp", mats, col, ox + hw + 0.02, oy - 0.10, gf + 1.20, 90, 83)
    add_ivy("Cot_Ivy", mats, col, ox - hw - 0.02, oy - hd - 0.02, oz + 0.10,
            -90, 41, h=2.5, w=1.0, corner=True, stems=3, density=1.1)
    clutter("Cot", mats, col, [
        ("garden", ox - 1.0, oy - hd - 0.62, 0, 109),
        ("bench", ox + hw + 0.70, oy + 1.30, 90, 103),
        ("firewood", ox - hw - 0.34, oy + 1.20, -90, 107),
        ("barrel", ox + hw + 0.62, oy + 2.35, 0, 97),
        ("flowerbox", ox + 1.30, oy - hd - 0.45, 0, 113)])
    fen = bp.create_fence_section("Cot_Fence", length=2.4, height=0.9,
                                  timber_mat=mats["M_Timber_Aged"])
    fen.location = (ox - 1.0, oy - hd - 1.35, oz)
    _link(fen, col)
    return L


def build_townhouse(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 4.4, 5.4
    L = build_structure("Twn", mats, col, o, w=w, d=d, base_h=1.1,
                        storey_h=(1.5, 2.2), jetty=0.175, roof_axis="y",
                        pitch=48.0, palette="clay", seed=11,
                        overhang=(0.44, 0.34),
                        chimney=[(-0.52, -1.65, 2.80, 0.96)])
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    jhw, jhd = L["w"] * 0.5, L["d"] * 0.5
    window_row("Twn_GFY", mats, col, "y", [-1.65, 0.55], oy - hd + 0.02,
               gf + 0.34, 61, width=0.88, height=1.08)
    window_row("Twn_1FY", mats, col, "y", [-1.15, 1.15], oy - jhd + 0.02,
               L["top0"] + 0.55, 71, width=0.86, height=1.18, planter=True)
    add_window("Twn_Attic", mats, col, ox, oy - jhd - 0.14, L["eaves"] + 0.92, 0,
               83, width=0.62, height=0.76, planter=False, pane_cols=2,
               pane_rows=3, stone_sill=False)
    add_door("Twn_Door", mats, col, ox + hw + 0.02, oy - 1.20, gf - 0.62, 90,
             71, ground=oz)
    window_row("Twn_GFX", mats, col, "x", [0.55, 2.05], ox + hw + 0.02,
               gf + 0.34, 91, width=0.86, height=1.08, planter=True)
    window_row("Twn_1FX", mats, col, "x", [-1.55, 0.0, 1.55], ox + jhw + 0.02,
               L["top0"] + 0.55, 101, width=0.84, height=1.18, planter=True)
    add_lantern("Twn_Lamp", mats, col, ox + hw + 0.02, oy - 0.30, gf + 1.30, 90, 83)
    add_lantern("Twn_Lamp2", mats, col, ox - 0.58, oy - hd + 0.02, gf + 1.30, 0, 97)
    add_sign("Twn_Sign", mats, col, ox + 1.78, oy - hd + 0.02, gf + 1.42, 0, 89)
    add_ivy("Twn_IvyA", mats, col, ox - hw - 0.02, oy - hd - 0.02, oz + 0.10,
            -90, 41, h=3.35, w=1.05, corner=True, stems=4, density=1.15)
    add_ivy("Twn_IvyB", mats, col, ox + hw + 0.02, oy + hd + 0.02, oz + 0.10,
            90, 47, h=2.85, w=0.95, corner=True, stems=3)
    add_ivy("Twn_IvyC", mats, col, ox + hw + 0.02, oy + 2.55, oz + 0.35, 90, 59,
            h=1.95, w=0.85, stems=3, density=0.95)
    clutter("Twn", mats, col, [
        ("garden", ox - 1.05, oy - hd - 0.62, 0, 109),
        ("flowerbox", ox + 1.85, oy - hd - 0.48, 0, 113),
        ("bench", ox + hw + 0.68, oy + 1.30, 90, 103),
        ("barrel_open", ox + hw + 0.62, oy + 2.95, 0, 97),
        ("barrel", ox + hw + 1.24, oy + 3.10, 0, 108),
        ("crate", ox + hw + 0.70, oy - 2.60, 14, 101),
        ("crate_small", ox + hw + 1.36, oy - 2.35, -22, 163),
        ("firewood", ox - hw - 0.34, oy + 1.55, -90, 107)])
    return L


def build_tenement(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 6.4, 4.6
    L = build_structure("Ten", mats, col, o, w=w, d=d, base_h=0.95,
                        storey_h=(1.6, 1.9, 1.9), jetty=0.15, roof_axis="x",
                        pitch=46.0, palette="slate", seed=131,
                        overhang=(0.40, 0.30),
                        chimney=[(-1.9, 1.35, 2.55, 0.86),
                                 (1.9, -1.35, 2.35, 0.80)])
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    j1w = (w + 0.30) * 0.5
    j2w, j2d = L["w"] * 0.5, L["d"] * 0.5
    window_row("Ten_GFY", mats, col, "y", [-2.0, -0.4, 1.25], oy - hd + 0.02,
               gf + 0.32, 141, width=0.80, height=1.00)
    window_row("Ten_1FY", mats, col, "y", [-2.1, -0.6, 0.9, 2.3],
               oy - (d + 0.30) * 0.5 + 0.02, L["top0"] + 0.44, 151,
               width=0.78, height=1.06, planter=True)
    window_row("Ten_2FY", mats, col, "y", [-2.2, -0.7, 0.8, 2.3],
               oy - j2d + 0.02, L["top1"] + 0.44, 161, width=0.78, height=1.06,
               planter=True)
    window_row("Ten_GFX", mats, col, "x", [0.6, -1.4], ox + hw + 0.02,
               gf + 0.32, 171, width=0.80, height=1.00)
    window_row("Ten_2FX", mats, col, "x", [-1.0, 0.9], ox + j2w + 0.02,
               L["top1"] + 0.44, 181, width=0.78, height=1.06, planter=True)
    add_door("Ten_Door", mats, col, ox + hw + 0.02, oy + 1.55, gf - 0.50, 90,
             191, ground=oz, width=1.05)
    add_lantern("Ten_Lamp", mats, col, ox + hw + 0.02, oy + 0.35, gf + 1.20, 90, 199)
    add_lantern("Ten_Lamp2", mats, col, ox - 2.6, oy - hd + 0.02, gf + 1.16, 0, 211)
    add_ivy("Ten_Ivy", mats, col, ox - hw - 0.02, oy - hd - 0.02, oz + 0.10,
            -90, 223, h=3.6, w=1.0, corner=True, stems=4, density=1.2)
    clutter("Ten", mats, col, [
        ("barrel", ox - hw - 0.62, oy + 1.20, 0, 227),
        ("crate", ox + hw + 0.72, oy - 1.30, 9, 229),
        ("crate_small", ox + hw + 0.66, oy - 1.26, -14, 233),
        ("firewood", ox - 2.4, oy - hd - 0.45, 0, 239),
        ("flowerbox", ox + 0.5, oy - hd - 0.42, 0, 241)])
    return L


def build_tavern(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 6.2, 4.4
    L = build_structure("Tav", mats, col, o, w=w, d=d, base_h=1.0,
                        storey_h=(1.9, 2.1), jetty=0.18, roof_axis="x",
                        pitch=47.0, palette="clay", seed=251,
                        overhang=(0.46, 0.34),
                        chimney=[(-1.7, 1.1, 2.75, 1.00)])
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    jhw, jhd = L["w"] * 0.5, L["d"] * 0.5
    window_row("Tav_GFY", mats, col, "y", [-1.95, 1.75], oy - hd + 0.02,
               gf + 0.36, 261, width=0.92, height=1.10)
    window_row("Tav_1FY", mats, col, "y", [-2.0, -0.6, 0.8, 2.15],
               oy - jhd + 0.02, L["top0"] + 0.50, 271, width=0.82, height=1.14,
               planter=True)
    window_row("Tav_GFX", mats, col, "x", [1.2], ox + hw + 0.02, gf + 0.36,
               281, width=0.88, height=1.10, planter=True)
    window_row("Tav_1FX", mats, col, "x", [-1.0, 0.95], ox + jhw + 0.02,
               L["top0"] + 0.50, 291, width=0.82, height=1.14, planter=True)
    add_door("Tav_Door", mats, col, ox - 0.15, oy - hd + 0.02, gf - 0.48, 0,
             301, ground=oz, width=1.25, canopy=False)
    aw = da.create_striped_awning("Tav_Awning", width=3.4, depth=1.55,
                                  mats=mats, seed=311, colour="red",
                                  posts=True, height=2.35)
    aw.location = (ox - 0.15, oy - hd + 0.02, gf - 0.48)
    _link(aw, col)
    add_sign("Tav_Sign", mats, col, ox + hw + 0.02, oy - 1.30, gf + 1.55, 90,
             321, bw=1.00, bh=0.72)
    add_lantern("Tav_Lamp", mats, col, ox + 1.90, oy - hd + 0.02, gf + 1.40, 0, 331)
    add_lantern("Tav_Lamp2", mats, col, ox - 2.20, oy - hd + 0.02, gf + 1.40, 0, 337)
    ban = da.create_banner("Tav_Banner", width=0.78, height=2.0, mats=mats,
                           seed=341, colour="red")
    ban.location = (ox + jhw + 0.06, oy + 0.9, L["top0"] + 0.30)
    ban.rotation_euler = (0, 0, radians(90))
    _link(ban, col)
    add_ivy("Tav_Ivy", mats, col, ox - hw - 0.02, oy + hd + 0.02, oz + 0.10,
            180, 347, h=2.9, w=1.0, corner=True, stems=3)
    clutter("Tav", mats, col, [
        ("barrel", ox + hw + 0.66, oy + 1.15, 0, 353),
        ("barrel_open", ox + hw + 1.28, oy + 1.32, 0, 359),
        ("barrel", ox + hw + 0.90, oy + 1.95, 0, 367),
        ("bench", ox - 2.4, oy - hd - 1.05, 0, 373),
        ("bench", ox + 1.5, oy - hd - 1.05, 0, 379),
        ("crate", ox - hw - 0.70, oy - 0.9, -12, 383),
        ("firewood", ox - hw - 0.34, oy + 0.9, -90, 389)])
    tbl = bp.create_table_set("Tav_Table", timber_mat=mats["M_Timber_Aged"],
                              iron_mat=mats["M_Iron_Aged"])
    tbl.location = (ox - 0.4, oy - hd - 1.75, oz)
    _link(tbl, col)
    return L


def build_shop(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 5.2, 4.4
    L = build_structure("Shp", mats, col, o, w=w, d=d, base_h=0.95,
                        storey_h=(1.8, 2.0), jetty=0.18, roof_axis="x",
                        pitch=47.0, palette="slate", seed=401,
                        overhang=(0.44, 0.32),
                        chimney=[(1.45, 1.05, 2.45, 0.84)])
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    jhw, jhd = L["w"] * 0.5, L["d"] * 0.5
    window_row("Shp_1FY", mats, col, "y", [-1.55, 0.0, 1.55], oy - jhd + 0.02,
               L["top0"] + 0.46, 411, width=0.82, height=1.12, planter=True)
    window_row("Shp_1FX", mats, col, "x", [-0.95, 0.95], ox + jhw + 0.02,
               L["top0"] + 0.46, 421, width=0.82, height=1.12, planter=True)
    # Shopfront: wide glazed opening under an awning, plus the door
    add_window("Shp_Front", mats, col, ox - 1.25, oy - hd + 0.02, gf + 0.26, 0,
               431, width=1.45, height=1.30, shutters=False, planter=False,
               pane_cols=4, pane_rows=4)
    add_door("Shp_Door", mats, col, ox + 1.30, oy - hd + 0.02, gf - 0.45, 0,
             441, ground=oz, width=1.10, canopy=False)
    aw = da.create_striped_awning("Shp_Awning", width=4.2, depth=1.45,
                                  mats=mats, seed=451, colour="blue",
                                  posts=False, height=2.30)
    aw.location = (ox, oy - hd + 0.02, gf - 0.45)
    _link(aw, col)
    add_sign("Shp_Sign", mats, col, ox + hw + 0.02, oy - 1.20, gf + 1.50, 90,
             461, emblem="disc", bw=0.88, bh=0.62)
    add_lantern("Shp_Lamp", mats, col, ox + hw + 0.02, oy + 0.5, gf + 1.26, 90, 463)
    cnt = bp.create_potion_counter_prop(
        "Shp_Counter", width=2.2, depth=0.72, height=0.88,
        timber_mat=mats["M_Timber_Aged"], plank_mat=mats["M_Wood_Planks"],
        potion_mats=[mats["M_Potion_Red"], mats["M_Potion_Blue"],
                     mats["M_Potion_Green"]])
    cnt.location = (ox - 1.25, oy - hd - 1.05, oz)
    _link(cnt, col)
    clutter("Shp", mats, col, [
        ("crate", ox + hw + 0.70, oy + 1.35, 11, 467),
        ("crate_small", ox + hw + 0.64, oy + 1.30, -16, 479),
        ("barrel", ox - hw - 0.64, oy - 0.8, 0, 487),
        ("flowerbox", ox + 1.2, oy - hd - 1.75, 0, 491)])
    return L


def build_blacksmith(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 4.4, 4.8
    L = build_structure("Bks", mats, col, o, w=w, d=d, base_h=1.0,
                        stone="fieldstone",
                        storey_h=(2.35,), jetty=0.0, roof_axis="y", pitch=44.0,
                        palette="shingle", seed=503, overhang=(0.55, 0.38),
                        chimney=[(-1.05, 0.55, 3.10, 1.15)])
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    window_row("Bks_WinY", mats, col, "y", [1.15], oy - hd + 0.02, gf + 0.40,
               509, width=0.86, height=1.05)
    window_row("Bks_WinX", mats, col, "x", [1.35], ox + hw + 0.02, gf + 0.40,
               521, width=0.86, height=1.05)
    add_door("Bks_Door", mats, col, ox + hw + 0.02, oy - 1.30, gf - 0.52, 90,
             523, ground=oz, width=1.15)
    # Open forge bay on the gable elevation, under a deep pentice
    forge, fire = bp.create_blacksmith_forge_hearth(
        "Bks_Forge", stone_mat=mats["M_Stone_Block_B"],
        ember_mat=mats["M_Fire_Embers"], iron_mat=mats["M_Iron_Aged"])
    forge.location = (ox - 1.05, oy - hd - 0.75, oz)
    _link(forge, col)
    fire.location = (ox - 1.05, oy - hd - 0.75, oz + 0.9)
    _link(fire, col)
    cp = dp.create_pentice_canopy("Bks_Pentice", width=2.6, depth=1.35,
                                  mats=mats, seed=541)
    cp.location = (ox - 1.05, oy - hd + 0.02, gf + 1.55)
    _link(cp, col)
    trough = bp.create_quenching_trough(
        "Bks_Trough", length=1.35, width=0.62, height=0.58,
        timber_mat=mats["M_Timber_Aged"], water_mat=mats["M_Water"],
        iron_mat=mats["M_Iron_Aged"])
    trough.location = (ox + 1.30, oy - hd - 0.95, oz)
    _link(trough, col)
    add_sign("Bks_Sign", mats, col, ox + hw + 0.02, oy + 1.55, gf + 1.45, 90,
             547, emblem="disc", bw=0.76, bh=0.58)
    add_lantern("Bks_Lamp", mats, col, ox + hw + 0.02, oy - 0.10, gf + 1.30, 90, 557)
    clutter("Bks", mats, col, [
        ("firewood", ox - hw - 0.36, oy + 0.4, -90, 563),
        ("barrel", ox + hw + 0.66, oy + 0.55, 0, 569),
        ("crate", ox + hw + 0.74, oy - 2.35, -18, 571),
        ("crate_small", ox - 1.9, oy - hd - 1.75, 24, 577)])
    return L


def build_stables(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 6.4, 4.6
    L = build_structure("Stb", mats, col, o, w=w, d=d, base_h=0.75,
                        stone="fieldstone",
                        storey_h=(2.15,), jetty=0.0, roof_axis="x", pitch=45.0,
                        palette="thatch", seed=601, overhang=(0.58, 0.40),
                        chimney=None)
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    # Stall doors: three half-doors along the long elevation
    for i, sx in enumerate((-1.95, 0.0, 1.95)):
        dr = dp.create_door_detailed(f"Stb_Stall_{i}", width=1.15, height=1.85,
                                     mats=mats, seed=611 + i * 7,
                                     speakeasy=False)
        dr.location = (ox + sx, oy - hd + 0.02, gf - 0.30)
        _link(dr, col)
        rail = bp.create_railing(f"Stb_Rail_{i}", length=1.05, height=0.62,
                                 timber_mat=mats["M_Timber_Aged"],
                                 iron_mat=mats["M_Iron_Aged"])
        rail.location = (ox + sx, oy - hd - 0.16, gf + 0.55)
        _link(rail, col)
    window_row("Stb_WinX", mats, col, "x", [-1.1, 1.1], ox + hw + 0.02,
               gf + 0.55, 631, width=0.78, height=0.92, planter=False)
    hoist = bp.create_hay_crane_hoist("Stb_Hoist", length=1.5,
                                      timber_mat=mats["M_Timber_Aged"],
                                      iron_mat=mats["M_Iron_Aged"])
    hoist.location = (ox + hw + 0.05, oy + 0.0, L["eaves"] + 0.55)
    hoist.rotation_euler = (0, 0, radians(90))
    _link(hoist, col)
    for i, (hx, hy) in enumerate([(hw + 0.85, -1.5), (hw + 0.80, -0.75)]):
        hay = bp.create_hay_bale(f"Stb_Hay_{i}", width=0.78, length=1.25,
                                 height=0.58, straw_mat=mats["M_Straw"])
        hay.location = (ox + hx, oy + hy, oz)
        hay.rotation_euler = (0, 0, radians(12 * (i + 1)))
        _link(hay, col)
    fen = bp.create_fence_section("Stb_Fence", length=3.0, height=0.95,
                                  timber_mat=mats["M_Timber_Aged"])
    fen.location = (ox - 1.0, oy - hd - 1.55, oz)
    _link(fen, col)
    add_lantern("Stb_Lamp", mats, col, ox - 3.05, oy - hd + 0.02, gf + 1.22, 0, 641)
    clutter("Stb", mats, col, [
        ("barrel_open", ox + hw + 0.68, oy + 1.55, 0, 643),
        ("crate", ox - hw - 0.72, oy + 0.4, 15, 647),
        ("firewood", ox + 2.6, oy - hd - 1.05, 0, 653)])
    return L


def build_warehouse(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 4.8, 6.0
    L = build_structure("Wrh", mats, col, o, w=w, d=d, base_h=1.05,
                        stone="fieldstone",
                        storey_h=(2.0, 2.0), jetty=0.0, roof_axis="y",
                        pitch=50.0, palette="slate", seed=701,
                        overhang=(0.42, 0.34), chimney=None)
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    # Cargo doors: a tall double opening on the gable end
    for sgn in (-1, 1):
        dr = dp.create_door_detailed(f"Wrh_Cargo_{sgn}", width=1.05,
                                     height=2.45, mats=mats,
                                     seed=711 + (0 if sgn < 0 else 9),
                                     speakeasy=False)
        dr.location = (ox + sgn * 0.56, oy - hd + 0.02, gf - 0.55)
        _link(dr, col)
    st = dp.create_stone_steps_detailed("Wrh_Steps", mats=mats, seed=721,
                                        width=2.5, depth=1.1, height=0.50,
                                        n_steps=3)
    st.location = (ox, oy - hd - 0.05, oz)
    _link(st, col)
    # Loading door and hoist at first floor
    dr2 = dp.create_door_detailed("Wrh_Loft", width=1.20, height=1.85,
                                  mats=mats, seed=731, speakeasy=False)
    dr2.location = (ox, oy - hd + 0.02, L["top0"] + 0.18)
    _link(dr2, col)
    hoist = dp.create_timber_frame("Wrh_Hoist", [
        {"p0": (ox, oy - hd - 0.10, L["eaves"] + L["pitch_h"] - 0.60),
         "p1": (ox, oy - hd - 1.25, L["eaves"] + L["pitch_h"] - 0.48),
         "w": 0.17, "d": 0.17, "chips": 3, "pegs": [0.12]},
        {"p0": (ox - 0.02, oy - hd - 0.72, L["eaves"] + L["pitch_h"] - 0.56),
         "p1": (ox - 0.02, oy - hd - 0.14, L["eaves"] + L["pitch_h"] - 1.35),
         "w": 0.11, "d": 0.12, "chips": 2}], mats=mats, seed=741)
    _link(hoist, col)
    blk = dp.create_lantern_bracket("Wrh_Block", mats=mats, seed=743,
                                    reach=0.16, lantern=False)
    blk.location = (ox, oy - hd - 1.15, L["eaves"] + L["pitch_h"] - 0.64)
    blk.rotation_euler = (radians(90), 0, 0)
    _link(blk, col)
    for i, sgn in enumerate((-1, 1)):
        vent = dp.create_window_detailed(f"Wrh_Vent_{i}", width=0.58,
                                         height=0.62, mats=mats,
                                         seed=745 + i * 7, shutters=True,
                                         shutter_open=False, planter=False,
                                         stone_sill=False, pane_cols=2,
                                         pane_rows=2, glow="dim")
        vent.location = (ox + sgn * 1.35, oy - hd + 0.02, L["top0"] + 1.05)
        _link(vent, col)
    window_row("Wrh_WinX", mats, col, "x", [-1.6, 0.4, 2.1], ox + hw + 0.02,
               gf + 0.45, 751, width=0.76, height=0.94, planter=False)
    window_row("Wrh_1FX", mats, col, "x", [-1.2, 1.2], ox + hw + 0.02,
               L["top0"] + 0.55, 761, width=0.76, height=1.00, planter=False)
    add_lantern("Wrh_Lamp", mats, col, ox + hw + 0.02, oy - 2.2, gf + 1.30, 90, 769)
    add_ivy("Wrh_Ivy", mats, col, ox + hw + 0.02, oy + hd + 0.02, oz + 0.10,
            90, 773, h=3.2, w=1.0, corner=True, stems=3)
    clutter("Wrh", mats, col, [
        ("crate", ox + hw + 0.78, oy - 0.7, 10, 787),
        ("crate_small", ox + hw + 0.72, oy - 0.65, -14, 797),
        ("crate", ox + hw + 1.48, oy - 1.3, -20, 809),
        ("barrel", ox - hw - 0.66, oy + 1.5, 0, 811),
        ("barrel", ox - hw - 0.66, oy + 2.2, 0, 821)])
    cart = bp.create_handcart("Wrh_Cart", timber_mat=mats["M_Timber_Aged"],
                              iron_mat=mats["M_Iron_Aged"])
    cart.location = (ox + hw + 1.55, oy + 1.2, oz)
    cart.rotation_euler = (0, 0, radians(-65))
    _link(cart, col)
    return L


# =============================================================================
# 9-16  Monuments
# =============================================================================

def build_noble_manor(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 7.0, 7.8
    L = build_structure("Mnr", mats, col, o, w=w, d=d, base_h=1.25,
                        storey_h=(2.1, 2.2), jetty=0.20, roof_axis="y",
                        pitch=50.0, palette="slate", seed=901,
                        overhang=(0.46, 0.36),
                        chimney=[(-1.7, -2.3, 3.10, 1.00),
                                 (-1.7, 2.3, 2.90, 0.94)])
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    jhw, jhd = L["w"] * 0.5, L["d"] * 0.5
    window_row("Mnr_GFY", mats, col, "y", [-2.3, -0.75, 0.9, 2.4],
               oy - hd + 0.02, gf + 0.40, 911, width=0.88, height=1.25)
    window_row("Mnr_1FY", mats, col, "y", [-2.4, -0.8, 0.85, 2.45],
               oy - jhd + 0.02, L["top0"] + 0.55, 921, width=0.86, height=1.30,
               planter=True)
    window_row("Mnr_GFX", mats, col, "x", [-2.2, 1.9], ox + hw + 0.02,
               gf + 0.40, 931, width=0.88, height=1.25)
    window_row("Mnr_1FX", mats, col, "x", [-2.3, -0.7, 0.9, 2.5],
               ox + jhw + 0.02, L["top0"] + 0.55, 941, width=0.86, height=1.30,
               planter=True)
    add_door("Mnr_Door", mats, col, ox + 0.05, oy - hd + 0.02, gf - 0.72, 0,
             951, ground=oz, width=1.35, height=2.35, canopy=False)
    cp = dp.create_pentice_canopy("Mnr_Porch", width=2.5, depth=1.25,
                                  mats=mats, seed=953)
    cp.location = (ox + 0.05, oy - hd + 0.02, gf + 1.85)
    _link(cp, col)
    # Corner stair turret
    tw = da.create_round_tower("Mnr_Turret", radius=1.15,
                               height=L["eaves"] - oz + 0.85, mats=mats,
                               seed=961, course_h=0.30, arrow_slits=2,
                               string_courses=(L["top0"] - oz,))
    tw.location = (ox - hw - 0.35, oy - hd - 0.35, oz)
    _link(tw, col)
    cap = da.create_conical_roof("Mnr_Turret_Cap", radius=1.42, height=1.85,
                                 mats=mats, seed=967, palette="slate")
    cap.location = (ox - hw - 0.35, oy - hd - 0.35, L["eaves"] + 0.85)
    _link(cap, col)
    for i, sgn in enumerate((-1, 1)):
        ban = da.create_banner(f"Mnr_Banner_{i}", width=0.80, height=2.15,
                               mats=mats, seed=971 + i * 5,
                               colour="blue" if i else "red")
        ban.location = (ox + sgn * 1.55, oy - jhd - 0.04, L["top0"] + 0.28)
        _link(ban, col)
    bal = bp.create_balcony_unit("Mnr_Balcony", width=2.6, depth=1.05,
                                 timber_mat=mats["M_Timber_Aged"],
                                 plank_mat=mats["M_Wood_Planks"])
    bal.location = (ox + jhw + 0.02, oy + 0.9, L["top0"] + 0.05)
    bal.rotation_euler = (0, 0, radians(90))
    _link(bal, col)
    add_ivy("Mnr_Ivy", mats, col, ox + hw + 0.02, oy + hd + 0.02, oz + 0.10,
            90, 977, h=3.8, w=1.1, corner=True, stems=4, density=1.2)
    clutter("Mnr", mats, col, [
        ("garden", ox + 2.3, oy - hd - 0.70, 0, 983),
        ("garden", ox - 2.3, oy - hd - 0.70, 0, 991),
        ("bench", ox + hw + 0.75, oy - 2.2, 90, 997),
        ("flowerbox", ox - 0.05, oy - hd - 1.95, 0, 1009)])
    for i, (px, py) in enumerate([(-hw - 1.2, 2.1), (hw + 1.3, 3.0)]):
        tr = bp.create_stylized_tree(f"Mnr_Tree_{i}", tree_type="oak",
                                     trunk_mat=mats["M_Bark"],
                                     foliage_mat=mats["M_Leaf_Spring"])
        tr.location = (ox + px, oy + py, oz)
        _link(tr, col)
    return L


def build_guildhouse(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 5.8, 7.4
    L = build_structure("Gld", mats, col, o, w=w, d=d, base_h=1.15,
                        storey_h=(2.0, 2.0, 1.8), jetty=0.17, roof_axis="y",
                        pitch=52.0, palette="clay", seed=1021,
                        overhang=(0.44, 0.34),
                        chimney=[(-1.35, 2.2, 2.80, 0.92)])
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    j2w, j2d = L["w"] * 0.5, L["d"] * 0.5
    j1w = (w + 0.34) * 0.5
    window_row("Gld_GFY", mats, col, "y", [-1.55, 1.55], oy - hd + 0.02,
               gf + 0.42, 1031, width=0.92, height=1.28)
    window_row("Gld_1FY", mats, col, "y", [-1.65, 0.0, 1.65],
               oy - (d + 0.34) * 0.5 + 0.02, L["top0"] + 0.48, 1041,
               width=0.84, height=1.22, planter=True)
    window_row("Gld_2FY", mats, col, "y", [-1.7, 0.0, 1.7], oy - j2d + 0.02,
               L["top1"] + 0.42, 1051, width=0.82, height=1.12, planter=True)
    window_row("Gld_GFX", mats, col, "x", [-2.1, -0.4, 1.4, 2.9],
               ox + hw + 0.02, gf + 0.42, 1061, width=0.86, height=1.28)
    window_row("Gld_2FX", mats, col, "x", [-2.0, -0.5, 1.2, 2.6],
               ox + j2w + 0.02, L["top1"] + 0.42, 1071, width=0.82,
               height=1.12, planter=True)
    add_door("Gld_Door", mats, col, ox, oy - hd + 0.02, gf - 0.66, 0, 1081,
             ground=oz, width=1.30, height=2.30)
    for i, sgn in enumerate((-1, 1)):
        ban = da.create_banner(f"Gld_Banner_{i}", width=0.82, height=2.25,
                               mats=mats, seed=1091 + i * 7,
                               colour="blue" if i else "red")
        ban.location = (ox + sgn * 1.30, oy - j2d - 0.04, L["top1"] + 0.24)
        _link(ban, col)
    ban3 = da.create_banner("Gld_Banner_X", width=0.78, height=2.0, mats=mats,
                            seed=1103, colour="cream")
    ban3.location = (ox + j2w + 0.06, oy + 0.5, L["top1"] + 0.24)
    ban3.rotation_euler = (0, 0, radians(90))
    _link(ban3, col)
    add_sign("Gld_Sign", mats, col, ox + hw + 0.02, oy - 2.8, gf + 1.55, 90,
             1109, emblem="disc", bw=0.95, bh=0.68)
    add_lantern("Gld_Lamp", mats, col, ox - 1.05, oy - hd + 0.02, gf + 1.45, 0, 1117)
    add_lantern("Gld_Lamp2", mats, col, ox + 1.05, oy - hd + 0.02, gf + 1.45, 0, 1123)
    add_ivy("Gld_Ivy", mats, col, ox - hw - 0.02, oy + hd + 0.02, oz + 0.10,
            180, 1129, h=3.4, w=1.0, corner=True, stems=3)
    clutter("Gld", mats, col, [
        ("flowerbox", ox - 2.0, oy - hd - 0.45, 0, 1151),
        ("flowerbox", ox + 2.0, oy - hd - 0.45, 0, 1153),
        ("bench", ox + hw + 0.72, oy + 1.9, 90, 1163),
        ("barrel", ox - hw - 0.66, oy - 1.4, 0, 1171)])
    return L


def build_chapel(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 4.6, 7.2
    L = build_structure("Chp", mats, col, o, w=w, d=d, base_h=0.85,
                        stone="ashlar",
                        storey_h=(3.35,), jetty=0.0, roof_axis="y", pitch=52.0,
                        palette="slate", seed=1201, overhang=(0.40, 0.32),
                        frame_style="stone", chimney=None, course_h=0.26)
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    for i, sy in enumerate((-2.0, -0.2, 1.6)):
        aw_ = da.create_arch_window(f"Chp_WinX_{i}", stone="ashlar", width=0.72, height=1.85,
                                    mats=mats, seed=1211 + i * 7, stained=True)
        aw_.location = (ox + hw + 0.02, oy + sy, gf + 0.85)
        aw_.rotation_euler = (0, 0, radians(90))
        _link(aw_, col)
    aw_f = da.create_arch_window("Chp_WinY", stone="ashlar", width=0.90, height=2.15,
                                 mats=mats, seed=1231, stained=True)
    aw_f.location = (ox, oy - hd + 0.02, gf + 0.95)
    _link(aw_f, col)
    for i, sy in enumerate((-2.9, -1.1, 0.7, 2.5)):
        bt = da.create_buttress(f"Chp_But_{i}", stone="ashlar", height=2.85, mats=mats,
                                seed=1241 + i * 5, width=0.50, projection=0.72)
        bt.location = (ox + hw + 0.02, oy + sy, oz)
        bt.rotation_euler = (0, 0, radians(90))
        _link(bt, col)
    # Bell gable over the west end
    bell = da.create_arch_portal("Chp_Bell", width=0.85, height=1.05,
                                 stone="ashlar",
                                 depth=0.42, mats=mats, seed=1251, gate=False,
                                 portcullis=False)
    bell.location = (ox, oy - hd - 0.02, L["eaves"] + L["pitch_h"] * 0.28)
    _link(bell, col)
    bl = dp.create_lantern_bracket("Chp_BellBody", mats=mats, seed=1259,
                                   reach=0.10, lantern=False)
    bl.location = (ox, oy - hd - 0.20, L["eaves"] + L["pitch_h"] * 0.28 + 0.78)
    bl.rotation_euler = (radians(90), 0, 0)
    _link(bl, col)
    add_door("Chp_Door", mats, col, ox, oy - hd + 0.02, gf - 0.42, 0, 1277,
             ground=oz, width=1.15, height=2.10, canopy=False)
    port = da.create_arch_portal("Chp_Portal", width=1.55, height=2.65,
                                 stone="ashlar",
                                 depth=0.62, mats=mats, seed=1279, gate=False,
                                 portcullis=False)
    port.location = (ox, oy - hd - 0.14, gf - 0.42)
    _link(port, col)
    add_ivy("Chp_Ivy", mats, col, ox - hw - 0.02, oy + hd + 0.02, oz + 0.10,
            180, 1283, h=3.0, w=1.0, corner=True, stems=3)
    clutter("Chp", mats, col, [
        ("garden", ox + hw + 1.35, oy - 2.6, 90, 1289),
        ("bench", ox - hw - 0.75, oy - 1.5, -90, 1291)])
    return L


def build_church(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 5.4, 8.6
    L = build_structure("Chu", mats, col, o, w=w, d=d, base_h=0.95,
                        stone="ashlar",
                        storey_h=(3.8,), jetty=0.0, roof_axis="y", pitch=54.0,
                        palette="slate", seed=1301, overhang=(0.42, 0.34),
                        frame_style="stone", chimney=None, course_h=0.28)
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    # West tower
    tw_w, tw_h = 3.0, 6.6
    tower_y = oy - hd - tw_w * 0.5 + 0.35
    build_structure("Chu_Tower", mats, col, (ox, tower_y, oz), w=tw_w, d=tw_w,
                    stone="ashlar",
                    base_h=1.0, storey_h=(tw_h,), jetty=0.0, roof=False,
                    frame_style="stone", seed=1311, gables=False,
                    course_h=0.28, ledge=True, deck=True)
    cren = da.create_crenellation("Chu_Cren", tw_w + 0.20, tw_w + 0.20,
                                  stone="ashlar",
                                  mats=mats, seed=1321, merlon=0.40, gap=0.32,
                                  height=0.58, thick=0.28)
    cren.location = (ox, tower_y, oz + 1.0 + tw_h)
    _link(cren, col)
    sp = da.create_spire("Chu_Spire", base=1.32, height=4.4, mats=mats,
                         seed=1331, palette="slate", lucarnes=2)
    sp.location = (ox, tower_y, oz + 1.0 + tw_h + 0.35)
    _link(sp, col)
    for i, sy in enumerate((-2.6, -0.5, 1.6, 3.4)):
        aw_ = da.create_arch_window(f"Chu_WinX_{i}", stone="ashlar", width=0.78, height=2.20,
                                    mats=mats, seed=1341 + i * 7, stained=True,
                                    gothic=True)
        aw_.location = (ox + hw + 0.02, oy + sy, gf + 1.05)
        aw_.rotation_euler = (0, 0, radians(90))
        _link(aw_, col)
        bt = da.create_buttress(f"Chu_But_{i}", stone="ashlar", height=3.2, mats=mats,
                                seed=1351 + i * 5, width=0.55, projection=0.85,
                                stages=2)
        bt.location = (ox + hw + 0.02, oy + sy + 1.05, oz)
        bt.rotation_euler = (0, 0, radians(90))
        _link(bt, col)
    # Tower openings
    for i, zf in enumerate((0.34, 0.72)):
        aw_ = da.create_arch_window(f"Chu_TowWin_{i}", stone="ashlar", width=0.60, height=1.35,
                                    mats=mats, seed=1361 + i * 7,
                                    stained=(i == 0), gothic=True)
        aw_.location = (ox, tower_y - tw_w * 0.5 - 0.02, oz + 1.0 + tw_h * zf)
        _link(aw_, col)
        aw2 = da.create_arch_window(f"Chu_TowWinX_{i}", stone="ashlar", width=0.60,
                                    height=1.35, mats=mats, seed=1371 + i * 7,
                                    stained=(i == 0), gothic=True)
        aw2.location = (ox + tw_w * 0.5 + 0.02, tower_y, oz + 1.0 + tw_h * zf)
        aw2.rotation_euler = (0, 0, radians(90))
        _link(aw2, col)
    port = da.create_arch_portal("Chu_Portal", width=1.75, height=3.05,
                                 stone="ashlar",
                                 depth=0.75, mats=mats, seed=1381, gate=True,
                                 portcullis=False)
    port.location = (ox, tower_y - tw_w * 0.5 - 0.10, oz + 1.0)
    _link(port, col)
    st = dp.create_stone_steps_detailed("Chu_Steps", mats=mats, seed=1391,
                                        stone="ashlar",
                                        width=2.6, depth=1.2, height=1.0,
                                        n_steps=4)
    st.location = (ox, tower_y - tw_w * 0.5 - 0.70, oz)
    _link(st, col)
    add_ivy("Chu_Ivy", mats, col, ox - hw - 0.02, oy + hd + 0.02, oz + 0.10,
            180, 1399, h=3.4, w=1.0, corner=True, stems=3)
    return L


def build_windmill(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    r, h = 2.15, 6.0
    tw = da.create_round_tower("Wml_Tower", radius=r, height=h, mats=mats,
                               stone="fieldstone",
                               seed=1409, course_h=0.30, batter=0.16,
                               arrow_slits=0, string_courses=(2.4, 4.4))
    tw.location = (ox, oy, oz)
    _link(tw, col)
    cap = da.create_conical_roof("Wml_Cap", radius=r * 0.90, height=2.15,
                                 mats=mats, seed=1423, palette="shingle",
                                 finial=True, flare=0.18)
    cap.location = (ox, oy, oz + h)
    _link(cap, col)
    sails = da.create_windmill_sails("Wml_Sails", mats=mats, seed=1427,
                                     length=3.5, blades=4)
    sails.location = (ox - 0.25, oy - r * 0.92, oz + h + 0.95)
    _link(sails, col)
    # Tail pole steadying the cap
    tail = dp.create_timber_frame("Wml_Tail", [
        {"p0": (ox + 0.10, oy + r * 0.55, oz + h + 0.60),
         "p1": (ox + 0.10, oy + r * 1.85, oz + 1.30),
         "w": 0.16, "d": 0.16, "chips": 3}], mats=mats, seed=1429)
    _link(tail, col)
    for i, zf in enumerate((0.28, 0.58, 0.80)):
        aw_ = da.create_arch_window(f"Wml_Win_{i}", stone="fieldstone", width=0.58, height=1.10,
                                    mats=mats, seed=1433 + i * 7,
                                    stained=False, tracery=False)
        ang = -pi * 0.5 + i * 0.7
        rr = r * (1.0 - 0.16 * zf)
        aw_.location = (ox + cos(ang) * rr, oy + sin(ang) * rr, oz + h * zf)
        aw_.rotation_euler = (0, 0, ang + pi * 0.5)
        _link(aw_, col)
    dr = dp.create_door_detailed("Wml_Door", width=1.10, height=2.05,
                                 mats=mats, seed=1439)
    dr.location = (ox + r * 0.94, oy + 0.15, oz + 0.18)
    dr.rotation_euler = (0, 0, radians(90))
    _link(dr, col)
    clutter("Wml", mats, col, [
        ("crate", ox + r + 1.05, oy - 1.0, 18, 1447),
        ("barrel", ox + r + 0.95, oy + 1.35, 0, 1451),
        ("barrel", ox + r + 1.55, oy + 1.55, 0, 1453)])
    for i in range(3):
        sk = bp.create_grain_sacks(f"Wml_Sacks_{i}", num_sacks=3,
                                   straw_mat=mats["M_Straw"])
        sk.location = (ox - r - 0.9 - i * 0.55, oy - 0.4 + i * 0.75, oz)
        _link(sk, col)
    return None


def build_watchtower(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, h = 4.0, 6.4
    L = build_structure("Wtc", mats, col, o, w=w, d=w, base_h=1.0,
                        stone="granite",
                        storey_h=(h,), jetty=0.0, roof=False, gables=False,
                        frame_style="stone", seed=1459, course_h=0.29,
                        deck=True)
    gf = L["gf"]
    top = L["eaves"]
    # Machicolated head: corbel course then merlons
    for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
        for i, c in enumerate(_spread(w * 0.5 - 0.30, 6)):
            cb = dp.create_corbel_bracket(f"Wtc_Corb_{ax}{sgn}_{i}", mats=mats,
                                          seed=1461 + i * 3, size=0.36,
                                          projection=0.26)
            if ax == 0:
                cb.location = (ox + sgn * (w * 0.5 - 0.02), oy + c, top - 0.50)
                cb.rotation_euler = (0, 0, radians(90 if sgn > 0 else -90))
            else:
                cb.location = (ox + c, oy + sgn * (w * 0.5 - 0.02), top - 0.50)
                cb.rotation_euler = (0, 0, radians(0 if sgn < 0 else 180))
            _link(cb, col)
    cren = da.create_crenellation("Wtc_Cren", w + 0.44, w + 0.44, mats=mats,
                                  stone="granite",
                                  seed=1471, merlon=0.44, gap=0.36,
                                  height=0.68, thick=0.32)
    cren.location = (ox, oy, top + 0.06)
    _link(cren, col)
    for i, zf in enumerate((0.26, 0.52, 0.78)):
        aw_ = da.create_arch_window(f"Wtc_Slit_{i}", stone="granite", width=0.40, height=1.15,
                                    mats=mats, seed=1481 + i * 5,
                                    stained=False, tracery=False)
        aw_.location = (ox, oy - w * 0.5 + 0.02, gf + h * zf)
        _link(aw_, col)
        aw2 = da.create_arch_window(f"Wtc_SlitX_{i}", stone="granite", width=0.40, height=1.15,
                                    mats=mats, seed=1487 + i * 5,
                                    stained=False, tracery=False)
        aw2.location = (ox + w * 0.5 + 0.02, oy + 0.4 - i * 0.5, gf + h * zf)
        aw2.rotation_euler = (0, 0, radians(90))
        _link(aw2, col)
    add_door("Wtc_Door", mats, col, ox + w * 0.5 + 0.02, oy - 1.0, gf - 0.55,
             90, 1493, ground=oz, width=1.05, height=2.0, canopy=False)
    ban = da.create_banner("Wtc_Banner", width=0.80, height=2.1, mats=mats,
                           seed=1499, colour="red")
    ban.location = (ox + 1.2, oy - w * 0.5 - 0.04, top - 1.35)
    _link(ban, col)
    add_ivy("Wtc_Ivy", mats, col, ox - w * 0.5 - 0.02, oy - w * 0.5 - 0.02,
            oz + 0.10, -90, 1511, h=3.3, w=1.0, corner=True, stems=4)
    clutter("Wtc", mats, col, [
        ("firewood", ox + w * 0.5 + 0.80, oy + 1.2, 90, 1523),
        ("barrel", ox - w * 0.5 - 0.66, oy + 0.7, 0, 1531),
        ("crate", ox + w * 0.5 + 0.80, oy - 2.2, -12, 1543)])
    return L


def build_gatehouse(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    gap, th, h = 3.2, 1.6, 4.6
    port = da.create_arch_portal("Gat_Portal", width=gap, height=h * 0.82,
                                 stone="granite",
                                 depth=th, mats=mats, seed=1549, gate=True,
                                 portcullis=True)
    port.location = (ox, oy, oz)
    _link(port, col)
    # Flanking towers
    for i, sgn in enumerate((-1, 1)):
        tw = da.create_round_tower(f"Gat_Tower_{i}", radius=1.35, height=h,
                                   stone="granite",
                                   mats=mats, seed=1553 + i * 7, course_h=0.30,
                                   batter=0.05, arrow_slits=2,
                                   string_courses=(h * 0.62,))
        tw.location = (ox + sgn * (gap * 0.5 + 1.25), oy, oz)
        _link(tw, col)
        cr = da.create_crenellation(f"Gat_Cren_{i}", 0, 0, mats=mats,
                                    stone="granite",
                                    seed=1567 + i * 5, merlon=0.40, gap=0.32,
                                    height=0.60, thick=0.30, round_plan=True,
                                    radius=1.38)
        cr.location = (ox + sgn * (gap * 0.5 + 1.25), oy, oz + h + 0.16)
        _link(cr, col)
    # Curtain head over the arch
    wall_h = h * 0.92
    _link(dp.create_masonry_box("Gat_Head", gap + 0.30, th, wall_h - h * 0.82 + 0.5,
                                stone="granite",
                                location=(ox, oy, oz + h * 0.82 - 0.5),
                                mats=mats, seed=1571, course_h=0.28,
                                block_len=(0.22, 0.58), shaded_faces=SHADED,
                                plinth=False, ledge=True, ground_moss=False,
                                weeds=False, moss_amount=0.12), col)
    cr = da.create_crenellation("Gat_Cren_Mid", gap + 0.34, th + 0.18,
                                stone="granite",
                                mats=mats, seed=1579, merlon=0.42, gap=0.34,
                                height=0.62, thick=0.28)
    cr.location = (ox, oy, oz + wall_h + 0.12)
    _link(cr, col)
    for i, sgn in enumerate((-1, 1)):
        ban = da.create_banner(f"Gat_Banner_{i}", width=0.76, height=1.85,
                               mats=mats, seed=1583 + i * 5,
                               colour="blue" if i else "red")
        ban.location = (ox + sgn * 0.95, oy - th * 0.5 - 0.04, oz + h * 0.86)
        _link(ban, col)
    add_ivy("Gat_Ivy", mats, col, ox - gap * 0.5 - 2.4, oy - th * 0.5 - 0.02,
            oz + 0.10, 0, 1597, h=2.4, w=0.9, stems=3)
    return None


def build_keep(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, h = 8.6, 7.0
    L = build_structure("Kep", mats, col, o, w=w, d=w, base_h=1.35,
                        stone="granite",
                        storey_h=(h,), jetty=0.0, roof=False, gables=False,
                        frame_style="stone", seed=1601, course_h=0.32,
                        deck=True)
    gf, top = L["gf"], L["eaves"]
    cren = da.create_crenellation("Kep_Cren", w + 0.34, w + 0.34, mats=mats,
                                  stone="granite",
                                  seed=1607, merlon=0.52, gap=0.40,
                                  height=0.78, thick=0.36)
    cren.location = (ox, oy, top + 0.08)
    _link(cren, col)
    # Corner turrets
    for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        tw = da.create_round_tower(f"Kep_Turret_{i}", radius=1.05, stone="granite",
                                   height=h + 1.9, mats=mats,
                                   seed=1609 + i * 7, course_h=0.30,
                                   batter=0.04, arrow_slits=2)
        tw.location = (ox + sx * (w * 0.5 - 0.10), oy + sy * (w * 0.5 - 0.10),
                       gf)
        _link(tw, col)
        cr = da.create_crenellation(f"Kep_TCren_{i}", 0, 0, mats=mats,
                                    stone="granite",
                                    seed=1613 + i * 5, merlon=0.36, gap=0.28,
                                    height=0.52, thick=0.26, round_plan=True,
                                    radius=1.08)
        cr.location = (ox + sx * (w * 0.5 - 0.10), oy + sy * (w * 0.5 - 0.10),
                       gf + h + 1.9 + 0.14)
        _link(cr, col)
    for i, zf in enumerate((0.24, 0.50, 0.76)):
        for j, sx in enumerate((-1.9, 0.0, 1.9)):
            aw_ = da.create_arch_window(f"Kep_Win_{i}_{j}", stone="granite", width=0.48,
                                        height=1.30, mats=mats,
                                        seed=1621 + i * 11 + j * 3,
                                        stained=False, tracery=False)
            aw_.location = (ox + sx, oy - w * 0.5 + 0.02, gf + h * zf)
            _link(aw_, col)
            aw2 = da.create_arch_window(f"Kep_WinX_{i}_{j}", stone="granite", width=0.48,
                                        height=1.30, mats=mats,
                                        seed=1657 + i * 11 + j * 3,
                                        stained=False, tracery=False)
            aw2.location = (ox + w * 0.5 + 0.02, oy + sx, gf + h * zf)
            aw2.rotation_euler = (0, 0, radians(90))
            _link(aw2, col)
    port = da.create_arch_portal("Kep_Portal", width=1.75, height=2.85,
                                 stone="granite",
                                 depth=0.85, mats=mats, seed=1667, gate=True,
                                 portcullis=True)
    port.location = (ox, oy - w * 0.5 - 0.12, gf - 0.70)
    _link(port, col)
    st = dp.create_stone_steps_detailed("Kep_Steps", mats=mats, seed=1669,
                                        stone="granite",
                                        width=2.7, depth=1.5, height=0.70,
                                        n_steps=4)
    st.location = (ox, oy - w * 0.5 - 0.80, oz)
    _link(st, col)
    for i, sgn in enumerate((-1, 1)):
        ban = da.create_banner(f"Kep_Banner_{i}", width=0.86, height=2.4,
                               mats=mats, seed=1693 + i * 5,
                               colour="blue" if i else "red")
        ban.location = (ox + sgn * 2.7, oy - w * 0.5 - 0.04, top - 1.75)
        _link(ban, col)
    add_ivy("Kep_Ivy", mats, col, ox + w * 0.5 + 0.02, oy + w * 0.5 + 0.02,
            oz + 0.10, 90, 1697, h=3.8, w=1.1, corner=True, stems=4,
            density=1.2)
    clutter("Kep", mats, col, [
        ("crate", ox + w * 0.5 + 0.9, oy - 2.0, 14, 1699),
        ("barrel", ox + w * 0.5 + 0.85, oy + 1.4, 0, 1709),
        ("firewood", ox - w * 0.5 - 0.40, oy - 1.0, -90, 1721)])
    return L


# =============================================================================
# 17-20  Townhouse states
# =============================================================================

def _variation_shell(tag, mats, col, o, seed, damage=1.0, roof=True,
                     palette="clay"):
    ox, oy, oz = o
    w, d = 4.4, 5.2
    return build_structure(tag, mats, col, o, w=w, d=d, base_h=1.0,
                           storey_h=(1.5, 2.1), jetty=0.17, roof_axis="y",
                           pitch=48.0, palette=palette, seed=seed,
                           overhang=(0.44, 0.34), roof=roof,
                           chimney=[(-0.50, -1.55, 2.70, 0.92)] if roof else None)


def build_var_normal(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    L = _variation_shell("VarN", mats, col, o, 1801)
    hw, hd, gf = 2.2, 2.6, L["gf"]
    jhw, jhd = L["w"] * 0.5, L["d"] * 0.5
    window_row("VarN_GFY", mats, col, "y", [-1.25, 1.25], oy - hd + 0.02,
               gf + 0.32, 1811, width=0.86, height=1.05)
    window_row("VarN_1FY", mats, col, "y", [-1.15, 1.15], oy - jhd + 0.02,
               L["top0"] + 0.50, 1821, width=0.84, height=1.14, planter=True)
    window_row("VarN_1FX", mats, col, "x", [-1.4, 0.3, 1.9], ox + jhw + 0.02,
               L["top0"] + 0.50, 1831, width=0.82, height=1.14, planter=True)
    add_door("VarN_Door", mats, col, ox + hw + 0.02, oy - 1.0, gf - 0.52, 90,
             1841, ground=oz)
    add_lantern("VarN_Lamp", mats, col, ox + hw + 0.02, oy + 0.2, gf + 1.24, 90, 1847)
    add_ivy("VarN_Ivy", mats, col, ox - hw - 0.02, oy - hd - 0.02, oz + 0.10,
            -90, 1861, h=3.1, w=1.0, corner=True, stems=3)
    clutter("VarN", mats, col, [
        ("garden", ox - 0.9, oy - hd - 0.62, 0, 1867),
        ("bench", ox + hw + 0.70, oy + 1.5, 90, 1871),
        ("barrel", ox + hw + 0.64, oy + 2.4, 0, 1873)])
    return L


def build_var_with_stall(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    L = _variation_shell("VarS", mats, col, o, 1877)
    hw, hd, gf = 2.2, 2.6, L["gf"]
    jhw, jhd = L["w"] * 0.5, L["d"] * 0.5
    window_row("VarS_1FY", mats, col, "y", [-1.15, 1.15], oy - jhd + 0.02,
               L["top0"] + 0.50, 1879, width=0.84, height=1.14, planter=True)
    window_row("VarS_1FX", mats, col, "x", [-1.4, 0.3, 1.9], ox + jhw + 0.02,
               L["top0"] + 0.50, 1889, width=0.82, height=1.14, planter=True)
    add_window("VarS_Shopfront", mats, col, ox - 0.95, oy - hd + 0.02,
               gf + 0.24, 0, 1901, width=1.40, height=1.25, shutters=False,
               planter=False, pane_cols=4, pane_rows=4)
    add_door("VarS_Door", mats, col, ox + 1.45, oy - hd + 0.02, gf - 0.52, 0,
             1907, ground=oz, width=1.05, canopy=False)
    aw = da.create_striped_awning("VarS_Awning", width=3.6, depth=1.55,
                                  mats=mats, seed=1913, colour="blue",
                                  posts=True, height=2.32)
    aw.location = (ox - 0.15, oy - hd + 0.02, gf - 0.52)
    _link(aw, col)
    stall = bp.create_market_stall_awning(
        "VarS_Stall", width=2.2, depth=1.4, height=2.1,
        stripe_mat=mats["M_Awning_Blue"], timber_mat=mats["M_Timber_Aged"])
    stall.location = (ox + hw + 1.35, oy - 0.4, oz)
    stall.rotation_euler = (0, 0, radians(90))
    _link(stall, col)
    add_sign("VarS_Sign", mats, col, ox + hw + 0.02, oy - 1.9, gf + 1.40, 90,
             1931, emblem="disc")
    clutter("VarS", mats, col, [
        ("crate", ox + hw + 0.72, oy + 1.5, 12, 1933),
        ("crate_small", ox + hw + 0.66, oy + 1.45, -18, 1949),
        ("barrel_open", ox - hw - 0.66, oy - 1.1, 0, 1951),
        ("flowerbox", ox + 1.5, oy - hd - 1.85, 0, 1973)])
    return L


def build_var_damaged(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    L = _variation_shell("VarD", mats, col, o, 1979)
    hw, hd, gf = 2.2, 2.6, L["gf"]
    jhw, jhd = L["w"] * 0.5, L["d"] * 0.5
    window_row("VarD_GFY", mats, col, "y", [-1.25], oy - hd + 0.02, gf + 0.32,
               1987, width=0.86, height=1.05, shutter_open=False, glow="dim")
    window_row("VarD_1FY", mats, col, "y", [1.15], oy - jhd + 0.02,
               L["top0"] + 0.50, 1993, width=0.84, height=1.14, planter=False)
    add_door("VarD_Door", mats, col, ox + hw + 0.02, oy - 1.0, gf - 0.52, 90,
             1997, ground=oz, canopy=False)
    # Boarded openings and a collapsed corner
    for i, (bx, bz) in enumerate([(1.25, gf + 0.32), (-1.15, L["top0"] + 0.50)]):
        for j in range(3):
            bd = bp.create_box(f"VarD_Board_{i}_{j}", size=(1.15, 0.07, 0.17),
                               location=(ox + bx, oy - hd - 0.05,
                                         bz + 0.25 + j * 0.34),
                               material=mats["M_Wood_Planks"], bevel=0.012)
            bd.rotation_euler = (0, radians(6 - j * 5), 0)
            _link(bd, col)
    rub = bp.create_ruin_wall("VarD_Rubble", width=1.9, height=1.25,
                              stone_mat=mats["M_Stone_Block_B"],
                              foliage_mat=mats["M_Moss"])
    rub.location = (ox - hw - 0.55, oy + 1.5, oz)
    rub.rotation_euler = (0, 0, radians(-90))
    _link(rub, col)
    for i, (px, py) in enumerate([(-hw - 1.0, 0.6), (-hw - 0.7, -1.2),
                                  (hw + 0.9, 2.2)]):
        rk = bp.create_rock_boulder(f"VarD_Rock_{i}", size=(0.7, 0.55, 0.42),
                                    stone_mat=mats["M_Stone_Block_B"])
        rk.location = (ox + px, oy + py, oz)
        _link(rk, col)
    # Collapsed roof: a bare rafter cage where the tiles have gone
    rafters = []
    for i, rx in enumerate([-1.35, -0.95, -0.55, -0.15, 0.25]):
        rafters.append({"p0": (ox + rx, oy - jhd + 0.25, L["eaves"] + 0.05),
                        "p1": (ox + rx * 0.18, oy - jhd + 0.25,
                               L["eaves"] + L["pitch_h"] - 0.12),
                        "w": 0.11, "d": 0.12, "chips": 3, "moss": True})
        rafters.append({"p0": (ox + rx, oy - jhd + 1.35, L["eaves"] + 0.05),
                        "p1": (ox + rx * 0.18, oy - jhd + 1.35,
                               L["eaves"] + L["pitch_h"] - 0.12),
                        "w": 0.10, "d": 0.11, "chips": 3})
    rafters.append({"p0": (ox - 1.5, oy - jhd + 0.15, L["eaves"] + 1.15),
                    "p1": (ox - 1.5, oy - jhd + 1.55, L["eaves"] + 1.15),
                    "w": 0.12, "d": 0.12, "chips": 4, "moss": True})
    _link(dp.create_timber_frame("VarD_Rafters", rafters, mats=mats,
                                 seed=2005), col)
    # Fallen tiles and timber heaped under the breach
    for i in range(14):
        ang = 2011 + i * 13
        tx = ox - 2.1 + (i % 5) * 0.42 + (0.11 * (i % 3))
        ty = oy - hd - 0.55 - 0.32 * (i % 3)
        tl = bp.create_box(f"VarD_Fallen_{i}", size=(0.30, 0.26, 0.055),
                           location=(tx, ty, 0.03 + 0.05 * (i % 3)),
                           material=mats["M_Tile_Aged"], bevel=0.008)
        tl.rotation_euler = (radians(6 * (i % 4)), radians(4 * (i % 3)),
                             radians(17 * i))
        _link(tl, col)
    _link(dp.create_timber_frame("VarD_Debris", [
        {"p0": (ox - 2.3, oy - hd - 1.0, 0.06),
         "p1": (ox - 0.7, oy - hd - 0.35, 0.72), "w": 0.15, "d": 0.14,
         "chips": 4, "moss": True},
        {"p0": (ox - 1.8, oy - hd - 1.25, 0.06),
         "p1": (ox - 0.2, oy - hd - 0.95, 0.42), "w": 0.13, "d": 0.13,
         "chips": 4}], mats=mats, seed=2009), col)

    add_ivy("VarD_Ivy", mats, col, ox - hw - 0.02, oy - hd - 0.02, oz + 0.10,
            -90, 2011, h=3.3, w=1.1, corner=True, stems=4, density=1.35)
    add_ivy("VarD_Ivy2", mats, col, ox + hw + 0.02, oy + 1.9, oz + 0.35, 90,
            2017, h=2.4, w=0.9, stems=3, density=1.2)
    clutter("VarD", mats, col, [
        ("crate", ox + hw + 0.76, oy - 2.3, 26, 2027),
        ("barrel", ox - hw - 0.70, oy - 2.0, 0, 2029)])
    return L


def build_var_ruin(mats, col, o=(0, 0, 0)):
    ox, oy, oz = o
    w, d = 4.4, 5.2
    # Only the foundation and a broken ground storey survive
    L = build_structure("VarR", mats, col, o, w=w, d=d, base_h=0.95,
                        stone="fieldstone",
                        storey_h=(), jetty=0.0, roof=False, gables=False,
                        frame_style="stone", seed=2039, course_h=0.24,
                        deck=True)
    hw, hd, gf = w * 0.5, d * 0.5, L["gf"]
    for i, (rw, rh, rx, ry, rr) in enumerate([
            (2.6, 3.1, -0.6, -hd - 0.02, 0),
            (1.3, 1.5, 1.5, -hd - 0.02, 0),
            (3.4, 2.5, hw + 0.02, 0.4, 90),
            (2.0, 1.2, hw + 0.02, -2.0, 90),
            (2.4, 1.9, -0.2, hd + 0.02, 180),
            (2.8, 2.7, -hw - 0.02, -0.3, -90)]):
        rn = bp.create_ruin_wall(f"VarR_Wall_{i}", width=rw, height=rh,
                                 stone_mat=mats["M_Stone_Block_B"],
                                 foliage_mat=mats["M_Moss"])
        rn.location = (ox + rx, oy + ry, gf)
        rn.rotation_euler = (0, 0, radians(rr))
        _link(rn, col)
    for i, (px, py, ph) in enumerate([(-1.5, -1.2, 1.7), (1.6, 1.9, 1.15)]):
        pl = bp.create_ruined_pillar(f"VarR_Pillar_{i}", height=ph,
                                     stone_mat=mats["M_Stone_Block_C"],
                                     foliage_mat=mats["M_Moss"])
        pl.location = (ox + px, oy + py, gf)
        _link(pl, col)
    for i, (px, py, sz) in enumerate([(-2.3, 0.9, 0.8), (0.4, -2.4, 0.62),
                                      (2.4, -1.3, 0.72), (-0.9, 2.5, 0.55),
                                      (1.9, 2.2, 0.9)]):
        rk = bp.create_rock_boulder(f"VarR_Rock_{i}",
                                    size=(sz, sz * 0.78, sz * 0.55),
                                    stone_mat=mats["M_Stone_Block_B"])
        rk.location = (ox + px, oy + py, oz)
        _link(rk, col)
    bm_ = dp.create_timber_frame("VarR_Beams", [
        {"p0": (ox - 1.7, oy + 0.3, gf + 0.05),
         "p1": (ox + 0.9, oy - 1.4, gf + 1.35), "w": 0.19, "d": 0.18,
         "chips": 4, "moss": True},
        {"p0": (ox + 1.4, oy + 1.5, gf + 0.05),
         "p1": (ox - 0.2, oy + 2.1, gf + 0.95), "w": 0.17, "d": 0.16,
         "chips": 4, "moss": True}], mats=mats, seed=2053)
    _link(bm_, col)
    for i, (px, py) in enumerate([(-1.0, -0.5), (1.2, 0.9), (0.1, 2.0)]):
        add_ivy(f"VarR_Ivy_{i}", mats, col, ox + px, oy + py, gf, 0,
                2063 + i * 7, h=1.5, w=0.9, stems=2, density=1.4)
    for i, (px, py) in enumerate([(-2.0, -2.0), (2.1, 2.3)]):
        gb = dp.create_garden_bed(f"VarR_Growth_{i}", mats=mats,
                                  seed=2069 + i * 5, width=1.3, depth=0.7,
                                  edging="stone")
        gb.location = (ox + px, oy + py, oz)
        _link(gb, col)
    return L


def build_lighthouse(mats, col, o=(0, 0, 0)):
    """Estuary lighthouse - the hero landmark on the island SW of the harbor.

    Sea-battered fieldstone socle, granite shaft with a hard batter, corbelled
    gallery, glazed lamp room and a slate cap. Total height ~14 m, which makes
    it the tallest thing in the city and readable from the Lower City quay.
    """
    ox, oy, oz = o
    sr, sh = 3.30, 1.15          # socle
    tr, th = 2.30, 8.80          # shaft
    tr_top = tr * (1.0 - 0.34)   # 1.52 - gallery corbels out from here

    # Socle: wider, rougher, taking the weather off the water
    soc = da.create_round_tower("Lig_Socle", radius=sr, height=sh, mats=mats,
                                stone="fieldstone", seed=1601, course_h=0.34,
                                batter=0.22, moss=True, weeds=True)
    soc.location = (ox, oy, oz)
    _link(soc, col)

    # Shaft
    sft = da.create_round_tower("Lig_Shaft", radius=tr, height=th, mats=mats,
                                stone="granite", seed=1607, course_h=0.29,
                                batter=0.34, moss=True, weeds=False,
                                string_courses=(2.60, 5.60))
    sft.location = (ox, oy, oz + sh)
    _link(sft, col)

    # Gallery + lamp room + cap
    lamp = da.create_lighthouse_lamp("Lig_Lamp", radius=1.30, height=1.95,
                                     mats=mats, seed=1613, gallery=2.05,
                                     posts=8, stone="granite")
    lamp.location = (ox, oy, oz + sh + th)
    _link(lamp, col)
    cap = da.create_conical_roof("Lig_Cap", radius=1.46, height=1.55,
                                 mats=mats, seed=1619, palette="slate",
                                 finial=True, flare=0.16)
    cap.location = (ox, oy, oz + sh + th + 2.51)
    _link(cap, col)

    # Lights spiralling up the stair inside the shaft
    for i, zf in enumerate((0.20, 0.40, 0.60, 0.80)):
        za = th * zf
        ang = -pi * 0.5 + i * 1.15
        rr = tr * (1.0 - 0.34 * (za / th))
        aw_ = da.create_arch_window(f"Lig_Win_{i}", width=0.54, height=1.05,
                                    mats=mats, seed=1621 + i * 7,
                                    stained=False, tracery=False,
                                    stone="granite")
        aw_.location = (ox + cos(ang) * rr, oy + sin(ang) * rr, oz + sh + za)
        aw_.rotation_euler = (0, 0, ang + pi * 0.5)
        _link(aw_, col)

    # Door on the -Y front, up three worn steps off the rock
    add_door("Lig_Door", mats, col, ox, oy - tr - 0.02, oz + sh, 0, 1637,
             ground=oz + sh, width=1.08, height=2.05, canopy=False)
    st = dp.create_stone_steps_detailed("Lig_Steps", mats=mats, seed=1643,
                                        width=1.60, depth=1.05, height=sh,
                                        n_steps=4, kerbs=False,
                                        stone="fieldstone")
    st.location = (ox, oy - tr - 0.55, oz)
    _link(st, col)

    # Bracket lantern beside the door, for the keeper coming up in the dark
    lb = dp.create_lantern_bracket("Lig_Bracket", mats=mats, seed=1649,
                                   reach=0.46, lantern=True, lit=True)
    lb.location = (ox + 0.92, oy - tr + 0.18, oz + sh + 1.95)
    lb.rotation_euler = (0, 0, radians(-14))
    _link(lb, col)

    # Weathering on the shaded flanks
    add_ivy("Lig_Ivy", mats, col, ox - sr * 0.72, oy + sr * 0.52, oz + 0.08,
            -50, 1657, h=2.4, w=1.2, corner=False, stems=3)

    # Keeper's clutter at the foot
    clutter("Lig", mats, col, [
        ("barrel", ox + sr + 0.55, oy - 0.85, 0, 1663),
        ("barrel", ox + sr + 0.50, oy + 0.30, 0, 1667),
        ("crate", ox - sr - 0.70, oy - 1.30, 22, 1669),
        ("firewood", ox - sr - 0.60, oy + 0.95, 74, 1693)])
    return None


ALL_BUILDINGS = [
    ("bld_cottage", "01_Cottage", build_cottage),
    ("bld_townhouse", "02_Townhouse", build_townhouse),
    ("bld_tenement", "03_Tenement", build_tenement),
    ("bld_tavern", "04_Tavern", build_tavern),
    ("bld_shop", "05_Shop", build_shop),
    ("bld_blacksmith", "06_Blacksmith", build_blacksmith),
    ("bld_stables", "07_Stables", build_stables),
    ("bld_warehouse", "08_Warehouse", build_warehouse),
    ("monument_noble_manor", "09_Noble_Manor", build_noble_manor),
    ("monument_guildhouse", "10_Guildhouse", build_guildhouse),
    ("monument_chapel", "11_Chapel", build_chapel),
    ("monument_church", "12_Church", build_church),
    ("monument_windmill", "13_Windmill", build_windmill),
    ("monument_watchtower", "14_Watchtower", build_watchtower),
    ("monument_gatehouse", "15_Gatehouse", build_gatehouse),
    ("monument_keep", "16_Keep", build_keep),
    ("variation_normal", "17_Var_Normal", build_var_normal),
    ("variation_with_stall", "18_Var_Stall", build_var_with_stall),
    ("variation_damaged", "19_Var_Damaged", build_var_damaged),
    ("variation_ruin", "20_Var_Ruin", build_var_ruin),
    ("monument_lighthouse", "21_Lighthouse", build_lighthouse),
]
