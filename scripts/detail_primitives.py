"""
Emberglass Detail Primitive Library - finished-asset geometry.

Everything here resolves a surface that builder_primitives.py leaves as a single
box: individual masonry blocks with recessed mortar, individual roof tiles with
slip/crack/loss damage, chamfered timber with peg joints and knocked corners,
troweled plaster with fallen patches, and the growth/soot/clutter layers that sit
on top of all of it.

Conventions match builder_primitives.py: front faces -Y, ridges run along Y,
+Z is up, and every generator returns a single object carrying its own material
slots so an asset stays one draw call per component.

builder_primitives.py is imported, never modified.
"""

import bpy
import bmesh
import os
import sys
import random
from math import radians, degrees, cos, sin, tan, pi, sqrt, atan2
from mathutils import Vector, Matrix, Euler

# Flat import, and scripts/city must be on sys.path first. Importing city_lod
# both flat and as `city.city_lod` makes two module objects with two separate
# `L` globals, so set_lod() on one is invisible to the other.
_CITY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "city")
if _CITY_DIR not in sys.path:
    sys.path.append(_CITY_DIR)
import city_lod as _lod

from builder_primitives import add_bevel_modifier, link_to_collection


# =============================================================================
# Low-level bmesh helpers
# =============================================================================

def _begin(name, mat_list):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    for m in mat_list:
        obj.data.materials.append(m)
    return obj, mesh, bmesh.new()


def _end(obj, mesh, bm, bevel=0.0, segments=2, angle=35.0):
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    if bevel > 0.0:
        # The bevel is the single largest multiplier in the whole library:
        # measured on the townhouse foundation, 13,330 authored faces evaluate
        # to 69,826 -- 5.2x, and up to 9x on the timber cores. At city viewing
        # distance a 10mm chamfer is sub-pixel, so city LOD drops the segment
        # count and then the modifier entirely. Every generator returns through
        # here, so this one place governs all of them.
        segments = _lod.L.bevel_segments(segments)
        if segments <= 0:
            return obj
        mod = obj.modifiers.new(name="Bevel", type='BEVEL')
        mod.width = bevel
        mod.segments = segments
        mod.limit_method = 'ANGLE'
        mod.angle_limit = radians(angle)
    return obj


def _box(bm, mat_idx=0, size=(1.0, 1.0, 1.0), loc=(0.0, 0.0, 0.0),
         rot=(0.0, 0.0, 0.0), base=False):
    """One cube, scaled / rotated / placed. O(1) material assignment.

    base=True puts the cube's bottom face on z=loc.z instead of its centre.
    """
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res['verts']
    for v in verts:
        for f in v.link_faces:
            f.material_index = mat_idx
    mat = Euler(rot, 'XYZ').to_matrix()
    off = 0.5 if base else 0.0
    base_v = Vector(loc)
    for v in verts:
        p = Vector((v.co.x * size[0],
                    v.co.y * size[1],
                    (v.co.z + off) * size[2]))
        v.co = base_v + (mat @ p)
    return verts


def _blob(bm, mat_idx, loc, size, rot=(0.0, 0.0, 0.0), subdiv=0):
    """Irregular lump - moss clumps, soil, fieldstone. subdiv 0 = 12 verts."""
    res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=0.5)
    verts = res['verts']
    for v in verts:
        for f in v.link_faces:
            f.material_index = mat_idx
    mat = Euler(rot, 'XYZ').to_matrix()
    base_v = Vector(loc)
    for v in verts:
        p = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        v.co = base_v + (mat @ p)
    return verts


def _cyl(bm, mat_idx, radius, depth, loc, rot=(0.0, 0.0, 0.0), segments=8,
         radius2=None, base=False):
    r2 = radius if radius2 is None else radius2
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=segments,
                                radius1=radius, radius2=r2, depth=depth)
    verts = res['verts']
    for v in verts:
        for f in v.link_faces:
            f.material_index = mat_idx
    mat = Euler(rot, 'XYZ').to_matrix()
    base_v = Vector(loc)
    off = depth * 0.5 if base else 0.0
    for v in verts:
        p = Vector((v.co.x, v.co.y, v.co.z + off))
        v.co = base_v + (mat @ p)
    return verts


def _quad(bm, mat_idx, pts):
    """Flat polygon from a list of 3D points (leaves, streaks, blades)."""
    verts = [bm.verts.new(Vector(p)) for p in pts]
    face = bm.faces.new(verts)
    face.material_index = mat_idx
    return verts


def _set_mat(verts, mat_idx):
    for v in verts:
        for f in v.link_faces:
            f.material_index = mat_idx


# -----------------------------------------------------------------------------
# Chamfered, bowed, chipped timber - the base unit of every beam in this library
# -----------------------------------------------------------------------------

def _prism_beam(bm, mat_idx, length, width, depth, loc=(0, 0, 0), rot=(0, 0, 0),
                chamfer=0.018, rings=5, bow=0.0, twist=0.0, rng=None,
                chips=0, chip_mat=None, base=True, taper=1.0):
    """Octagonal-section timber: hand-adzed chamfer, slight bow, worn corners.

    Runs along local +Z. A real hewn beam is never a clean box - the chamfer and
    the bow are what separate 'timber' from 'grey cuboid' at sprite resolution.
    """
    rng = rng or random.Random(0)
    hw, hd, c = width * 0.5, depth * 0.5, chamfer
    c = min(c, hw * 0.45, hd * 0.45)
    section = [
        (hw - c, -hd), (hw, -hd + c), (hw, hd - c), (hw - c, hd),
        (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c), (-hw + c, -hd),
    ]

    bow_dir = rng.uniform(0, 2 * pi)
    bow_x, bow_y = cos(bow_dir) * bow, sin(bow_dir) * bow

    ring_verts = []
    for i in range(rings):
        t = i / (rings - 1)
        z = t * length + (0.0 if base else -length * 0.5)
        sag = sin(pi * t)
        s = 1.0 + (taper - 1.0) * t
        jitter = 1.0 + rng.uniform(-0.022, 0.022)
        ang = twist * t
        ca, sa = cos(ang), sin(ang)
        ring = []
        for (px, py) in section:
            px2, py2 = px * s * jitter, py * s * jitter
            rx = px2 * ca - py2 * sa + bow_x * sag
            ry = px2 * sa + py2 * ca + bow_y * sag
            ring.append(bm.verts.new(Vector((rx, ry, z))))
        ring_verts.append(ring)

    faces = []
    for i in range(rings - 1):
        a, b = ring_verts[i], ring_verts[i + 1]
        for k in range(8):
            k2 = (k + 1) % 8
            faces.append(bm.faces.new((a[k], a[k2], b[k2], b[k])))
    faces.append(bm.faces.new(tuple(reversed(ring_verts[0]))))
    faces.append(bm.faces.new(tuple(ring_verts[-1])))
    for f in faces:
        f.material_index = mat_idx

    # Knocked corners: pull a few section verts toward the axis and expose
    # lighter heartwood underneath.
    for _ in range(chips):
        ri = rng.randint(1, max(1, rings - 2))
        k = rng.randint(0, 7)
        v = ring_verts[ri][k]
        v.co.x *= rng.uniform(0.60, 0.82)
        v.co.y *= rng.uniform(0.60, 0.82)
        if chip_mat is not None:
            for f in v.link_faces:
                f.material_index = chip_mat

    all_verts = [v for ring in ring_verts for v in ring]
    mat = Euler(rot, 'XYZ').to_matrix()
    base_v = Vector(loc)
    for v in all_verts:
        v.co = base_v + (mat @ v.co)
    return all_verts


def _peg(bm, mat_idx, loc, rot, radius=0.032, proud=0.016):
    """Draw-bored oak peg standing proud of a mortice-and-tenon joint."""
    return _cyl(bm, mat_idx, radius, proud * 2.0, loc, rot, segments=6)


def _nail_head(bm, mat_idx, loc, rot=(0, 0, 0), radius=0.022):
    return _cyl(bm, mat_idx, radius, 0.018, loc, rot, segments=6)


# -----------------------------------------------------------------------------
# Growth: moss clumps, lichen crusts, weed tufts
# -----------------------------------------------------------------------------

def _moss_clump(bm, mat_idx, loc, scale, rng, squash=0.38):
    """Two or three overlapping lumps - a single sphere reads as a ball."""
    n = rng.randint(2, 3)
    for i in range(n):
        s = scale * rng.uniform(0.55, 1.0)
        _blob(bm, mat_idx,
              (loc[0] + rng.uniform(-scale, scale) * 0.6,
               loc[1] + rng.uniform(-scale, scale) * 0.6,
               loc[2] + rng.uniform(-scale, scale) * 0.25),
              (s, s * rng.uniform(0.7, 1.3), s * squash),
              rot=(0, 0, rng.uniform(0, pi)))


def _moss_run(bm, mat_idx, p0, p1, count, scale, rng, drift=0.02, skip=0.35):
    """Moss following a shaded edge - gappy, never a continuous sausage."""
    p0, p1 = Vector(p0), Vector(p1)
    for i in range(count):
        if rng.random() < skip:
            continue
        t = (i + rng.uniform(0.1, 0.9)) / count
        p = p0.lerp(p1, t) + Vector((rng.uniform(-drift, drift),
                                     rng.uniform(-drift, drift),
                                     rng.uniform(-drift, drift) * 0.5))
        _moss_clump(bm, mat_idx, p, scale * rng.uniform(0.7, 1.35), rng)


def _lichen_patch(bm, mat_idx, loc, radius, normal_axis, rng, plates=4):
    """Flat crusty rosettes - almost no thickness, sits on the stone face."""
    for _ in range(plates):
        r = radius * rng.uniform(0.35, 1.0)
        off = (rng.uniform(-radius, radius) * 0.7,
               rng.uniform(-radius, radius) * 0.7,
               rng.uniform(-radius, radius) * 0.7)
        size = [r, r, r]
        size[normal_axis] = 0.008
        _blob(bm, mat_idx,
              (loc[0] + off[0], loc[1] + off[1], loc[2] + off[2]),
              tuple(size), rot=(0, 0, rng.uniform(0, pi)))


def _weed_tuft(bm, mat_idx, loc, scale, rng, blades=6, up=(0, 0, 1)):
    """Grass/weed pushing out of a joint: bent tapering blades, no billboards."""
    ox, oy, oz = loc
    for _ in range(blades):
        h = scale * rng.uniform(0.6, 1.25)
        yaw = rng.uniform(0, 2 * pi)
        lean = rng.uniform(0.18, 0.62)
        bx, by = cos(yaw) * lean * h, sin(yaw) * lean * h
        w = scale * 0.085
        px, py = -sin(yaw) * w, cos(yaw) * w
        base_a = (ox - px, oy - py, oz)
        base_b = (ox + px, oy + py, oz)
        mid_a = (ox + bx * 0.45 - px * 0.6, oy + by * 0.45 - py * 0.6, oz + h * 0.62)
        mid_b = (ox + bx * 0.45 + px * 0.6, oy + by * 0.45 + py * 0.6, oz + h * 0.62)
        tip = (ox + bx, oy + by, oz + h)
        try:
            _quad(bm, mat_idx, [base_a, base_b, mid_b, mid_a])
            _quad(bm, mat_idx, [mid_a, mid_b, tip])
        except ValueError:
            pass


# =============================================================================
# 1. MASONRY - individually laid irregular blocks with recessed mortar
# =============================================================================

# slot order used by create_masonry_box / create_cobble_apron
M_MORTAR, M_BLK_A, M_BLK_B, M_BLK_C, M_MOSS, M_LICHEN, M_WEED = range(7)


STONE_PALETTES = {
    # mortar, block A, block B, block C
    "limestone":  ("M_Mortar", "M_Stone_Block_A", "M_Stone_Block_B",
                   "M_Stone_Block_C"),
    "granite":    ("M_Mortar_Grey", "M_Granite_A", "M_Granite_B",
                   "M_Granite_C"),
    "ashlar":     ("M_Mortar_Pale", "M_Ashlar_A", "M_Ashlar_B", "M_Ashlar_C"),
    "fieldstone": ("M_Mortar", "M_Fieldstone_A", "M_Fieldstone_B",
                   "M_Fieldstone_C"),
}


def _masonry_slots(mats, stone="limestone"):
    mo, a, b, c = STONE_PALETTES.get(stone, STONE_PALETTES["limestone"])
    return [mats[mo], mats[a], mats[b], mats[c], mats["M_Moss"],
            mats["M_Lichen"], mats["M_Weed_Green"]]


def _lay_face(bm, rng, axis, sign, run_half, other_half, z0, z1, quoin,
              block_len, mortar, proud_rng, shaded, moss_amount, lichen_amount,
              recess=0.025):
    """One course on one face. axis 0 = face normal on X, axis 1 = normal on Y."""
    span_a = -run_half + quoin
    span_b = run_half - quoin
    if span_b - span_a < 0.12:
        return
    bh = (z1 - z0) - mortar
    if bh <= 0.03:
        return
    zc = (z0 + z1) * 0.5

    cursor = span_a
    guard = 0
    while cursor < span_b - 0.02 and guard < 64:
        guard += 1
        bl = rng.uniform(*block_len)
        if span_b - (cursor + bl) < block_len[0] * 0.55:
            bl = span_b - cursor
        bl = min(bl, span_b - cursor)
        if bl < 0.08:
            break
        cx = cursor + bl * 0.5
        t = proud_rng[0] + rng.random() * (proud_rng[1] - proud_rng[0])
        mat_idx = rng.choice([M_BLK_A, M_BLK_A, M_BLK_B, M_BLK_B, M_BLK_C])
        face_pos = sign * (other_half - recess + t * 0.5)
        tilt = rng.uniform(-0.022, 0.022)
        yaw = rng.uniform(-0.016, 0.016)
        eff_l = bl - mortar
        # Real rubble is never one height per course: vary the block and let
        # it sit low or high in its bed, so the joints wander.
        eff_h = bh * rng.uniform(0.74, 1.0)
        zc_b = zc + (bh - eff_h) * rng.uniform(-0.45, 0.45)

        if axis == 0:   # normal along X, run along Y
            _box(bm, mat_idx, size=(t, eff_l, eff_h),
                 loc=(face_pos, cx, zc_b), rot=(tilt, yaw, 0.0))
            outer = (sign * (other_half + t * 0.35), cx, zc_b)
        else:           # normal along Y, run along X
            _box(bm, mat_idx, size=(eff_l, t, eff_h),
                 loc=(cx, face_pos, zc_b), rot=(tilt, yaw, 0.0))
            outer = (cx, sign * (other_half + t * 0.35), zc_b)

        if shaded and rng.random() < moss_amount:
            _moss_clump(bm, M_MOSS, (outer[0], outer[1], zc_b + eff_h * 0.42),
                        rng.uniform(0.035, 0.075), rng, squash=0.5)
        if rng.random() < lichen_amount:
            _lichen_patch(bm, M_LICHEN, outer, rng.uniform(0.05, 0.10),
                          axis, rng, plates=rng.randint(2, 4))

        cursor += bl


