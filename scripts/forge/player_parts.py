"""Every piece of the EMBERGLASS player, one generator per part.

Sizes are authored in SPRITE PIXELS, not metres. The figure is 48 px tall for
1.85 world units, so PX = 0.03854 u, and `p(n)` converts.

Geometry is boxes and one 8-sided prism (a frustum -- same shape the old
`cone()` used, kept under a new name because the top is not always a point).
No bevel modifiers anywhere: a bevel would smear the per-face atlas UVs this
module builds, so painted edges (`player_paint.edges`) replace them.

Every face of every part is UV-unwrapped onto its own rectangle of a shared
atlas and painted with `player_paint` -- a brush for the blotchy base colour,
optional decals, optional band overrides (top/bottom rows, side columns).
`build_all()` creates the geometry; `paint_and_uv()` (called once, from
`build_player.py`, after every part exists) packs the atlas, paints every
tile and rewrites every mesh's UVs to point into it.

Imports bpy. Blender only. (`player_paint.py` is the numpy-only half of this
and is importable under plain CPython too.)
"""
import math
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

import player_paint as PP
from player_palette import shade8

WORLD_H = 1.85          # the figure's height, crest tip included
SPRITE_PX = 48
PX = WORLD_H / SPRITE_PX
TEXELS_PER_PX = 2        # 1 texel = 1 sprite pixel at the 96 px bake
# Vertex coords from bmesh are in WORLD UNITS (p() already applied); texel
# coords are in PX. Divide out PX before scaling by TEXELS_PER_PX, or every
# face's texel extent comes out ~26x too small (PX ~= 0.0385) and every tile
# collapses to 1x1.
_WORLD_TO_TEXEL = TEXELS_PER_PX / PX


def p(n):
    """px -> world units."""
    return n * PX


def _sfx(s):
    return "1" if s > 0 else "-1"


# --------------------------------------------------------------------------
# per-swatch default brush -- "The figure" below never passes `brush=`
# explicitly except where a face needs a DIFFERENT one from its part.
# --------------------------------------------------------------------------
_BRUSH_BY_SWATCH = {
    "steel": "steel", "steel_lit": "steel",
    "gold": "brass",
    "cream": "wool",
    "green_mid": "cloth", "green_deep": "cloth", "green_sleeve": "cloth",
    "leather": "leather", "leather_dk": "leather",
    "crest": "plume",
    "skin": "skin",
    "dark": "flat",
}


def _default_brush(swatch):
    return _BRUSH_BY_SWATCH.get(swatch, "flat")


def _default_edge_kind(facekey):
    if facekey in ("+z", "top"):
        return "top"
    if facekey in ("-z", "bottom"):
        return "bottom"
    return "side"


def _box_facekey(n):
    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
    if az >= ax and az >= ay:
        return "+z" if n.z > 0 else "-z"
    if ax >= ay:
        return "+x" if n.x > 0 else "-x"
    return "+y" if n.y > 0 else "-y"


def _uv_axes(n):
    """Per-face UV basis, in the LOCAL frame. Side faces (|n.z| < 0.7) get
    v_axis pointing up the face; ±Z-ish faces (the rest, including a steep
    taper) get v_axis = +Y outright. Either way u_axis = v_axis x n, which is
    what makes a -Y face read u=+X, v=+Z -- upright when viewed from outside.
    """
    n = n.normalized()
    if abs(n.z) < 0.7:
        v_axis = Vector((0, 0, 1)) - n * n.z
        if v_axis.length < 1e-9:
            return None
        v_axis.normalize()
    else:
        v_axis = Vector((0, 1, 0))
    u_axis = v_axis.cross(n)
    if u_axis.length < 1e-9:
        return None
    u_axis.normalize()
    return u_axis, v_axis


# --------------------------------------------------------------------------
# paint jobs -- one per face, queued as parts are built, resolved into the
# shared atlas by paint_and_uv() once every part exists.
# --------------------------------------------------------------------------

class _Job:
    __slots__ = ("part", "facekey", "swatch", "brush", "shade", "decals",
                 "edges_kind", "bands", "slit", "fringe", "fuller", "stitch",
                 "w", "h", "obj", "face_index", "pos", "key")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


JOBS = []


