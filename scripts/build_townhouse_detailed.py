"""
Emberglass Townhouse - finished asset pass.

Same footprint, silhouette and camera orientation as bld_townhouse in
build_emberglass_buildings.py, but every surface is resolved: masonry laid
block by block, roof laid tile by tile, timber chamfered and pegged, plaster
troweled and locally fallen, plus the soot / moss / lichen / ivy / weed and
street-clutter layers.

    blender --background --python scripts/build_townhouse_detailed.py

Writes emberglass_townhouse_detailed.blend and renders to renders/.
"""

import bpy
import sys
import os
import random
from math import radians, cos, sin, tan, pi
from mathutils import Vector

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import materials
import detail_materials
import builder_primitives as bp
import detail_primitives as dp

COL = "01_Townhouse_Detailed"

# Shell dimensions - identical to the blockout so the two are comparable
W_X, D_Y = 4.4, 5.4
H_STONE, H1, H2 = 1.1, 2.6, 4.8
J_W, J_D = W_X + 0.35, D_Y + 0.35          # jetty (first floor) overhang
PITCH = 48.0

# The key sun runs (-0.58, +0.53, -0.62): it lights -Y and +X, so -X and +Y are
# the permanently shaded elevations. The -Y gable also sits under a deep verge,
# so its lower courses stay damp and get the same treatment.
SHADED = ("-X", "+Y", "-Y")


def link(obj):
    bp.link_to_collection(obj, COL)
    return obj


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def setup_world(scene):
    world = bpy.data.worlds.new("Emberglass_Detail_World")
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


# -----------------------------------------------------------------------------
# Facade assembly helpers
# -----------------------------------------------------------------------------

def facade_frame(name, members, seed):
    """Wrap create_timber_frame so every facade shares one call signature."""
    return link(dp.create_timber_frame(name, members, mats=MATS, seed=seed))


def panel_run(name_prefix, face, span_lo, span_hi, z0, z1, offset, studs,
              openings, seed, damage_chance=0.45):
    """Fill the bays between studs on one elevation with plaster panels.

    face is '-Y' or '+X'. openings is a list of (centre, half_width) along the
    run that a panel must not cover - windows and doors.
    """
    rng = random.Random(seed)
    edges = [span_lo] + list(studs) + [span_hi]
    panels = []
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        c = (a + b) * 0.5
        w = (b - a) - 0.14
        if w < 0.16:
            continue
        # Skip the bay if an opening eats most of it
        blocked = any(abs(c - oc) < (ow + w * 0.5) * 0.72 for oc, ow in openings)
        if blocked:
            continue
        h = (z1 - z0) - 0.14
        dmg = 1 if rng.random() < damage_chance else 0
        if face == "-Y":
            loc, rz = (c, offset, (z0 + z1) * 0.5), 0.0
        else:
            loc, rz = (offset, c, (z0 + z1) * 0.5), radians(90)
        panels.append(link(dp.create_plaster_panel(
            f"{name_prefix}_{i}", w, h, depth=0.17, location=loc, rot_z=rz,
            mats=MATS, seed=seed + i * 7, damage=dmg)))
    return panels


def place_window(name, x, y, z, facing, seed, **kw):
    w = dp.create_window_detailed(name, mats=MATS, seed=seed, **kw)
    w.location = (x, y, z)
    w.rotation_euler = (0, 0, radians(facing))
    return link(w)


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------