def create_masonry_box(name, width, depth, height, location=(0, 0, 0), mats=None,
                       seed=11, course_h=0.26, block_len=(0.32, 0.56),
                       mortar=0.035, quoins=True, plinth=True, ledge=True,
                       shaded_faces=("-X", "+Y"), moss_amount=0.16,
                       lichen_amount=0.09, weeds=True, weed_rows=2,
                       ground_moss=True, stone="limestone"):
    """A masonry volume built block by block on all four faces.

    The mortar core sits 25mm behind the block faces so every joint reads as a
    real recess under raking light; quoins interlock at the corners so the two
    faces of a corner never butt into each other.
    """
    obj, mesh, bm = _begin(name, _masonry_slots(mats, stone))
    rng = random.Random(seed)
    hw, hd = width * 0.5, depth * 0.5

    # Mortar core. It sits well back so each block stands proud and the
    # joint between them is a real shadow rather than a drawn line.
    _box(bm, M_MORTAR, size=(width - 0.17, depth - 0.17, height),
         loc=(0, 0, 0), base=True)

    # Splayed plinth so the wall reads as founded, not floating
    if plinth:
        _box(bm, M_BLK_B, size=(width + 0.16, depth + 0.16, 0.10),
             loc=(0, 0, 0.0), base=True)
        for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            run = hd if ax == 0 else hw
            n = max(3, int(run * 2 / 0.42))
            for i in range(n):
                t = (i + 0.5) / n
                c = -run + 2 * run * t
                bl = (2 * run / n) - 0.03
                if ax == 0:
                    _box(bm, rng.choice([M_BLK_A, M_BLK_B, M_BLK_C]),
                         size=(0.09, bl, 0.20),
                         loc=(sgn * (hw + 0.035), c, 0.10),
                         rot=(rng.uniform(-0.02, 0.02), 0, 0), base=True)
                else:
                    _box(bm, rng.choice([M_BLK_A, M_BLK_B, M_BLK_C]),
                         size=(bl, 0.09, 0.20),
                         loc=(c, sgn * (hd + 0.035), 0.10),
                         rot=(0, rng.uniform(-0.02, 0.02), 0), base=True)

    # Course boundaries, jittered but monotonic so the wall tiles exactly
    z_bot = 0.30 if plinth else 0.0
    z_top = height - (0.16 if ledge else 0.0)
    n_courses = max(2, int(round((z_top - z_bot) / course_h)))
    ch = (z_top - z_bot) / n_courses
    bounds = [z_bot]
    for i in range(1, n_courses):
        bounds.append(z_bot + i * ch + rng.uniform(-ch * 0.10, ch * 0.10))
    bounds.append(z_top)

    q_long, q_short = 0.40, 0.25
    shaded_set = set(shaded_faces)

    for i in range(n_courses):
        z0, z1 = bounds[i], bounds[i + 1]
        even = (i % 2 == 0)
        qx = q_long if even else q_short     # quoin reach along X
        qy = q_short if even else q_long     # quoin reach along Y

        if quoins:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    t = rng.uniform(0.095, 0.145)
                    _box(bm, rng.choice([M_BLK_C, M_BLK_A, M_BLK_C]),
                         size=(qx + t, qy + t, (z1 - z0) - mortar),
                         loc=(sx * (hw + t * 0.5 - qx * 0.5),
                              sy * (hd + t * 0.5 - qy * 0.5),
                              (z0 + z1) * 0.5),
                         rot=(0, 0, rng.uniform(-0.010, 0.010)))
        else:
            qx = qy = 0.0

        proud = (0.090, 0.145)
        # -Y / +Y faces run along X, quoins eat qx from each end
        for sy in (-1, 1):
            shaded = ("+Y" if sy > 0 else "-Y") in shaded_set
            _lay_face(bm, rng, 1, sy, hw, hd, z0, z1, qx, block_len, mortar,
                      proud, shaded, moss_amount, lichen_amount, recess=0.085)
        # -X / +X faces run along Y
        for sx in (-1, 1):
            shaded = ("+X" if sx > 0 else "-X") in shaded_set
            _lay_face(bm, rng, 0, sx, hd, hw, z0, z1, qy, block_len, mortar,
                      proud, shaded, moss_amount, lichen_amount, recess=0.085)

    # Drip ledge / string course at the wall head, laid as separate stones
    if ledge:
        lz = height - 0.16
        for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            run = hd if ax == 0 else hw
            n = max(3, int(run * 2 / 0.48))
            for i in range(n):
                t = (i + 0.5) / n
                c = -run + 2 * run * t
                bl = (2 * run / n) - 0.035
                mi = rng.choice([M_BLK_A, M_BLK_C])
                if ax == 0:
                    _box(bm, mi, size=(0.14, bl, 0.16),
                         loc=(sgn * (hw + 0.045), c, lz), base=True)
                    edge = (sgn * (hw + 0.10), c, lz + 0.17)
                else:
                    _box(bm, mi, size=(bl, 0.14, 0.16),
                         loc=(c, sgn * (hd + 0.045), lz), base=True)
                    edge = (c, sgn * (hd + 0.10), lz + 0.17)
                if rng.random() < 0.35:
                    _moss_clump(bm, M_MOSS, edge, rng.uniform(0.075, 0.145), rng)

    # Damp moss skirt where the wall meets the ground, all round
    if ground_moss:
        for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            run = hd if ax == 0 else hw
            # Two runs: one in the angle where the plinth meets the ground,
            # one along the plinth's weathering top where water sits.
            for (off, z, sc) in ((0.15, 0.035, 0.155), (0.055, 0.295, 0.105)):
                if ax == 0:
                    p0 = (sgn * (hw + off), -run, z)
                    p1 = (sgn * (hw + off), run, z)
                else:
                    p0 = (-run, sgn * (hd + off), z)
                    p1 = (run, sgn * (hd + off), z)
                _moss_run(bm, M_MOSS, p0, p1, int(run * 2 / 0.19) + 2,
                          sc, rng, drift=0.04, skip=0.18)

    # Weeds rooting in the lower joints
    if weeds:
        for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            run = hd if ax == 0 else hw
            n = max(2, int(run * 2 / 0.55))
            for i in range(n):
                if rng.random() < 0.40:
                    continue
                t = (i + rng.uniform(0.15, 0.85)) / n
                c = -run + 2 * run * t
                zc = rng.uniform(0.32, 0.32 + weed_rows * course_h)
                if ax == 0:
                    loc = (sgn * (hw + 0.075), c, zc)
                else:
                    loc = (c, sgn * (hd + 0.075), zc)
                _weed_tuft(bm, M_WEED, loc, rng.uniform(0.17, 0.32), rng,
                           blades=rng.randint(5, 9))

    obj.location = location
    return _end(obj, mesh, bm, bevel=0.012, segments=2)


# =============================================================================
# 2. ROOF - individually laid tiles with slip / crack / loss damage
# =============================================================================

T_TIMBER, T_A, T_B, T_C, T_AGED, T_MOSS, T_VOID, T_LICHEN = range(8)


ROOF_PALETTES = {
    "clay":    ("M_Tile_A", "M_Tile_B", "M_Tile_C", "M_Tile_Aged"),
    "slate":   ("M_Slate_A", "M_Slate_B", "M_Slate_C", "M_Slate_Aged"),
    "shingle": ("M_Shingle_A", "M_Shingle_B", "M_Shingle_C", "M_Shingle_Aged"),
    "thatch":  ("M_Thatch_A", "M_Thatch_B", "M_Thatch_A", "M_Thatch_Aged"),
}


def _roof_slots(mats, palette="clay"):
    a, b, c, aged = ROOF_PALETTES.get(palette, ROOF_PALETTES["clay"])
    return [mats["M_Timber_Aged"], mats[a], mats[b], mats[c], mats[aged],
            mats["M_Moss"], mats["M_Roof_Void"], mats["M_Lichen"]]