def _resolve_anchor(anchor, w, h, decal_name):
    """A small placement mini-language on top of `player_paint.stamp`'s own
    "center"/"center-low": ('center-x', row) centres horizontally at a fixed
    row, ('L'|'R', dx, dy) places relative to the left/right edge, dx/dy
    texels in. Concrete (col, row) tuples and the two strings pass through."""
    if isinstance(anchor, str):
        return anchor
    tag = anchor[0]
    if tag not in ("center-x", "L", "R"):
        return anchor
    rows, _legend = PP.DECALS[decal_name]
    dh, dw = len(rows), len(rows[0])
    if tag == "center-x":
        return ((w - dw) // 2, anchor[1])
    _, dx, dy = anchor
    col = dx if tag == "L" else w - dw - dx
    return (col, h - dh - dy)


def _make_job(part, facekey, swatch, base_brush, shade, ov, edges_on, w, h,
              face_index):
    f_swatch = ov.get("swatch", swatch)
    if "brush" in ov:
        f_brush = ov["brush"]
    elif "swatch" in ov:
        f_brush = _default_brush(f_swatch)
    else:
        f_brush = base_brush
    f_edges_on = ov.get("edges", edges_on)
    return _Job(
        part=part, facekey=facekey, swatch=f_swatch, brush=f_brush,
        shade=ov.get("shade", shade), decals=ov.get("decals", []),
        edges_kind=(_default_edge_kind(facekey) if f_edges_on else None),
        bands={"top_rows": ov.get("top_rows", []),
               "bottom_rows": ov.get("bottom_rows", []),
               "side_cols": ov.get("side_cols", [])},
        slit=ov.get("slit"), fringe=ov.get("fringe"),
        fuller=ov.get("fuller", False), stitch=None,
        w=w, h=h, obj=None, face_index=face_index, pos=None,
        key="%s:%s" % (part, facekey),
    )


def _finish(name, bm, metal):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o["metal"] = bool(metal)
    return o


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------

def box(name, centre, size, swatch, brush=None, shade=2, rot=(0, 0, 0),
        taper=None, faces=None, edges=True, metal=False, stitch=None):
    """A box, UV-mapped and paint-jobbed per face. `taper` scales the TOP
    face in X/Y. `faces` overrides swatch/brush/shade/decals/bands per
    facekey ('+x','-x','+y','-y','+z','-z'). `stitch` (a shade index) draws
    an alternating stitch line along the middle row of every SIDE face --
    used once, for the skirt hem.
    """
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((p(size[0]), p(size[1]), p(size[2]))),
                    verts=bm.verts)
    if taper:
        top = max(v.co.z for v in bm.verts)
        for v in bm.verts:
            if abs(v.co.z - top) < 1e-6:
                v.co.x *= taper[0]
                v.co.y *= taper[1]
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    base_brush = brush if brush is not None else _default_brush(swatch)
    face_ov = faces or {}
    jobs_here = []

    for f in bm.faces:
        facekey = _box_facekey(f.normal)
        axes = _uv_axes(f.normal)
        if axes is None:
            continue
        u_axis, v_axis = axes
        s_vals, t_vals = [], []
        for loop in f.loops:
            c = loop.vert.co
            s_vals.append(c.dot(u_axis) * _WORLD_TO_TEXEL)
            t_vals.append(c.dot(v_axis) * _WORLD_TO_TEXEL)
        s_min, t_min = min(s_vals), min(t_vals)
        w = max(1, math.ceil(max(s_vals) - s_min - 1e-6))
        h = max(1, math.ceil(max(t_vals) - t_min - 1e-6))
        for loop, s, t in zip(f.loops, s_vals, t_vals):
            loop[uv_layer].uv = (s - s_min, t - t_min)

        ov = face_ov.get(facekey, {})
        jobs_here.append(_make_job(name, facekey, swatch, base_brush, shade,
                                    ov, edges, w, h, f.index))

    if stitch is not None:
        for job in jobs_here:
            if job.facekey not in ("+z", "-z"):
                job.stitch = stitch

    for axis, deg in zip("XYZ", rot):
        if deg:
            bmesh.ops.rotate(bm, verts=bm.verts, cent=Vector((0, 0, 0)),
                             matrix=Matrix.Rotation(math.radians(deg), 3, axis))
    bmesh.ops.translate(bm, vec=Vector((p(centre[0]), p(centre[1]), p(centre[2]))),
                        verts=bm.verts)

    obj = _finish(name, bm, metal)
    for job in jobs_here:
        job.obj = obj
        JOBS.append(job)
    return obj