def build_townhouse_detailed(origin=(0, 0, 0)):
    ox, oy, oz = origin
    rng = random.Random(2026)

    # --- Ground: cobbled street apron, building footprint excluded ----------
    apron = dp.create_cobble_apron(
        "TH_Cobbles", 10.4, 10.4, mats=MATS, seed=53, cobble=0.25,
        exclude=(-W_X * 0.5 - 0.1, -D_Y * 0.5 - 0.1,
                 W_X * 0.5 + 0.1, D_Y * 0.5 + 0.1),
        location=(ox, oy, oz))
    link(apron)

    # --- Foundation: coursed rubble with quoins, moss skirt, joint weeds ----
    fnd = dp.create_masonry_box(
        "TH_Foundation", W_X, D_Y, H_STONE, location=(ox, oy, oz), mats=MATS,
        seed=11, course_h=0.21, block_len=(0.17, 0.52), shaded_faces=SHADED,
        moss_amount=0.20, lichen_amount=0.10, weeds=True, weed_rows=2)
    link(fnd)

    # --- Ground floor: plaster between a pegged box frame -------------------
    gf_h = H1 - H_STONE
    gf_z = oz + H_STONE
    # Hidden core so no gap ever shows between panels
    core = dp.create_coated_box("TH_GF_Core", W_X - 0.26, D_Y - 0.26, gf_h,
                                location=(ox, oy, gf_z + gf_h * 0.5),
                                mats=MATS, seed=211, faces=("-Y", "+X"),
                                coat=0.20, damage=2, moss_base=True)
    link(core)

    gf_members = []
    hw, hd = W_X * 0.5, D_Y * 0.5
    # Corner posts
    for sx in (-1, 1):
        for sy in (-1, 1):
            gf_members.append({
                "p0": (ox + sx * (hw - 0.10), oy + sy * (hd - 0.10), gf_z),
                "p1": (ox + sx * (hw - 0.10), oy + sy * (hd - 0.10), gf_z + gf_h),
                "w": 0.20, "d": 0.20, "chips": 3, "pegs": [0.05, 0.95]})
    # Sill beams on the masonry and head beams under the jetty
    for sy in (-1, 1):
        for z, tag in ((gf_z, "sill"), (gf_z + gf_h, "head")):
            gf_members.append({
                "p0": (ox - hw, oy + sy * (hd - 0.10), z),
                "p1": (ox + hw, oy + sy * (hd - 0.10), z),
                "w": 0.19, "d": 0.17, "chips": 3,
                "pegs": [0.10, 0.5, 0.90], "moss": (tag == "sill")})
    for sx in (-1, 1):
        for z, tag in ((gf_z, "sill"), (gf_z + gf_h, "head")):
            gf_members.append({
                "p0": (ox + sx * (hw - 0.10), oy - hd, z),
                "p1": (ox + sx * (hw - 0.10), oy + hd, z),
                "w": 0.17, "d": 0.19, "chips": 3,
                "pegs": [0.10, 0.5, 0.90], "moss": (tag == "sill")})
    # Intermediate studs: -Y elevation in three bays, +X in four
    gf_studs_y = [-1.10, 1.10]
    gf_studs_x = [-1.75, -0.30, 1.30]
    for sx_ in gf_studs_y:
        gf_members.append({"p0": (ox + sx_, oy - hd + 0.02, gf_z),
                           "p1": (ox + sx_, oy - hd + 0.02, gf_z + gf_h),
                           "w": 0.15, "d": 0.15, "chips": 2, "pegs": [0.93]})
    for sy_ in gf_studs_x:
        gf_members.append({"p0": (ox + hw - 0.02, oy + sy_, gf_z),
                           "p1": (ox + hw - 0.02, oy + sy_, gf_z + gf_h),
                           "w": 0.15, "d": 0.15, "chips": 2, "pegs": [0.93],
                           "peg_axis": (1, 0, 0)})
    # Down-braces in the end bays, the way a real box frame is stiffened
    gf_members.append({"p0": (ox - hw + 0.10, oy - hd + 0.02, gf_z + 0.10),
                       "p1": (ox - 1.10, oy - hd + 0.02, gf_z + gf_h - 0.08),
                       "w": 0.12, "d": 0.13, "chips": 2})
    gf_members.append({"p0": (ox + hw - 0.10, oy - hd + 0.02, gf_z + 0.10),
                       "p1": (ox + 1.10, oy - hd + 0.02, gf_z + gf_h - 0.08),
                       "w": 0.12, "d": 0.13, "chips": 2})
    gf_members.append({"p0": (ox + hw - 0.02, oy + hd - 0.10, gf_z + 0.10),
                       "p1": (ox + hw - 0.02, oy + 1.30, gf_z + gf_h - 0.08),
                       "w": 0.12, "d": 0.13, "chips": 2})
    facade_frame("TH_GF_Frame", gf_members, seed=17)

    panel_run("TH_GF_Panel_Y", "-Y", -hw + 0.10, hw - 0.10, gf_z, gf_z + gf_h,
              oy - hd + 0.03, gf_studs_y,
              openings=[(-1.65, 0.55), (0.55, 0.55)], seed=23)
    panel_run("TH_GF_Panel_X", "+X", -hd + 0.10, hd - 0.10, gf_z, gf_z + gf_h,
              ox + hw - 0.03, gf_studs_x,
              openings=[(-1.20, 0.80), (0.55, 0.55), (2.05, 0.55)], seed=29)

    # --- Jetty: bressummer, carved corbels, first-floor frame ---------------
    jet_h = H2 - H1
    jet_z = oz + H1
    jhw, jhd = J_W * 0.5, J_D * 0.5
    core2 = dp.create_coated_box("TH_1F_Core", J_W - 0.26, J_D - 0.26, jet_h,
                                 location=(ox, oy, jet_z + jet_h * 0.5),
                                 mats=MATS, seed=223, faces=("-Y", "+X"),
                                 coat=0.20, damage=2)
    link(core2)
    # Jetty floor plate closing the underside of the overhang
    plate = bp.create_box("TH_Jetty_Plate", size=(J_W, J_D, 0.13),
                          location=(ox, oy, jet_z - 0.055),
                          material=MATS["M_Timber_Aged"], bevel=0.015)
    link(plate)

    jf_members = []
    for sy in (-1, 1):
        jf_members.append({
            "p0": (ox - jhw, oy + sy * (jhd - 0.10), jet_z),
            "p1": (ox + jhw, oy + sy * (jhd - 0.10), jet_z),
            "w": 0.26, "d": 0.22, "chips": 4, "pegs": [0.08, 0.5, 0.92],
            "moss": True})
        jf_members.append({
            "p0": (ox - jhw, oy + sy * (jhd - 0.10), jet_z + jet_h),
            "p1": (ox + jhw, oy + sy * (jhd - 0.10), jet_z + jet_h),
            "w": 0.21, "d": 0.19, "chips": 3, "pegs": [0.08, 0.5, 0.92]})
    for sx in (-1, 1):
        jf_members.append({
            "p0": (ox + sx * (jhw - 0.10), oy - jhd, jet_z),
            "p1": (ox + sx * (jhw - 0.10), oy + jhd, jet_z),
            "w": 0.22, "d": 0.26, "chips": 4, "pegs": [0.08, 0.5, 0.92],
            "moss": True})
        jf_members.append({
            "p0": (ox + sx * (jhw - 0.10), oy - jhd, jet_z + jet_h),
            "p1": (ox + sx * (jhw - 0.10), oy + jhd, jet_z + jet_h),
            "w": 0.19, "d": 0.21, "chips": 3, "pegs": [0.08, 0.5, 0.92]})
        for sy in (-1, 1):
            jf_members.append({
                "p0": (ox + sx * (jhw - 0.10), oy + sy * (jhd - 0.10), jet_z),
                "p1": (ox + sx * (jhw - 0.10), oy + sy * (jhd - 0.10),
                       jet_z + jet_h),
                "w": 0.21, "d": 0.21, "chips": 3, "pegs": [0.04, 0.96]})

    # St Andrew's crosses on -Y (two bays) and +X (three bays)
    jf_studs_y = [-0.95, 0.95]
    jf_studs_x = [-1.55, 0.0, 1.55]
    y_face = oy - jhd + 0.03
    x_face = ox + jhw - 0.03
    for sx_ in jf_studs_y:
        jf_members.append({"p0": (ox + sx_, y_face, jet_z),
                           "p1": (ox + sx_, y_face, jet_z + jet_h),
                           "w": 0.16, "d": 0.15, "chips": 2, "pegs": [0.05, 0.95]})
    for sy_ in jf_studs_x:
        jf_members.append({"p0": (x_face, oy + sy_, jet_z),
                           "p1": (x_face, oy + sy_, jet_z + jet_h),
                           "w": 0.15, "d": 0.16, "chips": 2, "pegs": [0.05, 0.95],
                           "peg_axis": (1, 0, 0)})
    edges_y = [-jhw + 0.10] + jf_studs_y + [jhw - 0.10]
    for i in range(len(edges_y) - 1):
        a, b = edges_y[i], edges_y[i + 1]
        if b - a < 0.5:
            continue
        for s in (1, -1):
            jf_members.append({
                "p0": (ox + (a if s > 0 else b), y_face, jet_z + 0.12),
                "p1": (ox + (b if s > 0 else a), y_face, jet_z + jet_h - 0.12),
                "w": 0.115, "d": 0.14, "chips": 2})
    edges_x = [-jhd + 0.10] + jf_studs_x + [jhd - 0.10]
    for i in range(len(edges_x) - 1):
        a, b = edges_x[i], edges_x[i + 1]
        if b - a < 0.5:
            continue
        for s in (1, -1):
            jf_members.append({
                "p0": (x_face, oy + (a if s > 0 else b), jet_z + 0.12),
                "p1": (x_face, oy + (b if s > 0 else a), jet_z + jet_h - 0.12),
                "w": 0.14, "d": 0.115, "chips": 2})
    facade_frame("TH_1F_Frame", jf_members, seed=31)

    panel_run("TH_1F_Panel_Y", "-Y", -jhw + 0.10, jhw - 0.10, jet_z,
              jet_z + jet_h, oy - jhd + 0.03, jf_studs_y,
              openings=[(-1.15, 0.60), (1.15, 0.60)], seed=37,
              damage_chance=0.55)
    panel_run("TH_1F_Panel_X", "+X", -jhd + 0.10, jhd - 0.10, jet_z,
              jet_z + jet_h, ox + jhw - 0.03, jf_studs_x,
              openings=[(-1.55, 0.55), (0.0, 0.55), (1.55, 0.55)], seed=41,
              damage_chance=0.55)

    # Carved corbels under the jetty on both visible elevations
    for cx in (-1.75, -0.60, 0.60, 1.75):
        c = dp.create_corbel_bracket(f"TH_Corbel_Y_{cx}", mats=MATS,
                                     seed=137 + int(cx * 10), size=0.44,
                                     projection=0.30)
        c.location = (ox + cx, oy - hd + 0.06, jet_z - 0.52)
        link(c)
    for cy in (-2.10, -0.70, 0.70, 2.10):
        c = dp.create_corbel_bracket(f"TH_Corbel_X_{cy}", mats=MATS,
                                     seed=151 + int(cy * 10), size=0.44,
                                     projection=0.30)
        c.location = (ox + hw - 0.06, oy + cy, jet_z - 0.52)
        c.rotation_euler = (0, 0, radians(90))
        link(c)

    # --- Roof: laid tile by tile -------------------------------------------
    roof, pitch_h = dp.create_tiled_roof_y(
        "TH_Roof", span_x=J_W, length_y=J_D, overhang_eave=0.44,
        overhang_gable=0.34, mats=MATS, seed=23, pitch_deg=PITCH,
        tile_w=0.27, exposure=0.185, tile_len=0.31, tile_thick=0.055,
        damage=1.25,
        shaded_slope=1, moss_amount=1.0)
    roof.location = (ox, oy, oz + H2)
    link(roof)

    # --- Gable ends: raked plaster inside a braced apex frame ---------------
    gf_front = dp.create_gable_infill("TH_Gable_F", J_W, pitch_h, mats=MATS,
                                      seed=131, depth=0.20,
                                      location=(ox, oy - jhd, oz + H2))
    link(gf_front)
    gb_back = dp.create_gable_infill("TH_Gable_B", J_W, pitch_h, mats=MATS,
                                     seed=157, depth=0.20,
                                     location=(ox, oy + jhd, oz + H2),
                                     rot_z=radians(180))
    link(gb_back)

    # --- Chimney: coursed stone, clay pot, soot, lead flashing --------------
    ch_w = 0.96
    ch_x, ch_y = ox - 0.52, oy - jhd + 1.25
    # Sink the base below the tile plane at that x so the stack grows out of
    # the roof instead of standing beside it.
    roof_z_at_ch = oz + H2 + pitch_h - abs(ch_x - ox) * tan(radians(PITCH))
    ch_base = roof_z_at_ch - 0.95
    chim = dp.create_chimney_detailed("TH_Chimney", height=2.80, width=ch_w,
                                      depth=ch_w, mats=MATS, seed=31,
                                      smoke=True, soot=True)
    chim.location = (ch_x, ch_y, ch_base)
    link(chim)
    # Lead soakers dressed over the tiles on the uphill and downhill sides
    for sy in (-1, 1):
        fl = bp.create_box(f"TH_Flash_Y{sy}", size=(ch_w + 0.34, 0.09, 0.34),
                           location=(ch_x, ch_y + sy * (ch_w * 0.5 + 0.10),
                                     roof_z_at_ch + 0.10),
                           material=MATS["M_Iron_Aged"], bevel=0.012)
        fl.rotation_euler = (0, radians(-PITCH), 0)
        link(fl)
    fl_up = bp.create_box("TH_Flash_Up", size=(0.34, ch_w + 0.30, 0.30),
                          location=(ch_x + ch_w * 0.5 + 0.12, ch_y,
                                    roof_z_at_ch - 0.10),
                          material=MATS["M_Iron_Aged"], bevel=0.012)
    fl_up.rotation_euler = (0, radians(-PITCH), 0)
    link(fl_up)

    # --- Openings ------------------------------------------------------------
    # Gable elevation (-Y): two lit windows on the ground floor
    for i, wx in enumerate((-1.65, 0.55)):
        place_window(f"TH_GF_Win_Y{i}", ox + wx, oy - hd + 0.02, gf_z + 0.34,
                     0, seed=61 + i * 13, width=0.88, height=1.08,
                     shutters=True, shutter_open=True, planter=(i == 1),
                     stone_sill=True)
    # First floor, -Y: two windows with planted boxes
    for i, wx in enumerate((-1.15, 1.15)):
        place_window(f"TH_1F_Win_Y{i}", ox + wx, oy - jhd + 0.02, jet_z + 0.55,
                     0, seed=71 + i * 13, width=0.86, height=1.18,
                     shutters=True, shutter_open=True, planter=True)
    # Attic light in the gable apex
    place_window("TH_Attic_Win", ox, oy - jhd - 0.14, oz + H2 + 0.92, 0,
                 seed=83, width=0.62, height=0.76, shutters=True,
                 shutter_open=True, planter=False, pane_cols=2, pane_rows=3,
                 stone_sill=False)

    # Street elevation (+X): door, canopy, windows
    door = dp.create_door_detailed("TH_Door", width=1.12, height=2.12,
                                   mats=MATS, seed=71)
    door.location = (ox + hw + 0.02, oy - 1.20, gf_z - 0.62)
    door.rotation_euler = (0, 0, radians(90))
    link(door)

    steps = dp.create_stone_steps_detailed("TH_Steps", mats=MATS, seed=127,
                                           width=1.72, depth=1.05, height=0.50,
                                           n_steps=3)
    steps.location = (ox + hw + 0.02, oy - 1.20, oz)
    steps.rotation_euler = (0, 0, radians(90))
    link(steps)

    canopy = dp.create_pentice_canopy("TH_Canopy", width=1.95, depth=0.95,
                                      mats=MATS, seed=139)
    canopy.location = (ox + hw + 0.04, oy - 1.20, gf_z + 1.32)
    canopy.rotation_euler = (0, 0, radians(90))
    link(canopy)

    for i, wy in enumerate((0.55, 2.05)):
        place_window(f"TH_GF_Win_X{i}", ox + hw + 0.02, oy + wy, gf_z + 0.34,
                     90, seed=91 + i * 13, width=0.86, height=1.08,
                     shutters=True, shutter_open=True, planter=True)
    for i, wy in enumerate((-1.55, 0.0, 1.55)):
        place_window(f"TH_1F_Win_X{i}", ox + jhw + 0.02, oy + wy, jet_z + 0.55,
                     90, seed=101 + i * 13, width=0.84, height=1.18,
                     shutters=True, shutter_open=(i != 1), planter=True)

    # --- Ironwork and signage ------------------------------------------------
    brk = dp.create_lantern_bracket("TH_Lantern_Door", mats=MATS, seed=83,
                                    reach=0.50, lantern=True, lit=True)
    brk.location = (ox + hw + 0.02, oy - 0.30, gf_z + 1.30)
    brk.rotation_euler = (0, 0, radians(90))
    link(brk)
    # A light on the gable elevation too, plus an empty bracket beside it
    brk2 = dp.create_lantern_bracket("TH_Lantern_Gable", mats=MATS, seed=97,
                                     reach=0.44, lantern=True, lit=True)
    brk2.location = (ox - 0.58, oy - hd + 0.02, gf_z + 1.30)
    link(brk2)
    brk3 = dp.create_lantern_bracket("TH_Bracket_Empty", mats=MATS, seed=109,
                                     reach=0.40, lantern=False)
    brk3.location = (ox + hw + 0.02, oy + 2.85, gf_z + 1.34)
    brk3.rotation_euler = (0, 0, radians(90))
    link(brk3)

    sign = dp.create_hanging_sign_detailed("TH_Sign", mats=MATS, seed=89,
                                           board_w=0.82, board_h=0.60,
                                           emblem="tankard")
    sign.location = (ox + 1.78, oy - hd + 0.02, gf_z + 1.42)
    sign.rotation_euler = (0, 0, 0.0)
    link(sign)

    # --- Growth: ivy at both exposed corners and across a blank bay ---------
    ivy_a = dp.create_ivy_climber("TH_Ivy_Corner_FL", height=3.35, width=1.05,
                                  mats=MATS, seed=41, stems=4, density=1.15,
                                  corner=True, depth=0.16)
    ivy_a.location = (ox - hw - 0.02, oy - hd - 0.02, oz + 0.10)
    ivy_a.rotation_euler = (0, 0, radians(-90))
    link(ivy_a)

    ivy_b = dp.create_ivy_climber("TH_Ivy_Corner_BR", height=2.85, width=0.95,
                                  mats=MATS, seed=47, stems=3, density=1.0,
                                  corner=True, depth=0.16)
    ivy_b.location = (ox + hw + 0.02, oy + hd + 0.02, oz + 0.10)
    ivy_b.rotation_euler = (0, 0, radians(90))
    link(ivy_b)

    ivy_c = dp.create_ivy_climber("TH_Ivy_Wall_X", height=1.95, width=0.85,
                                  mats=MATS, seed=59, stems=3, density=0.95,
                                  depth=0.14)
    ivy_c.location = (ox + hw + 0.02, oy + 2.55, oz + 0.35)
    ivy_c.rotation_euler = (0, 0, radians(90))
    link(ivy_c)

    ivy_d = dp.create_ivy_climber("TH_Ivy_Wall_Y", height=1.55, width=0.70,
                                  mats=MATS, seed=67, stems=2, density=0.85,
                                  depth=0.14)
    ivy_d.location = (ox + hw + 0.02, oy - 2.35, oz + 0.45)
    ivy_d.rotation_euler = (0, 0, radians(90))
    link(ivy_d)

    # --- Garden and street clutter -------------------------------------------
    garden = dp.create_garden_bed("TH_Garden", mats=MATS, seed=109, width=2.05,
                                  depth=0.78, edging="stone")
    garden.location = (ox - 1.05, oy - hd - 0.62, oz)
    link(garden)

    fbox = dp.create_flower_box_standalone_detailed(
        "TH_FlowerBox_Street", mats=MATS, seed=113, length=1.25)
    fbox.location = (ox + 1.85, oy - hd - 0.48, oz + 0.16)
    link(fbox)

    bench = dp.create_bench_detailed("TH_Bench", mats=MATS, seed=103,
                                     length=1.55, mossy=True)
    bench.location = (ox + hw + 0.68, oy + 1.30, oz)
    bench.rotation_euler = (0, 0, radians(90))
    link(bench)

    for i, (bx, by, tilt, op, mossy) in enumerate([
            (hw + 0.62, 2.95, False, True, True),
            (hw + 1.24, 3.10, False, False, False),
            (hw + 1.05, 2.42, True, False, True)]):
        b = dp.create_barrel_detailed(f"TH_Barrel_{i}", mats=MATS,
                                      seed=97 + i * 11, radius=0.33,
                                      height=0.84, open_top=op, tilted=tilt,
                                      mossy=mossy)
        b.location = (ox + bx, oy + by, oz)
        link(b)

    crate_a = dp.create_crate_detailed("TH_Crate_A", mats=MATS, seed=101,
                                       size=0.64, lid=True, stencil=True)
    crate_a.location = (ox + hw + 0.70, oy - 2.60, oz)
    crate_a.rotation_euler = (0, 0, radians(14))
    link(crate_a)
    crate_b = dp.create_crate_detailed("TH_Crate_B", mats=MATS, seed=149,
                                       size=0.52, lid=False, stencil=False)
    crate_b.location = (ox + hw + 0.64, oy - 2.55, oz + 0.53)
    crate_b.rotation_euler = (0, 0, radians(-9))
    link(crate_b)
    crate_c = dp.create_crate_detailed("TH_Crate_C", mats=MATS, seed=163,
                                       size=0.58, lid=True, stencil=True)
    crate_c.location = (ox + hw + 1.36, oy - 2.35, oz)
    crate_c.rotation_euler = (0, 0, radians(-22))
    link(crate_c)

    wood = dp.create_firewood_stack_detailed("TH_Firewood", mats=MATS,
                                             seed=107, width=1.45, depth=0.52,
                                             height=0.84)
    wood.location = (ox - hw - 0.34, oy + 1.55, oz)
    wood.rotation_euler = (0, 0, radians(-90))
    link(wood)

    # Reused blockout props that already read at finished density
    for i, (px, py) in enumerate([(-2.45, -1.05), (2.05, -2.95)]):
        pot = bp.create_flowerpot_prop(f"TH_Pot_{i}", radius=0.23, height=0.36,
                                       stone_mat=MATS["M_Terracotta"],
                                       foliage_mat=MATS["M_Foliage"],
                                       flower_mat=MATS["M_Flowers"])
        pot.location = (ox + px, oy + py, oz)
        link(pot)

    # ponytail: the blockout notice board and multi-signpost are still at
    # blockout density and would break the pass; a second hanging sign and a
    # leaning handcart carry the same street read at the right fidelity.
    sign2 = dp.create_hanging_sign_detailed("TH_Sign_Small", mats=MATS,
                                            seed=173, board_w=0.58,
                                            board_h=0.42, emblem="disc")
    sign2.location = (ox - 2.05, oy - hd + 0.02, gf_z + 1.16)
    sign2.rotation_euler = (0, 0, 0.0)
    link(sign2)

    # Gable hoist: the loading beam and pulley a townhouse uses to get goods
    # into the attic. Breaks the apex silhouette and reads at any distance.
    hoist = dp.create_timber_frame("TH_Hoist", [
        {"p0": (ox, oy - jhd - 0.10, oz + H2 + pitch_h - 0.62),
         "p1": (ox, oy - jhd - 1.05, oz + H2 + pitch_h - 0.52),
         "w": 0.15, "d": 0.15, "chips": 3, "pegs": [0.12]},
        {"p0": (ox - 0.02, oy - jhd - 0.62, oz + H2 + pitch_h - 0.58),
         "p1": (ox - 0.02, oy - jhd - 0.14, oz + H2 + pitch_h - 1.22),
         "w": 0.10, "d": 0.11, "chips": 2}],
        mats=MATS, seed=181)
    link(hoist)
    pulley = dp.create_lantern_bracket("TH_Hoist_Block", mats=MATS, seed=191,
                                       reach=0.16, lantern=False)
    pulley.location = (ox, oy - jhd - 0.95, oz + H2 + pitch_h - 0.66)
    pulley.rotation_euler = (radians(90), 0, 0)
    link(pulley)

    return pitch_h


