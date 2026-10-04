"""
Emberglass detailed building driver.

One parameterised `build_structure()` produces the shared anatomy every building
in the library has - masonry foundation, framed or coursed storeys, jettied
upper floor, tiled roof, gable infill, chimney, openings - so all 20 structures
come from one code path and stay stylistically identical. Each building then
adds only its signature extras on top.

Everything here composes `detail_primitives`; `builder_primitives` is used only
for the handful of blockout props that still hold up at sprite scale.
"""

import bpy
import os
import sys
import random
from math import radians, cos, sin, tan, pi

# `scripts/city` must be on sys.path BEFORE city_lod is imported, and it must
# be imported flat rather than as `city.city_lod`. Importing it both ways
# creates two distinct module objects with two distinct `L` globals, so
# set_lod() on one is invisible to the other -- which silently produced
# identical face counts at every LOD level.
_CITY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "city")
if _CITY_DIR not in sys.path:
    sys.path.append(_CITY_DIR)

import builder_primitives as bp
import detail_primitives as dp
import city_lod as _lod


# The camera sees -Y and +X; the key sun lights those two faces, so -X and +Y
# are the shaded elevations. -Y is included because deep verges keep it damp.
SHADED = ("-X", "+Y", "-Y")


def _link(obj, col):
    bp.link_to_collection(obj, col)
    return obj


# =============================================================================
# Shared anatomy
# =============================================================================