# --------------------------------------------------------------------------
# paint_and_uv -- pack every queued job into one atlas, paint it, rewrite UVs
# --------------------------------------------------------------------------

def paint_and_uv(objects):
    """Packs `JOBS` into a `player_paint.Atlas`, paints every tile and
    rewrites each mesh's "UVMap" from provisional local texel coords to
    normalised atlas UVs. Returns the composed atlas as uint8 [S,S,4]."""
    atlas = PP.Atlas()
    for job in JOBS:
        job.pos = atlas.add(job.key, job.w, job.h)

    tiles = {}
    for job in JOBS:
        w, h = job.w, job.h
        if job.fuller:
            # A flat-painted fuller groove, not the blotchy brush: the whole
            # face is the lit facet colour, with a darker channel down the
            # centre that stops short of the guard and the tip.
            tile = np.tile(np.array(shade8("steel_lit", 2), dtype=np.uint8),
                            (h, w, 1))
            c = w // 2
            r0, r1 = 2, h - 3
            if r1 > r0:
                tile[r0:r1, c, :] = shade8("steel", 1)
        else:
            seed = zlib.crc32(("%s:%s" % (job.part, job.facekey)).encode())
            idx = PP.brush(job.brush, w, h, job.shade, seed)
            if job.edges_kind:
                idx = PP.edges(idx, job.edges_kind)
            lut = np.array([shade8(job.swatch, k) for k in range(5)],
                           dtype=np.uint8)
            tile = lut[idx]

            for n, sw, sh in job.bands["top_rows"]:
                tile[0:n, :, :] = shade8(sw, sh)
            for n, sw, sh in job.bands["bottom_rows"]:
                tile[h - n:h, :, :] = shade8(sw, sh)
            for n, sw, sh in job.bands["side_cols"]:
                tile[:, 0:n, :] = shade8(sw, sh)
                tile[:, w - n:w, :] = shade8(sw, sh)

            if job.slit:
                sw, sh = job.slit
                rows = max(1, int(round(0.6 * h)))
                r0 = h - rows
                c0 = max(0, w // 2 - 1)
                c1 = min(w, c0 + 2)
                tile[r0:h, c0:c1, :] = shade8(sw, sh)

            if job.fringe:
                sw_a, sw_b, sh = job.fringe
                band_n = job.bands["bottom_rows"][-1][0] if job.bands["bottom_rows"] else 0
                row = h - band_n - 1
                if 0 <= row < h:
                    tile[row, 0::2, :] = shade8(sw_a, sh)
                    tile[row, 1::2, :] = shade8(sw_b, sh)

            if job.stitch is not None:
                row = h // 2
                tile[row, 0::2, :] = shade8(job.swatch, job.stitch)

        for dname, anchor in job.decals:
            PP.stamp(tile, dname, _resolve_anchor(anchor, w, h, dname))

        tiles[job.key] = tile

    rgba = atlas.compose(tiles)
    S = atlas.size
    for job in JOBS:
        x, y = job.pos
        me = job.obj.data
        uv_layer = me.uv_layers["UVMap"]
        poly = me.polygons[job.face_index]
        for li in poly.loop_indices:
            u_local, t_local = uv_layer.data[li].uv
            u = (x + u_local) / S
            v = 1.0 - (y + job.h - t_local) / S
            uv_layer.data[li].uv = (u, v)
    return rgba


# --------------------------------------------------------------------------
# the figure, section by section, in the order the reference sheet lists it.
# Bone group for each part is in [brackets] in the design notes; the actual
# bone -> part map lives in build_player.py.
# --------------------------------------------------------------------------

def head():
    """Open-face kettle helm over the chibi face: flat-topped dome, brass
    brim, and a steel cap block the plume grows from."""
    out = [
        prism("P_Helm", (0, 0, 39.1), 6.7, 5.2, 6.6, "steel", metal=True),
        prism("P_HelmCrown", (0, 0, 43.0), 5.2, 3.9, 1.2, "steel", metal=True),
        box("P_HelmCap", (0, 0, 44.3), (3.6, 3.6, 1.4), "steel", metal=True),
        prism("P_Brim", (0, 0, 35.2), 7.3, 7.3, 1.6, "gold", metal=True),
        box("P_Face", (0, 0, 31.5), (11.4, 9.6, 5.8), "skin", faces={
            "-y": {"decals": [("eyes", ("center-x", 3))], "edges": False,
                   "top_rows": [(1, "skin", 1)]},
        }),
    ]
    for s in (-1, 1):
        sfx = _sfx(s)
        out.append(box("P_Cheek_" + sfx, (s * 5.9, -1.0, 31.8), (1.4, 7.4, 5.2),
                       "steel", metal=True))
    out.append(box("P_Hair", (0, 4.2, 32.0), (10.8, 2.0, 4.8), "leather"))
    for s in (-1, 1):
        sfx = _sfx(s)
        out.append(box("P_HairTuft_" + sfx, (s * 5.3, 1.6, 32.6), (1.2, 2.0, 2.0),
                       "leather"))
    return out


def crest():
    """Red plume, curling forward and down over the front of the helm.

    Shifted 0.7 px lower than the design numbers: P_Plume_b's rotated
    back-top corner otherwise lands at z 48.65, over the height budget. The
    whole chain moves together so the curl itself is unchanged; the base
    sits slightly further into P_HelmCap, which is the block it grows from.
    """
    dz = -0.7
    return [
        box("P_Plume_a", (0, 0.4, 46.2 + dz), (3.8, 3.4, 2.6), "crest"),
        box("P_Plume_b", (0, -1.8, 47.0 + dz), (3.8, 3.6, 2.2), "crest",
            rot=(-20, 0, 0)),
        box("P_Plume_c", (0, -3.9, 45.6 + dz), (3.6, 2.6, 2.6), "crest",
            rot=(-55, 0, 0)),
        box("P_Plume_d", (0, -4.6, 43.9 + dz), (3.2, 2.0, 2.0), "crest",
            rot=(-80, 0, 0)),
    ]


def scarf():
    """Bulky cream wrap up to the chin."""
    out = [box("P_ScarfRoll", (0, 0, 27.9), (16.8, 12.6, 3.6), "cream")]
    for s in (-1, 1):
        sfx = _sfx(s)
        # roty = s*18: the drape's OUTER end (away from the body centreline)
        # is always local x = s*(+half-width), and z' = -x*sin(roty) needs to
        # come out lower there for either side -- solving that gives this sign.
        out.append(box("P_ScarfDrape_" + sfx, (s * 6.2, 0, 26.0), (6.0, 11.0, 2.2),
                       "cream", rot=(0, s * 18, 0)))
    out.append(box("P_ScarfKnot", (5.4, -4.6, 26.2), (3.2, 2.6, 3.6), "cream"))
    out.append(box("P_ScarfTail", (5.8, -5.0, 22.8), (2.6, 1.4, 5.0), "cream",
                   rot=(0, -8, 0)))
    return out


def shoulders():
    """Steel pauldrons, tapered narrower at the top, two rivets each."""
    out = []
    for s in (-1, 1):
        sfx = _sfx(s)
        out.append(box("P_Pauldron_" + sfx, (s * 8.6, 0, 26.4), (5.4, 6.6, 2.8),
                       "steel", metal=True, taper=(0.78, 0.84), faces={
                           "-y": {"decals": [("rivet", ("L", 2, 1)),
                                              ("rivet", ("R", 2, 1))]},
                       }))
    return out


def torso():
    return [
        box("P_Torso", (0, 0, 22.2), (13.0, 9.0, 7.0), "green_mid"),
        box("P_Baldric", (0.4, -5.4, 21.6), (2.2, 1.0, 14.2), "leather",
            rot=(0, -32, 0)),
        box("P_Medallion", (-4.4, -6.0, 24.4), (3.0, 1.2, 3.0), "gold",
            metal=True, faces={"-y": {"decals": [("boss", "center")]}}),
        box("P_StrapBuckle", (2.4, -6.0, 19.9), (2.2, 0.8, 2.0), "gold",
            metal=True, faces={"-y": {"decals": [("buckle", "center")]}}),
    ]


def arms():
    out = []
    for s in (-1, 1):
        sfx = _sfx(s)
        x = s * 8.6
        out.append(box("P_Sleeve_" + sfx, (x, 0, 22.8), (4.2, 4.6, 5.6),
                       "green_mid"))
        out.append(box("P_Cuff_" + sfx, (x, 0, 19.6), (4.6, 5.0, 1.4), "cream"))
        out.append(box("P_Gauntlet_" + sfx, (x, -0.4, 16.4), (5.0, 5.6, 4.4),
                       "leather"))
        out.append(box("P_GauntletCuff_" + sfx, (x, -0.4, 18.8), (5.6, 6.0, 1.4),
                       "leather_dk"))
    return out


def hips():
    out = [
        box("P_Belt", (0, 0, 18.0), (13.6, 9.4, 2.0), "leather"),
        box("P_Buckle", (0, -5.1, 18.0), (3.0, 1.0, 2.6), "gold", metal=True,
            faces={"-y": {"decals": [("buckle", "center")]}}),
        box("P_Skirt", (0, 0, 13.4), (14.2, 9.4, 7.2), "green_mid",
            taper=(0.90, 0.92), faces={"-y": {"slit": ("green_deep", 0)}}),
        box("P_SkirtHem", (0, 0, 10.3), (14.8, 9.8, 1.4), "cream", stitch=3),
        box("P_Satchel", (-7.6, -3.0, 13.6), (5.2, 3.4, 5.0), "leather"),
        box("P_SatchelFlap", (-7.6, -3.2, 15.6), (5.6, 3.8, 2.0), "leather_dk",
            faces={"-y": {"decals": [("buckle", "center-low")]}}),
        box("P_Pouch", (6.2, -3.2, 15.4), (2.8, 2.6, 3.0), "leather",
            faces={"-y": {"decals": [("buckle", "center")]}}),
        box("P_Scabbard", (-7.0, 2.6, 10.0), (2.6, 2.0, 11.0), "leather_dk",
            rot=(14, 0, 0)),
    ]
    # The chape sits where the scabbard's own (rotated) bottom end lands,
    # computed rather than eyeballed -- see the spec's own caveat about it.
    a = math.radians(14)
    half_h = 11.0 / 2
    ty = half_h * math.sin(a)
    tz = -half_h * math.cos(a)
    out.append(box("P_ScabbardTip", (-7.0, 2.6 + ty, 10.0 + tz), (3.0, 2.4, 1.4),
                   "gold", rot=(14, 0, 0), metal=True))
    return out


def legs():
    out = []
    for s in (-1, 1):
        sfx = _sfx(s)
        out.append(box("P_Leg_" + sfx, (s * 3.4, -0.3, 9.0), (4.4, 4.8, 3.4),
                       "leather_dk"))
    return out


def boots():
    """Strapped leather boots. The old gold cuff band is gone."""
    out = []
    for s in (-1, 1):
        sfx = _sfx(s)
        x = s * 3.6
        outer = "+x" if s > 0 else "-x"
        out.append(box("P_Boot_" + sfx, (x, -0.8, 3.6), (6.0, 8.0, 6.0),
                       "leather", taper=(0.92, 0.84)))
        out.append(box("P_Sole_" + sfx, (x, -0.8, 0.6), (6.4, 8.6, 1.2), "dark"))
        out.append(box("P_BootFold_" + sfx, (x, -0.6, 7.4), (6.8, 7.0, 2.0),
                       "leather", shade=3))
        out.append(box("P_BootStrap_" + sfx, (x, -0.8, 3.4), (6.4, 8.4, 1.0),
                       "leather_dk",
                       faces={outer: {"decals": [("buckle", "center")]}}))
    return out


def cape():
    """Two segments, green outside / cream inside, a wide cream border and
    the tree upright on the back."""
    return [
        box("P_Cape_a", (0, 5.2, 21.4), (25.0, 1.4, 12.4), "green_mid",
            taper=(0.62, 1.0), faces={
                "-y": {"swatch": "cream", "brush": "wool"},
                "+y": {"side_cols": [(2, "cream", 2)],
                       "decals": [("tree", "center-low")]},
                "+x": {"swatch": "cream"},
                "-x": {"swatch": "cream"},
            }),
        box("P_Cape_b", (0, 5.8, 10.5), (24.0, 1.4, 9.4), "green_mid",
            taper=(1.042, 1.0), faces={
                "-y": {"swatch": "cream", "brush": "wool"},
                "+y": {"side_cols": [(2, "cream", 2)],
                       "bottom_rows": [(5, "cream", 2)],
                       "fringe": ("cream", "green_mid", 2)},
                "+x": {"swatch": "cream"},
                "-x": {"swatch": "cream"},
                "-z": {"swatch": "cream"},
            }),
    ]


def sword():
    """Longsword, point down, held in the +X hand."""
    x = 8.9
    return [
        box("P_Sword_Grip", (x, -1.4, 16.2), (1.6, 1.6, 3.2), "leather_dk"),
        box("P_Pommel", (x, -1.4, 18.4), (2.4, 2.4, 1.4), "gold", metal=True),
        box("P_Sword_Guard", (x, -1.4, 13.9), (6.0, 1.8, 1.4), "gold",
            metal=True),
        box("P_Sword_Blade", (x, -1.4, 7.9), (2.4, 1.0, 10.6), "steel",
            metal=True, faces={"+y": {"fuller": True}, "-y": {"fuller": True}}),
        box("P_Sword_Tip", (x, -1.4, 1.8), (2.4, 1.0, 1.6), "steel", metal=True,
            taper=(0.12, 0.12)),
    ]


ALL = (head, crest, scarf, shoulders, torso, arms, hips, legs, boots, cape,
       sword)


def build_all():
    """Every part, linked into the scene. Returns the object list."""
    JOBS.clear()
    out = []
    for fn in ALL:
        out.extend(fn())
    return out


def prism(name, centre, r_base, r_top, height, swatch, brush=None, shade=2,
          sides=8, faces=None, edges=True, metal=False):
    """The 8-sided frustum -- same construction as the old `cone()`, 22.5 deg
    rotation so a FACE sits toward the camera, not an edge. Flat n-gon caps.
    Facekeys: 'top', 'bottom', 'side0'..'side{sides-1}'; 'front' is accepted
    as an alias for the side whose normal is closest to -Y.
    """
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=sides,
                          radius1=p(r_base), radius2=p(r_top), depth=p(height))
    bmesh.ops.rotate(bm, verts=bm.verts, cent=Vector((0, 0, 0)),
                     matrix=Matrix.Rotation(math.radians(22.5), 3, "Z"))
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    base_brush = brush if brush is not None else _default_brush(swatch)
    face_ov = faces or {}

    side_faces = [f for f in bm.faces if abs(f.normal.z) < 0.9]
    cap_faces = [f for f in bm.faces if abs(f.normal.z) >= 0.9]
    side_faces.sort(key=lambda f: math.atan2(
        sum(v.co.y for v in f.verts), sum(v.co.x for v in f.verts)))
    facekeys = {f.index: "side%d" % i for i, f in enumerate(side_faces)}
    front_f = min(side_faces, key=lambda f: (f.normal.normalized() -
                                              Vector((0, -1, 0))).length)
    front_key = facekeys[front_f.index]
    for f in cap_faces:
        facekeys[f.index] = "top" if f.normal.z > 0 else "bottom"

    jobs_here = []
    for f in bm.faces:
        facekey = facekeys[f.index]
        axes = _uv_axes(f.normal)
        if axes is None:
            continue
        u_axis, v_axis = axes
        s_vals, t_vals = [], []
        for loop in f.loops:
            c = loop.vert.co
            s_vals.append(c.dot(u_axis) * _WORLD_TO_TEXEL)
            t_vals.append(c.dot(v_axis) * _WORLD_TO_TEXEL)
        s_min, t_min = min(s_vals), min(t_vals)
        w = max(1, math.ceil(max(s_vals) - s_min - 1e-6))
        h = max(1, math.ceil(max(t_vals) - t_min - 1e-6))
        for loop, s, t in zip(f.loops, s_vals, t_vals):
            loop[uv_layer].uv = (s - s_min, t - t_min)

        ov = face_ov.get(facekey) or (
            face_ov.get("front") if facekey == front_key else None) or {}
        jobs_here.append(_make_job(name, facekey, swatch, base_brush, shade,
                                    ov, edges, w, h, f.index))

    bmesh.ops.translate(bm, vec=Vector((p(centre[0]), p(centre[1]), p(centre[2]))),
                        verts=bm.verts)
    obj = _finish(name, bm, metal)
    for job in jobs_here:
        job.obj = obj
        JOBS.append(job)
    return obj