def _patch_noise(rng_seed, row, col, cell=3):
    """Low-frequency hash so aged tiles and moss form patches, not static."""
    h = (int(row // cell) * 73856093) ^ (int(col // cell) * 19349663) ^ (rng_seed * 83492791)
    h &= 0x7FFFFFFF
    return (h % 10000) / 10000.0


def create_tiled_roof_y(name, span_x, length_y, overhang_eave=0.42,
                        overhang_gable=0.32, mats=None, seed=23, pitch_deg=48.0,
                        tile_w=0.26, exposure=0.185, tile_len=0.30,
                        tile_thick=0.038, damage=1.0, shaded_slope=-1,
                        moss_amount=1.0, ridge_caps=True, bargeboards=True,
                        palette="clay"):
    """Ridge along Y, slopes falling to -X and +X, laid tile by tile.

    Returns (object, pitch_height). Tiles are staggered course to course, each
    one individually rotated and lifted, a low-frequency hash drives patches of
    aged and mossy tile, and a small fraction of tiles are slipped, cracked or
    missing so the field never reads as a repeated stamp.
    """
    obj, mesh, bm = _begin(name, _roof_slots(mats, palette))
    rng = random.Random(seed)

    a = radians(pitch_deg)
    ca, sa = cos(a), sin(a)
    half = span_x * 0.5
    pitch_h = half * tan(a)
    total_half = half + overhang_eave
    slope_len = total_half / ca
    total_y = length_y + overhang_gable * 2.0
    n_rows = max(4, int(round(slope_len / exposure)))
    exposure = slope_len / n_rows
    n_cols = max(4, int(round(total_y / tile_w)))
    col_w = total_y / n_cols

    def beta(sx):
        """Rotation about Y that lays a box's local +X straight down the slope.

        R_y(B) maps local +X to (cos B, 0, -sin B); the down-slope direction is
        (sx*cos a, 0, -sin a), so B = a on the +X pitch and pi - a on the -X one.
        """
        return a if sx > 0 else (pi - a)

    for sign_x in (-1, 1):
        # Down-slope unit vector from the ridge, and the slope's outward normal
        dx, dz = sign_x * ca, -sa
        nx, nz = sign_x * sa, ca
        shaded = (sign_x == shaded_slope)
        b = beta(sign_x)

        def on_slope(s, y, lift, _dx=dx, _dz=dz, _nx=nx, _nz=nz):
            """Point s metres down-slope from the ridge, lift metres proud."""
            return (_dx * s + _nx * lift, y, pitch_h + _dz * s + _nz * lift)

        # Decking + battens (only ever seen through a missing tile)
        deck_mid = on_slope(slope_len * 0.5, 0.0, -0.045)
        _box(bm, T_VOID, size=(slope_len, total_y + 0.02, 0.05),
             loc=deck_mid, rot=(0, b, 0))
        for r in range(n_rows):
            s = (r + 1) * exposure
            bp = on_slope(s, 0.0, -0.012)
            _box(bm, T_TIMBER, size=(0.05, total_y, 0.032), loc=bp, rot=(0, b, 0))

        # Tile field, eave course first
        for r in range(n_rows):
            s_head = (r + 1) * exposure
            stagger = (col_w * 0.5) if (r % 2) else 0.0
            for c in range(n_cols + 1):
                y = -total_y * 0.5 + stagger + (c + 0.5) * col_w
                if y < -total_y * 0.5 - col_w * 0.25 or y > total_y * 0.5 + col_w * 0.25:
                    continue
                y = max(-total_y * 0.5 + col_w * 0.35,
                        min(total_y * 0.5 - col_w * 0.35, y))

                patch = _patch_noise(seed, r, c, cell=3)
                edge_patch = _patch_noise(seed + 7, r, c, cell=2)
                roll = rng.random()

                if patch > 0.86:
                    mat_idx = T_AGED
                elif roll < 0.40:
                    mat_idx = T_A
                elif roll < 0.72:
                    mat_idx = T_B
                else:
                    mat_idx = T_C

                dmg = rng.random()
                s_centre = s_head - tile_len * 0.5
                lift = 0.011 + rng.uniform(-0.006, 0.011)
                yaw = rng.uniform(-0.045, 0.045)
                tilt = rng.uniform(-0.035, 0.035)

                if dmg < 0.016 * damage and 1 < r < n_rows - 2:
                    continue                                   # tile lost
                if dmg < 0.032 * damage and 1 < r < n_rows - 2:
                    # slipped tile hanging off its peg
                    p = on_slope(s_centre + 0.09, y + rng.uniform(-0.03, 0.03),
                                 lift + 0.012)
                    _box(bm, T_AGED,
                         size=(tile_len, col_w - 0.012, tile_thick),
                         loc=p, rot=(rng.uniform(0.28, 0.52), b + tilt, yaw))
                    continue
                if dmg < 0.055 * damage:
                    # cracked in two, halves drifted apart
                    for hsign in (-1, 1):
                        hw_ = (col_w - 0.012) * 0.5 - 0.012
                        p = on_slope(s_centre, y + hsign * (hw_ * 0.5 + 0.012),
                                     lift)
                        _box(bm, mat_idx, size=(tile_len, hw_, tile_thick),
                             loc=p, rot=(rng.uniform(-0.05, 0.05), b + tilt,
                                         yaw + hsign * 0.03))
                    continue

                p = on_slope(s_centre, y, lift)
                _box(bm, mat_idx, size=(tile_len, col_w - 0.012, tile_thick),
                     loc=p, rot=(tilt, b, yaw))

                # Moss gathers low on the slope and on the shaded pitch
                low = r < 3
                if moss_amount > 0 and (low or (shaded and edge_patch > 0.78)):
                    if rng.random() < (0.30 if low else 0.34) * moss_amount:
                        mp = on_slope(s_head - 0.02, y + rng.uniform(-0.05, 0.05),
                                      lift + 0.020)
                        _moss_clump(bm, T_MOSS, mp,
                                    rng.uniform(0.065, 0.145), rng, squash=0.45)
                if shaded and rng.random() < 0.04:
                    lp = on_slope(s_centre, y, lift + 0.019)
                    _lichen_patch(bm, T_LICHEN, lp, rng.uniform(0.04, 0.08),
                                  2, rng, plates=2)

            # Tilting fillet: double eave course, kicked up
            if r == 0:
                for c in range(n_cols):
                    y = -total_y * 0.5 + (c + 0.5) * col_w
                    p = on_slope(exposure * 0.55, y, 0.030)
                    _box(bm, rng.choice([T_A, T_B, T_C, T_AGED]),
                         size=(tile_len * 0.92, col_w - 0.012, tile_thick),
                         loc=p, rot=(rng.uniform(-0.03, 0.03),
                                     b - sign_x * 0.075,
                                     rng.uniform(-0.04, 0.04)))

        # Fascia board under the eave, with exposed rafter feet over it
        ep = on_slope(slope_len, 0.0, -0.045)
        _box(bm, T_TIMBER, size=(0.055, total_y + 0.05, 0.165),
             loc=(ep[0], ep[1], ep[2] - 0.075), rot=(0, 0, 0))
        n_raft = max(4, int(total_y / 0.52))
        for i in range(n_raft):
            ry = -total_y * 0.5 + (i + 0.5) * (total_y / n_raft)
            rp = on_slope(slope_len - 0.20, ry, -0.085)
            _prism_beam(bm, T_TIMBER, 0.46, 0.075, 0.115,
                        loc=rp, rot=(0, b + pi / 2, 0), chamfer=0.012,
                        rings=3, bow=0.004, rng=rng, chips=1,
                        chip_mat=T_TIMBER, base=True)

    # Half-round ridge caps bedded in mortar, each one jittered
    if ridge_caps:
        n_cap = max(4, int(total_y / 0.30))
        cap_l = total_y / n_cap
        for i in range(n_cap):
            y = -total_y * 0.5 + (i + 0.5) * cap_l
            mi = T_AGED if _patch_noise(seed + 3, i, 0, cell=2) > 0.72 else \
                rng.choice([T_A, T_B, T_C])
            _cyl(bm, mi, 0.115, cap_l * 0.97,
                 (rng.uniform(-0.012, 0.012), y, pitch_h + 0.055),
                 rot=(pi / 2, 0, rng.uniform(-0.05, 0.05)), segments=8)
            if rng.random() < 0.28 * moss_amount:
                _moss_clump(bm, T_MOSS,
                            (shaded_slope * 0.09, y + rng.uniform(-0.05, 0.05),
                             pitch_h + 0.11),
                            rng.uniform(0.07, 0.135), rng)

    # Bargeboards closing the gable verges, with a carved drop finial
    if bargeboards:
        for sy in (-1, 1):
            y = sy * (total_y * 0.5 - 0.02)
            for sx in (-1, 1):
                # Beam runs along +Z locally; b + pi/2 lays it down the slope
                start = (sx * sa * 0.075, y, pitch_h + ca * 0.075)
                _prism_beam(bm, T_TIMBER, slope_len + 0.06, 0.075, 0.24,
                            loc=start, rot=(0, beta(sx) + pi / 2, 0),
                            chamfer=0.016, rings=4, bow=0.008, rng=rng,
                            chips=3, chip_mat=T_TIMBER, base=True)
            # Carved drop finial where the verges meet at the apex
            _box(bm, T_TIMBER, size=(0.13, 0.10, 0.34),
                 loc=(0, y, pitch_h - 0.02))
            _cyl(bm, T_TIMBER, 0.075, 0.09, (0, y, pitch_h - 0.20),
                 segments=8, radius2=0.030)

    return _end(obj, mesh, bm, bevel=0.007, segments=1, angle=40.0), pitch_h


# =============================================================================
# 3. PLASTER - troweled render with fallen patches over brick nogging
# =============================================================================

P_NOG, P_PLASTER, P_WARM, P_LATH, P_MOSS, P_TIMBER = range(6)


def create_plaster_panel(name, width, height, depth=0.16, location=(0, 0, 0),
                         rot_z=0.0, mats=None, seed=5, damage=1,
                         coat_cell=0.22, moss_base=True):
    """A render panel built as overlapping troweled coats over brick nogging.

    Damage is a region left uncoated: the nogging and riven lath behind it show
    through, with a thicker ragged lip where the render let go.
    """
    obj, mesh, bm = _begin(name, [
        mats["M_Brick_Nogging"], mats["M_Plaster_Weathered"],
        mats["M_Plaster_Warm"], mats["M_Lath"], mats["M_Moss"],
        mats["M_Timber_Aged"], mats["M_Plaster_Repair"]])
    P_REPAIR = 6
    rng = random.Random(seed)
    hw, hh = width * 0.5, height * 0.5

    # Nogging core
    _box(bm, P_NOG, size=(width, depth * 0.44, height), loc=(0, 0, 0))

    # Riven lath across the core - only visible inside a damage hole
    n_lath = max(3, int(height / 0.16))
    for i in range(n_lath):
        z = -hh + (i + 0.5) * (height / n_lath)
        _box(bm, P_LATH, size=(width * 0.99, 0.028, height / n_lath * 0.62),
             loc=(0, -depth * 0.23, z), rot=(rng.uniform(-0.01, 0.01), 0, 0))

    # Damage regions, in normalised panel space
    holes = []
    for _ in range(damage):
        holes.append((rng.uniform(-0.75, 0.75), rng.uniform(-0.8, 0.55),
                      rng.uniform(0.16, 0.30), rng.uniform(0.18, 0.34)))

    def in_hole(u, v):
        for (hu, hv, ru, rv) in holes:
            d = ((u - hu) / ru) ** 2 + ((v - hv) / rv) ** 2
            if d < 1.0 + rng.uniform(-0.18, 0.18):
                return True
        return False

    # Troweled coats: overlapping irregular plates, two tones, varied thickness
    nx = max(3, int(width / coat_cell))
    nz = max(3, int(height / coat_cell))
    for i in range(nx):
        for j in range(nz):
            u = -1.0 + 2.0 * (i + 0.5) / nx
            v = -1.0 + 2.0 * (j + 0.5) / nz
            if in_hole(u, v):
                continue
            px = u * hw + rng.uniform(-0.02, 0.02)
            pz = v * hh + rng.uniform(-0.02, 0.02)
            sx = (width / nx) * rng.uniform(1.12, 1.42)
            sz = (height / nz) * rng.uniform(1.12, 1.42)
            sx = min(sx, width * 0.9)
            sz = min(sz, height * 0.9)
            px = max(-hw + sx * 0.5, min(hw - sx * 0.5, px))
            pz = max(-hh + sz * 0.5, min(hh - sz * 0.5, pz))
            thick = depth * rng.uniform(0.22, 0.50)
            r = rng.random()
            mi = P_REPAIR if r < 0.13 else (P_WARM if r < 0.42 else P_PLASTER)
            _box(bm, mi, size=(sx, thick, sz),
                 loc=(px, -depth * 0.5 + thick * 0.35, pz),
                 rot=(rng.uniform(-0.012, 0.012), rng.uniform(-0.02, 0.02),
                      rng.uniform(-0.012, 0.012)))

    # Ragged lip where the render broke away
    for (hu, hv, ru, rv) in holes:
        for k in range(12):
            ang = 2 * pi * k / 12 + rng.uniform(-0.12, 0.12)
            u = hu + cos(ang) * ru * rng.uniform(1.0, 1.16)
            v = hv + sin(ang) * rv * rng.uniform(1.0, 1.16)
            px = max(-hw + 0.04, min(hw - 0.04, u * hw))
            pz = max(-hh + 0.04, min(hh - 0.04, v * hh))
            _box(bm, P_PLASTER,
                 size=(rng.uniform(0.05, 0.12), depth * rng.uniform(0.40, 0.60),
                       rng.uniform(0.05, 0.12)),
                 loc=(px, -depth * 0.5 + depth * 0.22, pz),
                 rot=(0, 0, rng.uniform(-0.4, 0.4)))

    # Damp moss creeping up from the panel's bottom edge
    if moss_base:
        _moss_run(bm, P_MOSS, (-hw + 0.06, -depth * 0.52, -hh + 0.02),
                  (hw - 0.06, -depth * 0.52, -hh + 0.02),
                  max(3, int(width / 0.22)), 0.055, rng, drift=0.025, skip=0.45)

    obj.location = location
    obj.rotation_euler = (0, 0, rot_z)
    return _end(obj, mesh, bm, bevel=0.009, segments=2)


# =============================================================================
# 4. TIMBER FRAME - chamfered, pegged, braced, with knocked corners
# =============================================================================

F_TIMBER, F_CHIP, F_IRON, F_MOSS = range(4)


def _frame_slots(mats):
    return [mats["M_Timber_Aged"], mats["M_Timber_Chip"], mats["M_Iron_Aged"],
            mats["M_Moss"]]


def create_timber_frame(name, members, mats=None, seed=17, chamfer=0.020,
                        location=(0, 0, 0)):
    """Assemble a frame from a list of member dicts into one object.

    Each member: {p0, p1, w, d, pegs, chips, bow, twist}. p0/p1 are world-ish
    points in the object's local space; the beam is built along that vector so
    braces, studs, plates and rails all come from one code path.
    """
    obj, mesh, bm = _begin(name, _frame_slots(mats))
    rng = random.Random(seed)

    for m in members:
        p0, p1 = Vector(m["p0"]), Vector(m["p1"])
        d = p1 - p0
        L = d.length
        if L < 0.02:
            continue
        dirv = d.normalized()
        z_axis = Vector((0, 0, 1))
        if abs(dirv.dot(z_axis)) > 0.9999:
            rot = Euler((0, 0, 0)) if dirv.z > 0 else Euler((pi, 0, 0))
        else:
            rot = z_axis.rotation_difference(dirv).to_euler()
        _prism_beam(bm, F_TIMBER, L, m.get("w", 0.17), m.get("d", 0.17),
                    loc=p0, rot=(rot.x, rot.y, rot.z), chamfer=chamfer,
                    rings=m.get("rings", 5), bow=m.get("bow", L * 0.006),
                    twist=m.get("twist", rng.uniform(-0.03, 0.03)), rng=rng,
                    chips=m.get("chips", 2), chip_mat=F_CHIP, base=True)

        # Draw-bored pegs at the joints
        for frac in m.get("pegs", []):
            pp = p0 + dirv * (L * frac)
            side = m.get("peg_axis", (0, -1, 0))
            n = Vector(side).normalized()
            prot = Vector((0, 0, 1)).rotation_difference(n).to_euler()
            _peg(bm, F_TIMBER,
                 pp + n * (m.get("d", 0.17) * 0.5 - 0.004),
                 (prot.x, prot.y, prot.z), radius=0.030, proud=0.014)

        if m.get("moss"):
            _moss_run(bm, F_MOSS, p0 + Vector((0, -m.get("d", 0.17) * 0.5, 0)),
                      p1 + Vector((0, -m.get("d", 0.17) * 0.5, 0)),
                      max(2, int(L / 0.30)), 0.045, rng, skip=0.55)

    obj.location = location
    return _end(obj, mesh, bm, bevel=0.006, segments=1, angle=40.0)


# =============================================================================
# 5. CHIMNEY with soot
# =============================================================================

def create_chimney_detailed(name, height=3.8, width=0.85, depth=0.85, mats=None,
                            seed=31, smoke=True, soot=True,
                            stone="limestone"):
    """Coursed stone stack, moulded cap, clay pot, flaunching, soot staining."""
    obj, mesh, bm = _begin(name, _masonry_slots(mats, stone) + [
        mats["M_Soot"], mats["M_Terracotta"], mats["M_Smoke"]])
    S_SOOT, S_POT, S_SMOKE = 7, 8, 9
    rng = random.Random(seed)
    hw, hd = width * 0.5, depth * 0.5

    _box(bm, M_MORTAR, size=(width - 0.12, depth - 0.12, height),
         loc=(0, 0, 0), base=True)

    body_h = height - 0.42
    n_courses = max(4, int(body_h / 0.24))
    ch = body_h / n_courses
    for i in range(n_courses):
        z0 = i * ch
        z1 = z0 + ch
        even = (i % 2 == 0)
        qx = 0.34 if even else 0.22
        qy = 0.22 if even else 0.34
        for sx in (-1, 1):
            for sy in (-1, 1):
                t = rng.uniform(0.045, 0.075)
                _box(bm, rng.choice([M_BLK_A, M_BLK_B, M_BLK_C]),
                     size=(qx + t, qy + t, ch - 0.032),
                     loc=(sx * (hw + t * 0.5 - qx * 0.5),
                          sy * (hd + t * 0.5 - qy * 0.5), (z0 + z1) * 0.5),
                     rot=(0, 0, rng.uniform(-0.012, 0.012)))
        for sy in (-1, 1):
            _lay_face(bm, rng, 1, sy, hw, hd, z0, z1, qx, (0.16, 0.34), 0.040,
                      (0.070, 0.110), sy > 0, 0.10, 0.07, recess=0.060)
        for sx in (-1, 1):
            _lay_face(bm, rng, 0, sx, hd, hw, z0, z1, qy, (0.16, 0.34), 0.040,
                      (0.070, 0.110), sx < 0, 0.10, 0.07, recess=0.060)

    # Corbelled, moulded cap
    _box(bm, M_BLK_C, size=(width + 0.16, depth + 0.16, 0.12),
         loc=(0, 0, body_h), base=True)
    _box(bm, M_BLK_A, size=(width + 0.26, depth + 0.26, 0.11),
         loc=(0, 0, body_h + 0.12), base=True)
    _box(bm, M_BLK_C, size=(width + 0.18, depth + 0.18, 0.09),
         loc=(0, 0, body_h + 0.23), base=True)
    # Sloped flaunching around the pot
    _box(bm, M_MORTAR, size=(width + 0.06, depth + 0.06, 0.09),
         loc=(0, 0, body_h + 0.32), base=True)

    # Clay flue pot
    pot_z = body_h + 0.40
    _cyl(bm, S_POT, 0.20, 0.44, (0, 0, pot_z), segments=10, radius2=0.175,
         base=True)
    _cyl(bm, S_POT, 0.215, 0.07, (0, 0, pot_z + 0.40), segments=10, base=True)

    if soot:
        # Soot ring inside and over the pot mouth
        _cyl(bm, S_SOOT, 0.168, 0.10, (0, 0, pot_z + 0.36), segments=10,
             base=True)
        _cyl(bm, S_SOOT, 0.225, 0.05, (0, 0, pot_z + 0.40), segments=10,
             radius2=0.24, base=True)
        # Staining washed down the cap and the top courses
        n_streak = 4
        for sy in (-1, 1):
            for k in range(n_streak):
                x = -hw * 0.66 + k * (width * 0.66 / (n_streak - 1.0))
                run = rng.uniform(0.22, 0.62)
                _box(bm, S_SOOT,
                     size=(rng.uniform(0.045, 0.105), 0.030, run),
                     loc=(x + rng.uniform(-0.07, 0.07),
                          sy * (hd + 0.075), body_h - run * 0.5 - 0.02),
                     rot=(0, rng.uniform(-0.05, 0.05), 0))
        for sx in (-1, 1):
            for k in range(n_streak):
                y = -hd * 0.66 + k * (depth * 0.66 / (n_streak - 1.0))
                run = rng.uniform(0.22, 0.62)
                _box(bm, S_SOOT,
                     size=(0.030, rng.uniform(0.045, 0.105), run),
                     loc=(sx * (hw + 0.075), y + rng.uniform(-0.07, 0.07),
                          body_h - run * 0.5 - 0.02),
                     rot=(rng.uniform(-0.05, 0.05), 0, 0))
        # Thin blackened line right under the cap where the wash starts
        for sy in (-1, 1):
            _box(bm, S_SOOT, size=(width * 0.88, 0.026, 0.055),
                 loc=(0, sy * (hd + 0.075), body_h - 0.03))
        for sx in (-1, 1):
            _box(bm, S_SOOT, size=(0.026, depth * 0.88, 0.055),
                 loc=(sx * (hw + 0.075), 0, body_h - 0.03))
        # Soot film over the cap top
        _box(bm, S_SOOT, size=(width + 0.10, depth + 0.10, 0.012),
             loc=(0, 0, body_h + 0.325), base=True)

    if smoke:
        z = pot_z + 0.58
        r = 0.16
        for i in range(5):
            _blob(bm, S_SMOKE,
                  (rng.uniform(-0.10, 0.10) * (i + 1), rng.uniform(-0.10, 0.10) * (i + 1),
                   z + i * 0.34),
                  (r, r, r * 0.82), rot=(0, 0, rng.uniform(0, pi)), subdiv=1)
            r *= 1.22

    return _end(obj, mesh, bm, bevel=0.010, segments=2)


# =============================================================================
# 6. IVY
# =============================================================================

def _ivy_leaf(bm, mat_idx, loc, size, rot, rng):
    """Five-lobed ivy leaf as a shallow cupped pentagon."""
    s = size
    pts_2d = [(0.0, -0.55), (0.62, -0.10), (0.34, 0.52), (-0.34, 0.52), (-0.62, -0.10)]
    mat = Euler(rot, 'XYZ').to_matrix()
    base_v = Vector(loc)
    pts = []
    for (u, v) in pts_2d:
        cup = -0.10 * (u * u + v * v)
        p = Vector((u * s, v * s, cup * s))
        pts.append(base_v + (mat @ p))
    try:
        _quad(bm, mat_idx, pts)
    except ValueError:
        pass


def create_ivy_climber(name, height=3.0, width=1.4, mats=None, seed=41,
                       stems=3, density=1.0, corner=False, depth=0.14,
                       flowers=False):
    """Ivy climbing a wall face (or wrapping a corner when corner=True).

    Growth thins with height and throws a few bare tendrils past the leaf mass,
    which is what stops a climber reading as a green rectangle.
    """
    slots = [mats["M_Ivy_Stem"], mats["M_Ivy_Leaf"], mats["M_Moss"]]
    if flowers:
        slots.append(mats["M_Flowers"])
    obj, mesh, bm = _begin(name, slots)
    I_STEM, I_LEAF, I_DARK, I_FLOWER = 0, 1, 2, 3
    rng = random.Random(seed)

    for si in range(stems):
        base_u = (-0.5 + (si + 0.5) / stems) * width + rng.uniform(-0.05, 0.05)
        top = height * rng.uniform(0.72, 1.0)
        segs = max(5, int(top / 0.22))
        u = base_u
        prev = None
        for k in range(segs + 1):
            z = top * k / segs
            u += rng.uniform(-0.055, 0.055)
            u = max(-width * 0.55, min(width * 0.55, u))
            if corner:
                # split the run between the two faces meeting at the corner
                side = 1 if (si % 2 == 0) else 0
                p = (u if side else depth * 0.35,
                     -depth * 0.35 if side else u, z)
            else:
                p = (u, -depth * 0.35, z)
            if prev is not None:
                mid = ((prev[0] + p[0]) * 0.5, (prev[1] + p[1]) * 0.5,
                       (prev[2] + p[2]) * 0.5)
                dv = Vector(p) - Vector(prev)
                L = dv.length
                if L > 0.01:
                    rot = Vector((0, 0, 1)).rotation_difference(dv.normalized()).to_euler()
                    _box(bm, I_STEM, size=(0.026, 0.026, L),
                         loc=mid, rot=(rot.x, rot.y, rot.z))
            prev = p

            # Leaf cluster, thinning as the stem climbs
            fall = 1.0 - (z / max(0.001, top)) * 0.62
            n_leaf = int(rng.uniform(2, 6) * density * fall)
            for _ in range(n_leaf):
                lsz = rng.uniform(0.075, 0.145)
                off = (rng.uniform(-0.16, 0.16), rng.uniform(-0.05, 0.02),
                       rng.uniform(-0.10, 0.10))
                lp = (p[0] + off[0], p[1] + off[1] - 0.02, p[2] + off[2])
                mi = I_LEAF if rng.random() < 0.72 else I_DARK
                _ivy_leaf(bm, mi, lp, lsz,
                          (rng.uniform(-1.3, 1.3), rng.uniform(-1.3, 1.3),
                           rng.uniform(0, 2 * pi)), rng)
            if flowers and rng.random() < 0.06:
                _blob(bm, I_FLOWER, (p[0], p[1] - 0.05, p[2]),
                      (0.035, 0.035, 0.035))

        # Bare tendrils reaching above the leaf mass
        for _ in range(rng.randint(1, 3)):
            tz = top
            tu = u
            for k in range(rng.randint(2, 4)):
                nz = tz + rng.uniform(0.10, 0.22)
                nu = tu + rng.uniform(-0.10, 0.10)
                _box(bm, I_STEM, size=(0.016, 0.016, nz - tz),
                     loc=((tu + nu) * 0.5, -depth * 0.35, (tz + nz) * 0.5),
                     rot=(0, rng.uniform(-0.35, 0.35), 0))
                if rng.random() < 0.5:
                    _ivy_leaf(bm, I_LEAF, (nu, -depth * 0.38, nz), 0.065,
                              (rng.uniform(-1.0, 1.0), 0, rng.uniform(0, pi)), rng)
                tz, tu = nz, nu

    return _end(obj, mesh, bm, bevel=0.0)


# =============================================================================
# 7. COBBLE APRON
# =============================================================================

def create_cobble_apron(name, width, depth, mats=None, seed=53, cobble=0.24,
                        exclude=None, location=(0, 0, 0), kerb=True,
                        weeds=True, thickness=0.14, stone="limestone"):
    """Individually set cobbles over a dirt bed, with kerb, ruts and weeds.

    exclude is (x0, y0, x1, y1) in local space - the building footprint, where
    cobbles would never be seen and are skipped.
    """
    obj, mesh, bm = _begin(name, _masonry_slots(mats, stone) +
                           [mats["M_Cobble_A"], mats["M_Cobble_B"],
                            mats["M_Cobble_Dirt"]])
    C_A, C_B, C_DIRT = 7, 8, 9
    rng = random.Random(seed)
    hw, hd = width * 0.5, depth * 0.5

    # Dirt bed under the setts, so gaps read as packed earth not holes
    _box(bm, C_DIRT, size=(width, depth, thickness),
         loc=(0, 0, -thickness * 0.5 + 0.02))

    def excluded(x, y):
        if not exclude:
            return False
        x0, y0, x1, y1 = exclude
        return x0 <= x <= x1 and y0 <= y <= y1

    n_rows = int(depth / cobble)
    row_d = depth / n_rows
    for r in range(n_rows):
        y = -hd + (r + 0.5) * row_d
        phase = rng.uniform(0, cobble)
        n_cols = int(width / cobble) + 1
        for c in range(n_cols):
            x = -hw + phase + (c + 0.5) * cobble
            if x > hw - 0.04 or x < -hw + 0.04:
                continue
            if excluded(x, y):
                continue
            if rng.random() < 0.035:      # missing sett -> dirt shows
                continue
            sx = cobble * rng.uniform(0.70, 0.94)
            sy = row_d * rng.uniform(0.70, 0.94)
            sz = rng.uniform(0.085, 0.135)
            sink = rng.uniform(-0.022, 0.012)
            mi = C_A if rng.random() < 0.55 else C_B
            if rng.random() < 0.10:
                mi = C_DIRT
            _box(bm, mi, size=(sx, sy, sz),
                 loc=(x + rng.uniform(-0.015, 0.015),
                      y + rng.uniform(-0.015, 0.015), sink),
                 rot=(rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05),
                      rng.uniform(-0.16, 0.16)), base=True)

            if weeds and rng.random() < 0.018:
                _weed_tuft(bm, M_WEED, (x + cobble * 0.5, y, sink + 0.02),
                           rng.uniform(0.07, 0.15), rng, blades=rng.randint(3, 6))
            if rng.random() < 0.020:
                _moss_clump(bm, M_MOSS, (x + cobble * 0.5, y, sink + 0.03),
                            rng.uniform(0.03, 0.06), rng, squash=0.3)

    # Kerb stones round the edge, individually laid
    if kerb:
        for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            run = hd if ax == 0 else hw
            n = max(4, int(run * 2 / 0.52))
            for i in range(n):
                t = (i + 0.5) / n
                c = -run + 2 * run * t
                L = (2 * run / n) - 0.03
                mi = rng.choice([M_BLK_A, M_BLK_B, M_BLK_C])
                if ax == 0:
                    _box(bm, mi, size=(0.16, L, rng.uniform(0.17, 0.22)),
                         loc=(sgn * (hw - 0.08), c, -0.04),
                         rot=(0, 0, rng.uniform(-0.02, 0.02)), base=True)
                else:
                    _box(bm, mi, size=(L, 0.16, rng.uniform(0.17, 0.22)),
                         loc=(c, sgn * (hd - 0.08), -0.04),
                         rot=(0, 0, rng.uniform(-0.02, 0.02)), base=True)

    obj.location = location
    return _end(obj, mesh, bm, bevel=0.010, segments=2)


# =============================================================================
# 8. WINDOW - leaded lights, strap-hinged shutters, planted box
# =============================================================================

W_TIMBER, W_GLOW, W_DIM, W_IRON, W_FOLIAGE, W_FLOWER, W_STONE, W_SOIL, W_CHIP = range(9)


def _window_slots(mats):
    return [mats["M_Timber_Aged"], mats["M_Window_Warm"], mats["M_Window_Dim"],
            mats["M_Iron_Aged"], mats["M_Foliage"], mats["M_Flowers"],
            mats["M_Stone_Block_A"], mats["M_Soil"], mats["M_Timber_Chip"]]


def _strap_hinge(bm, rng, origin, length, sign_x, iron_mat=W_IRON, thick=0.016):
    """Tapering iron strap with pintle barrel and three clenched nail heads."""
    segs = [(0.0, 0.085), (0.45, 0.062), (0.80, 0.040), (1.0, 0.022)]
    for i in range(len(segs) - 1):
        t0, h0 = segs[i]
        t1, h1 = segs[i + 1]
        x0 = origin[0] + sign_x * length * t0
        x1 = origin[0] + sign_x * length * t1
        _box(bm, iron_mat,
             size=(abs(x1 - x0), thick, (h0 + h1) * 0.5),
             loc=((x0 + x1) * 0.5, origin[1], origin[2]),
             rot=(0, 0, 0))
    # Pintle barrel at the hanging end
    _cyl(bm, iron_mat, 0.030, 0.10, (origin[0], origin[1], origin[2]),
         rot=(0, 0, 0), segments=8)
    for t in (0.20, 0.55, 0.88):
        _nail_head(bm, iron_mat,
                   (origin[0] + sign_x * length * t, origin[1] - thick * 0.9,
                    origin[2] + rng.uniform(-0.008, 0.008)),
                   rot=(pi / 2, 0, 0), radius=0.018)


def _shutter_leaf(bm, rng, width, height, thick=0.042, mat=W_TIMBER,
                  iron=W_IRON, chip=W_CHIP):
    """Ledged-and-braced shutter: three boards, two ledges, one diagonal brace."""
    n_boards = 3
    bw = width / n_boards
    for i in range(n_boards):
        x = -width * 0.5 + (i + 0.5) * bw
        _prism_beam(bm, mat, height, bw - 0.012, thick,
                    loc=(x, 0, -height * 0.5),
                    rot=(0, 0, 0), chamfer=0.008, rings=3,
                    bow=0.004, rng=rng, chips=1, chip_mat=chip, base=True)
    for z in (-height * 0.32, height * 0.32):
        _box(bm, mat, size=(width * 0.96, thick * 0.65, 0.075),
             loc=(0, thick * 0.72, z))
    _box(bm, mat, size=(width * 0.92, thick * 0.55, 0.055),
         loc=(0, thick * 0.70, 0), rot=(0, 0, 0.62))
    # Ring pull
    _cyl(bm, iron, 0.036, 0.012, (width * 0.30, -thick * 0.75, -height * 0.06),
         rot=(pi / 2, 0, 0), segments=10)
    _box(bm, iron, size=(0.045, 0.014, 0.045),
         loc=(width * 0.30, -thick * 0.62, -height * 0.02))


def create_window_detailed(name, width=0.88, height=1.15, mats=None, seed=61,
                           shutters=True, shutter_open=True, planter=True,
                           glow="warm", stone_sill=True, pane_cols=3,
                           pane_rows=4, moss=True):
    """Window facing -Y: leaded lights, chamfered pegged frame, working ironwork.

    Individual panes are separately lit and slightly out of plane, which is what
    makes a glazed opening read as hand-made rather than as a glowing rectangle.
    """
    obj, mesh, bm = _begin(name, _window_slots(mats) + [mats["M_Moss"]])
    W_MOSS = 9
    rng = random.Random(seed)
    fw, fd = 0.085, 0.11
    hw = width * 0.5

    # Chamfered, pegged frame
    for sgn in (-1, 1):
        _prism_beam(bm, W_TIMBER, height, fw, fd,
                    loc=(sgn * (hw - fw * 0.5), -fd * 0.5, 0.0),
                    chamfer=0.012, rings=4, bow=0.004, rng=rng, chips=2,
                    chip_mat=W_CHIP, base=True)
        _peg(bm, W_TIMBER, (sgn * (hw - fw * 0.5), -fd - 0.004, height - fw * 0.6),
             (pi / 2, 0, 0), radius=0.022, proud=0.012)
        _peg(bm, W_TIMBER, (sgn * (hw - fw * 0.5), -fd - 0.004, 0.10),
             (pi / 2, 0, 0), radius=0.022, proud=0.012)
    # Head / lintel with a shallow carved stop
    _prism_beam(bm, W_TIMBER, width + 0.16, 0.10, fd + 0.02,
                loc=(-(width + 0.16) * 0.5, -fd * 0.5, height - fw * 0.5),
                rot=(0, pi / 2, 0), chamfer=0.014, rings=4, bow=0.004, rng=rng,
                chips=2, chip_mat=W_CHIP, base=True)

    # Sill: weathered outward with a drip groove underneath
    sill_mat = W_STONE if stone_sill else W_TIMBER
    _box(bm, sill_mat, size=(width + 0.22, fd + 0.16, 0.085),
         loc=(0, -0.045, -0.02), rot=(-0.055, 0, 0))
    _box(bm, sill_mat, size=(width + 0.14, 0.025, 0.022),
         loc=(0, -fd - 0.055, -0.070))
    if moss:
        for sgn in (-1, 1):
            _moss_clump(bm, W_MOSS,
                        (sgn * (width * 0.5 + 0.055), -fd - 0.02, -0.015),
                        rng.uniform(0.035, 0.060), rng, squash=0.4)

    # Leaded lights: individual panes, separate brightness, slight cant
    gw = width - fw * 2.0 - 0.02
    gh = height - fw * 1.6
    gz0 = 0.07
    pw = gw / pane_cols
    ph = gh / pane_rows
    for i in range(pane_cols):
        for j in range(pane_rows):
            px = -gw * 0.5 + (i + 0.5) * pw
            pz = gz0 + (j + 0.5) * ph
            lit = W_GLOW if rng.random() < 0.72 else W_DIM
            _box(bm, lit, size=(pw - 0.016, 0.018, ph - 0.016),
                 loc=(px, -fd * 0.42, pz),
                 rot=(rng.uniform(-0.03, 0.03), 0, rng.uniform(-0.03, 0.03)))
    # Lead cames between the panes
    for i in range(1, pane_cols):
        _box(bm, W_IRON, size=(0.014, 0.026, gh),
             loc=(-gw * 0.5 + i * pw, -fd * 0.52, gz0 + gh * 0.5))
    for j in range(1, pane_rows):
        _box(bm, W_IRON, size=(gw, 0.026, 0.012),
             loc=(0, -fd * 0.52, gz0 + j * ph))
    # Heavier timber transom across the middle
    _box(bm, W_TIMBER, size=(gw + 0.03, 0.05, 0.045),
         loc=(0, -fd * 0.62, gz0 + gh * 0.52))

    # Shutters with strap hinges, hung back against the wall
    if shutters:
        sw = width * 0.50
        sh = height * 0.92
        for sgn in (-1, 1):
            hinge_x = sgn * (hw + 0.015)
            hinge_y = -fd * 0.45
            hinge_z = height * 0.5
            # Pintles driven into the frame
            for hz in (sh * 0.34, -sh * 0.30):
                _cyl(bm, W_IRON, 0.026, 0.075,
                     (hinge_x, hinge_y, hinge_z + hz),
                     rot=(0, pi / 2, 0), segments=8)

            # Leaf built centred, then swung about its hinge edge. Closed is
            # 180 deg (covering the light); open lays it back on the wall with
            # a few degrees of stand-off so it never z-fights the render.
            tmp = bmesh.new()
            _shutter_leaf(tmp, rng, sw, sh)
            for hz in (sh * 0.34, -sh * 0.30):
                _strap_hinge(tmp, rng, (-sw * 0.5 + 0.02, -0.030, hz),
                             sw * 0.80, 1)
            ang = radians(rng.uniform(5.0, 15.0)) if shutter_open else pi
            rotm = Matrix.Rotation(ang, 3, 'Z')
            pivot = Vector((-sw * 0.5, 0.0, 0.0))
            for v in tmp.verts:
                p = rotm @ (v.co - pivot)
                v.co = Vector((hinge_x + sgn * p.x, hinge_y + p.y,
                               hinge_z + p.z))
            tmp_mesh = bpy.data.meshes.new("_tmp_shutter")
            tmp.to_mesh(tmp_mesh)
            tmp.free()
            bm.from_mesh(tmp_mesh)
            bpy.data.meshes.remove(tmp_mesh)

            # Hold-back hook on the wall, catching the open leaf
            _box(bm, W_IRON, size=(0.022, 0.022, 0.11),
                 loc=(sgn * (hw + sw * 0.92), -0.03, hinge_z - 0.20))
            _box(bm, W_IRON, size=(0.05, 0.020, 0.020),
                 loc=(sgn * (hw + sw * 0.92), -0.06, hinge_z - 0.26))

    # Planted window box with individual blooms and trailing stems
    if planter:
        bw = width + 0.20
        _prism_beam(bm, W_TIMBER, bw, 0.055, 0.24,
                    loc=(-bw * 0.5, -fd - 0.14, -0.30), rot=(0, pi / 2, 0),
                    chamfer=0.010, rings=3, rng=rng, chips=1, chip_mat=W_CHIP,
                    base=True)
        _box(bm, W_TIMBER, size=(bw, 0.24, 0.045),
             loc=(0, -fd - 0.14, -0.315))
        for sgn in (-1, 1):
            _box(bm, W_TIMBER, size=(0.05, 0.24, 0.26),
                 loc=(sgn * bw * 0.5, -fd - 0.14, -0.185))
            _box(bm, W_IRON, size=(0.055, 0.012, 0.22),
                 loc=(sgn * bw * 0.34, -fd - 0.265, -0.185))
        _box(bm, W_SOIL, size=(bw - 0.09, 0.20, 0.06),
             loc=(0, -fd - 0.14, -0.105))
        for i in range(9):
            fx = -bw * 0.40 + i * (bw * 0.80 / 8.0)
            _blob(bm, W_FOLIAGE,
                  (fx + rng.uniform(-0.02, 0.02), -fd - 0.14 + rng.uniform(-0.04, 0.04),
                   -0.075 + rng.uniform(-0.01, 0.02)),
                  (rng.uniform(0.07, 0.11), rng.uniform(0.07, 0.11),
                   rng.uniform(0.05, 0.08)))
            for _ in range(rng.randint(1, 3)):
                _blob(bm, W_FLOWER,
                      (fx + rng.uniform(-0.05, 0.05),
                       -fd - 0.18 + rng.uniform(-0.04, 0.02),
                       -0.035 + rng.uniform(0.0, 0.05)),
                      (0.030, 0.030, 0.030))
        # Trailing growth over the front edge
        for _ in range(5):
            tx = rng.uniform(-bw * 0.42, bw * 0.42)
            L = rng.uniform(0.10, 0.24)
            _box(bm, W_FOLIAGE, size=(0.035, 0.035, L),
                 loc=(tx, -fd - 0.255, -0.20 - L * 0.5 + 0.08),
                 rot=(rng.uniform(-0.2, 0.2), 0, 0))

    return _end(obj, mesh, bm, bevel=0.007, segments=2, angle=40.0)


# =============================================================================
# 9. DOOR - planked, strapped, studded, with a worn threshold
# =============================================================================

def create_door_detailed(name, width=1.12, height=2.15, mats=None, seed=71,
                         speakeasy=True, moss=True):
    """Door facing -Y: five boards, forged straps, ring handle, worn threshold."""
    obj, mesh, bm = _begin(name, [
        mats["M_Timber_Aged"], mats["M_Wood_Planks"], mats["M_Iron_Aged"],
        mats["M_Stone_Block_A"], mats["M_Window_Warm"], mats["M_Timber_Chip"],
        mats["M_Moss"]])
    D_TIM, D_PLANK, D_IRON, D_STONE, D_GLOW, D_CHIP, D_MOSS = range(7)
    rng = random.Random(seed)
    hw = width * 0.5

    # Frame: chamfered posts and a carved lintel
    for sgn in (-1, 1):
        _prism_beam(bm, D_TIM, height + 0.12, 0.13, 0.17,
                    loc=(sgn * (hw + 0.065), 0, 0), chamfer=0.016, rings=4,
                    bow=0.006, rng=rng, chips=2, chip_mat=D_CHIP, base=True)
        _peg(bm, D_TIM, (sgn * (hw + 0.065), -0.09, height + 0.02),
             (pi / 2, 0, 0), radius=0.026, proud=0.013)
    _prism_beam(bm, D_TIM, width + 0.42, 0.16, 0.19,
                loc=(-(width + 0.42) * 0.5, 0, height + 0.12),
                rot=(0, pi / 2, 0), chamfer=0.018, rings=4, bow=0.005, rng=rng,
                chips=3, chip_mat=D_CHIP, base=True)
    # Shallow relief on the lintel so it is not a bare bar
    for i in range(5):
        x = -width * 0.40 + i * (width * 0.80 / 4.0)
        _box(bm, D_TIM, size=(0.055, 0.035, 0.055),
             loc=(x, -0.105, height + 0.19), rot=(0, 0, 0.78))

    # Leaf: five boards of unequal width, each chamfered and knocked about
    n = 5
    widths = [rng.uniform(0.85, 1.15) for _ in range(n)]
    tot = sum(widths)
    cursor = -hw
    for i in range(n):
        bw = (widths[i] / tot) * width
        x = cursor + bw * 0.5
        _prism_beam(bm, D_PLANK, height, bw - 0.012, 0.062,
                    loc=(x, -0.045, 0.0), chamfer=0.009, rings=4, bow=0.005,
                    rng=rng, chips=2, chip_mat=D_CHIP, base=True)
        cursor += bw

    # Ledges behind, visible at the edges
    for z in (height * 0.17, height * 0.82):
        _box(bm, D_TIM, size=(width * 0.97, 0.05, 0.10), loc=(0, 0.0, z))

    # Forged strap hinges across the full leaf width
    for z in (height * 0.19, height * 0.80):
        _strap_hinge(bm, rng, (-hw + 0.03, -0.085, z), width * 0.78, 1,
                     iron_mat=D_IRON, thick=0.020)

    # Clout nails in a diaper pattern
    for row in range(4):
        for col in range(4):
            if (row + col) % 2:
                continue
            _nail_head(bm, D_IRON,
                       (-hw + 0.16 + col * (width - 0.32) / 3.0,
                        -0.083,
                        0.30 + row * (height - 0.70) / 3.0),
                       rot=(pi / 2, 0, 0), radius=0.019)

    # Ring handle on a rosette, plus a thumb latch
    _cyl(bm, D_IRON, 0.075, 0.020, (hw - 0.20, -0.095, height * 0.46),
         rot=(pi / 2, 0, 0), segments=12)
    _cyl(bm, D_IRON, 0.048, 0.030, (hw - 0.20, -0.088, height * 0.46),
         rot=(pi / 2, 0, 0), segments=10)
    _box(bm, D_IRON, size=(0.075, 0.022, 0.075),
         loc=(hw - 0.20, -0.078, height * 0.46), rot=(0, 0.78, 0))
    _box(bm, D_IRON, size=(0.030, 0.020, 0.16),
         loc=(hw - 0.20, -0.088, height * 0.58))

    # Barred speakeasy with warm light behind it
    if speakeasy:
        gz = height * 0.76
        _box(bm, D_GLOW, size=(0.19, 0.020, 0.15), loc=(0, -0.020, gz))
        for i in range(3):
            _box(bm, D_IRON, size=(0.016, 0.030, 0.17),
                 loc=(-0.06 + i * 0.06, -0.078, gz))
        _box(bm, D_TIM, size=(0.27, 0.030, 0.035), loc=(0, -0.072, gz + 0.092))
        _box(bm, D_TIM, size=(0.27, 0.030, 0.035), loc=(0, -0.072, gz - 0.092))

    # Worn threshold stone, dished by traffic
    _box(bm, D_STONE, size=(width + 0.38, 0.42, 0.11), loc=(0, -0.13, 0.03),
         rot=(0.02, 0, 0))
    _box(bm, D_STONE, size=(width * 0.62, 0.30, 0.055), loc=(0, -0.15, 0.055),
         rot=(0.03, 0, 0))
    if moss:
        _moss_run(bm, D_MOSS, (-hw - 0.20, -0.32, 0.02), (hw + 0.20, -0.32, 0.02),
                  6, 0.045, rng, skip=0.5)

    return _end(obj, mesh, bm, bevel=0.007, segments=2, angle=40.0)


# =============================================================================
# 10. IRONWORK - lantern brackets, hanging lanterns, signs
# =============================================================================

def create_lantern_bracket(name, mats=None, seed=83, reach=0.48, lantern=True,
                           lit=True):
    """Wall-fixed forged bracket with a scrolled stay, chain, and lantern."""
    obj, mesh, bm = _begin(name, [
        mats["M_Iron_Aged"], mats["M_Lantern_Flame"], mats["M_Timber_Aged"],
        mats["M_Window_Warm"]])
    L_IRON, L_FLAME, L_TIM, L_GLOW = range(4)
    rng = random.Random(seed)

    # Wall plate with clenched nails
    _box(bm, L_IRON, size=(0.09, 0.030, 0.30), loc=(0, 0.015, 0))
    for z in (-0.115, 0.115):
        _nail_head(bm, L_IRON, (0, -0.012, z), rot=(pi / 2, 0, 0), radius=0.020)

    # Arm out from the wall, with a slight upward set
    _box(bm, L_IRON, size=(0.030, reach, 0.030),
         loc=(0, -reach * 0.5, 0.10), rot=(-0.06, 0, 0))
    # Scrolled stay under the arm
    steps = 7
    for i in range(steps):
        t = i / (steps - 1.0)
        ang = t * 2.4
        rad = 0.16 * (1.0 - t * 0.55)
        y = -reach * 0.22 - sin(ang) * rad - t * 0.16
        z = -0.02 - (1 - cos(ang)) * rad * 0.9
        _box(bm, L_IRON, size=(0.022, 0.055, 0.022), loc=(0, y, z),
             rot=(ang * 0.5, 0, 0))
    _box(bm, L_IRON, size=(0.026, 0.026, 0.20), loc=(0, -0.10, -0.045),
         rot=(0.5, 0, 0))
    # Curl finial at the arm tip
    _cyl(bm, L_IRON, 0.045, 0.022, (0, -reach - 0.02, 0.12),
         rot=(0, pi / 2, 0), segments=10)

    if lantern:
        # Chain: alternating links
        top_z = 0.10
        for i in range(3):
            _cyl(bm, L_IRON, 0.026, 0.014,
                 (0, -reach + 0.02, top_z - 0.035 - i * 0.055),
                 rot=(pi / 2 if i % 2 else 0, 0, 0), segments=8)

        lz = top_z - 0.24
        ly = -reach + 0.02
        # Lantern: four corner posts, four glazed faces, vented pyramid cap
        hs = 0.105
        for sx in (-1, 1):
            for sy in (-1, 1):
                _box(bm, L_IRON, size=(0.020, 0.020, 0.26),
                     loc=(sx * hs, ly + sy * hs, lz))
        for sx in (-1, 1):
            _box(bm, L_GLOW, size=(0.014, hs * 1.85, 0.22),
                 loc=(sx * hs, ly, lz))
        for sy in (-1, 1):
            _box(bm, L_GLOW, size=(hs * 1.85, 0.014, 0.22),
                 loc=(0, ly + sy * hs, lz))
        _box(bm, L_IRON, size=(hs * 2.3, hs * 2.3, 0.030), loc=(0, ly, lz - 0.145))
        _cyl(bm, L_IRON, hs * 1.55, 0.13, (0, ly, lz + 0.14), segments=4,
             radius2=0.012, base=True)
        _cyl(bm, L_IRON, 0.026, 0.05, (0, ly, lz + 0.27), segments=6, base=True)
        if lit:
            _blob(bm, L_FLAME, (0, ly, lz - 0.02), (0.055, 0.055, 0.085))

    return _end(obj, mesh, bm, bevel=0.005, segments=1, angle=45.0)


def create_hanging_sign_detailed(name, mats=None, seed=89, board_w=0.80,
                                 board_h=0.58, emblem="tankard"):
    """Bracket, chains, planked board with a raised carved emblem, and rust."""
    obj, mesh, bm = _begin(name, [
        mats["M_Iron_Aged"], mats["M_Timber_Aged"], mats["M_Sign_Paint"],
        mats["M_Gold_Brass"], mats["M_Paint_Green"], mats["M_Timber_Chip"]])
    S_IRON, S_TIM, S_PAINT, S_GOLD, S_GREEN, S_CHIP = range(6)
    rng = random.Random(seed)

    reach = 0.72
    _box(bm, S_IRON, size=(0.09, 0.032, 0.34), loc=(0, 0.016, 0))
    for z in (-0.13, 0.13):
        _nail_head(bm, S_IRON, (0, -0.014, z), rot=(pi / 2, 0, 0), radius=0.021)
    _box(bm, S_IRON, size=(0.034, reach, 0.034), loc=(0, -reach * 0.5, 0.12))
    # Diagonal stay with a scroll
    _box(bm, S_IRON, size=(0.026, 0.026, 0.46), loc=(0, -0.20, -0.06),
         rot=(0.72, 0, 0))
    for i in range(5):
        t = i / 4.0
        _box(bm, S_IRON, size=(0.020, 0.048, 0.020),
             loc=(0, -reach * 0.30 - t * 0.10, 0.02 - t * 0.10),
             rot=(t * 1.3, 0, 0))
    _cyl(bm, S_IRON, 0.05, 0.024, (0, -reach - 0.03, 0.14),
         rot=(0, pi / 2, 0), segments=10)

    # Chains
    for sy in (-0.28, 0.28):
        for i in range(2):
            _cyl(bm, S_IRON, 0.024, 0.013,
                 (0, -reach * 0.55 + sy, 0.085 - i * 0.050),
                 rot=(pi / 2 if i % 2 else 0, 0, 0), segments=8)

    # Board: three planks, framed, with chipped edges
    bz = -0.28
    by = -reach * 0.55
    for i in range(3):
        z = bz + (i - 1) * (board_h / 3.0)
        _prism_beam(bm, S_TIM, board_w, board_h / 3.0 - 0.008, 0.045,
                    loc=(-board_w * 0.5, by, z), rot=(0, pi / 2, 0),
                    chamfer=0.008, rings=3, bow=0.004, rng=rng, chips=1,
                    chip_mat=S_CHIP, base=True)
    for sx in (-1, 1):
        _box(bm, S_IRON, size=(0.024, 0.055, board_h + 0.05),
             loc=(sx * board_w * 0.5, by, bz))
    _box(bm, S_PAINT, size=(board_w - 0.05, 0.014, board_h - 0.05),
         loc=(0, by - 0.030, bz))

    # Raised carved emblem
    if emblem == "tankard":
        _cyl(bm, S_GOLD, 0.115, 0.030, (-0.04, by - 0.048, bz),
             rot=(pi / 2, 0, 0), segments=12)
        _cyl(bm, S_GOLD, 0.055, 0.022, (0.115, by - 0.048, bz + 0.01),
             rot=(pi / 2, 0, 0), segments=10)
        _box(bm, S_GREEN, size=(0.19, 0.016, 0.045), loc=(-0.04, by - 0.058, bz + 0.085))
    else:
        _blob(bm, S_GOLD, (0, by - 0.050, bz), (0.14, 0.022, 0.14), subdiv=1)

    return _end(obj, mesh, bm, bevel=0.005, segments=1, angle=45.0)


# =============================================================================
# 11. CLUTTER - barrels, crates, benches, firewood, garden beds
# =============================================================================

def create_barrel_detailed(name, mats=None, seed=97, radius=0.34, height=0.86,
                           open_top=False, tilted=False, mossy=False):
    """Coopered barrel: individual staves, four iron hoops, chime and rivets."""
    obj, mesh, bm = _begin(name, [
        mats["M_Wood_Planks"], mats["M_Iron_Aged"], mats["M_Water"],
        mats["M_Moss"], mats["M_Timber_Chip"]])
    B_WOOD, B_IRON, B_WATER, B_MOSS, B_CHIP = range(5)
    rng = random.Random(seed)

    n_staves = 14
    bulge = 1.14
    # Dark interior so the joints between staves read as shadow, not as a seam
    _cyl(bm, B_IRON, radius * 0.97, height * 0.98, (0, 0, height * 0.5),
         segments=16)
    for i in range(n_staves):
        ang = 2 * pi * i / n_staves
        r_mid = radius * bulge
        sw = 2 * pi * radius / n_staves * 0.76
        # Each stave: three rings, widest at the bilge
        for (z0, z1, r0, r1) in [(0.0, height * 0.5, radius, r_mid),
                                 (height * 0.5, height, r_mid, radius)]:
            rm = (r0 + r1) * 0.5
            # Tilt about the tangential axis so the stave follows the bilge
            tilt = -atan2(r1 - r0, z1 - z0)
            _box(bm, B_WOOD,
                 size=(sw * rng.uniform(0.94, 1.03), 0.055, (z1 - z0) * 1.02),
                 loc=(cos(ang) * rm, sin(ang) * rm, (z0 + z1) * 0.5),
                 rot=(tilt, 0.0, ang + pi / 2))
        if rng.random() < 0.12:
            _box(bm, B_CHIP, size=(sw * 0.5, 0.05, 0.07),
                 loc=(cos(ang) * radius * 1.02, sin(ang) * radius * 1.02,
                      rng.choice([0.03, height - 0.03])),
                 rot=(0, 0, ang + pi / 2))

    # Iron hoops - wider at the ends, narrower at the bilge
    for (hz, hr, hh) in [(0.055, radius * 1.02, 0.055),
                         (height * 0.30, radius * 1.10, 0.042),
                         (height * 0.70, radius * 1.10, 0.042),
                         (height - 0.055, radius * 1.02, 0.055)]:
        _cyl(bm, B_IRON, hr + 0.018, hh, (0, 0, hz), segments=16)
        for k in range(3):
            a2 = 2 * pi * k / 3 + rng.uniform(0, 1.0)
            _nail_head(bm, B_IRON,
                       (cos(a2) * (hr + 0.026), sin(a2) * (hr + 0.026), hz),
                       rot=(pi / 2, 0, a2), radius=0.015)

    # Head boards
    _cyl(bm, B_WOOD, radius * 0.97, 0.05, (0, 0, height - 0.035), segments=14)
    if open_top:
        _cyl(bm, B_WATER, radius * 0.92, 0.03, (0, 0, height - 0.07), segments=14)
    _cyl(bm, B_WOOD, radius * 0.97, 0.05, (0, 0, 0.030), segments=14)
    # Bung
    _cyl(bm, B_WOOD, 0.035, 0.030, (0, -radius * 1.10, height * 0.5),
         rot=(pi / 2, 0, 0), segments=8)

    if mossy:
        for _ in range(4):
            a2 = rng.uniform(0, 2 * pi)
            _moss_clump(bm, B_MOSS,
                        (cos(a2) * radius * 1.06, sin(a2) * radius * 1.06,
                         rng.uniform(0.04, 0.22)),
                        rng.uniform(0.035, 0.065), rng)

    if tilted:
        obj.rotation_euler = (radians(rng.uniform(78, 92)), 0,
                              radians(rng.uniform(0, 360)))
    return _end(obj, mesh, bm, bevel=0.008, segments=2)


def create_crate_detailed(name, mats=None, seed=101, size=0.62, lid=True,
                          stencil=True):
    """Boarded crate: gapped slats, corner cleats, iron corner brackets."""
    obj, mesh, bm = _begin(name, [
        mats["M_Wood_Planks"], mats["M_Iron_Aged"], mats["M_Timber_Aged"],
        mats["M_Sign_Paint"], mats["M_Timber_Chip"]])
    C_WOOD, C_IRON, C_TIM, C_PAINT, C_CHIP = range(5)
    rng = random.Random(seed)
    h = size * rng.uniform(0.82, 1.0)
    hs = size * 0.5

    n_slat = 4
    sh = h / n_slat
    for face in range(4):
        ang = face * pi / 2
        for i in range(n_slat):
            z = (i + 0.5) * sh
            _box(bm, C_WOOD, size=(size - 0.02, 0.035, sh - 0.016),
                 loc=(sin(ang) * hs, -cos(ang) * hs, z),
                 rot=(rng.uniform(-0.012, 0.012), 0, ang))
    # Corner cleats
    for sx in (-1, 1):
        for sy in (-1, 1):
            _prism_beam(bm, C_TIM, h, 0.062, 0.062,
                        loc=(sx * hs, sy * hs, 0), chamfer=0.008, rings=3,
                        rng=rng, chips=1, chip_mat=C_CHIP, base=True)
    # Iron corner brackets
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0.045, h - 0.045):
                _box(bm, C_IRON, size=(0.13, 0.022, 0.05),
                     loc=(sx * (hs - 0.04), sy * (hs + 0.012), z))
                _box(bm, C_IRON, size=(0.022, 0.13, 0.05),
                     loc=(sx * (hs + 0.012), sy * (hs - 0.04), z))
    if lid:
        for i in range(3):
            _box(bm, C_WOOD, size=(size - 0.02, size / 3.0 - 0.014, 0.042),
                 loc=(0, -size * 0.5 + (i + 0.5) * size / 3.0, h + 0.021),
                 rot=(0, rng.uniform(-0.01, 0.01), 0))
    if stencil:
        _box(bm, C_PAINT, size=(size * 0.44, 0.012, 0.10),
             loc=(0, -hs - 0.022, h * 0.55))

    return _end(obj, mesh, bm, bevel=0.007, segments=2)