# -----------------------------------------------------------------------------
# Camera + lights: identical rig to the showcase sheet so this is comparable
# -----------------------------------------------------------------------------

def setup_camera_and_lights(pitch_h):
    col = "00_Lighting_and_Cameras"

    cam_data = bpy.data.cameras.new("Cam_Townhouse_Detail")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 13.5
    cam = bpy.data.objects.new("Cam_Townhouse_Detail", cam_data)
    dist = 30.0
    cam.location = (dist, -dist, 3.6 + dist)
    cam.rotation_euler = (radians(54.736), 0, radians(45.0))
    bp.link_to_collection(cam, col)
    bpy.context.scene.camera = cam

    sun_data = bpy.data.lights.new(name="Sun_KeyLight", type='SUN')
    sun_data.energy = 5.0
    sun_data.color = (1.0, 0.90, 0.76)
    sun_data.angle = radians(6.0)
    sun = bpy.data.objects.new("Sun_KeyLight", sun_data)
    sun.rotation_euler = (radians(50.0), radians(15.0), radians(35.0))
    bp.link_to_collection(sun, col)

    sky_data = bpy.data.lights.new(name="Sun_SkyFill", type='SUN')
    sky_data.energy = 1.45
    sky_data.color = (0.56, 0.68, 0.88)
    sky = bpy.data.objects.new("Sun_SkyFill", sky_data)
    sky.rotation_euler = (radians(130.0), radians(15.0), radians(-145.0))
    bp.link_to_collection(sky, col)

    # Warm bounce off the cobbles so the shaded underside of the jetty and the
    # eaves keep some colour instead of going to flat black
    bounce_data = bpy.data.lights.new(name="Sun_WarmBounce", type='SUN')
    bounce_data.energy = 1.2
    bounce_data.color = (1.0, 0.82, 0.62)
    bounce = bpy.data.objects.new("Sun_WarmBounce", bounce_data)
    bounce.rotation_euler = (radians(-28.0), radians(0.0), radians(30.0))
    bp.link_to_collection(bounce, col)
    return cam