def build_structure(name, mats, col, origin=(0, 0, 0), w=4.4, d=5.4,
                    base_h=1.0, storey_h=(1.5, 2.2), jetty=0.18,
                    roof_axis="y", pitch=48.0, palette="clay", seed=11,
                    overhang=(0.42, 0.32), frame_style="timber",
                    base_style="masonry", chimney=None, gables=True,
                    roof=True, ledge=True, course_h=0.21, deck=False,
                    stone="limestone"):
    """The common shell. Returns a dict of the key levels and the roof pitch.

    storey_h is a tuple of storey heights above the foundation. A second entry
    triggers the jettied upper floor. frame_style 'timber' gives a half-timbered
    box frame with plaster panels; 'stone' gives coursed masonry all the way up.
    """
    rng = random.Random(seed)
    ox, oy, oz = origin
    hw, hd = w * 0.5, d * 0.5
    levels = {"base": oz}

    # --- Foundation ---------------------------------------------------------
    if base_style == "masonry" and base_h > 0.05:
        _link(dp.create_masonry_box(
            f"{name}_Foundation", w, d, base_h, location=(ox, oy, oz),
            mats=mats, seed=seed, course_h=_lod.L.course_h(course_h),
            block_len=_lod.L.block_len((0.17, 0.52)),
            shaded_faces=SHADED, moss_amount=_lod.L.growth(0.20),
            lichen_amount=_lod.L.growth(0.10),
            weeds=True, weed_rows=_lod.L.weed_rows(2), ledge=ledge,
            stone=stone), col)
    z = oz + base_h
    levels["gf"] = z

    # --- Storeys -------------------------------------------------------------
    cur_w, cur_d = w, d
    for i, sh in enumerate(storey_h):
        is_upper = (i > 0)
        if is_upper and jetty > 0.0:
            cur_w, cur_d = cur_w + jetty * 2.0, cur_d + jetty * 2.0
            # Jetty floor plate closing the underside of the overhang
            _link(bp.create_box(f"{name}_Jetty_Plate_{i}",
                                size=(cur_w, cur_d, 0.13),
                                location=(ox, oy, z - 0.055),
                                material=mats["M_Timber_Aged"], bevel=0.015), col)
            for cx in _spread(cur_w * 0.5 - 0.35, 4):
                c = dp.create_corbel_bracket(
                    f"{name}_Corbel_Y_{i}_{cx:.2f}", mats=mats,
                    seed=seed + int(abs(cx) * 37) + 3, size=0.44, projection=0.30)
                c.location = (ox + cx, oy - cur_d * 0.5 + jetty + 0.06, z - 0.52)
                _link(c, col)
            for cy in _spread(cur_d * 0.5 - 0.35, 4):
                c = dp.create_corbel_bracket(
                    f"{name}_Corbel_X_{i}_{cy:.2f}", mats=mats,
                    seed=seed + int(abs(cy) * 41) + 7, size=0.44, projection=0.30)
                c.location = (ox + cur_w * 0.5 - jetty - 0.06, oy + cy, z - 0.52)
                c.rotation_euler = (0, 0, radians(90))
                _link(c, col)

        chw, chd = cur_w * 0.5, cur_d * 0.5

        if frame_style == "stone":
            _link(dp.create_masonry_box(
                f"{name}_Stone_{i}", cur_w, cur_d, sh,
                location=(ox, oy, z), mats=mats, seed=seed + 40 + i * 5,
                course_h=_lod.L.course_h(course_h + 0.03),
                block_len=_lod.L.block_len((0.20, 0.58)),
                shaded_faces=SHADED, moss_amount=_lod.L.growth(0.13),
                lichen_amount=_lod.L.growth(0.10),
                weeds=(i == 0), weed_rows=_lod.L.weed_rows(1),
                plinth=(i == 0),
                ledge=(i == len(storey_h) - 1), ground_moss=(i == 0),
                stone=stone), col)
        else:
            _link(dp.create_coated_box(
                f"{name}_Core_{i}", cur_w - 0.26, cur_d - 0.26, sh,
                location=(ox, oy, z + sh * 0.5), mats=mats,
                seed=seed + 60 + i * 9, faces=("-Y", "+X"), coat=0.20,
                damage=2, moss_base=(i == 0)), col)
            _timber_frame_storey(f"{name}_Frame_{i}", mats, col, ox, oy, z,
                                 chw, chd, sh, seed + 80 + i * 11,
                                 crosses=is_upper)
            _panel_bays(f"{name}_Panel_{i}", mats, col, ox, oy, z, chw, chd, sh,
                        seed + 100 + i * 13, crosses=is_upper)
        z += sh
        levels[f"top{i}"] = z

    levels["eaves"] = z
    levels["w"], levels["d"] = cur_w, cur_d

    # A roofless tower needs a walked-on surface, not the bare top of the
    # masonry box. Flagstones give it joints, moss and weeds for free.
    if deck:
        dk = dp.create_cobble_apron(
            f"{name}_Deck", cur_w + 0.04, cur_d + 0.04, mats=mats,
            seed=seed + 71, cobble=_lod.L.cobble(0.44),
            location=(ox, oy, z + 0.03),
            kerb=False, weeds=True, thickness=0.14, stone=stone)
        _link(dk, col)

    # --- Roof ---------------------------------------------------------------
    pitch_h = 0.0
    if roof:
        span = cur_w if roof_axis == "y" else cur_d
        length = cur_d if roof_axis == "y" else cur_w
        rf, pitch_h = dp.create_tiled_roof_y(
            f"{name}_Roof", span_x=span, length_y=length,
            overhang_eave=overhang[0], overhang_gable=overhang[1], mats=mats,
            seed=seed + 3, pitch_deg=pitch,
            tile_w=_lod.L.tile_w(0.27), exposure=_lod.L.exposure(0.185),
            tile_len=_lod.L.tile_len(0.31), tile_thick=0.055,
            damage=_lod.L.damage(1.2),
            shaded_slope=(1 if roof_axis == "y" else -1),
            moss_amount=_lod.L.growth(1.0),
            palette=palette)
        rf.location = (ox, oy, z)
        if roof_axis == "x":
            rf.rotation_euler = (0, 0, radians(90))
        _link(rf, col)

        if gables:
            gw = span
            for sgn in (-1, 1):
                g = dp.create_gable_infill(
                    f"{name}_Gable_{'F' if sgn < 0 else 'B'}", gw, pitch_h,
                    mats=mats, seed=seed + 5 + (0 if sgn < 0 else 17),
                    depth=0.20)
                if roof_axis == "y":
                    g.location = (ox, oy + sgn * cur_d * 0.5, z)
                    g.rotation_euler = (0, 0, radians(0 if sgn < 0 else 180))
                else:
                    g.location = (ox + sgn * cur_w * 0.5, oy, z)
                    g.rotation_euler = (0, 0, radians(-90 if sgn > 0 else 90))
                _link(g, col)
    levels["pitch_h"] = pitch_h
    levels["apex"] = z + pitch_h

    # --- Chimneys -----------------------------------------------------------
    for i, ch in enumerate(chimney or []):
        cx, cy, chh, cww = ch
        ridge_off = abs(cx) if roof_axis == "y" else abs(cy)
        roof_z = z + pitch_h - ridge_off * tan(radians(pitch))
        stack = dp.create_chimney_detailed(
            f"{name}_Chimney_{i}", height=chh, width=cww, depth=cww,
            mats=mats, seed=seed + 31 + i * 7, smoke=True, soot=True,
            stone=stone)
        stack.location = (ox + cx, oy + cy, roof_z - 0.95)
        _link(stack, col)
        for sgn in (-1, 1):
            fl = bp.create_box(f"{name}_Flash_{i}_{sgn}",
                               size=(cww + 0.34, 0.09, 0.34),
                               location=(ox + cx, oy + cy + sgn * (cww * 0.5 + 0.10),
                                         roof_z + 0.10),
                               material=mats["M_Iron_Aged"], bevel=0.012)
            fl.rotation_euler = (0, radians(-pitch), 0)
            _link(fl, col)

    return levels