def create_bench_detailed(name, mats=None, seed=103, length=1.5, mossy=True):
    """Plank bench: two slats, splayed legs, stretcher, iron strapping."""
    obj, mesh, bm = _begin(name, [
        mats["M_Timber_Aged"], mats["M_Wood_Planks"], mats["M_Iron_Aged"],
        mats["M_Moss"], mats["M_Timber_Chip"]])
    N_TIM, N_PLANK, N_IRON, N_MOSS, N_CHIP = range(5)
    rng = random.Random(seed)
    h, d = 0.48, 0.40

    for i, sy in enumerate((-1, 1)):
        _prism_beam(bm, N_PLANK, length, d * 0.46, 0.055,
                    loc=(-length * 0.5, sy * d * 0.26, h), rot=(0, pi / 2, 0),
                    chamfer=0.010, rings=4, bow=0.008, rng=rng, chips=2,
                    chip_mat=N_CHIP, base=True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _prism_beam(bm, N_TIM, h, 0.075, 0.075,
                        loc=(sx * (length * 0.5 - 0.15), sy * d * 0.30, 0),
                        rot=(0, sx * 0.06, 0), chamfer=0.010, rings=3,
                        rng=rng, chips=1, chip_mat=N_CHIP, base=True)
    for sx in (-1, 1):
        _prism_beam(bm, N_TIM, d * 0.70, 0.055, 0.055,
                    loc=(sx * (length * 0.5 - 0.15), -d * 0.35, h * 0.40),
                    rot=(-pi / 2, 0, 0), chamfer=0.008, rings=2, rng=rng,
                    base=True)
    _prism_beam(bm, N_TIM, length - 0.34, 0.048, 0.048,
                loc=(-(length - 0.34) * 0.5, 0, h * 0.34), rot=(0, pi / 2, 0),
                chamfer=0.008, rings=3, rng=rng, base=True)
    for sx in (-1, 1):
        _box(bm, N_IRON, size=(0.022, d * 0.80, 0.030),
             loc=(sx * (length * 0.5 - 0.15), 0, h - 0.045))
    if mossy:
        for sx in (-1, 1):
            _moss_clump(bm, N_MOSS,
                        (sx * (length * 0.5 - 0.15), d * 0.30, 0.03),
                        rng.uniform(0.04, 0.07), rng)

    return _end(obj, mesh, bm, bevel=0.006, segments=2)


def create_firewood_stack_detailed(name, mats=None, seed=107, width=1.25,
                                   depth=0.50, height=0.80):
    """Split logs stacked end-on, bark faces out, a couple fallen loose."""
    obj, mesh, bm = _begin(name, [
        mats["M_Timber_Aged"], mats["M_Timber_Chip"], mats["M_Moss"]])
    L_BARK, L_SPLIT, L_MOSS = range(3)
    rng = random.Random(seed)

    log_r = 0.062
    rows = int(height / (log_r * 2.0))
    cols = int(width / (log_r * 2.0))
    for r in range(rows):
        z = log_r + r * log_r * 2.0 * 0.96
        off = (log_r if r % 2 else 0.0)
        for c in range(cols):
            x = -width * 0.5 + log_r + off + c * log_r * 2.0
            if x > width * 0.5 - log_r * 0.5:
                continue
            rr = log_r * rng.uniform(0.82, 1.06)
            _cyl(bm, L_BARK, rr, depth * rng.uniform(0.9, 1.0),
                 (x, rng.uniform(-0.02, 0.02), z),
                 rot=(pi / 2, 0, rng.uniform(-0.05, 0.05)), segments=7)
            _cyl(bm, L_SPLIT, rr * 0.90, 0.02,
                 (x, -depth * 0.5 - 0.005, z), rot=(pi / 2, 0, 0), segments=7)
    for _ in range(3):
        _cyl(bm, L_BARK, log_r * rng.uniform(0.8, 1.0), depth * 0.9,
             (rng.uniform(-width * 0.5, width * 0.5),
              -depth * 0.5 - rng.uniform(0.12, 0.26), log_r),
             rot=(pi / 2, 0, rng.uniform(-0.6, 0.6)), segments=7)
    _moss_run(bm, L_MOSS, (-width * 0.5, -depth * 0.5, 0.02),
              (width * 0.5, -depth * 0.5, 0.02), 6, 0.05, rng, skip=0.5)

    return _end(obj, mesh, bm, bevel=0.005, segments=1, angle=45.0)


def create_garden_bed(name, mats=None, seed=109, width=1.9, depth=0.75,
                      edging="stone"):
    """Small kitchen garden: edging stones, tilled soil, plants, stray weeds."""
    obj, mesh, bm = _begin(name, [
        mats["M_Soil"], mats["M_Stone_Block_B"], mats["M_Foliage"],
        mats["M_Flowers"], mats["M_Weed_Green"], mats["M_Timber_Aged"],
        mats["M_Moss"]])
    G_SOIL, G_STONE, G_FOL, G_FLOWER, G_WEED, G_TIM, G_MOSS = range(7)
    rng = random.Random(seed)
    hw, hd = width * 0.5, depth * 0.5

    _box(bm, G_SOIL, size=(width, depth, 0.10), loc=(0, 0, 0), base=True)
    # Tilled ridges
    for i in range(int(width / 0.22)):
        x = -hw + 0.11 + i * 0.22
        _box(bm, G_SOIL, size=(0.16, depth * 0.9, 0.05),
             loc=(x, rng.uniform(-0.02, 0.02), 0.10),
             rot=(0, 0, rng.uniform(-0.04, 0.04)), base=True)

    # Edging
    if edging == "stone":
        for sgn, ax in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            run = hd if ax == 0 else hw
            n = max(3, int(run * 2 / 0.22))
            for i in range(n):
                t = (i + 0.5) / n
                c = -run + 2 * run * t
                s = rng.uniform(0.13, 0.19)
                loc = (sgn * hw, c, 0.0) if ax == 0 else (c, sgn * hd, 0.0)
                _blob(bm, G_STONE, (loc[0], loc[1], 0.055),
                      (s, s * rng.uniform(0.75, 1.1), s * rng.uniform(0.7, 1.0)),
                      rot=(0, 0, rng.uniform(0, pi)))
                if rng.random() < 0.25:
                    _moss_clump(bm, G_MOSS, (loc[0], loc[1], 0.09),
                                rng.uniform(0.03, 0.05), rng)
    else:
        for sgn in (-1, 1):
            _prism_beam(bm, G_TIM, width, 0.05, 0.16, loc=(-hw, sgn * hd, 0.0),
                        rot=(0, pi / 2, 0), chamfer=0.008, rings=3, rng=rng,
                        base=True)

    # Planting: cabbages, herbs, a few bright blooms, plus escaped weeds
    for i in range(int(width / 0.28)):
        x = -hw + 0.16 + i * 0.28
        for j in range(2):
            y = -hd * 0.45 + j * hd * 0.9
            if rng.random() < 0.18:
                continue
            s = rng.uniform(0.09, 0.15)
            cx_, cy_ = x + rng.uniform(-0.03, 0.03), y + rng.uniform(-0.04, 0.04)
            _blob(bm, G_FOL, (cx_, cy_, 0.145 + s * 0.22),
                  (s * 0.62, s * 0.62, s * 0.50), rot=(0, 0, rng.uniform(0, pi)))
            # Outer leaves, so a cabbage is not a ball
            for li in range(rng.randint(4, 6)):
                ang = 2 * pi * li / 5.0 + rng.uniform(-0.4, 0.4)
                _ivy_leaf(bm, G_FOL,
                          (cx_ + cos(ang) * s * 0.72,
                           cy_ + sin(ang) * s * 0.72, 0.135 + s * 0.20),
                          s * 1.15,
                          (rng.uniform(0.9, 1.5), 0.0, ang + pi * 0.5), rng)
            if rng.random() < 0.34:
                _blob(bm, G_FLOWER, (x, y, 0.17 + s * 0.6),
                      (0.035, 0.035, 0.035))
    for _ in range(6):
        _weed_tuft(bm, G_WEED,
                   (rng.uniform(-hw, hw), rng.uniform(-hd, hd), 0.12),
                   rng.uniform(0.09, 0.17), rng, blades=rng.randint(4, 7))

    return _end(obj, mesh, bm, bevel=0.007, segments=2)


def create_flower_box_standalone_detailed(name, mats=None, seed=113, length=1.3):
    """Planked planter with iron bands, soil, blooms and trailing growth."""
    obj, mesh, bm = _begin(name, [
        mats["M_Timber_Aged"], mats["M_Iron_Aged"], mats["M_Soil"],
        mats["M_Foliage"], mats["M_Flowers"], mats["M_Timber_Chip"]])
    B_TIM, B_IRON, B_SOIL, B_FOL, B_FLOWER, B_CHIP = range(6)
    rng = random.Random(seed)
    w, h = 0.30, 0.30

    for sy in (-1, 1):
        for i in range(2):
            _prism_beam(bm, B_TIM, length, h * 0.5 - 0.008, 0.045,
                        loc=(-length * 0.5, sy * w * 0.5, h * 0.25 + i * h * 0.5),
                        rot=(0, pi / 2, 0), chamfer=0.008, rings=3, bow=0.005,
                        rng=rng, chips=1, chip_mat=B_CHIP, base=True)
    for sx in (-1, 1):
        _box(bm, B_TIM, size=(0.045, w, h), loc=(sx * length * 0.5, 0, h * 0.5))
        _prism_beam(bm, B_TIM, 0.14, 0.07, 0.07,
                    loc=(sx * (length * 0.5 - 0.02), 0, -0.14),
                    chamfer=0.008, rings=2, rng=rng, base=True)
    _box(bm, B_TIM, size=(length, w, 0.035), loc=(0, 0, 0.018))
    for sx in (-0.28, 0.28):
        _box(bm, B_IRON, size=(0.035, w + 0.02, h * 0.92),
             loc=(sx * length, 0, h * 0.5))
    _box(bm, B_SOIL, size=(length - 0.08, w - 0.05, 0.06), loc=(0, 0, h - 0.045))

    n = max(4, int(length / 0.17))
    for i in range(n):
        x = -length * 0.42 + i * (length * 0.84 / max(1, n - 1))
        s = rng.uniform(0.07, 0.12)
        _blob(bm, B_FOL, (x + rng.uniform(-0.02, 0.02), rng.uniform(-0.04, 0.04),
                          h + s * 0.35),
              (s, s, s * 0.8), rot=(0, 0, rng.uniform(0, pi)))
        for _ in range(rng.randint(1, 3)):
            _blob(bm, B_FLOWER,
                  (x + rng.uniform(-0.05, 0.05), rng.uniform(-0.08, 0.02),
                   h + rng.uniform(0.03, 0.10)), (0.030, 0.030, 0.030))
    for _ in range(4):
        L = rng.uniform(0.10, 0.22)
        _box(bm, B_FOL, size=(0.035, 0.035, L),
             loc=(rng.uniform(-length * 0.4, length * 0.4), -w * 0.5 - 0.02,
                  h - 0.05 - L * 0.4),
             rot=(rng.uniform(-0.25, 0.25), 0, 0))

    return _end(obj, mesh, bm, bevel=0.006, segments=2)


def create_stone_steps_detailed(name, mats=None, seed=127, width=1.7, depth=1.05,
                                height=0.52, n_steps=3, kerbs=True,
                                stone="limestone"):
    """Steps built from separate worn slabs on a coursed cheek wall."""
    obj, mesh, bm = _begin(name, _masonry_slots(mats, stone))
    rng = random.Random(seed)
    sh = height / n_steps
    sd = depth / n_steps

    for i in range(n_steps):
        z = i * sh
        run_d = depth - i * sd
        # Tread built from two or three slabs with open joints
        n_slab = rng.choice([2, 3])
        weights = [rng.uniform(0.8, 1.2) for _ in range(n_slab)]
        tot_w = sum(weights)
        cursor = -width * 0.5
        for s in range(n_slab):
            sw = (weights[s] / tot_w) * width
            _box(bm, rng.choice([M_BLK_A, M_BLK_B, M_BLK_C]),
                 size=(sw - 0.02, run_d, sh),
                 loc=(cursor + sw * 0.5, -depth * 0.5 + run_d * 0.5, z),
                 rot=(rng.uniform(-0.008, 0.008), 0, rng.uniform(-0.006, 0.006)),
                 base=True)
            cursor += sw
        # Projecting nosing. Without it the flight reads as one solid ramp:
        # the overhang is what throws the shadow line that separates treads.
        _box(bm, rng.choice([M_BLK_A, M_BLK_C]),
             size=(width * 1.01, 0.13, sh * 0.42),
             loc=(0, -depth * 0.5 + run_d - 0.045, z + sh - sh * 0.21),
             rot=(rng.uniform(-0.006, 0.006), 0, 0))
        # Worn dish in the middle of the tread
        _box(bm, M_BLK_B, size=(width * 0.44, run_d * 0.55, 0.018),
             loc=(rng.uniform(-0.05, 0.05), -depth * 0.5 + run_d * 0.5,
                  z + sh - 0.008), rot=(0.01, 0, 0))
        # Moss and weeds in the riser joints
        _moss_run(bm, M_MOSS,
                  (-width * 0.5, -depth * 0.5 + run_d - 0.01, z + sh * 0.1),
                  (width * 0.5, -depth * 0.5 + run_d - 0.01, z + sh * 0.1),
                  5, 0.05, rng, skip=0.5)
        if rng.random() < 0.7:
            _weed_tuft(bm, M_WEED,
                       (rng.uniform(-width * 0.45, width * 0.45),
                        -depth * 0.5 + run_d, z + 0.01),
                       rng.uniform(0.08, 0.15), rng)

    # Cheek walls, stepping down with the flight so the treads stay visible.
    # A standalone flight reads better without them - at isometric angles the
    # near kerb plus the mass of the treads looks like a low wall.
    for sgn in ((-1, 1) if kerbs else ()):
        for i in range(n_steps):
            z = i * sh
            run_d = depth - i * sd
            # A low kerb per tread, not a full cheek wall: a wall this side
            # of the flight hides the treads completely at isometric angles.
            _box(bm, rng.choice([M_BLK_A, M_BLK_C]),
                 size=(0.15, run_d, 0.22),
                 loc=(sgn * (width * 0.5 + 0.07),
                      -depth * 0.5 + run_d * 0.5, z + sh),
                 rot=(0, 0, rng.uniform(-0.008, 0.008)), base=True)
            if rng.random() < 0.4:
                _moss_clump(bm, M_MOSS,
                            (sgn * (width * 0.5 + 0.07),
                             -depth * 0.5 + run_d * 0.5, z + sh + 0.24),
                            rng.uniform(0.05, 0.10), rng)

    return _end(obj, mesh, bm, bevel=0.010, segments=2)


def create_gable_infill(name, width, pitch_height, mats=None, seed=131,
                        depth=0.18, location=(0, 0, 0), rot_z=0.0):
    """Gable end: raked plaster panels between a braced apex frame."""
    obj, mesh, bm = _begin(name, [
        mats["M_Brick_Nogging"], mats["M_Plaster_Weathered"],
        mats["M_Plaster_Warm"], mats["M_Timber_Aged"], mats["M_Moss"],
        mats["M_Timber_Chip"], mats["M_Plaster_Repair"]])
    G_NOG, G_PL, G_WARM, G_TIM, G_MOSS, G_CHIP, G_REPAIR = range(7)
    rng = random.Random(seed)
    hw = width * 0.5

    # Solid triangular core built from stacked strips
    n = 14
    for i in range(n):
        t0 = i / n
        t1 = (i + 1) / n
        z = pitch_height * (t0 + t1) * 0.5
        strip_h = pitch_height / n
        # Width at the TOP of the strip: anything wider punches through the
        # rake of the roof, which the tiles sit directly on.
        w = width * (1.0 - t1)
        if w < 0.10:
            continue
        _box(bm, G_NOG, size=(w, depth * 0.62, strip_h + 0.004), loc=(0, 0, z))
        # Troweled coat in front, two tones, irregular but inside the rake
        cols = max(1, int(w / 0.30))
        for c in range(cols):
            cw = (w / cols) * rng.uniform(0.92, 1.12)
            cw = min(cw, w)
            cx = -w * 0.5 + (c + 0.5) * (w / cols)
            cx = max(-w * 0.5 + cw * 0.5, min(w * 0.5 - cw * 0.5, cx))
            r = rng.random()
            _box(bm, G_REPAIR if r < 0.14 else (G_WARM if r < 0.44 else G_PL),
                 size=(cw, depth * rng.uniform(0.22, 0.50),
                       strip_h * rng.uniform(0.94, 1.06)),
                 loc=(cx, -depth * 0.42, z),
                 rot=(rng.uniform(-0.01, 0.01), 0, rng.uniform(-0.01, 0.01)))

    # Apex frame: principal rafters, collar, king post, curved braces
    members = []
    for sgn in (-1, 1):
        members.append({"p0": (sgn * hw, -depth * 0.62, 0.0),
                        "p1": (0.0, -depth * 0.62, pitch_height),
                        "w": 0.16, "d": 0.13, "chips": 3, "pegs": [0.08, 0.92]})
    members.append({"p0": (-hw * 0.52, -depth * 0.62, pitch_height * 0.46),
                    "p1": (hw * 0.52, -depth * 0.62, pitch_height * 0.46),
                    "w": 0.15, "d": 0.13, "chips": 2, "pegs": [0.06, 0.94]})
    members.append({"p0": (0.0, -depth * 0.62, pitch_height * 0.46),
                    "p1": (0.0, -depth * 0.62, pitch_height - 0.04),
                    "w": 0.14, "d": 0.13, "chips": 2, "pegs": [0.10, 0.88]})
    for sgn in (-1, 1):
        members.append({"p0": (sgn * hw * 0.30, -depth * 0.62, 0.0),
                        "p1": (sgn * hw * 0.30, -depth * 0.62, pitch_height * 0.46),
                        "w": 0.12, "d": 0.12, "chips": 2, "pegs": [0.92]})
        members.append({"p0": (sgn * hw * 0.30, -depth * 0.62, pitch_height * 0.20),
                        "p1": (sgn * hw * 0.62, -depth * 0.62, pitch_height * 0.46),
                        "w": 0.10, "d": 0.11, "chips": 1})
    members.append({"p0": (-hw, -depth * 0.62, 0.0),
                    "p1": (hw, -depth * 0.62, 0.0),
                    "w": 0.18, "d": 0.15, "chips": 3, "moss": True,
                    "pegs": [0.12, 0.5, 0.88]})

    for m in members:
        p0, p1 = Vector(m["p0"]), Vector(m["p1"])
        d = p1 - p0
        L = d.length
        if L < 0.02:
            continue
        dirv = d.normalized()
        z_axis = Vector((0, 0, 1))
        if abs(dirv.dot(z_axis)) > 0.9999:
            rot = Euler((0, 0, 0)) if dirv.z > 0 else Euler((pi, 0, 0))
        else:
            rot = z_axis.rotation_difference(dirv).to_euler()
        _prism_beam(bm, G_TIM, L, m["w"], m["d"], loc=p0,
                    rot=(rot.x, rot.y, rot.z), chamfer=0.018, rings=5,
                    bow=L * 0.007, twist=rng.uniform(-0.03, 0.03), rng=rng,
                    chips=m.get("chips", 2), chip_mat=G_CHIP, base=True)
        for frac in m.get("pegs", []):
            pp = p0 + dirv * (L * frac)
            _peg(bm, G_TIM, (pp.x, pp.y - m["d"] * 0.5 - 0.004, pp.z),
                 (pi / 2, 0, 0), radius=0.028, proud=0.013)
        if m.get("moss"):
            _moss_run(bm, G_MOSS, (p0.x, p0.y - m["d"] * 0.6, p0.z),
                      (p1.x, p1.y - m["d"] * 0.6, p1.z),
                      max(3, int(L / 0.3)), 0.045, rng, skip=0.55)

    obj.location = location
    obj.rotation_euler = (0, 0, rot_z)
    return _end(obj, mesh, bm, bevel=0.007, segments=2, angle=40.0)


def create_corbel_bracket(name, mats=None, seed=137, size=0.42, projection=0.30):
    """Carved jetty corbel: stepped ogee profile, chamfered, pegged.

    Projects in -Y, sits under a bressummer. Built as a stack of boxes whose
    projection grows with height, which is how a real corbel transfers the
    overhang load back into the post below.
    """
    obj, mesh, bm = _begin(name, [mats["M_Timber_Aged"], mats["M_Timber_Chip"],
                                  mats["M_Moss"]])
    B_TIM, B_CHIP, B_MOSS = range(3)
    rng = random.Random(seed)

    n = 6
    for i in range(n):
        t = (i + 0.5) / n
        # ogee: slow start, fast finish
        proj = projection * (t ** 1.7)
        w = size * (0.62 + 0.38 * t)
        _box(bm, B_TIM, size=(w, proj + 0.10, size / n + 0.006),
             loc=(0, -(proj + 0.10) * 0.5 + 0.05, t * size),
             rot=(0, 0, rng.uniform(-0.004, 0.004)))
    # Squared head under the beam, with a roll moulding
    _box(bm, B_TIM, size=(size, projection + 0.16, 0.075),
         loc=(0, -(projection + 0.16) * 0.5 + 0.06, size + 0.030))
    _cyl(bm, B_TIM, 0.050, size * 0.96,
         (0, -projection - 0.05, size - 0.02), rot=(0, pi / 2, 0), segments=8)
    # Peg back into the post
    _peg(bm, B_TIM, (0, 0.028, size * 0.35), (pi / 2, 0, 0), radius=0.028,
         proud=0.014)
    if rng.random() < 0.6:
        _moss_clump(bm, B_MOSS, (0, -projection * 0.5, size + 0.06),
                    rng.uniform(0.030, 0.055), rng)
    return _end(obj, mesh, bm, bevel=0.008, segments=2, angle=40.0)


def create_pentice_canopy(name, width=1.9, depth=0.95, mats=None, seed=139,
                          pitch_deg=34.0):
    """Tiled door hood on carved brackets. Projects in -Y, tiles readable.

    Small enough that the tiles must stay coarse relative to the main roof or
    they stop reading at sprite resolution, so they use a wider gauge.
    """
    obj, mesh, bm = _begin(name, [
        mats["M_Timber_Aged"], mats["M_Tile_A"], mats["M_Tile_B"],
        mats["M_Tile_C"], mats["M_Tile_Aged"], mats["M_Moss"],
        mats["M_Timber_Chip"]])
    P_TIM, P_A, P_B, P_C, P_AGED, P_MOSS, P_CHIP = range(7)
    rng = random.Random(seed)
    a = radians(pitch_deg)
    hw = width * 0.5

    # Wall plate and brackets
    _prism_beam(bm, P_TIM, width, 0.085, 0.10, loc=(-hw, 0.0, 0.0),
                rot=(0, pi / 2, 0), chamfer=0.012, rings=3, rng=rng, chips=2,
                chip_mat=P_CHIP, base=True)
    for sgn in (-1, 1):
        for i in range(5):
            t = (i + 0.5) / 5.0
            proj = depth * 0.80 * (t ** 1.6)
            _box(bm, P_TIM, size=(0.085, proj + 0.08, 0.075),
                 loc=(sgn * (hw - 0.09), -(proj + 0.08) * 0.5, -0.42 + t * 0.42))
        _box(bm, P_TIM, size=(0.075, 0.075, 0.30),
             loc=(sgn * (hw - 0.09), -depth * 0.30, -0.30), rot=(0.7, 0, 0))

    # Rafters and boarding running down the slope
    slope_len = depth / cos(a)
    n_raft = 4
    for i in range(n_raft):
        x = -hw + 0.12 + i * ((width - 0.24) / (n_raft - 1))
        _prism_beam(bm, P_TIM, slope_len + 0.06, 0.055, 0.075,
                    loc=(x, 0.0, 0.03), rot=(pi / 2 + a, 0, 0), chamfer=0.008,
                    rings=3, rng=rng, chips=1, chip_mat=P_CHIP, base=True)

    # Tiles laid on the real slope plane. Rx(pi + a) sends a box's local +Y
    # down the slope and its local +Z along the (inverted, symmetric) normal.
    beta = pi + a

    def on_slope(s, x, lift):
        return (x, -cos(a) * s - sin(a) * lift, 0.03 - sin(a) * s + cos(a) * lift)

    n_rows = max(3, int(round(slope_len / 0.19)))
    exposure = slope_len / n_rows
    n_cols = max(5, int(round(width / 0.26)))
    col_w = width / n_cols
    for r in range(n_rows):
        s = (r + 0.5) * exposure
        stagger = (col_w * 0.5) if (r % 2) else 0.0
        for c in range(n_cols + 1):
            x = -hw + stagger + (c + 0.5) * col_w
            if x < -hw + col_w * 0.3 or x > hw - col_w * 0.3:
                continue
            mi = rng.choice([P_A, P_A, P_B, P_C, P_AGED])
            p = on_slope(s, x, 0.022)
            _box(bm, mi, size=(col_w - 0.013, exposure * 1.60, 0.046),
                 loc=p, rot=(beta + rng.uniform(-0.035, 0.035), 0,
                             rng.uniform(-0.035, 0.035)))
            if r == n_rows - 1 and rng.random() < 0.30:
                _moss_clump(bm, P_MOSS, on_slope(s + exposure * 0.4, x, 0.045),
                            rng.uniform(0.030, 0.055), rng, squash=0.45)

    # Ridge roll against the wall, and a fascia at the drip edge
    _cyl(bm, rng.choice([P_A, P_B, P_AGED]), 0.075, width * 0.98,
         (0, -0.045, 0.075), rot=(0, pi / 2, 0), segments=8)
    ep = on_slope(slope_len, 0.0, -0.030)
    _prism_beam(bm, P_TIM, width + 0.05, 0.045, 0.13,
                loc=(-(width + 0.05) * 0.5, ep[1], ep[2] - 0.045),
                rot=(0, pi / 2, 0), chamfer=0.010, rings=3, rng=rng, chips=2,
                chip_mat=P_CHIP, base=True)

    return _end(obj, mesh, bm, bevel=0.007, segments=2, angle=40.0)


def create_coated_box(name, width, depth, height, location=(0, 0, 0), mats=None,
                      seed=7, faces=("-Y", "+X"), coat=0.22, damage=2,
                      thickness=0.11, moss_base=False):
    """Solid wall core whose named faces carry a real troweled render coat.

    The blockout leaves the wall behind an opening as one flat plane, which is
    exactly where the eye lands. This gives that plane the same overlapping
    lime coats, tonal drift and fallen patches as a framed panel, so no part of
    an elevation is left as bare geometry.
    """
    obj, mesh, bm = _begin(name, [
        mats["M_Brick_Nogging"], mats["M_Plaster_Weathered"],
        mats["M_Plaster_Warm"], mats["M_Lath"], mats["M_Moss"],
        mats["M_Plaster_Repair"]])
    C_NOG, C_PL, C_WARM, C_LATH, C_MOSS, C_REPAIR = range(6)
    rng = random.Random(seed)
    hw, hd, hh = width * 0.5, depth * 0.5, height * 0.5

    _box(bm, C_NOG, size=(width, depth, height), loc=(0, 0, 0))

    for face in faces:
        axis = 0 if face in ("-X", "+X") else 1
        sgn = 1 if face in ("+X", "+Y") else -1
        run = hd if axis == 0 else hw          # half-extent along the face
        out = hw if axis == 0 else hd          # half-extent along the normal

        holes = [(rng.uniform(-0.78, 0.78), rng.uniform(-0.8, 0.6),
                  rng.uniform(0.10, 0.22), rng.uniform(0.12, 0.26))
                 for _ in range(damage)]

        def in_hole(u, v):
            for (hu, hv, ru, rv) in holes:
                if ((u - hu) / ru) ** 2 + ((v - hv) / rv) ** 2 < 1.0:
                    return True
            return False

        # Riven lath behind the coat, so a fallen patch has something in it
        n_lath = max(3, int(height / 0.20))
        for i in range(n_lath):
            z = -hh + (i + 0.5) * (height / n_lath)
            t = thickness * 0.30
            if axis == 0:
                _box(bm, C_LATH, size=(t, run * 2 * 0.99, height / n_lath * 0.58),
                     loc=(sgn * (out + t * 0.4), 0, z))
            else:
                _box(bm, C_LATH, size=(run * 2 * 0.99, t, height / n_lath * 0.58),
                     loc=(0, sgn * (out + t * 0.4), z))

        nu = max(3, int((run * 2) / coat))
        nv = max(3, int(height / coat))
        for i in range(nu):
            for j in range(nv):
                u = -1.0 + 2.0 * (i + 0.5) / nu
                v = -1.0 + 2.0 * (j + 0.5) / nv
                if in_hole(u, v):
                    continue
                pu = u * run + rng.uniform(-0.02, 0.02)
                pv = v * hh + rng.uniform(-0.02, 0.02)
                su = (run * 2 / nu) * rng.uniform(1.10, 1.45)
                sv = (height / nv) * rng.uniform(1.10, 1.45)
                pu = max(-run + su * 0.5, min(run - su * 0.5, pu))
                pv = max(-hh + sv * 0.5, min(hh - sv * 0.5, pv))
                th = thickness * rng.uniform(0.45, 1.05)
                r = rng.random()
                mi = C_REPAIR if r < 0.13 else (C_WARM if r < 0.43 else C_PL)
                if axis == 0:
                    _box(bm, mi, size=(th, su, sv),
                         loc=(sgn * (out + th * 0.45), pu, pv),
                         rot=(rng.uniform(-0.012, 0.012), 0,
                              rng.uniform(-0.012, 0.012)))
                else:
                    _box(bm, mi, size=(su, th, sv),
                         loc=(pu, sgn * (out + th * 0.45), pv),
                         rot=(0, rng.uniform(-0.012, 0.012),
                              rng.uniform(-0.012, 0.012)))

        # Ragged lip around each fallen patch
        for (hu, hv, ru, rv) in holes:
            for k in range(10):
                ang = 2 * pi * k / 10 + rng.uniform(-0.15, 0.15)
                pu = max(-run + 0.05, min(run - 0.05,
                                          (hu + cos(ang) * ru * 1.12) * run))
                pv = max(-hh + 0.05, min(hh - 0.05,
                                         (hv + sin(ang) * rv * 1.12) * hh))
                sz = rng.uniform(0.05, 0.12)
                th = thickness * rng.uniform(0.75, 1.1)
                if axis == 0:
                    _box(bm, C_PL, size=(th, sz, sz),
                         loc=(sgn * (out + th * 0.45), pu, pv))
                else:
                    _box(bm, C_PL, size=(sz, th, sz),
                         loc=(pu, sgn * (out + th * 0.45), pv))

        if moss_base:
            if axis == 0:
                _moss_run(bm, C_MOSS, (sgn * (out + 0.06), -run + 0.05, -hh + 0.03),
                          (sgn * (out + 0.06), run - 0.05, -hh + 0.03),
                          max(3, int(run * 2 / 0.22)), 0.06, rng, skip=0.45)
            else:
                _moss_run(bm, C_MOSS, (-run + 0.05, sgn * (out + 0.06), -hh + 0.03),
                          (run - 0.05, sgn * (out + 0.06), -hh + 0.03),
                          max(3, int(run * 2 / 0.22)), 0.06, rng, skip=0.45)

    obj.location = location
    return _end(obj, mesh, bm, bevel=0.008, segments=2)