def setup_vintage_grade(scene):
    """Warm, slightly desaturated grade - the vintage note over the render."""
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    rl = tree.nodes.new("CompositorNodeRLayers")
    bal = tree.nodes.new("CompositorNodeColorBalance")
    bal.correction_method = 'LIFT_GAMMA_GAIN'
    bal.lift = (1.010, 1.000, 0.980)      # shadows toward warm brown
    bal.gamma = (1.020, 1.000, 0.962)     # midtones toward ochre
    bal.gain = (1.045, 1.010, 0.945)      # highlights toward sunlight
    hsv = tree.nodes.new("CompositorNodeHueSat")
    hsv.inputs['Saturation'].default_value = 0.92
    hsv.inputs['Value'].default_value = 1.02
    comp = tree.nodes.new("CompositorNodeComposite")
    tree.links.new(rl.outputs['Image'], bal.inputs['Image'])
    tree.links.new(bal.outputs['Image'], hsv.inputs['Image'])
    tree.links.new(hsv.outputs['Image'], comp.inputs['Image'])


def render(cam, out_path, res=1600):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.film_transparent = False
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.filepath = out_path
    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass
    try:
        scene.eevee.use_raytracing = True
        scene.eevee.taa_render_samples = 96
    except Exception:
        pass
    bpy.ops.render.render(write_still=True)
    print(f"rendered -> {out_path}")