def _spread(half, n):
    """n positions symmetric about 0 spanning +/-half."""
    if n < 2:
        return [0.0]
    return [-half + i * (2.0 * half / (n - 1)) for i in range(n)]


def _timber_frame_storey(name, mats, col, ox, oy, z, chw, chd, sh, seed,
                         crosses=False):
    """Box frame: corner posts, sill and head plates, studs, braces."""
    rng = random.Random(seed)
    m = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.append({"p0": (ox + sx * (chw - 0.10), oy + sy * (chd - 0.10), z),
                      "p1": (ox + sx * (chw - 0.10), oy + sy * (chd - 0.10), z + sh),
                      "w": 0.20, "d": 0.20, "chips": 3, "pegs": [0.05, 0.95]})
    for sy in (-1, 1):
        for zz, tag in ((z, "sill"), (z + sh, "head")):
            m.append({"p0": (ox - chw, oy + sy * (chd - 0.10), zz),
                      "p1": (ox + chw, oy + sy * (chd - 0.10), zz),
                      "w": 0.19, "d": 0.17, "chips": 3,
                      "pegs": [0.10, 0.5, 0.90], "moss": tag == "sill"})
    for sx in (-1, 1):
        for zz, tag in ((z, "sill"), (z + sh, "head")):
            m.append({"p0": (ox + sx * (chw - 0.10), oy - chd, zz),
                      "p1": (ox + sx * (chw - 0.10), oy + chd, zz),
                      "w": 0.17, "d": 0.19, "chips": 3,
                      "pegs": [0.10, 0.5, 0.90], "moss": tag == "sill"})

    y_face, x_face = oy - chd + 0.03, ox + chw - 0.03
    studs_y = _spread(chw - 0.85, max(2, int(chw / 1.15)))
    studs_x = _spread(chd - 0.85, max(2, int(chd / 1.15)))
    for sx_ in studs_y:
        m.append({"p0": (ox + sx_, y_face, z), "p1": (ox + sx_, y_face, z + sh),
                  "w": 0.16, "d": 0.15, "chips": 2, "pegs": [0.05, 0.95]})
    for sy_ in studs_x:
        m.append({"p0": (x_face, oy + sy_, z), "p1": (x_face, oy + sy_, z + sh),
                  "w": 0.15, "d": 0.16, "chips": 2, "pegs": [0.05, 0.95],
                  "peg_axis": (1, 0, 0)})

    if crosses:
        for edges, face, horiz in ((( [-chw + 0.10] + studs_y + [chw - 0.10]),
                                    "y", True),
                                   (([-chd + 0.10] + studs_x + [chd - 0.10]),
                                    "x", False)):
            for i in range(len(edges) - 1):
                a, b = edges[i], edges[i + 1]
                if b - a < 0.55:
                    continue
                for sgn in (1, -1):
                    p, q = (a, b) if sgn > 0 else (b, a)
                    if horiz:
                        m.append({"p0": (ox + p, y_face, z + 0.12),
                                  "p1": (ox + q, y_face, z + sh - 0.12),
                                  "w": 0.115, "d": 0.14, "chips": 2})
                    else:
                        m.append({"p0": (x_face, oy + p, z + 0.12),
                                  "p1": (x_face, oy + q, z + sh - 0.12),
                                  "w": 0.14, "d": 0.115, "chips": 2})
    else:
        # Down-braces in the end bays, the way a box frame is really stiffened
        if len(studs_y):
            m.append({"p0": (ox - chw + 0.10, y_face, z + 0.10),
                      "p1": (ox + studs_y[0], y_face, z + sh - 0.08),
                      "w": 0.12, "d": 0.13, "chips": 2})
            m.append({"p0": (ox + chw - 0.10, y_face, z + 0.10),
                      "p1": (ox + studs_y[-1], y_face, z + sh - 0.08),
                      "w": 0.12, "d": 0.13, "chips": 2})
        if len(studs_x):
            m.append({"p0": (x_face, oy + chd - 0.10, z + 0.10),
                      "p1": (x_face, oy + studs_x[-1], z + sh - 0.08),
                      "w": 0.12, "d": 0.13, "chips": 2})
    _link(dp.create_timber_frame(name, m, mats=mats, seed=seed), col)