def report_stats():
    dg = bpy.context.evaluated_depsgraph_get()
    total_v = total_f = 0
    rows = []
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        ev = obj.evaluated_get(dg)
        m = ev.to_mesh()
        nv, nf = len(m.vertices), len(m.polygons)
        ev.to_mesh_clear()
        total_v += nv
        total_f += nf
        rows.append((nf, obj.name, nv))
    rows.sort(reverse=True)
    print("\n--- heaviest components ---")
    for nf, nm, nv in rows[:12]:
        print(f"  {nm:26s} verts={nv:7d} faces={nf:7d}")
    print(f"TOTAL objects={len(rows)} verts={total_v} faces={total_f}")


def main():
    global MATS
    print("Emberglass Townhouse - finished asset pass")
    clear_scene()
    scene = bpy.context.scene
    setup_world(scene)
    MATS = materials.setup_all_materials()
    MATS = detail_materials.setup_detail_materials(MATS)
    print(f"  materials: {len(MATS)}")

    pitch_h = build_townhouse_detailed(origin=(0, 0, 0))
    print(f"  pitch height: {pitch_h:.3f}")
    cam = setup_camera_and_lights(pitch_h)
    setup_vintage_grade(scene)

    out_blend = "d:/assests/emberglass_townhouse_detailed.blend"
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print(f"  saved {out_blend}")

    report_stats()
    render(cam, "d:/assests/renders/townhouse_detailed.png", res=1600)

    # Close-ups: the pass only counts if the detail survives at sprite scale
    for tag, target, scale in [
            ("roof", (-0.3, 0.2, 6.4), 4.2),
            ("street", (2.3, -0.6, 1.5), 3.6),
            ("base", (-1.2, -2.8, 0.9), 3.0)]:
        d = 30.0
        cam.location = (target[0] + d, target[1] - d, target[2] + d)
        cam.data.ortho_scale = scale
        render(cam, f"d:/assests/renders/townhouse_detail_{tag}.png", res=1100)


if __name__ == "__main__":
    main()