def _panel_bays(name, mats, col, ox, oy, z, chw, chd, sh, seed, crosses=False):
    """Plaster panels in the bays between studs on the two visible faces."""
    rng = random.Random(seed)
    studs_y = _spread(chw - 0.85, max(2, int(chw / 1.15)))
    studs_x = _spread(chd - 0.85, max(2, int(chd / 1.15)))
    for face, edges, off in (("-Y", [-chw + 0.10] + studs_y + [chw - 0.10],
                              oy - chd + 0.03),
                             ("+X", [-chd + 0.10] + studs_x + [chd - 0.10],
                              ox + chw - 0.03)):
        for i in range(len(edges) - 1):
            a, b = edges[i], edges[i + 1]
            pw = (b - a) - 0.14
            ph = sh - 0.14
            if pw < 0.22 or ph < 0.22:
                continue
            c = (a + b) * 0.5
            loc = (ox + c, off, z + sh * 0.5) if face == "-Y" else \
                  (off, oy + c, z + sh * 0.5)
            _link(dp.create_plaster_panel(
                f"{name}_{face}_{i}", pw, ph, depth=0.17, location=loc,
                rot_z=0.0 if face == "-Y" else radians(90), mats=mats,
                seed=seed + i * 7 + (0 if face == "-Y" else 3),
                damage=1 if rng.random() < 0.5 else 0), col)


# =============================================================================
# Opening helpers
# =============================================================================

def add_window(name, mats, col, x, y, z, facing, seed, **kw):
    w = dp.create_window_detailed(name, mats=mats, seed=seed, **kw)
    w.location = (x, y, z)
    w.rotation_euler = (0, 0, radians(facing))
    return _link(w, col)


def window_row(name, mats, col, face, positions, other, z, seed, **kw):
    """A run of windows on the -Y (face='y') or +X (face='x') elevation."""
    out = []
    for i, p in enumerate(positions):
        if face == "y":
            out.append(add_window(f"{name}_{i}", mats, col, p, other, z, 0,
                                  seed + i * 13, **kw))
        else:
            out.append(add_window(f"{name}_{i}", mats, col, other, p, z, 90,
                                  seed + i * 13, **kw))
    return out


def add_door(name, mats, col, x, y, z, facing, seed, steps=True, canopy=True,
             width=1.12, height=2.12, ground=None, stone="limestone"):
    d = dp.create_door_detailed(name, width=width, height=height, mats=mats,
                                seed=seed)
    d.location = (x, y, z)
    d.rotation_euler = (0, 0, radians(facing))
    _link(d, col)
    if steps and ground is not None:
        st = dp.create_stone_steps_detailed(
            f"{name}_Steps", mats=mats, seed=seed + 5, width=width + 0.6,
            depth=1.05, height=max(0.12, z - ground), n_steps=3, stone=stone)
        st.location = (x, y, ground)
        st.rotation_euler = (0, 0, radians(facing))
        _link(st, col)
    if canopy:
        cp = dp.create_pentice_canopy(f"{name}_Canopy", width=width + 0.85,
                                      depth=0.95, mats=mats, seed=seed + 9)
        cp.location = (x, y, z + height + 0.22)
        cp.rotation_euler = (0, 0, radians(facing))
        _link(cp, col)
    return d


def add_lantern(name, mats, col, x, y, z, facing, seed, lantern=True):
    b = dp.create_lantern_bracket(name, mats=mats, seed=seed, reach=0.48,
                                  lantern=lantern, lit=True)
    b.location = (x, y, z)
    b.rotation_euler = (0, 0, radians(facing))
    return _link(b, col)


def add_sign(name, mats, col, x, y, z, facing, seed, emblem="tankard",
             bw=0.82, bh=0.60):
    sg = dp.create_hanging_sign_detailed(name, mats=mats, seed=seed,
                                         board_w=bw, board_h=bh, emblem=emblem)
    sg.location = (x, y, z)
    sg.rotation_euler = (0, 0, radians(facing))
    return _link(sg, col)


def add_ivy(name, mats, col, x, y, z, facing, seed, h=3.0, w=1.1, corner=False,
            stems=3, density=1.0):
    iv = dp.create_ivy_climber(name, height=h, width=w, mats=mats, seed=seed,
                               stems=stems, density=density, corner=corner,
                               depth=0.16)
    iv.location = (x, y, z)
    iv.rotation_euler = (0, 0, radians(facing))
    return _link(iv, col)


def clutter(name, mats, col, items):
    """Scatter detailed street props. items: (kind, x, y, rot_deg, seed)."""
    made = []
    for i, (kind, x, y, rot, sd) in enumerate(items):
        if kind == "barrel":
            o = dp.create_barrel_detailed(f"{name}_Barrel_{i}", mats=mats,
                                          seed=sd, radius=0.33, height=0.84,
                                          mossy=(i % 3 == 0))
        elif kind == "barrel_open":
            o = dp.create_barrel_detailed(f"{name}_BarrelO_{i}", mats=mats,
                                          seed=sd, radius=0.33, height=0.84,
                                          open_top=True, mossy=True)
        elif kind == "crate":
            o = dp.create_crate_detailed(f"{name}_Crate_{i}", mats=mats,
                                         seed=sd, size=0.62)
        elif kind == "crate_small":
            o = dp.create_crate_detailed(f"{name}_CrateS_{i}", mats=mats,
                                         seed=sd, size=0.50, lid=False,
                                         stencil=False)
        elif kind == "bench":
            o = dp.create_bench_detailed(f"{name}_Bench_{i}", mats=mats,
                                         seed=sd, length=1.55)
        elif kind == "firewood":
            o = dp.create_firewood_stack_detailed(f"{name}_Wood_{i}", mats=mats,
                                                  seed=sd, width=1.45,
                                                  depth=0.52, height=0.84)
        elif kind == "garden":
            o = dp.create_garden_bed(f"{name}_Garden_{i}", mats=mats, seed=sd,
                                     width=2.05, depth=0.78)
        elif kind == "flowerbox":
            o = dp.create_flower_box_standalone_detailed(
                f"{name}_FBox_{i}", mats=mats, seed=sd, length=1.25)
        else:
            continue
        o.location = (x, y, 0.0)
        o.rotation_euler = (0, 0, radians(rot))
        made.append(_link(o, col))
    return made
